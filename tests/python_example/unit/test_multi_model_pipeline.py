# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Pipeline JSON loads into a graph without opening an NPU engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from common.multi.factory import MultiModelFactory
from common.multi.fusers import fuse_outputs
from common.multi.pipeline import PipelineError, execution_waves, load_pipeline
from common.multi.stage import variant_factory_dir

_MULTI_ROOT = (
    Path(__file__).resolve().parents[3] / "src" / "python_example" / "multi_model"
)
_PIPELINES = (
    "hand_cascade/pipeline.json",
    "logistics_volume/pipeline.json",
    "dms_clip/pipeline.json",
)


@pytest.mark.parametrize("relative", _PIPELINES)
def test_pipeline_json_is_a_valid_graph(relative: str) -> None:
    pipeline = load_pipeline(_MULTI_ROOT / relative)
    factory = MultiModelFactory(pipeline)
    assert factory.get_task_type() == "multi_model"
    assert factory.get_model_name() == pipeline.name
    waves = execution_waves(pipeline.stages)
    assert sum(len(wave) for wave in waves) == len(pipeline.stages)
    for spec in pipeline.stages:
        if spec.kind != "npu":
            continue
        assert variant_factory_dir(spec).joinpath("__init__.py").is_file()


def test_hand_cascade_landmark_waits_for_palm() -> None:
    pipeline = load_pipeline(_MULTI_ROOT / "hand_cascade/pipeline.json")
    waves = execution_waves(pipeline.stages)
    assert [spec.id for spec in waves[0]] == ["palm"]
    assert [spec.id for spec in waves[1]] == ["landmark"]


def test_logistics_stages_share_one_wave() -> None:
    pipeline = load_pipeline(_MULTI_ROOT / "logistics_volume/pipeline.json")
    waves = execution_waves(pipeline.stages)
    assert len(waves) == 1
    assert {spec.id for spec in waves[0]} == {"det", "seg", "depth"}


def test_dms_clip_runs_after_face() -> None:
    pipeline = load_pipeline(_MULTI_ROOT / "dms_clip/pipeline.json")
    waves = execution_waves(pipeline.stages)
    assert {spec.id for spec in waves[0]} == {"face", "pose"}
    assert {spec.id for spec in waves[1]} == {"clip", "headpose"}


def test_cycle_is_rejected() -> None:
    with pytest.raises(PipelineError):
        load_pipeline_payload = {
            "name": "loop",
            "fuse": "hand_cascade",
            "stages": [
                {"id": "a", "kind": "cpu", "op": "face_solvepnp", "depends_on": ["b"]},
                {"id": "b", "kind": "cpu", "op": "face_solvepnp", "depends_on": ["a"]},
            ],
        }
        from common.multi.pipeline import parse_pipeline
        parse_pipeline(load_pipeline_payload)


def test_fuse_names_match_the_demos() -> None:
    for relative, fuse_name in (
        ("hand_cascade/pipeline.json", "hand_cascade"),
        ("logistics_volume/pipeline.json", "logistics_volume"),
        ("dms_clip/pipeline.json", "dms"),
    ):
        pipeline = load_pipeline(_MULTI_ROOT / relative)
        assert pipeline.fuse == fuse_name
        fused = fuse_outputs(pipeline.fuse, {}, pipeline.fuse_config)
        assert "event" in fused
