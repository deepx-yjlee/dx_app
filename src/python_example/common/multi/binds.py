# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Input bindings between pipeline stages."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .pipeline import BindSpec, PipelineError


def boxes_of(results: Sequence[Any]) -> list[tuple[int, int, int, int]]:
    """Integer xyxy boxes from postprocessor results that carry ``box``."""
    boxes: list[tuple[int, int, int, int]] = []
    for result in results or []:
        raw = getattr(result, "box", None)
        if raw is None or len(raw) < 4:
            continue
        x1, y1, x2, y2 = (int(float(value)) for value in raw[:4])
        if x2 > x1 and y2 > y1:
            boxes.append((x1, y1, x2, y2))
    return boxes


# The crop rule of src/cpp_example/common/utility/roi_crop.hpp (PadBox,
# ClipBoxToFrame, PaddedCropRect), which the graph engine and the C++
# multi_model runtime share: pad around the box's own centre, clamp the corners
# to the frame in float, then truncate the left/top corner and the clamped size
# to int once each. The arithmetic is float32, as in C++, so both runtimes cut
# the same pixels from the same box. Boxes are (x, y, width, height).


def pad_box(box: Sequence[float], pad: float) -> tuple:
    """Grow ``box`` by ``pad`` x its width (height) on each side; pad <= 0 keeps it."""
    pad = np.float32(pad)
    if pad <= 0:
        return tuple(box)
    x, y, w, h = (np.float32(v) for v in box)
    dx = np.float32(w * pad)
    dy = np.float32(h * pad)
    return (np.float32(x - dx), np.float32(y - dy),
            np.float32(w + dx * np.float32(2)), np.float32(h + dy * np.float32(2)))


def clip_box_to_frame(box: Sequence[float], cols: int, rows: int) -> tuple[int, int, int, int]:
    """Integer (x, y, width, height) inside a cols x rows frame; all zero when empty."""
    x, y, w, h = (np.float32(v) for v in box)
    x1 = max(np.float32(0), x)
    y1 = max(np.float32(0), y)
    x2 = min(np.float32(cols), np.float32(x + w))
    y2 = min(np.float32(rows), np.float32(y + h))
    if x2 <= x1 or y2 <= y1:
        return (0, 0, 0, 0)
    return (int(x1), int(y1), int(np.float32(x2 - x1)), int(np.float32(y2 - y1)))


def padded_crop_rect(box: Sequence[float], pad: float, cols: int,
                     rows: int) -> tuple[int, int, int, int]:
    """``pad_box`` then ``clip_box_to_frame``: the crop window of ``box``."""
    return clip_box_to_frame(pad_box(box, pad), cols, rows)


def crop_rois(
    frame_bgr: np.ndarray,
    results: Sequence[Any],
    pad_ratio: float = 0.0,
) -> list[tuple[tuple[int, int, int, int], np.ndarray]]:
    """Crop one BGR patch per detection box, by the C++ crop rule (above).

    ``pad_ratio`` grows each side by that fraction of the box width and height.
    The returned box is the crop window as integer xyxy. A box with no whole
    pixel inside the frame is skipped.
    """
    height, width = frame_bgr.shape[:2]
    crops: list[tuple[tuple[int, int, int, int], np.ndarray]] = []
    for result in results or []:
        raw = getattr(result, "box", None)
        if raw is None or len(raw) < 4:
            continue
        x1, y1, x2, y2 = (np.float32(float(value)) for value in raw[:4])
        left, top, w, h = padded_crop_rect(
            (x1, y1, np.float32(x2 - x1), np.float32(y2 - y1)), pad_ratio, width, height)
        if w <= 0 or h <= 0:
            continue
        box = (left, top, left + w, top + h)
        crops.append((box, frame_bgr[top:top + h, left:left + w].copy()))
    return crops


def bound_inputs(
    bind: BindSpec,
    frame_bgr: np.ndarray,
    upstream: Sequence[Any],
) -> list[tuple[Any, np.ndarray]]:
    """Return ``(meta, image)`` pairs the dependent stage should run."""
    if bind.op == "roi":
        return [(box, crop) for box, crop in crop_rois(frame_bgr, upstream)]
    if bind.op == "face_roi":
        # Driver monitoring scores the selected face, not every detection.
        selected = largest_box_result(upstream)
        if selected is None:
            return []
        return [(box, crop) for box, crop in crop_rois(frame_bgr, [selected], pad_ratio=0.15)]
    raise PipelineError(f"unknown bind op {bind.op!r}")


def largest_box_result(results: Sequence[Any]) -> Any | None:
    """The result whose box covers the largest area, or None."""
    best = None
    best_area = -1
    for result in results or []:
        raw = getattr(result, "box", None)
        if raw is None or len(raw) < 4:
            continue
        area = max(0.0, float(raw[2]) - float(raw[0])) * max(0.0, float(raw[3]) - float(raw[1]))
        if area > best_area:
            best = result
            best_area = area
    return best
