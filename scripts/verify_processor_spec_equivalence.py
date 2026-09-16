#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Prove the variant configs rebuild exactly what each original factory built.

Collapsing 353 per-variant factories into 89 family factories is only safe if
``common.variant_config.build_processor`` -- the code path the generated family
factories actually use -- reconstructs the same processors the original factory did.
This script is that proof, and it deliberately exercises the production builder rather
than a bespoke reimplementation.

Two sources of false positives are handled:

* Non-deterministic attributes -- ``DetectionVisualizer`` builds a RANDOM 80x3 colour
  palette, so two instances of the same class with identical arguments already differ.
  The original's processor is built a second time and whatever differs between those two
  is treated as noise. Without this, 142 of 352 variants look broken.
* ``config``, which the runner owns rather than the variant.

A residual mismatch means the variant needs real code rather than config -- computed
arguments such as ``imagenet_mean`` or ``[m * 255.0 for m in mean]`` cannot be reduced to
literals. Those belong in the family's ``custom_ops.py``, the same escape hatch
dx-modelzoo uses, and are reported separately from genuine failures.

Usage:
    ../venv-dx-runtime/bin/python scripts/verify_processor_spec_equivalence.py
"""
from __future__ import annotations

import collections
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python_example"))

from common.variant_config import (  # noqa: E402
    VariantConfigError, build_processor, spec_is_buildable,
)

ROLES = (("preprocessor", "create_preprocessor"),
         ("postprocessor", "create_postprocessor"),
         ("visualizer", "create_visualizer"))


def load_original_factory(task: str, dir_name: str):
    fdir = ROOT / "src" / "python_example" / task / dir_name / "factory"
    cands = sorted(fdir.glob("*_factory.py"))
    if not cands:
        return None, {}
    spec = importlib.util.spec_from_file_location(f"orig_{abs(hash(dir_name))}", cands[0])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = next((o for n, o in vars(mod).items()
                if isinstance(o, type) and n.endswith("Factory") and n != "Factory"
                and o.__module__ == mod.__name__), None)
    cfg_path = fdir.parent / "config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    return cls, cfg


def main() -> int:
    specs = json.loads((ROOT / "tests" / "data" / "processor_specs.json").read_text())
    W = H = 640

    ok = needs_code = broken = 0
    reasons: dict[str, list[str]] = collections.defaultdict(list)

    for variant, s in sorted(specs.items()):
        # A spec with a non-literal argument is expected to need custom_ops.py.
        if not all(spec_is_buildable(s.get(role) or {}) for role, _ in ROLES):
            needs_code += 1
            reasons["needs custom_ops.py (non-literal arg)"].append(variant)
            continue

        FC, cfg = load_original_factory(s["source_task"], s["source_dir"])
        if FC is None:
            broken += 1
            reasons["no original factory class"].append(variant)
            continue
        try:
            fac = FC(cfg)
        except TypeError:
            fac = FC()

        problems = []
        for role, meth in ROLES:
            call = (lambda: fac.create_visualizer()) if meth == "create_visualizer" \
                else (lambda m=meth: getattr(fac, m)(W, H))
            try:
                orig, twin = call(), call()
            except Exception as ex:
                problems.append((role, "ORIGINAL_RAISED", f"{type(ex).__name__}: {ex}"))
                continue
            try:
                rebuilt = build_processor(s[role], input_width=W, input_height=H, config=cfg)
            except VariantConfigError as ex:
                problems.append((role, "BUILD_REFUSED", str(ex)[:90]))
                continue
            except Exception as ex:
                problems.append((role, "BUILD_RAISED", f"{type(ex).__name__}: {ex}"))
                continue
            if type(orig) is not type(rebuilt):
                problems.append((role, "TYPE",
                                 f"{type(orig).__name__} != {type(rebuilt).__name__}"))
                continue
            ov, tv, rv = vars(orig), vars(twin), vars(rebuilt)
            nondet = {k for k in set(ov) | set(tv) if repr(ov.get(k)) != repr(tv.get(k))}
            diff = {k for k in set(ov) | set(rv)
                    if repr(ov.get(k)) != repr(rv.get(k))} - nondet - {"config"}
            if diff:
                problems.append((role, "ATTRS", sorted(diff)[:6]))

        if problems:
            broken += 1
            reasons[str(sorted({p[1] for p in problems}))].append(f"{variant} {problems}")
        else:
            ok += 1

    total = len(specs)
    print(f"variants                      : {total}")
    print(f"  rebuilt identically         : {ok}")
    print(f"  need family custom_ops.py   : {needs_code}")
    print(f"  MISMATCH (must investigate) : {broken}")
    print()
    for kind, items in sorted(reasons.items(), key=lambda x: -len(x[1])):
        print(f"  {len(items):4d}  {kind}")
        for it in items[:4]:
            print(f"          {it}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
