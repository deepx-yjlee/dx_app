#!/bin/bash
# ▼ SDKREQ-519 — AI 태스크별 추론 결과 출력 포맷 (Linux)
#   [요구사항] C++ 예제는 태스크별 SyncRunner 로 추론 후 "정해진 포맷"으로 stdout 에 결과를 출력한다.
#     - Object Detection : [DET] class conf x1 y1 x2 y2 frame_w frame_h   (verbose=--show-log)
#     - Classification   : "Top predictions:" 상위 5개(클래스·신뢰도) + [CLS] 파이프라인 태그
#     - Pose Estimation  : [POSE] ...
#     - Instance Seg     : [ISEG] class conf x1 y1 x2 y2
#     - OBB / Face / Face Alignment / Hand Landmark / 3D Det : [OBB]/[FACE]/[ALIGN]/[HAND]/[3D]
#     - Semantic Seg·Depth·Embedding·Restoration(SR/Denoise/Enhance) : 결과가 "이미지" 라
#       stdout 텍스트 태그 없이 이미지 저장 → --show-log 시 "produces image-based ..." INFO 출력
#   [검증] ① 카테고리별 결과 출력 포맷 마커가 러너 소스에 존재하는지 정적 확인 (없으면 SKIP)
#          ② 카테고리마다 대표 예제 1개를 --show-log 로 실제 실행해 그 포맷 마커가 나오는지 확인
#             (_rt_resolve.py cpp-showlog --per-task — run_tc --e2e-short 의 "카테고리별 대표" 방식).
#             빌드/모델/NPU 없으면 SKIP.
#   테스트 불가: 실제 출력 "값" 정확성은 NPU+.dxnn 필요(포맷/코드경로 자체는 소스로 확인 가능).
#   (Windows 대응: test_520.bat)
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
#   $1 제목  $2 SKIP시 수동안내  $3.. resolver 인자(cpp-img/cpp-showlog/py-img/models-present)
rt(){ __t="$1"; __man="$2"; shift 2; echo -e "   ${BLUE}\$ _rt_resolve.py $*${NC}"; "$PY" "$SCRIPT_DIR/_rt_resolve.py" "$@"; __rc=$?; if [ "$__rc" -eq 0 ]; then pass "$__t"; elif [ "$__rc" -eq 77 ]; then skipcmd "$__t" "$__man"; else fail "$__t (rc=$__rc)"; fi; }
PY="python"; command -v python >/dev/null 2>&1 || PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then for v in venv/bin/activate .venv/bin/activate ../venv-dx-runtime/bin/activate; do [ -f "$v" ] && . "$v" && PY="python" && break; done; fi
if [ -z "${BUILD_DIR:-}" ]; then for d in bin build_x86_64/release/bin build_aarch64/release/bin build/bin; do [ -d "$d" ] && BUILD_DIR="$d" && break; done; fi
echo "PROJECT_ROOT=$PROJECT_ROOT | BUILD_DIR=${BUILD_DIR:-<none>} | PY=$PY"
echo ""

# ── ① 정적: 카테고리별 결과 출력 포맷 마커가 러너 소스에 존재하는지 (없으면 SKIP) ──
# grcat: $1 카테고리 라벨  $2 러너 파일명  $3 기대 출력 포맷 마커
grcat(){ __p="src/cpp_example/common/runner/$2";
  if grep -Fq -- "$3" "$__p" 2>/dev/null; then pass "출력포맷 $1  ('$3' @ $2)";
  else skip "출력포맷 $1  (마커 없음: '$3' @ $2)"; fi; }

# 태그형 (전용 러너, verbose=--show-log 게이트)
grcat "Object Detection"        sync_detection_runner.hpp      "[DET]"
grcat "Classification(Top-K)"   sync_classification_runner.hpp "Top predictions:"
grcat "Pose Estimation"         sync_pose_runner.hpp           "[POSE]"
grcat "Instance Segmentation"   sync_segmentation_runner.hpp   "[ISEG]"
grcat "OBB Detection"           sync_obb_runner.hpp            "[OBB]"
grcat "Face Detection"          sync_face_runner.hpp           "[FACE]"
grcat "Face Alignment"          sync_face_alignment_runner.hpp "[ALIGN]"
grcat "Hand Landmark"           sync_hand_landmark_runner.hpp  "[HAND]"
grcat "3D Object Detection"     sync_3d_object_detection_runner.hpp   "[3D]"
# 러너 재사용 (alias / include) — 출력 포맷은 재사용하는 러너의 것
grcat "Object Pose (→Pose)"        sync_pose_runner.hpp           "[POSE]"
grcat "Keypoint Detection (→Pose)" sync_pose_runner.hpp           "[POSE]"
grcat "Panoptic Driving (→Detection)" sync_detection_runner.hpp   "[DET]"
grcat "Hand Detection (→Face,[HAND])" sync_face_runner.hpp        "[HAND]"
grcat "Attribute Recog (→Classification)" sync_classification_runner.hpp "Top predictions:"
# image-based (텍스트 태그 없음 → 결과 이미지 저장, --show-log 시 produces image-based)
grcat "Semantic Seg(이미지 저장)"  sync_semantic_seg_runner.hpp   "produces image-based"
grcat "Depth Estimation(이미지)"   sync_depth_runner.hpp          "produces image-based"
grcat "Embedding(이미지)"          sync_embedding_runner.hpp      "produces image-based"
grcat "ReID (→Embedding, 이미지)"  sync_embedding_runner.hpp      "produces image-based"
grcat "Restoration/SR/Denoise/Enhance(이미지)" sync_restoration_runner.hpp "produces image-based"
# PPU: 모델별로 detection/face/pose 러너를 재사용 → 단일 출력 포맷 없음
skip "출력포맷 PPU (모델별 상이: detection→[DET] / face→[FACE] / pose→[POSE] 재사용)"

# ── ② 실행: 카테고리마다 대표 1개를 --show-log 로 실제 실행 → 출력 포맷 마커 확인 ──
# run_tc --e2e-short 처럼 카테고리별 대표 1개만. 마커 미정의 카테고리/실행대상 없음은 내부에서 스킵.
rt "카테고리별 --show-log 출력포맷 실동작 (대표 1개씩)" \
   "빌드+모델+NPU 후: bin/<model>_sync -i <img> --show-log --no-display  (참고: ./run_tc.sh --e2e-short)" \
   cpp-showlog --per-task

# 보조: Python 예제가 --show-log 옵션을 노출하고 실제 기동되는지(--help→exit 0)
gr "Python --show-log 옵션 존재" "src/python_example/common/runner/args.py" "--show-log"
pyhelp "Python 예제 실행 기동(--help→exit 0)" "src/python_example/object_detection/*/*_sync.py"
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
