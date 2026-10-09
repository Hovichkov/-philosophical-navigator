"""Final corpus 2026-10-07: retrieval invariants for the three experimental document modes (A move / B move+quote /
C diagnostic legacy metadata), and the per-corpus exclusion policy. Fake embeddings: these tests check structure and
policy, not retrieval quality (that is the product evaluation)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from navigator.corpus.final_corpus import (
    ACTIVE_CSV,
    FINAL_CORPUS_VERSION,
    PACKAGE_DIR,
    final_snapshot_fragments,
    load_final_active,
)
from navigator.corpus.policy import excluded_ids_for, final_excluded_ids
from navigator.models.fragment import Fragment
from navigator.models.query import QueryProvenance, QueryRepresentation, UserContext
from navigator.models.retrieval import CandidateRetrievalResult
from navigator.models.vocabularies import UNRESOLVED_IDS
from navigator.providers.fake import FakeEmbeddingClient
from navigator.representations.final_meaning import MODE_VERSIONS, MODES, load_legacy, mode_snapshot
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def final():
    return final_snapshot_fragments(load_final_active())


@pytest.fixture(scope="module")
def legacy():
    return load_legacy()


def query():
    return QueryRepresentation(
        confirmed_question="Как принять то, на что я не могу повлиять, если страх остаётся?",
        context=UserContext(circumstance="Отношения с близким человеком", narrative=None), experiences=["Страх"],
        working_hypotheses=["принятие мыслится как умственное согласие, а страх живёт отдельно",
                            "возможно, «принять» значит жить без гарантии"],
        coordinates=["принятие / сопротивление", "контроль", "страх / конечность"],
        canonical_tensions=["контроль ↔ конечность", "действие ↔ принятие"], free_tensions=[],
        provenance=QueryProvenance(origin="production", confirmed_question_source="user_confirmed",
                                   interpretation_source="test"))


def test_final_corpus_is_non_empty_unique_and_contract_clean(final):
    ids = [f.id for f in final]
    assert ids and len(ids) == len(set(ids))
    assert not set(ids) & final_excluded_ids()
    assert all(f.technical.operational_status == "final_active" and f.fragment for f in final)


def test_old_unresolved_ids_are_resolved_in_the_final_corpus_only(final):
    assert UNRESOLVED_IDS <= {f.id for f in final}  # active and verified in the final package
    assert excluded_ids_for(FINAL_CORPUS_VERSION) == final_excluded_ids()
    assert excluded_ids_for(None) == UNRESOLVED_IDS and excluded_ids_for("launch-124") == UNRESOLVED_IDS


@pytest.mark.parametrize("mode", MODES)
def test_retrieval_returns_valid_active_cards(mode, final, legacy, tmp_path):
    snap = mode_snapshot(final, mode, legacy)
    r = CandidateRetriever(snap.fragments, FakeEmbeddingClient(), cache_root=tmp_path, card_docs=snap.docs)
    assert r.corpus_version == FINAL_CORPUS_VERSION and len(r.card_ids) == len(final)
    assert all(d.version == MODE_VERSIONS[mode] for d in r.card_docs)
    res = r.retrieve(query(), f"t-{mode}")
    ids = {c.card_id for c in res.candidate_union} | {h.card_id for h in res.q0_control.hits}
    assert ids and ids <= {f.id for f in final} and not ids & final_excluded_ids()
    if mode in ("A", "B"):
        assert res.structure.hits == []  # the final corpus has no coordinates / tensions
    data = res.model_dump()
    data["q1_meaning"]["hits"][0]["card_id"] = "C0364"  # a rejected row of the package
    with pytest.raises(ValidationError):
        CandidateRetrievalResult.model_validate(data)


def test_mode_documents(final, legacy):
    by = {f.id: f for f in final}
    a, b, c = (mode_snapshot(final, m, legacy) for m in MODES)
    for d in a.docs:
        assert d.text == by[d.key].technical.launch_philosophical_move
    for d in b.docs:
        f = by[d.key]
        assert d.text == f"{f.technical.launch_philosophical_move}\n{f.fragment}"
    matched = set(c.legacy_matched)
    assert matched and len(matched) < len(final)
    for d, f in zip(c.docs, c.fragments):
        if d.key in matched:
            assert d.text.startswith("Перспектива:") and f.coordinates is not None
        else:
            assert d.text == by[d.key].technical.launch_philosophical_move and f.coordinates is None


def test_mode_c_never_writes_into_the_final_corpus(final, legacy):
    before = hashlib.sha256((PACKAGE_DIR / ACTIVE_CSV).read_bytes()).hexdigest()
    snap = mode_snapshot(final, "C", legacy)
    assert hashlib.sha256((PACKAGE_DIR / ACTIVE_CSV).read_bytes()).hexdigest() == before
    assert all(f.coordinates is None and f.perspective is None for f in final)  # the input snapshot is untouched
    by = {f.id: f for f in final}
    for f in snap.fragments:  # only STRUCTURE metadata is attached in memory; ids, text and move stay final
        o = by[f.id]
        assert (f.fragment, f.work, f.location, f.technical.launch_philosophical_move) == \
               (o.fragment, o.work, o.location, o.technical.launch_philosophical_move)


def test_legacy_guard_still_protects_the_legacy_corpus(tmp_path):
    compact = [Fragment.model_validate(json.loads(l))
               for l in (ROOT / "data/corpus/fragments.jsonl").read_text(encoding="utf-8").splitlines()]
    r = CandidateRetriever(compact, FakeEmbeddingClient(), cache_root=tmp_path)
    assert r.corpus_version is None and not set(r.card_ids) & UNRESOLVED_IDS
    data = r.retrieve(query(), "legacy").model_dump()
    data["q1_meaning"]["hits"][0]["card_id"] = "C0377"
    with pytest.raises(ValidationError):
        CandidateRetrievalResult.model_validate(data)


# ------------------------------------------------------------------ verified quotes in the final-corpus test mode


def test_final_card_shows_the_verified_quote_on_top_verbatim(final, tmp_path):
    """MVP pass 1: the final card = verified quote (top) · comment · application · ONE question. The quote is never
    rewritten; a long one is a verbatim excerpt with the whole quote behind a tap. No title / «Подробнее» / «Что
    имеется в виду?»."""
    import re

    import test_m3_3_1_human_language as base
    from navigator.composition.references import display_label

    s = base.session(final, tmp_path)
    view = s.compose()
    by = {f.id: f for f in final}
    norm = lambda t: re.sub(r"\s+", " ", t).strip()
    for p, card in zip(view["perspectives"], s.composition.perspectives):
        q, f = p["quote"], by[card.card_id]
        assert p["format"] == "final-mvp" and set(p) == {"format", "title", "source", "quote", "comment",
                                                         "application", "question"}
        if q["excerpt"]:
            assert norm(q["text"]) in norm(f.fragment) and q["full"] == f.fragment
        else:
            assert q["text"] == f.fragment and q["full"] is None
        assert p["source"] == display_label(f) and "(" not in p["source"] and "*" not in p["source"]
        assert p["question"].count("?") == 1 and p["comment"] and p["application"]
        assert q["translator"] == f.translation and q["edition"] == f.source
    ct = view["copy_text"]
    assert all(by[c.card_id].fragment in ct for c in s.composition.perspectives)


def test_final_card_always_carries_its_quote(final, tmp_path):
    import test_m3_3_1_human_language as base

    s = base.session(final, tmp_path)  # the quote is part of the final card itself (not the old show_quotes switch)
    assert all(p["quote"]["text"] for p in s.compose()["perspectives"])
