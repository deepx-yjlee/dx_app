#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Extract each python variant's processor spec from its existing factory.

A family factory can only replace 353 per-variant factories without losing behaviour if
every variant's ``(preprocessor, postprocessor, visualizer)`` class AND its non-default
constructor arguments are captured. 36 of 300 factories pass such arguments
(``SimpleResizePreprocessor(normalize_float=True)``,
``ZeroDCEPostprocessor({**config, "num_iterations": 4})``, SuperPoint's visualizer
thresholds, …), so dropping them would silently change results for those models.

This reads each factory with ``ast`` -- never by regex, and never by importing it, since
importing executes module-level code and needs the whole dependency tree present -- and
emits one JSON record per variant. The record is the input to the variant configs and the
oracle the generated family factories are checked against.

Usage:
    python3 scripts/extract_processor_specs.py                    # write + summary
    python3 scripts/extract_processor_specs.py --print yolov5s    # inspect one
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = PROJECT_ROOT / "config" / "model_registry.json"
PY_ROOT = PROJECT_ROOT / "src" / "python_example"
OUT = PROJECT_ROOT / "tests" / "data" / "processor_specs.json"

SUFFIX_RULES = (r"_q_lite$", r"_\d+$")
# Positional arguments every processor takes; they come from the runner, not the variant.
POSITIONAL_PASSTHROUGH = {"input_width", "input_height", "self.config", "config", "cfg",
                          "width", "height", "w", "h"}
FACTORY_METHODS = {
    "create_preprocessor": "preprocessor",
    "create_postprocessor": "postprocessor",
    "create_visualizer": "visualizer",
}


def existing_dirs() -> dict[str, str]:
    out: dict[str, str] = {}
    for task in sorted(PY_ROOT.iterdir()):
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


def _literal(node: ast.AST):
    """Best-effort literal value; ``None`` sentinel string when not a literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return f"<expr:{ast.unparse(node)}>"


def _locals_in(fn: ast.FunctionDef) -> dict[str, ast.AST]:
    """``{local name -> assigned expression}`` for simple single-target assignments.

    Several factories assemble the config into a local first::

        cfg = {**self.config, "num_iterations": 4}
        return ZeroDCEPostprocessor(input_width, input_height, cfg)

    Treating ``cfg`` as a plain passthrough token loses the override entirely, which
    silently dropped num_iterations=4 (ZeroDCE++), FastSAM's score/nms thresholds and
    two PPU anchor sets. The call's positionals are therefore resolved through this map
    before being classified.
    """
    out: dict[str, ast.AST] = {}
    for node in fn.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = node.value
    return out


def _spec_from_call(call: ast.Call, local_defs: dict[str, ast.AST] | None = None) -> dict:
    """Record the call SHAPE symbolically, not a guess at the signature.

    ``args`` keeps each positional in order as either a runner-supplied token
    (``"input_width"``, ``"input_height"``, ``"config"``) or a literal value, so a
    builder replays the exact original call instead of introspecting the signature and
    hoping. That guesswork is what produced spurious CTOR_FAILs for the SuperPoint and
    DOPE visualisers, whose first positional is not a width.
    """
    cls = getattr(call.func, "id", None) or getattr(call.func, "attr", "")
    local_defs = local_defs or {}
    args: list = []
    kwargs: dict = {}
    injected: dict = {}

    def _harvest_dict(d: ast.Dict) -> None:
        for k, v in zip(d.keys, d.values):
            if isinstance(k, ast.Constant):
                injected[k.value] = _literal(v)

    for arg in call.args:
        # Resolve a local alias to the expression it was assigned, so a config built
        # one line earlier is not mistaken for a bare passthrough.
        if isinstance(arg, ast.Name) and arg.id in local_defs:
            resolved = local_defs[arg.id]
            if isinstance(resolved, ast.Dict):
                _harvest_dict(resolved)
                args.append({"token": "config"})
                continue
            arg = resolved
        if isinstance(arg, ast.Name) and arg.id in POSITIONAL_PASSTHROUGH:
            args.append({"token": arg.id})
        elif isinstance(arg, ast.Attribute) and ast.unparse(arg) in POSITIONAL_PASSTHROUGH:
            args.append({"token": "config"})
        elif isinstance(arg, ast.Dict):         # {**self.config, "num_iterations": 4}
            _harvest_dict(arg)
            args.append({"token": "config"})
        else:
            args.append({"value": _literal(arg)})
    for kw in call.keywords:
        if kw.arg is None:                      # **something
            kwargs["**"] = ast.unparse(kw.value)
            continue
        val = kw.value
        if isinstance(val, ast.Name) and val.id in local_defs:
            val = local_defs[val.id]
        kwargs[kw.arg] = _literal(val)
    return {"class": cls, "args": args, "kwargs": kwargs, "config_overrides": injected}


def extract(path: Path) -> dict:
    """``{role -> spec}`` for one factory file."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    out: dict[str, dict] = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name not in FACTORY_METHODS:
            continue
        role = FACTORY_METHODS[fn.name]
        local_defs = _locals_in(fn)
        # The returned call is the processor; helper calls inside are ignored.
        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
                out[role] = _spec_from_call(node.value, local_defs)
                break
        else:
            calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
            if calls:
                out[role] = _spec_from_call(calls[-1], local_defs)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", dest="show", default=None, help="print one dir's spec")
    a = ap.parse_args()

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    table = existing_dirs()

    specs: dict[str, dict] = {}
    no_factory, no_roles = [], []
    for e in reg:
        d = resolve_dir(e["model_name"], table)
        if d is None:
            print(f"ABORT: unresolved dir for {e['model_name']}")
            return 1
        # Glob rather than assume ``{dir}_factory.py``: a digit-leading directory
        # carries an ``n_`` prefix on its module (n_3ddfa_v2_..._factory.py) so the
        # module name is a valid identifier.
        fdir = PY_ROOT / table[d] / d / "factory"
        cands = sorted(fdir.glob("*_factory.py")) if fdir.is_dir() else []
        if not cands:
            no_factory.append(e["model_name"])
            continue
        f = cands[0]
        roles = extract(f)
        missing = sorted(set(FACTORY_METHODS.values()) - set(roles))
        if missing:
            no_roles.append((d, missing))
        specs[e["variant"]] = dict(
            variant=e["variant"], model_name=e["model_name"], task=e["task"],
            family=e["family"], source_dir=d, source_task=table[d], **roles)

    if a.show:
        key = next((k for k, v in specs.items() if a.show in (k, v["source_dir"],
                                                              v["model_name"])), None)
        print(json.dumps(specs[key], indent=2) if key else f"not found: {a.show}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(specs, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    with_kwargs = [v for v in specs.values()
                   if any((v.get(r) or {}).get("kwargs") or (v.get(r) or {}).get("config_overrides")
                          for r in FACTORY_METHODS.values())]
    nonliteral = [
        v["variant"] for v in specs.values()
        for r in FACTORY_METHODS.values()
        if any(str(x).startswith("<expr:") for x in
               list((v.get(r) or {}).get("kwargs", {}).values())
               + [a.get("value") for a in (v.get(r) or {}).get("args", []) if "value" in a]
               + list((v.get(r) or {}).get("config_overrides", {}).values()))
    ]
    classes = collections.Counter(
        (v.get(r) or {}).get("class") for v in specs.values() for r in FACTORY_METHODS.values())
    print(f"wrote {OUT.relative_to(PROJECT_ROOT)}")
    print(f"  variants with a factory   : {len(specs)} / {len(reg)}")
    print(f"  entries sharing a dir     : {len(no_factory)} (no own factory file)")
    print(f"  factories missing a role  : {len(no_roles)} {no_roles[:5]}")
    print(f"  variants with non-default args: {len(with_kwargs)}")
    print(f"  distinct processor classes: {len([c for c in classes if c])}")
    print(f"  variants with a NON-LITERAL arg (need family code): {len(set(nonliteral))}")
    if nonliteral:
        print(f"    {sorted(set(nonliteral))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
