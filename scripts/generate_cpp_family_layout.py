#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Generate the dx-modelzoo family/variant layout for src/cpp_example.

Mirrors scripts/generate_family_layout.py on the C++ side, emitting per
``<task>/<family>/``::

    variants/<dxnn-stem>.json      the same variant configs the python tree uses
    factory/<family>_factory.hpp   one factory for the family
    <family>_sync.cpp, <family>_async.cpp

Two constraints shape this:

* There is no ``ast`` for C++, so nothing is re-derived. The donor variant's factory is
  carried over verbatim and only its class name, include guard and role bodies are
  rewritten. Where a family's variants disagree, each variant's ORIGINAL body is spliced
  into a branch, so behaviour is preserved by construction.
* The 26 shared runner headers are left untouched. The variant is selected in the
  generated ``main()``, which already has ``argv`` -- and because a variant key IS the
  ``.dxnn`` stem, the model path alone identifies it. No ``--variant`` flag, no runner
  change.

Measured: of the 89 families, bodies agree outright in most; 5 roles across 5 families
differ in both class and argument list (retinaface pre, yolov5_seg post, nanodet post,
yolov5_pose post, espcn pre), which is why the dispatch splices whole bodies rather than
switching a class name.

Usage:
    python3 scripts/generate_cpp_family_layout.py --out /tmp/stage_cpp
    python3 scripts/generate_cpp_family_layout.py --out /tmp/stage_cpp --orig /tmp/orig
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "model_registry.json"
SPECS = ROOT / "tests" / "data" / "processor_specs.json"
CPP_SRC = ROOT / "src" / "cpp_example"
SUFFIX_RULES = (r"_q_lite$", r"_\d+$")

ROLES = ("createPreprocessor", "createPostprocessor", "createVisualizer")


def pascal(family: str) -> str:
    parts = [p for p in family.split("_") if p]
    name = "".join(p[:1].upper() + p[1:] for p in parts)
    return name if name[:1].isalpha() else "N" + name


def existing_dirs(root: Path) -> dict[str, str]:
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


def role_block(text: str, role: str) -> tuple[int, int, str] | None:
    """``(body_start, body_end, body)`` for one create* method, brace-matched.

    Index-based rather than string-based: reconstructing "signature + { + body + }" to
    search for loses the exact whitespace before the brace, so the splice silently
    matched nothing and every dispatch was dropped.
    """
    m = re.search(role + r"\s*\([^)]*\)\s*(?:override)?\s*\{", text, re.S)
    if not m:
        return None
    open_brace = m.end() - 1
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return open_brace + 1, i, text[open_brace + 1:i]
    return None


def private_members(text: str) -> list[str]:
    """Member declarations from a factory's private section.

    A spliced body may reference a member only ITS OWN class declared -- yolov5's
    dispatch pulled in a body using ``max_nms_candidates_`` while the donor class had no
    such member, and the target failed to compile. The generated class therefore unions
    the private members of every variant in the family.
    """
    m = re.search(r"\nprivate:\n(.*?)\n\};", text, re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).split("\n"):
        t = line.strip()
        if t and not t.startswith("//") and t.endswith(";"):
            out.append(t)
    return out


def member_name(decl: str) -> str:
    m = re.search(r"(\w+)_\s*(?:\{[^}]*\})?\s*;", decl)
    return m.group(1) + "_" if m else decl


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--orig", default=None,
                    help="root holding the ORIGINAL src/cpp_example, needed once the "
                         "restructure has replaced the working tree")
    ap.add_argument("--py-stage", default=None,
                    help="generated python tree, to copy variant configs from "
                         "(default: src/python_example)")
    a = ap.parse_args()

    src_root = (Path(a.orig) / "src" / "cpp_example") if a.orig else CPP_SRC
    py_root = Path(a.py_stage) if a.py_stage else (ROOT / "src" / "python_example")
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    table = existing_dirs(src_root)

    fams: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    unresolved = []
    for e in reg:
        d = resolve_dir(e["model_name"], table)
        if d is None:
            unresolved.append(e["model_name"])
            continue
        fams[(e["task"], e["family"])].append({**e, "_dir": d, "_task_dir": table[d]})
    if unresolved:
        print(f"ABORT: unresolved cpp dirs for {unresolved}")
        return 1

    n_var = n_dispatch = 0
    n_carried = [0]
    dispatched: dict[str, list[str]] = {}

    for (task, family), members in sorted(fams.items()):
        fdir = out / task / family
        (fdir / "variants").mkdir(parents=True, exist_ok=True)
        (fdir / "factory").mkdir(parents=True, exist_ok=True)

        # Variant configs: reuse the python tree's, so both trees read one description.
        for e in members:
            srcj = py_root / task / family / "variants" / f"{e['variant']}.json"
            if srcj.is_file():
                (fdir / "variants" / f"{e['variant']}.json").write_bytes(srcj.read_bytes())
                n_var += 1

        # Donor = alphabetically first canonical variant with a factory.
        donor = None
        bodies: dict[str, dict[str, str]] = {r: {} for r in ROLES}
        # NOT "members": that name is already the family's member list, and
        # shadowing it made the donor loop iterate this dict instead.
        priv_members: dict[str, str] = {}   # member name -> decl, first wins
        extra_includes: set[str] = set()
        for e in sorted(members, key=lambda x: x["variant"]):
            hp = sorted((src_root / e["_task_dir"] / e["_dir"] / "factory")
                        .glob("*_factory.hpp"))
            if not hp:
                continue
            txt = hp[0].read_text(encoding="utf-8", errors="ignore")
            if donor is None:
                donor = (e, hp[0], txt)
            for r in ROLES:
                blk = role_block(txt, r)
                if blk:
                    bodies[r][e["variant"]] = blk[2]
            for decl in private_members(txt):
                priv_members.setdefault(member_name(decl), decl)
            for inc in re.findall(r'#include\s+(["<][^">]+[">])', txt):
                extra_includes.add(inc)
        if donor is None:
            print(f"ABORT: no cpp factory for {task}/{family}")
            return 1
        de, dpath, dtxt = donor

        # The FACTORY class, not merely the first class: superpoint_factory.hpp
        # defines a tracker helper first, and renaming that left the factory without
        # any of its methods.
        _cands = re.findall(r"class\s+(\w*Factory)\s*:", dtxt) \
            or re.findall(r"class\s+(\w+)\s*:", dtxt)
        cls_old = _cands[0]
        cls_new = f"{pascal(family)}Factory"
        # A macro name may not start with a digit, so a digit-leading family gets the
        # same N prefix its C++ class and python module get.
        _g = family.upper()
        guard_new = (f"{_g}_FACTORY_HPP" if _g[:1].isalpha()
                     else f"N{_g}_FACTORY_HPP")
        body = dtxt
        body = re.sub(r"#ifndef\s+\w+_FACTORY_HPP", f"#ifndef {guard_new}", body)
        body = re.sub(r"#define\s+\w+_FACTORY_HPP", f"#define {guard_new}", body)
        body = re.sub(r"#endif\s*//\s*\w+_FACTORY_HPP", f"#endif  // {guard_new}", body)
        body = re.sub(rf"\b{re.escape(cls_old)}\b", cls_new, body)
        body = re.sub(r"@file\s+\S+", f"@file {family}_factory.hpp", body)

        # Splice a variant dispatch wherever the family's bodies disagree.
        fam_dispatch = []
        for r in ROLES:
            variants_bodies = bodies[r]
            distinct = {re.sub(r"\s+", " ", b).strip() for b in variants_bodies.values()}
            if len(distinct) <= 1:
                continue
            blk = role_block(body, r)
            if blk is None:
                continue
            default_v = de["variant"]
            branches = []
            seen: dict[str, str] = {}
            for v, b in sorted(variants_bodies.items()):
                key = re.sub(r"\s+", " ", b).strip()
                if v == default_v or key == re.sub(r"\s+", " ", variants_bodies[default_v]).strip():
                    continue
                seen.setdefault(key, v)
                branches.append((v, b))
            if not branches:
                continue
            disp = ["\n        // Variant dispatch: these variants' ORIGINAL bodies are",
                    "        // spliced verbatim, so no behaviour is re-derived."]
            for v, b in branches:
                disp.append(f'        if (variant_ == "{v}") {{{b}        }}')
            disp.append("        // default: " + default_v)
            new_body = "\n".join(disp) + variants_bodies[default_v]
            body = body[:blk[0]] + new_body + body[blk[1]:]
            fam_dispatch.append(r)

        # variant_ member + a constructor that accepts it. Both are anchored at the
        # FACTORY class, not at the first public:/private: in the file -- superpoint's
        # header defines a tracker helper first, and anchoring on the file put the
        # constructor inside that helper.
        _cls_at = body.index(f"class {cls_new}")
        _pub = body.index("public:", _cls_at) + len("public:")
        body = (body[:_pub]
                + "\n    /// The variant (a .dxnn stem) this factory should build for."
                  "\n    /// Empty means the family default. Set from main(), which"
                  "\n    /// is the only place that sees argv.\n"
                  f"    explicit {cls_new}(std::string variant)"
                  f" : variant_(std::move(variant)) {{}}\n"
                + body[_pub:])
        # Union every variant's private members so a spliced body always finds the
        # members its original class declared.
        donor_members = {member_name(d) for d in private_members(dtxt)}
        merged = ["    std::string variant_;"]
        merged += [f"    {decl}  // from a sibling variant in this family"
                   for name, decl in sorted(priv_members.items())
                   if name not in donor_members]
        _cls_at2 = body.index(f"class {cls_new}")
        _priv = body.find("\nprivate:", _cls_at2)
        if _priv != -1:
            _end = _priv + len("\nprivate:")
            body = body[:_end] + "\n" + "\n".join(merged) + body[_end:]
        else:
            body = body.replace("};\n\n}  // namespace dxapp",
                                "\nprivate:\n" + "\n".join(merged)
                                + "\n};\n\n}  // namespace dxapp", 1)
        # Includes a spliced body may need that the donor did not pull in.
        donor_includes = set(re.findall(r'#include\s+(["<][^">]+[">])', dtxt))
        need = sorted(extra_includes - donor_includes)
        if need:
            body = body.replace(
                "namespace dxapp {",
                "// Includes required by bodies spliced in from sibling variants.\n"
                + "\n".join(f"#include {i}" for i in need)
                + "\n\nnamespace dxapp {", 1)
        if "#include <string>" not in body:
            body = body.replace("namespace dxapp {", "#include <string>\n#include <utility>\n\nnamespace dxapp {", 1)

        (fdir / "factory" / f"{family}_factory.hpp").write_text(body, encoding="utf-8")
        if fam_dispatch:
            n_dispatch += 1
            dispatched[f"{task}/{family}"] = fam_dispatch

        # Carry over anything the generator does not produce. One such file exists --
        # superpoint_tracker.hpp, which superpoint_factory.hpp includes as a sibling --
        # and omitting it broke that target's compile.
        for e in members:
            sdir = src_root / e["_task_dir"] / e["_dir"]
            if not sdir.is_dir():
                continue
            for f in sdir.rglob("*"):
                if not f.is_file():
                    continue
                n = f.name
                if (n == "config.json" or n.endswith("_factory.hpp")
                        or n.endswith("_sync.cpp") or n.endswith("_async.cpp")):
                    continue
                dest = ((fdir / "factory" / n) if f.parent.name == "factory"
                        else (fdir / n))
                if not dest.exists():
                    dest.write_bytes(f.read_bytes())
                    n_carried[0] += 1

        # Entry points: derive the variant from the model path in main().
        for kind in ("sync", "async"):
            dentry = src_root / de["_task_dir"] / de["_dir"] / f"{de['_dir']}_{kind}.cpp"
            if not dentry.is_file():
                continue
            etxt = dentry.read_text(encoding="utf-8", errors="ignore")
            runner = re.search(r"dxapp::(\w*Runner)<", etxt)
            runner_name = runner.group(1) if runner else "SyncDetectionRunner"
            inc = re.search(r'#include "(common/runner/\w+\.hpp)"', etxt)
            runner_inc = inc.group(1) if inc else "common/runner/sync_detection_runner.hpp"
            (fdir / f"{family}_{kind}.cpp").write_text(f'''/**
 * @file {family}_{kind}.cpp
 * @brief {family} {kind} inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/{family}_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "{runner_inc}"

int main(int argc, char* argv[]) {{
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::{cls_new}>(variant);
    dxapp::{runner_name}<dxapp::{cls_new}> runner(std::move(factory));
    return runner.run(argc, argv);
}}
''', encoding="utf-8")

    print(f"out={out}")
    print(f"  families        : {len(fams)}")
    print(f"  variant configs : {n_var}")
    print(f"  extra files carried : {n_carried[0]}")
    print(f"  families with a variant dispatch: {n_dispatch}")
    for k, v in sorted(dispatched.items()):
        print(f"      {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
