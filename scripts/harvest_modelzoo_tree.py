#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Harvest the dx-modelzoo CV model tree into a committed snapshot.

dx-modelzoo lays its CV models out as
``src/dx_modelzoo/models/cv/<task>/<family>/<variant>.yaml``, where ``<variant>``
is byte-identical to the DX Model Zoo ``.dxnn`` stem. That layout is the
authoritative (task, family, variant) table for dx_app -- family assignment is
data, not an algorithm (dx-modelzoo folds depth/width into the family:
resnet50 -> resnet, vgg16-bn -> vgg, wide-resnet50 -> wide-resnet), so no
heuristic can reproduce it.

The snapshot is committed so tests are hermetic and offline. Re-run this script
to refresh it when dx-modelzoo adds models.

Usage:
    python scripts/harvest_modelzoo_tree.py
    python scripts/harvest_modelzoo_tree.py --ref main --out tests/data/modelzoo_cv_tree.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = "DEEPX-AI/dx-modelzoo"
CV_PREFIX = "src/dx_modelzoo/models/cv/"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fetch_tree(ref: str) -> list[dict]:
    url = f"https://api.github.com/repos/{REPO}/git/trees/{ref}?recursive=1"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if "tree" not in payload:
        raise SystemExit(f"GitHub API returned no tree: {str(payload)[:200]}")
    if payload.get("truncated"):
        raise SystemExit("GitHub tree response was truncated -- cannot trust the snapshot")
    return payload["tree"]


def build_snapshot(tree: list[dict], ref: str) -> dict:
    variants: dict[str, dict] = {}
    for entry in tree:
        path = entry.get("path", "")
        if not path.startswith(CV_PREFIX) or not path.endswith(".yaml"):
            continue
        parts = path[len(CV_PREFIX):].split("/")
        if len(parts) != 3:
            raise SystemExit(f"unexpected depth in modelzoo tree: {path}")
        task, family, filename = parts
        stem = filename[: -len(".yaml")]
        if stem in variants:
            raise SystemExit(f"duplicate variant stem in modelzoo tree: {stem}")
        variants[stem] = {"task": task, "family": family}
    if not variants:
        raise SystemExit("no .yaml variants found -- has the modelzoo layout changed?")
    return {
        "source": f"https://github.com/{REPO}/tree/{ref}/{CV_PREFIX}",
        "ref": ref,
        "harvested_at": datetime.now().strftime("%Y-%m-%d"),
        "variant_count": len(variants),
        "variants": dict(sorted(variants.items())),
    }


def carry_provisional(old: dict, new: dict) -> list[str]:
    """Preserve the 'provisional' block and report guesses upstream contradicts.

    The block holds OUR (task, family) for variants dx-modelzoo has not filed -- the
    147 DX Model Zoo 2_5_0 additions. A plain re-harvest would silently drop it, and
    silently dropping it would take with it the only record that those names were
    assigned rather than derived. Worse, once upstream DOES file one of those stems,
    its authoritative assignment may differ from ours; that is the moment the tree
    has to be migrated, so it is reported here as an error rather than a note.
    """
    provisional = old.get("provisional")
    if not provisional:
        return []
    complaints = []
    for stem, ours in provisional["variants"].items():
        theirs = new["variants"].get(stem)
        if theirs and theirs != ours:
            complaints.append(
                f"{stem}: we assigned {ours['task']}/{ours['family']}, "
                f"upstream now says {theirs['task']}/{theirs['family']}")
    new["provisional"] = provisional
    return complaints


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", default="main", help="git ref to harvest (default: main)")
    ap.add_argument("--out", default="tests/data/modelzoo_cv_tree.json",
                    help="output path, relative to the dx_app root")
    args = ap.parse_args()

    snapshot = build_snapshot(fetch_tree(args.ref), args.ref)
    out = PROJECT_ROOT / args.out
    complaints: list[str] = []
    if out.is_file():
        complaints = carry_provisional(
            json.loads(out.read_text(encoding="utf-8")), snapshot)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    tasks = {v["task"] for v in snapshot["variants"].values()}
    families = {(v["task"], v["family"]) for v in snapshot["variants"].values()}
    try:
        where = out.relative_to(PROJECT_ROOT)
    except ValueError:
        where = out
    print(f"wrote {where}")
    print(f"  variants={snapshot['variant_count']} tasks={len(tasks)} families={len(families)}")
    provisional = snapshot.get("provisional")
    if provisional:
        published = [s for s in provisional["variants"] if s in snapshot["variants"]]
        print(f"  provisional={provisional['variant_count']} "
              f"(now published upstream: {len(published)})")
        if published:
            print("[DXAPP] [WARN] these stems must move from 'provisional' into "
                  f"'variants': {sorted(published)}")
    for line in complaints:
        print(f"[DXAPP] [WARN] provisional mismatch -- {line}")
    if complaints:
        print(f"[DXAPP] [ERROR] {len(complaints)} provisional assignment(s) disagree "
              "with dx-modelzoo. Update scripts/data/modelzoo_2_5_0.py to upstream's "
              "names, re-run scripts/add_modelzoo_2_5_0_models.py, then regenerate "
              "both example trees.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
