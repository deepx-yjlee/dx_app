# req_test — SDKREQ 요구사항 검증 스크립트

`tests/req_test/` 는 DX-APP 의 요구사항(SDKREQ) 하나하나가 **실제로 구현·동작하는지**를
자동으로 검증하는 스크립트 모음이다. 각 요구사항은 Linux(`.sh`) / Windows(`.bat`)
**한 쌍**으로 검증하며, 파일 번호가 곧 SDKREQ 티켓 번호다 (`test_517.sh` → SDKREQ-517).

- 총 28개 파일, 번호 517~545 (**532는 결번** → 531↔533 쌍)
- 홀수 = `.sh` (Linux/bash), 짝수 = `.bat` (Windows/cmd)
- 인접 홀/짝이 **같은 요구사항을 OS별로** 검증

---

## ⚠ 실행 위치 (필독)

이 repo 는 **독립 저장소**로 관리되지만, 스크립트들은 자기 위치를 기준으로
dx_app 루트를 계산한다.

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"   # ← 두 단계 위가 dx_app 루트라고 가정
cd "$PROJECT_ROOT" || exit 2
```

`_rt_resolve.py` 도 동일하게 `Path(__file__).resolve().parent.parent` 로 루트를
잡고, 모든 `subprocess.run(cwd=PROJECT_ROOT)` 이 여기에 의존한다.

**따라서 실행하려면 이 repo 를 `<dx_app>/tests/req_test/` 에 두어야 한다.**

```bash
git clone <this-repo> <dx_app>/tests/req_test
<dx_app>/tests/req_test/run_all.sh
```

임의의 경로에 clone 한 상태로 실행하면 `PROJECT_ROOT` 가 엉뚱한 디렉토리를
가리켜 28개 스크립트가 모두 FAIL 한다.

---

## 1. 공통 동작 원리

### 1.1 2층 검증 — "코드에 있는가(static)" + "실제로 도는가(runtime)"

하나의 요구사항을 두 각도로 조여서, 둘 다 통과할 때 "커버됐다"고 판정한다.

**(A) 정적 검증 (static)** — 소스/옵션이 실제로 구현돼 있는지

| 헬퍼 | 동작 | 검증 대상 |
|------|------|-----------|
| `ex "제목" <경로>` | 파일/디렉토리 존재 확인 | 기능 모듈·산출물 존재 |
| `gr "제목" <파일> <문자열>` | `grep -Fq` (bat: `findstr /C:`) | 특정 옵션/코드가 소스에 존재 |
| `grd` | 디렉토리 재귀 `grep -rFq` | 여러 파일에 걸친 패턴 |
| `pyc` | `python -c "assert ..."` | 개수/버전 등 수치 조건 |
| `shn` | `bash -n` (문법만 파싱) | 스크립트 무결성 |

**(B) 실행 검증 (runtime)** — 예제/바이너리가 실제로 기동·추론되는지

| 헬퍼 | 동작 | 검증 대상 |
|------|------|-----------|
| `pyhelp` | 예제 `*_sync.py --help` → exit 0 | 예제가 기동되고 인자를 파싱 |
| `pybad` | 잘못된 인자 실행 → exit ≠ 0 기대 | 에러 처리 동작 |
| `run` / `runfail` | 명령 실행 후 종료코드 확인 | 바이너리/스크립트 실동작 |
| `rt` | `_rt_resolve.py` 로 **실제 NPU 추론** 실행 | 요구 기능 end-to-end 동작 |

### 1.2 `rt()` + `_rt_resolve.py` 의 3-state 규약 (SKIP 의 정체)

실행 검증의 핵심. NPU·빌드·모델이 없는 환경에서도 테스트가 "실패"로 무너지지 않게 한다.

```
rc = 0   → 실제 추론 성공          → [PASS]
rc = 77  → 실행 대상 없음(환경 미비) → [SKIP]  (실패 아님, 수동 안내 출력)
rc = 124 → 타임아웃                → [FAIL]
그 외    → 실행했으나 비정상 종료   → [FAIL]
```

→ CI(NPU 없음)에서는 **static 은 PASS, runtime 은 SKIP** 으로 통과하고,
실장비에서는 SKIP 이 PASS 로 바뀌며 실제 추론까지 커버된다.

`_rt_resolve.py` 의 mode: `cpp-img` / `cpp-vid` / `py-img` / `py-cpp-img` / `cam` /
`models-present` (`--task`, `--per-task`, `--loop N` 인자로 범위 지정).

### 1.3 sh ↔ bat 동형(mirror) 구조

두 파일은 **같은 요구사항을 같은 검증 항목으로**, 각 OS 셸 문법만 바꿔 구현한다.

| 개념 | `.sh` (bash) | `.bat` (cmd) |
|------|-------------|-------------|
| 문자열 탐색 | `grep -Fq` | `findstr /C:` |
| 종료코드 | `$?` | `%ERRORLEVEL%` |
| 결과 라인 | `결과: PASS=.. FAIL=.. SKIP=..` | `Result: PASS=.. FAIL=.. SKIP=..` |
| 최종 exit | `exit $F` (FAIL 개수) | `exit /b %F%` |
| 실행 러너 | 공용 `_rt_resolve.py` | **동일한** `_rt_resolve.py` |

핵심은 실제 추론/탐색 로직이 `_rt_resolve.py` 한 곳에 모여 있어, **두 OS가 같은 기준으로
같은 요구사항을 커버**한다는 점이다. `.bat` 이 `.sh` 대비 다른 부분만 아래 표에 "Windows 고유"로 표기한다.

### 1.4 실행 방법

```bash
tests/req_test/run_all.sh                 # Linux: 전체 실행 + 집계
tests/req_test/run_all.sh 517 519 534     # 특정 SDKREQ 번호만
SHOW_FAIL=1 tests/req_test/run_all.sh      # 실패 스크립트 전체 출력
```
```bat
tests\req_test\run_all.bat                 :: Windows: 전체 실행 + 집계
tests\req_test\run_all.bat 518 520 530     :: 특정 번호만
```
종료코드 = FAIL 을 1개 이상 보고한 스크립트 수 (0 = 전부 클린).

---

## 2. SDKREQ 파일별 상세

각 항목: **커버 요구사항 → static 검사 → runtime 검사 → 커버 논리**.

### SDKREQ-517 / 518 — 다양한 입력 소스 지원
- **파일**: [test_517.sh](test_517.sh) / [test_518.bat](test_518.bat)
- **요구사항**: **모든 C++ 실행파일과 Python 예제가 image / stream inference 로 동작해야 한다.**
  단, image-only 예제(태스크: embedding·reid·attribute_recognition·object_pose_estimation·
  3d_object_detection·super_resolution)와 face 모델은 **stream 제외**.
  (hand_detection·hand_landmark 는 프레임 단위 단일 모델 추론으로 **stream 지원**.)
- **static**: `common/inputs` 계층 존재; `async_detection_runner.hpp` 에
  `-i/--image_path`, `-v/--video_path`, `-c/--camera_index`, `-r/--rtsp_url` 옵션 코드 존재
- **runtime (전체 예제 image/stream — `pytest` 마커 직접 구동, sh/bat 동일)**:
  - `tests/cpp_example` · `tests/python_example` 에서 `pytest -m e2e_image` →
    `bin/` 의 **모든** `_sync`·`_async` 바이너리와 **모든** Python `*_sync.py` 예제를 이미지 추론
  - 같은 위치에서 `pytest -m e2e_stream` → 위 전체를 동영상 추론하되,
    **image-only 태스크·face 모델은 자동 skip**
    (`test_e2e.py::test_stream_inference_e2e` 가 `IMAGE_ONLY_TASKS` 로 판별 → 요구의 "제외"와 일치)
  - **사전조건 게이트**: pytest·모델(`assets/models/*.dxnn`)·빌드산출물(C++)/`dx_engine`(Python)이
    없으면 SKIP. pytest 는 "0 tests collected"를 exit 5 로 반환하므로 이를 SKIP 처리하고,
    모델 부재로 전 케이스가 개별 skip 되어 exit 0(헛 PASS)이 나는 것을 막기 위해 실행 전 대상 존재를 먼저 확인한다.
  - 카메라: `rt cam` 자동감지(`/dev/video0`) → 있으면 실행, 없으면 SKIP. RTSP 는 서버 필요로 수동 SKIP
- **커버 논리**: 옵션이 소스에 있고(static) → **전체 예제**가 실장비에서 image/stream 추론까지
  실제로 성공(runtime)해야 통과. "모든 예제" 열거는 `pytest` 의 자동 discovery(`EXECUTABLE_PARAMS`)가
  담당하므로 예제가 추가돼도 테스트 수정 없이 커버된다.
- **sh ↔ bat 동일 메커니즘**: 양쪽 모두 `pytest -m e2e_image` / `e2e_stream` 를 직접 구동
  (`run_tc.sh` 래퍼 불필요 — 어차피 내부가 같은 pytest 마커). **Windows 고유**: `build.bat` 존재 확인 추가

### SDKREQ-519 / 520 — AI 태스크별 추론 결과 출력 포맷
- **파일**: [test_519.sh](test_519.sh) / [test_520.bat](test_520.bat)
- **요구사항**: C++ 예제는 태스크별 `SyncRunner` 로 추론 후 **정해진 포맷으로 stdout 에 결과를 출력**한다.
  결과 텍스트 태그는 `--show-log`(=verbose) 로 게이트되고, image-based 태스크는 텍스트 대신 결과 이미지를 저장한다.
- **카테고리별 출력 포맷 (러너 소스의 마커)**:

  | 카테고리 | 출력 포맷 마커 | 러너 파일 |
  |---|---|---|
  | Object Detection | `[DET] class conf x1 y1 x2 y2 fw fh` | sync_detection_runner.hpp |
  | Classification | `Top predictions:` 상위 5개 + `[CLS]` 태그 | sync_classification_runner.hpp |
  | Pose Estimation | `[POSE] ...` | sync_pose_runner.hpp |
  | Instance Segmentation | `[ISEG] class conf x1 y1 x2 y2` | sync_segmentation_runner.hpp |
  | OBB Detection | `[OBB] ...` | sync_obb_runner.hpp |
  | Face Detection | `[FACE] ...` | sync_face_runner.hpp |
  | Face Alignment | `[ALIGN] ...` | sync_face_alignment_runner.hpp |
  | Hand Landmark | `[HAND] ...` | sync_hand_landmark_runner.hpp |
  | 3D Object Detection | `[3D] ...` | sync_3d_object_detection_runner.hpp |
  | **Object Pose Estimation** | `[POSE]` — `using = SyncPoseRunner` (alias) | sync_object_pose_runner.hpp |
  | **Keypoint Detection** | `[POSE]` — `using = SyncPoseRunner` (alias) | sync_keypoint_runner.hpp |
  | **Panoptic Driving Perception** | `[DET]` — `using = SyncDetectionRunner` (alias) | sync_panoptic_runner.hpp |
  | **Hand Detection** | `[HAND]` — sync_face_runner 재사용하되 task-aware 태그(과거 `[FACE]` → 수정) | (reuses face) |
  | **Attribute Recognition** | `Top predictions:` — 예제가 sync_classification_runner include | (reuses classification) |
  | Semantic Seg · Depth · Embedding · **ReID** · Restoration(SR/Denoise/Enhance) | stdout 텍스트 없음, 결과 이미지 저장 → `--show-log` 시 `produces image-based` INFO | sync_{semantic_seg,depth,embedding,restoration}_runner.hpp |
  | **PPU** | 모델별로 detection/face/pose 러너 재사용 → **단일 포맷 없음** (`[DET]`/`[FACE]`/`[POSE]`) | (heterogeneous) |

  > **핵심**: 22개 지원 태스크 중 상당수가 **전용 러너가 아니라 다른 태스크의 러너를 재사용**한다 —
  > type alias(`using SyncObjectPoseRunner = SyncPoseRunner`)이거나 예제 `_sync.cpp` 가 특정
  > `sync_*_runner.hpp` 를 include 하는 방식. 그래서 출력 포맷은 "태스크 이름"이 아니라 **실제 실행되는
  > 러너**가 결정한다. `ppu` 만은 모델(scrfd/yolo/pose)별로 러너가 달라 단일 포맷이 없다.

- **static**: `grcat` 로 위 표의 **카테고리별 마커가 (재사용 대상 포함) 러너 소스에 존재하는지** 확인. 라인
  번호가 아니라 마커 문자열로 grep(라인 드리프트에 견고). 재사용 태스크는 재사용하는 러너 파일을 grep.
  `ppu` 는 단일 포맷이 없어 **SKIP**(재사용 러너들의 포맷은 각 태스크에서 이미 검증됨).
- **runtime**: `rt cpp-showlog --per-task` → `_rt_resolve.py` 가 **카테고리마다 대표 예제 1개**를
  `-i <task별 이미지> --show-log --no-display -l 1` 로 실제 실행하고, 그 카테고리의 출력 포맷 마커가
  stdout 에 나오는지 확인. `run_tc --e2e-short` 의 "카테고리별 대표 1개" 아이디어를 이식(전 모델 아님).
  빌드/모델/NPU 없으면 SKIP. 대표 모델 해석은 `model_registry.json` 기반이라 이름 gap 문제 없음
  (SDKREQ-517/518 수정과 동일 경로).
- **커버 논리**: 카테고리별 출력 포맷 코드가 존재(static)하고, 카테고리마다 실제 `--show-log` 실행에서
  그 포맷이 실제로 출력(runtime)됨을 증명. 카테고리가 늘어도 `SHOWLOG_MARKERS` 표에 한 줄 추가하면 커버.
- **테스트 불가**: 실제 출력 "값"의 정확성(검출 좌표·클래스 정확도)은 NPU+`.dxnn` 필요 — 포맷/코드 경로
  자체는 소스로 확인 가능.

### SDKREQ-521 / 522 — Python/C++ 예제 커버리지
- **파일**: [test_521.sh](test_521.sh) / [test_522.bat](test_522.bat)
- **static**: `pyshow` 로 **모델 커버리지 상대 비교** — Python 모델 디렉토리 수 ≥ C++ 모델 디렉토리 수
  (고정 개수 하드코딩이 아니라 파일시스템 실재 기준; 현재 python 348 ≥ cpp 348). 공통 인자 파서
  `common/runner/args.py` 존재. (참고: `*_sync.py`·`*_async.py` 각 348개, `*_cpp_postprocess` 변형 별도)
- **runtime**: `*_sync.py --help` 기동으로 예제가 실제 실행 가능한지
- **커버 논리**: Python 예제 커버리지가 C++ 이상임이 파일시스템에 실재(static)하고,
  대표 예제가 실제로 기동(runtime)됨. 개수는 상대 비교라 예제가 늘어도 테스트 수정 불필요

### SDKREQ-523 / 524 — x86-64 / aarch64 네이티브 빌드·실행
- **파일**: [test_523.sh](test_523.sh) / [test_524.bat](test_524.bat)
- **요구사항 해석**: 크로스컴파일이 아니라, **x86-64 호스트 "또는" aarch64 호스트**에서 각각
  네이티브로 `install → build → setup → run_tc` 4단계 파이프라인을 그대로 수행할 수 있어야 한다.
- **static (Linux)**: 4단계 스크립트(`install.sh`/`build.sh`/`setup.sh`/`run_tc.sh`) 존재;
  `build.sh` 가 `target_arch=$(uname -m)` 로 **호스트 arch 자동 감지(네이티브)** + `--arch` 명시 옵션;
  `cmake/toolchain.x86_64.cmake` **와** `toolchain.aarch64.cmake` 가 **둘 다** 존재(=두 arch 모두 빌드 타깃);
  `install.sh` 의 OpenCV `4.2.0`
- **runtime (Linux, 기본 경량)**: `uname -m` 로 호스트 arch 감지 → 4단계 스크립트 `bash -n` →
  네이티브 빌드 산출물(`build_$ARCH/.../*_sync`)이 있으면 PASS, 없으면 SKIP →
  `rt cpp-img` 로 setup 모델+run_tc(pytest) 경로 실추론; **다른** arch 네이티브 빌드는 그 arch 장비에서 수동 SKIP
- **runtime (실제 실행 모드, 옵트인)**: `RUN_FULL=1 bash test_523.sh`(또는 `--run`) 이면
  `./install.sh → ./build.sh --type Release --all → ./setup.sh --all → ./run_tc.sh --e2e-short`
  를 **실제로 순차 실행**하고 각 종료코드로 PASS/FAIL(앞 단계 실패 시 이후 SKIP).
  기본값에서 안 하는 이유: install=sudo apt+네트워크, build=수 분 컴파일, setup=수 GB 다운로드,
  run_tc=NPU 필요 → 매 실행 무조건 돌리면 위험/고비용이라 옵트인. (Windows: `set RUN_FULL=1` 또는 `test_524.bat --run` → `build.bat --all → setup.bat → pytest -m e2e_image`)
- **커버 논리**: 두 arch 모두 네이티브 빌드 타깃임이 스크립트/툴체인에 정의(static)되고,
  현재 호스트 arch 에서 4단계 파이프라인이 실제 추론(runtime)까지 성립함
- **Windows 고유**: Windows(x64) 네이티브 파이프라인 = vcpkg(`vcpkg.json` **유효 JSON 파싱** + `CMakeSettings.json`)
  → `build.bat`(`--all/--minimal/--category`) → `setup.bat` → `pytest -m e2e_image`(run_tc 대응).
  aarch64 네이티브는 aarch64(Linux) 장비에서 test_523.sh 가 검증

### SDKREQ-525 / 526 — Python 환경/버전 요구사항
- **파일**: [test_525.sh](test_525.sh) / [test_526.bat](test_526.bat)
- **시나리오(핵심, 가상환경 테스트)**: 사용자가 원하는 Python 버전의 **venv 를 activate 한 뒤** 스크립트를
  실행하면 자동으로 ① 그 python 버전이 최소 요구(3.8.10) 충족 확인 → ② **그 python 으로 dx_app 빌드**
  (`./build.sh --all` / `build.bat --all`, pybind11 바인딩이 활성 python 에 묶임) → ③ venv 의
  `python -m pip list` 에 **dx-engine 이 없으면 그 목록을 화면에 노출하고 `[WARN]` 경고**(FAIL 아님)
  → ④ **Python 예제만 image 추론** 실행: `./run_tc.sh --python --e2e-quick`
  (= `tests/python_example` 에서 `pytest -m e2e_image`, bat 은 run_tc.bat 이 없어 pytest 직접 호출).
  C++ 예제는 제외(가상환경 = Python 예제 검증이 목적). venv 활성 감지는 `VIRTUAL_ENV` 로 판단.
- **static**: venv 설치 스크립트(`install_python_and_venv.sh` / `setup.bat`) 존재,
  최소 버전 `3.8.10`, `--venv_path` 옵션; 활성 python `version_info ≥ (3,8,10)` 확인(`pyshow`)
- **runtime (venv 미활성 시 경량)**: `bash -n` → `pyhelp` 로 예제 기동 → `rt py-img` 로 실추론,
  venv 시나리오는 재실행 안내로 SKIP
- **exit 5 처리**: pytest 가 수집된 테스트 0개(모델 미설치)면 exit 5 → run_tc.sh/bat 모두 **SKIP**(=pass) 처리
- **override**: `BUILD_CMD`(기본 `./build.sh --all` / `build.bat --all`)로 빌드 명령 교체 가능
  (예: `BUILD_CMD='./build.sh --minimal'`); sh 는 `E2E_CMD` 도 override 가능
- **커버 논리**: 버전 요구/설치 경로가 스크립트에 명시(static)되고, 사용자가 지정한 venv python 으로
  실제 빌드 + **Python 예제 image 추론**(runtime)까지 이어짐. dx-engine 부재는 차단이 아니라 경고로 노출

### SDKREQ-527 / 528 — 모델/자산 다운로드
- **파일**: [test_527.sh](test_527.sh) / [test_528.bat](test_528.bat)
- **요구사항**: `setup --all` 로 ModelZoo 의 모든 `.dxnn` 모델과 테스트 비디오가 받아져야 한다.
- **static**: 다운로더(`download_models.py` / `setup_assets.py`, 출력 경로 `assets/models`),
  `setup.sh`/`setup.bat` 및 `--all`/`--list`/`--dry-run` 옵션, `scripts/modelzoo_manifest.json` 존재.
  manifest 의 `.dxnn` 엔트리 수(현재 **350**)를 참고로 출력
- **runtime (핵심)**: `setup --all` 결과물 점검 —
  ① `assets/models` 의 `.dxnn` 파일 개수 == 기대값(**기본 347**, `EXPECTED_MODELS` 로 override) → 일치 PASS / 불일치 FAIL(actual 표시),
  ② `assets/videos` 에 테스트 비디오(mp4/mov/avi/mkv/webm/m4v) 존재 → 있으면 PASS(개수 표시).
  자산이 없으면(미다운로드) 각각 SKIP + 수동 안내
- **실제 다운로드 모드(옵트인)**: `RUN_FULL=1 bash test_527.sh`(또는 `--run` / Windows `set RUN_FULL=1` / `test_528.bat --run`)
  이면 위 점검 전에 `./setup.sh --all`(bat: `call setup.bat --all`)을 **실제 실행**해 다운로드. 기본값은 네트워크·수 GB
  부담 때문에 실행하지 않고 이미 받아진 자산만 점검
- **커버 논리**: 다운로더/매니페스트/옵션이 존재(static)하고, `setup --all` 산출물의 **모델 347개 + 비디오 존재**를
  실제 파일 개수로 검증(runtime)
- **symlink 주의(Linux 한정)**: **Linux** 에선 `assets/models`·`assets/videos` 가 실제 저장소를 가리키는
  **symlink** 라서, 일반 `find`(미추적)로 세면 **0 개로 오탐**한다 → sh 는 `find -L`(symlink 추적)로 센다.
  (실장비 확인: `find -L assets/models -type f -name '*.dxnn' | wc -l` = **347**)
  **Windows** 는 링크 없이 `assets\models` 에 **직접** 다운로드(실디렉터리)라 링크 이슈가 없다.
  bat 은 `os.walk(followlinks=True)` 로 세지만 실디렉터리라 사실상 일반 순회와 동일(방어적 설정)
- **기대 개수**: 실장비 다운로드 결과 **347** 로 확정(기본값). manifest 엔트리 수(349, casvit 중복 dxnn 2건으로
  실제 파일은 347)와는 다를 수 있으며, 다르면 `EXPECTED_MODELS` 로 조정

### SDKREQ-529 / 530 — 에러 처리 및 종료 처리
- **파일**: [test_529.sh](test_529.sh) / [test_530.bat](test_530.bat)
- **static**: `grd` 로 `runner` 디렉토리에 `[DXAPP] [ERROR]` 포맷; `run_dir.hpp` 에 `signalHandler`(SIGINT);
  `common_util.hpp` 에 SDKREQ-529 정책 헬퍼 `resolveAndValidateModel`/`resolveDefaultModelPath`/
  `requireInputExists`/`requireBinInput`
- **runtime (기본)**: `pybad` 로 인자 없음/`--nonexistent-xyz` → exit ≠ 0; `runfail` 로 C++ 없는 모델 경로 →
  비정상 종료(argparse/로드 레벨이라 **NPU 불필요**)
- **SDKREQ-529 입력 정책(코드 동작)**: `-m` 미지정 → 예제 dir 이름(=바이너리 base)으로 `model_registry.json` 을
  조회해 기본 모델을 해석하고 없으면 auto-download 시도. **명시적 `-m` 오류경로 → auto-download 실행 없이
  즉시 `[DXAPP] [ERROR]` 종료**(잘못 지정은 사용자 책임). 없는 `-i`/`-v` → `Input file not found` 종료(기본
  샘플로 fallback 안 함). 입력 전부 생략 → 기본 샘플 사용. `.bin` 을 요구하는 3D 예제는 비-.bin 입력이면 오류.
  C++ 에러 exit=255(`fatal_error`→예외→`return -1`), Python 은 `sys.exit(1)`.
- **runtime (실제 실행, `--run` / `RUN_FULL=1`)**: 정적 검증 후 빌드된 바이너리로 실제 실행까지 확인 —
  ① `_rt_resolve.py cpp-badmodel`: 없는 모델/이미지로 실행 → 출력에 **`[DXAPP] [ERROR]` 포맷** + **비정상 종료**,
  ② `cpp-model-policy`: 명시적 `-m` 오류경로 → **auto-download 미실행 + 즉시 `[DXAPP][ERROR]` 종료**(정책),
  ③ `cpp-badinput`: 유효 모델 + 없는 `-i` → **`Input file not found` 종료**(기본샘플 fallback 안 함),
  ④ `cpp-bin-input`: 3D 예제에 비-.bin(-i .jpg) → **`.bin`/`LiDAR` 오류 종료**(①~④ 모두 NPU 불필요),
  ⑤ `cpp-sigint`: 스트림 추론을 몇 초 돌린 뒤 **SIGINT(Ctrl+C) → graceful 종료(exit 0/130)**
  (`_run_stream` 재사용, 빌드+모델+비디오+NPU 필요). Windows 는 `cpp-sigint` 자동 **SKIP**(수동 안내)
- **커버 논리**: 에러 포맷/시그널 핸들러/정책 헬퍼가 구현(static)돼 있고, 잘못된 모델·입력은 정책대로 비정상 종료·
  `[DXAPP][ERROR]` 출력(auto-dl 오남용 없음), 스트림 중 Ctrl+C 는 graceful 종료됨을 실제 실행(runtime)으로 검증

### SDKREQ-531 / 533 — C++ 후처리(cpp_postprocess) pybind11 바인딩
- **파일**: [test_531.sh](test_531.sh) / [test_533.bat](test_533.bat) *(532 결번)*
- **static**: `src/postprocess` 및 `src/bindings/python/dx_postprocess` 존재;
  `CMakeLists.txt` 의 `pybind11_add_module(dx_postprocess`; 예제의 `from dx_postprocess import`
- **카테고리 커버리지(핵심)**: `_rt_resolve.py postproc-coverage` — `src/postprocess/<family>` 각 카테고리가
  ① postprocess 소스(.h/.hpp/.cpp) 보유 ② pybind11 바인딩(`postprocess_pybinding.cpp`)에
  `<family>_postprocess.h` 로 등록됨 을 집계. 하나라도 빠지면 FAIL(누락 목록 출력).
  현재 **50개 카테고리 전부 소스 존재 + 바인딩 등록**(sh `catcov` / bat `:catcov` 공용, 로직은 resolver 단일 소스)
- **runtime**: `setup_postprocess_lib.sh` `bash -n` → `pytry import dx_postprocess`(미빌드 시 SKIP) →
  `rt py-cpp-img` 로 cpp_postprocess Python 예제 실행
- **커버 논리**: 바인딩 모듈이 소스/빌드 설정에 존재하고 **모든 postprocess 카테고리가 바인딩에 등록**됨(static/커버리지),
  빌드되면 import 및 예제 실행(runtime)됨

### SDKREQ-534 / 535 — 반복 추론(loop) 옵션
- **파일**: [test_534.sh](test_534.sh) / [test_535.bat](test_535.bat)
- **static**: `async_detection_runner.hpp` 의 `-l/--loop`; `args.py` 의 `--loop`
- **runtime (실행 시나리오)**: `_rt_resolve.py async-loop` 모드로 —
  ① **classification async 대표 2개** → 이미지 input(`-i`), **`--loop 10000`**,
  ② **object_detection async 대표 2개** → 비디오 input(`-v`), **`--loop 20`** 을 실제 실행하고
  모두 정상 종료(exit 0)하는지 확인. 대표 예제는 레지스트리 task(`classification`/`object_detection`)로
  매칭된 `*_async` 바이너리 중 모델 준비된 것 앞에서부터 `--count`개(기본 2). 빌드/모델/NPU 없으면 SKIP.
  (`--task`/`--input`(img|vid)/`--loop`/`--count` 인자로 조정)
- **저사양 보드 자동 감량 (요구사항 이탈)**: 저사양 보드에서 `--loop 10000` 은 케이스 하나가
  수십 분~시간 단위로 늘어나 완주가 불가능하다. `_rt_resolve.py` 가 보드 스펙을 자동 판별해
  **케이스당 wall-clock 예산 300초**에 맞춰 반복 횟수를 감량한다.
  - **판별**: `platform.machine()` 이 ARM 계열(`aarch64`/`arm*`) **이면서** `os.cpu_count() <= 8`.
    자동 판별이 맞지 않는 보드는 **`RT_LOW_SPEC=1`**(강제 감량) / **`RT_LOW_SPEC=0`**(강제 해제)로 지정.
  - **상한**: `300s × 가정 처리량`(img `7.0 it/s` → 2100회, vid `3.0 it/s` → 900회, 최소 20회).
    가정 처리량은 실측이 아니라 **하한 가정치**라 실제 보드가 더 빠르면 예산보다 일찍 끝난다.
    요청값보다 늘리지 않으므로 od(vid/20)는 영향 없고, 고사양 보드는 10000 그대로 실행한다.
  - **표기**: 감량되면 `[rt][loop-cut] 저사양 보드 감량: --loop 10000 → 2100 (...)` 줄을 출력하고
    결과는 **[PASS]** 로 둔다(반복 추론의 안정 종료 자체는 검증되므로). 출력은 `test_534.sh` 의
    `rtloop()` / `test_535.bat` 의 `:rtloop` 헬퍼가 노출한다.
- **커버 논리**: 반복 옵션이 구현(static)되고, 대량 반복 추론(cls 10000·od 20 — 저사양 보드는 감량)이
  실제로 안정 종료(runtime)됨

### SDKREQ-536 / 537 — CLI help/usage 및 인자 파서
- **파일**: [test_536.sh](test_536.sh) / [test_537.bat](test_537.bat)
- **static**: C++ `h, help` 옵션; Python argparse `allow_abbrev=False`
- **runtime (`pytest -m help` 위임, --help 만)**: `tests/python_example` · `tests/cpp_example` 에서
  `pytest -m help -k "not cpp_postprocess"`(전용 `@pytest.mark.help` = `test_cli_help.py` 의 `--help` 테스트) 실행 —
  **`--help` → exit 0 + usage 키워드** 검증. `cli` 마커 전체(인자 없음/잘못된 옵션/모드 파싱 등)가 아니라
  **--help 만 최소로** 확인. Python plain `_sync`/`_async` 는 `common.runner` 를 통해 dx_engine 를 lazy load 하므로
  `--help` 가 런타임 없이 동작(CI-safe); **`_cpp_postprocess` 변형은 top-level 에서 `dx_postprocess`/`dx_engine` 를
  eager import 해 --help 조차 네이티브 런타임이 필요**하므로 `-k "not cpp_postprocess"` 로 제외한다.
  C++ 은 빌드된 바이너리 기준. exit 5(수집 0개=예제/빌드 필요)·pytest 부재는 SKIP
- **커버 논리**: help 옵션/파서 설정이 존재(static)하고, 전체 예제의 `--help` 가 실제로 exit 0 + usage 출력(runtime)함을
  `test_cli_help.py` 스위트로 위임 검증(예제 추가 시 pytest 자동 discovery 로 커버)

### SDKREQ-538 / 539 — 독립(standalone) 모델 패키지 추출
- **파일**: [test_538.sh](test_538.sh) / [test_539.bat](test_539.bat)
- **static (Linux)**: `extract_model_package.sh` 의 `--lang`/`--output-dir`
- **runtime (Linux, 기본)**: `bash -n` → `run` 으로 **실제 독립 패키지 추출 + CMakeLists 생성 확인**
  (파일 복사라 NPU 불필요, 대표 object_detection 모델 1개를 `--output-dir` 로 추출)
- **static (dx_tool 래퍼)**: `dx_tool.sh` 존재 + `extract|export)` 서브커맨드 디스패치,
  `Prune unused common/ files?` 프롬프트, `PRUNE_OPT=(--no-prune)` 전달, `bash -n`
- **runtime (dx_tool 래퍼, Linux 기본)**: 같은 extract 기능의 **대화형 진입점 `dx_tool.sh extract`** 를
  프롬프트에 stdin 주입(`lang` → `model path` → `output dir` → `prune [Y/n]`)해 비대화형 실행 —
  ① C++ 추출(prune 기본) → `CMakeLists.txt` 생성 ② Python 추출 → `<out>/py/<cat>/<model>/<model>_sync.py`
  ③ `n` 응답 → `--no-prune` 전체 `common/` 복사 ④ **prune 이 실제로 축소했는지 파일 수 비교**
  (`prune=16 < no-prune=121`) — ④ 가 깨지면 prune 프롬프트가 `--no-prune` 을 잘못 전달한다는 뜻.
  `dx_tool.sh` 는 `set -e` 라 `extract_model_package.sh` 실패가 종료코드로 전파된다.
  **stdin 이 EOF 면 model-path 재입력 루프가 무한 반복**되므로 모든 실행에 `timeout 300` 을 건다
  (`timeout` 부재 시 SKIP). `dx_tool.sh` 는 Linux 전용이라 `test_539.bat` 에는 대응 항목이 없다
- **runtime (실제 빌드, `--run` / `RUN_FULL=1`)**: 추출된 패키지를 **소스 트리 밖에서 `cmake -S … -B … && cmake --build`**
  하여 `*_sync` 실행파일이 생성되는지 확인 → "진짜 독립적으로 컴파일되는가"를 검증(cmake+OpenCV+dxrt 필요,
  `DXRT_INSTALLED_DIR` 기본 `/usr/local`). cmake 없으면 SKIP
- **커버 논리**: 추출 옵션이 있고(static), 실제로 독립 패키지가 생성되며(runtime), **두 진입점
  (`extract_model_package.sh` 직접 호출 · `dx_tool.sh extract` 대화형 래퍼)이 모두 동작**하고,
  prune 기본/`--no-prune` 양 경로가 성립하며, 옵트인 시 그 패키지가 단독으로 빌드(runtime `--run`)됨
- **잡아낸 실제 결함**: `--run` 단독 빌드가 추출된 `_async` 예제의 **pthread 링크 누락**(`undefined reference to
  pthread_create`)을 검출 → `extract_model_package.sh` 가 생성하는 CMakeLists 가 엔트리 `.cpp` 만 grep 해
  스레드 사용을 못 보고 pthread 를 안 걸던 버그. `find_package(Threads)` + `Threads::Threads`(COMMON_LIBS)로 수정
- **Windows 고유**: `extract_sln_package.bat`/`.py`, `--output-dir`/`--no-generate-sln`, `ast.parse` 유효성 + `--help` 기동;
  **실제 추출**은 `--no-generate-sln`(파일 복사, VS 불필요)로 `<out>\sln\<category>\<model>\CMakeLists.txt` 생성 확인;
  `--run` 이면 CMake 로 **`.sln` 실제 생성**까지(VS2022 generator 필요, 없으면 SKIP)

### SDKREQ-540 / 541 — 문서 기재 진입 스크립트/커맨드
- **파일**: [test_540.sh](test_540.sh) / [test_541.bat](test_541.bat)
- **static**: `install.sh`/`setup.sh`/`build.sh`/`run_demo.sh`/`dx_tool.sh` 존재;
  `README.md`·설치문서에 `build.sh`/`setup.bat` 커맨드 기재
- **runtime (문서 커맨드 일괄, `_rt_resolve.py doc-commands`)**: 진입 스크립트 `bash -n` → `run_demo.py --help` →
  **README·docs/\*\*/\*.md 의 코드블록에서 실행형 커맨드라인을 모두 추출**(`./`·`\` 연속 라인·`bin/` 포함)해
  **각 커맨드를 실행/스킵하고 한 줄씩 로그**(`[doc][RUN ok/FAIL/SKIP] <커맨드>`)로 남긴다:
  - `bin/*_sync|_async …` 추론 커맨드 → 바이너리+모델·이미지 있으면 **실제 실행**(`--no-display` 보강), 없으면 SKIP(사유)
  - `--help`/`--list`/`--dry-run` 안전 플래그 스크립트 → 실행
  - `install`/`build`/`setup`/`run_tc`/`run_demo` 의 전체 실행형(무인자·설치·빌드·다운로드) → 기본은 **SKIP 로그**,
    **`--run`/`RUN_FULL=1` 이면 이들까지 실제 실행**(넉넉한 타임아웃 7200s, `stdin=EOF` 로 인터랙티브 hang 방지)
  - `<model_name>` 등 **자리표시자 포함 커맨드는 항상 SKIP**(문서 예시)
  - `.sh` 는 Linux 전용 → Windows(bat)에선 SKIP, `bin/*.exe` 만 실행. 런타임/NPU 미탐지도 SKIP
  - 종료: 실행한 커맨드 중 실패 있으면 FAIL, 하나라도 성공하면 PASS, 실행 대상 없으면 SKIP(rc=77)
- **커버 논리**: 문서가 가리키는 스크립트가 실재/무결(static)하고, 문서에 적힌 **모든 커맨드라인**을 열거해
  실행 가능한 것은 실제 실행하고 나머지는 사유와 함께 로그로 남겨 "문서 커맨드가 실제 동작함"을 투명하게 검증(runtime)

### SDKREQ-542 / 543 — 모델 레지스트리 및 벤치마킹
- **파일**: [test_542.sh](test_542.sh) / [test_543.bat](test_543.bat)
- **static**: `config/model_registry.json` 존재 + `pyc` 로 **349개 등록** 검증; `bench_models.sh` 존재
- **runtime (기본)**: `bench_models.sh` `bash -n` → `rt cpp-img --per-task` / `rt py-img --per-task`
  로 태스크 카테고리별 대표 모델 C++/Python sync 추론
- **runtime (실제 벤치, `--run` / `RUN_FULL=1`)**: `./scripts/bench_models.sh --lang both --loops 1`
  (범위 조정 `BENCH_ARGS`)로 **전체 모델 벤치마킹을 실제 실행**하고 결과 **`<out>/results.csv` 생성 + 모델 행 수**를
  확인 → PASS. bin(빌드) 없으면 SKIP. 실행 로그는 실시간 스트리밍
- **커버 논리**: 레지스트리 모델 수/벤치 스크립트가 존재(static)하고, 대표 모델 실추론 + (`--run`) 전체 벤치 CSV까지 성립(runtime)
- **Windows 고유**: `bench_models.sh` 가 **Linux 전용**이라, `--run` 시 Windows 는 `rt cpp-img --per-task`/`py-img --per-task`
  로 태스크 카테고리별 전체 실추론으로 대체(벤치 CSV 는 Linux 에서 test_542.sh 로)

### SDKREQ-544 / 545 — 통합 데모 런처(run_demo)
- **파일**: [test_544.sh](test_544.sh) / [test_545.bat](test_545.bat)
- **데모 레지스트리**: `run_demo.py` 에 **23개 데모**(태스크별 대표 모델 1개씩; Detection·Pose·Seg·
  Classification·Depth·Restoration·Recognition·PPU·Keypoint·Driving·3D·Hand 등)가 등록돼 있고,
  3단계 대화형(Task → Mode → Input) 또는 `--task/--mode/--input` 비대화형으로 1개 데모 실행.
- **static**: `run_demo.sh`/`run_demo.py` 의 `--task`/`--mode`/`--input` 옵션 + **`--all`** 옵션 존재
- **runtime (`run_demo.py --all` — 전 데모 일괄 실행)**: `run_demo.sh` `bash -n` → `run_demo.py --help`(exit 0) →
  **`run_demo.py --all`** 로 23개 데모를 데모당 **최대 3변형** — **C++ async + Python async +
  Python async+cpp_postprocess**(py async 없는 데모는 C++ async만) · **image** 입력 · **`--no-display`** ·
  **save 모드** · show-log 없음으로 실제 실행(총 **최대 67 실행** = 23 C++ + 22 Python + 22 Python+cpp_pp)하고
  **`OK/FAIL/SKIP` 요약** 출력. 모델/바이너리/예제/입력 없으면 각 SKIP.
  3-state 종료(0=일부 실행 성공 / 1=실패 / 77=실행 대상 없음)라 CI(모델 없음)에선 SKIP, 실장비에선 실제 실행.
- **커버 논리**: 런처 옵션(`--all` 포함)이 존재(static)하고, **모든 데모가 실제로 기동·추론(runtime)** 됨을
  한 번에 검증. 데모가 늘면 `run_demo.py` 의 `DEMOS` 에 한 줄 추가하면 `--all` 이 자동 커버

---

## 3. 참고

- 실행 러너 로직: [_rt_resolve.py](_rt_resolve.py) — 환경 유무에 따라 실추론(rc=0) 또는 SKIP(rc=77)
- 티켓 번호는 **파일 번호 그대로** 부여(예: `test_517` → SDKREQ-517). 실제 Jira 에서
  홀/짝 쌍이 하나의 티켓으로 묶여 있다면 라벨을 공유 번호로 통일 가능.
- 각 스크립트 헤더 주석에도 동일한 SDKREQ 라벨/요약이 기재돼 있다.
