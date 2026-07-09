from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


Box = tuple[int, int, int, int]


def crop_box(frame: np.ndarray, box: Box) -> np.ndarray | None:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    x1 = min(max(0, x1), width - 1)
    y1 = min(max(0, y1), height - 1)
    x2 = min(max(x1 + 1, x2), width)
    y2 = min(max(y1 + 1, y2), height)
    crop = frame[y1:y2, x1:x2]
    return crop if crop.size else None


def crop_appearance_context(frame: np.ndarray, box: Box) -> np.ndarray | None:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    face_width = max(1, x2 - x1)
    face_height = max(1, y2 - y1)
    left = int(x1 - face_width * 0.45)
    right = int(x2 + face_width * 0.45)
    top = int(y1 + face_height * 0.35)
    bottom = int(y2 + face_height * 1.10)
    return crop_box(frame, (left, top, min(width, right), min(height, bottom)))


def crop_person_shirt_context(frame: np.ndarray, box: Box) -> np.ndarray | None:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    box_height = max(1, y2 - y1)
    top = int(y1 + box_height * 0.48)
    bottom = int(y2 - box_height * 0.04)
    left = int(x1 + (x2 - x1) * 0.12)
    right = int(x2 - (x2 - x1) * 0.12)
    return crop_box(frame, (left, top, min(width, right), min(height, bottom)))


def crop_person_torso_context(frame: np.ndarray, box: Box) -> np.ndarray | None:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    box_height = max(1, y2 - y1)
    top = int(y1 + box_height * 0.28)
    bottom = int(y2 - box_height * 0.10)
    left = int(x1 + (x2 - x1) * 0.08)
    right = int(x2 - (x2 - x1) * 0.08)
    return crop_box(frame, (left, top, min(width, right), min(height, bottom)))


def crop_rotation_variants(crop: np.ndarray) -> list[np.ndarray]:
    return [
        crop,
        cv2.rotate(crop, cv2.ROTATE_180),
        cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]


@dataclass(slots=True)
class SimilarityScore:
    total: float
    template: float
    histogram: float
    context: float = 0.0


@dataclass(slots=True)
class FaceSignature:
    template: np.ndarray
    histogram: np.ndarray

    @classmethod
    def from_crop(cls, crop: np.ndarray) -> "FaceSignature":
        resized = cv2.resize(crop, (48, 48), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray).astype(np.float32) / 255.0

        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        histogram = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
        cv2.normalize(histogram, histogram)
        return cls(template=gray, histogram=histogram)

    def compare(self, other: "FaceSignature") -> SimilarityScore:
        hist_score = float(cv2.compareHist(self.histogram, other.histogram, cv2.HISTCMP_CORREL))
        mse = float(np.mean((self.template - other.template) ** 2))
        template_score = max(0.0, 1.0 - mse * 6.0)
        total = (hist_score * 0.35) + (template_score * 0.65)
        return SimilarityScore(total=total, template=template_score, histogram=hist_score)

    def similarity(self, other: "FaceSignature") -> float:
        return self.compare(other).total


@dataclass(slots=True)
class AppearanceSignature:
    face: FaceSignature
    context_histogram: np.ndarray | None

    @classmethod
    def from_frame(cls, frame: np.ndarray, box: Box) -> "AppearanceSignature | None":
        face_crop = crop_box(frame, box)
        if face_crop is None:
            return None
        context_crop = crop_appearance_context(frame, box)
        context_histogram = context_histogram_from_crop(context_crop) if context_crop is not None else None
        return cls(face=FaceSignature.from_crop(face_crop), context_histogram=context_histogram)


@dataclass(slots=True)
class PersonSignature:
    template: np.ndarray
    histogram: np.ndarray
    shirt_histogram: np.ndarray | None
    torso_histogram: np.ndarray | None

    @classmethod
    def from_crop(cls, crop: np.ndarray) -> "PersonSignature":
        resized = cv2.resize(crop, (64, 96), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray).astype(np.float32) / 255.0

        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        histogram = cv2.calcHist([hsv], [0, 1, 2], None, [18, 12, 8], [0, 180, 0, 256, 0, 256])
        cv2.normalize(histogram, histogram)
        return cls(template=gray, histogram=histogram, shirt_histogram=None, torso_histogram=None)

    @classmethod
    def from_frame(cls, frame: np.ndarray, box: Box) -> "PersonSignature | None":
        crop = crop_box(frame, box)
        if crop is None:
            return None
        signature = cls.from_crop(crop)
        shirt_crop = crop_person_shirt_context(frame, box)
        if shirt_crop is not None:
            shirt_hsv = cv2.cvtColor(cv2.resize(shirt_crop, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV)
            shirt_histogram = cv2.calcHist([shirt_hsv], [0, 1, 2], None, [18, 12, 8], [0, 180, 0, 256, 0, 256])
            cv2.normalize(shirt_histogram, shirt_histogram)
            signature.shirt_histogram = shirt_histogram
        torso_crop = crop_person_torso_context(frame, box)
        if torso_crop is not None:
            torso_hsv = cv2.cvtColor(cv2.resize(torso_crop, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV)
            torso_histogram = cv2.calcHist([torso_hsv], [0, 1, 2], None, [18, 12, 8], [0, 180, 0, 256, 0, 256])
            cv2.normalize(torso_histogram, torso_histogram)
            signature.torso_histogram = torso_histogram
        return signature

    def compare(self, other: "PersonSignature") -> SimilarityScore:
        hist_score = float(cv2.compareHist(self.histogram, other.histogram, cv2.HISTCMP_CORREL))
        mse = float(np.mean((self.template - other.template) ** 2))
        template_score = max(0.0, 1.0 - mse * 4.0)
        shirt_score = 0.0
        if self.shirt_histogram is not None and other.shirt_histogram is not None:
            shirt_score = float(cv2.compareHist(self.shirt_histogram, other.shirt_histogram, cv2.HISTCMP_CORREL))
        torso_score = 0.0
        if self.torso_histogram is not None and other.torso_histogram is not None:
            torso_score = float(cv2.compareHist(self.torso_histogram, other.torso_histogram, cv2.HISTCMP_CORREL))
        total = (hist_score * 0.25) + (template_score * 0.10) + (shirt_score * 0.40) + (torso_score * 0.25)
        context_score = max(shirt_score, torso_score)
        return SimilarityScore(total=total, template=template_score, histogram=hist_score, context=context_score)


def context_histogram_from_crop(crop: np.ndarray) -> np.ndarray:
    resized = cv2.resize(crop, (64, 64), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1, 2], None, [18, 12, 8], [0, 180, 0, 256, 0, 256])
    cv2.normalize(histogram, histogram)
    return histogram


def compare_context(first: np.ndarray | None, second: np.ndarray | None) -> float:
    if first is None or second is None:
        return 0.0
    return float(cv2.compareHist(first, second, cv2.HISTCMP_CORREL))


class FaceMemory:
    def __init__(
        self,
        kind: str = "face",
        threshold: float = 0.78,
        min_template_score: float = 0.68,
        min_histogram_score: float = 0.20,
        context_assisted_threshold: float = 0.62,
        min_context_score: float = 0.54,
        person_threshold: float = 0.68,
        person_min_histogram_score: float = 0.45,
    ) -> None:
        self.kind = kind
        self.threshold = threshold
        self.min_template_score = min_template_score
        self.min_histogram_score = min_histogram_score
        self.context_assisted_threshold = context_assisted_threshold
        self.min_context_score = min_context_score
        self.person_threshold = person_threshold
        self.person_min_histogram_score = person_min_histogram_score
        self.signatures: list[AppearanceSignature | PersonSignature] = []

    def __len__(self) -> int:
        return len(self.signatures)

    def clear(self) -> None:
        self.signatures.clear()

    def remember(self, frame: np.ndarray, box: Box) -> bool:
        if self.matches(frame, box):
            return False
        signature = self._signature_from_frame(frame, box)
        if signature is None:
            return False
        self.signatures.append(signature)
        return True

    def split_detections(self, frame: np.ndarray, detections: list[Box]) -> tuple[list[Box], list[Box]]:
        remembered: list[Box] = []
        unknown: list[Box] = []
        for detection in detections:
            if self.matches(frame, detection):
                remembered.append(detection)
            else:
                unknown.append(detection)
        return unknown, remembered

    def forget(self, frame: np.ndarray, box: Box) -> bool:
        if not self.signatures:
            return False
        if self.kind == "person":
            candidate = PersonSignature.from_frame(frame, box)
            if candidate is None:
                return False
            for index, signature in enumerate(self.signatures):
                if not isinstance(signature, PersonSignature):
                    continue
                score = signature.compare(candidate)
                if score.total >= self.person_threshold and score.histogram >= self.person_min_histogram_score:
                    del self.signatures[index]
                    return True
            return False

        candidates = self._face_candidates(frame, box)
        if not candidates:
            return False
        context_crop = crop_appearance_context(frame, box)
        context_histogram = context_histogram_from_crop(context_crop) if context_crop is not None else None
        for index, signature in enumerate(self.signatures):
            if not isinstance(signature, AppearanceSignature):
                continue
            for candidate in candidates:
                score = signature.face.compare(candidate)
                context_score = compare_context(signature.context_histogram, context_histogram)
                if self._is_match(score, context_score):
                    del self.signatures[index]
                    return True
        return False

    def matches(self, frame: np.ndarray, box: Box) -> bool:
        if not self.signatures:
            return False
        if self.kind == "person":
            return self._matches_person(frame, box)
        candidates = self._face_candidates(frame, box)
        if not candidates:
            return False
        context_crop = crop_appearance_context(frame, box)
        context_histogram = context_histogram_from_crop(context_crop) if context_crop is not None else None
        return any(
            self._is_match(
                signature.face.compare(candidate),
                compare_context(signature.context_histogram, context_histogram),
            )
            for signature in self.signatures
            for candidate in candidates
        )

    def _signature_from_frame(self, frame: np.ndarray, box: Box) -> AppearanceSignature | PersonSignature | None:
        if self.kind == "person":
            return PersonSignature.from_frame(frame, box)
        return AppearanceSignature.from_frame(frame, box)

    def _matches_person(self, frame: np.ndarray, box: Box) -> bool:
        candidate = PersonSignature.from_frame(frame, box)
        if candidate is None:
            return False
        for signature in self.signatures:
            if not isinstance(signature, PersonSignature):
                continue
            score = signature.compare(candidate)
            if (
                score.total >= self.person_threshold
                and score.histogram >= self.person_min_histogram_score
                and score.context >= 0.25
            ):
                return True
        return False

    def _face_candidates(self, frame: np.ndarray, box: Box) -> list[FaceSignature]:
        crop = crop_box(frame, box)
        if crop is None:
            return []
        candidates: list[FaceSignature] = []
        for variant in crop_rotation_variants(crop):
            candidates.append(FaceSignature.from_crop(variant))
        return candidates

    def _is_match(self, score: SimilarityScore, context_score: float) -> bool:
        strict_face_match = (
            score.total >= self.threshold
            and score.template >= self.min_template_score
            and score.histogram >= self.min_histogram_score
        )
        if strict_face_match:
            return True
        if context_score >= 0.90 and score.histogram >= 0.92:
            return True
        return (
            context_score >= self.min_context_score
            and score.total >= self.context_assisted_threshold
            and score.template >= 0.38
            and score.histogram >= 0.05
        )
