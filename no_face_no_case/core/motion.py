from __future__ import annotations

import cv2
import numpy as np

from no_face_no_case.core.models import Rect


def estimate_translation(previous_frame: np.ndarray, current_frame: np.ndarray) -> tuple[float, float]:
    """Estimate global camera translation between frames.

    Feature tracking is tried first because it handles real handheld footage better than
    whole-frame phase correlation when people move independently in the scene.
    """
    feature_shift = estimate_feature_translation(previous_frame, current_frame)
    if feature_shift is not None:
        return feature_shift

    return estimate_phase_translation(previous_frame, current_frame)


def estimate_feature_translation(previous_frame: np.ndarray, current_frame: np.ndarray) -> tuple[float, float] | None:
    previous_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    points = cv2.goodFeaturesToTrack(
        previous_gray,
        maxCorners=250,
        qualityLevel=0.01,
        minDistance=8,
        blockSize=7,
    )
    if points is None or len(points) < 12:
        return None

    next_points, status, _error = cv2.calcOpticalFlowPyrLK(previous_gray, current_gray, points, None)
    if next_points is None or status is None:
        return None

    valid_previous = points[status.reshape(-1) == 1].reshape(-1, 2)
    valid_next = next_points[status.reshape(-1) == 1].reshape(-1, 2)
    if len(valid_previous) < 12:
        return None

    deltas = valid_next - valid_previous
    median_delta = np.median(deltas, axis=0)
    distances = np.linalg.norm(deltas - median_delta, axis=1)
    median_distance = float(np.median(distances))
    inliers = distances <= max(3.0, median_distance * 2.5)
    if int(np.count_nonzero(inliers)) < 8:
        return None

    dx, dy = np.median(deltas[inliers], axis=0)
    return float(dx), float(dy)


def estimate_phase_translation(previous_frame: np.ndarray, current_frame: np.ndarray) -> tuple[float, float]:
    previous_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    previous_gray = cv2.GaussianBlur(previous_gray, (5, 5), 0)
    current_gray = cv2.GaussianBlur(current_gray, (5, 5), 0)
    shift, response = cv2.phaseCorrelate(previous_gray, current_gray)
    if response < 0.05:
        return 0.0, 0.0
    dx, dy = shift
    return float(dx), float(dy)


def shift_regions(regions: list[Rect], dx: float, dy: float, frame_width: int, frame_height: int) -> list[Rect]:
    if not regions:
        return []
    normalized_dx = dx / frame_width
    normalized_dy = dy / frame_height
    return [Rect(region.x + normalized_dx, region.y + normalized_dy, region.width, region.height).normalized() for region in regions]


class CameraMotionTracker:
    def __init__(self, frame_width: int, frame_height: int, regions: list[Rect]) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.regions = list(regions)
        self.previous_frame: np.ndarray | None = None

    def update(self, frame: np.ndarray) -> list[Rect]:
        if self.previous_frame is None:
            self.previous_frame = frame.copy()
            return self.regions

        dx, dy = estimate_translation(self.previous_frame, frame)
        self.regions = shift_regions(self.regions, dx, dy, self.frame_width, self.frame_height)
        self.previous_frame = frame.copy()
        return self.regions
