# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""``image_only`` in the registry must reproduce the task-keyed runner behavior.

``sync_runner._IMAGE_ONLY_TASKS`` keys image-only-ness on the task name. The
dx-modelzoo task alignment (Phase 1) deletes three of those task names and moves
two of their models into video-capable tasks:

    reid/casvit_*           -> image_classification  (110 other models need video)
    embedding/eigenplaces-* -> super_resolution      (6 other models need video)

So the flag has to move to the variant before the tasks are renamed. This test
pins the migrated per-variant flag to what the runner does *today*, making the
rename provably behavior-preserving.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REGISTRY = PROJECT_ROOT / "config" / "model_registry.json"
SYNC_RUNNER = (PROJECT_ROOT / "src" / "python_example" / "common" / "runner" / "sync_runner.py")

# Mirror of sync_runner._IMAGE_ONLY_TASKS, translated from the runner's internal
# "3d_detection" alias to the registry's add_model_task spelling.
IMAGE_ONLY_LEGACY_TASKS = frozenset({
    "embedding", "reid", "attribute_recognition",
    "object_pose_estimation", "3d_object_detection",
})


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_image_only_matches_legacy_task_membership(registry):
    bad = [
        (e["model_name"], e["task_legacy"], e["image_only"])
        for e in registry
        if e["image_only"] != (e["task_legacy"] in IMAGE_ONLY_LEGACY_TASKS)
    ]
    assert not bad, f"image_only diverges from the legacy task set: {bad}"


def test_image_only_count_is_pinned(registry):
    """17 at the Phase 0 migration, 22 after the 2_5_0 additions.

    The five new ones all land in a legacy task the runner already treats as
    image-only, so the count moves without the RULE moving -- which is exactly what
    test_image_only_matches_legacy_task_membership above checks:

        clip-img_resnet50_224x224_openai                    legacy embedding
        clip-img_vit-b16-quickgelu_224x224_metaclip-fullcc  legacy embedding
        clip-text_resnet50_77x512_openai                    legacy embedding
        pp-shituv2-feature-extraction_224x224               legacy embedding
        repvgg-a0-reid_256x128                              legacy reid

    The pin stays because it is the tripwire for a flag being set by accident: a
    variant silently becoming image-only loses video input with no error.
    """
    flagged = [e["variant"] for e in registry if e["image_only"]]
    assert len(flagged) == 22, (
        f"expected 22 image-only variants, got {len(flagged)}: {sorted(flagged)}"
    )


def test_runner_image_only_set_still_matches_this_mirror():
    """Fail loudly if the runner's set changes without this mirror being updated."""
    text = SYNC_RUNNER.read_text(encoding="utf-8")
    start = text.index("_IMAGE_ONLY_TASKS = {")
    literal = text[start : text.index("}", start) + 1]
    names = {tok.strip().strip('"').strip("'")
             for tok in literal.split("{", 1)[1].rstrip("}").split(",")}
    names = {n for n in names if n}
    expected = (set(IMAGE_ONLY_LEGACY_TASKS) - {"3d_object_detection"}) | {"3d_detection"}
    assert names == expected, (
        f"sync_runner._IMAGE_ONLY_TASKS is {sorted(names)}, this test mirrors "
        f"{sorted(expected)} -- update IMAGE_ONLY_LEGACY_TASKS and the migration "
        "script together"
    )


def test_models_that_move_into_video_capable_tasks_keep_image_only(registry):
    """Models whose task gains video capability must stay image-only."""
    by_variant = {e["variant"]: e for e in registry}
    movers = [
        ("casvit-t_224x224", "image_classification"),
        ("casvit-m_224x224", "image_classification"),
        ("eigenplaces-resnet18_512x512", "super_resolution"),
        ("eigenplaces-resnet50_512x512", "super_resolution"),
    ]
    for variant, new_task in movers:
        e = by_variant.get(variant)
        assert e is not None, f"{variant} missing from the registry"
        assert e["task"] == new_task, f"{variant}: task is {e['task']}, expected {new_task}"
        assert e["image_only"] is True, (
            f"{variant} moves into video-capable task {new_task} and MUST keep image_only=True"
        )
