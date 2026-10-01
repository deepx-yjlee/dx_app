"""multi_model_run: a missing model names its stage, file and download command.

The pipeline is copied into tmp_path and --models-dir is an empty temp dir,
so no fallback search directory (the pipeline's own dir, any
workspace/res/models above it) can hold the model. Every stage's model is
looked up before any engine is created, so these runs never touch the NPU.
"""
import json
import shutil
import subprocess

import pytest

from conftest import PROJECT_ROOT, resolve_bin_dir

PIPELINE_DIR = PROJECT_ROOT / "src" / "cpp_example" / "multi_model"
HAND_IMAGE = PROJECT_ROOT / "sample" / "img" / "sample_hand.jpg"


def _binary():
    path = resolve_bin_dir() / "multi_model_run"
    if not path.exists():
        pytest.skip("multi_model_run not built")
    return path


def _copy_pipeline(tmp_path, name):
    work = tmp_path / "pipeline"
    work.mkdir()
    target = work / "pipeline.json"
    shutil.copyfile(str(PIPELINE_DIR / name / "pipeline.json"), str(target))
    return target


def _run(pipeline, models_dir):
    return subprocess.run(
        [str(_binary()), "--pipeline", str(pipeline), "--image", str(HAND_IMAGE),
         "--models-dir", str(models_dir)],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=60)


def test_missing_model_names_stage_variant_path_and_download(tmp_path):
    pipeline = _copy_pipeline(tmp_path, "hand_cascade")
    empty = tmp_path / "models"
    empty.mkdir()

    result = _run(pipeline, empty)
    assert result.returncode != 0, result.stdout + result.stderr
    message = result.stderr
    assert "stage 'palm'" in message, message
    assert "variant mediapipe-hand-detector_192x192" in message, message
    assert str(empty / "mediapipe-hand-detector_192x192.dxnn") in message, message
    assert "./setup.sh --models mediapipe-hand-detector_192x192" in message, message
    assert "stage ready" not in result.stdout, result.stdout


def test_a_later_missing_model_fails_before_any_engine_is_created(tmp_path):
    """palm's file exists (not a real model: opening it would fail), the
    landmark model does not. The run names the landmark stage, so it stopped
    before it tried to open palm's engine."""
    pipeline = _copy_pipeline(tmp_path, "hand_cascade")
    models = tmp_path / "models"
    models.mkdir()
    (models / "mediapipe-hand-detector_192x192.dxnn").write_bytes(b"not a model")

    result = _run(pipeline, models)
    assert result.returncode != 0, result.stdout + result.stderr
    message = result.stderr
    assert "stage 'landmark'" in message, message
    assert "variant mediapipe-hands-lite_224x224" in message, message
    assert str(models / "mediapipe-hands-lite_224x224.dxnn") in message, message
    assert "./setup.sh --models mediapipe-hands-lite_224x224" in message, message
    assert "stage ready" not in result.stdout, result.stdout


def test_a_custom_model_file_gets_no_model_zoo_download_line(tmp_path):
    """worker_safety's ppe stage names its own file (ppe_yolo26n.dxnn), which
    is not a model-zoo file: ./setup.sh cannot fetch it."""
    source = json.loads((PIPELINE_DIR / "worker_safety" / "pipeline.json")
                        .read_text(encoding="utf-8"))
    ppe = next(stage for stage in source["stages"] if stage["id"] == "ppe")
    work = tmp_path / "pipeline"
    work.mkdir()
    pipeline = work / "pipeline.json"
    pipeline.write_text(json.dumps({"name": "ppe_only", "fuse": source["fuse"],
                                    "stages": [ppe]}), encoding="utf-8")
    empty = tmp_path / "models"
    empty.mkdir()

    result = _run(pipeline, empty)
    assert result.returncode != 0, result.stdout + result.stderr
    message = result.stderr
    assert "stage 'ppe'" in message, message
    assert str(empty / "ppe_yolo26n.dxnn") in message, message
    assert "./setup.sh --models" not in message, message
    assert "--models-dir" in message, message
