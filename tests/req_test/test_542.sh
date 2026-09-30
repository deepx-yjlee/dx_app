#!/bin/bash
# ▼ SDKREQ-542 — 모델 레지스트리 및 벤치마킹 (Linux)
#   model_registry.json에 고유 모델 347개 등록, bench_models.sh 존재·파싱 확인 및
#   레지스트리 모델로 태스크 카테고리별 대표 모델의 C++/Python Sync 추론을 검증한다.
#   --run / RUN_FULL=1 이면 bench_models.sh 로 "전체 모델 벤치마킹"을 실제 실행하고 결과 CSV 생성까지 확인.
#   (Windows 대응: test_543.bat)
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
# --run / RUN_FULL=1: 대표 추론이 아니라 bench_models.sh 로 "전체 모델 벤치마킹"을 실제 실행.
RUN_FULL="${RUN_FULL:-0}"; for a in "$@"; do [ "$a" = "--run" ] && RUN_FULL=1; done
BENCH_ARGS="${BENCH_ARGS:---lang both --loops 1}"   # 범위 조정 예: BENCH_ARGS='--lang cpp --filter yolov8'
echo "PROJECT_ROOT=$PROJECT_ROOT | BUILD_DIR=${BUILD_DIR:-<none>} | RUN_FULL=$RUN_FULL | PY=$PY"
echo ""
ex "model_registry.json" "config/model_registry.json"
# 행(row) 수가 아니라 고유 dxnn 파일 수를 센다: model_registry.json 은 같은 .dxnn 을
#   두 개의 model_name 별칭으로 등록할 수 있어(예: deitbase384 / deit_base384_distilled 가
#   모두 deit-b_384x384.dxnn) len(d) 는 348 이지만 실제 모델은 347 개다.
#   347 이 단일 기준값 — scripts/modelzoo_manifest.json 엔트리 수와
#   test_527.sh 의 EXPECTED_MODELS(assets/models/*.dxnn 다운로드 수)와 일치한다.
pyc "고유 등록 모델 347개" "import json;d=json.load(open('config/model_registry.json',encoding='utf-8'));n=len({e['dxnn_file'] for e in d});assert n==347,n"
ex "bench_models.sh" "scripts/bench_models.sh"
# 실행: 벤치 스크립트가 문법 오류 없이 기동되는지(bash -n)
shn "bench_models.sh 실행 파싱(bash -n)" "scripts/bench_models.sh"
# run_tc 이식: 레지스트리 모델로 실제 Sync 추론이 동작하는지 확인 (태스크 카테고리마다 대표 1개씩 — C++/Python 모두)
rt "레지스트리 모델 Sync 추론 (C++, 태스크별)" "NPU: ./scripts/bench_models.sh --lang cpp --loops 1" cpp-img --per-task
rt "레지스트리 모델 Sync 추론 (Python, 태스크별)" "NPU+dx_engine: ./scripts/bench_models.sh --lang py --loops 1" py-img --per-task
# 실제 실행(--run): bench_models.sh 로 전체 모델 벤치마킹을 돌리고 결과 CSV 생성까지 확인
if [ "$RUN_FULL" = "1" ]; then
  if [ -z "${BUILD_DIR:-}" ]; then
    skipcmd "전체 모델 벤치마킹(--run)" "빌드 필요: ./build.sh --all (bin 없음)"
  else
    __bout="logs/req542_bench"; rm -rf "$__bout"
    echo -e "   ${BLUE}\$ ./scripts/bench_models.sh $BENCH_ARGS --output-dir $__bout${NC}"
    ./scripts/bench_models.sh $BENCH_ARGS --output-dir "$__bout"; __rc=$?
    __csv=$(find "$__bout" -name results.csv 2>/dev/null | head -1)
    if [ "$__rc" -eq 0 ] && [ -n "$__csv" ]; then
      pass "전체 모델 벤치마킹 실행 + CSV 생성"
      echo -e "   ${BLUE}↳ CSV $(( $(wc -l < "$__csv") - 1 ))개 모델 결과: $__csv${NC}"
    else
      fail "전체 모델 벤치마킹 (rc=$__rc, CSV=${__csv:-없음})"
    fi
  fi
else
  skipcmd "전체 모델 Sync/Async 벤치 + CSV(--run)" "RUN_FULL=1 bash tests/req_test/test_542.sh (또는 --run) — ./scripts/bench_models.sh $BENCH_ARGS"
fi
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
