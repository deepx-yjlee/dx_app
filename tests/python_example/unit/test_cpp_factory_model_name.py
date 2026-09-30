# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Each C++ variant example names itself.

The executable, factory, and config live in ``<task>/<family>/<variant>/``.
``getModelName()`` returns that variant folder name, which is the ``.dxnn`` stem.
A wrapper postprocessor in the same header still names the algorithm, not the model.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CPP_FACTORIES = sorted(
    (PROJECT_ROOT / "src" / "cpp_example").glob("*/*/*/factory/*_factory.hpp")
)

GET_MODEL_NAME = re.compile(r"getModelName\(\)\s*const\s*override\s*\{(.*?)\}", re.S)
CLASS = re.compile(r"^\s*class\s+(\w+)\s*:", re.M)


def _factory_class_body(path: Path) -> str:
    """The class that builds the pipeline, not a wrapper postprocessor."""
    text = path.read_text(encoding="utf-8")
    class_starts = [m.start() for m in CLASS.finditer(text)]
    for match in GET_MODEL_NAME.finditer(text):
        before = [s for s in class_starts if s < match.start()]
        if not before:
            continue
        after = [s for s in class_starts if s > match.start()]
        body = text[before[-1]:(after[0] if after else len(text))]
        if "createPreprocessor" in body:
            return match.group(1)
    raise AssertionError(f"no factory getModelName() in {path}")


def test_the_factories_are_found_at_all():
    """A glob that silently matches nothing would make every test below vacuous."""
    assert len(CPP_FACTORIES) > 100


def test_every_factory_reports_its_variant_folder():
    offenders = []
    for path in CPP_FACTORIES:
        variant = path.parent.parent.name
        body = _factory_class_body(path)
        if f'"{variant}"' not in body:
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert not offenders, (
        "getModelName() does not return the variant folder in:\n  "
        + "\n  ".join(offenders)
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
        PROJECT_ROOT / "src/cpp_example/panoptic_driving_perception/yolopv2/yolopv2_384x640/factory/yolopv2_384x640_factory.hpp",
        PROJECT_ROOT / "src/cpp_example/keypoint_detection/superpoint/superpoint_480x640/factory/superpoint_480x640_factory.hpp",
        PROJECT_ROOT / "src/cpp_example/object_pose_estimation/dope/dope-hope-ketchup_480x640/factory/dope-hope-ketchup_480x640_factory.hpp",
    ]
    for path in wrappers:
        text = path.read_text(encoding="utf-8")
        assert re.search(r'getModelName\(\) const override \{ return "[^"]+"; \}', text), path
        assert "variant_" not in text, path


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
