#!/bin/bash
# =============================================================================
# run_all.sh — run every requirement test (tests/req_test/test_*.sh) at once
#              and print one aggregate PASS/FAIL/SKIP summary.
#
# Each test_<N>.sh self-reports "결과: PASS=.. FAIL=.. SKIP=.." and exits with
# a code equal to its FAIL count. This wrapper just runs them all and tallies.
#
# Usage:
#   tests/req_test/run_all.sh                 # run all test_*.sh
#   tests/req_test/run_all.sh 517 519 534     # run only these requirement numbers
#   SHOW_FAIL=1 tests/req_test/run_all.sh     # also print full output of failing scripts
#
# Exit code: number of scripts that reported at least one FAIL (0 = all clean).
# (Windows: run tests\req_test\run_all.bat, which aggregates the test_<N>.bat
#  files the same way; this wrapper is Linux/bash.)
#
# 각 test_<N>.sh 는 정적 검증(소스/옵션 존재)과 실행 검증(run_tc 방식: 실제
# 실행 후 종료코드 확인)을 함께 수행한다. NPU/장치/네트워크/네이티브 빌드가
# 있어야만 가능한 항목만 [SKIP] 으로 남긴다.
# =============================================================================
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
G='\033[0;32m'; R='\033[0;31m'; Y='\033[1;33m'; B='\033[1m'; NC='\033[0m'

shopt -s nullglob
scripts=("$SCRIPT_DIR"/test_*.sh)

# Optional filter: keep only the requirement numbers passed as args.
if [ "$#" -gt 0 ]; then
    sel=()
    for n in "$@"; do
        if [ -f "$SCRIPT_DIR/test_${n}.sh" ]; then
            sel+=("$SCRIPT_DIR/test_${n}.sh")
        else
            printf "%b\n" "${Y}[skip]${NC} test_${n}.sh not found" >&2
        fi
    done
    scripts=("${sel[@]}")
fi

# Sort by filename for stable ordering.
IFS=$'\n' scripts=($(printf '%s\n' "${scripts[@]}" | sort)); unset IFS

if [ "${#scripts[@]}" -eq 0 ]; then
    echo "No matching test_*.sh scripts found in $SCRIPT_DIR"
    exit 0
fi

gP=0; gF=0; gS=0
failed=()

printf "%b\n" "${B}Running ${#scripts[@]} requirement test(s) in ${SCRIPT_DIR#$PWD/} ...${NC}"
echo "------------------------------------------------------------------"

for s in "${scripts[@]}"; do
    name="$(basename "$s" .sh)"
    out="$(bash "$s" 2>&1)"
    code=$?

    # Strip ANSI colour codes first — the summary numbers are colour-wrapped
    # ("PASS=6<esc>  <esc>FAIL=0<esc>  ..."), so parse the de-coloured text.
    clean="$(printf '%s\n' "$out" | sed "s/$(printf '\033')\[[0-9;]*m//g")"
    sum="$(printf '%s\n' "$clean" \
        | grep -oE 'PASS=[0-9]+[[:space:]]+FAIL=[0-9]+[[:space:]]+SKIP=[0-9]+' \
        | tail -n1)"
    p=0; f=0; sk=0
    if [ -n "$sum" ]; then
        read -r p f sk < <(printf '%s' "$sum" | grep -oE '[0-9]+' | tr '\n' ' ')
    fi
    gP=$((gP + p)); gF=$((gF + f)); gS=$((gS + sk))

    # A script "failed" if it reported FAIL>0, or exited non-zero with no summary.
    if [ "$f" -gt 0 ] || { [ -z "$sum" ] && [ "$code" -ne 0 ]; }; then
        printf "  %b %-12s PASS=%-3s FAIL=%-3s SKIP=%-3s\n" "${R}[FAIL]${NC}" "$name" "$p" "$f" "$sk"
        failed+=("$name")
        if [ -n "${SHOW_FAIL:-}" ]; then
            printf '%s\n' "$out" | sed 's/^/        /'
        fi
    else
        printf "  %b %-12s PASS=%-3s FAIL=%-3s SKIP=%-3s\n" "${G}[ ok ]${NC}" "$name" "$p" "$f" "$sk"
    fi
done

echo "------------------------------------------------------------------"
printf "%b\n" "${B}TOTAL${NC}  PASS=${gP}  FAIL=${gF}  SKIP=${gS}   (scripts: ${#scripts[@]}, with failures: ${#failed[@]})"
if [ "${#failed[@]}" -gt 0 ]; then
    printf "%b %s\n" "${R}Failing scripts:${NC}" "${failed[*]}"
    printf "%b\n" "  (re-run one with full detail:  SHOW_FAIL=1 $0 <number>)"
fi

exit "${#failed[@]}"
