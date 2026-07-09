from __future__ import annotations

import cv2
import numpy as np

from no_face_no_case.core.models import EffectSettings, Rect


def pixelate(image: np.ndarray, pixel_size: int) -> np.ndarray:
    pixel_size = max(2, int(pixel_size))
    height, width = image.shape[:2]
    small_width = max(1, width // pixel_size)
    small_height = max(1, height // pixel_size)
    small = cv2.resize(image, (small_width, small_height), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_NEAREST)


def blur(image: np.ndarray, blur_size: int) -> np.ndarray:
    blur_size = max(3, int(blur_size))
    if blur_size % 2 == 0:
        blur_size += 1
    return cv2.GaussianBlur(image, (blur_size, blur_size), 30)


def apply_region_effect(image: np.ndarray, settings: EffectSettings) -> np.ndarray:
    output = image.copy()
    if settings.blur_faces:
        output = blur(output, settings.blur_size)
    if settings.pixelate_faces:
        output = pixelate(output, settings.pixel_size)
    return output


def privacy_preview(
    frame: np.ndarray,
    detections: list[tuple[int, int, int, int]],
    protected_regions: list[Rect],
    settings: EffectSettings,
    manual_effect_regions: list[Rect] | None = None,
) -> np.ndarray:
    return apply_privacy_effects(frame, detections, protected_regions, settings, manual_effect_regions)


def expand_box(box: tuple[int, int, int, int], ratio: float, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    grow_x = int(width * max(0.0, ratio - 1.0) / 2)
    grow_y = int(height * max(0.0, ratio - 1.0) / 2)
    return max(0, x1 - grow_x), max(0, y1 - grow_y), min(frame_width, x2 + grow_x), min(frame_height, y2 + grow_y)


def detection_effect_boxes(
    detections: list[tuple[int, int, int, int]],
    settings: EffectSettings,
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int, int, int]]:
    if settings.detection_effect_area == "person":
        boxes = []
        ratio = min(max(settings.person_effect_ratio, 0.05), 1.0)
        for x1, y1, x2, y2 in detections:
            top = max(0, y1)
            bottom = min(frame_height, y1 + max(1, int((y2 - y1) * ratio)))
            boxes.append((max(0, x1), top, min(frame_width, x2), max(top + 1, bottom)))
        return boxes
    return [expand_box(box, settings.face_expand_ratio, frame_width, frame_height) for box in detections]


def intersects(rect_a: tuple[int, int, int, int], rect_b: tuple[int, int, int, int]) -> bool:
    ax1, ay1, ax2, ay2 = rect_a
    bx1, by1, bx2, by2 = rect_b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def restore_regions(output: np.ndarray, source: np.ndarray, regions: list[tuple[int, int, int, int]]) -> np.ndarray:
    for x1, y1, x2, y2 in regions:
        output[y1:y2, x1:x2] = source[y1:y2, x1:x2]
    return output


def apply_effect_regions(output: np.ndarray, regions: list[tuple[int, int, int, int]], settings: EffectSettings) -> np.ndarray:
    for x1, y1, x2, y2 in regions:
        area = output[y1:y2, x1:x2]
        if area.size == 0:
            continue
        output[y1:y2, x1:x2] = apply_region_effect(area, settings)
    return output


def filter_detections_by_regions(
    detections: list[tuple[int, int, int, int]],
    ignored_regions: list[Rect],
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int, int, int]]:
    ignored_pixels = [region.to_pixels(frame_width, frame_height) for region in ignored_regions]
    return [box for box in detections if not any(intersects(box, ignored) for ignored in ignored_pixels)]


def apply_overlay(base: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    if overlay.shape[2] != 4:
        return overlay[:, :, :3]
    alpha = overlay[:, :, 3] / 255.0
    blended = base.copy()
    for channel in range(3):
        blended[:, :, channel] = alpha * overlay[:, :, channel] + (1.0 - alpha) * base[:, :, channel]
    return blended


def apply_privacy_effects(
    frame: np.ndarray,
    detections: list[tuple[int, int, int, int]],
    protected_regions: list[Rect],
    settings: EffectSettings,
    manual_effect_regions: list[Rect] | None = None,
) -> np.ndarray:
    output = frame.copy()
    frame_height, frame_width = output.shape[:2]
    protected_pixels = [region.to_pixels(frame_width, frame_height) for region in protected_regions]
    manual_effect_pixels = [
        region.to_pixels(frame_width, frame_height) for region in (manual_effect_regions or [])
    ]
    detected_effect_boxes = detection_effect_boxes(detections, settings, frame_width, frame_height)

    if settings.target == "background":
        output = apply_region_effect(output, settings)
        output = restore_regions(output, frame, detected_effect_boxes + protected_pixels)
        return apply_effect_regions(output, manual_effect_pixels, settings)

    overlay = None
    if settings.overlay_faces and settings.overlay_path:
        overlay = cv2.imread(str(settings.overlay_path), cv2.IMREAD_UNCHANGED)

    for box in detected_effect_boxes:
        x1, y1, x2, y2 = box
        area = output[y1:y2, x1:x2]
        if area.size == 0:
            continue

        area = apply_region_effect(area, settings)

        if overlay is not None:
            resized = cv2.resize(overlay, (x2 - x1, y2 - y1), interpolation=cv2.INTER_AREA)
            area = apply_overlay(area, resized)

        output[y1:y2, x1:x2] = area

    output = restore_regions(output, frame, protected_pixels)
    return apply_effect_regions(output, manual_effect_pixels, settings)


apply_face_effects = apply_privacy_effects
