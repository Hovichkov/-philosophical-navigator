"""Parser regressions and checks against the real source documents / canonical corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from navigator.corpus.importer import map_coordinates, map_tensions
from navigator.corpus.sources import SOURCE_FILES, _load_yaml, _quote_list_items, load_sources
from navigator.corpus.validator import validate_corpus_file
from navigator.models.vocabularies import COORDINATES, TENSIONS, UNRESOLVED_IDS

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus/fragments.jsonl"
MANIFEST = ROOT / "data/corpus/launch-manifest.json"
NOT_RECOVERED_4 = {"C1105", "C0957", "C0937", "C0949"}

needs_sources = pytest.mark.skipif(
    not all((ROOT / p).exists() for p in SOURCE_FILES), reason="source documents not available"
)
needs_corpus = pytest.mark.skipif(not CORPUS.exists(), reason="canonical corpus not built")


def _records() -> dict[str, dict]:
    return {json.loads(line)["id"]: json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines()}


def test_yaml_keeps_locations_as_text():
    data = _load_yaml("location: 2.10\nother: 12.1\nflag: true\nnothing: null\n")
    assert data == {"location": "2.10", "other": "12.1", "flag": True, "nothing": None}


def test_quoting_keeps_prose_list_items_verbatim():
    block = "q:\n  - Какой ход в ситуации: `жэнь` связывается?\n  - []\n"
    assert _load_yaml(_quote_list_items(block))["q"][0] == "Какой ход в ситуации: `жэнь` связывается?"


def test_registry_label_mapping_is_total_and_preserves_qualifier():
    assert set(map_coordinates(["desire", "belonging"])) <= COORDINATES
    assert map_tensions(["desire ↔ duty (potential)", "expectation ↔ reality"]) == [
        "желание ↔ долг (potential)",
        "ожидание ↔ действительность",
    ]
    with pytest.raises(ValueError):
        map_coordinates(["hope"])
    with pytest.raises(ValueError):
        map_tensions(["hope ↔ despair"])


@needs_sources
def test_sources_cover_launch_124():
    src = load_sources(ROOT)
    launch = [r.id for r in src.launch]
    assert len(launch) == len(set(launch)) == 124
    assert len(src.audit) == 113
    assert set(src.unresolved_v2_0) == UNRESOLVED_IDS
    assert {r.id for r in src.audit} | set(src.unresolved_v2_0) == set(launch)
    assert {c.id for c in src.textual_pass} | set(src.recovery) == set(launch)
    assert not ({c.id for c in src.textual_pass} & set(src.recovery))
    assert {k for k, r in src.recovery.items() if not r.registry_recovered} == NOT_RECOVERED_4


@needs_corpus
def test_canonical_corpus_closes_m1():
    result = validate_corpus_file(CORPUS, MANIFEST)
    assert result.ok, [i for i in result.errors][:5]
    assert result.actual_count == 124 and len(result.fragments) == 124
    assert len(result.allowlist) == 113
    assert not set(result.allowlist) & UNRESOLVED_IDS
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest["unresolved_ids"]) == UNRESOLVED_IDS
    assert manifest["retrieval_allowlist"] == result.allowlist
    assert manifest["routes"]["SOURCE"] == "disabled_pending_full_fragment_text"


@needs_corpus
def test_unresolved_kept_for_audit_and_excluded():
    recs = _records()
    for fid in UNRESOLVED_IDS:
        assert recs[fid]["technical"]["operational_status"] == "unresolved"
        assert recs[fid]["technical"]["retrieval_eligible"] is False


@needs_corpus
def test_source_corrections_preserved():
    recs = _records()
    assert (recs["C0246"]["work"], recs["C0246"]["location"]) == ("Sallatha Sutta", "SN 36.6")
    assert recs["C0215"]["location"] == "SN 22.59"
    assert recs["C0230"]["location"].startswith("MN 21")
    assert recs["C0258"]["location"] == "AN 6.55"
    assert all("56.11" not in (recs[f]["work"] or "") for f in ("C0246", "C0215", "C0230", "C0258"))


@needs_corpus
def test_first_29_recovery_imports_without_invention():
    recs = _records()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    first_29 = manifest["first_29_recovery"]["records"]
    assert len(first_29) == 29
    for fid in first_29:
        r = recs[fid]
        assert r["technical"]["recovery_status"] is not None  # original provenance kept
        assert r["technical"]["old_yaml_status"] == "original approved YAML not physically recovered"
        # TEXT / verification were never recovered and must not be synthesised
        for field in ("fragment", "thought", "context", "commentary",
                      "translation", "source", "source_verified", "interpretation_verified"):
            assert r[field] is None, (fid, field)
        assert r["perspective"] and set(r["coordinates"]) <= COORDINATES
        assert all(t.removesuffix(" (potential)") in TENSIONS for t in r["tensions"])
        prov = r["technical"]["field_provenance"]
        if fid in NOT_RECOVERED_4:
            # M1.5: level-2 recovery from CORPUS-FULL-1090, explicitly marked
            assert r["technical"]["recovery_status"].startswith("approved_batch_membership_confirmed")
            for field in ("perspective", "coordinates", "tensions"):
                assert prov[field].startswith("RECOVERED level 2 from CORPUS-FULL-1090")
            assert prov["philosophical_questions"].startswith("RECONSTRUCTED")
            assert len(r["philosophical_questions"]) == 1
        else:
            assert r["philosophical_questions"] is None


@needs_corpus
def test_canonical_corpus_contains_no_placeholders_or_runtime_fields():
    for rec in _records().values():
        for field in ("thought", "translation"):
            assert rec[field] is None or "[FINAL TEXTUAL PASS" not in rec[field]
        assert "required_assumption" not in rec
