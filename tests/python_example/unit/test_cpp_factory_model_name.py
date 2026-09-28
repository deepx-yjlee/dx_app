# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""A C++ family factory must name the variant it was actually given.

One example serves a whole family and the variant is the ``.dxnn`` stem, so
``variantFromArgs()`` reads it straight off ``-m``. ``getModelName()`` was left as the
literal the family was generated with, and every runner builds its artifact directory
and window title from that call:

    ./bin/arcface_sync -m .../arcface_mobilefacenet_112x112.dxnn --save
      -> artifacts/cpp_example/Arcface_iResNet100_ms1m_sync-image-...

The right model runs -- ``run_info.txt`` records its real path -- but every label
around it names a different one, and iResNet100 vs MobileFaceNet is a 20x difference in
size. Python's ``get_model_name()`` already returns ``self.variant``, so the two trees
also disagreed.

The literal stays as the fallback: a bare run with no ``-m`` has no variant to report.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CPP_FACTORIES = sorted((PROJECT_ROOT / "src" / "cpp_example").glob("*/*/factory/*.hpp"))

GET_MODEL_NAME = re.compile(r"getModelName\(\)\s*const\s*override\s*\{(.*?)\}", re.S)
CLASS = re.compile(r"^\s*class\s+(\w+)\s*:", re.M)


def _factory_bodies(path: Path):
    """``getModelName()`` bodies that belong to a FACTORY class.

    Three headers (yolopv2, superpoint, dope) also define a wrapper postprocessor in
    the same file, and ``IPostprocessor`` declares a ``getModelName()`` of its own.
    Those classes hold no variant and never see the command line -- their name is the
    algorithm's, not the model's -- so they are excluded by the only durable marker:
    whether the enclosing class actually declares ``std::string variant_;``.
    """
    text = path.read_text(encoding="utf-8")
    class_starts = [m.start() for m in CLASS.finditer(text)]
    bodies = []
    for match in GET_MODEL_NAME.finditer(text):
        before = [s for s in class_starts if s < match.start()]
        if not before:
            continue
        after = [s for s in class_starts if s > match.start()]
        body = text[before[-1]:(after[0] if after else len(text))]
        if "std::string variant_;" in body:
            bodies.append(match.group(1))
    return bodies


def test_the_factories_are_found_at_all():
    """A glob that silently matches nothing would make every test below vacuous."""
    assert len(CPP_FACTORIES) > 100


def test_every_factory_reports_the_variant_it_was_given():
    offenders = []
    for path in CPP_FACTORIES:
        for body in _factory_bodies(path):
            if "variant_" not in body:
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert not offenders, (
        "getModelName() ignores the selected variant in:\n  "
        + "\n  ".join(offenders)
    )


def test_a_family_fallback_literal_is_kept_for_a_run_without_m():
    """With no -m there is no variant, and the label must not go blank."""
    without_fallback = []
    for path in CPP_FACTORIES:
        for body in _factory_bodies(path):
            if "variant_" in body and not re.search(r'"[^"]+"', body):
                without_fallback.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert not without_fallback, (
        "getModelName() has no fallback name in:\n  " + "\n  ".join(without_fallback)
    )


def test_the_super_resolution_sample_override_still_matches():
    """getDefaultSampleImage() keys the low-res sample off this string.

    ``normalizeModelKey(modelName).compare(0, 10, "realesrgan")`` picks the 165x90 crop
    for Real-ESRGAN instead of the 275x150 one, so the returned name -- literal OR
    variant -- has to keep starting with "realesrgan" once punctuation is stripped.
    """
    configs = sorted((PROJECT_ROOT / "src" / "cpp_example" / "super_resolution"
                      / "realesrgan").glob("*/config.json"))
    assert configs, "realesrgan model folders not found"
    for config_path in configs:
        variant_name = config_path.parent.name
        key = "".join(c for c in variant_name.lower() if c.isalnum())
        assert key.startswith("realesrgan"), f"{variant_name} -> {key}"


def test_a_wrapper_postprocessors_name_is_left_alone():
    """IPostprocessor::getModelName() is a different interface with no variant.

    Rewriting it too does not even compile -- those classes have no variant_ -- and it
    would be wrong anyway: the wrapper names the algorithm it implements.
    """
    wrappers = [
        PROJECT_ROOT / "src/cpp_example/panoptic_driving_perception/yolopv2/factory/yolopv2_factory.hpp",
        PROJECT_ROOT / "src/cpp_example/keypoint_detection/superpoint/factory/superpoint_factory.hpp",
        PROJECT_ROOT / "src/cpp_example/object_pose_estimation/dope/factory/dope_factory.hpp",
    ]
    for path in wrappers:
        text = path.read_text(encoding="utf-8")
        # The wrapper keeps the one-line literal; the factory carries the variant form.
        assert re.search(r'getModelName\(\) const override \{ return "[^"]+"; \}', text), path
        assert "return variant_.empty() ?" in text, path


def test_the_generator_produces_the_same_thing_it_swept():
    """Pin the generator, not just its output.

    ``generate_cpp_family_layout.py`` needs the pre-restructure tree (``--orig``) to
    run at all, so it cannot be re-run here to prove the two agree. Its rewriter can be
    called directly, and that is what this asserts.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cpp_gen", PROJECT_ROOT / "scripts" / "generate_cpp_family_layout.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    source = (
        'class FooWrapper : public IPostprocessor<X> {\n'
        '    std::string getModelName() const override { return "Algo"; }\n'
        '};\n'
        '\n'
        'class BarFactory : public IFactory {\n'
        '    std::string getModelName() const override { return "BarDefault"; }\n'
        'private:\n'
        '    std::string variant_;\n'
        '};\n'
    )
    out = gen.variant_aware_model_name(source, "BarFactory")

    assert 'return "Algo"; }' in out, "the wrapper postprocessor must be left alone"
    assert 'return variant_.empty() ? "BarDefault" : variant_;' in out
    assert gen.variant_aware_model_name(out, "BarFactory") == out, "not idempotent"
