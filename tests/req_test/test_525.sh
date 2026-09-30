#!/bin/bash
# ▼ SDKREQ-525 — Python 환경/버전 요구사항 (Linux)
#   [요구사항] dx_app 은 지정된 Python(최소 3.8.10) 환경에서 빌드·실행되어야 한다.
#   [시나리오] 사용자가 원하는 Python 버전의 venv 를 activate 한 뒤 이 스크립트를 실행하면:
#     ① 활성 venv 의 python 버전이 최소 요구(3.8.10)를 만족하는지 확인하고
#     ② 그 python 으로 dx_app 을 빌드하고 (pybind11 바인딩이 활성 python 에 묶임)
#     ③ venv 의 `python -m pip list` 에 dx-engine 이 없으면 그 목록을 화면에 노출하고 경고한 뒤
#     ④ `./run_tc.sh --python --e2e-quick` (Python 예제만 image 추론)을 실행한다.
#        (가상환경 테스트이므로 C++ 이 아닌 Python 예제 image 추론까지만 확인)
#   venv 를 activate 하지 않고 실행하면(=시나리오 미충족) 정적/경량 검증만 하고 재실행을 안내한다.
#   (Windows 대응: test_526.bat)
# =============================================================================
# 결과: [PASS]/[FAIL]/[SKIP]/[WARN], 종료코드 = FAIL 개수
#   [PASS] 정적 검증(소스/옵션 존재) 또는 실행 검증(실제 실행 후 종료코드 확인) 통과
#   [SKIP] NPU/장치/네트워크/네이티브 빌드가 있어야만 가능(수동 안내)
#   [WARN] 진행은 하되 결과 신뢰도에 영향(예: dx-engine 미설치) — FAIL 로 세지 않음
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
warn(){ echo -e "${YELLOW}[WARN]${NC} $1"; S=$((S+1)); }
ex(){ [ -e "$2" ] && pass "$1 ($2)" || fail "$1 (missing: $2)"; }
gr(){ grep -Fq -- "$3" "$2" 2>/dev/null && pass "$1" || fail "$1 (not found: $3)"; }
skipcmd(){ skip "$1"; echo -e "   ${YELLOW}↳ 수동:${NC} $2"; }
# ── 실행 검증 헬퍼 (run_tc 방식: 실제 실행 후 종료코드 확인) ──
shn(){ bash -n "$2" 2>/dev/null && pass "$1 ($2)" || fail "$1 (문법오류: $2)"; }
# pyshow: python 표현식의 stdout(진단 로그)을 보여주고 exit code 로 PASS/FAIL.
pyshow(){ __out=$("$PY" -c "$2" 2>&1); __rc=$?; [ -n "$__out" ] && echo -e "   ${BLUE}↳ ${__out}${NC}"; [ "$__rc" -eq 0 ] && pass "$1" || fail "$1"; }
pyhelp(){ __ex=$(ls $2 2>/dev/null | head -1); if [ -n "$__ex" ]; then echo -e "   ${BLUE}\$ $PY $__ex --help${NC}"; "$PY" "$__ex" --help >/dev/null 2>&1 && pass "$1" || fail "$1"; else skip "$1 (예제 없음: $2)"; fi; }
# runstage: 파이프라인 단계를 "실제로" 실행(로그 그대로 노출)하고 종료코드로 PASS/FAIL.
runstage(){ echo -e "   ${BLUE}\$ $2${NC}"; if eval "$2"; then pass "$1"; else __r=$?; fail "$1 (실행 실패 rc=$__r)"; return 1; fi; }
# rt: run_tc 이식 — 환경 있으면 실제 추론 실행+종료코드 확인, 없으면(rc=77) SKIP.
rt(){ __t="$1"; __man="$2"; shift 2; echo -e "   ${BLUE}\$ _rt_resolve.py $*${NC}"; "$PY" "$SCRIPT_DIR/_rt_resolve.py" "$@" >/dev/null 2>&1; __rc=$?; if [ "$__rc" -eq 0 ]; then pass "$__t"; elif [ "$__rc" -eq 77 ]; then skipcmd "$__t" "$__man"; else fail "$__t (rc=$__rc)"; fi; }
# check_dx_engine: 활성 venv 의 pip list 에서 dx-engine 존재 확인.
#   없으면 "해당 내용을 밖으로 꺼내고"(=dx 관련 pip list 출력) 경고만 준다(FAIL 아님).
check_dx_engine(){
  if "$PY" -m pip list 2>/dev/null | grep -iqE 'dx[-_]engine'; then
    pass "② dx-engine 설치 확인 (활성 venv)"
  else
    warn "② dx-engine 미설치 — Python 예제 image 추론(--python --e2e-quick)이 SKIP/실패할 수 있음"
    echo -e "   ${YELLOW}↳ 현재 venv 의 dx 관련 pip 패키지:${NC}"
    __dx=$("$PY" -m pip list 2>/dev/null | grep -iE '^dx|dx[-_]' || true)
    if [ -n "$__dx" ]; then echo "$__dx" | sed 's/^/      /'; else echo "      (dx* 패키지 없음)"; fi
    echo -e "   ${YELLOW}↳ 설치: pip install <dx_engine wheel>  (또는 dx_engine 이 있는 공유 런타임 venv 사용)${NC}"
  fi
}
PY="python"; command -v python >/dev/null 2>&1 || PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then for v in venv/bin/activate .venv/bin/activate ../venv-dx-runtime/bin/activate; do [ -f "$v" ] && . "$v" && PY="python" && break; done; fi
if [ -z "${BUILD_DIR:-}" ]; then for d in bin build_x86_64/release/bin build_aarch64/release/bin build/bin; do [ -d "$d" ] && BUILD_DIR="$d" && break; done; fi
# 활성 venv 감지(activate 시 VIRTUAL_ENV 설정됨). 빌드/실행 명령은 필요시 env 로 override 가능.
VENV="${VIRTUAL_ENV:-}"
BUILD_CMD="${BUILD_CMD:-./build.sh --all}"
E2E_CMD="${E2E_CMD:-./run_tc.sh --python --e2e-quick}"
echo "PROJECT_ROOT=$PROJECT_ROOT | VENV=${VENV:-<none>} | BUILD_DIR=${BUILD_DIR:-<none>} | PY=$PY"
echo ""

# ── ① 정적 + 활성 인터프리터: Python 버전 요구(최소 3.8.10) 검증 ──
echo -e "${BLUE}[1] Python 버전/환경 요구 검증${NC}"
ex "venv 설치 스크립트" "scripts/install_python_and_venv.sh"
gr "최소 Python 3.8.10 명시" "scripts/install_python_and_venv.sh" "3.8.10"
gr "--venv_path 옵션" "scripts/install_python_and_venv.sh" "--venv_path"
shn "install_python_and_venv.sh 실행 파싱(bash -n)" "scripts/install_python_and_venv.sh"
pyshow "활성 python 최소버전(3.8.10) 충족" \
  "import sys;v=sys.version_info;print('python '+sys.version.split()[0]+'  (venv=${VENV:-none})');assert v[:3]>=(3,8,10),f'need>=3.8.10, got {sys.version.split()[0]}'"
echo ""

# ── ② 시나리오: 활성 venv 면 그 python 으로 빌드 → dx-engine 확인 → --e2e-short ──
if [ -n "$VENV" ]; then
  echo -e "${BLUE}[2] 활성 venv 시나리오 → 이 python 으로 dx_app 빌드 → dx-engine 확인 → Python 예제 image 추론${NC}"
  echo -e "   ${YELLOW}※ 활성 venv($VENV) 감지: 빌드/추론을 자동 진행합니다 (수 분·NPU 소요)${NC}"
  # ① 활성 venv 의 python 으로 dx_app 빌드 (pybind11 바인딩이 이 python 버전에 묶임)
  runstage "① dx_app 빌드 (활성 venv python: $PY)" "$BUILD_CMD"
  # ② dx-engine 확인 (없으면 pip list 노출 + 경고, 그래도 계속)
  check_dx_engine
  # ③ Python 예제 image 추론 (--python --e2e-quick)
  runstage "③ ${E2E_CMD} (Python 예제 image 추론)" "$E2E_CMD"
else
  echo -e "${BLUE}[2] venv 미활성 → 경량 검증만 (시나리오는 venv activate 후 재실행)${NC}"
  pyhelp "현재 Python 환경에서 예제 기동(--help→exit 0)" "src/python_example/*/*/*_sync.py"
  rt "현재 Python 환경 예제 실추론" "venv+빌드+NPU: python <task>/<model>/*_sync.py --model <m>.dxnn --image <img>" py-img
  skipcmd "활성 venv 시나리오(빌드+dx-engine확인+Python image 추론)" \
    "원하는 python venv activate 후 재실행:  source <venv>/bin/activate && bash tests/req_test/test_525.sh"
fi
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP/WARN=$S${NC}"
exit $F
