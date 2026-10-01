# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Execute a multi-model pipeline JSON file."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .binds import bound_inputs
from .cpu_ops import CPU_OPS
from .factory import MultiModelFactory
from .fusers import fuse_outputs
from .pipeline import PipelineError, StageSpec, execution_waves
from .stage import resolve_stage_model

logger = logging.getLogger(__name__)


@dataclass
class FrameGraphResult:
    """Outputs of every stage plus the fuse result for one frame."""

    outputs: dict[str, Any] = field(default_factory=dict)
    fused: dict[str, Any] = field(default_factory=dict)


class _NpuStage:
    """One variant factory and the SyncRunner that owns its engine."""

    def __init__(self, factory: Any, model_path: Path):
        from common.runner import SyncRunner

        self.factory = factory
        self.model_path = model_path
        self.runner = SyncRunner(factory)
        self.runner._init_engine(str(model_path))
        logger.info(
            "stage ready: %s input=%dx%d model=%s",
            factory.get_model_name(),
            self.runner.input_width,
            self.runner.input_height,
            model_path.name,
        )

    def infer(self, frame_bgr: np.ndarray) -> list[Any]:
        """Preprocess, run, and postprocess one BGR image."""
        tensor, context = self.runner.preprocess(frame_bgr)
        return list(self.runner.postprocess(self.runner.infer(tensor), context) or [])


class MultiModelRunner:
    """Run the waves declared by a :class:`MultiModelFactory`."""

    def __init__(
        self,
        factory: MultiModelFactory,
        models_dir: Path | None = None,
    ):
        self.factory = factory
        self.models_dir = Path(models_dir) if models_dir else None
        self._engines: dict[str, _NpuStage] = {}
        self._model_paths: dict[str, Path] | None = None

    @classmethod
    def from_json(
        cls,
        path: str | Path,
        models_dir: Path | None = None,
    ) -> "MultiModelRunner":
        """Open a pipeline file. Engines are created on the first frame."""
        return cls(MultiModelFactory.from_json(path), models_dir)

    def run_frame(self, frame_bgr: np.ndarray) -> FrameGraphResult:
        """Execute every stage of one BGR frame and fuse the outputs."""
        pipeline = self.factory.pipeline
        outputs: dict[str, Any] = {}
        for wave in execution_waves(pipeline.stages):
            for spec in wave:
                outputs[spec.id] = self._run_stage(spec, frame_bgr, outputs)
        fused = fuse_outputs(pipeline.fuse, outputs, pipeline.fuse_config)
        return FrameGraphResult(outputs=outputs, fused=fused)

    def _run_stage(
        self,
        spec: StageSpec,
        frame_bgr: np.ndarray,
        outputs: dict[str, Any],
    ) -> Any:
        if spec.kind == "cpu":
            op = CPU_OPS.get(spec.op)
            if op is None:
                raise PipelineError(f"stage {spec.id!r} has unknown cpu op {spec.op!r}")
            return op(frame_bgr, outputs)
        engine = self._engine(spec)
        if spec.bind is None:
            return engine.infer(frame_bgr)
        upstream = outputs.get(spec.bind.source) or []
        calls = []
        for meta, crop in bound_inputs(spec.bind, frame_bgr, upstream):
            calls.append({"input": meta, "results": engine.infer(crop)})
        return calls

    def _engine(self, spec: StageSpec) -> _NpuStage:
        cached = self._engines.get(spec.id)
        if cached is not None:
            return cached
        model_path = self._stage_model_paths()[spec.id]
        stage_factory = self.factory.create_stage_factory(spec)
        engine = _NpuStage(stage_factory, model_path)
        self._engines[spec.id] = engine
        return engine

    def _stage_model_paths(self) -> dict[str, Path]:
        """Every NPU stage's model, found before any engine opens.

        A missing file then fails fast whichever stage it belongs to, instead
        of after the earlier stages' engines were created.
        """
        if self._model_paths is None:
            pipeline_dir: Optional[Path] = self.factory.pipeline.path
            pipeline_dir = pipeline_dir.parent if pipeline_dir is not None else None
            self._model_paths = {
                spec.id: resolve_stage_model(spec, pipeline_dir, self.models_dir)
                for spec in self.factory.pipeline.stages
                if spec.kind == "npu"
            }
        return self._model_paths
