#!/bin/bash
# ▼ SDKREQ-523 — x86-64 / aarch64 네이티브 빌드·실행 (Linux)
#   [요구사항] dx_app 은 x86-64 환경 "또는" aarch64 환경에서 (크로스컴파일이 아니라)
#     각 아키텍처의 네이티브 환경에서 다음 파이프라인을 그대로 수행할 수 있어야 한다:
#         ① ./install.sh   (의존성/OpenCV≥4.2.0/툴체인 설치)
#         ② ./build.sh     (호스트 arch 네이티브 빌드 → bin/*_sync)
#         ③ ./setup.sh     (모델 .dxnn + 테스트 미디어 다운로드)
#         ④ ./run_tc.sh    (pytest 로 예제 실행/추론 검증)
#   즉 "x86_64 호스트에서 위 4단계", "aarch64 호스트에서 위 4단계"가 각각 성립해야 한다.
#   (크로스컴파일 --arch <other> 은 별도 케이스이며 여기서 요구하는 대상이 아니다.)
#   [검증] ① 4단계 스크립트 존재 + build.sh 가 uname -m 으로 호스트 arch 를 네이티브
#            선택하고 x86_64·aarch64 툴체인이 "둘 다" 존재(=두 arch 모두 빌드 타깃)함을 정적 확인
#          ② 현재 호스트 arch 에서 4단계 스크립트가 문법상 실행 가능한지(bash -n) +
#             네이티브 빌드 산출물이 있으면 run_tc 경로(pytest)로 실제 추론까지 되는지 확인
#   테스트 불가: "다른" arch 의 네이티브 빌드는 그 arch 장비에서 동일 스크립트로 수행(수동 안내).
#   (Windows 대응: test_524.bat)
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
skipcmd(){ skip "$1"; echo -e "   ${YELLOW}↳ 수동:${NC} $2"; }
# ── 실행 검증 헬퍼 (run_tc 방식: 실제 실행 후 종료코드 확인) ──
shn(){ bash -n "$2" 2>/dev/null && pass "$1 ($2)" || fail "$1 (문법오류: $2)"; }
# rt: run_tc 이식 — 환경 있으면 실제 추론 실행+종료코드 확인, 없으면(rc=77) SKIP.
rt(){ __t="$1"; __man="$2"; shift 2; echo -e "   ${BLUE}\$ _rt_resolve.py $*${NC}"; "$PY" "$SCRIPT_DIR/_rt_resolve.py" "$@" >/dev/null 2>&1; __rc=$?; if [ "$__rc" -eq 0 ]; then pass "$__t"; elif [ "$__rc" -eq 77 ]; then skipcmd "$__t" "$__man"; else fail "$__t (rc=$__rc)"; fi; }
# runstage: 파이프라인 단계를 "실제로" 실행하고(로그 그대로 노출) 종료코드로 PASS/FAIL.
#   RUN_FULL=1 (또는 --run) 일 때만 호출. install/build/setup/run_tc 는 무겁고(수 분·수 GB)
#   부작용이 크며(sudo apt·네트워크) NPU/네이티브 툴체인이 필요하므로 기본값에선 실행하지 않는다.
runstage(){ echo -e "   ${BLUE}\$ $2${NC}"; if eval "$2"; then pass "$1"; else __r=$?; fail "$1 (실행 실패 rc=$__r)"; return 1; fi; }
# RUN_FULL=1 환경변수 또는 --run 인자로 실제 파이프라인 실행 모드 진입
RUN_FULL="${RUN_FULL:-0}"; for a in "$@"; do [ "$a" = "--run" ] && RUN_FULL=1; done
PY="python"; command -v python >/dev/null 2>&1 || PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then for v in venv/bin/activate .venv/bin/activate ../venv-dx-runtime/bin/activate; do [ -f "$v" ] && . "$v" && PY="python" && break; done; fi
# 호스트 아키텍처(네이티브) 감지 — build.sh 와 동일 규칙(uname -m, arm64→aarch64)
HOST_ARCH="$(uname -m)"; [ "$HOST_ARCH" = "arm64" ] && HOST_ARCH="aarch64"
if [ -z "${BUILD_DIR:-}" ]; then for d in bin "build_${HOST_ARCH}/release/bin" build_x86_64/release/bin build_aarch64/release/bin build/bin; do [ -d "$d" ] && BUILD_DIR="$d" && break; done; fi
echo "PROJECT_ROOT=$PROJECT_ROOT | HOST_ARCH=$HOST_ARCH | BUILD_DIR=${BUILD_DIR:-<none>} | PY=$PY"
echo ""

# ── ① 정적: 네이티브 파이프라인 4단계 스크립트 + 두 arch 모두 빌드 타깃임을 확인 ──
echo -e "${BLUE}[1] 네이티브 파이프라인(install→build→setup→run_tc) 및 arch 지원 정적 검증${NC}"
ex "① install.sh (의존성 설치)"      "install.sh"
ex "② build.sh (네이티브 빌드)"       "build.sh"
ex "③ setup.sh (모델/미디어 다운로드)" "setup.sh"
ex "④ run_tc.sh (pytest 실행/추론)"   "run_tc.sh"
# build.sh 가 호스트 arch 를 자동 감지(네이티브)하고 --arch 로 명시도 가능
gr "build.sh 호스트 arch 자동 감지(네이티브)" "build.sh" "target_arch=\$(uname -m)"
gr "build.sh --arch 옵션(x86_64/aarch64)"     "build.sh" "--arch"
# x86_64·aarch64 툴체인이 둘 다 존재해야 "두 아키텍처 모두" 네이티브 빌드 타깃이 됨
ex "x86_64 툴체인(=x86-64 네이티브 빌드 타깃)"  "cmake/toolchain.x86_64.cmake"
ex "aarch64 툴체인(=aarch64 네이티브 빌드 타깃)" "cmake/toolchain.aarch64.cmake"
# 두 arch 공통 최소 요구: OpenCV ≥ 4.2.0
gr "OpenCV 최소 4.2.0"                "install.sh" "4.2.0"
echo ""

# ── ② 실행: 현재 호스트 arch 에서 4단계가 실제로 성립하는지 ──
echo -e "${BLUE}[2] 현재 호스트($HOST_ARCH)에서 네이티브 파이프라인 실행 검증${NC}"
# 4단계 스크립트가 문법상 실행 가능한지(bash -n) — 파싱 실패면 이 arch 에서 파이프라인이 깨짐
shn "① install.sh 실행 파싱(bash -n)" "install.sh"
shn "② build.sh 실행 파싱(bash -n)"   "build.sh"
shn "③ setup.sh 실행 파싱(bash -n)"   "setup.sh"
shn "④ run_tc.sh 실행 파싱(bash -n)"  "run_tc.sh"

if [ "$RUN_FULL" = "1" ]; then
  # ▶ 실제 실행 모드(RUN_FULL=1 / --run): 4단계를 순차로 진짜 실행하고 종료코드로 판정.
  #   한 단계라도 실패하면 다음 단계는 무의미하므로 중단하고 나머지는 SKIP 처리한다.
  echo -e "${YELLOW}[FULL] RUN_FULL=1 → 파이프라인 4단계를 실제 실행합니다 (수 분·수 GB·네트워크·NPU 소요)${NC}"
  if   ! runstage "① ./install.sh 실제 실행"          "./install.sh"; then skip "② build.sh (앞 단계 실패로 중단)"; skip "③ setup.sh (중단)"; skip "④ run_tc.sh (중단)";
  elif ! runstage "② ./build.sh 실제 빌드"            "./build.sh --type Release --all"; then skip "③ setup.sh (앞 단계 실패로 중단)"; skip "④ run_tc.sh (중단)";
  elif ! runstage "③ ./setup.sh 실제 모델/미디어 다운로드" "./setup.sh --all"; then skip "④ run_tc.sh (앞 단계 실패로 중단)";
  else       runstage "④ ./run_tc.sh 실제 실행/추론"      "./run_tc.sh --e2e-short"; fi
else
  # ▶ 기본(경량) 모드: 무거운 실행은 하지 않고, 이미 존재하는 산출물로만 실추론 확인.
  #   실제 4단계 실행은 위험/고비용이라 옵트인. 실행하려면:  RUN_FULL=1 bash test_523.sh
  if [ -n "${BUILD_DIR:-}" ] && ls "$BUILD_DIR"/*_sync >/dev/null 2>&1; then
    pass "② 네이티브 빌드 산출물 존재 ($HOST_ARCH: $BUILD_DIR/*_sync)"
  else
    skipcmd "② 네이티브 빌드 산출물 ($HOST_ARCH)" "이 arch 장비에서: ./install.sh && ./build.sh --type Release --all"
  fi
  rt "③④ setup 모델+run_tc 실추론(호스트 $HOST_ARCH)" \
     "이 arch 장비에서 전체 파이프라인: ./install.sh && ./build.sh --type Release --all && ./setup.sh --all && ./run_tc.sh --e2e-short" \
     cpp-img
  echo -e "   ${YELLOW}↳ 4단계를 실제로 실행하려면:${NC} RUN_FULL=1 bash tests/req_test/test_523.sh  (또는 --run)"
fi

# "다른" 아키텍처의 네이티브 빌드는 그 arch 장비에서 동일 스크립트로 수행(크로스컴파일 아님)
if [ "$HOST_ARCH" = "x86_64" ]; then OTHER="aarch64"; else OTHER="x86_64"; fi
skipcmd "$OTHER 네이티브 파이프라인(해당 arch 장비 필요)" \
        "$OTHER 장비에서 동일하게: ./install.sh && ./build.sh --type Release --all && ./setup.sh --all && ./run_tc.sh --e2e-short"
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
