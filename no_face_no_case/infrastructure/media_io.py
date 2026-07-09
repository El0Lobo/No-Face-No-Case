from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from no_face_no_case.core.models import MediaInfo
from no_face_no_case.paths import app_root


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def inspect_media(path: Path) -> MediaInfo:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Could not read image: {path}")
        height, width = image.shape[:2]
        return MediaInfo(path=path, kind="image", width=width, height=height, size_bytes=path.stat().st_size)

    if suffix in VIDEO_EXTENSIONS:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Could not read video: {path}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return MediaInfo(path=path, kind="video", width=width, height=height, size_bytes=path.stat().st_size, fps=fps, frame_count=frame_count)

    raise ValueError(f"Unsupported file type: {suffix}")


def first_frame(path: Path) -> np.ndarray:
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Could not read image: {path}")
        return image

    cap = cv2.VideoCapture(str(path))
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise ValueError(f"Could not read first frame: {path}")
    return frame


def frame_at_percent(path: Path, percent: float) -> np.ndarray:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Could not read video: {path}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target = int(max(0.0, min(1.0, percent)) * max(0, frame_count - 1))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise ValueError(f"Could not seek video frame: {path}")
    return frame


def frame_at_index(path: Path, frame_index: int) -> np.ndarray:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Could not read video: {path}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target = min(max(0, int(frame_index)), max(0, frame_count - 1))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise ValueError(f"Could not seek video frame {target}: {path}")
    return frame


def cv_to_rgb(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def find_ffmpeg() -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    root = app_root().parent
    candidates = [
        root / "old" / "ffmpeg" / "bin" / "ffmpeg.exe",
        root / "old" / "ffmpeg.exe",
        root / "ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def mux_original_audio(video_path: Path, original_path: Path, output_path: Path) -> bool:
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        return False

    base_command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(original_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-c:v",
        "copy",
        "-shortest",
    ]
    copy_audio = base_command + ["-c:a", "copy", str(output_path)]
    result = subprocess.run(copy_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if result.returncode == 0 and output_path.exists():
        return True

    encode_audio = base_command + ["-c:a", "aac", "-b:a", "192k", str(output_path)]
    result = subprocess.run(encode_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return result.returncode == 0 and output_path.exists()
