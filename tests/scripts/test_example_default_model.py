"""An example without -m resolves its own model (SDKREQ-529).

``bin/<variant>_sync`` and ``bin/<variant>_async`` run without ``-m`` load
the default model that ``resolveExampleModel(argv[0])``
(``common/utility/common_util.hpp``) reads from ``config/model_registry.json``,
and pass its ``model_name`` to ``./setup.sh --models`` when the file is
missing. These tests compile a small probe against that header in
``tmp_path``, with ``PROJECT_ROOT_DIR`` set to this checkout so it reads the
committed registry, and check every non-alias row:

* ``path`` is ``assets/models/<dxnn_file>``;
* ``modelName`` is the row's ``model_name``.

A variant that also has an ``alias_of`` row resolves to the canonical row,
not the alias (``deit-b_384x384_distilled`` -> ``deit_base_distilled_2``).
Nothing outside ``tmp_path`` is written and no NPU is used.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CPP_ROOT = ROOT / "src" / "cpp_example"
REGISTRY = ROOT / "config" / "model_registry.json"
DXRT_INCLUDE = Path("/usr/local/include")
# 497 canonical rows (498 rows, one alias_of). Two PPU examples are not registered.
MIN_CANONICAL_ROWS = 497

PROBE_SOURCE = r"""
#include "common/utility/common_util.hpp"

#include <iostream>
#include <string>

// One argv[0] per input line; prints "<argv0>\t<path>\t<modelName>".
int main() {
    std::string argv0;
    while (std::getline(std::cin, argv0)) {
        const dxapp::ExampleModelRef ref = dxapp::resolveExampleModel(argv0);
        std::cout << argv0 << '\t' << ref.path << '\t' << ref.modelName << '\n';
    }
    return 0;
}
"""


def _opencv_cflags() -> list[str]:
    try:
        out = subprocess.run(["pkg-config", "--cflags", "opencv4"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return out.split()


@pytest.fixture(scope="module")
def probe(tmp_path_factory) -> Path:
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is not available")
    if not (DXRT_INCLUDE / "dxrt" / "dxrt_api.h").is_file():
        pytest.skip("DX-RT headers are not installed under /usr/local/include")
    opencv = _opencv_cflags()
    if not opencv:
        pytest.skip("pkg-config cannot find opencv4")
    work = tmp_path_factory.mktemp("example_default_model_probe")
    source = work / "probe.cpp"
    source.write_text(PROBE_SOURCE)
    binary = work / "probe"
    build = subprocess.run(
        [compiler, "-std=c++14", "-Wall", "-Wextra", "-Werror",
         '-DPROJECT_ROOT_DIR="{}"'.format(ROOT), f"-I{CPP_ROOT}", f"-I{DXRT_INCLUDE}",
         *opencv, str(source), "-o", str(binary), "-lstdc++fs"],
        capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stderr
    return binary


def resolve(probe: Path, argv0s: list[str]) -> dict[str, tuple[str, str]]:
    run = subprocess.run([str(probe)], input="".join(a + "\n" for a in argv0s),
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    answers = {}
    for line in run.stdout.splitlines():
        argv0, path, model_name = line.split("\t")
        answers[argv0] = (path, model_name)
    assert len(answers) == len(argv0s)
    return answers


def canonical_rows() -> list[dict]:
    rows = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [row for row in rows if not row.get("alias_of")]


def test_every_example_binary_resolves_its_registry_row(probe):
    rows = canonical_rows()
    assert len(rows) >= MIN_CANONICAL_ROWS
    expected = {}
    for row in rows:
        for kind in ("sync", "async"):
            argv0 = str(ROOT / "bin" / "{}_{}".format(row["variant"], kind))
            expected[argv0] = ("assets/models/" + row["dxnn_file"], row["model_name"])
    got = resolve(probe, sorted(expected))
    wrong = ["{}: {} (want {})".format(Path(a).name, got[a], expected[a])
             for a in sorted(expected) if got[a] != expected[a]]
    assert not wrong, "{}/{} binaries resolve wrongly:\n  {}".format(
        len(wrong), len(expected), "\n  ".join(wrong))


def test_a_variant_with_an_alias_row_resolves_the_canonical_row(probe):
    rows = json.loads(REGISTRY.read_text(encoding="utf-8"))
    alias = next(row for row in rows if row["variant"] == "deit-b_384x384_distilled"
                 and row.get("alias_of"))
    assert alias["model_name"] == "deit_base384_distilled"
    assert alias["alias_of"] == "deit_base_distilled_2"
    argv0 = str(ROOT / "bin" / "deit-b_384x384_distilled_sync")
    got = resolve(probe, [argv0])
    assert got[argv0] == ("assets/models/deit-b_384x384_distilled.dxnn",
                          "deit_base_distilled_2")
