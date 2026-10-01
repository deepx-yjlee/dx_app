# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""CPU stages declared in a pipeline JSON file.

These are not NPU models. A pipeline lists them with ``"kind": "cpu"`` so the
graph stays in one file.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

import cv2
import numpy as np

from .binds import largest_box_result

# A face model in millimetres, in the order of a FaceResult's 5 keypoints:
# left eye, right eye, nose, left mouth, right mouth (the C++ multi_model_run
# uses the same points in the same order). solvePnP pairs the i-th model
# point with the i-th keypoint.
_FACE_MODEL_POINTS = np.array(
    [
        [-30.0, -30.0, -30.0],
        [30.0, -30.0, -30.0],
        [0.0, 0.0, 0.0],
        [-25.0, 30.0, -20.0],
        [25.0, 30.0, -20.0],
    ],
    dtype=np.float64,
)

CpuOp = Callable[[np.ndarray, dict[str, Any]], Any]


def face_solvepnp(frame_bgr: np.ndarray, outputs: dict[str, Any]) -> Optional[dict[str, float]]:
    """Pitch, yaw, and roll in degrees from a face stage's 5 landmarks."""
    face = largest_box_result(_as_results(outputs.get("face")))
    points = _five_points(face)
    if points is None:
        return None
    height, width = frame_bgr.shape[:2]
    # Focal length approximated by the frame width; principal point at centre.
    camera = np.array(
        [[width, 0.0, width / 2.0], [0.0, width, height / 2.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    solved, rotation, _translation = cv2.solvePnP(
        _FACE_MODEL_POINTS,
        points,
        camera,
        np.zeros((4, 1)),
        flags=cv2.SOLVEPNP_SQPNP,
    )
    if not solved:
        return None
    matrix, _jacobian = cv2.Rodrigues(rotation)
    sy = float(np.sqrt(matrix[0, 0] ** 2 + matrix[1, 0] ** 2))
    if sy < 1e-6:
        pitch = np.degrees(np.arctan2(-matrix[1, 2], matrix[1, 1]))
        yaw = np.degrees(np.arctan2(-matrix[2, 0], sy))
        roll = 0.0
    else:
        pitch = np.degrees(np.arctan2(matrix[2, 1], matrix[2, 2]))
        yaw = np.degrees(np.arctan2(-matrix[2, 0], sy))
        roll = np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))
    return {"pitch": float(pitch), "yaw": float(yaw), "roll": float(roll)}


CPU_OPS: dict[str, CpuOp] = {
    "face_solvepnp": face_solvepnp,
}


def _as_results(value: Any) -> Sequence[Any]:
    if isinstance(value, list):
        return value
    return []


def _five_points(face: Any) -> Optional[np.ndarray]:
    keypoints = getattr(face, "keypoints", None)
    if not keypoints or len(keypoints) < 5:
        return None
    points = np.array(
        [[float(point.x), float(point.y)] for point in keypoints[:5]],
        dtype=np.float64,
    )
    return points
