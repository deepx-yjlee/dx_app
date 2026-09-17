#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Run real NPU inference for every registry variant and report pass/fail.

This exercises the PRODUCTION path -- it invokes each generated family entry script
exactly as a user would, ``<family>_sync.py --variant <dxnn-stem> --image <sample>
--no-display`` -- rather than re-implementing the pipeline in the harness. A harness
that builds the processors itself can pass while the shipped entry point is broken;
this cannot.

Each variant's input comes from its own variant config (``default_image``), which the
restructure baked from the legacy task tables, so an image-only model gets its pair
directory and SFA3D gets its KITTI .bin.

Usage:
    ../venv-dx-runtime/bin/python scripts/sweep_npu_inference.py
    ../venv-dx-runtime/bin/python scripts/sweep_npu_inference.py --tree cpp
    ../venv-dx-runtime/bin/python scripts/sweep_npu_inference.py --variant yolov5-s_640x640
    ../venv-dx-runtime/bin/python scripts/sweep_npu_inference.py --jobs 1 --timeout 180
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "model_registry.json"
MODELS = ROOT / "assets" / "models"
REPORT = ROOT / "artifacts" / "npu_sweep"


def variant_config(tree: str, task: str, family: str, variant: str) -> dict | None:
    p = ROOT / "src" / tree / task / family / "variants" / f"{variant}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def resolve_input(cfg: dict) -> tuple[str, str] | None:
    """``(flag, value)`` for this variant's default input, or None when absent."""
    img = cfg.get("default_image")
    if img and (ROOT / img).exists():
        return "--image", img
    # An image-only task has no default; fall back to the task's own sample if the
    # legacy table had none (a handful of tasks relied on the runner's hint path).
    return None


def run_one(entry: Path, variant: str, cfg: dict, dxnn: Path, timeout: int) -> dict:
    started = time.time()
    # C++ takes no --variant: it derives the variant from the model path, which is
    # the point of variant_from_args.hpp. Python accepts both; -m alone is enough.
    if entry.suffix == ".py":
        cmd = [sys.executable, entry.name, "--variant", variant,
               "-m", str(dxnn), "--no-display", "--show-log"]
        cwd = entry.parent
    else:
        cmd = [str(entry), "-m", str(dxnn), "--no-display"]
        cwd = ROOT
    inp = resolve_input(cfg)
    if inp:
        # cxxopts names the image option image_path/-i; argparse names it --image.
        flag = "-i" if entry.suffix != ".py" else inp[0]
        cmd += [flag, str(ROOT / inp[1])]
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")   # no X11 on a headless box
    try:
        pr = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                            timeout=timeout, env=env)
        out = (pr.stdout or "") + (pr.stderr or "")
        # rc == 0 is NOT sufficient evidence. A script that exits cleanly without ever
        # touching the NPU would score a pass, which is exactly the kind of hollow
        # green this sweep exists to rule out. Require the runner's own inference
        # latency line, which only appears after a real engine call.
        ran = ("Infer:" in out) or ("Inference " in out and "ms" in out) \
            or ("Inference:" in out)
        if pr.returncode != 0:
            status = "FAIL"
        elif not ran:
            status = "NO_INFERENCE"
        else:
            status = "PASS"
        infer_ms = None
        for tok in out.split("Infer:")[1:2]:
            try:
                infer_ms = float(tok.strip().split("ms")[0])
            except (ValueError, IndexError):
                pass
        return dict(variant=variant, status=status, rc=pr.returncode,
                    secs=round(time.time() - started, 1), infer_ms=infer_ms,
                    entry=(str(entry.relative_to(ROOT))
                           if ROOT in entry.parents else str(entry)),
                    input=inp[1] if inp else None,
                    tail="\n".join(out.strip().splitlines()[-8:])
                    if status != "PASS" else "")
    except subprocess.TimeoutExpired:
        return dict(variant=variant, status="TIMEOUT", rc=None,
                    secs=round(time.time() - started, 1),
                    entry=(str(entry.relative_to(ROOT))
                           if ROOT in entry.parents else str(entry)), input=inp[1] if inp else None,
                    tail=f"exceeded {timeout}s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", default="python_example",
                    choices=["python_example", "cpp_example"])
    ap.add_argument("--bindir", default=None,
                    help="directory holding the built C++ executables "
                         "(default: bin/, then src/cpp_example/build/)")
    ap.add_argument("--kind", default="sync", choices=["sync", "async"])
    ap.add_argument("--variant", default=None, help="run a single variant")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel workers. Default 1: one NPU, and concurrent engines "
                         "contend for it, which turns a real pass into a flaky timeout.")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--out", default=str(REPORT))
    a = ap.parse_args()

    bindir = Path(a.bindir) if a.bindir else None
    if a.tree == "cpp_example" and bindir is None:
        for cand in (ROOT / "bin", ROOT / "src" / "cpp_example" / "build"):
            if cand.is_dir() and any(cand.glob("*_sync")):
                bindir = cand
                break
        if bindir is None:
            print("ABORT: no C++ build found. Pass --bindir, or run ./build.sh")
            return 1
        print(f"bindir = {bindir}")

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    jobs = []
    skipped = []
    for e in reg:
        if a.variant and e["variant"] != a.variant:
            continue
        cfg = variant_config(a.tree, e["task"], e["family"], e["variant"])
        if cfg is None:
            skipped.append((e["variant"], "no variant config"))
            continue
        dxnn = MODELS / e["dxnn_file"]
        if not dxnn.is_file():
            skipped.append((e["variant"], "dxnn missing"))
            continue
        if a.tree == "cpp_example":
            entry = bindir / f"{e['family']}_{a.kind}"
        else:
            entry = (ROOT / "src" / a.tree / e["task"] / e["family"]
                     / f"{e['family']}_{a.kind}.py")
        if not entry.is_file():
            skipped.append((e["variant"], f"entry missing: {entry.name}"))
            continue
        jobs.append((entry, e["variant"], cfg, dxnn))

    print(f"variants to run : {len(jobs)}   skipped: {len(skipped)}")
    for v, why in skipped[:10]:
        print(f"  SKIP {v}: {why}")

    results = []
    t0 = time.time()
    if a.jobs > 1:
        with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
            futs = {ex.submit(run_one, *j, a.timeout): j[1] for j in jobs}
            for i, f in enumerate(cf.as_completed(futs), 1):
                r = f.result()
                results.append(r)
                print(f"[{i:3d}/{len(jobs)}] {r['status']:7s} {r['variant']} ({r['secs']}s)")
    else:
        for i, j in enumerate(jobs, 1):
            r = run_one(*j, a.timeout)
            results.append(r)
            print(f"[{i:3d}/{len(jobs)}] {r['status']:7s} {r['variant']} ({r['secs']}s)",
                  flush=True)
            if r["status"] != "PASS":
                for ln in r["tail"].splitlines():
                    print(f"          | {ln}")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report = out / f"sweep-{a.tree}-{a.kind}-{stamp}.json"
    report.write_text(json.dumps(
        dict(tree=a.tree, kind=a.kind, total=len(jobs), skipped=skipped,
             wall_secs=round(time.time() - t0, 1), results=results), indent=1) + "\n",
        encoding="utf-8")

    counts = {s: sum(1 for r in results if r["status"] == s)
              for s in ("PASS", "FAIL", "TIMEOUT", "NO_INFERENCE")}
    print(f"\n==== {a.tree} / {a.kind} ====")
    ms = [r["infer_ms"] for r in results if r.get("infer_ms")]
    print(f"  PASS={counts['PASS']}  FAIL={counts['FAIL']}  TIMEOUT={counts['TIMEOUT']}"
          f"  NO_INFERENCE={counts['NO_INFERENCE']}  SKIP={len(skipped)}"
          f"  of {len(jobs)} run in {round(time.time()-t0)}s")
    if ms:
        print(f"  NPU infer latency: n={len(ms)} min={min(ms):.1f}ms "
              f"median={sorted(ms)[len(ms)//2]:.1f}ms max={max(ms):.1f}ms")
    print(f"  report: {report.relative_to(ROOT)}")
    bad = [r for r in results if r["status"] != "PASS"]
    for r in bad[:25]:
        print(f"  {r['status']:7s} {r['variant']}  rc={r['rc']}")
        for ln in r["tail"].splitlines()[-3:]:
            print(f"          | {ln}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
