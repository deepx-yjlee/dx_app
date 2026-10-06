#!/bin/bash
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
#
# Smoke the two multi-model runtimes on the shipped sample scenarios.
#   pipeline  bin/multi_model_run          (image + named fuse)
#   graph     bin/multi_model_graph_{sync,async}
#
#   ./run_multi_model_demo.sh                         # interactive menu
#   ./run_multi_model_demo.sh --list
#   ./run_multi_model_demo.sh --check                 # every sample graph, no NPU
#   ./run_multi_model_demo.sh --all                   # --check, then each scenario
#   ./run_multi_model_demo.sh --scenario hand_cascade --runtime both
#   ./run_multi_model_demo.sh --scenario 1 --runtime graph --async

SCRIPT_DIR="$(realpath "$(dirname "$0")")"
# shellcheck source=scripts/color_env.sh
source "$SCRIPT_DIR/scripts/color_env.sh"
# shellcheck source=scripts/common_util.sh
source "$SCRIPT_DIR/scripts/common_util.sh"

DX_APP_PATH="$SCRIPT_DIR"
PIPELINE_DIR="$DX_APP_PATH/src/cpp_example/multi_model"
PY_PIPELINE_DIR="$DX_APP_PATH/src/python_example/multi_model"
GRAPH_DIR="$DX_APP_PATH/src/cpp_example/multi_model_graph"
MODEL_DIR="$DX_APP_PATH/assets/models"
OUT_DIR="$DX_APP_PATH/reports/dev/multi_model_demo"

# Scenario id, label, C++ pipeline, Python pipeline, graph, sample image.
# DMS keeps the CLIP crop-count pipeline and the head-pose graph as separate rows
# of the same scenario: they answer different questions.
SCENARIO_IDS=(hand_cascade logistics_volume dms)
SCENARIO_LABELS=(
    "Hand cascade (palm -> landmarks)"
    "Logistics volume (det + seg + depth)"
    "DMS (pipeline: face+pose+CLIP, graph: face+headpose)"
)
SCENARIO_PIPELINE=(
    "$PIPELINE_DIR/hand_cascade/pipeline.json"
    "$PIPELINE_DIR/logistics_volume/pipeline.json"
    "$PIPELINE_DIR/dms_clip/pipeline.json"
)
SCENARIO_PY_PIPELINE=(
    "$PY_PIPELINE_DIR/hand_cascade/pipeline.json"
    "$PY_PIPELINE_DIR/logistics_volume/pipeline.json"
    "$PY_PIPELINE_DIR/dms_clip/pipeline.json"
)
SCENARIO_GRAPH=(
    "$GRAPH_DIR/hand_cascade.json"
    "$GRAPH_DIR/logistics_volume.json"
    "$GRAPH_DIR/dms_headpose.json"
)
SCENARIO_IMAGE=(
    "$DX_APP_PATH/sample/img/sample_hand.jpg"
    "$DX_APP_PATH/sample/img/sample_people.jpg"
    "$DX_APP_PATH/sample/img/sample_face.jpg"
)
# In-cabin driver frame. Not shipped with the repo; used for DMS when present.
DMS_DRIVER_IMAGE="$DX_APP_PATH/sample/img/sample_driver_monitoring.png"
if [ -f "$DMS_DRIVER_IMAGE" ]; then
    SCENARIO_IMAGE[2]="$DMS_DRIVER_IMAGE"
fi

SCENARIO=""
RUNTIME=""
USE_ASYNC=0
DO_CHECK=0
DO_ALL=0
DO_LIST=0
FAIL_COUNT=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Check the shipped multi-model examples. Pipeline runs one sample image through
bin/multi_model_run (that binary also accepts --video). Graph runs the matching sample JSON through
bin/multi_model_graph_sync (or _async with --async).

Scenarios:
  0  hand_cascade       palm -> landmarks
  1  logistics_volume   det + seg + depth
  2  dms                pipeline dms_clip, graph dms_headpose

Options:
  --scenario ID|NUM   Scenario id or menu index (0-$(( ${#SCENARIO_IDS[@]} - 1 )))
  --runtime MODE      pipeline | graph | python | both
                      both = C++ pipeline + graph (default when --scenario is set)
  --async             Graph runtime uses multi_model_graph_async
  --check             Validate every sample graph (--check). Does not load the NPU.
  --all               --check, then each scenario as pipeline + graph sync
  --list              Print scenarios and sample graphs, then exit
  --output-dir DIR    Reports and saved frames (default: reports/dev/multi_model_demo)
  --models-dir DIR    .dxnn directory (default: assets/models)
  -h, --help          Show this help

No arguments opens the menu. A non-interactive shell with no arguments prints
this help and exits.
EOF
}

note() { print_colored "$1" "INFO"; }
ok() { print_colored "$1" "OK"; }
fail() { print_colored "$1" "FAIL"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

require_file() {
    local path="$1"
    local hint="$2"
    if [ ! -f "$path" ]; then
        fail "Missing $path"
        print_colored "  $hint" "HINT"
        return 1
    fi
    return 0
}

resolve_python() {
    local candidate
    for candidate in "$DX_APP_PATH/venv/bin/python3" \
                     "$DX_APP_PATH/.venv/bin/python3" \
                     "$DX_APP_PATH/../venv-dx-runtime/bin/python3"; do
        if [ -x "$candidate" ] && "$candidate" -c "import dx_engine" 2>/dev/null; then
            echo "$candidate"
            return 0
        fi
    done
    if python3 -c "import dx_engine" 2>/dev/null; then
        echo "python3"
        return 0
    fi
    return 1
}

scenario_index() {
    local key="$1"
    local i
    if [[ "$key" =~ ^[0-9]+$ ]] && [ "$key" -ge 0 ] && [ "$key" -lt ${#SCENARIO_IDS[@]} ]; then
        echo "$key"
        return 0
    fi
    for i in "${!SCENARIO_IDS[@]}"; do
        if [ "${SCENARIO_IDS[$i]}" = "$key" ]; then
            echo "$i"
            return 0
        fi
    done
    return 1
}

print_list() {
    local i graph
    echo "Scenarios:"
    for i in "${!SCENARIO_IDS[@]}"; do
        printf "  %d  %-18s %s\n" "$i" "${SCENARIO_IDS[$i]}" "${SCENARIO_LABELS[$i]}"
    done
    echo "Sample graphs:"
    shopt -s nullglob
    for graph in "$GRAPH_DIR"/*.json; do
        printf "  %s\n" "$(basename "$graph")"
    done
    shopt -u nullglob
}

ensure_runtime_path() {
    case ":${LD_LIBRARY_PATH:-}:" in
        *":$DX_APP_PATH/lib:"*) ;;
        *) export LD_LIBRARY_PATH="$DX_APP_PATH/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
    esac
}

run_pipeline_cpp() {
    local index="$1"
    local pipeline="${SCENARIO_PIPELINE[$index]}"
    local image="${SCENARIO_IMAGE[$index]}"
    local name="${SCENARIO_IDS[$index]}"
    local save="$OUT_DIR/${name}_pipeline.jpg"
    require_file "$DX_APP_PATH/bin/multi_model_run" "Build it with: ./build.sh --target multi_model_run" || return 1
    require_file "$pipeline" "C++ pipeline JSON is missing" || return 1
    require_file "$image" "Sample image is missing (./setup.sh)" || return 1
    mkdir -p "$OUT_DIR"
    note "pipeline  $name  $(basename "$image")"
    if "$DX_APP_PATH/bin/multi_model_run" \
            --pipeline "$pipeline" \
            --image "$image" \
            --models-dir "$MODEL_DIR" \
            --save "$save"; then
        ok "pipeline  $name  -> $save"
        return 0
    fi
    fail "pipeline  $name"
    return 1
}

run_pipeline_python() {
    local index="$1"
    local pipeline="${SCENARIO_PY_PIPELINE[$index]}"
    local image="${SCENARIO_IMAGE[$index]}"
    local name="${SCENARIO_IDS[$index]}"
    local save="$OUT_DIR/${name}_python.jpg"
    local py
    if ! py="$(resolve_python)"; then
        fail "python  $name"
        print_colored "  No interpreter with dx_engine. Run: ./install.sh && ./build.sh" "HINT"
        return 1
    fi
    require_file "$PY_PIPELINE_DIR/run_pipeline.py" "Python runner is missing" || return 1
    require_file "$pipeline" "Python pipeline JSON is missing" || return 1
    require_file "$image" "Sample image is missing (./setup.sh)" || return 1
    mkdir -p "$OUT_DIR"
    note "python    $name  ($py)"
    if "$py" "$PY_PIPELINE_DIR/run_pipeline.py" \
            --pipeline "$pipeline" \
            --image "$image" \
            --models-dir "$MODEL_DIR" \
            --save "$save"; then
        ok "python    $name  -> $save"
        return 0
    fi
    fail "python    $name"
    return 1
}

graph_binary() {
    if [ "$USE_ASYNC" -eq 1 ]; then
        echo "$DX_APP_PATH/bin/multi_model_graph_async"
    else
        echo "$DX_APP_PATH/bin/multi_model_graph_sync"
    fi
}

run_graph() {
    local index="$1"
    local graph="${SCENARIO_GRAPH[$index]}"
    local name="${SCENARIO_IDS[$index]}"
    local image="${SCENARIO_IMAGE[$index]}"
    local mode="sync"
    local bin report output
    local -a input_args=()
    [ "$USE_ASYNC" -eq 1 ] && mode="async"
    bin="$(graph_binary)"
    report="$OUT_DIR/${name}_graph_${mode}.json"
    output="$OUT_DIR/${name}_graph_${mode}.jpg"
    require_file "$bin" "Build it with: ./build.sh --target multi_model_graph_sync multi_model_graph_async" || return 1
    require_file "$graph" "Sample graph JSON is missing" || return 1
    # Feed the scenario image so pipeline and graph see the same frame.
    [ -f "$image" ] && input_args=(--input "$image")
    mkdir -p "$OUT_DIR"
    note "graph     $name  ($mode)  $(basename "$image")"
    if "$bin" \
            --graph "$graph" \
            "${input_args[@]}" \
            --model-dir "$MODEL_DIR" \
            --frames 1 \
            --report "$report" \
            --output "$output"; then
        ok "graph     $name  ($mode)  -> $report"
        return 0
    fi
    fail "graph     $name  ($mode)"
    return 1
}

check_all_graphs() {
    local graph bin status=0 count=0
    bin="$DX_APP_PATH/bin/multi_model_graph_sync"
    require_file "$bin" "Build it with: ./build.sh --target multi_model_graph_sync" || return 1
    shopt -s nullglob
    local graphs=( "$GRAPH_DIR"/*.json )
    shopt -u nullglob
    if [ ${#graphs[@]} -eq 0 ]; then
        fail "No sample graphs in $GRAPH_DIR"
        return 1
    fi
    note "Checking ${#graphs[@]} sample graphs (no NPU load)"
    for graph in "${graphs[@]}"; do
        count=$((count + 1))
        if "$bin" --check "$graph"; then
            ok "check  $(basename "$graph")"
        else
            fail "check  $(basename "$graph")"
            status=1
        fi
    done
    return "$status"
}

run_scenario() {
    local index="$1"
    local runtime="$2"
    case "$runtime" in
        pipeline) run_pipeline_cpp "$index" ;;
        python) run_pipeline_python "$index" ;;
        graph) run_graph "$index" ;;
        both)
            run_pipeline_cpp "$index" || true
            run_graph "$index" || true
            ;;
        *)
            fail "Unknown runtime '$runtime'"
            return 1
            ;;
    esac
}

choose_menu() {
    local choice runtime_choice
    print_list
    echo
    echo "Scenario [0-$(( ${#SCENARIO_IDS[@]} - 1 )), default 0]:"
    read -r choice
    SCENARIO="${choice:-0}"
    echo "Runtime: 1=pipeline  2=graph  3=python  4=both  [default 4]:"
    read -r runtime_choice
    case "${runtime_choice:-4}" in
        1|pipeline) RUNTIME="pipeline" ;;
        2|graph) RUNTIME="graph" ;;
        3|python) RUNTIME="python" ;;
        4|both) RUNTIME="both" ;;
        *)
            print_colored "Unknown runtime '$runtime_choice'" "ERROR"
            exit 1
            ;;
    esac
}

while [ $# -gt 0 ]; do
    case "$1" in
        --scenario)
            [ $# -ge 2 ] || { print_colored "--scenario needs a value" "ERROR"; exit 1; }
            SCENARIO="$2"
            shift 2
            ;;
        --runtime)
            [ $# -ge 2 ] || { print_colored "--runtime needs a value" "ERROR"; exit 1; }
            RUNTIME="$2"
            shift 2
            ;;
        --async) USE_ASYNC=1; shift ;;
        --check) DO_CHECK=1; shift ;;
        --all) DO_ALL=1; shift ;;
        --list) DO_LIST=1; shift ;;
        --output-dir)
            [ $# -ge 2 ] || { print_colored "--output-dir needs a value" "ERROR"; exit 1; }
            OUT_DIR="$2"
            shift 2
            ;;
        --models-dir)
            [ $# -ge 2 ] || { print_colored "--models-dir needs a value" "ERROR"; exit 1; }
            MODEL_DIR="$2"
            shift 2
            ;;
        -h|--help) usage; exit 0 ;;
        *)
            print_colored "Unknown option: $1" "ERROR"
            usage
            exit 1
            ;;
    esac
done

if [ "$DO_LIST" -eq 1 ]; then
    print_list
    exit 0
fi

if [ -z "$SCENARIO" ] && [ "$DO_CHECK" -eq 0 ] && [ "$DO_ALL" -eq 0 ]; then
    if [ ! -t 0 ]; then
        usage
        exit 2
    fi
    choose_menu
fi

if [ -n "$SCENARIO" ] && [ -z "$RUNTIME" ]; then
    RUNTIME="both"
fi

case "${RUNTIME:-}" in
    ""|pipeline|graph|python|both) ;;
    *)
        print_colored "Unknown runtime '$RUNTIME' (pipeline, graph, python, both)" "ERROR"
        exit 1
        ;;
esac

ensure_runtime_path
cd "$DX_APP_PATH" || exit 1

if [ "$DO_CHECK" -eq 1 ] || [ "$DO_ALL" -eq 1 ]; then
    check_all_graphs || true
fi

if [ "$DO_ALL" -eq 1 ]; then
    saved_async="$USE_ASYNC"
    USE_ASYNC=0
    for i in "${!SCENARIO_IDS[@]}"; do
        run_scenario "$i" both
    done
    USE_ASYNC="$saved_async"
elif [ -n "$SCENARIO" ]; then
    if ! index="$(scenario_index "$SCENARIO")"; then
        print_colored "Unknown scenario '$SCENARIO'. Use --list." "ERROR"
        exit 1
    fi
    run_scenario "$index" "$RUNTIME"
fi

echo
if [ "$FAIL_COUNT" -eq 0 ]; then
    ok "Multi-model demo finished with no failures"
    exit 0
fi
print_colored "$FAIL_COUNT step(s) failed" "ERROR"
exit 1
