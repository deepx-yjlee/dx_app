#!/bin/bash
# ▼ SDKREQ-517 — 다양한 입력 소스 지원 (Linux)
#   [요구사항] 모든 C++ 실행파일과 Python 예제가 image / stream inference 로 동작해야 한다.
#             단, image-only 태스크(embedding·reid·attribute_recognition·object_pose_estimation·
#             3d_object_detection·super_resolution)와 face 모델은
#             stream inference 대상에서 제외한다.
#             (hand_detection·hand_landmark 는 프레임 단위 단일 모델 추론으로 stream 을 지원한다.)
#   [검증] ① 입력 옵션(-i/-v/-c/-r) + C++ 입력 추상화 계층 존재 (static)
#          ② pytest 마커로 전체 C++ 바이너리·Python 예제를 image/stream 추론 (runtime)
#             - pytest -m e2e_image  → 모든 예제 이미지 추론
#             - pytest -m e2e_stream → 모든 예제 동영상 추론(image-only 태스크/face 자동 skip)
#             tests/cpp_example, tests/python_example 에서 각각 실행 (test_518.bat 과 동일 방식).
#   [옵션] --run / RUN_FULL=1 : 기본 SKIP 되는 고비용 준비 단계(모델 다운로드·C++ 빌드)까지
#             실제 실행해 C++/Python 전체 image·stream 추론을 끝까지 진행한다.
#             --rtsp-url <url> / RTSP_URL=<url> 지정 시 RTSP 실연결(e2e_rtsp)도 실제 실행.
#             --camera-index <n> / CAM_INDEX=<n> 로 USB 카메라 인덱스 지정(기본 0).
#   (Windows 대응: test_518.bat)
# =============================================================================
# 결과: [PASS]/[FAIL]/[SKIP], 종료코드 = FAIL 개수
#   [PASS] 정적 검증(소스/옵션 존재) 또는 실행 검증(실제 실행 후 종료코드 확인) 통과
#   [SKIP] NPU/장치/네트워크/네이티브 빌드가 있어야만 가능(수동 안내)
# 정적(static) + 실행(runtime, run_tc 방식) 혼합 검증.
# =============================================================================
set +e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT" || exit 2
# ── 옵션 파싱 (형제 스크립트 관례: --run / RUN_FULL=1) ─────────────────────
RUN_FULL="${RUN_FULL:-0}"; RTSP_URL="${RTSP_URL:-}"; CAM_INDEX="${CAM_INDEX:-0}"
while [ $# -gt 0 ]; do
    case "$1" in
        --run)             RUN_FULL=1 ;;
        --rtsp-url)        RTSP_URL="$2"; shift ;;
        --rtsp-url=*)      RTSP_URL="${1#*=}" ;;
        --camera-index)    CAM_INDEX="$2"; shift ;;
        --camera-index=*)  CAM_INDEX="${1#*=}" ;;
        -h|--help)
            cat <<'USAGE'
test_517.sh — SDKREQ-517 다양한 입력 소스 지원 (Linux)

  bash tests/req_test/test_517.sh [OPTIONS]

OPTIONS
  --run                 기본 SKIP 되는 고비용 준비 단계까지 실제 실행해 전체를 끝까지 진행.
                        (모델 없으면 ./setup.sh --all, C++ 실행파일 없으면 ./build.sh --all 후
                         C++/Python 전체 image·stream 추론 수행)  == RUN_FULL=1
  --rtsp-url <url>      RTSP 실연결 검증 주소. 지정 시 pytest -m e2e_rtsp 실제 실행. == RTSP_URL
  --camera-index <n>    USB 카메라 인덱스 (기본 0).                               == CAM_INDEX
  -h, --help            이 도움말 출력 후 종료.

종료코드 = FAIL 개수 (옵션 오류는 2)
USAGE
            exit 0 ;;
        *) echo "test_517.sh: 알 수 없는 옵션: $1  (--help 참고)" >&2; exit 2 ;;
    esac
    shift
done
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
P=0; F=0; S=0
pass(){ echo -e "${GREEN}[PASS]${NC} $1"; P=$((P+1)); }
fail(){ echo -e "${RED}[FAIL]${NC} $1"; F=$((F+1)); }
skip(){ echo -e "${YELLOW}[SKIP]${NC} $1"; S=$((S+1)); }
ex(){ [ -e "$2" ] && pass "$1 ($2)" || fail "$1 (missing: $2)"; }
gr(){ grep -Fq -- "$3" "$2" 2>/dev/null && pass "$1" || fail "$1 (not found: $3)"; }
grd(){ grep -rFq -- "$3" "$2" 2>/dev/null && pass "$1" || fail "$1 (not found: $3)"; }
pyc(){ "$PY" -c "$2" >/dev/null 2>&1 && pass "$1" || fail "$1"; }
pytry(){ "$PY" -c "$2" >/dev/null 2>&1 && pass "$1" || { skip "$1 (미빌드)"; echo -e "   ${YELLOW}↳${NC} $3"; }; }
run(){ echo -e "   ${BLUE}\$ $2${NC}"; eval "$2" >/dev/null 2>&1 && pass "$1" || fail "$1"; }
runfail(){ echo -e "   ${BLUE}\$ $2${NC}"; eval "$2" >/dev/null 2>&1; [ $? -ne 0 ] && pass "$1" || fail "$1"; }
skipcmd(){ skip "$1"; echo -e "   ${YELLOW}↳ 수동:${NC} $2"; }
# ── 실행 검증 헬퍼 (run_tc 방식: 실제 실행 후 종료코드 확인) ──
shn(){ bash -n "$2" 2>/dev/null && pass "$1 ($2)" || fail "$1 (문법오류: $2)"; }
pyhelp(){ __ex=$(ls $2 2>/dev/null | head -1); if [ -n "$__ex" ]; then run "$1" "\"$PY\" \"$__ex\" --help"; else skip "$1 (예제 없음: $2)"; fi; }
pybad(){ __ex=$(ls $2 2>/dev/null | head -1); if [ -n "$__ex" ]; then runfail "$1" "\"$PY\" \"$__ex\" $3"; else skip "$1 (예제 없음: $2)"; fi; }
# rt: run_tc 이식 — 환경 있으면 실제 추론 실행+종료코드 확인, 없으면(rc=77) SKIP.
#   $1 제목  $2 SKIP시 수동안내  $3.. resolver 인자(cpp-img/cpp-vid/py-img/py-cpp-img/models-present)
rt(){ __t="$1"; __man="$2"; shift 2; echo -e "   ${BLUE}\$ _rt_resolve.py $*${NC}"; "$PY" "$SCRIPT_DIR/_rt_resolve.py" "$@" >/dev/null 2>&1; __rc=$?; if [ "$__rc" -eq 0 ]; then pass "$__t"; elif [ "$__rc" -eq 77 ]; then skipcmd "$__t" "$__man"; else fail "$__t (rc=$__rc)"; fi; }
PY="python"; command -v python >/dev/null 2>&1 || PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then for v in venv/bin/activate .venv/bin/activate ../venv-dx-runtime/bin/activate; do [ -f "$v" ] && . "$v" && PY="python" && break; done; fi
if [ -z "${BUILD_DIR:-}" ]; then for d in bin build_x86_64/release/bin build_aarch64/release/bin build/bin; do [ -d "$d" ] && BUILD_DIR="$d" && break; done; fi
# ── --run: 기본 SKIP 되는 고비용 준비 단계를 실제 실행 (다운로드 → 빌드) ──
if [ "$RUN_FULL" = "1" ]; then
    echo -e "${BLUE}[--run]${NC} 전체 진행 모드 — 기본 SKIP 되는 모델 다운로드/C++ 빌드까지 실제 실행"
    if ! "$PY" "$SCRIPT_DIR/_rt_resolve.py" models-present >/dev/null 2>&1; then
        if [ -x ./setup.sh ]; then echo -e "   ${BLUE}\$ ./setup.sh --all${NC}"; ./setup.sh --all
        else echo -e "   ${YELLOW}↳${NC} setup.sh 없음 — 모델 다운로드 생략"; fi
    else
        echo -e "   ${GREEN}↳${NC} 모델 이미 존재 — 다운로드 생략"
    fi
    if ! ls "${BUILD_DIR:-/nonexistent}"/*_sync "${BUILD_DIR:-/nonexistent}"/*_async >/dev/null 2>&1; then
        # --all: 요구사항이 "모든 C++ 실행파일" 이므로 run_demo 만 만드는 기본 --minimal 로는 부족.
        if [ -x ./build.sh ]; then echo -e "   ${BLUE}\$ ./build.sh --all${NC}"; ./build.sh --all
        else echo -e "   ${YELLOW}↳${NC} build.sh 없음 — C++ 빌드 생략"; fi
        for d in bin build_x86_64/release/bin build_aarch64/release/bin build/bin; do
            [ -d "$d" ] && BUILD_DIR="$d" && break
        done
    else
        echo -e "   ${GREEN}↳${NC} C++ 실행파일 이미 존재 — 빌드 생략"
    fi
fi
echo "PROJECT_ROOT=$PROJECT_ROOT | BUILD_DIR=${BUILD_DIR:-<none>} | PY=$PY | RUN_FULL=$RUN_FULL"
echo ""

# ── ① 정적: 입력 옵션 + 입력 추상화 계층 ──────────────────────────────────
ex "C++ 입력 추상화 계층" "src/cpp_example/common/inputs"
gr "이미지 입력 옵션 -i/--image_path" "src/cpp_example/common/runner/async_detection_runner.hpp" "i, image_path"
gr "동영상 입력 옵션 -v/--video_path" "src/cpp_example/common/runner/async_detection_runner.hpp" "v, video_path"
gr "카메라 옵션 -c/--camera_index" "src/cpp_example/common/runner/async_detection_runner.hpp" "c, camera_index"
gr "RTSP 옵션 -r/--rtsp_url" "src/cpp_example/common/runner/async_detection_runner.hpp" "r, rtsp_url"

# ── ② 실행: 모든 예제의 image / stream 추론 (pytest 마커 직접 구동) ────────
# pytest -m e2e_image (모든 바이너리·예제 이미지) / -m e2e_stream (동영상, image-only·face
# 자동 skip). pytest 는 "0 tests collected(exit 5)"를 SKIP 으로 다루지만, 모델이 없어 전 케이스가
# 개별 skip 되면 exit 0(헛 PASS)이 될 수 있으므로, 실행 전 대상(pytest·모델·빌드산출물/런타임)을 게이트한다.
have_pytest(){ "$PY" -c "import pytest" >/dev/null 2>&1; }
have_models(){ "$PY" "$SCRIPT_DIR/_rt_resolve.py" models-present >/dev/null 2>&1; }
have_cpp_bin(){ ls "$BUILD_DIR"/*_sync "$BUILD_DIR"/*_async >/dev/null 2>&1; }
have_py_rt(){ "$PY" -c "import dx_engine" >/dev/null 2>&1; }
# tc: tests/<sub> 에서 pytest -m <marker> 실행 → 0 PASS / 5(no tests) SKIP / 그외 FAIL.
#     pytest 출력을 버리지 않고 그대로 흘려보내(-v) collection·테스트별 진행 로그가 실시간으로
#     보이게 한다(긴 e2e 스윕에서 "멈춘 것처럼" 보이는 문제 방지). 종료코드는 서브셸에서 그대로 전달.
tc(){ __t="$1"; __sub="$2"; __mk="$3"; shift 3; echo -e "   ${BLUE}\$ (cd tests/$__sub && $PY -m pytest -m $__mk --tb=short -v $*)${NC}";
      ( cd "$PROJECT_ROOT/tests/$__sub" && "$PY" -m pytest -m "$__mk" --tb=short -v "$@" ); __rc=$?;
      if [ "$__rc" -eq 0 ]; then pass "$__t"; elif [ "$__rc" -eq 5 ]; then skipcmd "$__t" "환경 미비(0 tests collected) — 빌드/모델/NPU 확인"; else fail "$__t (rc=$__rc)"; fi; }

# C++: 모든 실행파일 image / stream
if have_pytest && have_cpp_bin && have_models; then
    tc "C++ 전체 바이너리 image 추론 (pytest -m e2e_image)" cpp_example e2e_image
    tc "C++ 전체 바이너리 stream 추론, image-only 제외 (pytest -m e2e_stream)" cpp_example e2e_stream
else
    skipcmd "C++ 전체 바이너리 image 추론 (pytest -m e2e_image)" "빌드+모델+NPU 후: cd tests/cpp_example && pytest -m e2e_image"
    skipcmd "C++ 전체 바이너리 stream 추론, image-only 제외 (pytest -m e2e_stream)" "빌드+모델+NPU 후: cd tests/cpp_example && pytest -m e2e_stream"
fi

# Python: 모든 예제 image / stream
if have_pytest && have_py_rt && have_models; then
    tc "Python 전체 예제 image 추론 (pytest -m e2e_image)" python_example e2e_image
    tc "Python 전체 예제 stream 추론, image-only 제외 (pytest -m e2e_stream)" python_example e2e_stream
else
    skipcmd "Python 전체 예제 image 추론 (pytest -m e2e_image)" "venv+dx_engine+모델+NPU 후: cd tests/python_example && pytest -m e2e_image"
    skipcmd "Python 전체 예제 stream 추론, image-only 제외 (pytest -m e2e_stream)" "venv+dx_engine+모델+NPU 후: cd tests/python_example && pytest -m e2e_stream"
fi

# ── 카메라 / RTSP (입력 소스 커버리지, 장치·서버 필요 → 자동감지 or 수동) ──
rt "USB 카메라 실연결(자동감지 -c $CAM_INDEX)" "카메라 미연결(/dev/video$CAM_INDEX 없음) 또는 NPU/빌드 필요: cd tests/cpp_example && pytest test_e2e_camera_rtsp.py -m e2e_camera --camera-index $CAM_INDEX" cam --cam-index "$CAM_INDEX"
if [ -n "$RTSP_URL" ] && have_pytest && have_cpp_bin; then
    tc "RTSP 실연결 ($RTSP_URL)" cpp_example e2e_rtsp --rtsp-url "$RTSP_URL"
else
    skipcmd "RTSP 실연결" "스트림 서버 필요: --rtsp-url rtsp://<addr>/stream (또는 RTSP_URL=rtsp://<addr>/stream) 로 재실행 — 수동: cd tests/cpp_example && pytest test_e2e_camera_rtsp.py -m e2e_rtsp --rtsp-url rtsp://<addr>/stream"
fi
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
