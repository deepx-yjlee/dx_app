# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Load an existing variant factory for one pipeline stage."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .pipeline import PipelineError, StageSpec

# src/python_example, parent of common/.
_EXAMPLE_ROOT = Path(__file__).resolve().parents[2]


def variant_factory_dir(spec: StageSpec, example_root: Path | None = None) -> Path:
    """Directory that holds ``factory/<variant>_factory.py``."""
    root = example_root or _EXAMPLE_ROOT
    return root / spec.task / spec.family / spec.variant / "factory"


def load_variant_factory(spec: StageSpec, example_root: Path | None = None) -> Any:
    """Instantiate the variant's IFactory class.

    The class name stays the family class. The factory package exports it from
    ``__all__``, which is how hyphenated variant modules are imported.
    """
    factory_dir = variant_factory_dir(spec, example_root)
    init_file = factory_dir / "__init__.py"
    if not init_file.is_file():
        raise PipelineError(
            f"stage {spec.id!r} has no factory package at {factory_dir}"
        )
    module_name = "dxapp_stage_" + "".join(
        ch if ch.isalnum() else "_" for ch in spec.variant
    )
    loader_spec = importlib.util.spec_from_file_location(module_name, init_file)
    if loader_spec is None or loader_spec.loader is None:
        raise PipelineError(f"cannot import factory for stage {spec.id!r}")
    module = importlib.util.module_from_spec(loader_spec)
    loader_spec.loader.exec_module(module)
    exported = getattr(module, "__all__", None) or []
    if not exported:
        raise PipelineError(f"factory package for stage {spec.id!r} exports nothing")
    factory_cls = getattr(module, exported[0])
    return factory_cls(variant=spec.variant)


def resolve_model_file(
    filename: str,
    pipeline_dir: Path | None = None,
    models_dir: Path | None = None,
) -> Path:
    """Find ``filename`` next to the pipeline, in ``models_dir``, or in the suite model store."""
    candidates: list[Path] = []
    if models_dir is not None:
        candidates.append(Path(models_dir) / filename)
    if pipeline_dir is not None:
        candidates.append(pipeline_dir / "models" / filename)
        candidates.append(pipeline_dir / filename)
    start = pipeline_dir or Path.cwd()
    for parent in (start, *start.parents):
        candidates.append(parent / "workspace" / "res" / "models" / filename)
        if parent.name == "dx-all-suite":
            break
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    searched = "\n  ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"model {filename!r} was not found. Searched:\n  {searched}"
    )


def resolve_stage_model(
    spec: StageSpec,
    pipeline_dir: Path | None = None,
    models_dir: Path | None = None,
) -> Path:
    """The stage's ``.dxnn`` path, as :func:`resolve_model_file` finds it.

    A miss raises :class:`PipelineError` naming the stage, its variant, every
    path tried, and how to get the file: ``./setup.sh --models <variant>`` for
    the variant's model-zoo file (its ``.dxnn`` stem), ``--models-dir`` for any
    other file. Same message as the C++ ``multi_model_run``.
    """
    try:
        return resolve_model_file(spec.model, pipeline_dir, models_dir)
    except FileNotFoundError as exc:
        if spec.model == spec.variant + ".dxnn":
            hint = f"-> Download: ./setup.sh --models {spec.variant}"
        else:
            hint = (f"-> {spec.model!r} is not the variant's model-zoo file;"
                    " put it in --models-dir")
        raise PipelineError(
            f"stage {spec.id!r} (variant {spec.variant}): {exc}\n  {hint}"
        ) from exc
