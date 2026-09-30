#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""
SDKREQ-521/522 shared check — Python example completeness.

Verifies that every ``src/python_example/<task>/<model>/`` directory provides the
full set of 4 variants (sync / async / sync_cpp_postprocess / async_cpp_postprocess).

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
_SKIP_DIRS = {"common", "build"}


def _iter_model_dirs():
    for task in sorted(os.listdir(_EXROOT)):
        tp = os.path.join(_EXROOT, task)
        if not os.path.isdir(tp) or task in _SKIP_DIRS or task.startswith("__"):
            continue
        for model in sorted(os.listdir(tp)):
            mp = os.path.join(tp, model)
            if not os.path.isdir(mp) or model.startswith("__"):
                continue
            yield task, model, mp


def main() -> int:
    incomplete = []
    total = 0
    for task, model, mp in _iter_model_dirs():
        total += 1
        missing = [v for v in VARIANTS
                   if not os.path.exists(os.path.join(mp, f"{model}_{v}.py"))]
        if missing:
            incomplete.append(f"{task}/{model}: missing {', '.join(missing)}")

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
