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
    """models_dir None runs without --models-dir."""
    args = [str(_binary()), "--pipeline", str(pipeline), "--image", str(HAND_IMAGE)]
    if models_dir is not None:
        args += ["--models-dir", str(models_dir)]
    return subprocess.run(
        args, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=60)


def test_help_accepts_a_video_or_an_image():
    result = subprocess.run(
        [str(_binary()), "--help"], cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "--video" in result.stdout
    assert "--frames" in result.stdout
    assert "--image" in result.stdout


def test_image_and_video_cannot_be_combined():
    result = subprocess.run(
        [str(_binary()), "--pipeline", "unused.json", "--image", "a.jpg", "--video", "a.mp4"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=30)
    assert result.returncode == 1, result.stdout
    assert "pass either --image or --video" in result.stderr


def test_frames_applies_only_to_video():
    result = subprocess.run(
        [str(_binary()), "--pipeline", "unused.json", "--image", "a.jpg", "--frames", "2"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=30)
    assert result.returncode == 1, result.stdout
    assert "--frames applies to --video" in result.stderr


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
    # An explicit --models-dir stands in for the repository's store.
    assert str(PROJECT_ROOT / "assets" / "models") not in message, message
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


def _custom_file_pipeline(tmp_path):
    """A registered variant whose model file is not the model-zoo name."""
    work = tmp_path / "pipeline"
    work.mkdir(parents=True)
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
    return pipeline, model


def test_a_custom_model_file_gets_no_model_zoo_download_line(tmp_path):
    """A stage whose file is not <variant>.dxnn cannot be fetched by ./setup.sh."""
    pipeline, model = _custom_file_pipeline(tmp_path)
    empty = tmp_path / "models"
    empty.mkdir()

    result = _run(pipeline, empty)
    assert result.returncode != 0, result.stdout + result.stderr
    message = result.stderr
    assert "stage 'custom'" in message, message
    assert str(empty / model) in message, message
    assert "./setup.sh --models" not in message, message
    assert "--models-dir" in message, message


def test_without_models_dir_the_repository_model_store_is_searched_last(tmp_path):
    """./setup.sh --models downloads into <repository>/assets/models, so a run
    without --models-dir looks there too. The custom file is in no store."""
    pipeline, model = _custom_file_pipeline(tmp_path)

    result = _run(pipeline, None)
    assert result.returncode != 0, result.stdout + result.stderr
    searched = [line.strip() for line in result.stderr.splitlines()
                if line.startswith("  ") and not line.strip().startswith("->")]
    assert searched, result.stderr
    assert searched[-1] == str(PROJECT_ROOT / "assets" / "models" / model), result.stderr


@pytest.mark.parametrize("with_models_dir", [False, True], ids=["no-models-dir", "models-dir"])
def test_the_search_stops_at_the_repository_root(tmp_path, with_models_dir):
    """A missing custom model lists every path tried. None is above the
    repository (a suite checkout's workspace/res/models), so one run cannot
    mix that store with <repository>/assets/models; --models-dir comes first,
    and without it the repository's store comes last. Same order as Python's
    resolve_model_file. The pipeline sits inside the repository so the walk
    stops at that root."""
    folder = PROJECT_ROOT / "tests" / "cpp_example" / (
        "_search_models" if with_models_dir else "_search_repo")
    pipeline, _model = _custom_file_pipeline(folder)
    models_dir = None
    if with_models_dir:
        models_dir = tmp_path / "models"
        models_dir.mkdir()

    try:
        result = _run(pipeline, models_dir)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    assert result.returncode != 0, result.stdout + result.stderr
    searched = [line.strip() for line in result.stderr.splitlines()
                if line.startswith("  ") and not line.strip().startswith("->")]
    assert searched, result.stderr
    model = searched[0].rsplit("/", 1)[-1]
    if with_models_dir:
        assert searched[0] == str(models_dir / model), result.stderr
        searched = searched[1:]
    else:
        assert searched[-1] == str(PROJECT_ROOT / "assets" / "models" / model), result.stderr
    above = [path for path in searched if not path.startswith(str(PROJECT_ROOT) + "/")]
    assert not above, result.stderr
