# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""``generate_cpp_family_layout.py --variant-scope`` scopes each variant's C++ factory.

Two variants of one family both define ``dxapp::<Family>Factory`` inline in a header.
Linked into one program, the linker keeps one of the two class bodies without a
diagnostic, so one variant silently runs the other's postprocessor. The mode wraps each
variant's headers in ``dxapp::v_<variant>`` and qualifies its entry points; it also
comments ``create*()`` parameters a body never uses (``-Wunused-parameter``).

The tree is built in ``tmp_path``: nothing here reads or writes ``src/cpp_example``.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "cpp_gen_variant_scope", PROJECT_ROOT / "scripts" / "generate_cpp_family_layout.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

FACTORY = """\
/**
 * @file {variant}_factory.hpp
 */

#ifndef {guard}_FACTORY_HPP
#define {guard}_FACTORY_HPP

#include "common/base/i_factory.hpp"
{helper_include}
namespace dxapp {{

class FamFactory : public IDetectionFactory {{
public:
    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {{
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }}

    PostprocessorPtr<DetectionResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {{
{post_body}
    }}

    VisualizerPtr<DetectionResult> createVisualizer() override {{
        return std::make_unique<DetectionVisualizer>();
    }}

    std::string getModelName() const override {{ return "{variant}"; }}
}};

}}  // namespace dxapp

#endif  // {guard}_FACTORY_HPP
"""

POST_USES_ALL = ("        return std::make_unique<Post>(input_width, input_height,"
                 " is_ort_configured);")
POST_USES_WIDTH = ("        // input_height is implied by the square input.\n"
                   "        return std::make_unique<Post>(input_width);")

HELPER = """\
#ifndef {old_guard}
#define {old_guard}

#include <vector>

namespace dxapp {{

class FamTracker {{
public:
    int size() const {{ return 0; }}
}};

}}  // namespace dxapp

#endif  // {old_guard}
"""

ENTRY = """\
#include "factory/{variant}_factory.hpp"
#include "common/runner/{kind}_detection_runner.hpp"

int main(int argc, char* argv[]) {{
    auto factory = std::make_unique<dxapp::FamFactory>();
    dxapp::{Kind}DetectionRunner<dxapp::FamFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}}
"""


def _guard(variant: str) -> str:
    g = "".join(c if c.isalnum() else "_" for c in variant).upper()
    return g if g[:1].isalpha() else "DXAPP_" + g


def add_variant(cpp: Path, variant: str, post_body: str = POST_USES_ALL,
                helper: str | None = None) -> Path:
    vdir = cpp / "object_detection" / "fam" / variant
    (vdir / "factory").mkdir(parents=True)
    include = f'#include "{helper}.hpp"\n' if helper else ""
    (vdir / "factory" / f"{variant}_factory.hpp").write_text(
        FACTORY.format(variant=variant, guard=_guard(variant), helper_include=include,
                       post_body=post_body), encoding="utf-8")
    if helper:
        (vdir / "factory" / f"{helper}.hpp").write_text(
            HELPER.format(old_guard=helper.upper() + "_HPP"), encoding="utf-8")
    for kind in ("sync", "async"):
        (vdir / f"{variant}_{kind}.cpp").write_text(
            ENTRY.format(variant=variant, kind=kind, Kind=kind.capitalize()),
            encoding="utf-8")
    return vdir


@pytest.fixture
def cpp(tmp_path: Path) -> Path:
    root = tmp_path / "src" / "cpp_example"
    (root / "common").mkdir(parents=True)
    add_variant(root, "a-1_64x64", helper="fam_tracker")
    add_variant(root, "b_2_64x64", post_body=POST_USES_WIDTH)
    add_variant(root, "3x_64x64", helper="fam_tracker")
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def run(root: Path, *extra: str) -> int:
    return gen.main(["--variant-scope", str(root), *extra])


def header(root: Path, variant: str, name: str | None = None) -> str:
    f = root / "object_detection" / "fam" / variant / "factory" / (
        name or f"{variant}_factory.hpp")
    return f.read_text(encoding="utf-8")


def test_each_header_is_wrapped_in_its_variant_namespace_inside_dxapp(cpp):
    assert run(cpp) == 0
    for variant, ns in (("a-1_64x64", "v_a_1_64x64"), ("b_2_64x64", "v_b_2_64x64"),
                        ("3x_64x64", "v_3x_64x64")):
        text = header(cpp, variant)
        assert f"namespace dxapp {{\nnamespace {ns} {{\n" in text
        assert f"\n}}  // namespace {ns}\n}}  // namespace dxapp\n" in text
        assert text.count(f"namespace {ns} {{") == 1
    helper = header(cpp, "a-1_64x64", "fam_tracker.hpp")
    assert "namespace dxapp {\nnamespace v_a_1_64x64 {\n" in helper
    assert "\n}  // namespace v_a_1_64x64\n}  // namespace dxapp\n" in helper


def test_a_helper_header_gets_a_per_variant_guard(cpp):
    assert run(cpp) == 0
    helper = header(cpp, "a-1_64x64", "fam_tracker.hpp")
    assert "#ifndef A_1_64X64_FAM_TRACKER_HPP\n#define A_1_64X64_FAM_TRACKER_HPP\n" in helper
    assert "#endif  // A_1_64X64_FAM_TRACKER_HPP" in helper
    assert "FAM_TRACKER_HPP" not in helper.replace("A_1_64X64_FAM_TRACKER_HPP", "")
    digit = header(cpp, "3x_64x64", "fam_tracker.hpp")
    assert "#ifndef DXAPP_3X_64X64_FAM_TRACKER_HPP\n" in digit
    assert "#endif  // DXAPP_3X_64X64_FAM_TRACKER_HPP" in digit
    # The factory guards are per-variant already and stay as they are.
    assert "#ifndef A_1_64X64_FACTORY_HPP" in header(cpp, "a-1_64x64")
    assert "#ifndef DXAPP_3X_64X64_FACTORY_HPP" in header(cpp, "3x_64x64")


def test_only_parameters_the_body_does_not_name_are_commented(cpp):
    assert run(cpp) == 0
    used = header(cpp, "a-1_64x64")
    assert "createPostprocessor(\n        int input_width, int input_height, " \
           "bool is_ort_configured = false) override" in used
    unused = header(cpp, "b_2_64x64")
    # A mention in a comment is not a use: the compiler still warns.
    assert "createPostprocessor(\n        int input_width, int /*input_height*/, " \
           "bool /*is_ort_configured*/ = false) override" in unused
    assert "createPreprocessor(int input_width, int input_height) override" in unused
    assert "createVisualizer() override" in unused


def test_entry_points_name_the_scoped_factory(cpp):
    assert run(cpp) == 0
    vdir = cpp / "object_detection" / "fam" / "a-1_64x64"
    for kind in ("sync", "async"):
        text = (vdir / f"a-1_64x64_{kind}.cpp").read_text(encoding="utf-8")
        assert text.count("dxapp::v_a_1_64x64::FamFactory") == 2
        assert "dxapp::FamFactory" not in text
        assert f"dxapp::{kind.capitalize()}DetectionRunner<" in text


def test_a_second_run_changes_nothing(cpp, capsys):
    assert run(cpp) == 0
    first = snapshot(cpp)
    capsys.readouterr()
    assert run(cpp) == 0
    assert snapshot(cpp) == first
    assert "0 changed" in capsys.readouterr().out


def test_check_fails_before_the_run_and_passes_after(cpp, capsys):
    before = snapshot(cpp)
    assert run(cpp, "--check") == 1
    assert snapshot(cpp) == before, "--check wrote files"
    out = capsys.readouterr().out
    assert "--variant-scope" in out, "no fix command"
    assert run(cpp) == 0
    assert run(cpp, "--check") == 0
    assert gen.namespace_problems(cpp) == []
    assert gen.parameter_problems(cpp) == []


def test_a_header_with_two_dxapp_namespaces_is_refused(cpp, capsys):
    f = cpp / "object_detection" / "fam" / "b_2_64x64" / "factory" / "b_2_64x64_factory.hpp"
    f.write_text(f.read_text(encoding="utf-8").replace(
        "#endif", "namespace dxapp {\nclass Extra {};\n}  // namespace dxapp\n\n#endif"),
        encoding="utf-8")
    before = snapshot(cpp)
    assert run(cpp) != 0
    assert snapshot(cpp) == before, "a refused run wrote files"
    assert "b_2_64x64_factory.hpp" in capsys.readouterr().out


def test_two_variants_mapping_to_one_namespace_are_refused(tmp_path, capsys):
    root = tmp_path / "src" / "cpp_example"
    (root / "common").mkdir(parents=True)
    add_variant(root, "a-1_64x64")
    add_variant(root, "a_1_64x64")
    before = snapshot(root)
    assert run(root) != 0
    assert snapshot(root) == before
    out = capsys.readouterr().out
    assert "v_a_1_64x64" in out and "a-1_64x64" in out and "a_1_64x64" in out


def test_a_root_without_common_is_refused(tmp_path, capsys):
    root = tmp_path / "somewhere"
    add_variant(root, "a-1_64x64")
    before = snapshot(root)
    assert run(root) != 0
    assert snapshot(root) == before
    assert "common/" in capsys.readouterr().out


def test_a_class_outside_the_variant_namespace_fails_check(cpp, capsys):
    assert run(cpp) == 0
    f = cpp / "object_detection" / "fam" / "a-1_64x64" / "factory" / "a-1_64x64_factory.hpp"
    f.write_text(f.read_text(encoding="utf-8").replace(
        "}  // namespace v_a_1_64x64\n",
        "}  // namespace v_a_1_64x64\n\nclass Stray {\n};\n"), encoding="utf-8")
    capsys.readouterr()
    assert run(cpp, "--check") == 1
    out = capsys.readouterr().out
    assert "Stray" in out and "a-1_64x64_factory.hpp" in out
    problems = gen.namespace_problems(cpp)
    assert len(problems) == 1 and "Stray" in problems[0]
    assert gen.parameter_problems(cpp) == []


def test_an_unused_parameter_is_reported_apart_from_namespace_problems(cpp, capsys):
    assert run(cpp) == 0
    f = cpp / "object_detection" / "fam" / "b_2_64x64" / "factory" / "b_2_64x64_factory.hpp"
    f.write_text(f.read_text(encoding="utf-8").replace("/*input_height*/", "input_height"),
                 encoding="utf-8")
    capsys.readouterr()
    assert run(cpp, "--check") == 1
    out = capsys.readouterr().out
    assert gen.namespace_problems(cpp) == []
    problems = gen.parameter_problems(cpp)
    assert len(problems) == 1
    assert "b_2_64x64_factory.hpp" in problems[0] and "input_height" in problems[0]
    assert "createPostprocessor" in problems[0]
    assert "namespace problems" not in out and "parameter problems" in out
