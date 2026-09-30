#!/bin/bash
# ▼ SDKREQ-531 — C++ 후처리(cpp_postprocess) pybind11 바인딩 (Linux)
#   src/postprocess 모듈과 dx_postprocess pybind11 모듈 소스, Python의
#   `from dx_postprocess import` 사용을 확인하고, "각 postprocess 카테고리(패밀리)가
#   소스를 갖고 pybind11 바인딩에 등록됐는지" 커버리지를 검증하며, import 가능 여부·예제 실행을 검증한다.
#   (Windows 대응: test_533.bat — 532는 결번)
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
# catcov: postprocess 카테고리 커버리지(_rt_resolve.py postproc-coverage) — 출력 노출 + exit code 판정.
catcov(){ __o=$("$PY" "$SCRIPT_DIR/_rt_resolve.py" postproc-coverage 2>&1); __rc=$?; [ -n "$__o" ] && echo -e "${BLUE}${__o}${NC}"; if [ "$__rc" -eq 0 ]; then pass "$1"; elif [ "$__rc" -eq 77 ]; then skip "$1 (src/postprocess 없음)"; else fail "$1"; fi; }
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
echo "PROJECT_ROOT=$PROJECT_ROOT | BUILD_DIR=${BUILD_DIR:-<none>} | PY=$PY"
echo ""
ex "후처리 모듈 디렉토리" "src/postprocess"
ex "pybind dx_postprocess 소스" "src/bindings/python/dx_postprocess"
gr "pybind11 모듈 dx_postprocess" "src/bindings/python/dx_postprocess/CMakeLists.txt" "pybind11_add_module(dx_postprocess"
gr "Python에서 dx_postprocess import" "src/python_example/classification/alexnet/alexnet_sync_cpp_postprocess.py" "from dx_postprocess import"
# 카테고리 커버리지: src/postprocess 의 각 postprocess 카테고리(패밀리)가
#   (1) postprocess 소스(.h/.hpp/.cpp)를 갖고 있고 (2) pybind11 바인딩(postprocess_pybinding.cpp)에
#   <family>_postprocess.h 로 등록돼 있는지 한 번에 집계. 하나라도 빠지면 FAIL(누락 목록 출력).
catcov "postprocess 카테고리별 소스 존재 + pybind11 바인딩 등록"
# 실행: 후처리 라이브러리 세팅 스크립트 파싱 + 빌드 산출물 import 시도
shn "setup_postprocess_lib.sh 실행 파싱(bash -n)" "scripts/setup_postprocess_lib.sh"
pytry "dx_postprocess import 가능" "import dx_postprocess" "./build.sh --all && source scripts/setup_postprocess_lib.sh --session"
# run_tc 이식: 후처리 라이브러리+NPU 있으면 cpp_postprocess Python 예제 실제 실행
rt "C++ 후처리 Python 예제 실행" "빌드: ./build.sh --all" py-cpp-img
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
