# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""``config/model_registry.json`` must agree with the vendored dx-modelzoo tree.

The registry is the single source of truth for (task, family, variant). Family
assignment cannot be derived -- dx-modelzoo folds depth/width into the family
(resnet50 -> resnet, vgg16-bn -> vgg) -- so it is joined in from a committed
snapshot of the upstream tree and pinned here. Without this test the mapping
drifts silently the first time either side gains a model.

``variant`` is the identity used by ``--variant`` and by
``assets/models/<variant>.dxnn``; the four entries where it cannot equal the
dxnn stem are enumerated in EXCEPTIONS and nowhere else.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REGISTRY = PROJECT_ROOT / "config" / "model_registry.json"
SNAPSHOT = PROJECT_ROOT / "tests" / "data" / "modelzoo_cv_tree.json"

NEW_FIELDS = ("variant", "family", "task", "task_legacy", "image_only", "zoo_canonical")

# model_name -> (variant, task, family). The ONLY entries allowed to miss the
# dx-modelzoo snapshot. See the spec's "Documented exceptions" table.
EXCEPTIONS: dict[str, tuple[str, str, str]] = {
    "efficientnet_lite0":     ("efficientnet-lite0_256x256", "image_classification", "efficientnet"),
    "scrfd500m_ppu":          ("SCRFD500M_PPU",              "face_detection",       "scrfd"),
    "yolov5pose_ppu":         ("YOLOV5Pose_PPU",             "pose_estimation",      "yolov5_pose"),
    "deit_base384_distilled": ("deit-b_384x384_distilled",   "image_classification", "deit"),
}

# In the snapshot but intentionally not in dx_app: no example, not on disk.
SNAPSHOT_GAPS = {"efficientnet-lite0_224x224"}


def _snake(family: str) -> str:
    """dx-modelzoo family -> dx_app family directory (import-safe)."""
    return family.replace("-", "_").replace(".", "_")


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def snapshot() -> dict[str, dict]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["variants"]


def test_every_entry_has_the_new_fields(registry):
    missing = {
        e["model_name"]: [f for f in NEW_FIELDS if f not in e]
        for e in registry
        if any(f not in e for f in NEW_FIELDS)
    }
    assert not missing, f"entries missing dx-modelzoo fields: {missing}"


def test_variant_is_unique(registry):
    seen: dict[str, str] = {}
    dupes: list[tuple[str, str, str]] = []
    for e in registry:
        v = e["variant"]
        if v in seen:
            dupes.append((v, seen[v], e["model_name"]))
        seen[v] = e["model_name"]
    assert not dupes, f"duplicate variant keys: {dupes}"


def test_variant_matches_dxnn_stem_except_documented(registry):
    bad = [
        (e["model_name"], e["variant"], e["dxnn_file"])
        for e in registry
        if e["variant"] != e["dxnn_file"][: -len(".dxnn")]
        and e["model_name"] not in EXCEPTIONS
    ]
    assert not bad, f"variant != dxnn stem outside EXCEPTIONS: {bad}"


def test_task_and_family_match_the_snapshot(registry, snapshot):
    bad = []
    for e in registry:
        if e["model_name"] in EXCEPTIONS:
            continue
        upstream = snapshot.get(e["variant"])
        if upstream is None:
            bad.append((e["model_name"], e["variant"], "not in snapshot"))
            continue
        want = (upstream["task"], _snake(upstream["family"]))
        got = (e["task"], e["family"])
        if got != want:
            bad.append((e["model_name"], got, want))
    assert not bad, f"task/family disagree with dx-modelzoo: {bad}"


def test_exceptions_carry_their_declared_values(registry):
    by_name = {e["model_name"]: e for e in registry}
    for name, (variant, task, family) in EXCEPTIONS.items():
        e = by_name.get(name)
        assert e is not None, f"EXCEPTIONS lists {name}, which is not in the registry"
        assert (e["variant"], e["task"], e["family"]) == (variant, task, family), (
            f"{name}: got {(e['variant'], e['task'], e['family'])}, want {(variant, task, family)}"
        )
        assert e["zoo_canonical"] is False, f"{name} must be zoo_canonical=False"


def test_zoo_canonical_flag_agrees_with_snapshot_membership(registry, snapshot):
    bad = [
        (e["model_name"], e["zoo_canonical"], e["variant"] in snapshot)
        for e in registry
        if e["zoo_canonical"] is not (e["variant"] in snapshot)
    ]
    assert not bad, f"zoo_canonical disagrees with snapshot membership: {bad}"


def test_snapshot_coverage(registry, snapshot):
    covered = {e["variant"] for e in registry}
    uncovered = set(snapshot) - covered - SNAPSHOT_GAPS
    assert not uncovered, f"dx-modelzoo variants with no registry entry: {sorted(uncovered)}"


def test_task_legacy_preserves_the_old_task(registry):
    bad = [
        (e["model_name"], e["task_legacy"], e["add_model_task"])
        for e in registry
        if e["task_legacy"] != e["add_model_task"]
    ]
    assert not bad, f"task_legacy must mirror add_model_task: {bad}"
