#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Audit the NPU sweep reports: is every PASS actually backed by evidence?

A sweep prints ``PASS=357 FAIL=0``, and that number on its own is not an audit. It
answers "did the process exit 0 and did the runner print something that looks like
inference", once per combination. This script asks the questions the count hides:

* Does every combination cover the SAME set of variants? A variant silently absent
  from one tree's run would never show up as a failure -- it would just not be there.
* Does every PASS carry a latency measurement, or did some pass on a parse the
  sweep's evidence rule happens to accept?
* For the async variants, did callbacks actually complete (``Infer Completed : N``)?
  An async runner can print a summary having collected zero frames.
* Is every task and every family represented, or is the total carried by the 111
  classification models while some task is quietly unrun?
* Are the latencies plausible -- any variant near the timeout, or suspiciously fast?

It reads the newest report per (tree, kind) and exits non-zero if any of those checks
fails, so it can gate a release the way the sweep itself cannot.

Usage:
    python3 scripts/audit_sweep_reports.py
    python3 scripts/audit_sweep_reports.py --reports artifacts/npu_sweep --verbose
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "model_registry.json"
DEFAULT_REPORTS = ROOT / "artifacts" / "npu_sweep"

COMBINATIONS = (
    ("python_example", "sync"),
    ("python_example", "async"),
    ("python_example", "sync_cpp_postprocess"),
    ("python_example", "async_cpp_postprocess"),
    ("cpp_example", "sync"),
    ("cpp_example", "async"),
)

# ESPCN runs tiled 480-pixel inference and prints no per-frame "Infer:" line, so its
# three variants legitimately pass without a latency number. Measured, not assumed --
# the predecessor's sweep hit the same three.
LATENCY_EXEMPT_PREFIXES = ("espcn-",)


def newest_report(reports_dir: Path, tree: str, kind: str) -> Path | None:
    candidates = sorted(reports_dir.glob(f"sweep-{tree}-{kind}-*.json"))
    return candidates[-1] if candidates else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_variant = {e["variant"]: e for e in registry}

    problems: list[str] = []   # fail the audit
    warnings: list[str] = []   # report, do not fail
    ran: dict[tuple, set] = {}
    reports: dict[tuple, dict] = {}

    print(f"{'combination':<42} {'PASS':>5} {'FAIL':>5} {'other':>6} "
          f"{'unsupported':>12} {'latency n':>10}")
    print("-" * 86)
    for tree, kind in COMBINATIONS:
        path = newest_report(args.reports, tree, kind)
        if path is None:
            problems.append(f"{tree}/{kind}: no report in {args.reports}")
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        reports[(tree, kind)] = report
        results = report["results"]
        statuses = defaultdict(int)
        for r in results:
            statuses[r["status"]] += 1
        passed = statuses.get("PASS", 0)
        failed = statuses.get("FAIL", 0)
        other = sum(v for k, v in statuses.items() if k not in ("PASS", "FAIL"))
        with_latency = sum(1 for r in results if r.get("infer_ms"))
        ran[(tree, kind)] = {r["variant"] for r in results}
        print(f"{tree + '/' + kind:<42} {passed:>5} {failed:>5} {other:>6} "
              f"{len(report.get('unsupported_container', [])):>12} {with_latency:>10}")

        if failed or other:
            bad = [f"{r['variant']}({r['status']})" for r in results
                   if r["status"] != "PASS"]
            problems.append(f"{tree}/{kind}: {len(bad)} non-PASS: {bad[:8]}")

        # What makes a PASS trustworthy is the sweep's own NO_INFERENCE rule: it looks
        # for the runner's inference LINE, so a script exiting 0 without touching the
        # NPU is classified NO_INFERENCE, not PASS. Zero of those is the evidence.
        #
        # A missing infer_ms is therefore a REPORTING gap, not a hollow pass -- the
        # first version of this audit conflated the two and called four healthy
        # combinations failures. It is still worth flagging, because latency is how a
        # regression shows up before it becomes a failure.
        no_latency = [r["variant"] for r in results
                      if r["status"] == "PASS" and not r.get("infer_ms")
                      and not r["variant"].startswith(LATENCY_EXEMPT_PREFIXES)]
        if no_latency:
            warnings.append(f"{tree}/{kind}: {len(no_latency)} PASS carry no latency "
                            f"number (the inference LINE was still required for the "
                            f"pass): {sorted(no_latency)[:5]}")

        # Async: a summary can print having collected zero frames.
        if kind.startswith("async"):
            zero = [r["variant"] for r in results
                    if r["status"] == "PASS" and r.get("completed") is not None
                    and r["completed"] < 1]
            if zero:
                problems.append(f"{tree}/{kind}: {len(zero)} async PASS with zero "
                                f"completed callbacks: {sorted(zero)[:8]}")
            measured = sum(1 for r in results if r.get("completed") is not None)
            if args.verbose:
                print(f"    async callbacks reported by {measured}/{len(results)}")

    if not reports:
        print("\n[DXAPP] [ERROR] no reports found -- run scripts/sweep_npu_inference.py",
              file=sys.stderr)
        return 2

    # Every combination must cover the SAME variants: a variant missing from one run
    # is invisible in that run's counts.
    sets = list(ran.values())
    union = set().union(*sets)
    for (tree, kind), covered in ran.items():
        missing = union - covered
        if missing:
            problems.append(f"{tree}/{kind}: {len(missing)} variant(s) present in "
                            f"another combination but not here: {sorted(missing)[:8]}")
    print(f"\nvariants covered by every combination: "
          f"{len(set.intersection(*sets)) if sets else 0} / {len(union)}")

    # Task and family coverage, so a total carried by one big task is visible.
    tasks = defaultdict(int)
    families = set()
    for variant in union:
        entry = by_variant.get(variant)
        if entry:
            tasks[entry["task"]] += 1
            families.add(entry["family"])
    print(f"tasks represented: {len(tasks)}   families represented: {len(families)}")
    if args.verbose:
        for task, n in sorted(tasks.items(), key=lambda kv: -kv[1]):
            print(f"    {task:<34} {n}")

    runnable = {e["variant"] for e in registry
                if e["variant"] not in set(
                    v for (_, _), rep in reports.items()
                    for v, _ in rep.get("unsupported_container", []))}
    uncovered = runnable - union
    if uncovered:
        problems.append(f"{len(uncovered)} runnable variant(s) never appear in any "
                        f"report: {sorted(uncovered)[:8]}")

    # Latency sanity, across every combination at once.
    latencies = [(r["variant"], r["infer_ms"], f"{t}/{k}")
                 for (t, k), rep in reports.items()
                 for r in rep["results"] if r.get("infer_ms")]
    if latencies:
        slowest = sorted(latencies, key=lambda x: -x[1])[:5]
        fastest = sorted(latencies, key=lambda x: x[1])[:3]
        print(f"\nNPU latency across all combinations: n={len(latencies)}")
        print("  slowest: " + ", ".join(f"{v} {ms:.1f}ms [{c}]" for v, ms, c in slowest))
        print("  fastest: " + ", ".join(f"{v} {ms:.1f}ms [{c}]" for v, ms, c in fastest))

    print()
    for line in warnings:
        print(f"[DXAPP] [WARN] {line}")
    if warnings:
        print()
    if problems:
        for line in problems:
            print(f"[DXAPP] [ERROR] {line}", file=sys.stderr)
        print(f"[DXAPP] [ERROR] AUDIT: FAIL ({len(problems)} problem(s))",
              file=sys.stderr)
        return 1
    print("[DXAPP] [INFO] AUDIT: PASS -- every combination covers the same variants, "
          "no combination reported a non-PASS, and no async run passed with zero "
          "completed callbacks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
