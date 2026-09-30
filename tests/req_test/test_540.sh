#!/bin/bash
# ▼ SDKREQ-540 — 문서 기재 진입 스크립트/커맨드 (Linux)
#   핵심 진입 스크립트(install/setup/build/run_demo, dx_tool.sh) 존재와 README/문서에
#   커맨드 기재 확인, 스크립트 파싱을 검증하고, 문서(README/docs)의 "모든" 커맨드라인을 열거해
#   각각 실행/스킵을 로그로 남긴다(_rt_resolve.py doc-commands).
#   (Windows 대응: test_541.bat)
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
ex "install.sh" "install.sh"
ex "setup.sh" "setup.sh"
ex "build.sh" "build.sh"
ex "run_demo.sh" "run_demo.sh"
ex "dx_tool.sh" "scripts/dx_tool.sh"
gr "README에 build.sh 커맨드 기재" "README.md" "build.sh"
# 실행: 문서에 기재된 진입 스크립트들이 문법 오류 없이 기동되는지 + run_demo CLI 실행
shn "install.sh 실행 파싱(bash -n)" "install.sh"
shn "setup.sh 실행 파싱(bash -n)" "setup.sh"
shn "build.sh 실행 파싱(bash -n)" "build.sh"
shn "run_demo.sh 실행 파싱(bash -n)" "run_demo.sh"
run "run_demo.py --help → exit 0" "\"$PY\" scripts/run_demo.py --help"
# 문서(README/docs)의 "모든" 커맨드라인을 열거해 각각 실행/스킵을 로그로 출력.
#   bin/*_sync|_async 추론 = 빌드+모델 있으면 실제 실행 / --help·--list·--dry-run 스크립트 = 실행 /
#   install·build·setup·run_tc 전체실행형 = 고비용이라 실행 안 함(로그만).
# --run / RUN_FULL=1: 기본 SKIP 되는 설치/빌드/다운로드/전체테스트 커맨드까지 실제 실행
RUN_FULL="${RUN_FULL:-0}"; for a in "$@"; do [ "$a" = "--run" ] && RUN_FULL=1; done
[ "$RUN_FULL" = "1" ] && DOC_RUN="--run" || DOC_RUN=""
doccmd(){ echo -e "   ${BLUE}\$ _rt_resolve.py doc-commands $DOC_RUN${NC}";
  "$PY" "$SCRIPT_DIR/_rt_resolve.py" doc-commands $DOC_RUN; __rc=$?;
  if [ "$__rc" -eq 0 ]; then pass "$1"; elif [ "$__rc" -eq 77 ]; then skipcmd "$1" "빌드+모델+NPU 시 문서 bin/ 추론이 실제 실행됨(현재 실행 대상 없음). 설치/빌드/다운로드 커맨드까지: --run"; else fail "$1 (rc=$__rc)"; fi; }
doccmd "문서 기재 모든 커맨드 실행/스킵 로그${DOC_RUN:+ (--run: 전체 실행)}"
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
