#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""SDKREQ-521: every supported model has an example, in both trees.

Under the dx-modelzoo family/variant layout coverage is a DIRECT lookup, not a name
match: a model is covered when its family directory holds ``<variant>/config.json``
and the family's entry scripts exist. The previous version compared registry
``model_name`` against per-variant directory names through a normalise/strip/alias
cascade, which the family layout makes both unnecessary and wrong -- it reported
python=13 cpp=13 against 352 models and called 89 real family dirs orphans.

Exit 0 when every supported model is covered in both trees and python coverage is at
least C++ coverage; 1 otherwise; 77 when the registry is missing.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SKIP_TASK_DIRS = {"common", "build", "multi_model", "multi_model_graph"}
_ENTRY_SUFFIX = {"python_example": "_sync.py", "cpp_example": "_sync.cpp"}


def load_registry() -> list[dict]:
    p = _ROOT / "config" / "model_registry.json"
    if not p.is_file():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def family_dirs(tree: str):
    """``(task, family, path)`` for every family directory in *tree*."""
    root = _ROOT / "src" / tree
    for task in sorted(os.listdir(root)):
        tp = root / task
        if not tp.is_dir() or task in _SKIP_TASK_DIRS or task.startswith("__"):
            continue
        for fam in sorted(os.listdir(tp)):
            fp = tp / fam
            if fp.is_dir() and not fam.startswith("__"):
                yield task, fam, fp


def coverage(tree: str, supported: list[dict]):
    """``(covered dxnn, uncovered model names, orphan family dirs)``."""
    covered, problems = set(), []
    for e in supported:
        fp = _ROOT / "src" / tree / e["task"] / e["family"]
        cfg = fp / e["variant"] / "config.json"
        entry = fp / e["variant"] / f"{e['variant']}{_ENTRY_SUFFIX[tree]}"
        if cfg.is_file() and entry.is_file():
            covered.add(e["dxnn_file"])
        else:
            why = "variant config" if not cfg.is_file() else "entry script"
            problems.append(f"{e['model_name']} (missing {why}: "
                            f"{(cfg if why == 'variant config' else entry).relative_to(_ROOT)})")

    expected = {(e["task"], e["family"]) for e in supported}
    orphan = [f"{t}/{f}" for t, f, _ in family_dirs(tree) if (t, f) not in expected]
    return covered, sorted(problems), sorted(orphan)


def main() -> int:
    supported = load_registry()
    if not supported:
        print("model_registry.json not found or empty")
        return 77

    n_dxnn = len({e["dxnn_file"] for e in supported})
    ok = True
    cov = {}
    for tree in ("python_example", "cpp_example"):
        covered, uncovered, orphan = coverage(tree, supported)
        cov[tree] = len(covered)
        print(f"{tree}: supported_dxnn={n_dxnn} covered={len(covered)} "
              f"uncovered={len(uncovered)} orphan_dirs={len(orphan)}")
        for m in uncovered:
            print(f"   [uncovered] {m}")
            ok = False
        for d in orphan:
            print(f"   [orphan] family dir is in no registry entry: {d}")
            ok = False

    print(f"coverage: python={cov['python_example']}  cpp={cov['cpp_example']}  "
          "(need python>=cpp)")
    if cov["python_example"] < cov["cpp_example"]:
        print("   [FAIL] python coverage < cpp coverage")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
