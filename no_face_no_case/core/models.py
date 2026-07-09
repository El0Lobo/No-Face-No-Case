from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


MediaKind = Literal["image", "video"]
EffectTarget = Literal["faces", "background"]
DetectionEffectArea = Literal["face", "person"]
ManualRegionMode = Literal["clear", "effect"]


@dataclass(slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    def normalized(self) -> "Rect":
        x1 = min(max(self.x, 0.0), 1.0)
        y1 = min(max(self.y, 0.0), 1.0)
        x2 = min(max(self.x + self.width, 0.0), 1.0)
        y2 = min(max(self.y + self.height, 0.0), 1.0)
        return Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    def to_pixels(self, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
        rect = self.normalized()
        x1 = int(rect.x * frame_width)
        y1 = int(rect.y * frame_height)
        x2 = int((rect.x + rect.width) * frame_width)
        y2 = int((rect.y + rect.height) * frame_height)
        return x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)

    def eased_to(self, other: "Rect", amount: float) -> "Rect":
        t = min(max(amount, 0.0), 1.0)
        eased = t * t * (3.0 - (2.0 * t))
        return Rect(
            self.x + (other.x - self.x) * eased,
            self.y + (other.y - self.y) * eased,
            self.width + (other.width - self.width) * eased,
            self.height + (other.height - self.height) * eased,
        ).normalized()


@dataclass(slots=True)
class RegionKeyframe:
    frame: int
    rect: Rect


@dataclass(slots=True)
class EffectSettings:
    target: EffectTarget = "faces"
    detection_effect_area: DetectionEffectArea = "face"
    person_effect_ratio: float = 0.33
    pixelate_faces: bool = True
    blur_faces: bool = False
    overlay_faces: bool = False
    pixel_size: int = 20
    blur_size: int = 51
    face_expand_ratio: float = 1.2
    confidence_threshold: float = 0.25
    extra_hold_frames: int = 0
    follow_camera_motion: bool = True
    overlay_path: Path | None = None


@dataclass(slots=True)
class Metadata:
    title: str = "output"
    date: str = ""
    location: str = "unknown"

    def safe_stem(self) -> str:
        pieces = [self.title.strip() or "output", self.location.strip() or "unknown", self.date.strip()]
        return "_".join(piece.replace("/", "_").replace("\\", "_").replace(" ", "_") for piece in pieces if piece)


@dataclass(slots=True)
class MediaInfo:
    path: Path
    kind: MediaKind
    width: int
    height: int
    size_bytes: int
    fps: float | None = None
    frame_count: int | None = None

    @property
    def duration_seconds(self) -> float | None:
        if not self.fps or not self.frame_count:
            return None
        return self.frame_count / self.fps


@dataclass(slots=True)
class ManualRegion:
    rect: Rect
    mode: ManualRegionMode = "clear"
    start_frame: int = 0
    end_frame: int | None = None
    locked: bool = False
    follow_motion: bool = False
    keyframes: list[RegionKeyframe] = field(default_factory=list)

    def active_at(self, frame_index: int | None) -> bool:
        if frame_index is None:
            return True
        if frame_index < self.start_frame:
            return False
        return self.end_frame is None or frame_index <= self.end_frame

    def rect_at(self, frame_index: int | None) -> Rect:
        if frame_index is None or not self.keyframes:
            return self.rect

        keyframes = sorted(self.keyframes, key=lambda keyframe: keyframe.frame)
        if frame_index <= keyframes[0].frame:
            return keyframes[0].rect
        if frame_index >= keyframes[-1].frame:
            return keyframes[-1].rect

        previous = keyframes[0]
        for next_keyframe in keyframes[1:]:
            if frame_index <= next_keyframe.frame:
                span = max(1, next_keyframe.frame - previous.frame)
                return previous.rect.eased_to(next_keyframe.rect, (frame_index - previous.frame) / span)
            previous = next_keyframe
        return keyframes[-1].rect

    def set_keyframe(self, frame: int, rect: Rect) -> None:
        normalized = rect.normalized()
        for keyframe in self.keyframes:
            if keyframe.frame == frame:
                keyframe.rect = normalized
                self.rect = self.rect_at(self.start_frame)
                return
        self.keyframes.append(RegionKeyframe(max(0, frame), normalized))
        self.keyframes.sort(key=lambda keyframe: keyframe.frame)
        self.rect = self.rect_at(self.start_frame)


@dataclass(slots=True)
class PlannerState:
    media_path: Path | None = None
    output_dir: Path | None = None
    protected_regions: list[Rect] = field(default_factory=list)
    manual_regions: list[ManualRegion] = field(default_factory=list)
    ignored_detection_regions: list[Rect] = field(default_factory=list)
    settings: EffectSettings = field(default_factory=EffectSettings)
    metadata: Metadata = field(default_factory=Metadata)
