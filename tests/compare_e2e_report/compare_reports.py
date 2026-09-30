#!/usr/bin/env python3
"""
E2E Performance Report Comparison Tool

Compares two CSV E2E performance reports and generates a comprehensive comparison
including metrics differences, side-by-side values, and regression detection.
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# CSV column name constants
COL_E2E_FPS = "E2E FPS"
COL_INFLIGHT_AVG = "Inflight Avg"
COL_INFLIGHT_MAX = "Inflight Max"

# Status label constants
STATUS_PASS = "✅ PASS"
STATUS_WARN = "⚠️ WARN"
STATUS_FAIL = "❌ FAIL"
STATUS_MD_FAIL = "❌ **FAIL**"  # bold variant used in comparison table rows

# FPS columns to compare (higher is better)
FPS_COLUMNS = [
    COL_E2E_FPS,
    "Read FPS",
    "Preprocess FPS",
    "Inference FPS",
    "Postprocess FPS",
]

# Key columns to identify unique rows
KEY_COLUMNS = ["Model", "Variant"]

def parse_fps_value(value: str) -> Optional[float]:
    """Parse FPS value, handling asterisk markers and empty values."""
    if not value or value.strip() == "":
        return None
    # Remove asterisk marker (indicates bottleneck)
    clean_value = value.replace("*", "").strip()
    try:
        return float(clean_value)
    except ValueError:
        return None

def load_csv(filepath: Path) -> dict:
    """Load CSV file and return dict keyed by (Task, Model, Variant)."""
    data = {}
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = tuple(row[col] for col in KEY_COLUMNS)
            data[key] = row
    return data

def calculate_change(baseline_val: Optional[float], current_val: Optional[float]) -> tuple:
    """Calculate absolute and percentage change. Returns (diff, pct_change, is_regression)."""
    if baseline_val is None or current_val is None:
        return None, None, False

    diff = current_val - baseline_val
    if baseline_val != 0:
        pct_change = (diff / baseline_val) * 100
    else:
        pct_change = 100.0 if current_val > 0 else 0.0

    # For FPS, lower is worse (regression)
    is_regression = diff < 0
    return diff, pct_change, is_regression

def format_fps_cell(baseline_val: Optional[float], current_val: Optional[float], diff: Optional[float], pct: Optional[float], threshold: float = 30.0, higher_is_worse: bool = False, show_threshold: bool = False) -> str:
    """Format FPS cell as: old / new (diff, %) with ❌ if failed.
    For FPS metrics (higher_is_worse=False): fail when pct < -threshold (decrease).
    For inflight metrics (higher_is_worse=True): fail when pct > +threshold (increase).
    If show_threshold=True, appends [threshold%] to the cell.
    """
    if baseline_val is None or current_val is None:
        return "-"
    sign = "+" if diff >= 0 else ""
    cell = f"{baseline_val:.1f}/{current_val:.1f} ({sign}{diff:.1f}, {sign}{pct:.1f}%)"
    if show_threshold:
        cell += f" [{threshold:.1f}%]"
    if pct is not None and (
        (higher_is_worse and pct > threshold) or
        (not higher_is_worse and pct < -threshold)
    ):
        return f"❌ {cell}"
    return cell

def get_status(pct: Optional[float], threshold: float, higher_is_worse: bool = False) -> str:
    """Get status based on percentage change.
    For FPS metrics (higher_is_worse=False): fail when pct < -threshold (decrease).
    For inflight metrics (higher_is_worse=True): fail when pct > +threshold (increase).
    """
    if pct is None:
        return "N/A"
    if (higher_is_worse and pct > threshold) or (not higher_is_worse and pct < -threshold):
        return STATUS_FAIL
    return STATUS_PASS

def shorten_variant(model: str, variant: str) -> str:
    """Shorten variant by removing model name prefix."""
    # Remove model name from beginning of variant
    if variant.lower().startswith(model.lower()):
        shortened = variant[len(model):].lstrip("_")
        return shortened if shortened else variant
    return variant

def _compute_inflight_cells(baseline_row: dict, current_row: dict, row_th: dict, show_threshold: bool = False) -> tuple:
    """Return (avg_cell, avg_pct, max_cell, max_pct) for async inflight metrics."""
    baseline_avg = parse_fps_value(baseline_row.get(COL_INFLIGHT_AVG, ""))
    current_avg = parse_fps_value(current_row.get(COL_INFLIGHT_AVG, ""))
    avg_diff, avg_pct, _ = calculate_change(baseline_avg, current_avg)
    avg_cell = format_fps_cell(baseline_avg, current_avg, avg_diff, avg_pct, row_th["inflight_avg"], higher_is_worse=True, show_threshold=show_threshold)

    baseline_max = parse_fps_value(baseline_row.get(COL_INFLIGHT_MAX, ""))
    current_max = parse_fps_value(current_row.get(COL_INFLIGHT_MAX, ""))
    max_diff, max_pct, _ = calculate_change(baseline_max, current_max)
    max_cell = format_fps_cell(baseline_max, current_max, max_diff, max_pct, row_th["inflight_max"], higher_is_worse=True, show_threshold=show_threshold)

    return avg_cell, avg_pct, max_cell, max_pct

def _compute_sync_fps_cells(baseline_row: dict, current_row: dict, row_th: dict, show_threshold: bool = False) -> tuple:
    """Return (fps_cells, sub_fail) for sync rows; fps_cells are plain formatted strings."""
    fps_cells = []
    sub_fail = False
    for col in FPS_COLUMNS:
        baseline_val = parse_fps_value(baseline_row.get(col, ""))
        current_val = parse_fps_value(current_row.get(col, ""))
        diff, pct, _ = calculate_change(baseline_val, current_val)
        fps_cells.append(format_fps_cell(baseline_val, current_val, diff, pct, row_th[col], show_threshold=show_threshold))
        if col != COL_E2E_FPS and pct is not None and pct < -row_th[col]:
            sub_fail = True
    return fps_cells, sub_fail

def _is_inflight_fail(avg_pct: Optional[float], max_pct: Optional[float], row_th: dict) -> bool:
    """Return True if any inflight metric exceeds its threshold."""
    return (
        (avg_pct is not None and avg_pct > row_th["inflight_avg"]) or
        (max_pct is not None and max_pct > row_th["inflight_max"])
    )


def _resolve_status_md(is_fail: bool, secondary_fail: bool) -> str:
    """Return the markdown status string from primary/secondary fail flags."""
    if is_fail:
        return STATUS_MD_FAIL
    if secondary_fail:
        return STATUS_WARN
    return STATUS_PASS


# Sync FPS column name → threshold.json key mapping
_SYNC_COL_TO_KEY = {
    COL_E2E_FPS: "e2e_fps",
    "Read FPS": "read_fps",
    "Preprocess FPS": "preprocess_fps",
    "Inference FPS": "inference_fps",
    "Postprocess FPS": "postprocess_fps",
}

def load_threshold_json(path: Path) -> dict:
    """Load thresholds from a JSON file.

    Expected format::

        {
          "global": {
            "async": {"e2e_fps": 10.0, "inflight_avg": 30.0, "inflight_max": 30.0},
            "sync":  {"e2e_fps": 10.0, "read_fps": 30.0, ...}
          },
          "specific": {
            "async": [{"model": "...", "variant": "...", "e2e_fps": 10.0, ...}],
            "sync":  [{"model": "...", "variant": "...", "e2e_fps": 10.0, ...}]
          }
        }

    Lookup priority (highest → lowest):
      1. specific entry matching (model, variant)
      2. specific entry matching (model, "")   — model-level wildcard
      3. global section values
      4. --threshold default float
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    specific: dict = {"async": {}, "sync": {}}
    for mode in ("async", "sync"):
        for entry in data.get("specific", {}).get(mode, []):
            key = (entry["model"], entry.get("variant", ""))
            specific[mode][key] = entry

    return {
        "global": data.get("global", {}),
        "specific": specific,
    }


def get_async_thresholds(th_map: dict, model: str, short_variant: str, default: float) -> dict:
    """Return per-row async thresholds (specific → global → default)."""
    keys = ("e2e_fps", "inflight_avg", "inflight_max")

    # 1. specific: exact (model, variant) then model-level wildcard
    specific = th_map.get("specific", {}).get("async", {})
    entry = specific.get((model, short_variant)) or specific.get((model, ""))

    # 2. global async section
    glob = th_map.get("global", {}).get("async", {})

    return {
        k: (entry.get(k) if entry and entry.get(k) is not None
            else glob.get(k, default))
        for k in keys
    }


def get_sync_thresholds(th_map: dict, model: str, short_variant: str, default: float) -> dict:
    """Return per-row sync thresholds keyed by FPS_COLUMNS (specific → global → default)."""
    # 1. specific: exact (model, variant) then model-level wildcard
    specific = th_map.get("specific", {}).get("sync", {})
    entry = specific.get((model, short_variant)) or specific.get((model, ""))

    # 2. global sync section
    glob = th_map.get("global", {}).get("sync", {})

    return {
        col: (entry.get(json_key) if entry and entry.get(json_key) is not None
              else glob.get(json_key, default))
        for col, json_key in _SYNC_COL_TO_KEY.items()
    }


# ---------------------------------------------------------------------------
# Row-building helpers (one row per report format, per async/sync section)
# ---------------------------------------------------------------------------

def _build_json_async_row(
    key: tuple, baseline_data: dict, current_data: dict,
    threshold: float, th_map: dict,
) -> dict:
    """Build a JSON report dict for one async key."""
    model, variant = key
    short_variant = shorten_variant(model, variant)
    baseline_row = baseline_data.get(key, {})
    current_row = current_data.get(key, {})
    row_th = get_async_thresholds(th_map, model, short_variant, threshold)

    baseline_fps = parse_fps_value(baseline_row.get(COL_E2E_FPS, ""))
    current_fps = parse_fps_value(current_row.get(COL_E2E_FPS, ""))
    diff, pct, _ = calculate_change(baseline_fps, current_fps)

    baseline_avg = parse_fps_value(baseline_row.get(COL_INFLIGHT_AVG, ""))
    current_avg = parse_fps_value(current_row.get(COL_INFLIGHT_AVG, ""))
    _, avg_pct, _ = calculate_change(baseline_avg, current_avg)

    baseline_max = parse_fps_value(baseline_row.get(COL_INFLIGHT_MAX, ""))
    current_max = parse_fps_value(current_row.get(COL_INFLIGHT_MAX, ""))
    _, max_pct, _ = calculate_change(baseline_max, current_max)

    fps_fail = pct is not None and pct < -row_th["e2e_fps"]
    if fps_fail:
        status = "FAIL"
    elif _is_inflight_fail(avg_pct, max_pct, row_th):
        status = "WARN"
    else:
        status = "PASS"
    return {
        "model": model, "variant": short_variant, "status": status,
        "e2e_fps": {"baseline": baseline_fps, "current": current_fps, "diff": diff,
                    "pct": round(pct, 2) if pct is not None else None},
        "inflight_avg": {"baseline": baseline_avg, "current": current_avg,
                         "pct": round(avg_pct, 2) if avg_pct is not None else None},
        "inflight_max": {"baseline": baseline_max, "current": current_max,
                         "pct": round(max_pct, 2) if max_pct is not None else None},
        "threshold": row_th,
    }


def _build_json_sync_row(
    key: tuple, baseline_data: dict, current_data: dict,
    threshold: float, th_map: dict,
) -> dict:
    """Build a JSON report dict for one sync key."""
    model, variant = key
    short_variant = shorten_variant(model, variant)
    baseline_row = baseline_data.get(key, {})
    current_row = current_data.get(key, {})
    row_th = get_sync_thresholds(th_map, model, short_variant, threshold)

    baseline_e2e = parse_fps_value(baseline_row.get(COL_E2E_FPS, ""))
    current_e2e = parse_fps_value(current_row.get(COL_E2E_FPS, ""))
    _, e2e_pct, _ = calculate_change(baseline_e2e, current_e2e)

    e2e_fail = e2e_pct is not None and e2e_pct < -row_th[COL_E2E_FPS]
    sub_fail = False
    fps_metrics = {}
    for col in FPS_COLUMNS:
        baseline_val = parse_fps_value(baseline_row.get(col, ""))
        current_val = parse_fps_value(current_row.get(col, ""))
        diff, pct, _ = calculate_change(baseline_val, current_val)
        fps_metrics[col] = {
            "baseline": baseline_val, "current": current_val, "diff": diff,
            "pct": round(pct, 2) if pct is not None else None,
        }
        if col != COL_E2E_FPS and pct is not None and pct < -row_th[col]:
            sub_fail = True

    if e2e_fail:
        status = "FAIL"
    elif sub_fail:
        status = "WARN"
    else:
        status = "PASS"
    return {"model": model, "variant": short_variant, "status": status,
            "fps": fps_metrics, "threshold": row_th}


def _prepare_async_row(
    key: tuple, baseline_data: dict, current_data: dict,
    threshold: float, th_map: dict,
) -> tuple:
    """Shared computation for async row builders. Returns
    (model, short_variant, pct, fps_cell, avg_cell, avg_pct, max_cell, max_pct, row_th)."""
    model, variant = key
    short_variant = shorten_variant(model, variant)
    baseline_row = baseline_data.get(key, {})
    current_row = current_data.get(key, {})
    row_th = get_async_thresholds(th_map, model, short_variant, threshold)

    baseline_fps = parse_fps_value(baseline_row.get(COL_E2E_FPS, ""))
    current_fps = parse_fps_value(current_row.get(COL_E2E_FPS, ""))
    diff, pct, _ = calculate_change(baseline_fps, current_fps)
    fps_cell = format_fps_cell(baseline_fps, current_fps, diff, pct, row_th["e2e_fps"], show_threshold=True)
    avg_cell, avg_pct, max_cell, max_pct = _compute_inflight_cells(baseline_row, current_row, row_th, show_threshold=True)
    return model, short_variant, pct, fps_cell, avg_cell, avg_pct, max_cell, max_pct, row_th


def _build_md_async_row(
    key: tuple, baseline_data: dict, current_data: dict,
    threshold: float, th_map: dict,
) -> str:
    """Build a single markdown table row for an async key."""
    model, short_variant, pct, fps_cell, avg_cell, avg_pct, max_cell, max_pct, row_th = \
        _prepare_async_row(key, baseline_data, current_data, threshold, th_map)
    is_fail = STATUS_FAIL in get_status(pct, row_th["e2e_fps"])
    status_md = _resolve_status_md(is_fail, _is_inflight_fail(avg_pct, max_pct, row_th))
    return f"| {model} | {short_variant} | {status_md} | {fps_cell} | {avg_cell} | {max_cell} |"


def _prepare_sync_row(
    key: tuple, baseline_data: dict, current_data: dict,
    threshold: float, th_map: dict,
) -> tuple:
    """Shared computation for sync row builders. Returns
    (model, short_variant, e2e_pct, fps_cells, sub_fail, row_th)."""
    model, variant = key
    short_variant = shorten_variant(model, variant)
    baseline_row = baseline_data.get(key, {})
    current_row = current_data.get(key, {})
    row_th = get_sync_thresholds(th_map, model, short_variant, threshold)

    baseline_e2e = parse_fps_value(baseline_row.get(COL_E2E_FPS, ""))
    current_e2e = parse_fps_value(current_row.get(COL_E2E_FPS, ""))
    _, e2e_pct, _ = calculate_change(baseline_e2e, current_e2e)
    fps_cells, sub_fail = _compute_sync_fps_cells(baseline_row, current_row, row_th, show_threshold=True)
    return model, short_variant, e2e_pct, fps_cells, sub_fail, row_th


def _build_md_sync_row(
    key: tuple, baseline_data: dict, current_data: dict,
    threshold: float, th_map: dict,
) -> str:
    """Build a single markdown table row for a sync key."""
    model, short_variant, e2e_pct, fps_cells, sub_fail, row_th = \
        _prepare_sync_row(key, baseline_data, current_data, threshold, th_map)
    is_fail = STATUS_FAIL in get_status(e2e_pct, row_th[COL_E2E_FPS])
    status_md = _resolve_status_md(is_fail, sub_fail)
    return "| " + " | ".join([model, short_variant, status_md] + fps_cells) + " |"


def _build_html_async_row(
    key: tuple, baseline_data: dict, current_data: dict,
    threshold: float, th_map: dict,
) -> tuple:
    """Build HTML for one async row. Returns (html_str, status_str) where status_str is 'pass'|'warn'|'fail'."""
    model, short_variant, pct, fps_cell, avg_cell, avg_pct, max_cell, max_pct, row_th = \
        _prepare_async_row(key, baseline_data, current_data, threshold, th_map)
    is_fps_fail = pct is not None and pct < -row_th["e2e_fps"]
    is_inflight = _is_inflight_fail(avg_pct, max_pct, row_th)

    if is_fps_fail:
        status_str = "fail"
    elif is_inflight:
        status_str = "warn"
    else:
        status_str = "pass"

    badge = f'<span class="badge {status_str}">{status_str.upper()}</span>'
    row_class = f"{status_str}-row"
    html = (f'<tr class="{row_class}"><td>{model}</td><td>{short_variant}</td>'
            f'<td>{badge}</td><td>{fps_cell}</td><td>{avg_cell}</td><td>{max_cell}</td></tr>')
    return html, status_str


def _build_html_sync_row(
    key: tuple, baseline_data: dict, current_data: dict,
    threshold: float, th_map: dict,
) -> tuple:
    """Build HTML for one sync row. Returns (html_str, status_str) where status_str is 'pass'|'warn'|'fail'."""
    model, short_variant, e2e_pct, fps_cells_plain, sub_fail, row_th = \
        _prepare_sync_row(key, baseline_data, current_data, threshold, th_map)
    is_fail = e2e_pct is not None and e2e_pct < -row_th[COL_E2E_FPS]
    fps_tds = "".join(f"<td>{c}</td>" for c in fps_cells_plain)

    if is_fail:
        status_str = "fail"
    elif sub_fail:
        status_str = "warn"
    else:
        status_str = "pass"

    badge = f'<span class="badge {status_str}">{status_str.upper()}</span>'
    row_class = f"{status_str}-row"
    html = (f'<tr class="{row_class}"><td>{model}</td><td>{short_variant}</td>'
            f'<td>{badge}</td>{fps_tds}</tr>')
    return html, status_str


# ---------------------------------------------------------------------------
# Status-count helpers (used by summary sections)
# ---------------------------------------------------------------------------

def _count_statuses(rows: list) -> tuple:
    """Return (success, warn, fail) from a list of dicts with a 'status' key."""
    success = sum(1 for r in rows if r["status"] == "PASS")
    warn = sum(1 for r in rows if r["status"] == "WARN")
    fail = sum(1 for r in rows if r["status"] == "FAIL")
    return success, warn, fail


def generate_json_report(
    baseline_file: Path,
    current_file: Path,
    baseline_data: dict,
    current_data: dict,
    async_keys: List[tuple],
    sync_keys: List[tuple],
    threshold: float,
    th_map: dict = None,
) -> str:
    """Generate JSON formatted report."""
    th_map = th_map or {}
    async_rows = [_build_json_async_row(k, baseline_data, current_data, threshold, th_map) for k in async_keys]
    sync_rows = [_build_json_sync_row(k, baseline_data, current_data, threshold, th_map) for k in sync_keys]

    a_pass, a_warn, a_fail = _count_statuses(async_rows)
    s_pass, s_warn, s_fail = _count_statuses(sync_rows)
    report = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": baseline_file.name,
        "current": current_file.name,
        "global_threshold": threshold,
        "summary": {
            "async": {"total": len(async_rows), "pass": a_pass, "warn": a_warn, "fail": a_fail},
            "sync":  {"total": len(sync_rows),  "pass": s_pass, "warn": s_warn, "fail": s_fail},
        },
        "async": async_rows,
        "sync": sync_rows,
    }
    return json.dumps(report, indent=2)


def generate_markdown_report(
    baseline_file: Path,
    current_file: Path,
    baseline_data: dict,
    current_data: dict,
    async_keys: List[tuple],
    sync_keys: List[tuple],
    threshold: float,
    th_map: dict = None,
    title_prefix: str = "",
) -> str:
    """Generate markdown formatted report."""
    th_map = th_map or {}
    lines = []

    # Header
    title = f"{title_prefix} E2E Performance Report Comparison".strip() if title_prefix else "E2E Performance Report Comparison"
    lines.append(f"# 📊 {title}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"- **Baseline:** `{baseline_file.name}`")
    lines.append(f"- **Current:** `{current_file.name}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Pre-build rows (drives both summary counts and table rows in one pass)
    async_row_strs = [_build_md_async_row(k, baseline_data, current_data, threshold, th_map) for k in async_keys]
    sync_row_strs = [_build_md_sync_row(k, baseline_data, current_data, threshold, th_map) for k in sync_keys]

    # Count statuses by inspecting the rendered row strings
    a_fail = sum(1 for r in async_row_strs if STATUS_MD_FAIL in r)
    a_warn = sum(1 for r in async_row_strs if STATUS_WARN in r)
    a_pass = len(async_row_strs) - a_fail - a_warn
    s_fail = sum(1 for r in sync_row_strs if STATUS_MD_FAIL in r)
    s_warn = sum(1 for r in sync_row_strs if STATUS_WARN in r)
    s_pass = len(sync_row_strs) - s_fail - s_warn

    # Summary
    lines.append("## 📈 Summary")
    lines.append("")
    lines.append("### 🔄 Async")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|:-------|------:|")
    lines.append(f"| TOTAL | {len(async_keys)} |")
    lines.append(f"| {STATUS_PASS} | {a_pass} |")
    lines.append(f"| {STATUS_WARN} | {a_warn} |")
    lines.append(f"| {STATUS_FAIL} | {a_fail} |")
    lines.append("")
    lines.append("### ⚡ Sync")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|:-------|------:|")
    lines.append(f"| TOTAL | {len(sync_keys)} |")
    lines.append(f"| {STATUS_PASS} | {s_pass} |")
    lines.append(f"| {STATUS_WARN} | {s_warn} |")
    lines.append(f"| {STATUS_FAIL} | {s_fail} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 1: Async Comparison
    lines.append("## 🔄 Section 1: Async Comparison")
    lines.append("")
    lines.append("| Model | Variant | Status | E2E FPS | Inflight Avg | Inflight Max |")
    lines.append("|:------|:--------|:-------|:--------------------|:-------------|:-------------|")
    lines.extend(async_row_strs)
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 2: Sync Comparison
    lines.append("## ⚡ Section 2: Sync Comparison")
    lines.append("")
    header_cols = ["Model", "Variant", "Status"] + [col.replace(" FPS", "") for col in FPS_COLUMNS]
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("|" + "|".join([":---"] * len(header_cols)) + "|")
    lines.extend(sync_row_strs)
    lines.append("")

    return "\n".join(lines)


def generate_html_report(
    baseline_file: Path,
    current_file: Path,
    baseline_data: dict,
    current_data: dict,
    async_keys: List[tuple],
    sync_keys: List[tuple],
    threshold: float,
    th_map: dict = None,
    title_prefix: str = "",
) -> str:
    """Generate HTML formatted report."""
    th_map = th_map or {}
    title = f"{title_prefix} E2E Performance Report Comparison".strip() if title_prefix else "E2E Performance Report Comparison"

    # Build async rows and tally counts
    async_html_rows = []
    async_success = async_warn = async_fail = 0
    for key in async_keys:
        row_html, status_str = _build_html_async_row(key, baseline_data, current_data, threshold, th_map)
        async_html_rows.append(row_html)
        if status_str == "fail":
            async_fail += 1
        elif status_str == "warn":
            async_warn += 1
        else:
            async_success += 1

    # Build sync rows and tally counts
    sync_html_rows = []
    sync_success = sync_warn = sync_fail = 0
    for key in sync_keys:
        row_html, status_str = _build_html_sync_row(key, baseline_data, current_data, threshold, th_map)
        sync_html_rows.append(row_html)
        if status_str == "fail":
            sync_fail += 1
        elif status_str == "warn":
            sync_warn += 1
        else:
            sync_success += 1

    # Build sync header columns
    sync_header_cols = "".join(f"<th>{col.replace(' FPS', '')}</th>" for col in FPS_COLUMNS)
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; padding: 24px; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 8px; }}
  h2 {{ font-size: 1.2rem; margin: 24px 0 12px 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 6px; }}
  .meta {{ background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 0.9rem; line-height: 1.8; }}
  .meta strong {{ color: #555; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 24px; font-size: 0.85rem; }}
  th {{ background: #2c3e50; color: #fff; padding: 10px 12px; text-align: left; font-weight: 600; white-space: nowrap; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #eee; white-space: nowrap; }}
  tr:hover {{ background: #f0f4f8; }}
  .pass-row {{ }}
  .fail-row {{ background: #fff5f5; }}
  .fail-row:hover {{ background: #ffe8e8; }}
  .warn-row {{ background: #fffdf5; }}
  .warn-row:hover {{ background: #fff8e1; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 700; }}
  .badge.pass {{ background: #d4edda; color: #155724; }}
  .badge.warn {{ background: #fff3cd; color: #856404; }}
  .badge.fail {{ background: #f8d7da; color: #721c24; }}
  .summary-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
  .summary-card {{ background: #fff; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .summary-card h3 {{ font-size: 1rem; margin-bottom: 10px; }}
  .summary-card table {{ box-shadow: none; margin-bottom: 0; }}
  .summary-card th {{ background: #34495e; }}
  .count-pass {{ color: #155724; font-weight: 700; }}
  .count-warn {{ color: #856404; font-weight: 700; }}
  .count-fail {{ color: #721c24; font-weight: 700; }}
</style>
</head>
<body>
<div class="container">
  <h1>&#x1F4CA; {title}</h1>
  <div class="meta">
    <strong>Generated:</strong> {generated_time}<br>
    <strong>Baseline:</strong> {baseline_file.name}<br>
    <strong>Current:</strong> {current_file.name}
  </div>

  <h2>&#x1F4C8; Summary</h2>
  <div class="summary-grid">
    <div class="summary-card">
      <h3>&#x1F504; Async</h3>
      <table>
        <thead><tr><th>Metric</th><th>Count</th></tr></thead>
        <tbody>
          <tr><td>TOTAL</td><td>{len(async_keys)}</td></tr>
          <tr><td>{STATUS_PASS}</td><td class="count-pass">{async_success}</td></tr>
          <tr><td>{STATUS_WARN}</td><td class="count-warn">{async_warn}</td></tr>
          <tr><td>{STATUS_FAIL}</td><td class="count-fail">{async_fail}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="summary-card">
      <h3>&#x26A1; Sync</h3>
      <table>
        <thead><tr><th>Metric</th><th>Count</th></tr></thead>
        <tbody>
          <tr><td>TOTAL</td><td>{len(sync_keys)}</td></tr>
          <tr><td>{STATUS_PASS}</td><td class="count-pass">{sync_success}</td></tr>
          <tr><td>{STATUS_WARN}</td><td class="count-warn">{sync_warn}</td></tr>
          <tr><td>{STATUS_FAIL}</td><td class="count-fail">{sync_fail}</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <h2>&#x1F504; Section 1: Async Comparison</h2>
  <table>
    <thead><tr><th>Model</th><th>Variant</th><th>Status</th><th>E2E FPS</th><th>Inflight Avg</th><th>Inflight Max</th></tr></thead>
    <tbody>
      {''.join(async_html_rows)}
    </tbody>
  </table>

  <h2>&#x26A1; Section 2: Sync Comparison</h2>
  <table>
    <thead><tr><th>Model</th><th>Variant</th><th>Status</th>{sync_header_cols}</tr></thead>
    <tbody>
      {''.join(sync_html_rows)}
    </tbody>
  </table>
</div>
</body>
</html>"""
    return html

def compare_reports(
    baseline_file: Path,
    current_file: Path,
    threshold: float = 30.0,
    output_format: str = "json",
    threshold_json: Optional[Path] = None,
    title_prefix: str = "",
):
    """Compare two performance reports and generate a report file."""

    # Load per-model/variant threshold overrides if provided
    th_map = load_threshold_json(threshold_json) if threshold_json else {}

    # Load data
    baseline_data = load_csv(baseline_file)
    current_data = load_csv(current_file)

    # Find all unique keys and separate async/sync, sorted by model name alphabetically
    all_keys = set(baseline_data.keys()) | set(current_data.keys())
    async_keys = sorted([k for k in all_keys if "async" in k[1].lower()], key=lambda x: (x[0].lower(), x[1].lower()))
    sync_keys = sorted([k for k in all_keys if "sync" in k[1].lower() and "async" not in k[1].lower()], key=lambda x: (x[0].lower(), x[1].lower()))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if output_format == "html":
        content = generate_html_report(
            baseline_file, current_file, baseline_data, current_data,
            async_keys, sync_keys, threshold, th_map, title_prefix
        )
        output_file = Path(f"report_{timestamp}.html")
        output_file.write_text(content, encoding="utf-8")
        print(f"HTML report saved to: {output_file}")
    elif output_format == "md":
        content = generate_markdown_report(
            baseline_file, current_file, baseline_data, current_data,
            async_keys, sync_keys, threshold, th_map, title_prefix
        )
        output_file = Path(f"report_{timestamp}.md")
        output_file.write_text(content, encoding="utf-8")
        print(f"Markdown report saved to: {output_file}")
    else:  # json (default)
        content = generate_json_report(
            baseline_file, current_file, baseline_data, current_data,
            async_keys, sync_keys, threshold, th_map
        )
        output_file = Path(f"report_{timestamp}.json")
        output_file.write_text(content, encoding="utf-8")
        print(f"JSON report saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Compare two performance report CSV files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s baseline.csv current.csv
  %(prog)s baseline.csv current.csv --threshold 30
  %(prog)s baseline.csv current.csv --json
  %(prog)s baseline.csv current.csv --md
  %(prog)s baseline.csv current.csv --html
  %(prog)s baseline.csv current.csv --md --title_prefix Python
  %(prog)s baseline.csv current.csv --html --title_prefix "C++"
        """
    )
    parser.add_argument("baseline_file", type=Path, help="Baseline performance report CSV")
    parser.add_argument("current_file", type=Path, help="Current performance report CSV")
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=30.0,
        help="Threshold percentage (default: 30, applied as -30%%)"
    )
    parser.add_argument(
        "--threshold-json", "-tj",
        type=Path,
        default=None,
        metavar="FILE",
        help="JSON file with per-model/variant threshold overrides (e.g. threshold.json)"
    )
    parser.add_argument(
        "--title_prefix", "-tp",
        dest="title_prefix",
        default="",
        metavar="PREFIX",
        help="Prefix to add before 'E2E Performance Report' in the title (e.g. 'Python' or 'C++'). Only applies to --md and --html output."
    )
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument(
        "--json",
        dest="format",
        action="store_const",
        const="json",
        help="Output report as JSON file (default)"
    )
    format_group.add_argument(
        "--md",
        dest="format",
        action="store_const",
        const="md",
        help="Output report as Markdown file"
    )
    format_group.add_argument(
        "--html",
        dest="format",
        action="store_const",
        const="html",
        help="Output report as HTML file"
    )
    parser.set_defaults(format="json")

    args = parser.parse_args()

    # Validate files exist
    if not args.baseline_file.exists():
        print(f"Error: File not found: {args.baseline_file}", file=sys.stderr)
        sys.exit(1)
    if not args.current_file.exists():
        print(f"Error: File not found: {args.current_file}", file=sys.stderr)
        sys.exit(1)
    if args.threshold_json and not args.threshold_json.exists():
        print(f"Error: File not found: {args.threshold_json}", file=sys.stderr)
        sys.exit(1)

    # Run comparison
    compare_reports(args.baseline_file, args.current_file, args.threshold, args.format, args.threshold_json, args.title_prefix)


if __name__ == "__main__":
    main()
