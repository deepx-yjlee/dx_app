# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Declarative multi-model pipeline.

A pipeline JSON file is the composition. Each stage points at an existing
single-model variant factory. ``depends_on`` plus ``bind`` describe how the
outputs connect. The runner executes that graph; demo code does not.

.. code-block:: json

    {
      "name": "hand_cascade",
      "fuse": "hand_cascade",
      "stages": [
        {"id": "palm", "task": "hand_detection",
         "family": "mediapipe_hand_detector",
         "variant": "mediapipe-hand-detector_192x192"},
        {"id": "landmark", "task": "hand_landmark",
         "family": "mediapipe_hands_lite",
         "variant": "mediapipe-hands-lite_224x224",
         "depends_on": ["palm"],
         "bind": {"op": "roi", "source": "palm"}}
      ]
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


class PipelineError(ValueError):
    """The pipeline JSON does not describe an executable graph."""


@dataclass(frozen=True)
class BindSpec:
    """How a stage turns an upstream result into its own input."""

    op: str
    source: str


@dataclass(frozen=True)
class StageSpec:
    """One node in the pipeline graph."""

    id: str
    order: int
    kind: str
    depends_on: tuple[str, ...] = ()
    bind: Optional[BindSpec] = None
    task: str = ""
    family: str = ""
    variant: str = ""
    model: str = ""
    op: str = ""


@dataclass(frozen=True)
class Pipeline:
    """A loaded pipeline file."""

    name: str
    fuse: str
    stages: tuple[StageSpec, ...]
    fuse_config: Mapping[str, Any] = field(default_factory=dict)
    path: Optional[Path] = None

    def stage(self, stage_id: str) -> StageSpec:
        """Return the stage with this id."""
        for spec in self.stages:
            if spec.id == stage_id:
                return spec
        raise PipelineError(f"pipeline {self.name!r} has no stage {stage_id!r}")


def load_pipeline(path: str | Path) -> Pipeline:
    """Read and validate a pipeline JSON file."""
    pipeline_path = Path(path)
    try:
        payload = json.loads(pipeline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineError(f"{pipeline_path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PipelineError(f"{pipeline_path} must contain a JSON object")
    return parse_pipeline(payload, pipeline_path)


def parse_pipeline(payload: Mapping[str, Any], path: Optional[Path] = None) -> Pipeline:
    """Validate an already-decoded pipeline object."""
    name = _require_str(payload, "name")
    fuse = _require_str(payload, "fuse")
    raw_stages = payload.get("stages")
    if not isinstance(raw_stages, list) or not raw_stages:
        raise PipelineError(f"pipeline {name!r} needs a non-empty stages list")
    fuse_config = payload.get("fuse_config") or {}
    if not isinstance(fuse_config, dict):
        raise PipelineError(f"pipeline {name!r} fuse_config must be an object")

    stages = tuple(_parse_stage(item, index) for index, item in enumerate(raw_stages))
    _validate_graph(name, stages)
    return Pipeline(
        name=name,
        fuse=fuse,
        stages=stages,
        fuse_config=fuse_config,
        path=path,
    )


def execution_waves(stages: Sequence[StageSpec]) -> list[list[StageSpec]]:
    """Group stages into dependency waves, preserving declaration order.

    Stages in the same wave do not depend on each other, so they all see the
    same frame (or the same already-finished upstream results).
    """
    pending = {spec.id: spec for spec in stages}
    finished: set[str] = set()
    waves: list[list[StageSpec]] = []
    while pending:
        ready = [
            spec for spec in pending.values()
            if all(dep in finished for dep in spec.depends_on)
        ]
        if not ready:
            raise PipelineError(
                "pipeline graph has a cycle or a missing dependency: "
                + ", ".join(sorted(pending))
            )
        ready.sort(key=lambda spec: spec.order)
        waves.append(ready)
        for spec in ready:
            finished.add(spec.id)
            del pending[spec.id]
    return waves


def _parse_stage(item: Any, index: int) -> StageSpec:
    if not isinstance(item, dict):
        raise PipelineError(f"stage[{index}] must be an object")
    stage_id = _require_str(item, "id")
    kind = str(item.get("kind") or "npu")
    if kind not in ("npu", "cpu"):
        raise PipelineError(f"stage {stage_id!r} kind must be 'npu' or 'cpu'")
    depends = item.get("depends_on") or []
    if not isinstance(depends, list) or not all(isinstance(dep, str) and dep for dep in depends):
        raise PipelineError(f"stage {stage_id!r} depends_on must be a list of stage ids")
    bind = _parse_bind(stage_id, item.get("bind"))
    if bind is not None and bind.source not in depends:
        raise PipelineError(
            f"stage {stage_id!r} bind source {bind.source!r} must be listed in depends_on"
        )
    task = str(item.get("task") or "")
    family = str(item.get("family") or "")
    variant = str(item.get("variant") or "")
    op_name = str(item.get("op") or "")
    if kind == "npu" and not (task and family and variant):
        raise PipelineError(
            f"NPU stage {stage_id!r} needs task, family, and variant"
        )
    if kind == "cpu" and not op_name:
        raise PipelineError(f"CPU stage {stage_id!r} needs op")
    model = str(item.get("model") or "")
    if kind == "npu" and not model:
        model = f"{variant}.dxnn"
    return StageSpec(
        id=stage_id,
        order=index,
        kind=kind,
        depends_on=tuple(depends),
        bind=bind,
        task=task,
        family=family,
        variant=variant,
        model=model,
        op=op_name,
    )


def _parse_bind(stage_id: str, raw: Any) -> Optional[BindSpec]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PipelineError(f"stage {stage_id!r} bind must be an object")
    op_name = str(raw.get("op") or "")
    source = str(raw.get("source") or "")
    if not op_name or not source:
        raise PipelineError(f"stage {stage_id!r} bind needs op and source")
    return BindSpec(op=op_name, source=source)


def _validate_graph(name: str, stages: Sequence[StageSpec]) -> None:
    seen: set[str] = set()
    for spec in stages:
        if spec.id in seen:
            raise PipelineError(f"pipeline {name!r} repeats stage id {spec.id!r}")
        seen.add(spec.id)
    for spec in stages:
        missing = [dep for dep in spec.depends_on if dep not in seen]
        if missing:
            raise PipelineError(
                f"stage {spec.id!r} depends on unknown stage(s): {', '.join(missing)}"
            )
    execution_waves(stages)


def _require_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PipelineError(f"pipeline field {key!r} must be a non-empty string")
    return value.strip()
