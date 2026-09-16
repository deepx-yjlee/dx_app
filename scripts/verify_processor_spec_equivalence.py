#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Prove the extracted processor spec reproduces each original factory.

Collapsing 353 per-variant factories into 89 family factories is only safe if the
variant config plus the family factory rebuild exactly what the original factory built.
This script is that proof: for every variant it imports the ORIGINAL factory by path,
constructs its three processors, rebuilds them from tests/data/processor_specs.json, and
compares class and attributes.

Two sources of false positives are handled explicitly:

* Non-deterministic attributes -- DetectionVisualizer builds a RANDOM 80x3 colour
  palette, so two instances of the same class with the same arguments already differ.
  The original's class is constructed a second time and whatever differs between those
  two is treated as noise.
* ``config`` itself, which the runner owns rather than the variant.

A residual mismatch means the variant needs family-factory CODE rather than config --
computed constants such as ``imagenet_mean`` or ``[m * 255.0 for m in mean]`` cannot be
expressed as literal kwargs. Those are expected and are what a family factory (the
equivalent of dx-modelzoo's ``custom_ops.py``) exists to hold.

Usage:
    ../venv-dx-runtime/bin/python scripts/verify_processor_spec_equivalence.py
"""

import importlib.util, json, sys, types, inspect
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'python_example'))
import common.processors as P
import common.visualizers as V

specs = json.load(open(ROOT / 'tests/data/processor_specs.json'))
ok = fail = skip = 0
problems = []

def build(spec, w, h, cfg):
    cls = getattr(P, spec['class'], None) or getattr(V, spec['class'], None)
    if cls is None:
        return ('MISSING_CLASS', spec['class'])
    kw = {k: v for k, v in spec['kwargs'].items() if not k.startswith(('_', '*'))}
    merged = {**cfg, **spec.get('config_overrides', {})}
    sig = inspect.signature(cls.__init__).parameters
    args = []
    if 'input_width' in sig: args.append(w)
    if 'input_height' in sig: args.append(h)
    if 'config' in sig: args.append(merged)
    try:
        return cls(*args, **kw)
    except Exception as ex:
        return ('CTOR_FAIL', f'{type(ex).__name__}: {ex}')

for variant, s in sorted(specs.items()):
    d, t = s['source_dir'], s['source_task']
    fdir = ROOT / 'src/python_example' / t / d / 'factory'
    cands = sorted(fdir.glob('*_factory.py'))
    if not cands:
        skip += 1; continue
    mspec = importlib.util.spec_from_file_location(f'f_{abs(hash(variant))}', cands[0])
    mod = importlib.util.module_from_spec(mspec)
    try:
        mspec.loader.exec_module(mod)
    except Exception as ex:
        problems.append((variant, 'IMPORT', f'{type(ex).__name__}: {ex}')); fail += 1; continue
    FC = next((o for n, o in vars(mod).items()
               if isinstance(o, type) and n.endswith('Factory') and n != 'Factory'
               and o.__module__ == mod.__name__), None)
    if FC is None:
        problems.append((variant, 'NO_FACTORY_CLASS', '')); fail += 1; continue
    cfgf = fdir.parent / 'config.json'
    cfg = json.loads(cfgf.read_text()) if cfgf.exists() else {}
    try:
        fac = FC(cfg)
    except TypeError:
        fac = FC()
    w = h = 640
    bad = []
    for role, meth in (('preprocessor','create_preprocessor'),
                       ('postprocessor','create_postprocessor'),
                       ('visualizer','create_visualizer')):
        try:
            orig = getattr(fac, meth)(w, h) if meth != 'create_visualizer' else fac.create_visualizer()
        except Exception as ex:
            bad.append((role, 'ORIG_FAIL', f'{type(ex).__name__}: {ex}')); continue
        rebuilt = build(s[role], w, h, cfg)
        if isinstance(rebuilt, tuple):
            bad.append((role, rebuilt[0], rebuilt[1])); continue
        if type(orig) is not type(rebuilt):
            bad.append((role, 'TYPE', f'{type(orig).__name__} != {type(rebuilt).__name__}')); continue
        ov, rv = vars(orig), vars(rebuilt)
        # Some attributes are non-deterministic per construction (DetectionVisualizer
        # builds a RANDOM 80x3 colour palette), so two instances of the SAME class with
        # the SAME args already differ. Construct the original's class a second time and
        # treat whatever differs between those two as noise, not as a spec mismatch.
        try:
            twin = getattr(fac, meth)(w, h) if meth != 'create_visualizer' else fac.create_visualizer()
            tv = vars(twin)
            nondet = {k for k in set(ov) | set(tv) if repr(ov.get(k)) != repr(tv.get(k))}
        except Exception:
            nondet = set()
        diff = {k for k in set(ov) | set(rv)
                if repr(ov.get(k)) != repr(rv.get(k))}
        diff -= {'config'} | nondet
        if diff:
            bad.append((role, 'ATTRS', sorted(diff)[:6]))
    if bad:
        problems.append((variant, 'MISMATCH', bad)); fail += 1
    else:
        ok += 1

print(f'equivalent: {ok}  mismatched: {fail}  skipped: {skip}  / {len(specs)}')
kinds = {}
for v, k, d in problems:
    key = k if k != 'MISMATCH' else tuple(sorted({b[1] for b in d}))
    kinds.setdefault(str(key), []).append(v)
print('\nproblem kinds:')
for k, vs in sorted(kinds.items(), key=lambda x: -len(x[1])):
    print(f'  {len(vs):4d}  {k}   e.g. {vs[:3]}')
print()
for v, k, d in problems:
    print(f'  {v}: {k} {d}')
