"""The CLIP ViT-B/32 factory must normalize with open_clip canonical mean/std.

The .dxnn is an open_clip CLIP ViT-B-32-256 (datacomp_s34b_b86k), trained under
open_clip's transform. The factory previously built a plain ``x/255`` stretch
(``normalize_float=True``) with no mean/std, which silently places image embeddings in a
different space from host-encoded text: retrieval degrades without any error. Measured
against host FP32 over 21 sample images, p5 cosine was 0.4724 without these constants
and 0.8350 with them.

These tests need no ``.dxnn`` and no NPU: the factory class is imported directly and
only its preprocessor's arithmetic is checked on a synthetic frame.

Two conventions this file pins down, because getting either wrong is silent:

**Units.** ``SimpleResizePreprocessor`` applies mean/std to the RAW 0-255 resized image,
while these constants (and any config override) are in open_clip's [0,1] units, so the
factory rescales by 255 on the way in. Asserting on the [0,1] form keeps that honest.

**Channel order: the emitted tensor is RGB, channel 0 = R.** Determined by reading
``SimpleResizePreprocessor.process``: with the default ``bgr=False`` it runs
``cv2.cvtColor(input_image, cv2.COLOR_BGR2RGB)`` before resizing, then subtracts
``mean[0]`` from that first (red) channel; verified empirically against a BGR frame with
three distinct channel values. The frames below therefore use DISTINCT per-channel
values and compare per channel WITHOUT sorting -- sorting would make these tests blind
to a channel-order bug, which is exactly the sibling of the defect they exist to catch.
"""
from __future__ import annotations

import numpy as np
import pytest

from embedding.vit_b_32_256_datacomp_s34b_b86k.factory import (
    Vit_b_32_256_datacomp_s34b_b86kFactory,
)
from embedding.vit_b_32_256_datacomp_s34b_b86k.factory import (
    vit_b_32_256_datacomp_s34b_b86k_factory as clip_factory_module,
)

# open_clip's published constants for this checkpoint, in channel order R, G, B.
# Hard-coded rather than imported so that editing the factory's constants fails here.
OPEN_CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
OPEN_CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

# A BGR frame whose three channels are distinct, so a swapped channel is detectable.
FRAME_B, FRAME_G, FRAME_R = 40, 128, 200


def _bgr_frame(blue: int, green: int, red: int) -> np.ndarray:
    frame = np.zeros((256, 256, 3), dtype=np.uint8)
    frame[:, :, 0] = blue
    frame[:, :, 1] = green
    frame[:, :, 2] = red
    return frame


def _channel_values(tensor: np.ndarray) -> np.ndarray:
    """Per-channel value at one pixel of a CHW or HWC tensor.

    One pixel rather than a mean: every pixel is identical here, and averaging 65536
    float32 values accumulates ~2e-4 of error, which is larger than the tolerance these
    assertions want to use.
    """
    return tensor[:, 0, 0] if tensor.shape[0] == 3 else tensor[0, 0, :]


def _preprocessor(config=None):
    return Vit_b_32_256_datacomp_s34b_b86kFactory(config or {}).create_preprocessor(256, 256)


def test_factory_constants_are_the_open_clip_canonical_values():
    np.testing.assert_allclose(
        np.array(clip_factory_module.CLIP_MEAN, dtype=np.float32), OPEN_CLIP_MEAN,
        rtol=0, atol=1e-7,
    )
    np.testing.assert_allclose(
        np.array(clip_factory_module.CLIP_STD, dtype=np.float32), OPEN_CLIP_STD,
        rtol=0, atol=1e-7,
    )


def test_preprocessor_applies_canonical_mean_std_per_channel():
    """Distinct channels + unsorted comparison: catches wrong values AND wrong order."""
    tensor, _ = _preprocessor().process(_bgr_frame(FRAME_B, FRAME_G, FRAME_R))

    # The tensor is RGB, so the R channel of the BGR input comes first.
    rgb = np.array([FRAME_R, FRAME_G, FRAME_B], dtype=np.float32) / 255.0
    expected = (rgb - OPEN_CLIP_MEAN) / OPEN_CLIP_STD

    assert tensor.dtype == np.float32
    np.testing.assert_allclose(_channel_values(tensor), expected, rtol=1e-4, atol=1e-4)


def test_channel_order_is_rgb_not_bgr():
    """Pins the cvtColor: if the RGB conversion is dropped, these values swap."""
    tensor, _ = _preprocessor().process(_bgr_frame(FRAME_B, FRAME_G, FRAME_R))
    actual = _channel_values(tensor)

    bgr = np.array([FRAME_B, FRAME_G, FRAME_R], dtype=np.float32) / 255.0
    if_bgr_were_emitted = (bgr - OPEN_CLIP_MEAN) / OPEN_CLIP_STD

    assert not np.allclose(actual, if_bgr_were_emitted, rtol=1e-3, atol=1e-3), (
        "preprocessor emitted BGR - the BGR->RGB conversion was lost"
    )
    # Red is the brightest channel here, so after normalization it must stay the largest.
    assert int(np.argmax(actual)) == 0, f"channel 0 should be R (brightest), got {actual}"


def test_a_plain_zero_one_stretch_is_not_what_the_factory_produces():
    """Guards the specific regression: reverting to normalize_float=True."""
    tensor, _ = _preprocessor().process(_bgr_frame(FRAME_B, FRAME_G, FRAME_R))

    stretch = np.array([FRAME_R, FRAME_G, FRAME_B], dtype=np.float32) / 255.0
    assert not np.allclose(_channel_values(tensor), stretch, rtol=1e-3, atol=1e-3), (
        "preprocessor returned a plain [0,1] stretch - the canonical mean/std was lost"
    )


def test_config_overrides_mean_and_std_in_zero_one_units():
    tensor, _ = _preprocessor({"mean": [0.0, 0.0, 0.0], "std": [1.0, 1.0, 1.0]}).process(
        _bgr_frame(FRAME_B, FRAME_G, FRAME_R)
    )
    # mean=0 / std=1 in [0,1] units is exactly the identity x/255, so the channels must
    # come back as the plain stretch - not 0-255 values, which forgetting the rescale
    # would give.
    expected = np.array([FRAME_R, FRAME_G, FRAME_B], dtype=np.float32) / 255.0
    np.testing.assert_allclose(_channel_values(tensor), expected, rtol=1e-5, atol=1e-5)


@pytest.mark.parametrize(
    "config",
    [
        # The exact shape a caller would copy from retinaface_mobilenet_v1_*_factory.py,
        # which legitimately passes raw 0-255 means.
        {"mean": [104.0, 117.0, 123.0]},
        {"mean": [0.485, 0.456, 0.406], "std": [58.395, 57.12, 57.375]},
        {"mean": [-0.1, 0.5, 0.5]},
        {"std": [0.0, 0.5, 0.5]},
    ],
)
def test_out_of_range_override_is_rejected(config):
    """0-255 units must raise, not silently produce a wrongly normalized tensor."""
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        _preprocessor(config)


def test_the_rejection_message_names_the_value_and_the_convention():
    with pytest.raises(ValueError) as excinfo:
        _preprocessor({"mean": [104.0, 117.0, 123.0]})
    message = str(excinfo.value)
    assert "104.0" in message, message
    assert "255" in message, message


def test_a_wrong_length_override_is_rejected():
    with pytest.raises(ValueError, match="3 per-channel values"):
        _preprocessor({"mean": [0.5, 0.5]})
