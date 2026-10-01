"""dms_clip head pose: multi_model_run and run_pipeline.py agree.

Both runtimes take the largest face of the face stage and solve its pose from
the face's 5 landmarks (face_solvepnp). The pipeline here is dms_clip's face
and headpose stages only, so it runs with the face model alone. Both runs get
the same --models-dir, image and pipeline file.
"""
import ast
import json
import re
import subprocess

import pytest

from conftest import PROJECT_ROOT, resolve_bin_dir

# conftest.py puts tests/ on sys.path.
from test_helpers.proc import example_python, run_bounded  # noqa: E402

MODEL_DIR = PROJECT_ROOT / "assets" / "models"
CPP_PIPELINE = PROJECT_ROOT / "src" / "cpp_example" / "multi_model" / "dms_clip" / "pipeline.json"
PY_EXAMPLE = PROJECT_ROOT / "src" / "python_example"
IMAGE = PROJECT_ROOT / "sample" / "img" / "sample_people.jpg"
# multi_model_run prints 6 significant digits.
ANGLE_TOLERANCE_DEG = 1e-3


def _face_headpose_pipeline(tmp_path):
    source = json.loads(CPP_PIPELINE.read_text(encoding="utf-8"))
    stages = [stage for stage in source["stages"] if stage["id"] in ("face", "headpose")]
    face = next(stage for stage in stages if stage["id"] == "face")
    pipeline = tmp_path / "pipeline.json"
    pipeline.write_text(json.dumps({**source, "name": "face_headpose", "stages": stages}),
                        encoding="utf-8")
    return pipeline, face["variant"] + ".dxnn"


@pytest.mark.e2e
def test_dms_head_pose_matches_the_python_runtime(tmp_path):
    binary = resolve_bin_dir() / "multi_model_run"
    if not binary.exists():
        pytest.skip("multi_model_run not built")
    pipeline, model = _face_headpose_pipeline(tmp_path)
    if not (MODEL_DIR / model).is_file():
        pytest.skip("{} not downloaded".format(model))
    args = ["--pipeline", str(pipeline), "--image", str(IMAGE), "--models-dir", str(MODEL_DIR)]

    cpp = run_bounded([str(binary)] + args, cwd=str(PROJECT_ROOT), capture_output=True,
                      universal_newlines=True, timeout=120)
    assert cpp.returncode == 0, cpp.stdout + cpp.stderr
    found = re.search(r"faces=(\d+).*headpose=pitch=(\S+),yaw=(\S+),roll=(\S+)", cpp.stdout)
    assert found, cpp.stdout
    assert int(found.group(1)) > 0, cpp.stdout
    theirs = tuple(float(value) for value in found.groups()[1:])

    python = run_bounded(
        [example_python(), "multi_model/run_pipeline.py"] + args, cwd=str(PY_EXAMPLE),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=120)
    assert python.returncode == 0, python.stdout
    line = re.search(r"face_headpose (\{.*\})", python.stdout)
    assert line, python.stdout
    head = ast.literal_eval(line.group(1))["headpose"]
    ours = (head["pitch"], head["yaw"], head["roll"])

    assert ours == pytest.approx(theirs, abs=ANGLE_TOLERANCE_DEG), (ours, theirs)
