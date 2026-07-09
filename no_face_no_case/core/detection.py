from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

Box = tuple[int, int, int, int]


def rotate_frame(frame: np.ndarray, angle: int) -> np.ndarray:
    if angle == 0:
        return frame
    if angle == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Unsupported rotation angle: {angle}")


def map_box_to_original(box: Box, angle: int, original_width: int, original_height: int) -> Box:
    x1, y1, x2, y2 = box
    if angle == 0:
        mapped = (x1, y1, x2, y2)
    elif angle == 90:
        mapped = (y1, original_height - x2, y2, original_height - x1)
    elif angle == 180:
        mapped = (original_width - x2, original_height - y2, original_width - x1, original_height - y1)
    elif angle == 270:
        mapped = (original_width - y2, x1, original_width - y1, x2)
    else:
        raise ValueError(f"Unsupported rotation angle: {angle}")

    mx1, my1, mx2, my2 = mapped
    return (
        min(max(0, int(mx1)), original_width - 1),
        min(max(0, int(my1)), original_height - 1),
        min(max(1, int(mx2)), original_width),
        min(max(1, int(my2)), original_height),
    )


def box_area(box: Box) -> int:
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def box_intersection_area(first: Box, second: Box) -> int:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    width = max(0, min(ax2, bx2) - max(ax1, bx1))
    height = max(0, min(ay2, by2) - max(ay1, by1))
    return width * height


def box_iou(first: Box, second: Box) -> float:
    intersection = box_intersection_area(first, second)
    union = box_area(first) + box_area(second) - intersection
    return intersection / union if union else 0.0


def suppress_duplicate_boxes(boxes: list[Box], iou_threshold: float = 0.35, containment_threshold: float = 0.70) -> list[Box]:
    kept: list[Box] = []
    for box in sorted(boxes, key=box_area, reverse=True):
        area = box_area(box)
        if area <= 0:
            continue
        duplicate = False
        for kept_box in kept:
            intersection = box_intersection_area(box, kept_box)
            smaller_area = max(1, min(area, box_area(kept_box)))
            if box_iou(box, kept_box) >= iou_threshold or intersection / smaller_area >= containment_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(box)
    return kept


class FaceDetector:
    """Lazy face detector with YOLO first and OpenCV Haar as a portable fallback."""

    def __init__(self, model_path: Path | None = None, allowed_class_names: set[str] | None = None) -> None:
        self.model_path = model_path
        self.allowed_class_names = allowed_class_names
        self._model = None
        self._haar = None

    def set_yolo_model(self, model_path: Path | None, allowed_class_names: set[str] | None = None) -> None:
        if model_path == self.model_path and allowed_class_names == self.allowed_class_names:
            return
        self.model_path = model_path
        self.allowed_class_names = allowed_class_names
        self._model = None

    def detect(self, frame: np.ndarray, confidence: float) -> list[Box]:
        original_height, original_width = frame.shape[:2]
        for angle in (0, 180, 90, 270):
            rotated = rotate_frame(frame, angle)
            detections = self._detect_yolo(rotated, confidence)
            if detections:
                mapped = [map_box_to_original(box, angle, original_width, original_height) for box in detections]
                return suppress_duplicate_boxes(mapped)

        for angle in (0, 180, 90, 270):
            rotated = rotate_frame(frame, angle)
            detections = self._detect_haar(rotated, confidence)
            if detections:
                mapped = [map_box_to_original(box, angle, original_width, original_height) for box in detections]
                return suppress_duplicate_boxes(mapped)

        return []

    def _detect_yolo(self, frame: np.ndarray, confidence: float) -> list[Box]:
        if self._load_yolo():
            results = self._model(frame, conf=confidence, verbose=False)
            if not results or results[0].boxes is None:
                return []
            names = results[0].names
            detections: list[Box] = []
            for box in results[0].boxes:
                class_id = int(box.cls.item()) if box.cls is not None else -1
                class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else str(class_id)
                if self.allowed_class_names is not None and class_name not in self.allowed_class_names:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append((int(x1), int(y1), int(x2), int(y2)))
            return detections
        return []

    def _detect_haar(self, frame: np.ndarray, confidence: float) -> list[Box]:
        if confidence >= 0.65:
            return []

        # Some frozen Windows builds ship a reduced cv2 module that lacks the
        # Haar cascade helpers. Skip the fallback cleanly in that case.
        if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
            return []

        if self._haar is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._haar = cv2.CascadeClassifier(cascade_path)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        height, width = frame.shape[:2]
        min_size = max(24, int(min(width, height) * (0.03 + confidence * 0.08)))
        min_neighbors = max(4, int(4 + confidence * 8))
        scale_factor = 1.05 + min(0.12, confidence * 0.12)
        faces = self._haar.detectMultiScale(
            gray,
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=(min_size, min_size),
        )
        return [(int(x), int(y), int(x + w), int(y + h)) for x, y, w, h in faces]

    def _load_yolo(self) -> bool:
        if self._model is not None:
            return True
        if not self.model_path or not self.model_path.exists():
            return False
        try:
            from ultralytics import YOLO

            self._model = YOLO(str(self.model_path), task="detect")
            return True
        except Exception:
            return False
