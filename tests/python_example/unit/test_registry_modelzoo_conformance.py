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

NEW_FIELDS = ("variant", "family", "task", "task_legacy", "image_only",
              "zoo_canonical", "alias_of")

# Added with the 2_5_0 additions: 143 of the 499 variants have no published .dxnn, so
# "is there a file for this" has to be a declared fact rather than an inference from
# whatever happens to be in assets/models on one machine.
PUBLICATION_FIELDS = ("published",)

# model_name -> (variant, task, family). The ONLY entries allowed to miss the
# dx-modelzoo snapshot. See the spec's "Documented exceptions" table.
EXCEPTIONS: dict[str, tuple[str, str, str]] = {
    "efficientnet_lite0":     ("efficientnet-lite0_256x256", "image_classification", "efficientnet"),
    "scrfd500m_ppu":          ("SCRFD500M_PPU",              "face_detection",       "scrfd"),
    "yolov5pose_ppu":         ("YOLOV5Pose_PPU",             "pose_estimation",      "yolov5_pose"),
}

# RETENTION POLICY: a conflicting example is KEPT, never deleted.
#
# When two entries land on the same variant, the non-canonical one becomes an
# *alias*: it keeps its own model_name as the legacy compat key and shares the
# canonical entry's variant/family/task/dxnn_file. It is NOT slated for removal
# at any phase -- the alignment renames and regroups examples, it does not
# delete them.
#
# ``deit_base384_distilled`` is byte-identical to ``deitbase384`` apart from
# model_name and points at the NON-distilled deit-b_384x384.dxnn, so its name is
# misleading; the genuine distilled 384 model is the variant
# deit-b_384x384_distilled, which resolves from the snapshot with no exception.
# The misleading name is kept anyway, because dropping it would drop a working
# example.
#
# alias model_name -> canonical model_name it aliases.
ALIASES: dict[str, str] = {
    "deit_base384_distilled": "deitbase384",
}

# In the snapshot but intentionally not in dx_app: no example, not on disk.
SNAPSHOT_GAPS = {"efficientnet-lite0_224x224"}

# Field names the migration wrote in an earlier revision and must no longer emit.
# The migration rebuilds each entry by dropping the fields it is about to rewrite,
# so a RENAMED field silently survives from a previous run unless it is stripped
# explicitly -- that actually happened when duplicate_of became alias_of, leaving
# all 353 entries carrying both spellings.
RETIRED_FIELDS = ("duplicate_of",)


# dx-modelzoo family renames. CMake target names are global, so two families sharing a
# name across tasks collide as ``<family>_sync``. Exactly one collision exists, and
# dx-modelzoo's own convention (yolo26-seg, yolov5-face, yolov5-pose) is to suffix the
# sibling by task -- it just did not apply that to casvit.
FAMILY_OVERRIDES: dict[tuple[str, str], str] = {
    ("semantic_segmentation", "casvit"): "casvit_seg",
}


def _snake(family: str) -> str:
    """dx-modelzoo family -> dx_app family directory (import-safe)."""
    return family.replace("-", "_").replace(".", "_")


def _family_for(task: str, family: str) -> str:
    return FAMILY_OVERRIDES.get((task, family), _snake(family))


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def snapshot() -> dict[str, dict]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["variants"]


@pytest.fixture(scope="module")
def provisional() -> dict[str, dict]:
    """Our own (task, family) assignments for variants upstream has not filed.

    dx-modelzoo carries none of the 147 DX Model Zoo 2_5_0 additions (harvested
    2026-09-22: 350 variants, zero overlap), so for those the snapshot cannot be the
    oracle. The provisional table is, and unlike ``variants`` it already holds the
    dx_app-resolved family, so no FAMILY_OVERRIDES pass is applied to it.
    """
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["provisional"]["variants"]


def test_every_entry_has_the_new_fields(registry):
    missing = {
        e["model_name"]: [f for f in NEW_FIELDS if f not in e]
        for e in registry
        if any(f not in e for f in NEW_FIELDS)
    }
    assert not missing, f"entries missing dx-modelzoo fields: {missing}"


def test_no_retired_field_survives_a_rerun(registry):
    """A renamed field must be gone, not carried over from an earlier migration."""
    counts = {f: sum(1 for e in registry if f in e) for f in RETIRED_FIELDS}
    survivors = {f: n for f, n in counts.items() if n}
    assert not survivors, (
        f"retired field(s) still present in the registry: {survivors} -- "
        "add them to RETIRED_FIELDS in scripts/migrate_registry_modelzoo.py"
    )


def test_entry_key_set_is_exactly_the_expected_fields(registry):
    """Pin the full key set so neither a stale nor a stray field goes unnoticed."""
    expected = {
        "model_name", "dxnn_file", "original_name", "csv_task", "add_model_task",
        "postprocessor", "input_width", "input_height", "config", "source", "supported",
        *NEW_FIELDS, *PUBLICATION_FIELDS,
    }
    bad = {e["model_name"]: sorted(set(e) ^ expected) for e in registry if set(e) != expected}
    assert not bad, f"unexpected key set (symmetric difference shown): {bad}"


def test_variant_is_unique_among_canonical_entries(registry):
    """Every non-alias entry owns its variant outright.

    Entries listed in ALIASES deliberately share another entry's variant. They
    are retained examples, not pending deletions, so they are excluded here
    rather than being given a synthetic variant name that no .dxnn backs.
    """
    seen: dict[str, str] = {}
    dupes: list[tuple[str, str, str]] = []
    for e in registry:
        if e["alias_of"] is not None:
            continue
        v = e["variant"]
        if v in seen:
            dupes.append((v, seen[v], e["model_name"]))
        seen[v] = e["model_name"]
    assert not dupes, f"duplicate variant keys among canonical entries: {dupes}"


def test_alias_entries_are_declared_and_consistent(registry):
    """An alias must point at a real entry and carry that entry's identity."""
    by_name = {e["model_name"]: e for e in registry}
    declared = {e["model_name"]: e["alias_of"]
                for e in registry if e["alias_of"] is not None}
    assert declared == ALIASES, (
        f"alias_of markers are {declared}, ALIASES declares {ALIASES}"
    )
    for name, target_name in ALIASES.items():
        alias, target = by_name.get(name), by_name.get(target_name)
        assert alias is not None, f"ALIASES lists {name}, not in the registry"
        assert target is not None, f"{name} aliases {target_name}, not in the registry"
        assert target["alias_of"] is None, (
            f"{name} aliases {target_name}, which is itself an alias -- no alias chains"
        )
        assert alias["dxnn_file"] == target["dxnn_file"], (
            f"{name} claims to alias {target_name} but the .dxnn differs: "
            f"{alias['dxnn_file']} vs {target['dxnn_file']}"
        )
        for field in ("variant", "family", "task"):
            assert alias[field] == target[field], (
                f"{name}.{field}={alias[field]!r} must match {target_name}.{field}={target[field]!r}"
            )


def test_alias_entries_are_retained_not_deleted(registry):
    """Retention must be real, not just a label.

    The alignment regroups examples -- 353 per-variant directories became 89
    ``<task>/<family>/`` directories -- but it never deletes one. Post-restructure an
    alias is retained when its family directory exists in BOTH trees, its variant
    config is present, and the registry entry still resolves. Checking for the old
    per-variant directory would now fail for all 353 entries, not just aliases, so the
    test follows the variant rather than the legacy path.
    """
    by_name = {e["model_name"]: e for e in registry}
    for name, target_name in ALIASES.items():
        entry = by_name.get(name)
        assert entry is not None, f"alias {name} was dropped from the registry"
        for tree in ("python_example", "cpp_example"):
            fam = PROJECT_ROOT / "src" / tree / entry["task"] / entry["family"]
            assert fam.is_dir(), f"alias {name}: family dir missing -> {fam}"
            cfg = fam / "variants" / f"{entry['variant']}.json"
            assert cfg.is_file(), f"alias {name}: variant config missing -> {cfg}"
        # The alias shares its canonical entry's variant, so the config it points at is
        # the canonical one -- that sharing is the whole point of an alias.
        assert entry["variant"] == by_name[target_name]["variant"]


def test_the_real_distilled_384_model_owns_its_dxnn_stem(registry):
    """deit-b_384x384_distilled must belong to the entry holding that .dxnn.

    Guards the mistake this test file was born from: the entry *named*
    ``deit_base384_distilled`` points at the non-distilled .dxnn, while the
    genuine distilled model sits behind a legacy squashed name. Under
    dxnn-canonical naming the variant follows the .dxnn, not the legacy name.
    """
    owners = [e for e in registry if e["dxnn_file"] == "deit-b_384x384_distilled.dxnn"]
    assert len(owners) == 1, f"expected exactly 1 owner, got {[e['model_name'] for e in owners]}"
    owner = owners[0]
    assert owner["variant"] == "deit-b_384x384_distilled", (
        f"{owner['model_name']} must carry variant 'deit-b_384x384_distilled', "
        f"got {owner['variant']!r}"
    )
    assert owner["alias_of"] is None, "the genuine distilled model is not an alias"


def test_variant_matches_dxnn_stem_except_documented(registry):
    bad = [
        (e["model_name"], e["variant"], e["dxnn_file"])
        for e in registry
        if e["variant"] != e["dxnn_file"][: -len(".dxnn")]
        and e["model_name"] not in EXCEPTIONS
        and e["model_name"] not in ALIASES
    ]
    assert not bad, f"variant != dxnn stem outside EXCEPTIONS: {bad}"


def test_family_names_are_unique_across_tasks(registry):
    """CMake target names are global, so <family>_sync must be unambiguous.

    Two families sharing a name in different tasks would produce duplicate CMake
    targets. FAMILY_OVERRIDES exists to break exactly that; this test proves it is
    sufficient and stays sufficient as families are added.
    """
    import collections
    fams = {(e["task"], e["family"]) for e in registry}
    counts = collections.Counter(f for _, f in fams)
    clashes = {
        f: sorted(t for t, ff in fams if ff == f) for f, n in counts.items() if n > 1
    }
    assert not clashes, (
        f"family name(s) used in more than one task: {clashes} -- "
        "add an entry to FAMILY_OVERRIDES in scripts/migrate_registry_modelzoo.py"
    )


def test_task_and_family_match_the_snapshot(registry, snapshot, provisional):
    """Every entry's (task, family) must come from a declared table, never from nowhere.

    Upstream-published variants are checked against the harvested snapshot through
    FAMILY_OVERRIDES; the 2_5_0 additions are checked against the provisional table
    verbatim. An entry in neither table is the real failure this guards against.
    """
    bad = []
    for e in registry:
        if e["model_name"] in EXCEPTIONS:
            continue
        upstream = snapshot.get(e["variant"])
        if upstream is not None:
            want = (upstream["task"], _family_for(upstream["task"], upstream["family"]))
        elif e["variant"] in provisional:
            ours = provisional[e["variant"]]
            want = (ours["task"], ours["family"])
        else:
            bad.append((e["model_name"], e["variant"],
                        "in neither the snapshot nor the provisional table"))
            continue
        got = (e["task"], e["family"])
        if got != want:
            bad.append((e["model_name"], got, want))
    assert not bad, f"task/family disagree with their declared table: {bad}"


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
