"""Restored full corpus (data/corpus-full): CORPUS-FULL-1090 in the current Fragment schema.

Why. The 124 launch corpus is a greedy set-cover of a coverage matrix (Архив/minimum-viable-coverage-analysis-v1.md),
chosen to cover coordinates / tensions / perspective families / traditions with a minimum number of cards — not for
semantic resolution. The 1090 registry is the curated pool after two functional deduplication passes (1116 → 1090,
Архив/suboperation-compression-review-v1.md). This module brings it back as DATA into the current architecture;
nothing is generated and no text is reconstructed.

Rules (deterministic, no model):
- the 124 launch Fragments are copied verbatim (same fields, same status: 113 verified / 11 unresolved);
- every other registry row becomes a Fragment:
    SOURCE     tradition, work, location from the registry (author_speaker kept in registry_reference, as for the 124);
               the 62 early Pali sutta rows have a broken work/location in the registry (every row carries the first
               sutta's name, «location» holds the entry title) — work/location are recovered from the section headings
               of Источники/corpus-early-pali-suttas-candidates-v1.md by the entry title; unmatched rows are not
               retrieval-eligible;
    MEANING    perspective = registry perspective; philosophical_questions = the textual-pass convention built from the
               registry philosophical move (same template as the 124); coordinates / tensions mapped EN→RU 1:1
               (TAXONOMY v1.1, as the launch importer does);
    TEXT       none — the registry has no source text (neither do the 124: fragment is null, thought is a placeholder);
    OPERATION  philosophical_operation / question_structures: none (the operation audit covered only the 113).
- status: main rows → ``registry_curated`` (retrieval-eligible); reserve rows → ``registry_reserve`` (stored, not
  eligible: their registry perspective is a placeholder «[reserve; preliminary …]» and the move is a 2–6 word topic
  label, so there is no project-sourced meaning to retrieve by).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from navigator.corpus.importer import launch_move_question, map_coordinates, map_tensions
from navigator.corpus.sources import REGISTRY_1090, RegistryRow, parse_registry
from navigator.models.fragment import Fragment, FragmentTechnical, RegistryReference

FULL_CORPUS_DIR = Path("data/corpus-full")
FULL_CORPUS_VERSION = "corpus-full/1.0.0"
PALI_SOURCE = Path("Источники/corpus-early-pali-suttas-candidates-v1.md")
PALI_BROKEN_WORK = "Дхаммачаккаппаваттана сутта — СН 56.11"
BASIS = "FULL-CORPUS-RESTORATION: CORPUS-FULL-1090-v1.md (main → registry_curated, reserve → registry_reserve)"


def _norm(t: str) -> str:
    return " ".join(re.findall(r"\w+", t.lower().replace("ё", "е")))


def pali_sections(path: Path) -> list[tuple[str, str, str]]:
    """(entry title, work, location) from «### <sutta> — <ref>» / «#### N. <title>» headings."""
    out, work, loc = [], None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^### (?!#)(.+?)\s+—\s+(.+)$", line)
        if m:
            work, loc = m.group(1).strip(), m.group(2).strip()
            continue
        m = re.match(r"^####\s+(?:R?\d+\.\s+)?(.+)$", line)
        if m and work:
            out.append((m.group(1).strip(), work, loc))
    return out


def recover_pali(title: str, sections: list[tuple[str, str, str]]) -> tuple[str, str] | None:
    """Unique match of the registry entry title to a source entry title (exact, else prefix)."""
    t = _norm(title)
    exact = [s for s in sections if _norm(s[0]) == t]
    cands = exact or [s for s in sections if _norm(s[0]).startswith(t) or t.startswith(_norm(s[0]))]
    works = {(s[1], s[2]) for s in cands}
    return next(iter(works)) if len(works) == 1 else None


_CANON_REF = r"(?:МН|СН|АН|ДН|Сн|Уд|Ит|Кх)\s*\d+(?:\.\d+)?"


def inline_pali_reference(cell: str) -> tuple[str, str] | None:
    """Rows whose «location» cell is itself a bold reference («**МН 19 Дведха-витакка**», «**Махамангала сутта
    Сн 2.4**», «**СН 35.26**»): (work, location). The sutta name becomes the work; a bare reference keeps
    «Палийский канон» as the work."""
    t = cell.strip().strip("*").strip()
    m = re.search(_CANON_REF, t)
    if not m:
        return None
    ref = t[m.start():].split(",")[0].split("/")[0].strip()
    ref = re.match(_CANON_REF, ref).group(0)
    after = t[m.end():]
    after = "" if after.lstrip().startswith(",") else after  # «Уд 1.10, финал»: text after a comma is a note
    name = (t[:m.start()] + after).strip(" ,/–—")
    name = re.sub(r"\s*,.*$", "", name).split("/")[0].strip()
    if not name:
        return "Палийский канон", ref
    return (name if "сутта" in name.lower() else f"{name} сутта"), ref


def _registry_ref(r: RegistryRow) -> RegistryReference:
    return RegistryReference(status=r.status, decision=r.decision, author_speaker=r.author_speaker or None,
                             work=r.work or None, location=r.location or None,
                             philosophical_move=r.philosophical_move or None, perspective=r.perspective or None,
                             coordinates_en=list(r.coordinates_en), tensions_en=list(r.tensions_en))


def restored_fragment(r: RegistryRow, pali: list[tuple[str, str, str]]) -> tuple[Fragment, list[str]]:
    notes: list[str] = []
    prov = {"SOURCE": f"{REGISTRY_1090} (tradition, work, location)",
            "MEANING": f"{REGISTRY_1090}: perspective; philosophical_questions from the philosophical move "
                       "(textual-pass template); coordinates/tensions EN→RU (TAXONOMY v1.1)",
            "TEXT": "none in project data (registry has no source text)",
            "OPERATION": "none (OPERATION-AUDIT covered only the 113 launch cards)"}
    work, location = r.work, r.location
    eligible = r.status == "main"
    if r.work == PALI_BROKEN_WORK:
        found = recover_pali(r.location, pali) or inline_pali_reference(r.location)
        if found:
            work, location = found
            prov["SOURCE"] = (f"{PALI_SOURCE} section heading matched by entry title «{r.location}» "
                              f"(registry work/location broken: «{r.work}» / «{r.location}»)")
            notes.append(f"{r.id}: Pali work/location recovered → {work}, {location}")
        else:
            eligible = False
            notes.append(f"{r.id}: Pali work/location NOT recovered (title «{r.location}»); not retrieval-eligible")
    reserve = r.status != "main"
    if reserve:
        notes.append(f"{r.id}: reserve row — placeholder perspective, topic-label move; stored, not eligible")
    perspective = None if reserve else (r.perspective or None)
    move = r.philosophical_move or None
    pq = [launch_move_question(move)] if (move and not reserve) else None
    f = Fragment(
        id=r.id, tradition=r.tradition or None, author=None, work=work or None, location=location or None,
        philosophical_questions=pq, coordinates=map_coordinates(list(r.coordinates_en)),
        tensions=map_tensions(list(r.tensions_en)), perspective=perspective,
        source=f"{work}, {location}" if work and location else None,
        copyright_status="check_per_approved_source_registry", source_verified=False, interpretation_verified=False,
        technical=FragmentTechnical(
            corpus_status="restored_registry",
            operational_status="registry_reserve" if reserve else "registry_curated",
            retrieval_eligible=bool(eligible and not reserve and perspective and pq),
            operational_status_basis=BASIS,
            launch_philosophical_move=move, launch_location=location,
            has_textual_pass_card=False, in_operation_audit_113=False,
            historical_unresolved_status_v2_0=False, historical_unresolved_textual_pass=False,
            field_provenance=prov, registry_reference=_registry_ref(r),
        ),
    )
    return f, notes


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble_full(root: Path) -> tuple[list[Fragment], dict]:
    launch = [Fragment.model_validate(json.loads(l))
              for l in (root / "data/corpus/fragments.jsonl").read_text(encoding="utf-8").splitlines()]
    by_launch = {f.id: f for f in launch}
    registry = parse_registry(root / REGISTRY_1090)
    pali = pali_sections(root / PALI_SOURCE)
    out, notes = [], []
    for rid in sorted(set(registry) | set(by_launch)):
        if rid in by_launch:
            out.append(by_launch[rid])  # verbatim: the launch card, its status and textual-pass content
            continue
        f, n = restored_fragment(registry[rid], pali)
        out.append(f)
        notes += n
    elig = [f for f in out if f.technical.retrieval_eligible]
    manifest = {
        "corpus_version": FULL_CORPUS_VERSION,
        "built_from": {
            "data/corpus/fragments.jsonl": sha256(root / "data/corpus/fragments.jsonl"),
            str(REGISTRY_1090): sha256(root / REGISTRY_1090),
            str(PALI_SOURCE): sha256(root / PALI_SOURCE),
        },
        "counts": {
            "total": len(out),
            "registry_rows": len(registry),
            "launch_cards_copied_verbatim": len(launch),
            "launch_ids_not_in_registry": sorted(set(by_launch) - set(registry)),
            "retrieval_eligible": len(elig),
            "by_status": {s: sum(1 for f in out if f.technical.operational_status == s)
                          for s in ("verified", "unresolved", "registry_curated", "registry_reserve")},
            "registry_curated_not_eligible": sorted(f.id for f in out if f.technical.operational_status ==
                                                    "registry_curated" and not f.technical.retrieval_eligible),
        },
        "retrieval_eligible_ids": [f.id for f in elig],
        "rules": __doc__.split("Rules (deterministic, no model):", 1)[1].strip(),
        "notes": notes,
    }
    return out, manifest


def write_full(root: Path) -> dict:
    frags, manifest = assemble_full(root)
    d = root / FULL_CORPUS_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "fragments.jsonl").write_text(
        "".join(json.dumps(f.model_dump(mode="json", exclude_none=False), ensure_ascii=False) + "\n" for f in frags),
        encoding="utf-8")
    manifest["fragments_sha256"] = sha256(d / "fragments.jsonl")
    (d / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
