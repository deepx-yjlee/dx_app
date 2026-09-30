# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""The 2_5_0 additions are provisional: dx-modelzoo has not published them.

These tests pin the three things the design spec calls guesses, so that a guess
contradicted by upstream fails here rather than silently persisting.

Background, measured 2026-09-22: the refreshed DX Model Zoo table carries 497 rows,
350 with a q-lite .dxnn URL (today's registry coverage), 143 with no artifact at all,
and 4 with only a q-master .dxnn. A fresh harvest of dx-modelzoo still returns 350
variants with ZERO overlap with the 143, so the (task, family) table that the
predecessor relied on as authoritative data simply does not exist for them yet. Our
assignments follow dx-modelzoo's own rule, read from the repo: the family boundary is
the POSTPROCESSING CHAIN (yolov8-s_640x640_decode stays in family 'yolov8' because its
chain is identical; yolov8-n_640x640_ppu moves to 'yolo-ppu' because its chain differs,
despite sharing weights).
"""
from __future__ import annotations

import json

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = PROJECT_ROOT / "tests" / "data" / "modelzoo_cv_tree.json"
NEW_LIST = PROJECT_ROOT / "new_modelzoo.txt"
REGISTRY = PROJECT_ROOT / "config" / "model_registry.json"
SPECS = PROJECT_ROOT / "tests" / "data" / "processor_specs.json"
MANIFEST = PROJECT_ROOT / "scripts" / "modelzoo_manifest.json"

# 353 before the additions (352 distinct variants plus the retained
# deit_base384_distilled alias) + 147 = 500 entries describing 499 variants.
EXPECTED_REGISTRY_ENTRIES = 353 + 147

ALLOWED_URL_PREFIXES = (
    "https://sdk.deepx.ai/modelzoo/dxnn/2_4_0/",
    "https://sdk.deepx.ai/modelzoo/q-lite-dxnn/2_4_0/",
    "https://sdk.deepx.ai/modelzoo/q-lite-dxnn/2_5_0/",
    "https://sdk.deepx.ai/modelzoo/q-master-dxnn/2_4_0/",
    "https://sdk.deepx.ai/modelzoo/q-lite-json/2_4_0/",
    "https://sdk.deepx.ai/modelzoo/q-lite-json/2_5_0/",
    "https://sdk.deepx.ai/modelzoo/q-master-json/2_4_0/",
)

# The 4 rows that carry a q-master .dxnn but no q-lite one. Unlike the 143 they ARE
# downloadable (measured: HTTP 200 at modelzoo/q-master-dxnn/2_4_0/), so they are
# provisional only in the sense that dx-modelzoo has not filed them either.
Q_MASTER_ONLY = {
    "beit-l-p16_384x384",
    "levit-128s_224x224",
    "vit-b-p16_384x384",
    "vit-t-p16_224x224",
}


def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _unpublished_stems() -> set[str]:
    return {
        line.strip()[: -len(".dxnn")]
        for line in NEW_LIST.read_text(encoding="utf-8").split()
        if line.strip()
    }


def test_provisional_section_holds_exactly_the_unpublished_stems():
    """The provisional section must match new_modelzoo.txt plus the 4 q-master models.

    new_modelzoo.txt is the untracked list DEEPX supplied when the 147 additions were
    declared; the committed table is what every other test here pins. Skip rather than
    fail when the input file is not in the checkout.
    """
    if not NEW_LIST.is_file():
        pytest.skip(f"{NEW_LIST.name} is not in this checkout")
    provisional = _snapshot()["provisional"]["variants"]
    expected = _unpublished_stems() | Q_MASTER_ONLY
    assert set(provisional) == expected


def test_provisional_never_overlaps_the_harvested_table():
    """A stem upstream has published must leave the provisional section.

    This is the guard that makes a contradicted guess loud: the moment dx-modelzoo
    files one of these stems, its authoritative (task, family) must replace ours.
    """
    snap = _snapshot()
    overlap = set(snap["provisional"]["variants"]) & set(snap["variants"])
    assert overlap == set(), (
        f"{len(overlap)} stems are now published upstream and must be moved out of "
        f"'provisional' into 'variants' (re-run scripts/harvest_modelzoo_tree.py): "
        f"{sorted(overlap)}"
    )


def test_family_names_are_unique_across_tasks_including_provisional():
    """CMake target names are family-derived, so one family may live in one task only.

    The check is over the REGISTRY, not over the snapshot. dx-modelzoo itself files
    ``casvit`` under both image_classification and semantic_segmentation, so the raw
    upstream table legitimately contains that clash; dx_app resolves it to
    ``casvit_seg`` via FAMILY_OVERRIDES. The registry holds the resolved value, and
    the resolved value is what becomes a directory and a ``<family>_sync`` target.
    """
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    owner: dict[str, str] = {}
    clashes = []
    for entry in registry:
        family, task = entry["family"], entry["task"]
        if owner.setdefault(family, task) != task:
            clashes.append((family, owner[family], task, entry["variant"]))
    assert clashes == [], f"family used by two tasks: {clashes}"


def test_provisional_families_agree_with_the_registry():
    """The provisional table and the registry must not drift apart.

    Both are emitted from scripts/data/modelzoo_2_5_0.py, so a disagreement means one
    of them was hand-edited -- the exact failure the emitter exists to prevent.
    """
    provisional = _snapshot()["provisional"]["variants"]
    registry = {e["variant"]: e for e in
                json.loads(REGISTRY.read_text(encoding="utf-8"))}
    bad = []
    for stem, ours in provisional.items():
        entry = registry.get(stem)
        if entry is None:
            bad.append((stem, "no registry entry"))
        elif (entry["task"], entry["family"]) != (ours["task"], ours["family"]):
            bad.append((stem, (entry["task"], entry["family"]),
                        (ours["task"], ours["family"])))
    assert bad == [], f"provisional table disagrees with the registry: {bad}"


def test_registry_covers_every_provisional_variant():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    provisional = set(_snapshot()["provisional"]["variants"])
    assert provisional <= {e["variant"] for e in registry}
    assert len(registry) == EXPECTED_REGISTRY_ENTRIES


def test_published_means_the_url_serves_it_not_that_a_file_is_absent():
    """`published` is a fact about DX Model Zoo, not about this machine's disk.

    Two premises have now been retired here. The first asserted `published is False`
    implies "no file in assets/models", which broke when the 143 unpublished models
    were obtained out of band and extracted while their URLs still 403'd. The second
    read the flag off the URL VERSION -- anything under /2_5_0/ was unpublished -- and
    that held only until the zoo published 2_5_0 on 2026-09-30 and moved its whole
    q-lite tier there. Probing every manifest URL that day: 498 -> 200, one -> 403.

    So the flag is DECLARED, in exactly one place per consumer: `published` in the
    registry and `pending` on the manifest row. On-disk presence is what the sweep
    checks, independently, when it decides whether it can run something.
    """
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    manifest = {e["name"]: e for e in json.loads(MANIFEST.read_text(encoding="utf-8"))}
    disagree = []
    for entry in registry:
        row = manifest.get(entry["model_name"])
        if row is None or not row.get("dxnn_url"):
            continue
        if bool(row.get("pending")) != (entry["published"] is False):
            disagree.append((entry["variant"], entry["published"],
                             bool(row.get("pending"))))
    assert disagree == [], (
        "registry.published and manifest.pending disagree: " + str(disagree))


def test_the_four_q_master_models_are_marked_published():
    """The q-master tier decides the URL, not the publication state.

    These four carry a q-master .dxnn and no q-lite one (measured HTTP 200 at
    q-master-dxnn/2_4_0/ on both 2026-09-22 and 2026-09-30). That used to be the same
    set as "published", which is why one frozenset served both; after the 2_5_0 release
    all but one model is published, so the two facts are now separate.
    """
    registry = {e["variant"]: e for e in json.loads(REGISTRY.read_text(encoding="utf-8"))}
    manifest = {Path(e["dxnn_url"]).name[: -len(".dxnn")]: e
                for e in json.loads(MANIFEST.read_text(encoding="utf-8"))
                if e.get("dxnn_url")}
    for variant in Q_MASTER_ONLY:
        assert registry[variant]["published"] is True, variant
        assert "q-master-dxnn" in manifest[variant]["dxnn_url"], variant
    unpublished = [e["variant"] for e in registry.values() if e["published"] is False]
    assert unpublished == ["vit-l-p16_512x512_swag"], (
        f"expected only the model DEEPX reported as failing to build, got {unpublished}")


def test_specs_and_registry_agree_on_the_additions():
    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    provisional = set(_snapshot()["provisional"]["variants"])
    missing = sorted(provisional - set(specs))
    assert missing == [], f"no processor spec for: {missing}"
    for variant in sorted(provisional):
        for role in ("preprocessor", "postprocessor", "visualizer"):
            assert specs[variant].get(role, {}).get("class"), f"{variant}: no {role}"


def test_registry_and_specs_agree_on_the_postprocessor_class():
    """The registry's flat 'postprocessor' string must name the same class the spec builds."""
    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    provisional = set(_snapshot()["provisional"]["variants"])
    bad = [
        (e["variant"], e["postprocessor"], specs[e["variant"]]["postprocessor"]["class"])
        for e in json.loads(REGISTRY.read_text(encoding="utf-8"))
        if e["variant"] in provisional
        and e["postprocessor"] != specs[e["variant"]]["postprocessor"]["class"]
    ]
    assert bad == [], f"registry/spec postprocessor mismatch: {bad}"


def test_every_manifest_url_uses_a_known_scheme():
    """A hand-edit must not introduce a third URL shape."""
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad = [(e["name"], u) for e in entries
           for u in (e.get("dxnn_url"), e.get("json_url")) if u
           and not u.startswith(ALLOWED_URL_PREFIXES)]
    assert bad == [], f"unknown URL scheme: {bad}"


def test_manifest_covers_every_non_alias_registry_variant():
    """Joined on the .dxnn URL basename, not on 'name'.

    The manifest's 'name' is the legacy model_name (that is what --model whitelists
    against); the variant identity lives in the URL. Joining on 'name' would look
    right for the additions and wrong for the existing 352.
    """
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    stems = {Path(e["dxnn_url"]).name[: -len(".dxnn")]
             for e in json.loads(MANIFEST.read_text(encoding="utf-8"))
             if e.get("dxnn_url")}
    wanted = {e["variant"] for e in registry if e["alias_of"] is None}
    missing = sorted(wanted - stems)
    assert missing == [], f"{len(missing)} variants have no manifest entry: {missing[:10]}"
    extra = sorted(stems - wanted)
    assert extra == [], f"{len(extra)} manifest rows match no registry variant: {extra[:10]}"


def test_manifest_has_no_duplicate_rows():
    """A stale row left behind by a re-run is invisible to a coverage check alone.

    It happened: the emitter first keyed its rows by variant and then by model_name,
    and the second run could not find the first run's rows to replace, leaving 145
    duplicates while every coverage assertion still passed.
    """
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    stems = [Path(e["dxnn_url"]).name for e in entries if e.get("dxnn_url")]
    dupe_stems = sorted({s for s in stems if stems.count(s) > 1})
    assert dupe_stems == [], f"duplicate .dxnn in the manifest: {dupe_stems[:10]}"
    names = [e["name"] for e in entries]
    dupe_names = sorted({n for n in names if names.count(n) > 1})
    assert dupe_names == [], f"duplicate name in the manifest: {dupe_names[:10]}"
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    expected = len({e["variant"] for e in registry if e["alias_of"] is None})
    assert len(entries) == expected, (
        f"manifest has {len(entries)} rows, expected {expected}")


def test_rerunning_the_emitter_is_idempotent():
    """--check must pass right after a real run, or the emitter is not idempotent."""
    import subprocess
    result = subprocess.run(
        ["../venv-dx-runtime/bin/python", "scripts/add_modelzoo_2_5_0_models.py", "--check"],
        cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
