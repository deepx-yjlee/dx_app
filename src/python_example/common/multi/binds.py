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


def crop_rois(
    frame_bgr: np.ndarray,
    results: Sequence[Any],
    pad_ratio: float = 0.0,
) -> list[tuple[tuple[int, int, int, int], np.ndarray]]:
    """Crop one BGR patch per detection box.

    ``pad_ratio`` grows each side by that fraction of the box width and height.
    """
    height, width = frame_bgr.shape[:2]
    crops: list[tuple[tuple[int, int, int, int], np.ndarray]] = []
    for x1, y1, x2, y2 in boxes_of(results):
        pad_x = int((x2 - x1) * pad_ratio)
        pad_y = int((y2 - y1) * pad_ratio)
        left = max(0, x1 - pad_x)
        top = max(0, y1 - pad_y)
        right = min(width, x2 + pad_x)
        bottom = min(height, y2 + pad_y)
        if right <= left or bottom <= top:
            continue
        box = (left, top, right, bottom)
        crops.append((box, frame_bgr[top:bottom, left:right].copy()))
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
