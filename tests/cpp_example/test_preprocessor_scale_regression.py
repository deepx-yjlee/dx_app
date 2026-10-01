"""
Regression guard for GrayscaleResizePreprocessor's per-axis scale.

`GrayscaleResizePreprocessor` resizes to the model's exact input size with a
plain cv::resize, which does not preserve aspect ratio. It records both the
per-axis factors (``ctx.scale_x`` / ``ctx.scale_y``) and the uniform
``ctx.scale``. `scaleKeypoint` / `scaleBox` prefer the per-axis pair when it is
set and fall back to the uniform value otherwise.

Before that, only the uniform value was recorded, so SuperPoint keypoints came
back through the fallback branch: on a 960x540 frame into a 640x480 model,
``ctx.scale`` = min(640/960, 480/540) = 2/3, so y was scaled by 1.5 where the
correct factor is 540/480 = 1.125 -- a 1.33x vertical stretch that pushed ~20%
of the keypoints off the bottom of the canvas.

Seven factories build this preprocessor. Only SuperPoint consumes
`scaleKeypoint`; the DnCNN and ESPCN restoration models never read ``ctx.scale``
or the per-axis pair at all, so the change must leave their output untouched.
That was verified by reverting the header, rebuilding and diffing: dncnn_25,
dncnn_50, espcn_x3 and espcn_x4 came out byte-identical.

Two layers here:

* ``contract`` -- source-level, no NPU, sub-second. Pins the producers and
  consumers of the per-axis pair, so a new consumer (or a preprocessor that
  stops setting it) fails loudly instead of silently shifting some model's
  coordinates.
* ``golden`` -- runs the restoration binaries and checks their output still
  matches the reference captured with the fix in place. Compares decoded pixels
  with a tolerance rather than hashing the encoded file, so a different libjpeg
  build does not produce a false failure.
"""

import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import PROJECT_ROOT, resolve_bin_dir  # noqa: E402

cv2 = pytest.importorskip("cv2", reason="opencv-python required for output checks")

CPP_ROOT = PROJECT_ROOT / "src" / "cpp_example"
PREPROCESSOR = CPP_ROOT / "common" / "processors" / "grayscale_preprocessor.hpp"
CONVERTERS = CPP_ROOT / "common" / "processors" / "result_converters.hpp"

# Every factory that constructs GrayscaleResizePreprocessor. Adding a model here
# means its coordinates now go through the per-axis branch -- confirm that is
# intended before updating this set.
EXPECTED_PREPROCESSOR_USERS = {
    "superpoint/superpoint_480x640",
    "dncnn/dncnn-15_512x512",
    "dncnn/dncnn-25_512x512",
    "dncnn/dncnn-50_512x512",
    "dncnn/dncnn-gray_512x512",
    "espcn/espcn-x3_17x17",
    "espcn/espcn-x4_17x17",
}

# Files that READ ctx.scale_x / ctx.scale_y.
#
#   result_converters.hpp      scaleBox / scaleKeypoint -- the live path, and the
#                              only one any GrayscaleResizePreprocessor user hits
#   retinaface_postprocessor   live, but RetinaFace runs SimpleResizePreprocessor,
#                              which has always set the pair
#   utility/preprocessing.hpp  scaleToOriginal / scaleBoxToOriginal -- no external
#                              caller (YOLACT has its own scaleBoxToOriginal_)
#   rtdetr_postprocessor       live (decodePaddle); every RT-DETR / mask-RT-DETR
#                              factory runs SimpleResizePreprocessor, which sets
#                              the pair, so the uniform fallback is never taken
#
# A new entry means some model's coordinates now depend on the per-axis pair.
# Check whether that model's preprocessor actually sets it before accepting.
EXPECTED_SCALE_XY_READERS = {
    "common/processors/result_converters.hpp",
    "common/processors/retinaface_postprocessor.hpp",
    "common/processors/rtdetr_postprocessor.hpp",
    "common/utility/preprocessing.hpp",
}

# Preprocessors that WRITE the pair (they own an aspect-distorting resize).
EXPECTED_SCALE_XY_WRITERS = {
    "common/processors/grayscale_preprocessor.hpp",
    "common/processors/simple_resize_preprocessor.hpp",
    "common/processors/sfa3d_bev_preprocessor.hpp",
}

# `ctx.scale = std::min(ctx.scale_x, ctx.scale_y)` is how every writer derives the
# uniform fallback. It is a read, but a self-contained one -- not a consumer.
_SELF_READ = re.compile(r"ctx\.scale\s*=\s*std::min\(\s*ctx\.scale_x\s*,\s*ctx\.scale_y\s*\)")


# ---------------------------------------------------------------------------
# contract layer -- source only, no NPU
# ---------------------------------------------------------------------------

def _cpp_sources():
    for path in CPP_ROOT.rglob("*.hpp"):
        yield path
    for path in CPP_ROOT.rglob("*.cpp"):
        yield path


def _rel(path: Path) -> str:
    return path.relative_to(CPP_ROOT).as_posix()


@pytest.mark.contract
def test_preprocessor_sets_per_axis_and_uniform_scale():
    """The resize is aspect-distorting, so both factors must be recorded."""
    src = PREPROCESSOR.read_text(encoding="utf-8")
    body = src[src.index("void process("):]

    assert re.search(r"ctx\.scale_x\s*=", body), (
        "GrayscaleResizePreprocessor no longer sets ctx.scale_x. scaleKeypoint "
        "would fall back to the uniform ctx.scale, stretching y by "
        "(input_h/input_w)/(model_h/model_w) -- the SuperPoint bug."
    )
    assert re.search(r"ctx\.scale_y\s*=", body), (
        "GrayscaleResizePreprocessor no longer sets ctx.scale_y (see above)."
    )
    assert re.search(r"ctx\.scale\s*=", body), (
        "ctx.scale must stay set: postprocessors that only know the uniform "
        "factor (nanodet, ssd, tflite_det, yolopv2) still read it."
    )
    assert re.search(r"ctx\.pad_x\s*=\s*0", body) and re.search(r"ctx\.pad_y\s*=\s*0", body), (
        "pad_x/pad_y must stay 0: scaleKeypoint only takes the per-axis branch "
        "when there is no letterbox padding."
    )


@pytest.mark.contract
def test_scale_keypoint_and_box_prefer_per_axis_branch():
    """The converters must keep the guard that selects the per-axis factors."""
    src = CONVERTERS.read_text(encoding="utf-8")
    guard = r"ctx\.pad_x\s*==\s*0\s*&&\s*ctx\.pad_y\s*==\s*0\s*&&\s*ctx\.scale_x\s*>\s*0\s*&&\s*ctx\.scale_y\s*>\s*0"
    assert len(re.findall(guard, src)) == 2, (
        "scaleBox and scaleKeypoint must each gate on "
        "pad_x==0 && pad_y==0 && scale_x>0 && scale_y>0. Losing the guard sends "
        "aspect-distorting preprocessors back through the uniform branch."
    )
    for fn in ("scaleBox", "scaleKeypoint"):
        assert f"inline void {fn}(" in src, f"{fn} disappeared from result_converters.hpp"


@pytest.mark.contract
def test_grayscale_preprocessor_user_set_is_pinned():
    """Adding a model to this preprocessor changes how its coordinates scale."""
    found = set()
    for path in CPP_ROOT.rglob("*factory*.hpp"):
        if "GrayscaleResizePreprocessor" in path.read_text(encoding="utf-8"):
            # .../<task>/<family>/<variant>/factory/<variant>_factory.hpp
            #   -> "<family>/<variant>"
            model_dir = path.parent.parent
            found.add(f"{model_dir.parent.name}/{model_dir.name}")

    assert found == EXPECTED_PREPROCESSOR_USERS, (
        "The set of models using GrayscaleResizePreprocessor changed.\n"
        f"  added:   {sorted(found - EXPECTED_PREPROCESSOR_USERS)}\n"
        f"  removed: {sorted(EXPECTED_PREPROCESSOR_USERS - found)}\n"
        "A model added here now maps coordinates with per-axis factors. Confirm "
        "that is correct for it, then update EXPECTED_PREPROCESSOR_USERS."
    )


@pytest.mark.contract
def test_scale_xy_reader_and_writer_sets_are_pinned():
    """Only the shared converters may read the per-axis pair."""
    readers, writers = set(), set()
    for path in _cpp_sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"ctx\.scale_[xy]\s*=[^=]", text):
            writers.add(_rel(path))
        for line in text.splitlines():
            if "ctx.scale_x" not in line and "ctx.scale_y" not in line:
                continue
            if re.search(r"ctx\.scale_[xy]\s*=[^=]", line):
                continue          # the assignment itself
            if _SELF_READ.search(line):
                continue          # deriving the uniform fallback
            readers.add(_rel(path))
            break

    assert readers == EXPECTED_SCALE_XY_READERS, (
        "The set of files reading ctx.scale_x/ctx.scale_y changed.\n"
        f"  added:   {sorted(readers - EXPECTED_SCALE_XY_READERS)}\n"
        f"  removed: {sorted(EXPECTED_SCALE_XY_READERS - readers)}\n"
        "A new reader means some model's coordinate mapping now depends on the "
        "per-axis pair. Verify that model's preprocessor sets it -- if it does "
        "not, the reader silently falls back and the coordinates shift."
    )
    assert writers == EXPECTED_SCALE_XY_WRITERS, (
        "The set of preprocessors setting ctx.scale_x/ctx.scale_y changed.\n"
        f"  added:   {sorted(writers - EXPECTED_SCALE_XY_WRITERS)}\n"
        f"  removed: {sorted(EXPECTED_SCALE_XY_WRITERS - writers)}"
    )


@pytest.mark.contract
def test_restoration_postprocessors_ignore_scale():
    """Why DnCNN/ESPCN are unaffected -- assert the causal reason, not the symptom."""
    offenders = []
    for name in ("espcn_postprocessor.hpp", "restoration_postprocessor.hpp"):
        path = CPP_ROOT / "common" / "processors" / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in ("ctx.scale", "scaleKeypoint", "scaleBox"):
            if token in text:
                offenders.append(f"{name} reads {token}")

    assert not offenders, (
        "A restoration postprocessor now depends on the scale factors: "
        f"{offenders}. GrayscaleResizePreprocessor is shared with SuperPoint, so "
        "changing what it records would start moving DnCNN/ESPCN output too. "
        "Re-run the golden tests below and refresh the references if intended."
    )


@pytest.mark.contract
def test_grayscale_users_only_reach_the_converter_readers():
    """The direct answer to "does this change affect the other examples?".

    Of the three readers of the per-axis pair, only `result_converters.hpp`
    (scaleBox / scaleKeypoint) is reachable from a GrayscaleResizePreprocessor
    model. If a DnCNN or ESPCN factory ever pulls in `retinaface_postprocessor`
    or `scaleToOriginal`, what this preprocessor records starts moving its
    output too, and the golden references below need to be re-captured.
    """
    forbidden = {
        "retinaface_postprocessor.hpp": "retinaface_postprocessor",
        "preprocessing.hpp scaleToOriginal": "scaleToOriginal",
    }
    offenders = []
    for path in CPP_ROOT.rglob("*factory*.hpp"):
        text = path.read_text(encoding="utf-8")
        if "GrayscaleResizePreprocessor" not in text:
            continue
        model_dir = path.parent.parent
        model = f"{model_dir.parent.name}/{model_dir.name}"
        for label, token in forbidden.items():
            if token in text:
                offenders.append(f"{model} -> {label}")

    assert not offenders, (
        "A GrayscaleResizePreprocessor model now reaches a per-axis-scale reader "
        f"other than scaleBox/scaleKeypoint: {offenders}. Re-capture the GOLDEN "
        "references and confirm the new mapping is what you want."
    )


# ---------------------------------------------------------------------------
# golden layer -- runs the binaries
# ---------------------------------------------------------------------------

_DENOISE_IMG = "sample/img/sample_denoising.jpg"
_LOWRES_IMG = "sample/img/sample_lowres275x150.png"

# Captured on DX-M1 with the per-axis fix in place, and confirmed byte-identical
# to a build with the pre-fix header. shape is exact; mean/std carry a tolerance
# so a different JPEG encoder does not trip the test.
GOLDEN = {
    "dncnn_15":         dict(dxnn="dncnn-15_512x512.dxnn",   image=_DENOISE_IMG, shape=(512, 1024), mean=124.34, std=63.90),
    "dncnn_25":         dict(dxnn="dncnn-25_512x512.dxnn",   image=_DENOISE_IMG, shape=(512, 1024), mean=124.42, std=61.38),
    "dncnn_50":         dict(dxnn="dncnn-50_512x512.dxnn",   image=_DENOISE_IMG, shape=(512, 1024), mean=124.30, std=56.20),
    "dncnn_gray_blind": dict(dxnn="dncnn-gray_512x512.dxnn", image=_DENOISE_IMG, shape=(512, 1024), mean=124.65, std=56.97),
    "espcn_x3":         dict(dxnn="espcn-x3_17x17.dxnn",     image=_LOWRES_IMG,  shape=(450, 1654), mean=102.61, std=46.13),
    "espcn_x4":         dict(dxnn="espcn-x4_17x17.dxnn",     image=_LOWRES_IMG,  shape=(600, 2204), mean=102.82, std=45.79),
}

MEAN_TOL = 1.0   # grey levels
STD_TOL = 1.0


def _run_and_load(model: str, spec: dict, tmp_path: Path):
    """Run the model's <dxnn stem>_sync with --save and return the decoded output image."""
    exe = resolve_bin_dir() / f"{Path(spec['dxnn']).stem}_sync"
    if not exe.exists():
        pytest.skip(f"{exe.name} not built")
    dxnn = PROJECT_ROOT / "assets" / "models" / spec["dxnn"]
    if not dxnn.exists():
        pytest.skip(f"{spec['dxnn']} not downloaded")
    image = PROJECT_ROOT / spec["image"]
    if not image.exists():
        pytest.skip(f"{spec['image']} missing")

    result = subprocess.run(
        [str(exe), "-m", str(dxnn), "-i", str(image),
         "--no-display", "-s", "--save-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=300, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, (
        f"{exe.name} exited {result.returncode}\n{result.stdout[-1500:]}\n{result.stderr[-1500:]}"
    )

    saved = sorted(p for p in tmp_path.rglob("*") if p.suffix.lower() in (".jpg", ".png"))
    assert saved, f"{exe.name} --save produced no image under {tmp_path}"
    img = cv2.imread(str(saved[0]), cv2.IMREAD_UNCHANGED)
    assert img is not None, f"could not decode {saved[0]}"
    return img


@pytest.mark.golden
@pytest.mark.parametrize("model", sorted(GOLDEN))
def test_restoration_output_unchanged_by_per_axis_scale(model, tmp_path):
    """DnCNN/ESPCN must stay bit-for-bit indifferent to the scale bookkeeping."""
    spec = GOLDEN[model]
    img = _run_and_load(model, spec, tmp_path)
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img

    assert grey.shape == spec["shape"], (
        f"{model} output geometry changed: {grey.shape} != {spec['shape']}. "
        "A scale-mapping regression shows up here first."
    )
    assert abs(float(grey.mean()) - spec["mean"]) <= MEAN_TOL, (
        f"{model} output content drifted: mean {grey.mean():.2f} vs "
        f"reference {spec['mean']:.2f} (tolerance {MEAN_TOL})"
    )
    assert abs(float(grey.std()) - spec["std"]) <= STD_TOL, (
        f"{model} output content drifted: std {grey.std():.2f} vs "
        f"reference {spec['std']:.2f} (tolerance {STD_TOL})"
    )


# The input MUST NOT share the model's 4:3 aspect ratio. On a 4:3 source the two
# branches of scaleKeypoint compute the same thing (scale_x == scale_y), so the
# bug is invisible: measured on the pre-fix binary, 768x576 sample_street scores
# 11.9x and passes, while 1920x1080 sample_crowd scores 1.3x and fails.
SUPERPOINT_IMAGE = "sample/img/sample_crowd.jpg"
MODEL_ASPECT = 640 / 480


@pytest.mark.contract
def test_superpoint_probe_image_is_not_model_aspect():
    """Guard the guard: a 4:3 probe image would make the test below vacuous."""
    image = PROJECT_ROOT / SUPERPOINT_IMAGE
    if not image.exists():
        pytest.skip(f"{SUPERPOINT_IMAGE} missing")
    img = cv2.imread(str(image))
    assert img is not None, f"could not decode {image}"
    h, w = img.shape[:2]
    assert abs((w / h) - MODEL_ASPECT) > 0.05, (
        f"{SUPERPOINT_IMAGE} is {w}x{h}, aspect {w / h:.3f}, which matches the "
        f"model's {MODEL_ASPECT:.3f}. On such an input scale_x == scale_y and both "
        "branches of scaleKeypoint agree, so test_superpoint_keypoints_land_on_corners "
        "would pass even with the per-axis factors removed. Pick a non-4:3 image."
    )


@pytest.mark.golden
def test_superpoint_keypoints_land_on_corners(tmp_path):
    """The positive half: the fix must keep SuperPoint keypoints on real corners.

    Measured on a 1920x1080 input: with the uniform fallback the rendered
    keypoints score 1.3x a random-position control on Shi-Tomasi corner response
    -- i.e. no better than chance. With the per-axis factors they score >20x.
    """
    exe = resolve_bin_dir() / "superpoint_480x640_sync"
    if not exe.exists():
        pytest.skip("superpoint_480x640_sync not built")
    dxnn = PROJECT_ROOT / "assets" / "models" / "superpoint_480x640.dxnn"
    if not dxnn.exists():
        pytest.skip("superpoint_480x640.dxnn not downloaded")
    image = PROJECT_ROOT / SUPERPOINT_IMAGE
    if not image.exists():
        pytest.skip(f"{SUPERPOINT_IMAGE} missing")

    result = subprocess.run(
        [str(exe), "-m", str(dxnn), "-i", str(image),
         "--no-display", "-s", "--save-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=300, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"{exe.name} exited {result.returncode}\n{result.stderr[-1500:]}"
    saved = sorted(p for p in tmp_path.rglob("*") if p.suffix.lower() in (".jpg", ".png"))
    assert saved, f"{exe.name} --save produced no image"

    out = cv2.imread(str(saved[0]))
    src = cv2.imread(str(image))
    src = cv2.resize(src, (out.shape[1], out.shape[0]))

    response = cv2.cornerMinEigenVal(
        cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32), 7, 3)
    response /= max(float(response.max()), 1e-12)

    # green dots are the keypoints the visualizer drew
    b, g, r = (out[:, :, i].astype(int) for i in range(3))
    mask = ((g > 170) & (r < 110) & (b < 110)).astype(np.uint8)
    n_lab, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    pts = centroids[1:][stats[1:, 4] >= 2].astype(int)
    if len(pts) < 50:
        pytest.skip(f"only {len(pts)} keypoint blobs detected; visualizer style may have changed")

    def sample(points):
        vals = []
        for x, y in points:
            if 0 <= x < response.shape[1] and 0 <= y < response.shape[0]:
                vals.append(response[max(0, y - 1):y + 2, max(0, x - 1):x + 2].max())
        return np.asarray(vals)

    rng = np.random.default_rng(0)
    control = sample(np.stack([rng.uniform(0, response.shape[1], 2000),
                               rng.uniform(0, response.shape[0], 2000)], 1).astype(int))
    actual = sample(pts)

    ratio = float(np.median(actual)) / max(float(np.median(control)), 1e-12)
    assert ratio >= 10.0, (
        f"rendered keypoints score only {ratio:.1f}x a random-position control on "
        "corner response (expected >=10x). They are no longer landing on image "
        "features -- the most likely cause is scaleKeypoint falling back to the "
        "uniform ctx.scale for an aspect-distorting resize."
    )
