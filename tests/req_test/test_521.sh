#!/bin/bash
# ▼ SDKREQ-521 — Python/C++ 예제 커버리지 (Linux)
#   Python sync/async 예제가 등록된 supported 모델을 각각 커버하는지(모델 카탈로그
#   연동, 하드코딩 개수 아님), Python 모델 커버리지 ≥ C++, 공통 인자 파서 존재를
#   확인하고 예제가 실제 기동·추론되는지 검증한다.
#   (Windows 대응: test_522.bat)
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
# pynum: 개수 동등 비교 — 기대값과 실제값을 항상 로그로 보여준다(실패 원인 즉시 확인).
#   $1 제목  $2 실제 개수를 stdout으로 print 하는 python 표현식  $3 기대값
pynum(){ __n=$("$PY" -c "$2" 2>/dev/null); echo -e "   ${BLUE}↳ expected=$3  actual=${__n:-<error>}${NC}"; [ "$__n" = "$3" ] && pass "$1" || fail "$1 (expected=$3 actual=${__n:-error})"; }
# pyshow: python 표현식의 stdout(진단 로그)을 보여주고, exit code 로 PASS/FAIL.
#   표현식은 비교값을 print 하고 실패 시 assert/sys.exit(1) 로 종료한다.
pyshow(){ __out=$("$PY" -c "$2" 2>&1); __rc=$?; [ -n "$__out" ] && echo -e "   ${BLUE}↳ ${__out}${NC}"; [ "$__rc" -eq 0 ] && pass "$1" || fail "$1"; }
# pycov: pyshow 와 같되 exit code 77 은 SKIP(모델 미다운로드 등 환경 부재)으로 처리.
pycov(){ __out=$("$PY" -c "$2" 2>&1); __rc=$?; [ -n "$__out" ] && echo -e "   ${BLUE}↳ ${__out}${NC}"; if [ "$__rc" -eq 0 ]; then pass "$1"; elif [ "$__rc" -eq 77 ]; then skip "$1 (모델 미다운로드)"; else fail "$1"; fi; }
# shex: python 스크립트 파일을 실행해 stdout(진단 로그)을 보여주고 exit code 로 PASS/FAIL.
shex(){ __out=$("$PY" "$2" 2>&1); __rc=$?; [ -n "$__out" ] && echo -e "   ${BLUE}↳ ${__out}${NC}"; [ "$__rc" -eq 0 ] && pass "$1" || fail "$1"; }
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
# 예제 완성도(모델 카탈로그 연동): 각 예제 디렉터리가 4변형(sync/async/sync_cpp/
# async_cpp)을 완비했는지 검증한다. registry model_name→dxnn→dir 3단계 fuzzy 매칭은
# 변형 접미사(_1/_v2)·모델 미다운로드로 오탐이 나므로, 소스 사실인 변형 존재로 검증.
shex "Python 예제 4변형 완성도 (sync/async/cpp_postprocess)" "$SCRIPT_DIR/_check_example_variants.py"
# 커버리지: 모델 카탈로그(model_registry.json) 연동 — supported .dxnn 모델마다 Python/C++
# 예제 dir 이 존재하는지, orphan 예제가 없는지, python>=cpp 커버리지를 검증(개수 하드코딩 아님).
shex "모델 레지스트리 커버리지 (supported .dxnn ↔ 예제, python>=cpp)" "$SCRIPT_DIR/_check_registry_coverage.py"
ex "공통 인자 파서" "src/python_example/common/runner/args.py"
# 실행: C++ 예제와 동일 태스크의 Python 예제가 실제로 기동되는지
pyhelp "Python 예제 실행 기동(--help→exit 0)" "src/python_example/*/*/*_sync.py"
# run_tc 이식: dx_engine+모델 있으면 Python 예제로 실제 추론 실행(exit 0 확인)
rt "Python 예제 실추론(--no-display)" "NPU+dx_engine: python <task>/<model>/*_sync.py --model <m>.dxnn --image <img>" py-img
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
