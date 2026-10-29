from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


@dataclass(frozen=True)
class VideoMetadata:
    duration_seconds: float
    width: int
    height: int
    fps: float
    frame_count: int


def read_metadata(path: Path) -> VideoMetadata:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError("The uploaded file is not a readable video.")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_count <= 0 or width <= 0 or height <= 0:
            raise ValueError("The video contains no readable frames.")
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError("The video's frame rate could not be read.")
        return VideoMetadata(frame_count / fps, width, height, fps, frame_count)
    finally:
        capture.release()


def iter_sampled_frames(path: Path, sample_fps: float) -> Iterator[tuple[int, float, np.ndarray]]:
    """Yield frames near a fixed sampling cadence without decoding into a batch."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("The source video could not be opened for analysis.")
    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not np.isfinite(source_fps) or source_fps <= 0:
            raise ValueError("The video frame rate could not be read.")
        stride = max(1, round(source_fps / sample_fps))
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % stride == 0:
                yield frame_index, frame_index / source_fps, frame
            frame_index += 1
    finally:
        capture.release()
