"""Python multi_model runtime: a missing model names its stage, file and download command.

The Python counterpart of tests/cpp_example/test_multi_model_run.py. The
pipeline is copied into tmp_path and ``models_dir`` is an empty temp dir, so
no fallback search directory can hold the model. Every stage's model is
looked up before any engine is created, so these runs never open an engine.
"""
from __future__ import annotations

import json
import shutil
import subprocess
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
    """A stage whose file is not <variant>.dxnn cannot be fetched by ./setup.sh."""
    work = tmp_path / "pipeline"
    work.mkdir()
    pipeline = work / "pipeline.json"
    model = "not_in_zoo.dxnn"
    pipeline.write_text(json.dumps({
        "name": "custom_file",
        "fuse": "hand_cascade",
        "stages": [{
            "id": "custom",
            "task": "object_detection",
            "family": "yolo26",
            "variant": "yolo26-n_640x640",
            "model": model,
        }],
    }), encoding="utf-8")
    empty = tmp_path / "models"
    empty.mkdir()

    message, _ = _run(pipeline, empty)
    assert "stage 'custom'" in message, message
    assert str(empty / model) in message, message
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


def test_the_search_stops_at_the_repository_root(tmp_path, monkeypatch):
    """A pipeline inside the repository never takes a model from a store above
    it (a suite checkout's workspace/res/models), so one run cannot mix that
    store with <repository>/assets/models. The pipeline directory is absolute,
    as the C++ multi_model_run makes it."""
    from common.multi import stage

    suite = tmp_path / "dx-all-suite"
    above = suite / "workspace" / "res" / "models"
    above.mkdir(parents=True)
    root = suite / "dx-runtime" / "dx_app"
    store = root / "assets" / "models"
    store.mkdir(parents=True)
    pipeline_dir = root / "src" / "python_example" / "multi_model" / "dms_clip"
    pipeline_dir.mkdir(parents=True)
    name = "scrfd-500m_640x640.dxnn"
    (above / name).write_bytes(b"above")
    (store / name).write_bytes(b"repository")
    monkeypatch.setattr(stage, "_PROJECT_ROOT", root, raising=False)

    assert stage.resolve_model_file(name, pipeline_dir) == (store / name).resolve()
    with pytest.raises(FileNotFoundError) as excinfo:
        stage.resolve_model_file("absent.dxnn", pipeline_dir)
    searched = [line.strip() for line in str(excinfo.value).splitlines()[1:]]
    assert searched[-1] == str(store / "absent.dxnn"), searched
    assert all(path.startswith(str(root) + "/") for path in searched), searched


def test_run_pipeline_accepts_video_and_keeps_image():
    from test_helpers.proc import example_python, run_bounded

    script = PIPELINE_DIR / "run_pipeline.py"
    help_text = run_bounded(
        [example_python(), str(script), "--help"],
        cwd=str(PIPELINE_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=60)
    assert help_text.returncode == 0, help_text.stderr
    assert "--video" in help_text.stdout
    assert "--image" in help_text.stdout
    assert "--frames" in help_text.stdout

    both = run_bounded(
        [example_python(), str(script), "--pipeline", "unused.json",
         "--image", "a.jpg", "--video", "a.mp4"],
        cwd=str(PIPELINE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, timeout=60)
    assert both.returncode != 0
    assert "not allowed with argument" in both.stdout

    frames = run_bounded(
        [example_python(), str(script), "--pipeline", "unused.json",
         "--image", "a.jpg", "--frames", "2"],
        cwd=str(PIPELINE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, timeout=60)
    assert frames.returncode != 0
    assert "--frames applies to --video" in frames.stdout
