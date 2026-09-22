#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Prove each GENERATED family factory reproduces the original per-variant factory.

This is the gate the restructure turns on. For every variant it builds the three
processors twice -- once from the original per-variant factory, once from the generated
family factory selected by ``--variant`` -- and compares class and attributes. A green
run means collapsing 353 directories into 89 changes no behaviour.

Non-deterministic attributes are filtered by constructing the original twice and
treating whatever differs between those two as noise; ``DetectionVisualizer`` builds a
RANDOM 80x3 colour palette, which otherwise makes 142 of 352 variants look broken.

Usage:
    ../venv-dx-runtime/bin/python scripts/verify_generated_layout.py --stage /tmp/stage
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python_example"))

ROLES = (("preprocessor", "create_preprocessor"),
         ("postprocessor", "create_postprocessor"),
         ("visualizer", "create_visualizer"))


ORIG_ROOT = ROOT  # replaced in main() when --orig is given


def load_class(path: Path, tag: str):
    spec = importlib.util.spec_from_file_location(f"m_{tag}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return next((o for n, o in vars(mod).items()
                 if isinstance(o, type) and n.endswith("Factory") and n != "Factory"
                 and o.__module__ == mod.__name__), None)


def processors(fac, w, h):
    out = {}
    for role, meth in ROLES:
        out[role] = (fac.create_visualizer() if meth == "create_visualizer"
                     else getattr(fac, meth)(w, h))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", required=True, help="generated tree root")
    ap.add_argument("--orig", default=None,
                    help="root holding the ORIGINAL src/python_example. Needed once the "
                         "restructure has replaced the working tree -- restore it with "
                         "`git archive <pre-restructure-sha> src/python_example | tar -x -C DIR`.")
    a = ap.parse_args()
    stage = Path(a.stage)
    orig_root = Path(a.orig) if a.orig else ROOT

    specs = json.loads((ROOT / "tests" / "data" / "processor_specs.json").read_text())
    ok = fail = 0
    reasons: dict[str, list[str]] = collections.defaultdict(list)

    no_original: list[str] = []
    for variant, s in sorted(specs.items()):
        task, family = s["task"], s["family"]
        w, h = 640, 640

        # ---- original ----
        odir = orig_root / "src" / "python_example" / s["source_task"] / s["source_dir"]
        ocands = sorted((odir / "factory").glob("*_factory.py"))
        OC = load_class(ocands[0], f"o_{abs(hash(variant))}") if ocands else None
        if OC is None:
            # Not a difference -- an absence. A variant introduced AFTER the
            # restructure (the 147 DX Model Zoo 2_5_0 additions) has no
            # pre-restructure factory to be equivalent to, and counting that as a
            # failure would drown the one signal this gate exists to give: that a
            # variant which DID have an original still builds the same processors.
            no_original.append(variant); continue
        ocfg_p = odir / "config.json"
        ocfg = json.loads(ocfg_p.read_text()) if ocfg_p.exists() else {}
        try:
            ofac = OC(ocfg)
        except TypeError:
            ofac = OC()

        # ---- generated ----
        # Glob: a digit-leading family's module carries an n_ prefix so the module
        # name stays a valid identifier (n_3ddfa_v2_factory.py).
        gcands = sorted((stage / task / family / "factory").glob("*_factory.py"))
        gpath = gcands[0] if gcands else stage / task / family / "factory" / "missing.py"
        if not gpath.is_file():
            fail += 1; reasons["no generated factory"].append(variant); continue
        # custom_ops uses a relative import, so give the family dir a package identity.
        fam_pkg = f"fam_{task}_{family}".replace("-", "_").replace(".", "_")
        if fam_pkg not in sys.modules:
            pk = importlib.util.module_from_spec(
                importlib.machinery.ModuleSpec(fam_pkg, None, is_package=True))
            pk.__path__ = [str(stage / task / family)]
            sys.modules[fam_pkg] = pk
        gspec = importlib.util.spec_from_file_location(
            f"{fam_pkg}.factory_{abs(hash(variant))}", gpath)
        gmod = importlib.util.module_from_spec(gspec)
        sys.modules[gspec.name] = gmod
        try:
            gspec.loader.exec_module(gmod)
        except Exception as ex:
            fail += 1
            reasons[f"generated import: {type(ex).__name__}"].append(f"{variant}: {ex}")
            continue
        GC = next((o for n, o in vars(gmod).items()
                   if isinstance(o, type) and n.endswith("Factory") and n != "Factory"
                   and o.__module__ == gmod.__name__), None)
        try:
            gfac = GC(variant=variant)
        except Exception as ex:
            fail += 1
            reasons[f"generated ctor: {type(ex).__name__}"].append(f"{variant}: {ex}")
            continue

        problems = []
        try:
            orig, twin = processors(ofac, w, h), processors(ofac, w, h)
        except Exception as ex:
            fail += 1
            reasons[f"original raised: {type(ex).__name__}"].append(f"{variant}: {ex}")
            continue
        try:
            gen = processors(gfac, w, h)
        except Exception as ex:
            fail += 1
            reasons[f"generated raised: {type(ex).__name__}"].append(f"{variant}: {ex}")
            continue

        for role, _ in ROLES:
            if type(orig[role]) is not type(gen[role]):
                problems.append((role, "TYPE", f"{type(orig[role]).__name__} != "
                                               f"{type(gen[role]).__name__}"))
                continue
            ov, tv, gv = vars(orig[role]), vars(twin[role]), vars(gen[role])
            nondet = {k for k in set(ov) | set(tv) if repr(ov.get(k)) != repr(tv.get(k))}
            diff = {k for k in set(ov) | set(gv)
                    if repr(ov.get(k)) != repr(gv.get(k))} - nondet - {"config"}
            if diff:
                problems.append((role, "ATTRS", sorted(diff)[:5]))
        if problems:
            fail += 1
            reasons[str(sorted({p[1] for p in problems}))].append(f"{variant} {problems}")
        else:
            ok += 1

    print(f"variants                  : {len(specs)}")
    print(f"  comparable              : {ok + fail}")
    print(f"    generated == original : {ok}")
    print(f"    DIFFERENT             : {fail}")
    print(f"  no original (new since  : {len(no_original)}")
    print(f"   the restructure)")
    print()
    for kind, items in sorted(reasons.items(), key=lambda x: -len(x[1])):
        print(f"  {len(items):4d}  {kind}")
        for it in items[:3]:
            print(f"          {it}")
    if no_original:
        print(f"  {len(no_original):4d}  no original factory -- new variants, nothing "
              "to compare against")
        for it in sorted(no_original)[:3]:
            print(f"          {it}")
    # Only a real divergence fails: an absent original is information, not a defect.
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
