"""The docs say what SP6 built, and what it could not check (U-16, U-37, U-38, U-76)."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "source" / "docs"


def section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    assert heading in text, "{}: no {!r}".format(path.name, heading)
    level = len(heading.split(" ", 1)[0])
    body = text.split(heading, 1)[1]
    cuts = [i for i in (body.find("\n" + "#" * n + " ") for n in range(1, level + 1)) if i >= 0]
    return body[:min(cuts)] if cuts else body


def test_build_doc_covers_cross_builds():
    s = section(DOCS / "02_DX-APP_Installation_and_Build.md", "### Cross-compiling for aarch64")
    for needle in ("./build.sh --arch aarch64", "scripts/check_cross_compile.sh", "--with-registry",
                   "dx_graph Python module skipped: cross build", "-DDXAPP_CROSS_PYTHON_GRAPH=ON",
                   "-DPython_INCLUDE_DIR", "dx_postprocess skipped", "validated with x86_64 dxrt only",
                   "compile-checked"):
        assert needle in s, needle


def test_build_doc_covers_downloads_behind_a_tls_inspecting_proxy():
    s = section(DOCS / "02_DX-APP_Installation_and_Build.md", "### Downloads behind a TLS-inspecting proxy")
    for needle in ("Missing Authority Key Identifier", "VERIFY_X509_STRICT", "Python 3.13",
                   "DXAPP_SETUP_PYTHON", "venv-dx-runtime", "DXAPP_TLS_RELAX_X509_STRICT=1",
                   "still verified", "REQUESTS_CA_BUNDLE", "Downloader Python:"):
        assert needle in s, needle


def test_build_doc_says_what_was_not_checked_on_windows():
    s = section(DOCS / "02_DX-APP_Installation_and_Build.md", "### Graph engine on Windows")
    for needle in ("not built on Windows here", "C++17", "/bigobj", "C5038", "C4062",
                   "No Python 3 interpreter for the graph model registry", "SetConsoleCtrlHandler",
                   "Ctrl-Break", "run_tests.bat graph", "bin\\Release"):
        assert needle in s, needle


def test_test_doc_names_the_entry_point_every_check_and_the_npu_switch():
    s = section(DOCS / "04_DX-APP_CPP_Example_Test.md", "### Repository checks (GitHub Actions)")
    for needle in ("scripts/ci_checks.sh", ".github/workflows/dxapp-checks.yml", "--require-dxrt",
                   "DXRT_INCLUDE_DIR=/nonexistent", "DXAPP_NPU_CI", "DXAPP_NPU_PYTHON",
                   "DXAPP_NPU_RUNTIME_DIR", "DXAPP_NPU_ASSETS_DIR", "DXAPP_CHECKS_RUNNER",
                   "dxapp-npu", "pull_request"):
        assert needle in s, needle
    names = subprocess.run(["bash", str(ROOT / "scripts" / "ci_checks.sh"), "--list"],
                           capture_output=True, text=True, check=True).stdout.split()
    for name in names:
        assert "`{}`".format(name) in s, name


def test_tests_readme_states_the_hermetic_rule():
    text = (ROOT / "tests" / "README.md").read_text(encoding="utf-8")
    for needle in ("tests/scripts", "hermetic", "hermetic_guard.py", "build_sh_sandbox.sh",
                   "scripts/ci_checks.sh", "tests/windows", "bin/Release", "tests/cpp_example",
                   "tests/python_example"):
        assert needle in text, needle
    assert "bin/Release" in (ROOT / "tests" / "cpp_example" / "README.md").read_text(encoding="utf-8")


def test_readmes_point_at_ci_and_the_platform_notes():
    assert "scripts/ci_checks.sh" in section(ROOT / "README.md", "## Checks and CI")
    dx_graph = (ROOT / "src" / "bindings" / "python" / "dx_graph" / "README.md").read_text(encoding="utf-8")
    assert "DXAPP_CROSS_PYTHON_GRAPH" in dx_graph
    assert "cross build" in section(ROOT / "src" / "bindings" / "python" / "dx_graph" / "README.md",
                                    "## Limitations")
    platforms = section(ROOT / "src" / "cpp_example" / "multi_model_graph" / "README.md", "## Platforms")
    for needle in ("not built on Windows here", "SetConsoleCtrlHandler", "aarch64",
                   "x86_64 dxrt", "check_cross_compile.sh"):
        assert needle in platforms, needle


def test_the_ci_docs_match_the_check_table_and_keep_forks_on_the_hosted_runner():
    s = section(DOCS / "04_DX-APP_CPP_Example_Test.md", "### Repository checks (GitHub Actions)")
    readme = section(ROOT / "README.md", "## Checks and CI")
    # Three checks need the DX-RT headers: neither text may say none does.
    for text in (s, readme):
        assert "neither the DX-RT headers nor an NPU" not in " ".join(text.split())
    assert "the aarch64 and header checks run where the DX-RT headers are installed" in readme
    for row in ("| `header-odr` |", "| `cxx14-headers` |"):
        line = next(line for line in s.splitlines() if line.startswith(row))
        assert "OpenCV" in line.rsplit("|", 2)[1], line
    assert "Pull requests from a fork always run on `ubuntu-24.04`" in " ".join(s.split())
    assert "trust with a fork's code" not in s
