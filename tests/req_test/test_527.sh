#!/bin/bash
# ▼ SDKREQ-527 — 모델/자산 다운로드 (Linux)
#   [요구사항] ./setup.sh --all 로 ModelZoo 의 모든 .dxnn 모델과 테스트 비디오가 받아져야 한다.
#   [검증] ① 다운로더/매니페스트/옵션이 존재하는지 정적 확인
#          ② setup --all 결과물이 실제로 준비됐는지 확인:
#             - assets/models 의 .dxnn 파일 개수가 기대값(기본 347)과 일치하는지
#             - assets/videos 에 테스트 비디오가 존재하는지
#   실행 모드(RUN_FULL=1 또는 --run): 위 ② 전에 ./setup.sh --all 을 실제로 실행해 다운로드한다.
#     (기본값은 네트워크·수 GB 부담 때문에 실행하지 않고, 이미 받아진 자산만 점검한다.)
#   기대 모델 개수는 EXPECTED_MODELS 로 override 가능(기본 347). manifest 엔트리 수는 참고로 출력.
#   (Windows 대응: test_528.bat)
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
run(){ echo -e "   ${BLUE}\$ $2${NC}"; eval "$2" >/dev/null 2>&1 && pass "$1" || fail "$1"; }
skipcmd(){ skip "$1"; echo -e "   ${YELLOW}↳ 수동:${NC} $2"; }
# ── 실행 검증 헬퍼 (run_tc 방식: 실제 실행 후 종료코드 확인) ──
shn(){ bash -n "$2" 2>/dev/null && pass "$1 ($2)" || fail "$1 (문법오류: $2)"; }
# runstage: 단계를 "실제로" 실행(로그 노출)하고 종료코드로 PASS/FAIL.
runstage(){ echo -e "   ${BLUE}\$ $2${NC}"; if eval "$2"; then pass "$1"; else __r=$?; fail "$1 (실행 실패 rc=$__r)"; return 1; fi; }
# rt: run_tc 이식 — 환경 있으면 실제 실행+종료코드, 없으면(rc=77) SKIP.
rt(){ __t="$1"; __man="$2"; shift 2; echo -e "   ${BLUE}\$ _rt_resolve.py $*${NC}"; "$PY" "$SCRIPT_DIR/_rt_resolve.py" "$@" >/dev/null 2>&1; __rc=$?; if [ "$__rc" -eq 0 ]; then pass "$__t"; elif [ "$__rc" -eq 77 ]; then skipcmd "$__t" "$__man"; else fail "$__t (rc=$__rc)"; fi; }
PY="python"; command -v python >/dev/null 2>&1 || PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then for v in venv/bin/activate .venv/bin/activate ../venv-dx-runtime/bin/activate; do [ -f "$v" ] && . "$v" && PY="python" && break; done; fi
# 설정값: 기대 모델 개수(override 가능), 자산 경로, 실제 실행 모드
EXPECTED_MODELS="${EXPECTED_MODELS:-347}"
MODEL_DIR="assets/models"
VIDEO_DIR="assets/videos"
RUN_FULL="${RUN_FULL:-0}"; for a in "$@"; do [ "$a" = "--run" ] && RUN_FULL=1; done
echo "PROJECT_ROOT=$PROJECT_ROOT | EXPECTED_MODELS=$EXPECTED_MODELS | RUN_FULL=$RUN_FULL | PY=$PY"
echo ""

# ── ① 정적: 다운로더/매니페스트/옵션 존재 ──
echo -e "${BLUE}[1] 다운로더/매니페스트/옵션 정적 검증${NC}"
ex "download_models.py" "scripts/download_models.py"
gr "모델 출력 경로 assets/models" "scripts/download_models.py" "assets"
ex "setup.sh" "setup.sh"
gr "--all 옵션" "setup.sh" "--all"
gr "--list 옵션" "setup.sh" "--list"
gr "--dry-run 옵션" "setup.sh" "--dry-run"
ex "ModelZoo manifest" "scripts/modelzoo_manifest.json"
# manifest 의 .dxnn 엔트리 수(참고): 다운로드 대상 총량
__man_n=$("$PY" -c "import json;print(sum(1 for e in json.load(open('scripts/modelzoo_manifest.json',encoding='utf-8')) if str(e.get('dxnn_url','')).endswith('.dxnn')))" 2>/dev/null)
echo -e "   ${BLUE}↳ manifest .dxnn 엔트리 수 = ${__man_n:-?}  (기대 다운로드 = $EXPECTED_MODELS)${NC}"
shn "setup.sh 실행 파싱(bash -n)" "setup.sh"
run "download_models.py --help→exit 0" "\"$PY\" scripts/download_models.py --help"
echo ""

# ── ② 실행: setup --all 결과물(모델 개수 / 비디오 존재) 확인 ──
echo -e "${BLUE}[2] setup --all 결과물 검증 (모델 $EXPECTED_MODELS개 + 테스트 비디오)${NC}"
if [ "$RUN_FULL" = "1" ]; then
  echo -e "   ${YELLOW}[FULL] RUN_FULL=1 → ./setup.sh --all 을 실제 실행합니다 (네트워크·수 GB 소요)${NC}"
  runstage "setup.sh --all 실제 다운로드" "./setup.sh --all"
else
  echo -e "   ${YELLOW}↳ 실제 다운로드까지 하려면:${NC} RUN_FULL=1 bash tests/req_test/test_527.sh  (또는 --run)"
fi

# 모델 개수: assets/models 의 .dxnn 파일 수가 기대값과 일치하는지
# 주의: assets/models 는 실제 저장소를 가리키는 symlink 일 수 있으므로 find -L 로 심링크를 따라간다.
#       (-L 없으면 symlink 된 디렉터리/파일을 건너뛰어 actual=0 으로 오탐)
if [ -d "$MODEL_DIR" ]; then
  __n=$(find -L "$MODEL_DIR" -type f -name '*.dxnn' 2>/dev/null | wc -l | tr -d ' ')
  echo -e "   ${BLUE}↳ expected=$EXPECTED_MODELS  actual=$__n  ($MODEL_DIR/*.dxnn, symlink 추적)${NC}"
  if [ "$__n" -eq "$EXPECTED_MODELS" ]; then pass "모델 $EXPECTED_MODELS개 다운로드 확인"
  else fail "모델 개수 불일치 (expected=$EXPECTED_MODELS actual=$__n)"; fi
else
  skipcmd "모델 $EXPECTED_MODELS개 다운로드 확인" "네트워크: ./setup.sh --all (또는 RUN_FULL=1 로 재실행) → $MODEL_DIR 생성"
fi

# 테스트 비디오: assets/videos 에 영상 파일이 존재하는지 (symlink 일 수 있으므로 find -L)
if [ -d "$VIDEO_DIR" ]; then
  __v=$(find -L "$VIDEO_DIR" -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.avi' -o -iname '*.mkv' -o -iname '*.webm' -o -iname '*.m4v' \) 2>/dev/null | wc -l | tr -d ' ')
  echo -e "   ${BLUE}↳ videos found=$__v  ($VIDEO_DIR, symlink 추적)${NC}"
  if [ "$__v" -gt 0 ]; then pass "테스트 비디오 존재 ($__v개 @ $VIDEO_DIR)"
  else fail "테스트 비디오 없음 ($VIDEO_DIR 이 비어있음)"; fi
else
  skipcmd "테스트 비디오 존재 확인" "네트워크: ./setup.sh --all → $VIDEO_DIR 생성"
fi
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
