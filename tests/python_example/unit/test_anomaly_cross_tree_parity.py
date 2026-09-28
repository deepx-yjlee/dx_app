# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""The two trees must agree on what an anomaly map IS.

They did not. Python moved the efficientad family onto EfficientADPostprocessor --
teacher, student and autoencoder combined, which is the published method -- while the
C++ tree kept one network's feature magnitude behind a DepthResult and the depth
runner. Measured on the same frame and the same NPU outputs, that produced score
0.8992 against 0.0051 and a visibly different render (MAGMA at alpha 1.0, no label).

Numbers cannot be checked here -- that needs the NPU, and the cross-tree comparison is
run with DXAPP_VERIFY=1 -- so this pins the STRUCTURE that made them diverge: the
pieces exist in both trees, both anomaly families are wired to them, and neither is
routed back through the depth runner.
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CPP = PROJECT_ROOT / "src" / "cpp_example"
PY = PROJECT_ROOT / "src" / "python_example"
FAMILIES = ("efficientad", "patchcore")


def _read(path: Path) -> str:
    assert path.is_file(), f"missing: {path.relative_to(PROJECT_ROOT)}"
    return path.read_text(encoding="utf-8")


def test_both_trees_carry_the_three_network_postprocessor():
    assert "0.5" in _read(CPP / "common/processors/efficientad_postprocessor.hpp")
    assert "class EfficientADPostprocessor" in _read(
        CPP / "common/processors/efficientad_postprocessor.hpp")
    assert "class EfficientADPostprocessor" in _read(
        PY / "common/processors/efficientad_postprocessor.py")


def test_both_trees_carry_an_anomaly_visualizer():
    """The depth visualizer is opaque with MAGMA, which hides the frame."""
    cpp = _read(CPP / "common/visualizers/anomaly_visualizer.hpp")
    py = _read(PY / "common/visualizers/anomaly_visualizer.py")
    for text, name in ((cpp, "C++"), (py, "Python")):
        assert "JET" in text, name
        assert "relative severity" in text, name


def test_the_anomaly_families_do_not_use_the_depth_runner():
    for family in FAMILIES:
        for kind in ("sync", "async"):
            entry = _read(CPP / "anomaly_detection" / family / f"{family}_{kind}.cpp")
            assert f"{kind}_anomaly_runner.hpp" in entry, (family, kind)
            assert "depth_runner" not in entry, (family, kind)


def test_the_anomaly_factories_produce_an_anomaly_result():
    for family in FAMILIES:
        text = _read(CPP / "anomaly_detection" / family / "factory"
                     / f"{family}_factory.hpp")
        assert "IAnomalyDetectionFactory" in text, family
        assert "AnomalyVisualizer" in text, family
        assert "DepthResult" not in text, family


def test_efficientad_declares_its_companions_in_both_trees():
    """One -m, three engines: the factory is what says so."""
    assert "getCompanionModels" in _read(
        CPP / "anomaly_detection/efficientad/factory/efficientad_factory.hpp")
    assert "get_companion_models" in _read(
        PY / "anomaly_detection/efficientad/factory/efficientad_factory.py")


def test_both_runners_resolve_companions_and_patchcore_declares_none():
    assert "resolveCompanionModels" in _read(
        CPP / "common/runner/sync_anomaly_runner.hpp")
    assert "resolveCompanionModels" in _read(
        CPP / "common/runner/async_anomaly_runner.hpp")
    assert "resolve_companion_models" in _read(PY / "common/runner/sync_runner.py")
    # PatchCore is one network on purpose: its metric needs a memory bank, not a model.
    assert "getCompanionModels" not in _read(
        CPP / "anomaly_detection/patchcore/factory/patchcore_factory.hpp")


def test_an_anomaly_result_can_be_dumped_for_cross_tree_comparison():
    """Neither tree serialised this type, which is how the drift went unnoticed."""
    assert "serializeAnomaly" in _read(CPP / "common/utility/verify_serialize.hpp")
    assert '"AnomalyResult"' in _read(PY / "common/runner/verify_serialize.py")
