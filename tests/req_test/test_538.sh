#!/bin/bash
# ▼ SDKREQ-538 — 독립(standalone) 모델 패키지 추출 (Linux)
#   extract_model_package.sh의 --lang·--output-dir 옵션과 독립 C++ 패키지 추출 +
#   CMakeLists 생성이 실제로 동작하는지 검증한다.
#   추가로 같은 기능의 대화형 진입점인 dx_tool.sh extract 도 프롬프트에 stdin 을 주입해
#   비대화형으로 실행하여 C++/Python 추출과 prune/--no-prune 경로까지 검증한다.
#   --run / RUN_FULL=1 이면 추출된 패키지를 소스 트리 밖에서 cmake+build 하여 "진짜 독립적으로
#   빌드되는지"까지 확인한다(cmake+OpenCV+dxrt 필요).
#   (Windows 대응: test_539.bat — SLN 추출)
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
# runstage: 단계를 "실제로" 실행(로그 노출)하고 종료코드로 PASS/FAIL.
runstage(){ echo -e "   ${BLUE}\$ $2${NC}"; if eval "$2"; then pass "$1"; else __r=$?; fail "$1 (실행 실패 rc=$__r)"; return 1; fi; }
PY="python"; command -v python >/dev/null 2>&1 || PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then for v in venv/bin/activate .venv/bin/activate ../venv-dx-runtime/bin/activate; do [ -f "$v" ] && . "$v" && PY="python" && break; done; fi
if [ -z "${BUILD_DIR:-}" ]; then for d in bin build_x86_64/release/bin build_aarch64/release/bin build/bin; do [ -d "$d" ] && BUILD_DIR="$d" && break; done; fi
# --run / RUN_FULL=1: 추출한 standalone 패키지를 실제로 cmake+build 해서 단독 빌드되는지 확인
RUN_FULL="${RUN_FULL:-0}"; for a in "$@"; do [ "$a" = "--run" ] && RUN_FULL=1; done
DXRT_HINT="${DXRT_INSTALLED_DIR:-/usr/local}"   # 추출 패키지 cmake 시 dxrt 힌트
echo "PROJECT_ROOT=$PROJECT_ROOT | BUILD_DIR=${BUILD_DIR:-<none>} | RUN_FULL=$RUN_FULL | PY=$PY"
echo ""
ex "extract_model_package.sh" "scripts/extract_model_package.sh"
gr "--lang 옵션" "scripts/extract_model_package.sh" "--lang"
gr "--output-dir 옵션" "scripts/extract_model_package.sh" "--output-dir"
shn "extract_model_package.sh 실행 파싱(bash -n)" "scripts/extract_model_package.sh"
# 실행: 실제로 독립 패키지를 추출하고 CMakeLists 가 생성되는지(NPU 불필요, 파일 복사)
OUT="${TMPDIR:-/tmp}/req538_out"; rm -rf "$OUT"
MODELD=$(ls -d src/cpp_example/object_detection/*/ 2>/dev/null | head -1); MODELB=$(basename "$MODELD")
run "독립 패키지 추출 + CMakeLists 생성" "./scripts/extract_model_package.sh object_detection/$MODELB --lang cpp --output-dir \"$OUT\" >/dev/null 2>&1; ls \"$OUT\"/cpp/object_detection/*/CMakeLists.txt >/dev/null 2>&1"
# Family export writes <task>/<family>/<variant>/<variant>_sync.cpp. Count must
# match the source tree so a new variant cannot be dropped from the package.
if [ -n "$MODELB" ]; then
  __src_sync=$(find "src/cpp_example/object_detection/$MODELB" -mindepth 2 -maxdepth 2 -name '*_sync.cpp' | wc -l | tr -d ' ')
  __out_sync=$(find "$OUT/cpp/object_detection/$MODELB" -name '*_sync.cpp' ! -path '*/common/*' | wc -l | tr -d ' ')
  if [ "$__src_sync" -gt 0 ] && [ "$__src_sync" = "$__out_sync" ]; then
    pass "family export 가 variant sync 소스를 모두 포함 (src=$__src_sync)"
  else
    fail "family export variant 수 불일치 (src=$__src_sync export=$__out_sync)"
  fi
  VARIANTD=$(ls -d "src/cpp_example/object_detection/$MODELB"/*/ 2>/dev/null | head -1)
  VARIANTB=$(basename "$VARIANTD")
  VOUT="${TMPDIR:-/tmp}/req538_variant"; rm -rf "$VOUT"
  run "단일 variant 추출 (task/family/variant)" \
      "./scripts/extract_model_package.sh object_detection/$MODELB/$VARIANTB --lang both --output-dir \"$VOUT\" >/dev/null 2>&1; \
       test -f \"$VOUT/cpp/object_detection/$MODELB/$VARIANTB/CMakeLists.txt\" && \
       test -f \"$VOUT/py/object_detection/$MODELB/$VARIANTB/${VARIANTB}_sync.py\" && \
       test -f \"$VOUT/py/object_detection/$MODELB/$VARIANTB/${VARIANTB}_async.py\""
fi

# ── dx_tool.sh extract (대화형 래퍼) ─────────────────────────────────────────
# extract 는 extract_model_package.sh 직접 호출 외에 dx_tool.sh 의 서브커맨드/메뉴로도
# 노출된다. 래퍼 고유 로직(서브커맨드 디스패치, lang 선택, prune [Y/n] → --no-prune)이
# 실제로 동작하는지 프롬프트에 stdin 을 주입해 비대화형으로 검증한다(NPU 불필요, 파일 복사).
ex "dx_tool.sh" "scripts/dx_tool.sh"
gr "dx_tool extract 서브커맨드 디스패치" "scripts/dx_tool.sh" "extract|export) do_extract_model_package"
gr "dx_tool extract prune 프롬프트" "scripts/dx_tool.sh" "Prune unused common/ files?"
gr "dx_tool extract --no-prune 전달" "scripts/dx_tool.sh" "PRUNE_OPT=(--no-prune)"
shn "dx_tool.sh 실행 파싱(bash -n)" "scripts/dx_tool.sh"

# dxt: dx_tool.sh extract 의 프롬프트 4개에 stdin 을 순서대로 주입한다.
#   $1 lang(1=C++ / 2=Python / 3=Both)  $2 output-dir  $3 prune 응답('' = Y 기본 / n = --no-prune)
#   dx_tool.sh 는 set -e 라 extract_model_package.sh 실패가 종료코드로 전파된다.
#   단 stdin 이 EOF 로 끝나면 model-path 재입력 루프(_err "Model path is empty"; continue)가
#   무한 반복되므로 timeout 을 반드시 건다.
dxt(){ printf '%s\n%s\n%s\n%s\n' "$1" "object_detection/$MODELB" "$2" "$3" | timeout 300 bash ./scripts/dx_tool.sh extract; }
# nfiles: 추출된 패키지 common/ 의 실파일 수(prune 효과 비교용). $1 은 글롭이라 비인용으로 전개한다.
nfiles(){ find $1 -type f 2>/dev/null | wc -l | tr -d ' '; }

DXT="${TMPDIR:-/tmp}/req538_dxtool"; rm -rf "$DXT"
if [ -z "$MODELB" ]; then
  skip "dx_tool extract 실행 검증 (object_detection 예제 없음)"
elif ! command -v timeout >/dev/null 2>&1; then
  skipcmd "dx_tool extract 실행 검증" "timeout(coreutils) 필요 — 대화형 프롬프트 hang 방지용"
else
  run "dx_tool extract C++ 추출 + CMakeLists 생성(prune 기본)" \
      "dxt 1 \"$DXT/cpp_prune\" '' >/dev/null 2>&1; ls \"$DXT\"/cpp_prune/cpp/object_detection/*/CMakeLists.txt >/dev/null 2>&1"
  # Entries are <task>/<family>/<variant>/<variant>_sync.py, not family/<script>.
  run "dx_tool extract Python 추출" \
      "dxt 2 \"$DXT/pylang\" '' >/dev/null 2>&1; ls \"$DXT\"/pylang/py/object_detection/*/*/*_sync.py >/dev/null 2>&1"
  run "dx_tool extract --no-prune 전체 common/ 복사" \
      "dxt 1 \"$DXT/cpp_noprune\" n >/dev/null 2>&1; ls \"$DXT\"/cpp_noprune/cpp/object_detection/*/CMakeLists.txt >/dev/null 2>&1"
  # prune 이 실제로 common/ 을 줄였는지: pruned < no-prune 이어야 한다(기본이 prune 이므로
  # 이 비교가 깨지면 prune 프롬프트가 --no-prune 을 잘못 전달하고 있다는 뜻)
  __npc=$(nfiles "$DXT/cpp_noprune/cpp/object_detection/*/common")
  __prc=$(nfiles "$DXT/cpp_prune/cpp/object_detection/*/common")
  if [ "$__npc" -gt 0 ] && [ "$__prc" -gt 0 ] && [ "$__prc" -lt "$__npc" ]; then
    pass "dx_tool extract prune 이 common/ 축소 (prune=$__prc < no-prune=$__npc)"
  else
    fail "dx_tool extract prune 이 common/ 축소 (prune=$__prc / no-prune=$__npc)"
  fi
fi

# sabuild: 추출 패키지를 소스 트리 밖에서 cmake+build 해서 *_sync 가 나오는지 확인한다.
#   $1 제목  $2 패키지 디렉터리(빈 값 = 추출 실패 → SKIP)  $3 빌드 로그 파일
#   실패 원인(dxrt/OpenCV/prune 으로 지워진 소스 등)이 드러나도록 로그를 남기고 실패 시 tail 출력.
sabuild(){
  local title="$1" pkg="$2" blog="$3"
  if [ -z "$pkg" ]; then skip "$title (추출 실패)"; return; fi
  if ! command -v cmake >/dev/null 2>&1; then
    skipcmd "$title" "cmake 필요(+OpenCV+dxrt): apt install cmake"; return
  fi
  : > "$blog"
  echo -e "   ${BLUE}\$ cmake -S \"$pkg\" -B \"$pkg/build\" -DDXRT_INSTALLED_DIR=\"$DXRT_HINT\" && cmake --build \"$pkg/build\" -j${NC}"
  if cmake -S "$pkg" -B "$pkg/build" -DDXRT_INSTALLED_DIR="$DXRT_HINT" >>"$blog" 2>&1 \
     && cmake --build "$pkg/build" -j >>"$blog" 2>&1 \
     && find "$pkg/build" -maxdepth 2 -type f -name '*_sync' | grep -q .; then
    pass "$title → *_sync 생성"
  else
    fail "$title"
    echo -e "   ${YELLOW}↳ 빌드 로그(마지막 30줄, 전체: $blog):${NC}"
    tail -30 "$blog" 2>/dev/null | sed 's/^/      /'
  fi
}

# 실제 실행(--run): 추출 패키지를 소스 트리 밖에서 cmake+build → 진짜 독립 빌드되는지 확인(OpenCV+dxrt 필요)
if [ "$RUN_FULL" = "1" ]; then
  # ls 가 비면 dirname 이 "." 를 내놓아 소스 트리를 빌드하려 들므로, CMakeLists 경로를 먼저 잡는다
  __cml=$(ls "$OUT"/cpp/object_detection/*/CMakeLists.txt 2>/dev/null | head -1)
  sabuild "추출 패키지 단독 cmake+build ($MODELB)" \
          "${__cml:+$(dirname "$__cml")}" "${TMPDIR:-/tmp}/req538_build.log"
  # dx_tool extract 로 추출한 pruned 패키지도 단독 빌드되는지 — prune 이 빌드에 필요한
  # common/ 파일까지 지웠다면 여기서 컴파일/링크 에러로 드러난다(과거 pthread 누락 결함과 동종).
  __dcml=$(ls "$DXT"/cpp_prune/cpp/object_detection/*/CMakeLists.txt 2>/dev/null | head -1)
  sabuild "dx_tool extract pruned 패키지 단독 cmake+build ($MODELB)" \
          "${__dcml:+$(dirname "$__dcml")}" "${TMPDIR:-/tmp}/req538_dxtool_build.log"
else
  skipcmd "추출 폴더 단독 빌드/실행(--run)" "RUN_FULL=1 bash tests/req_test/test_538.sh (또는 --run) — cmake+OpenCV+dxrt 로 소스 트리 밖 단독 빌드(extract_model_package.sh + dx_tool pruned 양쪽)"
fi
echo ""
echo -e "결과: ${GREEN}PASS=$P${NC}  ${RED}FAIL=$F${NC}  ${YELLOW}SKIP=$S${NC}"
exit $F
