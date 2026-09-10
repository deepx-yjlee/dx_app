"""
Rn50x16_openai Factory
"""
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.

from common.base import IEmbeddingFactory
from common.processors import CLIPImagePostprocessor, SimpleResizePreprocessor
from common.visualizers import EmbeddingVisualizer


class Rn50x16_openaiFactory(IEmbeddingFactory):
    """Factory for creating Rn50x16_openai components."""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def create_preprocessor(self, input_width: int, input_height: int):
        # No normalization here, deliberately -- unlike the CLIP ViT siblings in this
        # directory. This .dxnn's input tensor is uint8 NHWC [1,384,384,3] and the
        # open_clip transform is compiled into the graph, so the model wants the RAW
        # resized RGB image; applying mean/std (or a plain x/255) would run the
        # normalization twice.
        #
        # Emitting float32 is not merely redundant, it destroys the input:
        # SyncRunner._prep_input coerces to the model's dtype, and for a uint8 model
        # that is astype(np.uint8), which floors every [0,1] value to 0 (measured
        # 0.0018% non-zero). The encoder then returns essentially the same vector for
        # every image -- cross-image cosine over 8 sample images was 0.9986/0.9991/1.0000
        # (min/mean/max) with the old normalize_float=True, versus 0.2110/0.3890/0.8602
        # with the raw image below.
        return SimpleResizePreprocessor(input_width, input_height)

    def create_postprocessor(self, input_width: int, input_height: int):
        return CLIPImagePostprocessor(input_width, input_height, self.config)

    def create_visualizer(self):
        return EmbeddingVisualizer()

    def get_model_name(self) -> str:
        return "rn50x16_openai"

    def get_task_type(self) -> str:
        return "embedding"
