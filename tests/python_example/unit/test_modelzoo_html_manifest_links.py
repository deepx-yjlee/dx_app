# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Three-way check: DX Model Zoo.html <-> modelzoo_manifest.json <-> the examples.

An example is only usable if the model behind it can be downloaded, and that chain has
three independent links: the zoo page offers a file, the manifest points a name at that
file's URL, and an example variant config exists for the stem. Each pair has drifted at
least once.

The check is TIER-AWARE, which the first attempt was not. The page offers the same
model under three quantisation tiers -- measured 350 q-lite, 341 q-pro, 15 q-master --
and comparing every manifest row against the q-lite list alone reported 7 mismatches of
which 4 were fine: beit-l-p16_384x384, levit-128s_224x224, vit-b-p16_384x384 and
vit-t-p16_224x224 are q-master entries, listed on the page and downloadable (HTTP 200).

Rows whose URL is a `/2_5_0/` path are excluded: those are models the zoo has announced
but not published, so no 2_4_0 link exists for them by construction.

The page itself is not committed, so the tests skip when it is absent rather than
failing a checkout that never had it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
HTML = PROJECT_ROOT / "DX Model Zoo.html"
MANIFEST = PROJECT_ROOT / "scripts" / "modelzoo_manifest.json"
REGISTRY = PROJECT_ROOT / "config" / "model_registry.json"

PENDING = "/2_5_0/"
URL = re.compile(r"https://sdk\.deepx\.ai/modelzoo/([a-z0-9-]+)/([0-9_]+)/([^\"' ]+\.dxnn)")

# The zoo page lists PPU models only under the current naming (<arch>_<res>_ppu), and
# these two predate it. Their manifest rows therefore point at the LEGACY
# `modelzoo/dxnn/` tier, which the page does not list at all -- and which still
# resolves: both were measured at HTTP 200 there, and 403 under q-lite. So the entries
# are correct and the page is simply silent about them; rewriting them to a tier the
# page does list is what breaks them.
LEGACY_TIER_ROWS = {"SCRFD500M_PPU", "YOLOV5Pose_PPU"}


def _requires_html():
    if not HTML.is_file():
        pytest.skip(f"{HTML.name} is not in this checkout")


@pytest.fixture(scope="module")
def html_links() -> dict:
    """``{(tier, version): {filename}}`` for every .dxnn the page offers."""
    _requires_html()
    text = HTML.read_text(encoding="utf-8", errors="replace")
    links: dict = {}
    for tier, version, filename in URL.findall(text):
        links.setdefault((tier, version), set()).add(filename)
    return links


@pytest.fixture(scope="module")
def manifest() -> list:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry() -> list:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def variant_configs() -> set:
    return {p.parent.name for p in
            (PROJECT_ROOT / "src" / "python_example").glob("*/*/*/config.json")}


def _parsed(manifest: list):
    for row in manifest:
        match = URL.fullmatch(row.get("dxnn_url") or "")
        yield row, (match.groups() if match else None)


# --------------------------------------------------------------------- manifest shape
def test_every_manifest_url_is_a_modelzoo_url(manifest):
    bad = [row["name"] for row, parts in _parsed(manifest) if parts is None]
    assert not bad, f"unparsable dxnn_url on: {bad}"


def test_the_manifest_covers_every_example_variant(manifest, variant_configs):
    """An example whose model is in no manifest row cannot be downloaded at all."""
    files = {parts[2] for _row, parts in _parsed(manifest) if parts}
    orphans = sorted(v for v in variant_configs if f"{v}.dxnn" not in files)
    assert not orphans, f"example variants with no manifest row: {orphans}"


def test_no_manifest_row_is_duplicated(manifest):
    stems = [parts[2] for _row, parts in _parsed(manifest) if parts]
    duplicated = sorted({s for s in stems if stems.count(s) > 1})
    assert not duplicated, f"duplicate manifest rows: {duplicated}"


# ------------------------------------------------------------------ manifest <-> page
def test_every_published_manifest_row_is_offered_by_the_page(manifest, html_links):
    missing = []
    for row, parts in _parsed(manifest):
        if not parts:
            continue
        tier, version, filename = parts
        if version == "2_5_0" or row["name"] in LEGACY_TIER_ROWS:
            continue
        if filename not in html_links.get((tier, version), set()):
            missing.append(f"{row['name']} -> {tier}/{version}/{filename}")
    assert not missing, (
        "manifest rows the zoo page does not offer at that tier:\n  "
        + "\n  ".join(missing))


def test_every_offered_q_lite_model_has_an_example(html_links, variant_configs):
    """The other direction: a model on the page that no example can run."""
    offered = html_links.get(("q-lite-dxnn", "2_4_0"), set())
    assert offered, "no q-lite links parsed from the page"
    unused = sorted(f for f in offered if Path(f).stem not in variant_configs)
    assert not unused, f"models offered by the page with no example variant: {unused}"


# -------------------------------------------------------------- registry consistency
def test_the_registry_and_the_manifest_agree_on_every_file(manifest, registry):
    manifest_files = {parts[2] for _row, parts in _parsed(manifest) if parts}
    registry_files = {m["dxnn_file"] for m in registry}
    assert registry_files == manifest_files, (
        f"only in registry: {sorted(registry_files - manifest_files)}\n"
        f"only in manifest: {sorted(manifest_files - registry_files)}")


def test_a_published_row_means_a_2_4_0_url(manifest, registry):
    """`published` drives the downloader, which treats 403 on a 2_4_0 URL as an error
    and only tolerates it behind the /2_5_0/ pending marker."""
    by_file = {parts[2]: parts for _row, parts in _parsed(manifest) if parts}
    wrong = [m["variant"] for m in registry
             if m["published"] and by_file.get(m["dxnn_file"], ("", "", ""))[1] == "2_5_0"]
    assert not wrong, f"published but pointing at a pending 2_5_0 URL: {wrong}"
