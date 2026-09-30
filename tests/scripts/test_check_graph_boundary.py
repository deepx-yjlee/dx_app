"""scripts/check_graph_boundary.py's CMake drift tripwire (U-52). Hermetic:
the module is imported and pointed at temporary CMake text."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "check_graph_boundary.py"
TOKEN = "${DXAPP_POSTPROCESS_INCLUDES}"


def load_guard():
    spec = importlib.util.spec_from_file_location("check_graph_boundary", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_real_cmake_lists_pass():
    assert load_guard().check_include_roots_drift()


def test_a_graph_target_without_the_postprocess_variable_is_fatal(tmp_path, monkeypatch, capsys):
    guard = load_guard()
    text = guard.CMAKE_LISTS_PATH.read_text(encoding="utf-8")
    block = guard._extract_named_block(guard._TARGET_INCLUDE_BLOCK, text, "graph_engine_test")
    assert block is not None and TOKEN in block
    broken = tmp_path / "CMakeLists.txt"
    broken.write_text(text.replace(block, block.replace(TOKEN, "")), encoding="utf-8")
    monkeypatch.setattr(guard, "CMAKE_LISTS_PATH", broken)
    assert not guard.check_include_roots_drift()
    assert "graph_engine_test" in capsys.readouterr().out


def test_the_postprocess_variable_left_in_a_comment_is_fatal(tmp_path, monkeypatch, capsys):
    """A "# ${DXAPP_POSTPROCESS_INCLUDES}" comment in the block lists nothing."""
    guard = load_guard()
    text = guard.CMAKE_LISTS_PATH.read_text(encoding="utf-8")
    block = guard._extract_named_block(guard._TARGET_INCLUDE_BLOCK, text, "graph_engine_test")
    assert block is not None and TOKEN in block
    broken = tmp_path / "CMakeLists.txt"
    broken.write_text(text.replace(block, block.replace(TOKEN, "# " + TOKEN)), encoding="utf-8")
    monkeypatch.setattr(guard, "CMAKE_LISTS_PATH", broken)
    assert not guard.check_include_roots_drift()
    assert "graph_engine_test" in capsys.readouterr().out


def test_the_vitpose_root_is_one_the_guard_resolves_against():
    assert ROOT / "src" / "postprocess" / "vitpose" in load_guard().INCLUDE_ROOTS
