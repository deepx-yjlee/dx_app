"""
Vit_l_14_datacomp_xl_s13b_b90k Factory
"""
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.

from common.base import IEmbeddingFactory
from common.processors import CLIPImagePostprocessor, SimpleResizePreprocessor
from common.visualizers import EmbeddingVisualizer

# open_clip canonical normalization, on [0,1] pixels. These are the DEFAULT rather than
# an opt-in option because this .dxnn is an open_clip CLIP ViT-L/14 (datacomp_xl) whose
# input tensor is float32 [1,3,224,224] with NO normalization baked into the compiled
# graph: any other normalization silently relocates image embeddings into a different
# space from host-encoded text, so retrieval degrades without ever raising an error.
# The values are this checkpoint's own preprocess_cfg
# (laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K), which is the standard OpenAI CLIP pair.
# On-NPU A/B over 8 sample images moved the mean cross-image cosine from 0.4530 (the
# previous x/255 stretch) to 0.4022 -- the same direction and magnitude as the ViT-B/32
# sibling, where the host-FP32 p5 cosine went 0.4724 -> 0.8350.
CLIP_MEAN = [0.48145466, 0.4578275, 0.40821073]
CLIP_STD = [0.26862954, 0.26130258, 0.27577711]


def _check_zero_one_units(values, name: str) -> list:
    """Reject mean/std overrides given in 0-255 units.

    Several factories in this tree legitimately pass raw 0-255 means (e.g. RetinaFace
    passes [104, 117, 123]), so copying that shape here is an easy and completely silent
    mistake: SimpleResizePreprocessor would accept it and emit a plausible-looking but
    wrongly normalized tensor. Fail loudly instead.
    """
    values = [float(v) for v in values]
    if len(values) != 3:
        raise ValueError(f"{name} must have 3 per-channel values, got {len(values)}")
    for channel, value in enumerate(values):
        # A zero mean is meaningful (it is the identity); a zero std would divide by 0.
        too_small = value < 0.0 if name == "mean" else value <= 0.0
        if too_small or value > 1.0:
            raise ValueError(
                f"{name}[{channel}]={value!r} is outside [0,1]. This factory takes "
                f"{name} in open_clip [0,1] units (e.g. {name}="
                f"{CLIP_MEAN if name == 'mean' else CLIP_STD}), not 0-255 units; "
                f"divide a 0-255 value by 255."
            )
    return values


class Vit_l_14_datacomp_xl_s13b_b90kFactory(IEmbeddingFactory):
    """Factory for creating Vit_l_14_datacomp_xl_s13b_b90k components."""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def create_preprocessor(self, input_width: int, input_height: int):
        # SimpleResizePreprocessor applies mean/std to the RAW 0-255 resized image, so
        # the [0,1]-scale constants must be rescaled on the way in. The two forms are
        # algebraically identical: (v - 255m) / (255s) == (v/255 - m) / s. Config
        # overrides are given in [0,1] units too, matching the open_clip convention.
        mean = _check_zero_one_units(self.config.get("mean", CLIP_MEAN), "mean")
        std = _check_zero_one_units(self.config.get("std", CLIP_STD), "std")
        return SimpleResizePreprocessor(
            input_width, input_height,
            mean=[m * 255.0 for m in mean],
            std=[s * 255.0 for s in std],
        )

    def create_postprocessor(self, input_width: int, input_height: int):
        return CLIPImagePostprocessor(input_width, input_height, self.config)

    def create_visualizer(self):
        return EmbeddingVisualizer()

    def get_model_name(self) -> str:
        return "vit_l_14_datacomp_xl_s13b_b90k"

    def get_task_type(self) -> str:
        return "embedding"
