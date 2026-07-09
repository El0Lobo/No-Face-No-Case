from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable
from dataclasses import dataclass

import cv2

from no_face_no_case.core.detection import FaceDetector
from no_face_no_case.core.effects import apply_privacy_effects, filter_detections_by_regions
from no_face_no_case.core.identity import FaceMemory
from no_face_no_case.core.motion import CameraMotionTracker, estimate_translation, shift_regions
from no_face_no_case.core.models import EffectSettings, ManualRegion, Metadata, Rect
from no_face_no_case.infrastructure.media_io import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, mux_original_audio


ProgressCallback = Callable[[float, str], None]


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if intersection == 0:
        return 0.0
    area_a = max(1, ax2 - ax1) * max(1, ay2 - ay1)
    area_b = max(1, bx2 - bx1) * max(1, by2 - by1)
    return intersection / (area_a + area_b - intersection)


def split_manual_regions(
    manual_regions: list[ManualRegion],
    frame_index: int | None,
    frame_width: int | None = None,
    frame_height: int | None = None,
    motion_dx: float = 0.0,
    motion_dy: float = 0.0,
) -> tuple[list[Rect], list[Rect]]:
    clear_regions: list[Rect] = []
    effect_regions: list[Rect] = []
    for region in manual_regions:
        if not region.active_at(frame_index):
            continue
        rect = region.rect_at(frame_index)
        if region.follow_motion and frame_width is not None and frame_height is not None:
            rect = shift_regions([rect], motion_dx, motion_dy, frame_width, frame_height)[0]
        if region.mode == "effect":
            effect_regions.append(rect)
        else:
            clear_regions.append(rect)
    return clear_regions, effect_regions


class FaceTracker:
    def __init__(self, extra_hold_frames: int) -> None:
        self.extra_hold_frames = max(0, int(extra_hold_frames))
        self._history_window = max(1, self.extra_hold_frames + 1)
        self._tracks: list[_Track] = []

    def update(self, detections: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        next_tracks: list[_Track] = []
        matched_track_indexes: set[int] = set()

        for detection in detections:
            best_index = None
            best_score = 0.0
            for index, track in enumerate(self._tracks):
                if index in matched_track_indexes:
                    continue
                score = _iou(detection, track.box)
                if score > best_score:
                    best_score = score
                    best_index = index

            if best_index is not None and best_score >= 0.15:
                matched_track_indexes.add(best_index)
                track = self._tracks[best_index]
                track.box = detection
                track.ttl = self.extra_hold_frames
                track.history.append(detection)
                track.history = track.history[-self._history_window :]
                next_tracks.append(track)
            else:
                next_tracks.append(_Track(box=detection, ttl=self.extra_hold_frames, history=[detection]))

        for index, track in enumerate(self._tracks):
            if index not in matched_track_indexes and track.ttl > 0:
                track.ttl -= 1
                next_tracks.append(track)

        self._tracks = next_tracks
        return [track.bounds for track in self._tracks]


@dataclass(slots=True)
class _Track:
    box: tuple[int, int, int, int]
    ttl: int
    history: list[tuple[int, int, int, int]]

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        x1 = min(box[0] for box in self.history)
        y1 = min(box[1] for box in self.history)
        x2 = max(box[2] for box in self.history)
        y2 = max(box[3] for box in self.history)
        return x1, y1, x2, y2


class MediaProcessor:
    def __init__(self, detector: FaceDetector) -> None:
        self.detector = detector

    def process(
        self,
        input_path: Path,
        output_dir: Path,
        metadata: Metadata,
        settings: EffectSettings,
        protected_regions: list[Rect],
        manual_regions: list[ManualRegion] | None = None,
        ignored_detection_regions: list[Rect] | None = None,
        remembered_faces: FaceMemory | None = None,
        ignored_detections: FaceMemory | None = None,
        progress: ProgressCallback | None = None,
    ) -> Path:
        suffix = input_path.suffix.lower()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{metadata.safe_stem()}_processed{suffix}"

        if suffix in IMAGE_EXTENSIONS:
            return self._process_image(
                input_path,
                output_path,
                settings,
                protected_regions,
                manual_regions or [],
                ignored_detection_regions or [],
                remembered_faces,
                ignored_detections,
                progress,
            )
        if suffix in VIDEO_EXTENSIONS:
            return self._process_video(
                input_path,
                output_path,
                settings,
                protected_regions,
                manual_regions or [],
                ignored_detection_regions or [],
                remembered_faces,
                ignored_detections,
                progress,
            )
        raise ValueError(f"Unsupported media type: {suffix}")

    def _process_image(
        self,
        input_path: Path,
        output_path: Path,
        settings: EffectSettings,
        protected_regions: list[Rect],
        manual_regions: list[ManualRegion],
        ignored_detection_regions: list[Rect],
        remembered_faces: FaceMemory | None,
        ignored_detections: FaceMemory | None,
        progress: ProgressCallback | None,
    ) -> Path:
        frame = cv2.imread(str(input_path))
        if frame is None:
            raise ValueError(f"Could not read image: {input_path}")
        detections = self.detector.detect(frame, settings.confidence_threshold)
        detections = filter_detections_by_regions(detections, ignored_detection_regions, frame.shape[1], frame.shape[0])
        if ignored_detections is not None:
            detections, _ignored = ignored_detections.split_detections(frame, detections)
        if remembered_faces is not None:
            detections, _remembered = remembered_faces.split_detections(frame, detections)
        clear_regions, effect_regions = split_manual_regions(manual_regions, None)
        processed = apply_privacy_effects(frame, detections, protected_regions + clear_regions, settings, effect_regions)
        cv2.imwrite(str(output_path), processed)
        if progress:
            progress(100.0, "Image complete")
        return output_path

    def _process_video(
        self,
        input_path: Path,
        output_path: Path,
        settings: EffectSettings,
        protected_regions: list[Rect],
        manual_regions: list[ManualRegion],
        ignored_detection_regions: list[Rect],
        remembered_faces: FaceMemory | None,
        ignored_detections: FaceMemory | None,
        progress: ProgressCallback | None,
    ) -> Path:
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise ValueError(f"Could not read video: {input_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_only_path = output_path.with_name(f"{output_path.stem}_video_only{output_path.suffix}")
        writer = cv2.VideoWriter(str(video_only_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        tracker = FaceTracker(settings.extra_hold_frames)
        motion_tracker = CameraMotionTracker(width, height, protected_regions)
        previous_frame = None
        motion_dx = 0.0
        motion_dy = 0.0

        processed_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if previous_frame is not None:
                dx, dy = estimate_translation(previous_frame, frame)
                motion_dx += dx
                motion_dy += dy
            previous_frame = frame.copy()
            detections = self.detector.detect(frame, settings.confidence_threshold)
            detections = filter_detections_by_regions(detections, ignored_detection_regions, width, height)
            if ignored_detections is not None:
                detections, _ignored = ignored_detections.split_detections(frame, detections)
            if remembered_faces is not None:
                detections, _remembered = remembered_faces.split_detections(frame, detections)
            tracked_faces = tracker.update(detections)
            frame_protected_regions = motion_tracker.update(frame) if settings.follow_camera_motion else protected_regions
            clear_regions, effect_regions = split_manual_regions(
                manual_regions,
                processed_count,
                width,
                height,
                motion_dx,
                motion_dy,
            )
            writer.write(
                apply_privacy_effects(
                    frame,
                    tracked_faces,
                    frame_protected_regions + clear_regions,
                    settings,
                    effect_regions,
                )
            )
            processed_count += 1
            if progress and frame_count:
                progress((processed_count / frame_count) * 100.0, f"Frame {processed_count}/{frame_count}")

        cap.release()
        writer.release()
        if not mux_original_audio(video_only_path, input_path, output_path):
            if output_path.exists():
                output_path.unlink()
            shutil.move(str(video_only_path), str(output_path))
        elif video_only_path.exists():
            video_only_path.unlink()
        if progress:
            progress(100.0, "Video complete")
        return output_path
