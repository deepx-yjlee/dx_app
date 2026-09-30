#!/bin/bash
# ▼ SDKREQ-529 — 에러 처리 및 종료 처리 (Linux)
#   통일된 에러 포맷([DXAPP] [ERROR])과 SIGINT(Ctrl+C) 핸들러 확인,
#   잘못된 옵션/명시적 없는 모델·입력 경로 입력 시 비정상 종료(exit≠0)를 검증한다.
#   SDKREQ-529 입력 정책도 검증한다:
#     - 명시적 -m 오류경로 → auto-download 실행 없이 즉시 [ERROR] 종료(잘못 지정은 사용자 책임)
#     - -m 미지정 → 예제 기본 모델을 레지스트리로 해석해 auto-download 시도
#     - 없는 -i/-v 입력 → 'Input file not found' 종료(기본 샘플 fallback 안 함)
#     - 입력 전부 생략 → 기본 샘플 사용(정상)
#     - .bin 요구 3D 예제 → 비-.bin 입력이면 오류
#   (Windows 대응: test_530.bat)
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
# --run / RUN_FULL=1: 정적 검증 뒤 실제 바이너리로 에러/종료 처리까지 검증
RUN_FULL="${RUN_FULL:-0}"; for a in "$@"; do [ "$a" = "--run" ] && RUN_FULL=1; done
echo "PROJECT_ROOT=$PROJECT_ROOT | BUILD_DIR=${BUILD_DIR:-<none>} | RUN_FULL=$RUN_FULL | PY=$PY"
echo ""
grd "에러 포맷 [DXAPP] [ERROR]" "src/cpp_example/common/runner" "[DXAPP] [ERROR]"
gr "SIGINT(Ctrl+C) 핸들러" "src/cpp_example/common/utility/run_dir.hpp" "signalHandler"
# SDKREQ-529 정책 헬퍼(common_util.hpp) 정적 확인
gr "모델 정책 resolveAndValidateModel(-m 없으면 default/auto-dl, 있으면 즉시검증)" "src/cpp_example/common/utility/common_util.hpp" "resolveAndValidateModel"
gr "기본 모델 레지스트리 해석 resolveDefaultModelPath" "src/cpp_example/common/utility/common_util.hpp" "resolveDefaultModelPath"
gr "입력 존재 검증 requireInputExists(엉뚱한 -i/-v → 즉시 종료)" "src/cpp_example/common/utility/common_util.hpp" "requireInputExists"
gr ".bin 입력 검증 requireBinInput(3D LiDAR)" "src/cpp_example/common/utility/common_util.hpp" "requireBinInput"
# 실행: 잘못된 입력에 대해 실제로 비정상 종료(exit!=0)하는지 — argparse 레벨(NPU 불필요)
# NOTE(SDKREQ-529): -m 는 optional 이 되었다(미지정 시 예제 기본 모델 auto-dl). 따라서
#   '인자 없음'은 더 이상 에러가 아니다. 대신 '명시적 -m 오류경로'가 비정상 종료하는지 검증한다.
pybad "Python 잘못된 옵션 → 비정상 종료(exit≠0)" "src/python_example/*/*/*_sync.py" "--nonexistent-xyz"
pybad "Python 명시적 -m 오류경로 → 비정상 종료(exit≠0)" "src/python_example/*/*/*_sync.py" "-m __nonexistent__.dxnn --image sample/img/sample_street.jpg"
__b=""; for __f in "$BUILD_DIR"/*_sync; do [ -x "$__f" ] && __b="$__f" && break; done; if [ -n "$__b" ]; then runfail "C++ 잘못된 모델 경로 → 비정상 종료" "$__b -m __nonexistent__.dxnn -i __nofile__.jpg"; else skipcmd "C++ 잘못된 모델 경로 → 비정상 종료" "빌드 후: bin/*_sync -m __nonexistent__.dxnn -i __nofile__.jpg (비정상 종료 기대)"; fi

# ── 실제 실행 검증(--run / RUN_FULL=1): 빌드된 바이너리로 에러 포맷·Ctrl+C graceful 종료까지 확인 ──
if [ "$RUN_FULL" = "1" ]; then
  echo -e "${BLUE}[--run] 실제 바이너리로 에러/종료 처리 검증${NC}"
  # (1) 없는 모델/파일 실행 → 통일 에러 포맷 '[DXAPP] [ERROR]' 출력 + 비정상 종료 (NPU 불필요)
  rt "C++ 없는 모델 → [DXAPP][ERROR] 포맷 + 비정상 종료" \
     "빌드 필요: ./build.sh --all → bin/*_sync 로 재실행" cpp-badmodel
  # (1a) SDKREQ-529 정책: 명시적 -m 오류경로 → auto-download 실행 없이 즉시 [ERROR] 종료
  rt "C++ 명시적 -m 오류경로 → auto-dl 없이 즉시 [ERROR](정책)" \
     "빌드 필요: bin/*_sync -m <없는경로> -i <아무거나> (다운로더 미실행 기대)" cpp-model-policy
  # (1b) SDKREQ-529 정책: 없는 -i 입력 → 'Input file not found' 종료(기본 샘플로 fallback 안 함)
  rt "C++ 없는 -i 입력 → 'Input file not found' 종료" \
     "빌드+모델 필요: bin/<det>_sync -m <model> -i <없는파일>" cpp-badinput
  # (1c) SDKREQ-529 정책: .bin 을 요구하는 3D 예제에 비-.bin(-i .jpg) → .bin/LiDAR 오류 종료
  rt "C++ 3D 비-.bin 입력 → .bin/LiDAR 오류 종료" \
     "빌드+3D모델 필요: bin/sfa3d_*_sync -m <model> -i <.jpg>" cpp-bin-input
  # (2) 스트림 추론 중 SIGINT(Ctrl+C) → graceful 종료(exit 0/130) (빌드+모델+비디오+NPU 필요)
  rt "C++ 스트림 중 Ctrl+C(SIGINT) → graceful 종료" \
     "빌드+모델+비디오+NPU: bin/<det>_sync -v <video> 실행 중 Ctrl+C → 정상 종료(0)" cpp-sigint
else
  skipcmd "실제 실행 에러/종료 처리(--run)" \
    "RUN_FULL=1 bash tests/req_test/test_529.sh (또는 --run) → 바이너리로 [DXAPP][ERROR]+비정상종료 / SIGINT graceful 확인"
fi
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
