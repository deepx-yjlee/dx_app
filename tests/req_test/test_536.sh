#!/bin/bash
# ▼ SDKREQ-536 — CLI help/usage 및 인자 파서 (Linux)
#   C++ help 옵션(h, help)과 Python argparse의 allow_abbrev=False 를 정적 확인하고,
#   --help 동작은 `pytest -m help`(tests/*/test_cli_help.py) 로 위임한다 — --help → exit 0 + usage 출력.
#   (help 마커는 --help 전용. cli 마커 전체(인자 파서 등)가 아니라 --help 만 최소로 검증)
#   cpp_postprocess 변형은 top-level 에서 dx_postprocess/dx_engine 를 eager import 하여 --help 도
#   런타임이 필요하므로 -k "not cpp_postprocess" 로 제외(plain sync/async 만 검증).
#   (Windows 대응: test_537.bat)
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
echo "PROJECT_ROOT=$PROJECT_ROOT | BUILD_DIR=${BUILD_DIR:-<none>} | PY=$PY"
echo ""
gr "C++ help 옵션(h, help)" "src/cpp_example/common/runner/async_detection_runner.hpp" "h, help"
gr "Python argparse(allow_abbrev=False)" "src/python_example/common/runner/args.py" "allow_abbrev=False"
# helptest: `pytest -m help`(test_cli_help.py) 를 예제 디렉토리에서 실행 — --help 만 검증.
#   exit 0=통과 / 5=수집된 --help 테스트 없음(예제·빌드 필요)→SKIP / pytest 없음→SKIP / 그외→FAIL.
helptest(){ __t="$1"; __d="$2";
  "$PY" -c "import pytest" >/dev/null 2>&1 || { skipcmd "$__t" "pytest 필요(pip install -r requirements)"; return; }
  [ -d "$__d" ] || { skip "$__t (디렉토리 없음: $__d)"; return; }
  # cpp_postprocess 변형은 top-level 에서 dx_postprocess/dx_engine 를 eager import 하므로
  # --help 조차 네이티브 런타임이 필요 → 경량 --help 검증에서 제외(plain sync/async 만).
  echo -e "   ${BLUE}\$ (cd $__d && $PY -m pytest -m help -k 'not cpp_postprocess')${NC}";
  ( cd "$__d" && "$PY" -m pytest -m help -k "not cpp_postprocess" --tb=short -q ); __rc=$?;
  if [ "$__rc" -eq 0 ]; then pass "$__t"; elif [ "$__rc" -eq 5 ]; then skipcmd "$__t" "수집된 --help 테스트 없음(예제/빌드 필요)"; else fail "$__t (rc=$__rc)"; fi; }
# 실행: --help 만 위임 검증 — Python(항상 가능) + C++(빌드 시) 예제의 --help → exit 0 + usage
helptest "Python 예제 --help (pytest -m help)" "tests/python_example"
helptest "C++ 예제 --help (pytest -m help)"    "tests/cpp_example"
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
