# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""dms_clip's face_solvepnp CPU stage recovers a known head pose.

A face detector's 5 landmarks come in the FaceResult order: left eye, right
eye, nose, left mouth, right mouth (the C++ FaceDetectionResult documents the
same order). The test projects a 3D face in that order through the stage's
own camera, with a known rotation, and the stage must give that rotation back.
No NPU engine is opened.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from common.base import Keypoint
from common.multi.cpu_ops import face_solvepnp
from common.processors.face_postprocessor import FaceResult

# Millimetres, image axes (x right, y down), per landmark in FaceResult order.
_FACE_LANDMARKS_3D = np.array(
    [
        [-30.0, -30.0, -30.0],  # left eye
        [30.0, -30.0, -30.0],   # right eye
        [0.0, 0.0, 0.0],        # nose
        [-25.0, 30.0, -20.0],   # left mouth
        [25.0, 30.0, -20.0],    # right mouth
    ],
    dtype=np.float64,
)
_WIDTH = 640
_HEIGHT = 480


def _rotation(pitch: float, yaw: float, roll: float) -> np.ndarray:
    """R = Rz(roll) @ Ry(yaw) @ Rx(pitch), the angles the stage reports."""
    p, y, r = np.radians([pitch, yaw, roll])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1]])
    return rz @ ry @ rx


def _face(pitch: float, yaw: float, roll: float) -> FaceResult:
    camera = np.array(
        [[_WIDTH, 0.0, _WIDTH / 2.0], [0.0, _WIDTH, _HEIGHT / 2.0], [0.0, 0.0, 1.0]]
    )
    rvec, _ = cv2.Rodrigues(_rotation(pitch, yaw, roll))
    tvec = np.array([[10.0], [-5.0], [600.0]])
    points, _ = cv2.projectPoints(_FACE_LANDMARKS_3D, rvec, tvec, camera, np.zeros((4, 1)))
    points = points.reshape(-1, 2)
    x1, y1 = points.min(axis=0) - 20.0
    x2, y2 = points.max(axis=0) + 20.0
    return FaceResult(
        box=[float(x1), float(y1), float(x2), float(y2)],
        confidence=0.9,
        class_id=0,
        keypoints=[Keypoint(float(x), float(y), 1.0) for x, y in points],
    )


@pytest.mark.parametrize(
    "pose",
    [(0.0, 0.0, 0.0), (10.0, 25.0, 5.0), (-15.0, -40.0, -10.0), (5.0, 70.0, 20.0)],
    ids=["frontal", "right-up", "left-down", "profile"],
)
def test_face_solvepnp_recovers_the_projected_pose(pose):
    frame = np.zeros((_HEIGHT, _WIDTH, 3), dtype=np.uint8)
    result = face_solvepnp(frame, {"face": [_face(*pose)]})
    assert result is not None
    got = (result["pitch"], result["yaw"], result["roll"])
    assert got == pytest.approx(pose, abs=0.05), got


def test_face_solvepnp_uses_the_largest_face():
    frame = np.zeros((_HEIGHT, _WIDTH, 3), dtype=np.uint8)
    small = _face(0.0, 0.0, 0.0)
    small.box = [0.0, 0.0, 10.0, 10.0]
    large = _face(10.0, 25.0, 5.0)
    result = face_solvepnp(frame, {"face": [small, large]})
    got = (result["pitch"], result["yaw"], result["roll"])
    assert got == pytest.approx((10.0, 25.0, 5.0), abs=0.05), got
