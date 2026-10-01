#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Generate the dx-modelzoo family/variant layout for src/python_example.

Emits, per ``<task>/<family>/``:

    <variant>/config.json       one model folder per .dxnn stem
    <variant>/<variant>_{sync,async,sync_cpp_postprocess,async_cpp_postprocess}.py
    <variant>/factory/<variant>_factory.py
                                config-driven factory owned by that variant
    <variant>/custom_ops.py     ONLY for families config cannot express

340 of 352 variants rebuild identically from their variant config (proved by
scripts/verify_processor_spec_equivalence.py). The other 12, across 8 families, pass
computed arguments -- ``imagenet_mean``, ``[m * 255.0 for m in mean]``, PPU anchor
tables -- that cannot be reduced to literals. For those the generator copies the
variant's ORIGINAL factory module verbatim into ``custom_ops.py`` and has the family
factory delegate to it, so behaviour is preserved by construction rather than by a
re-derivation that might drift. That mirrors dx-modelzoo, where a family carries a
``custom_ops.py`` beside its per-variant configs.

Writes into a staging directory by default so the result can be inspected before any
existing tree is touched.

Usage:
    python3 scripts/generate_family_layout.py --out /tmp/stage
    python3 scripts/generate_family_layout.py --out src/python_example --in-place
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import shutil
import sys
from pathlib import Path

from relocate_python_variant_factories import relocate_tree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python_example"))
from common.variant_config import spec_is_buildable  # noqa: E402
# The legacy task-keyed tables are the behavioural oracle for default media and
# image-only-ness. They are read here and BAKED per variant, because the dx-modelzoo
# task rename breaks every one of their keys and two moves would change behaviour
# outright: reid/casvit_* -> image_classification (person_pair -> sample_dog) and
# embedding/eigenplaces-* -> super_resolution.
from common.runner.sync_runner import (  # noqa: E402
    _DEFAULT_SAMPLE_IMAGE as LEGACY_IMAGE,
    _DEFAULT_SAMPLE_VIDEO as LEGACY_VIDEO,
    _IMAGE_ONLY_TASKS as LEGACY_IMAGE_ONLY,
    _MODEL_SAMPLE_IMAGE_OVERRIDE as LEGACY_IMAGE_OVERRIDE,
)

REGISTRY = ROOT / "config" / "model_registry.json"
SPECS = ROOT / "tests" / "data" / "processor_specs.json"
PY_SRC = ROOT / "src" / "python_example"
ROLES = ("preprocessor", "postprocessor", "visualizer")
VARIANT_SCRIPTS = ("sync", "async", "sync_cpp_postprocess", "async_cpp_postprocess")


def pascal(family: str) -> str:
    """``yolov5`` -> ``Yolov5``; ``3ddfa_v2`` -> ``N3ddfaV2`` (identifier-safe)."""
    parts = [p for p in family.split("_") if p]
    name = "".join(p[:1].upper() + p[1:] for p in parts)
    return name if name[:1].isalpha() else "N" + name


def family_base(members: list[dict], specs: dict) -> tuple[str, list[str]]:
    """``(base expression, import lines)`` read from the family's own factories.

    Never guessed from the task: a task can mix bases (image_classification holds 110
    IClassificationFactory and 2 IEmbeddingFactory) and keypoint_detection,
    object_pose_estimation and panoptic_driving_perception subclass
    ``_FactoryConfigMixin`` rather than an IFactory, so a per-task table would silently
    re-base those families. Measured: 0 of 89 families mix bases internally.
    """
    for e in members:
        s_ = specs.get(e["variant"]) or {}
        bases = s_.get("factory_bases") or []
        if bases:
            imports = [i for i in (s_.get("imports") or [])
                       if any(b.split(".")[0] in i for b in bases)]
            return ", ".join(bases), imports
    return "object", []


def available_bases() -> set[str]:
    import common.base as cb
    return {n for n in dir(cb) if n.startswith("I")}


# --------------------------------------------------------------------- generation
def legacy_media(entry: dict, spec: dict) -> tuple[str | None, str | None, bool]:
    """``(default_image, default_video, image_only)`` as the legacy runner resolved it.

    ``task_legacy`` is the key, never the new task name: the runner's tables predate
    the rename. The per-model image override is matched as a lowercase-alphanumeric
    prefix, exactly as ``_resolve_default_sample_image`` does.
    """
    lt = entry["task_legacy"]
    # task_legacy indexes the runner's tables directly -- both spell every task
    # the same way, so no translation is needed.
    image = LEGACY_IMAGE.get(lt)
    norm = "".join(c for c in (spec.get("source_dir") or "").lower() if c.isalnum())
    for prefix, override in LEGACY_IMAGE_OVERRIDE.items():
        if norm.startswith("".join(c for c in prefix.lower() if c.isalnum())):
            image = override
            break
    video = LEGACY_VIDEO.get(lt)
    image_only = lt in LEGACY_IMAGE_ONLY
    return image, video, image_only


# Per-variant escapes from the legacy task tables. The tables key on task_legacy, so
# every clip variant inherits "embedding" -- image-only, compared against a reference
# image. That is right for the embedding variants and wrong for the one that carries a
# prompt bank: zero-shot classification is a per-frame label, so it runs on video like
# any classifier. Keyed by variant because the task name cannot express the difference.
VARIANT_MEDIA_OVERRIDE = {
    "clip-img_vit-b32_256x256_datacomp-s34b-b86k": {
        "image_only": False,
        "default_image": "sample/img/sample_dog.jpg",
        "default_video": "assets/videos/dogs.mp4",
        "include_stream_inputs": True,
    },
}


def variant_json(entry: dict, spec: dict) -> dict:
    default_image, default_video, legacy_image_only = legacy_media(entry, spec)
    return {
        "variant": entry["variant"],
        "dxnn_file": entry["dxnn_file"],
        "task": entry["task"],
        "family": entry["family"],
        "input_width": entry["input_width"],
        "input_height": entry["input_height"],
        # Taken from the legacy runner tables, not from the registry field: the
        # registry marks 17 variants image_only while the runner treats 12 of those as
        # image-only for CLI purposes and the rest only at runtime.
        "image_only": VARIANT_MEDIA_OVERRIDE.get(entry["variant"], {})
                      .get("image_only", legacy_image_only),
        "registry_image_only": entry["image_only"],
        "default_image": VARIANT_MEDIA_OVERRIDE.get(entry["variant"], {})
                         .get("default_image", default_image),
        "default_video": VARIANT_MEDIA_OVERRIDE.get(entry["variant"], {})
                         .get("default_video", default_video),
        "zoo_canonical": entry["zoo_canonical"],
        # Whether a .dxnn exists to download. 143 of the 499 variants are declared in
        # the registry but not published yet, and default_variant() needs to know:
        # picking the alphabetically first config would otherwise make a bare run of
        # clip / yolo11_pose / stdc_seg fail on a missing model where it used to work.
        "published": entry.get("published", True),
        # The on-disk config.json is authoritative: it is what the original factory
        # read. The registry field disagrees for 75 of 352 variants, and using it would
        # silently move e.g. FastSAM's score threshold from 0.7 to 0.4.
        "config": spec.get("dir_config") if spec.get("dir_config") is not None
        else (entry.get("config") or {}),
        "registry_config": entry.get("config") or {},
        "cli": {**(spec.get("cli") or {"include_stream_inputs": True,
                                       "include_output": False,
                                       "include_kitti_paths": False}),
                **({"include_stream_inputs": True}
                   if VARIANT_MEDIA_OVERRIDE.get(entry["variant"], {})
                       .get("include_stream_inputs") else {})},
        "preprocessor": spec.get("preprocessor"),
        "postprocessor": spec.get("postprocessor"),
        "visualizer": spec.get("visualizer"),
    }


FACTORY_TEMPLATE = '''"""{display} family factory.

One factory serves every variant of the ``{family}`` family: the per-variant
differences -- processor classes and their non-default arguments -- live in
``<variant>/config.json`` rather than in {n} near-identical factory files.
{custom_note}
"""
from pathlib import Path

{base_imports}
from common.variant_config import (
    build_processor,
    default_variant,
    load_variant_config,
)
{custom_import}_FAMILY_DIR = str(Path(__file__).resolve().parent.parent)


class {cls}({base}):
    """Config-driven factory for the {display} family."""

    def __init__(self, config: dict = None, variant: str = None):
        self.variant = variant or default_variant(_FAMILY_DIR)
        self.spec = load_variant_config(_FAMILY_DIR, self.variant)
        # The variant config supplies the defaults; an explicit config overrides them.
        self.config = {{**(self.spec.get("config") or {{}}), **(config or {{}})}}

    def _build(self, role, input_width, input_height):
{custom_branch}        return build_processor(
            self.spec[role],
            input_width=input_width,
            input_height=input_height,
            config=self.config,
        )

    def create_preprocessor(self, input_width: int, input_height: int):
        return self._build("preprocessor", input_width, input_height)

    def create_postprocessor(self, input_width: int, input_height: int):
        return self._build("postprocessor", input_width, input_height)

    def create_visualizer(self):
        return self._build("visualizer", self.spec["input_width"],
                           self.spec["input_height"])

    def get_model_name(self) -> str:
        return self.variant

    def get_task_type(self) -> str:
        return self.spec["task"]
{extra_methods}'''

# custom_ops.py sits at the FAMILY level, mirroring dx-modelzoo, while this factory
# lives one level down in factory/. A relative import would therefore resolve to
# factory.custom_ops and fail, so it is loaded by path.
CUSTOM_IMPORT = '''import importlib.util as _ilu

_CUSTOM_OPS_PATH = Path(__file__).resolve().parent.parent / "custom_ops.py"
_co_spec = _ilu.spec_from_file_location(
    __name__.rsplit(".", 1)[0] + "_custom_ops", _CUSTOM_OPS_PATH)
custom_ops = _ilu.module_from_spec(_co_spec)
_co_spec.loader.exec_module(custom_ops)

'''

CUSTOM_BRANCH = '''        # Variants whose arguments are computed rather than literal delegate to the
        # family's custom_ops.py, which holds their original factory verbatim.
        if self.variant in custom_ops.FACTORIES:
            delegate = custom_ops.FACTORIES[self.variant](self.config)
            if role == "visualizer":
                return delegate.create_visualizer()
            return getattr(delegate, "create_" + role)(input_width, input_height)
'''

# Finds common.runner.entry before the helper finishes path setup. A vendored
# ./common next to the script is inserted first; install_import_paths then puts
# the family factory directory ahead of the in-tree common root.
_ENTRY_BOOTSTRAP = '''import sys
from pathlib import Path

_script = Path(__file__).resolve()
# Vendored ./common (extract layout) wins; otherwise walk up to src/python_example.
_script_dir = _script.parent
for _cursor in (_script_dir, *_script_dir.parents):
    if (_cursor / "common" / "runner" / "entry.py").is_file():
        if str(_cursor) not in sys.path:
            sys.path.insert(0, str(_cursor))
        break

from common.runner.entry import install_import_paths, run_entry

install_import_paths(_script)
'''

ENTRY_TEMPLATE = '''#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""{display} {kind} inference.

One entry point serves the whole family; ``--variant`` picks the model::

    python {family}_{kind}.py --variant {example}
"""
''' + _ENTRY_BOOTSTRAP + '''
from factory import {cls}
from common.runner import {runner}


def main():
    run_entry(
        _script,
        factory_cls={cls},
        runner_cls={runner},
        description="{display} {kind} inference",
    )


if __name__ == "__main__":
    main()
'''

MODEL_ENTRY_TEMPLATE = '''#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""{variant} {kind} inference.

The variant is fixed to this folder. Run it from here with no PYTHONPATH::

    python {variant}_{kind}.py -i <image>
"""
''' + _ENTRY_BOOTSTRAP + '''
from factory import {cls}
from common.runner import {runner}

# Directory name is the .dxnn stem this script always builds.
_FIXED_VARIANT = "{variant}"


def main():
    run_entry(
        _script,
        factory_cls={cls},
        runner_cls={runner},
        description="{variant} {kind} inference",
        fixed_variant=_FIXED_VARIANT,
    )


if __name__ == "__main__":
    main()
'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--orig", default=None,
                    help="root holding the ORIGINAL src/python_example, needed once the "
                         "restructure has replaced the working tree. Restore it with "
                         "`git archive <sha> src/python_example | tar -x -C DIR`.")
    ap.add_argument("--in-place", action="store_true",
                    help="write into src/python_example itself (otherwise a staging dir)")
    a = ap.parse_args()
    global PY_SRC
    if a.orig:
        PY_SRC = Path(a.orig) / "src" / "python_example"

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    bases = available_bases()
    out = Path(a.out)
    if not a.in_place:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)

    fams: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for e in reg:
        fams[(e["task"], e["family"])].append(e)

    n_var = n_custom = 0
    n_carried = [0]
    unknown_base: set[str] = set()
    custom_fams: dict[str, list[str]] = {}

    for (task, family), members in sorted(fams.items()):
        fdir = out / task / family
        (fdir / "factory").mkdir(parents=True, exist_ok=True)
        legacy_variants = fdir / "variants"
        if legacy_variants.is_dir():
            shutil.rmtree(legacy_variants)

        needs_custom: list[dict] = []
        for e in members:
            spec = specs.get(e["variant"], {})
            model_dir = fdir / e["variant"]
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / "config.json").write_text(
                json.dumps(variant_json(e, spec), indent=2) + "\n", encoding="utf-8")
            n_var += 1
            if not all(spec_is_buildable(spec.get(r) or {}) for r in ROLES):
                needs_custom.append(e)

        # custom_ops.py: the original factory module of each non-expressible variant,
        # copied verbatim so behaviour is preserved by construction.
        if needs_custom:
            n_custom += 1
            custom_fams[f"{task}/{family}"] = [e["variant"] for e in needs_custom]
            # In-place regeneration keeps the custom_ops.py already in the tree.
            # The pre-restructure factory dirs it was copied from are gone, and
            # rewriting it from a partial checkout would drop variants.
            if not (fdir / "custom_ops.py").is_file():
                chunks, mapping = [], []
                for e in needs_custom:
                    s = specs[e["variant"]]
                    src_dir = PY_SRC / s["source_task"] / s["source_dir"] / "factory"
                    originals = sorted(src_dir.glob("*_factory.py"))
                    if not originals:
                        print(f"ABORT: {task}/{family} needs custom_ops.py but "
                              f"{src_dir} has no factory and none is in the tree")
                        return 1
                    orig = originals[0]
                    body = orig.read_text(encoding="utf-8")
                    cls_name = next(
                        (n.name for n in ast.walk(ast.parse(body))
                         if isinstance(n, ast.ClassDef) and n.name.endswith("Factory")),
                        None)
                    chunks.append(f"# ---- carried over verbatim from "
                                  f"{orig.relative_to(PY_SRC.parent.parent)} ----\n{body}")
                    mapping.append(f'    "{e["variant"]}": {cls_name},')
                (fdir / "custom_ops.py").write_text(
                    '"""Family-specific processor construction that a variant config cannot express.\n\n'
                    "These variants pass COMPUTED arguments -- an ``imagenet_mean`` constant, a\n"
                    "``[m * 255.0 for m in mean]`` comprehension, a PPU anchor table -- so they cannot be\n"
                    "reduced to literal JSON. Their original factory modules are carried over verbatim\n"
                    "below and the family factory delegates to them, which preserves behaviour by\n"
                    "construction rather than by a re-derivation that could drift.\n"
                    '"""\n\n' + "\n\n".join(chunks) +
                    "\n\n# variant -> the factory class that builds it\nFACTORIES = {\n"
                    + "\n".join(mapping) + "\n}\n", encoding="utf-8")

        # Carry over any non-standard methods the family's base requires (e.g.
        # get_num_keypoints for IFaceFactory / IPoseFactory).
        extra_methods = ""
        for e in members:
            ex = (specs.get(e["variant"]) or {}).get("extra_methods") or []
            if ex:
                extra_methods = "\n" + "\n\n".join(
                    "\n".join("    " + ln if ln.strip() else ln
                              for ln in m.splitlines()) for m in ex) + "\n"
                break

        base, base_imports = family_base(members, specs)
        for b in base.split(", "):
            if b not in bases and not b.startswith("_"):
                unknown_base.add(f"{task}/{family}:{b}")
        cls = f"{pascal(family)}Factory"
        # A module name may not start with a digit, so a digit-leading family gets an
        # n_ prefix on the FILE while the directory keeps the dx-modelzoo name. The
        # original tree used the same device (n_3ddfa_v2_..._factory.py).
        mod = f"{family}_factory" if family[:1].isalpha() else f"n_{family}_factory"
        (fdir / "factory" / f"{mod}.py").write_text(
            FACTORY_TEMPLATE.format(
                display=family, family=family, n=len(members), cls=cls,
                base=base, base_imports="\n".join(base_imports),
                custom_note=("\nVariants needing computed arguments delegate to "
                             "``custom_ops.py``." if needs_custom else ""),
                custom_import=(CUSTOM_IMPORT if needs_custom else ""),
                custom_branch=(CUSTOM_BRANCH if needs_custom else ""),
                extra_methods=extra_methods,
            ), encoding="utf-8")
        (fdir / "factory" / "__init__.py").write_text(
            f"from .{mod} import {cls}\n\n__all__ = [\"{cls}\"]\n",
            encoding="utf-8")
        (fdir / "__init__.py").write_text("", encoding="utf-8")

        # Carry over anything the generator does not itself produce -- READMEs, the
        # *_ort_off.py debug variants, calib_policy.py. Deleting a file the user put
        # there is not part of regrouping examples.
        generated_names = {"__init__.py", "config.json", f"{mod}.py",
                           "custom_ops.py"} | {
            f"{family}_{k}.py" for k in VARIANT_SCRIPTS}
        for e in members:
            sp_ = specs.get(e["variant"]) or {}
            src_dir = PY_SRC / sp_.get("source_task", "") / sp_.get("source_dir", "")
            if not src_dir.is_dir():
                continue
            for f in src_dir.rglob("*"):
                if not f.is_file() or "__pycache__" in f.parts or f.suffix == ".pyc":
                    continue
                name = f.name
                is_std = (name in generated_names
                          or name.endswith("_factory.py")
                          or any(name.endswith(f"_{k}.py") for k in VARIANT_SCRIPTS)
                          or name in {"__init__.py", "config.json"})
                if is_std:
                    continue
                dest = fdir / name
                if not dest.exists():
                    dest.write_bytes(f.read_bytes())
                    n_carried[0] += 1

        # The same choice default_variant() makes, for the same reason: a docstring
        # that tells the reader to run --variant <something unpublished> is an
        # instruction that cannot work. Falls back to the first when a family has no
        # published variant at all (the 23 entirely new ones).
        ordered = sorted(members, key=lambda e: e["variant"])
        example = next((e["variant"] for e in ordered
                        if e.get("published", True)), ordered[0]["variant"])
        for kind in VARIANT_SCRIPTS:
            runner = "AsyncRunner" if kind.startswith("async") else "SyncRunner"
            (fdir / f"{family}_{kind}.py").write_text(
                ENTRY_TEMPLATE.format(display=family, family=family, kind=kind,
                                      cls=cls, runner=runner, example=example),
                encoding="utf-8")
            for e in members:
                (fdir / e["variant"] / f"{e['variant']}_{kind}.py").write_text(
                    MODEL_ENTRY_TEMPLATE.format(
                        variant=e["variant"], kind=kind, cls=cls, runner=runner),
                    encoding="utf-8")

    print(f"out={out}")
    print(f"  families          : {len(fams)}")
    print(f"  variant configs   : {n_var}")
    print(f"  custom_ops families: {n_custom}")
    print(f"  extra files carried : {n_carried[0]}")
    for k, v in sorted(custom_fams.items()):
        print(f"      {k}: {v}")
    if unknown_base:
        print(f"  UNKNOWN IFactory bases (fell back): {sorted(unknown_base)}")
    # Family factories are a staging shape. The tree that ships matches C++:
    # each variant directory owns factory/ and the family entry scripts are gone.
    print(f"  variant factories : {relocate_tree(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
