"""Source-level contract: every C++ runner that previews through DisplayPump
exposes ``--drop-frames`` and configures the pump from it.

Since 2026-10-06 the pump is lossless by default (every frame is shown; a slow
window paces the pipeline). ``--drop-frames`` opts back into the depth-1 lossy
sink. A runner that forgets the option silently keeps the default, and one that
prints ``dropped (stale)`` unconditionally reports a count that is always 0.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import PROJECT_ROOT  # noqa: E402

RUNNER_DIR = PROJECT_ROOT / "src" / "cpp_example" / "common" / "runner"
DISPLAY_PUMP = PROJECT_ROOT / "src" / "cpp_example" / "common" / "utility" / "display_pump.hpp"
COMMON_UTIL = PROJECT_ROOT / "src" / "cpp_example" / "common" / "utility" / "common_util.hpp"


def _pump_runners():
    """Runner headers that offer frames to a DisplayPump (async) or the sync preview pump."""
    found = []
    for path in sorted(RUNNER_DIR.glob("*_runner.hpp")):
        src = path.read_text(encoding="utf-8")
        if ".offer(" in src and ("DisplayPump" in src or "syncPreviewPump" in src):
            found.append(path)
    return found


RUNNERS = _pump_runners()


@pytest.mark.contract
def test_display_pump_is_lossless_by_default():
    src = DISPLAY_PUMP.read_text(encoding="utf-8")
    assert re.search(r"std::atomic<bool>\s+drop_stale_\{false\}", src), (
        "DisplayPump::drop_stale_ must default to false (lossless)."
    )
    assert "void setDropStale(bool" in src and "bool dropStale() const" in src


@pytest.mark.contract
def test_configure_helper_exists():
    src = COMMON_UTIL.read_text(encoding="utf-8")
    assert "inline void configureDisplayPump(DisplayPump&" in src, (
        "common_util.hpp must provide configureDisplayPump(pump, drop_frames) "
        "so every runner applies the screen size and the --drop-frames choice."
    )


@pytest.mark.contract
def test_every_preview_runner_is_covered():
    names = {p.name for p in RUNNERS}
    expected = {f"async_{k}_runner.hpp" for k in (
        "3d_object_detection anomaly classification depth detection face_alignment "
        "face hand_landmark obb pose restoration segmentation semantic_seg").split()}
    expected |= {f"sync_{k}_runner.hpp" for k in (
        "3d_object_detection anomaly depth detection face_alignment face hand_landmark "
        "obb pose segmentation semantic_seg").split()}
    assert expected <= names, f"missing preview runners: {sorted(expected - names)}"


@pytest.mark.contract
@pytest.mark.parametrize("runner", RUNNERS, ids=lambda p: p.name)
def test_runner_exposes_drop_frames(runner):
    src = runner.read_text(encoding="utf-8")
    assert re.search(r'\(\s*"drop-frames"\s*,', src), (
        f"{runner.name}: no --drop-frames option next to --no-display"
    )
    if runner.name in ("async_detection_runner.hpp", "sync_detection_runner.hpp"):
        # CommandLineArgs is defined here and shared by the other runners.
        assert "bool drop_frames = false;" in src, f"{runner.name}: CommandLineArgs lacks drop_frames"
    assert "configureDisplayPump(" in src, (
        f"{runner.name}: never calls configureDisplayPump(pump, args.drop_frames)"
    )
    if runner.name.startswith("async_"):
        # Lossless tail: the display thread's last frames are shown before stop().
        assert "pumpUntilJoined(display_pump_, displayThr)" in src, (
            f"{runner.name}: shutdown must pumpUntilJoined() before display_pump_.stop()"
        )
        assert src.index("pumpUntilJoined(display_pump_, displayThr)") < src.rindex("display_pump_.stop();"), (
            f"{runner.name}: pumpUntilJoined() must come before the final display_pump_.stop()"
        )


@pytest.mark.contract
@pytest.mark.parametrize("runner", RUNNERS, ids=lambda p: p.name)
def test_dropped_count_only_printed_in_drop_mode(runner):
    src = runner.read_text(encoding="utf-8")
    for m in re.finditer(r"dropped \(stale\)", src):
        window = src[max(0, m.start() - 400):m.start()]
        assert "dropStale()" in window, (
            f"{runner.name}: 'dropped (stale)' is printed without a dropStale() guard"
        )
