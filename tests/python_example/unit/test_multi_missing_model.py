"""Python multi_model runtime: a missing model names its stage, file and download command.

The Python counterpart of tests/cpp_example/test_multi_model_run.py. The
pipeline is copied into tmp_path and ``models_dir`` is an empty temp dir, so
no fallback search directory can hold the model. Every stage's model is
looked up before any engine is created, so these runs never open an engine.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from common.multi import MultiModelRunner
from common.multi.pipeline import PipelineError

PIPELINE_DIR = Path(__file__).resolve().parents[3] / "src" / "python_example" / "multi_model"


def _copy_pipeline(tmp_path: Path, name: str) -> Path:
    work = tmp_path / "pipeline"
    work.mkdir()
    target = work / "pipeline.json"
    shutil.copyfile(PIPELINE_DIR / name / "pipeline.json", target)
    return target


def _run(pipeline: Path, models_dir: Path) -> tuple[str, MultiModelRunner]:
    runner = MultiModelRunner.from_json(pipeline, models_dir)
    with pytest.raises(PipelineError) as excinfo:
        runner.run_frame(np.zeros((64, 64, 3), dtype=np.uint8))
    return str(excinfo.value), runner


def test_missing_model_names_stage_variant_path_and_download(tmp_path):
    pipeline = _copy_pipeline(tmp_path, "hand_cascade")
    empty = tmp_path / "models"
    empty.mkdir()

    message, runner = _run(pipeline, empty)
    assert "stage 'palm'" in message, message
    assert "variant mediapipe-hand-detector_192x192" in message, message
    assert str(empty / "mediapipe-hand-detector_192x192.dxnn") in message, message
    assert "./setup.sh --models mediapipe-hand-detector_192x192" in message, message
    assert not runner._engines


def test_a_later_missing_model_fails_before_any_engine_is_created(tmp_path):
    """palm's file exists (not a real model), the landmark model does not."""
    pipeline = _copy_pipeline(tmp_path, "hand_cascade")
    models = tmp_path / "models"
    models.mkdir()
    (models / "mediapipe-hand-detector_192x192.dxnn").write_bytes(b"not a model")

    message, runner = _run(pipeline, models)
    assert "stage 'landmark'" in message, message
    assert "variant mediapipe-hands-lite_224x224" in message, message
    assert str(models / "mediapipe-hands-lite_224x224.dxnn") in message, message
    assert "./setup.sh --models mediapipe-hands-lite_224x224" in message, message
    assert not runner._engines


def test_a_custom_model_file_gets_no_model_zoo_download_line(tmp_path):
    """worker_safety's ppe stage names its own file, which ./setup.sh cannot fetch."""
    source = json.loads((PIPELINE_DIR / "worker_safety" / "pipeline.json")
                        .read_text(encoding="utf-8"))
    ppe = next(stage for stage in source["stages"] if stage["id"] == "ppe")
    work = tmp_path / "pipeline"
    work.mkdir()
    pipeline = work / "pipeline.json"
    pipeline.write_text(json.dumps({**source, "name": "ppe_only", "stages": [ppe]}),
                        encoding="utf-8")
    empty = tmp_path / "models"
    empty.mkdir()

    message, _ = _run(pipeline, empty)
    assert "stage 'ppe'" in message, message
    assert str(empty / ppe["model"]) in message, message
    assert "./setup.sh --models" not in message, message
    assert "--models-dir" in message, message


# The repository store: ./setup.sh --models downloads into <root>/assets/models,
# so without models_dir that is searched too (last); the root is patched to a
# temp dir, so the real store never answers.
def _patch_repository(monkeypatch, tmp_path: Path) -> Path:
    from common.multi import stage

    root = tmp_path / "repo"
    (root / "assets" / "models").mkdir(parents=True)
    monkeypatch.setattr(stage, "_PROJECT_ROOT", root, raising=False)
    return root / "assets" / "models"


def test_without_models_dir_the_repository_model_store_is_searched(tmp_path, monkeypatch):
    from common.multi.stage import resolve_model_file

    store = _patch_repository(monkeypatch, tmp_path)
    model = store / "mediapipe-hand-detector_192x192.dxnn"
    model.write_bytes(b"x")
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()

    assert resolve_model_file(model.name, pipeline_dir) == model.resolve()


def test_a_missing_model_without_models_dir_lists_the_repository_store(tmp_path, monkeypatch):
    store = _patch_repository(monkeypatch, tmp_path)
    pipeline = _copy_pipeline(tmp_path, "hand_cascade")

    message, runner = _run(pipeline, None)
    assert str(store / "mediapipe-hand-detector_192x192.dxnn") in message, message
    assert "./setup.sh --models mediapipe-hand-detector_192x192" in message, message
    assert not runner._engines


def test_an_explicit_models_dir_stands_in_for_the_repository_store(tmp_path, monkeypatch):
    from common.multi.stage import resolve_model_file

    store = _patch_repository(monkeypatch, tmp_path)
    (store / "mediapipe-hand-detector_192x192.dxnn").write_bytes(b"x")
    empty = tmp_path / "models"
    empty.mkdir()

    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_model_file("mediapipe-hand-detector_192x192.dxnn", tmp_path, empty)
    assert str(store) not in str(excinfo.value), str(excinfo.value)
