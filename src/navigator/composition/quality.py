"""M3.2 property checks for a composed result (regression / reference cases, control runs).

Deterministic and structural only — they never judge meaning. Usefulness of a distinction and the
absence of subtle personal claims remain a matter of the prompt and of human review.
"""

from __future__ import annotations

import re

from navigator.composition.composer import source_label
from navigator.models.composition import (
    MAX_SENTENCE_WORDS,
    CompositionResult,
    meta_hits,
    sentences,
    word_count,
)
from navigator.models.fragment import Fragment
from navigator.models.interpretation import amplification_hits
from navigator.models.vocabularies import UNRESOLVED_IDS

USER_FIELDS = ("title", "main_idea", "applied_insight", "reflection_question", "question_explanation", "perspective")


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}


def property_checks(result: CompositionResult, fragments: list[Fragment], not_in_user_words: list[str] = ()) -> list[dict]:
    by_id = {f.id: f for f in fragments}
    ps = result.perspectives
    out = [
        _check("2–3 perspectives", 2 <= len(ps) <= 3, str(len(ps))),
        _check("2 perspectives carry a reason", len(ps) == 3 or bool(result.fewer_than_three_reason),
               result.fewer_than_three_reason or ""),
    ]
    distinctions = [re.sub(r"\W+", " ", (p.distinction or "").lower()).strip() for p in ps]
    out.append(_check("distinct insights (internal distinctions differ)", len(set(distinctions)) == len(distinctions)))
    for i, p in enumerate(ps, 1):
        tag = f"card {i}"
        user_text = " ".join(getattr(p, f) or "" for f in USER_FIELDS)
        invented = [pat for pat in not_in_user_words if re.search(pat, user_text, flags=re.IGNORECASE)]
        applied_sent = sentences(p.applied_insight or "")
        out += [
            _check(f"{tag}: declarative title", bool(p.title) and "?" not in p.title, p.title),
            _check(f"{tag}: one internal distinction", bool(p.distinction) and bool(re.search(r"различ|увидеть", p.distinction, re.I)),
                   p.distinction or ""),
            _check(f"{tag}: no guarded personal claims", not amplification_hits(user_text)),
            _check(f"{tag}: nothing the user did not say (case list)", not invented, ", ".join(invented)),
            _check(f"{tag}: simple applied insight", 1 <= len(applied_sent) <= 3
                   and all(word_count(s) <= MAX_SENTENCE_WORDS for s in applied_sent), f"{len(applied_sent)} sentences"),
            _check(f"{tag}: one question or two short linked ones (M3.3)", 1 <= p.reflection_question.count("?") <= 2
                   and len(sentences(p.reflection_question)) <= 2),
            _check(f"{tag}: simple reflection question", word_count(p.reflection_question) <= 30
                   and p.reflection_question.count(",") <= 3, f"{word_count(p.reflection_question)} words"),
            _check(f"{tag}: no model-supplied quote", p.verified_quote is None
                   or p.verified_quote.provenance.method == "local_source_match"),
            _check(f"{tag}: question explanation exists", bool(p.question_explanation) and "?" not in (p.question_explanation or "")),
            _check(f"{tag}: no meta-language in main card", not meta_hits(" ".join(
                [p.title, p.main_idea or "", p.applied_insight or "", p.reflection_question, p.question_explanation or ""]))),
            _check(f"{tag}: source grounded in corpus", p.card_id in by_id and p.card_id in result.candidate_pool
                   and p.card_id not in UNRESOLVED_IDS and p.source == source_label(by_id[p.card_id]), p.source),
        ]
    return out


def failed(checks: list[dict]) -> list[dict]:
    return [c for c in checks if not c["ok"]]
