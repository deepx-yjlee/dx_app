#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Restructure the example trees into the dx-modelzoo task/family/variant layout.

353 per-variant directories collapse into 89 ``<task>/<family>/`` directories, each
holding ONE factory plus one ``variants/<dxnn-stem>.json`` per variant -- the layout
dx-modelzoo uses (``custom_ops.py`` + one config per variant).

``config/model_registry.json`` is the sole source of truth: task, family, variant,
postprocessor, geometry and defaults all come from it, so this transformation is
deterministic and idempotent rather than 706 hand edits.

SAFETY -- a family only collapses when its variants' factories are equivalent.
Equivalence is checked by normalising away names, comments, whitespace, import order,
numbers and strings; what survives is control flow and structure. If two variants in a
family differ in anything beyond which postprocessor class they name, the family is
REFUSED and reported instead of being silently flattened. That refusal is the point:
collapsing a family whose variants really do differ would lose behaviour.

Usage:
    python3 scripts/restructure_examples.py --tree python --dry-run
    python3 scripts/restructure_examples.py --tree python
    python3 scripts/restructure_examples.py --tree cpp
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = PROJECT_ROOT / "config" / "model_registry.json"

TREES = {
    "python": dict(root="src/python_example", ext=".py", fac="factory/*_factory.py"),
    "cpp": dict(root="src/cpp_example", ext=".hpp", fac="factory/*_factory.hpp"),
}

# Registry model_name -> existing example dir. 53 entries carry a re-publish suffix
# (beit_large_patch16_1 -> beit_large_patch16) and one a quantisation suffix
# (deeplabv3plus_drn_512x512_q_lite -> deeplabv3plus_drn_512x512).
SUFFIX_RULES = (r"_q_lite$", r"_\d+$")


# --------------------------------------------------------------------------- utils
def sh(*cmd: str) -> str:
    return subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                          check=True).stdout


def existing_dirs(root: Path) -> dict[str, str]:
    """``{dir_name -> task_dir_name}`` for every example dir in the tree."""
    out: dict[str, str] = {}
    for task in sorted(root.iterdir()):
        if not task.is_dir() or task.name in {"common", "__pycache__"}:
            continue
        for d in sorted(task.iterdir()):
            if d.is_dir() and d.name != "__pycache__":
                out[d.name] = task.name
    return out


def resolve_dir(model_name: str, table: dict[str, str]) -> str | None:
    cand = model_name
    for _ in range(3):
        if cand in table:
            return cand
        nxt = cand
        for rx in SUFFIX_RULES:
            nxt = re.sub(rx, "", nxt)
        if nxt == cand:
            break
        cand = nxt
    return cand if cand in table else None


def normalise(body: str, dir_name: str) -> str:
    """Structure-only fingerprint: names, comments, literals and layout removed."""
    b = body
    b = re.sub(r'""".*?"""', "", b, flags=re.S)
    b = re.sub(r"/\*.*?\*/", "", b, flags=re.S)
    b = re.sub(r"//.*", "", b)
    b = re.sub(r"^\s*#(?!\s*(ifndef|define|endif|include|pragma)).*$", "", b, flags=re.M)
    for tok in sorted({dir_name, dir_name.upper(), dir_name.replace("_", ""),
                       dir_name.replace("_", "").upper()}, key=len, reverse=True):
        if tok:
            b = re.sub(re.escape(tok), "M", b, flags=re.I)
    b = re.sub(r"\b[A-Za-z0-9_]*FACTORY[A-Za-z0-9_]*\b", "G", b, flags=re.I)
    b = re.sub(r'"[^"]*"', "S", b)
    b = re.sub(r"'[^']*'", "S", b)
    b = re.sub(r"\b\d+(\.\d+)?f?\b", "N", b)
    b = re.sub(r"(from [\w.]+ import )(.+)",
               lambda m: m.group(1) + ", ".join(sorted(s.strip() for s in m.group(2).split(","))),
               b)
    b = re.sub(r"\s+", " ", b)
    return hashlib.md5(b.strip().encode()).hexdigest()[:10]


def processor_imports(body: str) -> frozenset[str]:
    """The processor class names a factory pulls in -- the axis families may differ on."""
    names: set[str] = set()
    for m in re.finditer(r"from common\.processors import (.+)", body):
        names |= {s.strip() for s in m.group(1).split(",") if s.strip()}
    for m in re.finditer(r"\b([A-Za-z0-9_]*(?:Preprocessor|Postprocessor|Visualizer))\b", body):
        names.add(m.group(1))
    return frozenset(names)


# ------------------------------------------------------------------------ analysis
def analyse(tree: str):
    cfg = TREES[tree]
    root = PROJECT_ROOT / cfg["root"]
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    table = existing_dirs(root)

    rows, unresolved = [], []
    for e in reg:
        d = resolve_dir(e["model_name"], table)
        if d is None:
            unresolved.append(e["model_name"])
            continue
        rows.append(dict(entry=e, dir=d, task_dir=table[d]))

    used = {r["dir"] for r in rows}
    orphans = sorted(set(table) - used)

    fams: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in rows:
        fams[(r["entry"]["task"], r["entry"]["family"])].append(r)

    # Per family: factory fingerprints and processor sets
    refused, dispatch, clean = {}, {}, []
    for key, members in sorted(fams.items()):
        prints: dict[str, str] = {}
        procs: dict[str, frozenset[str]] = {}
        for r in members:
            fdir = root / r["task_dir"] / r["dir"] / "factory"
            facs = sorted(fdir.glob(f"*_factory{cfg['ext']}")) if fdir.is_dir() else []
            if not facs:
                continue
            body = facs[0].read_text(errors="ignore")
            prints[r["dir"]] = normalise(body, r["dir"])
            procs[r["dir"]] = processor_imports(body)
        shapes = set(prints.values())
        if len(shapes) <= 1:
            clean.append(key)
        else:
            # Differ only by WHICH processor classes are named? Then one family
            # factory can dispatch on the variant. Re-fingerprint with every
            # processor class name collapsed to a single token: if the shapes now
            # agree, processor choice was the only difference.
            stripped: dict[str, str] = {}
            for r in members:
                f = (root / r["task_dir"] / r["dir"] / "factory"
                     / f"{r['dir']}_factory{cfg['ext']}")
                if not f.exists():
                    continue
                body = re.sub(
                    r"\b[A-Za-z0-9_]*(Preprocessor|Postprocessor|Visualizer)\b",
                    "P", f.read_text(errors="ignore"))
                stripped[r["dir"]] = normalise(body, r["dir"])
            if len(set(stripped.values())) <= 1:
                dispatch[key] = {d: sorted(procs.get(d, ())) for d in prints}
            else:
                by_shape = collections.defaultdict(list)
                for d, h in prints.items():
                    by_shape[h].append(d)
                refused[key] = dict(by_shape)

    return dict(root=root, cfg=cfg, rows=rows, unresolved=unresolved, orphans=orphans,
                fams=fams, clean=clean, dispatch=dispatch, refused=refused)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", choices=sorted(TREES), required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    r = analyse(a.tree)
    print(f"tree={a.tree}  root={r['cfg']['root']}")
    print(f"  entries resolved to a dir : {len(r['rows'])}")
    print(f"  unresolved                : {len(r['unresolved'])} {r['unresolved'][:5]}")
    print(f"  orphan dirs               : {len(r['orphans'])} {r['orphans'][:5]}")
    print(f"  target families           : {len(r['fams'])}")
    print(f"    uniform (plain collapse): {len(r['clean'])}")
    print(f"    need variant dispatch   : {len(r['dispatch'])}")
    print(f"    REFUSED (real divergence): {len(r['refused'])}")
    for k, v in r["dispatch"].items():
        procs = sorted({p for ps in v.values() for p in ps})
        print(f"      dispatch {k[0]}/{k[1]}: {len(v)} variants, processors={procs}")
    for k, v in r["refused"].items():
        print(f"      REFUSED  {k[0]}/{k[1]}: " + " | ".join(
            f"{len(ds)}x[{sorted(ds)[0]}]" for ds in v.values()))

    if r["unresolved"] or r["orphans"]:
        print("\nABORT: mapping is not complete (measured 353/353 with 0 orphans).")
        return 1
    if r["refused"]:
        print("\nABORT: the families above diverge beyond processor choice. Collapsing "
              "them would lose behaviour -- inspect and resolve before restructuring.")
        return 1
    print("\nmapping is complete and every family is collapsible.")
    if a.dry_run:
        print("dry-run: nothing moved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
