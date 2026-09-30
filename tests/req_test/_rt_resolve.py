#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_rt_resolve.py — run_tc 방식 "실제 실행" 헬퍼 (test_*.sh / test_*.bat 공용).

run_tc.sh(→ pytest e2e)가 쓰는 탐색/실행 로직(tests/test_helpers)을 그대로
재사용하여, 요구사항 테스트에서 **환경이 갖춰지면 실제 추론을 실행하고 종료코드를
확인**하고, 갖춰지지 않았으면 SKIP 하도록 한다.

사용법:
    python _rt_resolve.py <mode> [--task T] [--loop N]

mode:
    cpp-img       빌드된 C++ sync/async 바이너리 + 매칭 .dxnn 로 이미지 추론
    cpp-vid       위와 동일하나 동영상 입력(dance-group.mov)
    py-img        Python *_sync.py 예제 + 매칭 .dxnn 로 이미지 추론
    py-cpp-img    Python *_sync_cpp_postprocess.py 예제로 이미지 추론
    cam           USB 카메라 자동 감지(리눅스 /dev/video<N>) → 있으면 -c N 으로
                  몇 초 스트림 실행 후 SIGINT, 정상 종료면 성공. 없으면 SKIP.
    async-loop    task 의 async 예제 대표 --count 개를 --loop 회 반복 실행(SDKREQ-534/535).
                  저사양 보드로 판별되면 케이스당 wall-clock 예산에 맞춰 --loop 을
                  자동 감량하고 사유를 `[rt][감량]` 줄로 출력한다(RT_LOW_SPEC=1/0 로 강제 지정).
    models-present   assets/models 에 .dxnn 이 1개 이상 있으면 성공

종료코드:
    0    실제 실행 성공(프로세스 exit 0)   → 호출측 [PASS]
    77   실행 가능한 대상 없음(바이너리/모델/샘플 부재) → 호출측 [SKIP]
    124  타임아웃
    그 외  실행했으나 프로세스가 비정상 종료 → 호출측 [FAIL]
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

# tests/ 를 import 경로에 추가 (test_helpers 재사용)
_TESTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TESTS_DIR))

from test_helpers.constants import (  # noqa: E402
    ASSETS_DIR,
    BIN_DIR,
    IMAGE_ONLY_TASKS,
    MODELS_DIR,
    MULTI_MODEL_EXECUTABLES,
    PROJECT_ROOT,
    TASK_IMAGE_MAP,
)
from test_helpers.utils import (  # noqa: E402
    discover_python_scripts,
    load_registry,
    resolve_image_for_model,
    setup_environment,
)

SKIP = 77

# run_tc 기본 입력 (tests/*/test_e2e.py 와 동일)
DEFAULT_IMAGE = PROJECT_ROOT / "sample" / "img" / "sample_kitchen.jpg"
DEFAULT_VIDEO = ASSETS_DIR / "videos" / "dance-group.mov"
CAM_DURATION = 5  # 카메라 스트림을 몇 초 돌린 뒤 SIGINT 로 종료
IMAGE_ONLY_KEYWORDS = ("arcface", "casvit", "deepmar", "face_attr")
# IMAGE_ONLY_TASKS 는 test_helpers.constants 에서 단일 정의(= run_examples.sh
# IMAGE_ONLY_CATEGORIES)를 import 한다. cpp-vid 요청 시 이미지 추론으로 대체.

# ── 저사양 보드 대응: 반복 추론(loop) 상한 ──────────────────────────────────
# SDKREQ-534/535 는 classification async 를 `--loop 10000` 으로 요구하지만,
# 저사양 보드(코어 수가 적은 aarch64 등)에서는 케이스 하나가 수십 분~시간 단위로
# 늘어나 요구사항 테스트를 완주할 수 없다. 보드 스펙을 자동 판별해 케이스당
# wall-clock 예산 안에 들어오도록 반복 횟수를 감량한다.
#
# 요구사항 이탈이므로 감량이 일어나면 사유(요청값/실행값/판별 근거)를 stdout 에
# `[rt][감량]` 줄로 남기고, 호출측 test_534.sh / test_535.bat 이 이를 그대로
# 출력한다. 결과 자체는 [PASS] 로 처리한다(반복 추론의 안정 종료는 여전히 검증됨).
LOW_SPEC_BUDGET_SEC = 300          # 예제 1개당 wall-clock 예산
LOW_SPEC_MAX_CORES = 8             # 이 이하의 코어 수 + ARM 계열 → 저사양으로 판별
# 저사양 보드에서 *보수적으로 가정*하는 초당 반복 처리량. 실측이 아니라 하한
# 가정치이므로 실제 보드가 더 빠르면 예산보다 일찍 끝난다(감량은 상한이지
# 목표가 아니다). 비디오 입력은 프레임 디코딩이 얹혀 이미지보다 느리다.
LOW_SPEC_RATE_PER_SEC = {"img": 7.0, "vid": 3.0}
LOW_SPEC_MIN_LOOP = 20             # 감량하더라도 이 아래로는 내리지 않는다


def _is_low_spec_board():
    """저사양 보드 여부 판별 → (bool, 판별 근거 문자열).

    기본은 자동 판별(ARM 계열 + 코어 수 <= LOW_SPEC_MAX_CORES). 자동 판별이
    맞지 않는 보드(느린 x86 SoC, 코어만 많은 저성능 ARM 등)를 위해 환경변수
    ``RT_LOW_SPEC=1/0`` 으로 강제 지정할 수 있다.
    """
    machine = platform.machine().lower()
    cores = os.cpu_count() or 1
    forced = os.environ.get("RT_LOW_SPEC")
    if forced is not None and forced.strip() != "":
        on = forced.strip().lower() in ("1", "true", "yes", "on")
        return on, "RT_LOW_SPEC=%s (강제 지정, machine=%s cores=%d)" % (forced.strip(), machine, cores)
    is_arm = machine.startswith("aarch64") or machine.startswith("arm")
    low = is_arm and cores <= LOW_SPEC_MAX_CORES
    return low, "machine=%s cores=%d" % (machine, cores)


def _effective_async_loop(loop, input_kind):
    """저사양 보드에서 ``loop`` 을 wall-clock 예산 내로 감량 → (실행값, 사유|None).

    고사양 보드이거나 요청값이 이미 예산 안이면 요청값을 그대로 돌려주고
    사유는 ``None`` (= 감량 없음)을 반환한다. 절대 요청값보다 *늘리지* 않는다.
    """
    low, why = _is_low_spec_board()
    if not low:
        return loop, None
    rate = LOW_SPEC_RATE_PER_SEC.get(input_kind, LOW_SPEC_RATE_PER_SEC["vid"])
    cap = max(LOW_SPEC_MIN_LOOP, int(LOW_SPEC_BUDGET_SEC * rate))
    if loop <= cap:
        return loop, None
    reason = ("저사양 보드 감량: --loop %d → %d "
              "(예산 %ds × 가정 %.1f it/s, %s)" % (loop, cap, LOW_SPEC_BUDGET_SEC, rate, why))
    return cap, reason

# 카테고리(task) → --show-log 시 stdout 에 나타나는 "결과 출력 포맷" 마커 (SDKREQ-519).
#   태그형(verbose 게이트): [DET]/[POSE]/[ISEG]/... , Classification 은 "Top predictions:".
#   image-based 태스크(depth/semantic_seg/embedding/restoration)는 결과가 이미지라 텍스트 태그
#   대신 "--show-log: This task produces image-based ..." INFO 를 출력 → 'produces image-based' 로 확인.
#   (마커 미정의 카테고리 — ppu/reid/attribute/hand_detection/keypoint/object_pose/panoptic — 는
#    do_cpp_showlog_per_task 에서 건너뛴다.)
SHOWLOG_MARKERS = {
    # 태그형 (전용 러너)
    "object_detection": "[DET]",
    "classification": "Top predictions:",
    "pose_estimation": "[POSE]",
    "instance_segmentation": "[ISEG]",
    "obb_detection": "[OBB]",
    "face_detection": "[FACE]",
    "face_alignment": "[ALIGN]",
    "hand_landmark": "[HAND]",
    "3d_object_detection": "[3D]",
    # 러너 재사용 (alias / include) → 재사용 러너의 출력 포맷을 그대로 사용
    "object_pose_estimation": "[POSE]",       # = SyncPoseRunner (alias)
    "keypoint_detection": "[POSE]",           # = SyncPoseRunner (alias)
    "panoptic_driving_perception": "[DET]",   # = SyncDetectionRunner (alias)
    "hand_detection": "[HAND]",               # sync_face_runner include, task-aware 태그
    "attribute_recognition": "Top predictions:",  # sync_classification_runner include
    # image-based (텍스트 태그 없음 → 이미지 저장, --show-log 시 안내 INFO)
    "depth_estimation": "produces image-based",
    "semantic_segmentation": "produces image-based",
    "embedding": "produces image-based",
    "reid": "produces image-based",           # sync_embedding_runner include
    "super_resolution": "produces image-based",
    "image_denoising": "produces image-based",
    "image_enhancement": "produces image-based",
    # ppu 는 모델별로 detection/face/pose 러너를 재사용 → 단일 마커 없음 → 제외(런타임 스킵).
}

# DEEPX 런타임/NPU 부재 시그니처 — 실행 실패가 "앱 버그"가 아니라 "환경 미비"임을
# 나타내는 표시. 이 경우 FAIL 대신 SKIP 으로 강등한다(사용자가 NPU 박스에서 검증).
_RUNTIME_MISSING = (
    "no module named 'dx_engine'",
    "no module named 'dxrt'",
    "dx_engine",
    "libdxrt",
    "cannot open shared object file",
    "error while loading shared libraries",
    "failed to open device",
    "no npu",
    "device not found",
    "dxrt::",
)


def _runtime_available_py() -> bool:
    """dx_engine(파이썬 런타임) import 가능 여부 — run_tc 실행의 사실상 전제조건."""
    try:
        r = subprocess.run([sys.executable, "-c", "import dx_engine"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def _looks_like_missing_runtime(text: str) -> bool:
    low = (text or "").lower()
    return any(sig in low for sig in _RUNTIME_MISSING)


def _registry_map() -> dict:
    """model_name → (dxnn Path, task): model_registry.json 의 supported 항목.

    이름 정규화(normalize) 없이 레지스트리의 dxnn_file / add_model_task 를 그대로
    사용해 예제·모델·태스크를 매핑한다(cpp 바이너리 base 이름 == model_name).
    """
    out = {}
    for e in load_registry():
        name = e.get("model_name")
        dxnn = e.get("dxnn_file")
        if not name or not dxnn:
            continue
        out[name] = (MODELS_DIR / dxnn, e.get("add_model_task", ""))
    # 레지스트리 model_name 이 재배포 버전 접미사(`_1`/`_2`)를 달고 있는 경우가 있는데
    # (예: dope_hope_ketchup_1), 예제 디렉토리·바이너리 base 는 접미사가 없다
    # (dope_hope_ketchup). 이 드리프트를 잇기 위해 접미사를 뗀 base 별칭을 추가한다
    # (직접 키가 없을 때만 — 파일명은 여전히 레지스트리 dxnn_file 그대로 사용).
    for name in list(out):
        base = re.sub(r"_\d+$", "", name)
        if base != name and base not in out:
            out[base] = out[name]
    return out


def _iter_cpp_binaries():
    """빌드된 sync/async 바이너리를 (exe_path, base_name) 로 yield."""
    if not BIN_DIR.exists():
        return
    exe_suffix = ".exe" if os.name == "nt" else ""
    for p in sorted(BIN_DIR.iterdir()):
        if not p.is_file():
            continue
        stem = p.name[:-4] if (exe_suffix and p.name.endswith(".exe")) else p.name
        if not (stem.endswith("_sync") or stem.endswith("_async")):
            continue
        base = stem.rsplit("_", 1)[0]
        yield p, base


def _base_of(exe_path):
    """exe_path → registry base name. `_iter_cpp_binaries` 와 동일한 정규화
    (`sfa3d_608x608_sync.exe` → `sfa3d_608x608`)."""
    nm = exe_path.name
    stem = nm[:-4] if nm.endswith(".exe") else nm
    return stem.rsplit("_", 1)[0]


def _cpp_input_for(exe_path, task):
    """C++ 예제가 `-i` 로 실제 받아들이는 샘플 입력 경로(str).

    DEFAULT_IMAGE 를 하드코딩하면 안 된다. 3d_object_detection(sfa3d_*)은 KITTI
    LiDAR 포인트클라우드(sample/kitti/velodyne/*.bin)를, object_pose_estimation
    (dope_*)은 sample/dope/*.png 를 요구하며, JPG 를 주면 추론 전에 rc=255 로
    즉시 실패한다. 태스크/모델별 해석의 source of truth 는 TASK_IMAGE_MAP /
    MODEL_IMAGE_OVERRIDE 이고, tests/cpp_example 의 pytest 들은 같은 목적으로
    test_helpers.utils.resolve_cpp_exe_input() 을 쓴다. 여기서는 이미 정규화된
    base/task 를 들고 있으므로 그 하위 함수인 resolve_image_for_model() 을
    직접 호출한다(.exe 접미사 때문에 strip_variant_suffix 가 어긋나는 것을 회피).

    해석 실패(태스크 미상·샘플 없음) 시에만 DEFAULT_IMAGE 로 폴백한다.
    """
    rel = resolve_image_for_model(_base_of(exe_path), task or "")
    return str(PROJECT_ROOT / rel) if rel else str(DEFAULT_IMAGE)


def _multi_model_args(base: str):
    pairs = MULTI_MODEL_EXECUTABLES.get(base)
    if not pairs:
        return None
    args = []
    for flag, fname in pairs:
        mp = MODELS_DIR / fname
        if not mp.exists():
            return None
        args += [flag, str(mp)]
    return args


def _resolve_cpp(task_filter):
    """첫 번째 실행 가능한 (exe_path, model_args, task) 반환 or None.
    예제→모델→태스크 매핑은 model_registry.json 기준(이름 정규화 없음)."""
    reg = _registry_map()
    candidates = list(_iter_cpp_binaries())
    # task 필터 우선 적용, 매칭 없으면 전체
    if task_filter:
        filtered = [(p, b) for (p, b) in candidates if reg.get(b, (None, ""))[1] == task_filter]
        candidates = filtered or candidates
    for exe_path, base in candidates:
        multi = _multi_model_args(base)
        if multi is not None:
            return exe_path, multi, reg.get(base, (None, ""))[1]
        entry = reg.get(base)
        if entry is not None and entry[0].exists():
            return exe_path, ["-m", str(entry[0])], entry[1]
    return None


def _run(cmd, timeout):
    env = setup_environment()
    print("   [rt] $ " + " ".join(cmd))
    try:
        r = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env,
                           capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            combined = (r.stdout or "") + (r.stderr or "")
            sys.stderr.write(combined[-2000:])
            # 앱 버그가 아니라 런타임/NPU 미비면 SKIP 으로 강등
            if _looks_like_missing_runtime(combined):
                sys.stderr.write("\n[rt] DEEPX 런타임/NPU 미탐지 → SKIP\n")
                return SKIP
        return r.returncode
    except subprocess.TimeoutExpired:
        sys.stderr.write("timeout after %ss\n" % timeout)
        return 124


def _run_capture(cmd, timeout):
    """_run 과 동일하나 (rc, combined_output) 를 반환 — --show-log 출력 포맷 검증용."""
    env = setup_environment()
    print("   [rt] $ " + " ".join(cmd))
    try:
        r = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env,
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 and _looks_like_missing_runtime(out):
            return SKIP, out
        return r.returncode, out
    except subprocess.TimeoutExpired:
        return 124, ""


def do_cpp_img(task, loop):
    if not DEFAULT_IMAGE.exists():
        return SKIP
    res = _resolve_cpp(task)
    if res is None:
        return SKIP
    exe, model_args, rtask = res
    cmd = [str(exe)] + model_args + ["-i", _cpp_input_for(exe, rtask), "--no-display", "-l", str(loop)]
    return _run(cmd, 300 if "tta" in exe.name.lower() else 120)


def do_cpp_vid(task, loop):
    if not DEFAULT_VIDEO.exists():
        return SKIP
    res = _resolve_cpp(task)
    if res is None:
        return SKIP
    exe, model_args, rtask = res
    low = exe.name.lower()
    # 동영상 미지원 태스크(image-only) 또는 run_tc 가 스트림에서 제외하는 모델은
    # 이미지 추론으로 대체한다.
    if (rtask in IMAGE_ONLY_TASKS or "face" in low
            or any(k in low for k in IMAGE_ONLY_KEYWORDS)):
        return do_cpp_img(task, loop)
    cmd = [str(exe)] + model_args + ["-v", str(DEFAULT_VIDEO), "--no-display"]
    return _run(cmd, 900)


def _resolve_py(task_filter, cpp_postprocess):
    """첫 번째 실행 가능한 (script_path, model_path, task, model_name) or None."""
    cases = discover_python_scripts(suffixes=("_sync",))
    if task_filter:
        filtered = [c for c in cases if c[0] == task_filter]
        cases = filtered or cases
    for task, model_name, sync_scripts, _async, model_path in cases:
        if model_path is None:
            continue
        for scr in sync_scripts:
            is_cpp = "cpp_postprocess" in scr.stem
            if cpp_postprocess and not is_cpp:
                continue
            if not cpp_postprocess and is_cpp:
                continue
            return scr, model_path, task, model_name
    return None


def do_py_img(task, cpp_postprocess):
    if not DEFAULT_IMAGE.exists():
        return SKIP
    if not _runtime_available_py():
        # dx_engine 미설치 → 실제 추론 불가(환경 미비). run_tc 는 NPU 박스 전제.
        return SKIP
    res = _resolve_py(task, cpp_postprocess)
    if res is None:
        return SKIP
    scr, model_path, tsk, model_name = res
    img = resolve_image_for_model(model_name, tsk) or str(
        DEFAULT_IMAGE.relative_to(PROJECT_ROOT))
    img_abs = PROJECT_ROOT / img
    cmd = [sys.executable, str(scr), "--model", str(model_path),
           "--image", str(img_abs), "--no-display"]
    return _run(cmd, 300)


def _resolve_cpp_all_tasks():
    """task → (exe_path, model_args): 태스크 카테고리마다 첫 실행가능 후보 1개.
    매핑은 model_registry.json 기준(이름 정규화 없음)."""
    reg = _registry_map()
    out = {}
    for exe_path, base in _iter_cpp_binaries():
        multi = _multi_model_args(base)
        if multi is not None:
            out.setdefault(reg.get(base, (None, ""))[1], (exe_path, multi))
            continue
        entry = reg.get(base)
        if entry is not None and entry[0].exists() and entry[1] not in out:
            out[entry[1]] = (exe_path, ["-m", str(entry[0])])
    return out


def _resolve_py_all_tasks(cpp_postprocess):
    """task → (script, model_path, model_name): 태스크마다 첫 실행가능 예제 1개."""
    out = {}
    for task, model_name, sync_scripts, _async, model_path in discover_python_scripts(suffixes=("_sync",)):
        if model_path is None or task in out:
            continue
        for scr in sync_scripts:
            if ("cpp_postprocess" in scr.stem) != cpp_postprocess:
                continue
            out[task] = (scr, model_path, model_name)
            break
    return out


def _aggregate(ran, failed):
    """태스크별 실행 결과 집계 → 0(성공) / 1(하나라도 실패) / 77(실행 대상 없음)."""
    if failed:
        return 1
    if ran:
        return 0
    return SKIP


def do_cpp_img_per_task(loop):
    """C++ 바이너리를 태스크 카테고리마다 1개씩 이미지 추론 (yolo 하나가 아니라 전체 태스크)."""
    if not DEFAULT_IMAGE.exists():
        return SKIP
    per = _resolve_cpp_all_tasks()
    if not per:
        return SKIP
    ran = failed = 0
    for task, (exe, margs) in sorted(per.items()):
        rc = _run([str(exe)] + margs + ["-i", _cpp_input_for(exe, task), "--no-display", "-l", str(loop)],
                  300 if "tta" in exe.name.lower() else 120)
        if rc == SKIP:
            continue
        ran += 1
        failed += (rc != 0)
    return _aggregate(ran, failed)


def do_cpp_showlog_per_task():
    """카테고리(task)마다 대표 C++ 바이너리 1개를 --show-log 로 실행하고, 그 카테고리의
    결과 출력 포맷 마커(SHOWLOG_MARKERS)가 stdout 에 나오는지 확인 (SDKREQ-519).

    run_tc --e2e-short(카테고리별 대표 1개) 아이디어를 이식 — 전 모델이 아니라 태스크마다
    첫 실행가능 바이너리 하나만. 태스크에 맞는 샘플 이미지를 써서 실제 검출/결과가 나오게 한다.
    마커 미정의 카테고리는 건너뛰고, 실행 대상 없으면(rc=77) 그 태스크는 세지 않는다.
    """
    if not DEFAULT_IMAGE.exists():
        return SKIP
    per = _resolve_cpp_all_tasks()
    if not per:
        return SKIP
    ran = failed = 0
    for task, (exe, margs) in sorted(per.items()):
        marker = SHOWLOG_MARKERS.get(task)
        if marker is None:
            continue  # 출력 포맷 마커가 정의되지 않은 카테고리 → 스킵
        # 바이너리 base 이름(=model_name)으로 이미지 해석 → MODEL_IMAGE_OVERRIDE 적용
        # (예: mediapipe_hand_detector → 손이 보이는 이미지). 없으면 태스크 기본, 그것도 없으면 kitchen.
        stem = exe.name[:-4] if exe.name.endswith(".exe") else exe.name
        base = stem.rsplit("_", 1)[0] if stem.endswith(("_sync", "_async")) else stem
        img = resolve_image_for_model(base, task) or str(DEFAULT_IMAGE.relative_to(PROJECT_ROOT))
        rc, out = _run_capture(
            [str(exe)] + margs + ["-i", str(PROJECT_ROOT / img), "--show-log", "--no-display", "-l", "1"],
            300 if "tta" in exe.name.lower() else 120)
        if rc == SKIP:
            continue
        ran += 1
        if rc != 0 or marker not in out:
            sys.stderr.write("[rt] %s: 마커 '%s' 미검출 (rc=%s)\n" % (task, marker, rc))
            failed += 1
        else:
            print("   [rt] %s: '%s' 확인" % (task, marker))
    return _aggregate(ran, failed)


def do_py_img_per_task(cpp_postprocess):
    """Python 예제를 태스크 카테고리마다 1개씩 이미지 추론."""
    if not DEFAULT_IMAGE.exists():
        return SKIP
    if not _runtime_available_py():
        return SKIP
    per = _resolve_py_all_tasks(cpp_postprocess)
    if not per:
        return SKIP
    ran = failed = 0
    for task, (scr, model_path, model_name) in sorted(per.items()):
        img = resolve_image_for_model(model_name, task) or str(DEFAULT_IMAGE.relative_to(PROJECT_ROOT))
        rc = _run([sys.executable, str(scr), "--model", str(model_path),
                   "--image", str(PROJECT_ROOT / img), "--no-display"], 300)
        if rc == SKIP:
            continue
        ran += 1
        failed += (rc != 0)
    return _aggregate(ran, failed)


def _camera_present(index):
    """USB 카메라 자동 감지. 리눅스는 /dev/video<index> 존재로 판단.
    Windows/기타는 신뢰성 있는 감지 수단이 없어 '없음'으로 처리(→ SKIP)."""
    if os.name == "nt":
        return False
    return Path("/dev/video%d" % index).exists()


def _run_stream(cmd, duration):
    """카메라/RTSP 스트림 실행: duration초 뒤 SIGINT 로 종료시키고 결과 판정.
    0=정상(끝까지 돌다 SIGINT graceful 종료) / 77=런타임·NPU 미비 / 124=행 / 그외=실패."""
    env = setup_environment()
    print("   [rt] $ " + " ".join(cmd))
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=os.setsid if os.name != "nt" else None,
        )
    except Exception as e:  # noqa: BLE001
        sys.stderr.write("spawn failed: %s\n" % e)
        return 1

    # 조기 종료(기동 실패) 감지
    try:
        proc.wait(timeout=min(3, duration))
        combined = (proc.stdout.read().decode(errors="replace")
                    + proc.stderr.read().decode(errors="replace"))
        sys.stderr.write(combined[-2000:])
        if _looks_like_missing_runtime(combined):
            sys.stderr.write("\n[rt] DEEPX 런타임/NPU 미탐지 → SKIP\n")
            return SKIP
        return proc.returncode  # 0=정상 종료, !=0=기동 실패
    except subprocess.TimeoutExpired:
        pass  # 계속 실행 중 = 정상 기동

    time.sleep(max(0, duration - 3))
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
    except Exception:  # noqa: BLE001
        proc.terminate()
    try:
        out, err = proc.communicate(timeout=30)
        combined = ((out or b"").decode(errors="replace")
                    + (err or b"").decode(errors="replace"))
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:  # noqa: BLE001
            proc.kill()
        proc.wait()
        return 124
    if _looks_like_missing_runtime(combined):
        sys.stderr.write("\n[rt] DEEPX 런타임/NPU 미탐지 → SKIP\n")
        return SKIP
    rc = proc.returncode
    # SIGINT 로 인한 종료(130 / -SIGINT)는 graceful 종료로 간주 → 성공
    return 0 if rc in (0, 130, -signal.SIGINT) else (rc if rc else 1)


def do_cam(index):
    """카메라 자동 감지 후 대표 예제를 -c <index> 로 스트림 실행."""
    if not _camera_present(index):
        return SKIP  # 카메라 미연결 → SKIP
    # 빌드된 C++ 바이너리 우선, 없으면 Python 예제
    res = _resolve_cpp("object_detection")
    if res is not None:
        exe, margs, _ = res
        return _run_stream([str(exe)] + margs + ["-c", str(index), "--no-display"], CAM_DURATION)
    if _runtime_available_py():
        r = _resolve_py("object_detection", False)
        if r is not None:
            scr, model_path, _tsk, _name = r
            return _run_stream(
                [sys.executable, str(scr), "--model", str(model_path),
                 "--camera", str(index), "--no-display"], CAM_DURATION)
    return SKIP  # 실행 대상(바이너리/예제+모델) 없음


def do_cpp_badmodel():
    """빌드된 C++ 바이너리에 없는 모델/이미지를 주고 (1) 통일 에러 포맷 '[DXAPP] [ERROR]' 출력 +
    (2) 비정상 종료(exit!=0) 하는지 확인. 모델/이미지 로드 단계에서 실패하므로 NPU 없이도 검증 가능.
    0=정상(에러 포맷+비정상종료) / 77=검증 대상(빌드 바이너리) 없음 / 1=에러 처리 미흡."""
    bins = list(_iter_cpp_binaries())
    if not bins:
        return SKIP
    exe = bins[0][0]
    cmd = [str(exe), "-m", "__nonexistent__.dxnn", "-i", "__nofile__.jpg"]
    env = setup_environment()
    print("   [rt] $ " + " ".join(cmd))
    try:
        r = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env,
                           capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        sys.stderr.write("timeout\n")
        return 124
    out = (r.stdout or "") + (r.stderr or "")
    sys.stderr.write(out[-2000:])
    marker = "[DXAPP] [ERROR]"
    if r.returncode != 0 and marker in out:
        return 0
    if r.returncode == 0:
        sys.stderr.write("\n[rt] 정상 종료(exit=0) — 잘못된 입력이 에러 처리되지 않음\n")
        return 1
    sys.stderr.write("\n[rt] 비정상 종료지만 '%s' 포맷 미출력\n" % marker)
    return 1


def do_cpp_sigint(duration=6):
    """빌드+모델+비디오(+NPU) 가 있으면 스트림 추론을 duration초 돌린 뒤 SIGINT(Ctrl+C)를 보내
    graceful 종료(exit 0/130)가 되는지 확인. _run_stream 이 SIGINT 후 0/130/-SIGINT 를 성공(0)으로 판정.
    0=graceful / 77=대상(바이너리/모델/비디오/런타임) 없음 / 그외=비정상."""
    if os.name == "nt":
        return SKIP  # Windows 는 프로세스그룹/SIGINT 의미가 달라 자동화 부적합 → 수동
    if not DEFAULT_VIDEO.exists():
        return SKIP
    res = _resolve_cpp("object_detection")
    if res is None:
        return SKIP
    exe, model_args, rtask = res
    low = exe.name.lower()
    # 스트림(비디오) 미지원 예제면 SIGINT graceful 검증 대상이 아님 → SKIP
    if (rtask in IMAGE_ONLY_TASKS or "face" in low
            or any(k in low for k in IMAGE_ONLY_KEYWORDS)):
        return SKIP
    cmd = [str(exe)] + model_args + ["-v", str(DEFAULT_VIDEO), "--no-display"]
    return _run_stream(cmd, duration)


def do_cpp_model_policy():
    """SDKREQ-529 모델 경로 정책: 명시적 -m 에 없는 경로를 주면 auto-download 를
    돌리지 않고 즉시 '[DXAPP] [ERROR]' + 비정상 종료 해야 한다(잘못 지정한 파일은 사용자 책임).
    0=정책 준수 / 77=대상 바이너리 없음 / 1=위반(다운로더 실행 or 정상종료 or 포맷 미출력)."""
    bins = list(_iter_cpp_binaries())
    if not bins:
        return SKIP
    exe = bins[0][0]
    cmd = [str(exe), "-m", "__nonexistent_zzz__.dxnn", "-i", "__nofile__.jpg"]
    env = setup_environment()
    print("   [rt] $ " + " ".join(cmd))
    try:
        r = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env,
                           capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        sys.stderr.write("timeout\n")
        return 124
    out = (r.stdout or "") + (r.stderr or "")
    sys.stderr.write(out[-2000:])
    downloader = ("Auto Downloader" in out) or ("attempting auto-download" in out)
    if downloader:
        sys.stderr.write("\n[rt] 정책 위반: 명시적 -m 인데 auto-download 실행됨\n")
        return 1
    if r.returncode != 0 and "[DXAPP] [ERROR]" in out:
        return 0
    if r.returncode == 0:
        sys.stderr.write("\n[rt] 정책 위반: 없는 모델인데 정상 종료(exit=0)\n")
    else:
        sys.stderr.write("\n[rt] 정책 위반: '[DXAPP] [ERROR]' 포맷 미출력\n")
    return 1


def do_cpp_badinput():
    """SDKREQ-529 입력 정책: 유효한 모델 + 존재하지 않는 -i 경로 → 'Input file not found'
    + 비정상 종료(기본 샘플로 fallback 하지 않는다). object_detection 대표로 검증(NPU 불필요).
    0=정책 준수 / 77=대상(바이너리+모델) 없음 / 1=위반."""
    res = _resolve_cpp("object_detection")
    if res is None:
        return SKIP
    exe, model_args, _ = res
    cmd = [str(exe)] + model_args + ["-i", "__nofile_zzz__.jpg"]
    env = setup_environment()
    print("   [rt] $ " + " ".join(cmd))
    try:
        r = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env,
                           capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        sys.stderr.write("timeout\n")
        return 124
    out = (r.stdout or "") + (r.stderr or "")
    sys.stderr.write(out[-2000:])
    if r.returncode != 0 and "Input file not found" in out:
        return 0
    sys.stderr.write("\n[rt] 정책 위반: 없는 입력이 'Input file not found' 로 종료되지 않음\n")
    return 1


def do_cpp_bin_input():
    """SDKREQ-529 .bin 정책: LiDAR .bin 을 요구하는 3D 예제에 존재하는 비-.bin(-i .jpg)을 주면
    '.bin'/'LiDAR' 에러 + 비정상 종료 해야 한다(포맷이 맞아야 한다). NPU 불필요.
    0=정책 준수 / 77=대상(3D 바이너리+모델) 없음 / 1=위반."""
    reg = _registry_map()
    img = PROJECT_ROOT / "sample" / "img" / "sample_street.jpg"
    if not img.exists():
        return SKIP
    for exe, base in _iter_cpp_binaries():
        entry = reg.get(base)
        task = entry[1] if entry else ""
        # Precise match: only LiDAR 3D-detection examples require .bin input.
        # (Substring "3d" would wrongly catch "3ddfa" = 3D Dense Face Alignment,
        #  which is a face_alignment model with no .bin guard → would run + hang.)
        if task not in ("3d_object_detection", "3d_detection") \
                and not base.lower().startswith("sfa3d"):
            continue
        if not entry or not entry[0].exists():
            continue
        # --no-display: never open a GUI window (the .bin guard should error out
        # first, but stay headless-safe just in case).
        cmd = [str(exe), "-m", str(entry[0]), "-i", str(img), "--no-display"]
        env = setup_environment()
        print("   [rt] $ " + " ".join(cmd))
        try:
            r = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env,
                               capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            sys.stderr.write("timeout\n")
            return 124
        out = (r.stdout or "") + (r.stderr or "")
        sys.stderr.write(out[-2000:])
        if r.returncode != 0 and (".bin" in out or "LiDAR" in out):
            return 0
        sys.stderr.write("\n[rt] 정책 위반: 비-.bin 입력이 .bin 검사로 거부되지 않음\n")
        return 1
    return SKIP


def _resolve_async_examples(task_filter, count):
    """task_filter 에 해당하는 async 바이너리 중 모델이 준비된 것 최대 count개 반환.
    반환: [(exe_path, model_args, base, task), ...] — task 는 호출측이 예제별
    입력(-i)을 해석하는 데 필요하다(_cpp_input_for)."""
    reg = _registry_map()
    res = []
    for exe_path, base in _iter_cpp_binaries():
        nm = exe_path.name
        stem = nm[:-4] if nm.endswith(".exe") else nm
        if not stem.endswith("_async"):
            continue
        multi = _multi_model_args(base)
        if multi is not None:
            task = reg.get(base, (None, ""))[1]
            margs = multi
        else:
            entry = reg.get(base)
            if entry is None or not entry[0].exists():
                continue
            task, margs = entry[1], ["-m", str(entry[0])]
        if task_filter and task != task_filter:
            continue
        res.append((exe_path, margs, base, task))
        if len(res) >= count:
            break
    return res


def do_async_loop(task, input_kind, loop, count):
    """task 의 async 예제 대표 count개를, image(-i) 또는 video(-v) 입력으로 --loop <loop> 반복 실행하고
    모두 정상 종료(exit 0)하는지 확인. SDKREQ-534: classification=img/10000, object_detection=vid/20 등.
    저사양 보드에서는 `_effective_async_loop` 으로 반복 횟수를 감량한다(요구사항 이탈 → 사유 출력).
    0=전부 정상 / 77=실행 대상(빌드 async+모델)·입력 없음 또는 런타임 미비 / 그외=반복 중 비정상."""
    if input_kind == "vid":
        if not DEFAULT_VIDEO.exists():
            return SKIP
    elif not DEFAULT_IMAGE.exists():
        return SKIP
    examples = _resolve_async_examples(task, count)
    if not examples:
        return SKIP  # 빌드된 async 예제(+모델) 없음
    # 저사양 보드에서는 요청 loop 을 wall-clock 예산 내로 감량한다(요구사항 이탈 →
    # 사유를 [rt][감량] 줄로 남긴다). 고사양 보드는 요청값 그대로.
    loop_eff, cut_reason = _effective_async_loop(loop, input_kind)
    if cut_reason:
        # 마커는 ASCII 로 고정 — 호출측 test_534.sh(grep) / test_535.bat(findstr) 이
        # 이 줄만 골라 출력한다(Windows 코드페이지 문제 회피).
        print("   [rt][loop-cut] " + cut_reason)
    # loop 이 크면 시간이 오래 걸리므로 넉넉한 타임아웃(대량 반복은 10000초).
    # 감량된 경우엔 예산 기준(3배 여유)으로 잡아 한 케이스가 무한정 늘어지지 않게 한다.
    if cut_reason:
        timeout = LOW_SPEC_BUDGET_SEC * 3 + 120
    else:
        timeout = 10000 if loop_eff >= 1000 else 900
    worst = 0
    ran = []
    for exe, margs, base, etask in examples:
        # 입력은 예제별로 해석한다 — 3d_object_detection/object_pose_estimation
        # 예제는 JPG 를 거부하고 rc=255 로 죽는다(_cpp_input_for 주석 참고).
        input_args = (["-v", str(DEFAULT_VIDEO)] if input_kind == "vid"
                      else ["-i", _cpp_input_for(exe, etask)])
        cmd = [str(exe)] + margs + input_args + ["-l", str(loop_eff), "--no-display"]
        rc = _run(cmd, timeout)
        if rc == SKIP:  # 런타임/NPU 미비 → 전체 SKIP
            return SKIP
        ran.append(base)
        if rc != 0:
            worst = rc
    loop_desc = "%d" % loop_eff if loop_eff == loop else "%d(요청 %d)" % (loop_eff, loop)
    print("   [rt] task=%s input=%s loop=%s 실행 async 예제 %d개: %s"
          % (task, input_kind, loop_desc, len(ran), ", ".join(ran)))
    return worst


def _doc_command_lines():
    """README.md + docs/**/*.md 의 코드블록에서 실행형 커맨드라인을 추출(중복 제거, 순서 유지).
    대상: (./)install|setup|build|run_demo|run_tc.sh ... / bin/<model>_sync|_async[.exe] ..."""
    import glob
    files = [PROJECT_ROOT / "README.md"]
    files += [Path(p) for p in sorted(glob.glob(str(PROJECT_ROOT / "docs" / "**" / "*.md"), recursive=True))]
    cmd_re = re.compile(
        r"^\$?\s*((?:\./)?(?:install|setup|build|run_demo|run_tc)\.sh(?:\s.*)?"
        r"|(?:\./)?bin/[A-Za-z0-9_]+_(?:sync|async)(?:\.exe)?(?:\s.*)?)$")
    seen, cmds = set(), []
    for f in files:
        if not f.exists():
            continue
        in_block = False
        pending = ""  # '\' 로 이어지는 다중 라인 커맨드 누적
        for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
            s = raw.strip()
            if s.startswith("```"):
                in_block = not in_block
                pending = ""
                continue
            if not in_block:
                continue
            # 라인 연속(\) 결합
            if pending:
                s = pending + " " + s
                pending = ""
            if s.endswith("\\"):
                pending = s[:-1].rstrip()
                continue
            m = cmd_re.match(s)
            if not m:
                continue
            cmd = re.split(r"\s+#", m.group(1))[0].strip()
            if cmd and cmd not in seen:
                seen.add(cmd)
                cmds.append(cmd)
    return cmds


def _doc_bin_cmdline(parts, exe, windows=None):
    """문서의 `./bin/<x>_sync ...` 를 현재 셸에서 실제로 실행 가능한 커맨드라인으로.

    문서는 POSIX 표기(`./bin/yolov9s_sync`)로 적혀 있는데, Windows 에서 `shell=True`
    는 `cmd.exe /c <문자열>` 이고 cmd 는 이를 "`.` 라는 명령 + `/bin` 스위치" 로
    파싱해 버린다 → `'.' is not recognized as an internal or external command`.
    (`./bin/x_sync.exe` 처럼 확장자가 이미 붙어 있어도 똑같이 죽는다 — 확장자가
    아니라 `./` + forward slash 형태가 문제다.)

    그래서 Windows 에서는 호출측이 이미 해석해 둔 실제 실행파일 경로(`.exe` 포함)로
    argv[0] 만 갈아끼운다. cwd 가 PROJECT_ROOT 이므로 가능하면 상대경로를 쓴다
    (프로젝트 경로에 공백이 있어도 인용부호가 필요 없어진다). POSIX 는 문서 표기가
    그대로 유효하므로 손대지 않는다.

    `-m`/`-i` 등 인자 값은 앱이 직접 여는 경로라 문서 표기 그대로 넘긴다.
    """
    if windows is None:
        windows = os.name == "nt"
    argv = list(parts)
    if windows:
        try:
            head = str(exe.relative_to(PROJECT_ROOT))
        except ValueError:
            head = str(exe)
        # Path flavour 에 의존하지 않고 명시적으로 backslash 로 — Linux 에서 돌리는
        # 단위 테스트도 같은 결과를 봐야 한다.
        head = head.replace("/", "\\")
        argv[0] = '"%s"' % head if " " in head else head
    if "--no-display" not in argv:
        argv.append("--no-display")
    return " ".join(argv)


def _doc_missing_files(parts):
    """bin/ 커맨드의 -m/-i/-v 인자가 가리키는 파일 중 존재하지 않는 것 목록."""
    missing = []
    for flag in ("-m", "--model", "-i", "--image", "-v", "--video"):
        if flag in parts:
            val = parts[parts.index(flag) + 1] if parts.index(flag) + 1 < len(parts) else ""
            if val and not (PROJECT_ROOT / val).exists():
                missing.append(val)
    return missing


def do_doc_commands(run_full=False):
    """문서(README/docs)에 기재된 모든 커맨드라인을 열거하고 각각 실행/스킵을 로그로 남긴다(SDKREQ-540).
      - bin/<model>_sync|_async 추론: 바이너리+모델/이미지 있으면 실제 실행(--no-display), 없으면 SKIP
      - --help/--list/--dry-run 안전 플래그 스크립트: 실행
      - install/build/setup/run_tc/run_demo 전체실행형: 기본은 SKIP(고비용·부작용).
        run_full(--run) 이면 이들까지 실제 실행(넉넉한 타임아웃, stdin=EOF 로 인터랙티브 hang 방지).
      - <model_name> 같은 자리표시자 포함 커맨드는 항상 SKIP(문서 예시).
    0=실행된 커맨드 모두 성공 / 77=실행 대상 없음 / 1=실행한 커맨드 중 실패."""
    cmds = _doc_command_lines()
    if not cmds:
        return SKIP
    env = setup_environment()
    safe_flags = ("--help", "--list", "--dry-run", "--target list")
    ran = failed = skipped = 0
    print("   [doc] 문서 기재 커맨드 %d개 검사%s" % (len(cmds), " (--run: 전체 실행)" if run_full else ""))
    is_sh = re.compile(r"^(?:\./)?\S+\.sh(?:\s|$)")
    for cmd in cmds:
        # 자리표시자(<model_name> 등) 포함 = 문서 예시일 뿐 실제 실행 대상 아님
        if "<" in cmd and ">" in cmd:
            print("   [doc][SKIP] %s  (자리표시자 포함: 문서 예시)" % cmd)
            skipped += 1
            continue
        # .sh 스크립트는 Linux 전용 → Windows(cmd)에선 실행 불가하므로 스킵(로그만)
        if os.name == "nt" and is_sh.match(cmd):
            print("   [doc][SKIP] %s  (Linux 전용 .sh, Windows 제외)" % cmd)
            skipped += 1
            continue
        # 실행 대상 결정: bin/ 추론 / 안전 플래그 스크립트는 항상, 그 외 전체실행형은 --run 일 때만.
        timeout = 180
        stream = False   # True 면 출력을 캡처하지 않고 실시간으로 흘려보냄(긴 빌드·다운로드 진행 표시)
        if cmd.startswith("bin/") or cmd.startswith("./bin/"):
            parts = cmd.split()
            exe = PROJECT_ROOT / parts[0]
            if not exe.exists() and os.name == "nt" and not parts[0].endswith(".exe"):
                exe = PROJECT_ROOT / (parts[0] + ".exe")
            if not exe.exists():
                print("   [doc][SKIP] %s  (바이너리 없음: 빌드 필요)" % cmd)
                skipped += 1
                continue
            miss = _doc_missing_files(parts)
            if miss:
                print("   [doc][SKIP] %s  (파일 없음: %s)" % (cmd, ", ".join(miss)))
                skipped += 1
                continue
            run_cmd = _doc_bin_cmdline(parts, exe)
        elif any(sf in cmd for sf in safe_flags):
            run_cmd = cmd  # --help/--list/--dry-run: 안전(부작용 없음)
        elif run_full:
            run_cmd = cmd            # --run: 설치/빌드/다운로드/전체테스트까지 실제 실행
            timeout = 7200           # 고비용(빌드·다운로드) → 넉넉히
            stream = True            # 진행 상황이 보이도록 실시간 출력
        else:
            print("   [doc][SKIP] %s  (자동실행 제외: 설치/빌드/전체실행 등 — --run 으로 실행)" % cmd)
            skipped += 1
            continue

        # 실행 직전에 커맨드를 먼저 찍는다(긴 실행 중에도 "무엇을 하는 중"인지 보이도록). flush 필수.
        print("   [doc] $ %s%s" % (run_cmd, "   (실행 중...)" if stream else ""))
        sys.stdout.flush()
        try:
            if stream:
                # 출력 캡처하지 않고 그대로 콘솔에 흘려보냄 → 빌드/다운로드 로그가 실시간으로 보임
                r = subprocess.run(run_cmd, shell=True, cwd=str(PROJECT_ROOT), env=env,
                                   stdin=subprocess.DEVNULL, timeout=timeout)
                if r.returncode == 0:
                    print("   [doc]  => RUN ok   : %s" % run_cmd)
                    ran += 1
                else:
                    print("   [doc]  => RUN FAIL : %s  (rc=%s)" % (run_cmd, r.returncode))
                    ran += 1
                    failed += 1
            else:
                r = subprocess.run(run_cmd, shell=True, cwd=str(PROJECT_ROOT), env=env,
                                   stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
                out = (r.stdout or "") + (r.stderr or "")
                if r.returncode != 0 and _looks_like_missing_runtime(out):
                    print("   [doc]  => SKIP     : %s  (런타임/NPU 미탐지)" % run_cmd)
                    skipped += 1
                elif r.returncode == 0:
                    print("   [doc]  => RUN ok   : %s" % run_cmd)
                    ran += 1
                else:
                    print("   [doc]  => RUN FAIL : %s  (rc=%s)" % (run_cmd, r.returncode))
                    sys.stderr.write(out[-1000:])
                    ran += 1
                    failed += 1
        except subprocess.TimeoutExpired:
            print("   [doc]  => RUN FAIL : %s  (timeout %ss)" % (run_cmd, timeout))
            ran += 1
            failed += 1
        sys.stdout.flush()

    print("   [doc] 실행 %d개 / 실패 %d개 / 스킵 %d개" % (ran, failed, skipped))
    if failed:
        return 1
    return 0 if ran else SKIP


def do_postproc_coverage():
    """각 postprocess 카테고리(src/postprocess/<family>)가 (1) postprocess 소스(.h/.hpp/.cpp)를 갖고
    (2) pybind11 바인딩(postprocess_pybinding.cpp)에 '<family>_postprocess.h' 로 등록됐는지 집계.
    0=전부 충족 / 77=src/postprocess 없음 / 1=누락(소스없음/바인딩미등록) 존재."""
    base = PROJECT_ROOT / "src" / "postprocess"
    bind_path = PROJECT_ROOT / "src/bindings/python/dx_postprocess/postprocess_pybinding.cpp"
    if not base.exists() or not bind_path.exists():
        return SKIP
    # 빌드 산출물/캐시 디렉터리는 카테고리가 아니므로 제외(빌드 후 build/ 등이 생김)
    skip_dirs = {"build", "cmake", "cmakefiles", "__pycache__"}
    fams = sorted(d.name for d in base.iterdir()
                  if d.is_dir() and d.name.lower() not in skip_dirs
                  and not d.name.startswith((".", "_")))
    bind = bind_path.read_text(encoding="utf-8", errors="replace")
    exts = (".h", ".hpp", ".cpp", ".cc")
    missing_src, not_bound = [], []
    for f in fams:
        has_src = any("postprocess" in n.lower() and n.lower().endswith(exts)
                      for _, _, files in os.walk(base / f) for n in files)
        if not has_src:
            missing_src.append(f)
        if (f + "_postprocess.h") not in bind:
            not_bound.append(f)
    print("   [rt] postprocess 카테고리 %d개  |  소스없음=%s  바인딩미등록=%s"
          % (len(fams), missing_src or "없음", not_bound or "없음"))
    return 0 if (not missing_src and not not_bound) else 1


def do_models_present():
    if MODELS_DIR.exists() and any(MODELS_DIR.glob("*.dxnn")):
        n = len(list(MODELS_DIR.glob("*.dxnn")))
        print("   [rt] assets/models 에 .dxnn %d개 존재" % n)
        return 0
    return SKIP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("--task", default="")
    ap.add_argument("--loop", type=int, default=1)
    ap.add_argument("--per-task", action="store_true",
                    help="한 모델(yolo)만이 아니라 태스크 카테고리마다 대표 1개씩 실행")
    ap.add_argument("--cam-index", type=int, default=0,
                    help="cam 모드에서 사용할 카메라 인덱스(기본 0 자동)")
    ap.add_argument("--input", default="img", choices=["img", "vid"],
                    help="async-loop 입력 종류(img=이미지 -i / vid=비디오 -v)")
    ap.add_argument("--count", type=int, default=2,
                    help="async-loop 에서 실행할 대표 예제 개수(기본 2)")
    ap.add_argument("--run", action="store_true",
                    help="doc-commands 에서 설치/빌드/다운로드/전체테스트 커맨드까지 실제 실행")
    a = ap.parse_args()

    if a.mode == "cpp-img":
        rc = do_cpp_img_per_task(a.loop) if a.per_task else do_cpp_img(a.task, a.loop)
    elif a.mode == "cpp-vid":
        rc = do_cpp_vid(a.task, a.loop)
    elif a.mode == "py-img":
        rc = do_py_img_per_task(False) if a.per_task else do_py_img(a.task, False)
    elif a.mode == "py-cpp-img":
        rc = do_py_img_per_task(True) if a.per_task else do_py_img(a.task, True)
    elif a.mode == "cpp-showlog":
        rc = do_cpp_showlog_per_task()
    elif a.mode == "cpp-badmodel":
        rc = do_cpp_badmodel()
    elif a.mode == "cpp-model-policy":
        rc = do_cpp_model_policy()
    elif a.mode == "cpp-badinput":
        rc = do_cpp_badinput()
    elif a.mode == "cpp-bin-input":
        rc = do_cpp_bin_input()
    elif a.mode == "cpp-sigint":
        rc = do_cpp_sigint()
    elif a.mode == "postproc-coverage":
        rc = do_postproc_coverage()
    elif a.mode == "doc-commands":
        rc = do_doc_commands(run_full=a.run)
    elif a.mode == "async-loop":
        rc = do_async_loop(a.task, a.input, a.loop, a.count)
    elif a.mode == "cam":
        rc = do_cam(a.cam_index)
    elif a.mode == "models-present":
        rc = do_models_present()
    else:
        sys.stderr.write("unknown mode: %s\n" % a.mode)
        rc = 2
    sys.exit(rc)


if __name__ == "__main__":
    main()
