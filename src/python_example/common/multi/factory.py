# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Multi-model factory: the pipeline JSON is the wiring, variant factories are the stages."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .pipeline import Pipeline, StageSpec, load_pipeline
from .stage import load_variant_factory


class MultiModelFactory:
    """Build the single-model factories named by a pipeline file.

    This is not an IFactory. A single-model factory owns one preprocessor and
    one postprocessor. A multi-model factory owns a graph of those factories.
    """

    def __init__(self, pipeline: Pipeline, example_root: Path | None = None):
        self.pipeline = pipeline
        self.example_root = example_root

    @classmethod
    def from_json(cls, path: str | Path, example_root: Path | None = None) -> "MultiModelFactory":
        """Load ``pipeline.json`` and keep it as this factory's definition."""
        return cls(load_pipeline(path), example_root)

    def get_model_name(self) -> str:
        """Pipeline name, used in logs and the saved-result title."""
        return self.pipeline.name

    def get_task_type(self) -> str:
        """Always ``multi_model``. The fuse name distinguishes the demo."""
        return "multi_model"

    def stage_specs(self) -> tuple[StageSpec, ...]:
        """Stages in declaration order."""
        return self.pipeline.stages

    def create_stage_factory(self, spec: StageSpec) -> Any:
        """The existing variant IFactory for one NPU stage."""
        if spec.kind != "npu":
            raise TypeError(f"stage {spec.id!r} is {spec.kind}, not an NPU factory")
        return load_variant_factory(spec, self.example_root)
