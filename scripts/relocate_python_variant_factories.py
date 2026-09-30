#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Move each Python family factory into its variant folders.

C++ examples keep one factory header beside the variant entry points. This
script does the same for Python: ``<family>/<variant>/factory/<variant>_factory.py``
replaces the shared ``<family>/factory/``. Family-level ``<family>_sync.py``
entry points are removed. ``custom_ops.py`` is copied into every variant of a
family that uses it, because the factory loads it from its parent directory.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from pathlib import Path

_KINDS = (
    "_sync.py",
    "_async.py",
    "_sync_cpp_postprocess.py",
    "_async_cpp_postprocess.py",
)
_CLASS_RE = re.compile(r"^from \.\S+ import (\w+)\s*$", re.M)


def _factory_class(factory_dir: Path) -> str:
    init_text = (factory_dir / "__init__.py").read_text(encoding="utf-8")
    match = _CLASS_RE.search(init_text)
    if match is None:
        raise RuntimeError(f"no factory export in {factory_dir / '__init__.py'}")
    return match.group(1)


def _init_text(factory_filename: str, class_name: str) -> str:
    module_name = "dxapp_factory_" + re.sub(
        r"[^0-9A-Za-z_]", "_", Path(factory_filename).stem)
    return (
        "import importlib.util\n"
        "from pathlib import Path\n"
        "\n"
        f"_FACTORY_FILE = Path(__file__).with_name({factory_filename!r})\n"
        "_SPEC = importlib.util.spec_from_file_location(\n"
        f"    {module_name!r}, _FACTORY_FILE)\n"
        "if _SPEC is None or _SPEC.loader is None:\n"
        "    raise ImportError(f'cannot load variant factory {_FACTORY_FILE}')\n"
        "_MODULE = importlib.util.module_from_spec(_SPEC)\n"
        "_SPEC.loader.exec_module(_MODULE)\n"
        f"{class_name} = getattr(_MODULE, {class_name!r})\n"
        f"__all__ = [{class_name!r}]\n"
    )


def _variant_dirs(family_dir: Path) -> list[Path]:
    return sorted(
        child for child in family_dir.iterdir()
        if child.is_dir() and (child / "config.json").is_file()
    )


def relocate_family(family_dir: Path) -> int:
    """Copy the family factory into each variant. Returns variants updated."""
    factory_dir = family_dir / "factory"
    sources = sorted(factory_dir.glob("*_factory.py")) if factory_dir.is_dir() else []
    if len(sources) != 1:
        return 0
    source = sources[0]
    class_name = _factory_class(factory_dir)
    body = source.read_text(encoding="utf-8")
    custom_ops = family_dir / "custom_ops.py"
    written = 0
    for variant_dir in _variant_dirs(family_dir):
        factory_name = f"{variant_dir.name}_factory.py"
        dest_dir = variant_dir / "factory"
        dest_dir.mkdir(exist_ok=True)
        (dest_dir / factory_name).write_text(body, encoding="utf-8")
        (dest_dir / "__init__.py").write_text(
            _init_text(factory_name, class_name), encoding="utf-8")
        if custom_ops.is_file():
            shutil.copy2(custom_ops, variant_dir / "custom_ops.py")
        written += 1
    shutil.rmtree(factory_dir)
    if custom_ops.is_file():
        custom_ops.unlink()
    family = family_dir.name
    for suffix in _KINDS:
        entry = family_dir / f"{family}{suffix}"
        if entry.is_file():
            entry.unlink()
    return written


def relocate_tree(root: Path) -> int:
    """Relocate every family under a ``python_example`` root. Returns count."""
    updated = 0
    if not root.is_dir():
        return 0
    for task_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if task_dir.name in {"common", "__pycache__"} or task_dir.name.startswith("."):
            continue
        for family_dir in sorted(path for path in task_dir.iterdir() if path.is_dir()):
            updated += relocate_family(family_dir)
    return updated


def _self_check() -> None:
    spec = importlib.util.spec_from_file_location("relocate_self", __file__)
    if spec is None or spec.loader is None:
        raise RuntimeError("relocator failed to load itself")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <python_example_root>", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    count = relocate_tree(root)
    print(f"relocated_variants={count} root={root}")
    return 0 if count else 1


if __name__ == "__main__":
    _self_check()
    sys.exit(main(sys.argv))
