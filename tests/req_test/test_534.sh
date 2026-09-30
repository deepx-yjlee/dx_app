#!/bin/bash
# ▼ SDKREQ-534 — 반복 추론(loop) 옵션 (Linux)
#   C++(-l/--loop)·Python(--loop) 반복 추론 옵션 노출을 확인하고, 실제 반복 추론이 안정 종료되는지 검증한다.
#   [실행 시나리오] classification async 대표 2개 → 이미지 input, --loop 10000 회 /
#                  object_detection async 대표 2개 → 비디오 input, --loop 20 회.
#   저사양 보드(ARM + 코어<=8, 또는 RT_LOW_SPEC=1)에서는 케이스당 300s 예산에 맞춰
#   --loop 을 자동 감량한다 — 요구사항 이탈이므로 감량 사유를 로그에 출력한다.
#   (Windows 대응: test_535.bat)
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
# rtloop: rt 와 동일하나 저사양 보드 자동 감량 사유([rt][loop-cut] 줄)를 그대로 노출한다.
#   요구사항(--loop 10000)에서 감량되면 결과는 PASS 로 두되 사유가 로그에 남아야 한다.
rtloop(){ __t="$1"; __man="$2"; shift 2; echo -e "   ${BLUE}\$ _rt_resolve.py $*${NC}"; __out=$("$PY" "$SCRIPT_DIR/_rt_resolve.py" "$@" 2>&1); __rc=$?; echo "$__out" | grep -F "[rt][loop-cut]" | sed "s/^ *//" | while IFS= read -r __l; do echo -e "   ${YELLOW}↓${NC} $__l"; done; if [ "$__rc" -eq 0 ]; then pass "$__t"; elif [ "$__rc" -eq 77 ]; then skipcmd "$__t" "$__man"; else fail "$__t (rc=$__rc)"; fi; }
PY="python"; command -v python >/dev/null 2>&1 || PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then for v in venv/bin/activate .venv/bin/activate ../venv-dx-runtime/bin/activate; do [ -f "$v" ] && . "$v" && PY="python" && break; done; fi
if [ -z "${BUILD_DIR:-}" ]; then for d in bin build_x86_64/release/bin build_aarch64/release/bin build/bin; do [ -d "$d" ] && BUILD_DIR="$d" && break; done; fi
echo "PROJECT_ROOT=$PROJECT_ROOT | BUILD_DIR=${BUILD_DIR:-<none>} | PY=$PY"
echo ""
gr "반복 추론 옵션 -l/--loop" "src/cpp_example/common/runner/async_detection_runner.hpp" "l, loop"
gr "Python --loop(기본1,값없으면2)" "src/python_example/common/runner/args.py" "--loop"
# 실행: Python 예제가 실제 기동되고 --loop 옵션을 노출하는지(--help→exit 0)
pyhelp "Python 예제 --loop 노출/기동(--help→exit 0)" "src/python_example/object_detection/*/*_sync.py"
__b=""; for __f in "$BUILD_DIR"/*_sync; do [ -x "$__f" ] && __b="$__f" && break; done; if [ -n "$__b" ]; then run "C++ 바이너리 동작(-h)" "$__b -h"; else skipcmd "C++ 바이너리 동작(-h)" "빌드 후: bin/*_sync -h"; fi
# run_tc 이식: 반복 추론(--loop)을 실제로 돌려 안정 종료되는지 확인
#   저사양 보드로 판별되면 _rt_resolve.py 가 케이스당 예산(300s)에 맞춰 loop 을 자동
#   감량한다(요구사항 이탈 → [rt][감량] 사유 출력, 결과는 PASS). RT_LOW_SPEC=1/0 로 강제 지정 가능.
#   classification async 대표 2개 → 이미지 input, --loop 10000
rtloop "Classification async 2개 × 이미지 --loop 10000 안정성(저사양 보드 자동 감량)" \
   "빌드+모델+NPU: bin/<cls>_async -m <m>.dxnn -i <img> -l 10000 --no-display (대표 2개)" \
   async-loop --task classification --input img --loop 10000 --count 2
#   object_detection async 대표 2개 → 비디오 input, --loop 20
rtloop "Object Detection async 2개 × 비디오 --loop 20 안정성" \
   "빌드+모델+NPU: bin/<od>_async -m <m>.dxnn -v <vid> -l 20 --no-display (대표 2개)" \
   async-loop --task object_detection --input vid --loop 20 --count 2
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
