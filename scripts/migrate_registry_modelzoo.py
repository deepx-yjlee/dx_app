#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""One-shot: add the dx-modelzoo alignment fields to config/model_registry.json.

Adds six fields per entry, joining tests/data/modelzoo_cv_tree.json by dxnn stem:

    variant        identity used by --variant and assets/models/<variant>.dxnn
    family         dx-modelzoo family, snake_cased for import safety
    task           dx-modelzoo task name (one of 23)
    task_legacy    the pre-alignment add_model_task value, preserved verbatim
    image_only     per-variant replacement for the task-keyed _IMAGE_ONLY_TASKS
    zoo_canonical  True iff the variant exists in the dx-modelzoo snapshot
    duplicate_of   model_name this entry duplicates, else None

Phase 0 is additive only: it never drops an entry, because the example trees
still contain a directory per entry. The single redundant entry is *marked*
via duplicate_of and actually removed in Phase 2, where the trees restructure.

Existing fields are left untouched and key order is preserved, so the diff shows
only additions. Idempotent: re-running overwrites the six fields with the same
values.

Usage:
    python scripts/migrate_registry_modelzoo.py            # write
    python scripts/migrate_registry_modelzoo.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = PROJECT_ROOT / "config" / "model_registry.json"
SNAPSHOT = PROJECT_ROOT / "tests" / "data" / "modelzoo_cv_tree.json"

# model_name -> (variant, task, family); the entries the snapshot cannot supply.
EXCEPTIONS: dict[str, tuple[str, str, str]] = {
    "efficientnet_lite0":     ("efficientnet-lite0_256x256", "image_classification", "efficientnet"),
    "scrfd500m_ppu":          ("SCRFD500M_PPU",              "face_detection",       "scrfd"),
    "yolov5pose_ppu":         ("YOLOV5Pose_PPU",             "pose_estimation",      "yolov5_pose"),
}

# Entries that duplicate another entry's model: same dxnn, no distinct variant.
# ``deit_base384_distilled`` is byte-identical to ``deitbase384`` apart from
# model_name and points at the NON-distilled deit-b_384x384.dxnn -- its name is
# simply wrong. The real distilled 384 model is ``deit-b_384x384_distilled``,
# already owned by the entry whose dxnn_file is deit-b_384x384_distilled.dxnn.
# duplicate -> the model_name it duplicates.
DUPLICATES: dict[str, str] = {
    "deit_base384_distilled": "deitbase384",
}

# src/python_example/common/runner/sync_runner.py::_IMAGE_ONLY_TASKS, expressed in
# add_model_task terms ("3d_detection" is the runner's alias for this task).
IMAGE_ONLY_LEGACY_TASKS = {
    "embedding", "reid", "attribute_recognition",
    "object_pose_estimation", "3d_object_detection",
}

NEW_FIELDS = ("variant", "family", "task", "task_legacy", "image_only",
              "zoo_canonical", "duplicate_of")


def _snake(family: str) -> str:
    return family.replace("-", "_").replace(".", "_")


def migrate(registry: list[dict], snapshot: dict[str, dict]) -> tuple[list[dict], dict]:
    out: list[dict] = []
    stats = {"from_snapshot": 0, "from_exceptions": 0, "image_only": 0,
             "duplicates": 0, "unresolved": []}

    for entry in registry:
        name = entry["model_name"]
        stem = entry["dxnn_file"][: -len(".dxnn")]

        if name in EXCEPTIONS:
            variant, task, family = EXCEPTIONS[name]
            canonical = variant in snapshot
            stats["from_exceptions"] += 1
        elif stem in snapshot:
            variant = stem
            task = snapshot[stem]["task"]
            family = _snake(snapshot[stem]["family"])
            canonical = True
            stats["from_snapshot"] += 1
        else:
            stats["unresolved"].append(name)
            continue

        image_only = entry["add_model_task"] in IMAGE_ONLY_LEGACY_TASKS
        if image_only:
            stats["image_only"] += 1
        if name in DUPLICATES:
            stats["duplicates"] += 1

        # Rebuild so the six new fields land after the existing ones in a stable order.
        merged = {k: v for k, v in entry.items() if k not in NEW_FIELDS}
        merged.update(
            variant=variant,
            family=family,
            task=task,
            task_legacy=entry["add_model_task"],
            image_only=image_only,
            zoo_canonical=canonical,
            duplicate_of=DUPLICATES.get(name),
        )
        out.append(merged)

    return out, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    args = ap.parse_args()

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["variants"]
    migrated, stats = migrate(registry, snapshot)

    if stats["unresolved"]:
        raise SystemExit(
            "cannot resolve variant/task/family for: "
            f"{stats['unresolved']}\nAdd them to EXCEPTIONS or refresh the snapshot."
        )
    if len(migrated) != len(registry):
        raise SystemExit(f"entry count changed: {len(registry)} -> {len(migrated)}")

    print(f"entries={len(migrated)} from_snapshot={stats['from_snapshot']} "
          f"from_exceptions={stats['from_exceptions']} image_only={stats['image_only']} "
          f"duplicates={stats['duplicates']}")
    tasks = {e["task"] for e in migrated}
    families = {(e["task"], e["family"]) for e in migrated}
    canonical = [e for e in migrated if e["duplicate_of"] is None]
    print(f"tasks={len(tasks)} families={len(families)} "
          f"canonical_variants={len({e['variant'] for e in canonical})}/{len(canonical)}")

    if args.dry_run:
        print("dry-run: config/model_registry.json not written")
        return
    REGISTRY.write_text(json.dumps(migrated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {REGISTRY.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
