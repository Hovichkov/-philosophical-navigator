"""Quote readiness (M3.3): verified-quote contract, local verification, and the readiness audit.

A quote may be shown to a person only if it is a verbatim Russian excerpt found in a LOCAL full
source text (a file inside the project), with an exact reference and a known translation. The
model is never a source of quotes: the composer's output schema has no quote field, and a quote
can only be attached by code from a local file whose bytes are hashed and re-read at check time.

The audit classifies the retrieval-eligible cards:
- READY      — local full source text + verbatim excerpt found in it + exact reference + translator;
- PARTIAL    — the card has a candidate excerpt in project data and a known translation / reference,
               but the excerpt cannot be checked against a local copy of the edition;
- NOT_READY  — no excerpt in project data, or the excerpt / attribution is flagged as unresolved.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


from navigator.composition.references import fragment_reference
from navigator.models.fragment import Fragment
from navigator.models.quote import QuoteProvenance, VerifiedQuote  # noqa: F401  (re-exported)

INVENTORY_PATH = Path("data/quotes/QUOTE-READINESS-INVENTORY.json")
TEXTUAL_PASS = "Архив/CORPUS-LAUNCH-124-v1-final-textual-pass.md"
# Folders that hold full source texts. None exist yet (see the M3.3 report); the audit looks here.
LOCAL_SOURCE_DIRS = ("data/sources",)

# Primary Russian translation per work, from the project's source registry
# (filosofskiy-korpus-istochniki.md) or, for the Bible, from the candidate files in Источники/.
REGISTRY_TRANSLATION = {
    "Бхагавад-гита": ("В. С. Семенцов", "registry §1", "online (djvu.online), not local"),
    "Коран": ("И. Ю. Крачковский", "registry §2", "online (lib.ru), not local"),
    "Дао дэ цзин": ("Е. А. Торчинов", "registry §3", "online (djvu.online), not local"),
    "Чжуан-цзы": ("В. В. Малявин", "registry §4", "online preview only; copyright: не копируем полный текст"),
    "Лунь юй": ("Л. С. Переломов", "registry §5", "online (РГБ), not local"),
    "Дхаммапада": ("В. Н. Топоров", "registry §6", "online (dhamma.ru); эталонная копия не найдена — registry «Что ещё нужно закрыть»"),
    "Sallatha Sutta": ("переводчик по сутте (смешанный корпус)", "registry §7", "online (dhamma.ru), not local"),
    "Брихадараньяка-упанишада": ("А. Я. Сыркин", "registry §8", "online (РГБ), not local"),
    "Фрагменты ранних греческих философов": ("А. В. Лебедев", "registry §9", "PDF on author's page, not local"),
    "Диалоги Платона": ("Собрание сочинений в 4 т. (переводчик по диалогу)", "registry §10", "online (РГБ), not local"),
    "Энхиридион / Руководство": ("А. Я. Тыжов (предпочтительный)", "registry §11", "legal source not determined — registry «Что ещё нужно закрыть»"),
    "Беседы": ("Г. А. Таронян", "registry §12", "copyright: не помещаем полный текст — registry «Что ещё нужно закрыть»"),
    "Письмо к Менекею": ("М. Л. Гаспаров", "registry §13", "online (ancientrome.ru), not local"),
    "Тора / Пятикнижие": ("Новый русский перевод (НРП), 3-я ред., 2023", "Источники/corpus-torah-candidates-v1.md (не в реестре)", "no local text; source not in registry"),
    "Евангелия": ("Новый русский перевод (НРП), 3-я ред., 2023", "Источники/corpus-evangeliya-candidates-v1.md (не в реестре)", "no local text; source not in registry"),
    "Книга Иова и Экклезиаст": ("Новый русский перевод (НРП), 3-я ред., 2023", "Источники/corpus-job-ecclesiastes-candidates-v1.md (не в реестре)", "no local text; source not in registry"),
}


class QuoteNotVerified(ValueError):
    pass


def verify_quote(q: VerifiedQuote, root: Path) -> VerifiedQuote:
    """Re-read the local source file and check the quote is exactly there. Raises QuoteNotVerified."""
    p = q.provenance
    path = (root / p.source_file).resolve()
    if root.resolve() not in path.parents:
        raise QuoteNotVerified("source file is outside the project")
    if not any((root / d).resolve() in path.parents for d in LOCAL_SOURCE_DIRS):
        raise QuoteNotVerified(f"source file is not in a local source-text folder {LOCAL_SOURCE_DIRS}")
    if not path.is_file():
        raise QuoteNotVerified("local source file does not exist")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != p.source_sha256:
        raise QuoteNotVerified("local source file changed (sha256 mismatch)")
    text = data.decode("utf-8")
    if text[p.char_start:p.char_end] != q.text:
        raise QuoteNotVerified("quote text is not verbatim at the recorded position")
    return q


def quote_for_card(card_id: str, inventory: dict | None, root: Path) -> VerifiedQuote | None:
    """The only way a quote enters a result: a READY inventory row whose quote re-verifies locally."""
    if not inventory:
        return None
    row = inventory.get("cards", {}).get(card_id)
    if not row or row.get("category") != "READY" or not row.get("verified_quote"):
        return None
    try:
        return verify_quote(VerifiedQuote.model_validate(row["verified_quote"]), root)
    except (QuoteNotVerified, ValueError):
        return None


def load_inventory(root: Path) -> dict | None:
    p = root / INVENTORY_PATH
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ------------------------------------------------------------------ audit


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("ё", "е")).strip().strip("«»\"' ")


def _local_source_texts(root: Path) -> dict[str, str]:
    out = {}
    for d in LOCAL_SOURCE_DIRS:
        for p in sorted((root / d).rglob("*")) if (root / d).exists() else []:
            if p.is_file() and p.suffix in (".txt", ".md"):
                out[str(p.relative_to(root))] = _norm(p.read_text(encoding="utf-8"))
    return out


def audit(fragments: list[Fragment], root: Path) -> dict:
    local = _local_source_texts(root)
    project_md = {str(p.relative_to(root)): _norm(p.read_text(encoding="utf-8"))
                  for p in sorted(root.glob("*.md")) + sorted((root / "Архив").glob("*.md")) + sorted((root / "Источники").glob("*.md"))}
    cards = {}
    for f in fragments:
        t = f.technical.model_dump() if hasattr(f.technical, "model_dump") else dict(f.technical)
        if not t.get("retrieval_eligible"):
            continue
        excerpt = (f.thought or "").strip() or None
        flags = t.get("verification_flags") or []
        translator, registry_ref, full_text = REGISTRY_TRANSLATION.get(f.work, (None, "not in registry", "unknown"))
        in_local = [p for p, txt in local.items() if excerpt and _norm(excerpt)[:80] in txt]
        in_project = [p for p, txt in project_md.items() if excerpt and _norm(excerpt)[:60] in txt]
        loc = f.location or ""
        single_place = not re.search(r"[–-]|§§", loc)
        reasons = []
        if not local:
            reasons.append("no local full source text for any work (no files in data/sources)")
        if excerpt is None:
            reasons.append("no excerpt in project data: " + ("placeholder «вставить короткий дословный Thought»"
                           if t.get("thought_placeholder") else "TEXT not recovered (original approved YAML lost)"))
        if "unresolved_exact_text_or_attribution" in flags:
            reasons.append("flag unresolved_exact_text_or_attribution")
        if f.source_verified is False:
            reasons.append("source_verified = false")
        if excerpt and not in_local:
            reasons.append(f"excerpt exists only in project working files ({', '.join(in_project) or 'card data'}); "
                           "cannot be checked against the edition")
        if excerpt and not single_place:
            reasons.append(f"card reference is a range ({loc}); exact line of the excerpt not recorded")
        if not f.translation:
            reasons.append("card translation field empty" + (f"; registry names {translator}" if translator else ""))
        if f.work not in REGISTRY_TRANSLATION or "не в реестре" in registry_ref:
            reasons.append("work not in the source registry (translation named only in Источники/ candidate file)")
        if "copyright" in full_text or "не копируем" in full_text or "не помещаем" in full_text:
            reasons.append(f"registry copyright note: {full_text}")
        if excerpt and in_local and single_place and (f.translation or translator) and f.source_verified:
            category = "READY"
        elif excerpt and f.source_verified and "unresolved_exact_text_or_attribution" not in flags:
            category = "PARTIAL"
        else:
            category = "NOT_READY"
        cards[f.id] = {
            "card_id": f.id, "work": f.work, "tradition": f.tradition, "location": loc,
            "display_reference": fragment_reference(f), "category": category,
            "exact_reference_for_quote": single_place,
            "candidate_excerpt": excerpt,
            "excerpt_origin": (TEXTUAL_PASS if TEXTUAL_PASS in in_project else (in_project[0] if in_project else "card data"))
                              if excerpt else None,
            "excerpt_in_local_full_text": bool(in_local),
            "local_full_text_files": in_local,
            "translation_on_card": f.translation,
            "registry_translation": translator, "registry_reference": registry_ref, "registry_full_text": full_text,
            "source_verified": f.source_verified, "verification_flags": flags,
            "copyright_status_on_card": f.copyright_status,
            "reasons": reasons, "verified_quote": None,
        }
    counts = {c: sum(1 for r in cards.values() if r["category"] == c) for c in ("READY", "PARTIAL", "NOT_READY")}
    return {"inventory_version": "quote-readiness/0.1.0", "total_eligible": len(cards), "counts": counts,
            "local_source_dirs": list(LOCAL_SOURCE_DIRS), "local_source_files": sorted(local),
            "rule": "READY requires a verbatim excerpt found in a LOCAL full source text with exact reference and "
                    "translator. The model is never a source of quotes.",
            "cards": cards}
