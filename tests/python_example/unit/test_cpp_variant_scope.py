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
{helper_include}{pre}
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
{extra}
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
                helper: str | None = None, extra: str = "", pre: str = "",
                vdir: Path | None = None) -> Path:
    vdir = vdir or cpp / "object_detection" / "fam" / variant
    (vdir / "factory").mkdir(parents=True)
    include = f'#include "{helper}.hpp"\n' if helper else ""
    (vdir / "factory" / f"{variant}_factory.hpp").write_text(
        FACTORY.format(variant=variant, guard=_guard(variant), helper_include=include,
                       post_body=post_body, extra=extra, pre=pre), encoding="utf-8")
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


def test_a_factory_header_named_for_another_variant_fails_check(cpp, capsys):
    """A copied variant dir that kept its old header is no variant: it must not pass."""
    assert run(cpp) == 0
    add_variant(cpp, "a-1_64x64", vdir=cpp / "object_detection" / "fam" / "a-1_64x64_copy")
    capsys.readouterr()
    assert run(cpp, "--check") == 1
    out = capsys.readouterr().out
    assert "a-1_64x64_copy/factory/a-1_64x64_factory.hpp" in out
    problems = gen.namespace_problems(cpp)
    assert len(problems) == 1 and "a-1_64x64_copy" in problems[0]
    assert run(cpp) == 1, "the rewrite cannot place it and must say so"


def test_factory_headers_at_other_depths_fail_check(cpp):
    assert run(cpp) == 0
    add_variant(cpp, "fam", vdir=cpp / "object_detection" / "fam")
    add_variant(cpp, "deep_64x64", vdir=cpp / "object_detection" / "fam" / "x" / "deep_64x64")
    (cpp / "common" / "factory").mkdir()
    (cpp / "common" / "factory" / "shared_factory.hpp").write_text(
        "namespace dxapp {\n}  // namespace dxapp\n", encoding="utf-8")
    problems = gen.namespace_problems(cpp)
    assert len(problems) == 2, problems
    assert any("object_detection/fam/factory/fam_factory.hpp" in p for p in problems)
    assert any("fam/x/deep_64x64/factory/deep_64x64_factory.hpp" in p for p in problems)
    assert run(cpp, "--check") == 1


def test_digit_separators_are_not_character_literals(tmp_path):
    root = tmp_path / "src" / "cpp_example"
    (root / "common").mkdir(parents=True)
    add_variant(root, "a_64x64", post_body=(
        "        return std::make_unique<Post>(1'000, input_height, 2'000, input_width,"
        " is_ort_configured);"))
    assert gen.parameter_problems(root) == []
    assert run(root) == 0
    assert "/*" not in header(root, "a_64x64").split("createPostprocessor(")[1].split(")")[0]


def test_unnamed_parameters_are_left_alone(tmp_path):
    root = tmp_path / "src" / "cpp_example"
    (root / "common").mkdir(parents=True)
    extra = ("\n    int createExtra(int input_width, long long, const int, const Foo,"
             " unsigned, struct Bar*) override {\n        return input_width;\n    }\n")
    add_variant(root, "a_64x64", extra=extra)
    assert gen.parameter_problems(root) == []
    assert run(root) == 0
    assert "createExtra(int input_width, long long, const int, const Foo, unsigned, " \
           "struct Bar*) override" in header(root, "a_64x64")


def test_specifiers_and_parentheses_in_the_parameter_list_are_still_checked(tmp_path):
    root = tmp_path / "src" / "cpp_example"
    (root / "common").mkdir(parents=True)
    extra = ("\n    int createExtra(std::function<void(int)> cb, int input_width) const noexcept"
             " override {\n        return 0;\n    }\n"
             "\n    int createMore(int input_height) final {\n        return 1;\n    }\n")
    add_variant(root, "a_64x64", extra=extra)
    problems = gen.parameter_problems(root)
    assert sorted(p.split(": ", 1)[1].split("'")[1] for p in problems) == \
        ["cb", "input_height", "input_width"], problems
    assert run(root) == 0
    text = header(root, "a_64x64")
    assert "createExtra(std::function<void(int)> /*cb*/, int /*input_width*/) const noexcept" \
           " override {" in text
    assert "createMore(int /*input_height*/) final {" in text


def test_a_use_through_a_macro_counts_as_a_use(tmp_path):
    root = tmp_path / "src" / "cpp_example"
    (root / "common").mkdir(parents=True)
    add_variant(root, "a_64x64",
                pre="#define FAM_ARGS \\\n    input_width, input_height\n",
                post_body="        return std::make_unique<Post>(FAM_ARGS, is_ort_configured);")
    assert gen.parameter_problems(root) == []
    assert run(root) == 0
    assert "int input_width, int input_height, bool is_ort_configured = false" in \
        header(root, "a_64x64")


def _refused(root: Path, capsys) -> str:
    before = snapshot(root)
    capsys.readouterr()
    assert run(root) == 2
    assert snapshot(root) == before, "a refused run wrote files"
    return capsys.readouterr().out


def test_a_dxapp_line_of_another_shape_is_named(cpp, capsys):
    f = cpp / "object_detection" / "fam" / "b_2_64x64" / "factory" / "b_2_64x64_factory.hpp"
    f.write_text(f.read_text(encoding="utf-8").replace("namespace dxapp {", "namespace dxapp{"),
                 encoding="utf-8")
    out = _refused(cpp, capsys)
    assert "b_2_64x64_factory.hpp" in out and "'namespace dxapp{'" in out
    assert "found 1 and 1" not in out


def test_a_header_without_a_dxapp_namespace_is_refused(cpp, capsys):
    f = cpp / "object_detection" / "fam" / "b_2_64x64" / "factory" / "b_2_64x64_factory.hpp"
    t = f.read_text(encoding="utf-8")
    f.write_text(t.replace("namespace dxapp {\n", "").replace("}  // namespace dxapp\n", ""),
                 encoding="utf-8")
    out = _refused(cpp, capsys)
    assert "b_2_64x64_factory.hpp" in out and "found 0" in out


def test_a_header_in_another_variants_namespace_is_refused(cpp, capsys):
    f = cpp / "object_detection" / "fam" / "b_2_64x64" / "factory" / "b_2_64x64_factory.hpp"
    t = f.read_text(encoding="utf-8")
    f.write_text(t.replace("namespace dxapp {\n", "namespace dxapp {\nnamespace v_a_1_64x64 {\n")
                 .replace("}  // namespace dxapp\n",
                          "}  // namespace v_a_1_64x64\n}  // namespace dxapp\n"),
                 encoding="utf-8")
    out = _refused(cpp, capsys)
    assert "b_2_64x64_factory.hpp" in out and "v_a_1_64x64" in out and "v_b_2_64x64" in out


def test_an_entry_point_naming_a_sibling_variants_factory_is_refused(cpp, capsys):
    e = cpp / "object_detection" / "fam" / "b_2_64x64" / "b_2_64x64_sync.cpp"
    e.write_text(e.read_text(encoding="utf-8").replace(
        "dxapp::FamFactory", "dxapp::v_a_1_64x64::FamFactory"), encoding="utf-8")
    out = _refused(cpp, capsys)
    assert "b_2_64x64_sync.cpp" in out and "v_a_1_64x64" in out and "v_b_2_64x64" in out
