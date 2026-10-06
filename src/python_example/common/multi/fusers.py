# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Combine finished stage outputs into one demo result.

The fuse name in the pipeline JSON selects the function. Adding a demo is a
new JSON file plus, when the combination rule is new, one function here.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .binds import boxes_of, largest_box_result
from .pipeline import PipelineError

# COCO ids the logistics demo treats as a package.
_PACKAGE_CLASS_IDS = {24, 26, 28}

Fuser = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


def fuse_hand_cascade(outputs: Mapping[str, Any], _config: Mapping[str, Any]) -> dict[str, Any]:
    """Palm boxes plus the landmark calls made on each crop."""
    palms = _result_list(outputs.get("palm"))
    landmark_calls = outputs.get("landmark") or []
    return {
        "event": "HANDS" if landmark_calls else "NO_HAND",
        "palms": len(boxes_of(palms)),
        "hands": len(landmark_calls) if isinstance(landmark_calls, list) else 0,
    }


def fuse_logistics_volume(outputs: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    """Package detections joined to the best-overlap mask and the depth map."""
    packages = [item for item in _result_list(outputs.get("det")) if _is_package(item)]
    segments = [item for item in _result_list(outputs.get("seg")) if _is_package(item)]
    depth_rows = _result_list(outputs.get("depth"))
    depth_map = getattr(depth_rows[0], "depth_map", None) if depth_rows else None
    scale = float(config.get("scale_factor", 1.0))
    measured = []
    for item in packages:
        segment = _best_overlap(item, segments)
        mask = getattr(segment, "mask", None) if segment is not None else None
        area = _mask_area(mask)
        median = _median_under_mask(depth_map, mask)
        volume = None if median is None or area == 0 else float(area * median * scale)
        box = boxes_of([item])
        measured.append({
            "box": list(box[0]) if box else [],
            "mask_area_px": area,
            "median_depth": median,
            "volume_proxy": volume,
        })
    return {
        "event": "BOX_MEASURED" if measured else "NO_BOX",
        "packages": len(measured),
        "measurements": measured,
    }


def fuse_dms(outputs: Mapping[str, Any], _config: Mapping[str, Any]) -> dict[str, Any]:
    """Driver face, pose count, whether CLIP ran on the face crop, and head pose."""
    faces = _result_list(outputs.get("face"))
    poses = _result_list(outputs.get("pose"))
    clip_calls = outputs.get("clip") or []
    head = outputs.get("headpose")
    driver = largest_box_result(faces)
    return {
        "event": "DRIVER" if driver is not None else "NO_DRIVER",
        "faces": len(faces),
        "poses": len(poses),
        "clip_rois": len(clip_calls) if isinstance(clip_calls, list) else 0,
        "headpose": head,
    }


FUSERS: dict[str, Fuser] = {
    "hand_cascade": fuse_hand_cascade,
    "logistics_volume": fuse_logistics_volume,
    "dms": fuse_dms,
}


def fuse_outputs(
    fuse_name: str,
    outputs: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the fuse function named by the pipeline."""
    fuser = FUSERS.get(fuse_name)
    if fuser is None:
        known = ", ".join(sorted(FUSERS))
        raise PipelineError(f"unknown fuse {fuse_name!r}. Known: {known}")
    return fuser(outputs, config)


def _result_list(value: Any) -> Sequence[Any]:
    if isinstance(value, list):
        return value
    return []


def _best_overlap(detection: Any, segments: Sequence[Any]) -> Any | None:
    best = None
    best_iou = 0.0
    for segment in segments:
        iou = _box_iou(getattr(detection, "box", None), getattr(segment, "box", None))
        if iou > best_iou:
            best = segment
            best_iou = iou
    return best


def _box_iou(left: Any, right: Any) -> float:
    if left is None or right is None or len(left) < 4 or len(right) < 4:
        return 0.0
    x1 = max(float(left[0]), float(right[0]))
    y1 = max(float(left[1]), float(right[1]))
    x2 = min(float(left[2]), float(right[2]))
    y2 = min(float(left[3]), float(right[3]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter == 0.0:
        return 0.0
    area_left = max(0.0, float(left[2]) - float(left[0])) * max(0.0, float(left[3]) - float(left[1]))
    area_right = max(0.0, float(right[2]) - float(right[0])) * max(0.0, float(right[3]) - float(right[1]))
    union = area_left + area_right - inter
    return inter / union if union > 0.0 else 0.0


def _mask_area(mask: Any) -> int:
    """Non-zero count of a mask, or 0 when the stage did not produce one."""
    if mask is None or getattr(mask, "size", 0) == 0:
        return 0
    return int((np.asarray(mask) > 0).sum())


def _median_under_mask(depth_map: Any, mask: Any) -> float | None:
    """Median depth on the mask when both arrays share the same height and width."""
    if depth_map is None or mask is None:
        return None
    depth = np.asarray(depth_map)
    binary = np.asarray(mask) > 0
    if depth.ndim != 2 or binary.ndim != 2 or depth.shape != binary.shape:
        return None
    samples = depth[binary]
    samples = samples[np.isfinite(samples)]
    if samples.size == 0:
        return None
    return float(np.median(samples))


def _is_package(result: Any) -> bool:
    class_id = getattr(result, "class_id", None)
    if class_id in _PACKAGE_CLASS_IDS:
        return True
    name = str(getattr(result, "class_name", "")).lower()
    return name in {"backpack", "handbag", "suitcase", "box", "package", "luggage"}
