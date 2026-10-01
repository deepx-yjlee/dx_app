"""The Python multi_model runtime crops ROIs by the C++ rule.

``src/cpp_example/common/utility/roi_crop.hpp`` is the one crop rule of the
graph engine and the C++ multi_model runtime: pad around the box's own centre
by ``pad`` x its width (height), clamp the corners to the frame in float, then
truncate the left/top corner and the clamped size to int once each. The Python
runtime (``common/multi/binds.py``) used to truncate each corner first and pad
by the truncated size, so the two runtimes cut different pixels from one box.

The expected values below are the ones ``common_unit_test``
(``TestPaddedCropRectEdgeCases``) pins for the C++ functions.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from common.multi.binds import (
    BindSpec,
    bound_inputs,
    clip_box_to_frame,
    crop_rois,
    pad_box,
    padded_crop_rect,
)

COLS, ROWS = 640, 480


def _approx(box):
    return tuple(pytest.approx(v, abs=1e-5) for v in box)


@pytest.mark.parametrize("box,pad,expected", [
    # Fractional: y 10.7 .. 20.2 is 9 rows (per-corner truncation cut 10).
    ((3.5, 10.7, 5.0, 9.5), 0.0, (3, 10, 5, 9)),
    # Over the right border: 634.7 + 8.5 is clipped at 640.
    ((634.7, 200.0, 8.5, 20.0), 0.0, (634, 200, 5, 20)),
    # Over the top-left corner: starts at 0.
    ((-5.0, -2.5, 15.0, 12.5), 0.0, (0, 0, 10, 10)),
    # Exactly the frame, and larger than the frame on every side.
    ((0.0, 0.0, 640.0, 480.0), 0.0, (0, 0, COLS, ROWS)),
    ((-10.0, -10.0, 700.0, 500.0), 0.1, (0, 0, COLS, ROWS)),
    # Pad 0.25 of 100 x 50: 25 / 12.5 on each side.
    ((100.0, 100.0, 100.0, 50.0), 0.25, (75, 87, 150, 75)),
])
def test_padded_crop_rect_matches_the_cpp_rule(box, pad, expected):
    assert padded_crop_rect(box, pad, COLS, ROWS) == expected


def test_pad_grows_each_side_by_pad_times_the_size():
    assert _approx(pad_box((100.0, 100.0, 100.0, 50.0), 0.25)) == (75.0, 87.5, 150.0, 75.0)


def test_a_negative_or_zero_pad_leaves_the_box_alone():
    assert pad_box((1.5, 2.5, 3.0, 4.0), -0.5) == (1.5, 2.5, 3.0, 4.0)
    assert pad_box((1.5, 2.5, 3.0, 4.0), 0.0) == (1.5, 2.5, 3.0, 4.0)


@pytest.mark.parametrize("box,pad", [
    ((10.0, 10.0, 0.0, 5.0), 0.0),      # zero width
    ((10.0, 10.0, 5.0, 0.0), 0.25),     # zero height, padded
    ((10.0, 10.0, -4.0, 5.0), 0.0),     # inverted
    ((640.0, 10.0, 5.0, 5.0), 0.0),     # wholly right of the frame
    ((-20.0, 10.0, 20.0, 5.0), 0.0),    # wholly left of the frame
    ((10.0, 480.5, 5.0, 5.0), 0.0),     # wholly below the frame
])
def test_a_box_with_no_area_inside_the_frame_is_empty(box, pad):
    assert padded_crop_rect(box, pad, COLS, ROWS) == (0, 0, 0, 0)


def test_a_sliver_under_one_pixel_truncates_to_zero_width():
    assert padded_crop_rect((10.2, 10.0, 0.4, 5.0), 0.0, COLS, ROWS)[2] == 0


def test_an_empty_frame_gives_no_crop():
    assert clip_box_to_frame((0.0, 0.0, 5.0, 5.0), 0, 0) == (0, 0, 0, 0)


def _result(x1, y1, x2, y2):
    return SimpleNamespace(box=[x1, y1, x2, y2])


def _frame():
    frame = np.zeros((ROWS, COLS, 3), dtype=np.uint8)
    frame[:, :, 0] = np.arange(COLS, dtype=np.uint16)[None, :] % 256
    frame[:, :, 1] = np.arange(ROWS, dtype=np.uint16)[:, None] % 256
    return frame


def test_crop_rois_cuts_the_cpp_window():
    frame = _frame()
    (box, crop), = crop_rois(frame, [_result(3.5, 10.7, 8.5, 20.2)])
    assert box == (3, 10, 8, 19)
    assert crop.shape == (9, 5, 3)
    np.testing.assert_array_equal(crop, frame[10:19, 3:8])


def test_crop_rois_skips_boxes_without_a_whole_pixel():
    frame = _frame()
    results = [_result(10.2, 10.0, 10.6, 15.0), _result(700.0, 10.0, 710.0, 20.0),
               _result(20.0, 20.0, 30.0, 40.0)]
    assert [box for box, _ in crop_rois(frame, results)] == [(20, 20, 30, 40)]


def test_face_roi_pads_the_largest_box_by_the_cpp_ratio():
    frame = _frame()
    upstream = [_result(10.0, 10.0, 20.0, 20.0), _result(100.0, 100.0, 200.0, 150.0)]
    (box, crop), = bound_inputs(BindSpec(op="face_roi", source="face"), frame, upstream)
    # 100 x 50 at pad 0.15: 15 / 7.5 on each side, around the box.
    assert box == (85, 92, 215, 157)
    assert crop.shape == (65, 130, 3)


# --------------------------------------------------------------------------
# Cross-check against the C++ header itself, on a grid of fractional boxes.
# --------------------------------------------------------------------------

_PROBE = r"""
#include <cstdio>
#include "common/utility/roi_crop.hpp"
int main() {
    float x, y, w, h, pad;
    while (std::scanf("%f %f %f %f %f", &x, &y, &w, &h, &pad) == 5) {
        const cv::Rect r = dxapp::PaddedCropRect(cv::Rect2f(x, y, w, h), pad, 640, 480);
        std::printf("%d %d %d %d\n", r.x, r.y, r.width, r.height);
    }
    return 0;
}
"""


def test_python_rule_equals_the_cpp_header_on_a_grid(tmp_path):
    import shutil
    import subprocess
    from pathlib import Path

    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is not available")
    try:
        cflags = subprocess.run(["pkg-config", "--cflags", "opencv4"], check=True,
                                capture_output=True, text=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("pkg-config cannot find opencv4")
    cpp_root = Path(__file__).resolve().parents[3] / "src" / "cpp_example"
    source = tmp_path / "probe.cpp"
    source.write_text(_PROBE, encoding="utf-8")
    probe = tmp_path / "probe"
    build = subprocess.run([compiler, "-std=c++14", "-O0", "-I", str(cpp_root), *cflags,
                            str(source), "-o", str(probe)],
                           capture_output=True, text=True, timeout=300)
    assert build.returncode == 0, build.stderr

    xs = (-3.7, 0.0, 10.2, 10.7, 634.7, 637.9)
    sizes = (0.4, 5.5, 9.5, 100.25)
    pads = (0.0, 0.1, 0.15, 0.25)
    cases = [(x, y, w, h, p) for x in xs for y in xs for w in sizes for h in sizes
             for p in pads]
    text = "".join("{!r} {!r} {!r} {!r} {!r}\n".format(*(float(np.float32(v)) for v in c))
                   for c in cases)
    run = subprocess.run([str(probe)], input=text, capture_output=True, text=True,
                         timeout=60, check=True)
    cpp = [tuple(int(v) for v in line.split()) for line in run.stdout.splitlines()]
    assert len(cpp) == len(cases)
    py = [padded_crop_rect(c[:4], c[4], COLS, ROWS) for c in cases]
    # C++ returns cv::Rect() for an empty window; so does the Python rule.
    differ = [(c, a, b) for c, a, b in zip(cases, py, cpp) if a != b]
    assert not differ, differ[:10]
