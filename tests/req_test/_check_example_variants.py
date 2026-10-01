#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""
SDKREQ-521/522 shared check — Python example completeness.

Verifies that every ``src/python_example/<task>/<family>/<variant>/`` directory
provides the full set of 4 entry scripts
(sync / async / sync_cpp_postprocess / async_cpp_postprocess).

Why structural (not model-name coverage): matching registry ``model_name`` →
``dxnn_file`` → example directory is a 3-hop fuzzy chain (version suffixes ``_1``,
mid-name renames, ``.dxnn`` that may not be downloaded on a given machine), which
produces false "missing" reports. Directory/variant presence is a pure source fact:
it needs no models downloaded and no name resolution, so it is 100% reliable.

Exit code: 0 = every dir complete (PASS), 1 = one or more incomplete (FAIL).
Prints a diagnostic line and, when incomplete, the offending dirs.
An informational ``supported_models`` vs ``example_dirs`` line is printed when the
registry is importable (never fails the check — visibility only).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))  # dx_app/
_EXROOT = os.path.join(_ROOT, "src", "python_example")

VARIANTS = ("sync", "async", "sync_cpp_postprocess", "async_cpp_postprocess")
_SKIP_DIRS = {"common", "build", "multi_model", "multi_model_graph"}


def _iter_variant_dirs():
    for task in sorted(os.listdir(_EXROOT)):
        task_path = os.path.join(_EXROOT, task)
        if not os.path.isdir(task_path) or task in _SKIP_DIRS or task.startswith("__"):
            continue
        for family in sorted(os.listdir(task_path)):
            family_path = os.path.join(task_path, family)
            if not os.path.isdir(family_path) or family.startswith("__"):
                continue
            for variant in sorted(os.listdir(family_path)):
                variant_path = os.path.join(family_path, variant)
                if not os.path.isdir(variant_path) or variant.startswith("__"):
                    continue
                if not os.path.isfile(os.path.join(variant_path, "config.json")):
                    continue
                yield task, family, variant, variant_path


def main() -> int:
    incomplete = []
    total = 0
    for task, family, variant, variant_path in _iter_variant_dirs():
        total += 1
        missing = [kind for kind in VARIANTS
                   if not os.path.exists(os.path.join(variant_path, f"{variant}_{kind}.py"))]
        if missing:
            incomplete.append(
                f"{task}/{family}/{variant}: missing {', '.join(missing)}")

    # Informational: registry model count vs example dir count (never fails).
    info = ""
    try:
        sys.path.insert(0, os.path.join(_ROOT, "tests"))
        from test_helpers.utils import load_registry  # noqa: E402
        info = f"  supported_models={len(load_registry())}"
    except Exception:
        pass

    print(f"example_dirs={total}  incomplete={len(incomplete)}{info}")
    for line in incomplete:
        print(f"  {line}")
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
