"""Assemble canonical ``data/corpus/fragments.jsonl`` from the launch-corpus documents.

Field precedence (no field is ever filled from a lower-authority document):

- SOURCE / TEXT / MEANING / RELATIONS / VERIFICATION:
    1. textual-pass YAML card (CORPUS-LAUNCH-124-v1-final-textual-pass.md) — 95 cards;
    2. for the first 29 (no surviving YAML): CORPUS-LAUNCH-FIRST-29-recovery-source-v0.2.md.
       Its 25 recovered registry rows give SOURCE, perspective, coordinates and
       tensions (``recovery_status`` is kept verbatim, fields are marked as
       reconstructed in ``field_provenance``). For the 4 without a recovered row
       only launch-table SOURCE is used and semantic fields stay ``None``;
    3. SOURCE falls back to the launch table (CORPUS-LAUNCH-124-v.md).
- philosophical_operation / question_structures:
    OPERATION-AUDIT-launch-113-v0.1.md; ``None`` for cards outside the audit.
- operational status: 113 verified / 11 unresolved (CLOSEOUT-PROMPT §1). The 11
  stay in the corpus for audit but are excluded from the retrieval allowlist.
- CORPUS-FULL-1090 is attached as ``technical.registry_reference`` for
  traceability only; it never fills a canonical field.

Editorial placeholders (``[FINAL TEXTUAL PASS: …]``, «зафиксировать по
утверждённому реестру…») are instructions, not source text: they are moved
verbatim into ``technical.*_placeholder`` and the content field stays ``None``.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from navigator.corpus.sources import (
    FIRST_29_RECOVERY,
    sha256,
    LAUNCH_TABLE,
    OPERATION_AUDIT,
    REGISTRY_1090,
    TEXTUAL_PASS,
    RecoveryRecord,
    SourceBundle,
    load_sources,
)
from navigator.models.fragment import SCHEMA_VERSION, Fragment, FragmentTechnical, RegistryReference, Relations
from navigator.models.vocabularies import (
    COORDINATES_EN_TO_RU,
    LAUNCH_SHORTLIST_COUNT,
    PLACEHOLDER_MARKERS,
    RETRIEVAL_VERIFIED_COUNT,
    SOURCE_ROUTE_STATUS,
    TENSION_QUALIFIER,
    TENSIONS_EN_TO_RU,
    UNRESOLVED_IDS,
)

CORPUS_VERSION = "launch-124/0.3.0-m1.5-retrieval-readiness"
CURATION_DIR = Path("data/corpus/curation")
EXPECTED_COUNT = LAUNCH_SHORTLIST_COUNT

TEMPLATE_PREFIXES = {
    "context": "Launch-кандидат фиксирует следующий исходный ход:",
    "commentary": "Рабочее прочтение следует непосредственно за этим ходом:",
    "perspective": "Рассмотреть ситуацию через операцию, которую задаёт сам фрагмент:",
}


def _text(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"expected text, got {type(value).__name__}: {value!r}")
    value = value.strip()
    return value or None


def _is_placeholder(value: str | None) -> bool:
    return value is not None and any(m in value for m in PLACEHOLDER_MARKERS)


def _str_list(value) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise TypeError(f"expected a list of text items, got {value!r}")
    return [v.strip() for v in value]


def _registry_tags(cell: str | None) -> list[str]:
    if cell is None:
        return []
    return [t.strip() for t in cell.split(",") if t.strip() and t.strip() != "—"]


def map_coordinates(values: list[str]) -> list[str]:
    try:
        return [COORDINATES_EN_TO_RU[v] for v in values]
    except KeyError as exc:
        raise ValueError(f"registry coordinate {exc} has no TAXONOMY v1.1 mapping") from None


def map_tensions(values: list[str]) -> list[str]:
    out = []
    for v in values:
        base, qualifier = (v[: -len(TENSION_QUALIFIER)], TENSION_QUALIFIER) if v.endswith(TENSION_QUALIFIER) else (v, "")
        if base not in TENSIONS_EN_TO_RU:
            raise ValueError(f"registry tension «{v}» has no TAXONOMY v1.1 mapping")
        out.append(TENSIONS_EN_TO_RU[base] + qualifier)
    return out


def assemble(src: SourceBundle) -> tuple[list[Fragment], dict]:
    cards = {c.id: c for c in src.textual_pass}
    audit = {r.id: r for r in src.audit}
    recovery: dict[str, RecoveryRecord] = src.recovery
    tp_unresolved = set(src.textual_pass_status.get("unresolved_ids", []))
    v20_unresolved = set(src.unresolved_v2_0)
    notes: list[dict] = []

    def note(kind: str, fid: str | None, detail: str) -> None:
        notes.append({"kind": kind, "fragment_id": fid, "detail": detail})

    launch_ids = [r.id for r in src.launch]
    for dup in sorted(k for k, v in Counter(launch_ids).items() if v > 1):
        note("DUPLICATE_LAUNCH_ID", dup, "ID appears more than once in the launch table")
    for extra in sorted(set(cards) - set(launch_ids)):
        note("TEXTUAL_PASS_CARD_NOT_IN_LAUNCH", extra, "textual-pass card is not in the launch table; not imported")
    for extra in sorted(set(audit) - set(launch_ids)):
        note("AUDIT_ROW_NOT_IN_LAUNCH", extra, "operation-audit row is not in the launch table; not imported")
    for extra in sorted(set(recovery) - set(launch_ids)):
        note("RECOVERY_RECORD_NOT_IN_LAUNCH", extra, "recovery record is not in the launch table; not imported")
    for both in sorted(set(recovery) & set(cards)):
        note("RECOVERY_AND_CARD", both, "recovery record ignored: a textual-pass card exists")
    if v20_unresolved != UNRESOLVED_IDS:
        note(
            "UNRESOLVED_SOURCE_MISMATCH",
            None,
            f"operational-status-v2.0 unresolved {sorted(v20_unresolved)} differs from the closeout rule {sorted(UNRESOLVED_IDS)}",
        )
    for c in src.textual_pass:
        if c.yaml_repaired:
            note(
                "YAML_REPAIRED",
                c.id,
                "YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); "
                "list items were quoted verbatim and re-parsed",
            )

    fragments: list[Fragment] = []
    for row in src.launch:
        fid = row.id
        card = cards.get(fid)
        rec = recovery.get(fid) if card is None else None
        rec_fields = rec.fields if rec and rec.registry_recovered else None
        a = audit.get(fid)
        reg = src.registry.get(fid)
        prov: dict[str, str] = {}

        # ---------------- SOURCE
        if card:
            s = card.data.get("SOURCE", {})
            tradition, author = _text(s.get("tradition")), _text(s.get("author"))
            work, location = _text(s.get("work")), _text(s.get("location"))
            launch_location, speaker = _text(s.get("launch_location")), _text(s.get("speaker"))
            prov["SOURCE"] = str(TEXTUAL_PASS)
            origin = "textual pass"
        elif rec_fields:
            # tradition: the launch shortlist value is the harmonised launch-level label
            # (shared with the audit and the 95 cards); the recovered registry label is
            # pre-launch and is recorded as a resolved conflict. work/location come
            # from the recovery source, which carries the accepted C0246 correction.
            tradition, author = row.tradition, None
            work, location = rec_fields.get("work"), rec_fields.get("location")
            launch_location, speaker = row.location, None
            prov["SOURCE"] = (
                f"work/location: {FIRST_29_RECOVERY} (recovered registry row); tradition: {LAUNCH_TABLE}; "
                "author_speaker kept in registry_reference"
            )
            origin = "recovery source"
            if rec_fields.get("tradition") != row.tradition:
                note(
                    "SOURCE_CONFLICT_RESOLVED_BY_LAUNCH",
                    fid,
                    f"tradition: recovery source «{rec_fields.get('tradition')}» vs launch table «{row.tradition}»; "
                    "launch shortlist value used",
                )
        else:
            tradition, author, work, location = row.tradition, None, row.work, row.location
            launch_location, speaker = row.location, None
            prov["SOURCE"] = f"{LAUNCH_TABLE} (no textual-pass card, no recovered registry row; author unknown)"
            origin = None

        if origin:
            if tradition != row.tradition:
                note("SOURCE_CONFLICT", fid, f"tradition: {origin} «{tradition}» vs launch table «{row.tradition}»")
            if work != row.work:
                note("SOURCE_CORRECTION", fid, f"work: {origin} «{work}» vs launch table «{row.work}»")
            if location != row.location:
                note("SOURCE_CORRECTION", fid, f"location: {origin} «{location}» vs launch table «{row.location}»")
            if card and launch_location != row.location:
                note("SOURCE_CONFLICT", fid, f"launch_location «{launch_location}» differs from launch table «{row.location}»")
        if rec_fields and rec_fields.get("philosophical_move") != row.philosophical_move:
            note("SOURCE_CONFLICT", fid, "philosophical move differs between recovery source and launch table")

        if a:
            if a.tradition != row.tradition:
                note("SOURCE_CONFLICT", fid, f"tradition: operation audit «{a.tradition}» vs launch table «{row.tradition}»")
            if a.work_location != f"{row.work}, {row.location}":
                note("SOURCE_CONFLICT", fid, f"work/location: operation audit «{a.work_location}» vs launch table «{row.work}, {row.location}»")
            if a.philosophical_move != row.philosophical_move.replace("`", ""):
                note("SOURCE_CONFLICT", fid, "philosophical move differs between operation audit and launch table")

        # ---------------- TEXT / MEANING / RELATIONS / VERIFICATION
        fragment_text = storage_status = thought = context = commentary = None
        thought_placeholder = translation_placeholder = None
        pq = coordinates = tensions = None
        perspective = translation = source = copyright_status = None
        source_verified = interpretation_verified = None
        relations = None
        verification_flags = None

        if card:
            t = card.data.get("TEXT", {})
            frag = t.get("fragment")
            if isinstance(frag, dict):
                storage_status = _text(frag.get("storage_status"))
            else:
                fragment_text = _text(frag)
            thought = _text(t.get("thought"))
            if _is_placeholder(thought):
                thought_placeholder, thought = thought, None
            context, commentary = _text(t.get("context")), _text(t.get("commentary"))
            prov["TEXT"] = str(TEXTUAL_PASS)

            m = card.data.get("MEANING", {})
            pq = _str_list(m.get("philosophical_questions"))
            coordinates = _str_list(m.get("coordinates"))
            tensions = _str_list(m.get("tensions")) if m.get("tensions") is not None else None
            perspective = _text(m.get("perspective"))
            prov["MEANING"] = str(TEXTUAL_PASS)

            rel = (card.data.get("RELATIONS") or {}).get("relations")
            if rel == []:
                relations = Relations()
            elif isinstance(rel, dict):
                relations = Relations(**rel)
            else:
                note("RELATIONS_UNTYPED", fid, f"relations cannot be mapped to typed relations: {rel!r}")
            prov["RELATIONS"] = str(TEXTUAL_PASS)

            v = card.data.get("VERIFICATION", {})
            translation = _text(v.get("translation"))
            if _is_placeholder(translation):
                translation_placeholder, translation = translation, None
            source, copyright_status = _text(v.get("source")), _text(v.get("copyright_status"))
            source_verified, interpretation_verified = v.get("source_verified"), v.get("interpretation_verified")
            verification_flags = _str_list(v.get("verification_flags"))
            prov["VERIFICATION"] = str(TEXTUAL_PASS)
        elif rec_fields:
            perspective = rec_fields.get("perspective") or None
            coordinates = map_coordinates(_registry_tags(rec_fields.get("coordinates")))
            tensions = map_tensions(_registry_tags(rec_fields.get("tensions")))
            prov["MEANING"] = (
                f"RECONSTRUCTED from registry via {FIRST_29_RECOVERY}: perspective, coordinates, tensions "
                "(EN labels mapped 1:1 to TAXONOMY v1.1); philosophical_questions not recovered"
            )
            for layer in ("TEXT", "RELATIONS", "VERIFICATION"):
                prov[layer] = "RECOVERY_GAP: original approved YAML not physically recovered"
        elif rec:
            for layer in ("TEXT", "MEANING", "RELATIONS", "VERIFICATION"):
                prov[layer] = "RECOVERY_GAP: approved-batch membership confirmed, registry row not recovered"
            if reg:
                note(
                    "RECOVERY_CANDIDATE_NOT_APPLIED",
                    fid,
                    "CORPUS-FULL-1090 has a registry row for this ID (kept in technical.registry_reference); "
                    "not applied because the recovery source marks the original row as not recovered",
                )
        else:
            for layer in ("TEXT", "MEANING", "RELATIONS", "VERIFICATION"):
                prov[layer] = "ABSENT: no textual-pass card and no recovery record"

        if a:
            operation, structures = a.operation, list(a.question_structures)
            prov["OPERATION"] = str(OPERATION_AUDIT)
        else:
            operation = structures = None
            prov["OPERATION"] = "ABSENT: card not covered by OPERATION-AUDIT-launch-113"

        registry_reference = None
        if reg:
            registry_reference = RegistryReference(
                status=reg.status,
                decision=reg.decision,
                author_speaker=reg.author_speaker or None,
                work=reg.work or None,
                location=reg.location or None,
                philosophical_move=reg.philosophical_move or None,
                perspective=reg.perspective or None,
                coordinates_en=list(reg.coordinates_en),
                tensions_en=list(reg.tensions_en),
            )
            prov["registry_reference"] = f"{REGISTRY_1090} (traceability only; not canonical)"
            if reg.status != "main" or reg.decision not in {"KEEP", "PROMOTE", "KEEP_AS_CONTRAST"}:
                note(
                    "REGISTRY_STATUS_SUPERSEDED",
                    fid,
                    f"CORPUS-FULL-1090 marks this card status={reg.status}, decision={reg.decision}; "
                    "launch shortlist takes precedence",
                )
        else:
            note("REGISTRY_MISSING", fid, "launch ID not found in CORPUS-FULL-1090")

        unresolved = fid in UNRESOLVED_IDS
        fragments.append(
            Fragment(
                id=fid,
                tradition=tradition,
                author=author,
                work=work,
                location=location,
                fragment=fragment_text,
                thought=thought,
                context=context,
                commentary=commentary,
                philosophical_questions=pq,
                coordinates=coordinates,
                tensions=tensions,
                perspective=perspective,
                philosophical_operation=operation,
                question_structures=structures,
                relations=relations,
                translation=translation,
                source=source,
                copyright_status=copyright_status,
                source_verified=source_verified,
                interpretation_verified=interpretation_verified,
                technical=FragmentTechnical(
                    operational_status="unresolved" if unresolved else "verified",
                    retrieval_eligible=not unresolved,
                    recovery_status=rec.fields.get("recovery_status") if rec else None,
                    recovery_batch=rec.batch if rec else None,
                    old_yaml_status=rec.fields.get("old_yaml_status") if rec else None,
                    launch_philosophical_move=row.philosophical_move,
                    launch_location=launch_location,
                    speaker=speaker,
                    fragment_storage_status=storage_status,
                    verification_flags=verification_flags,
                    thought_placeholder=thought_placeholder,
                    translation_placeholder=translation_placeholder,
                    has_textual_pass_card=card is not None,
                    in_operation_audit_113=a is not None,
                    historical_unresolved_status_v2_0=fid in v20_unresolved,
                    historical_unresolved_textual_pass=fid in tp_unresolved,
                    field_provenance=prov,
                    registry_reference=registry_reference,
                ),
            )
        )

    allowlist = [f.id for f in fragments if f.technical.retrieval_eligible]
    manifest = {
        "corpus_version": CORPUS_VERSION,
        "schema_version": SCHEMA_VERSION,
        "expected_count": EXPECTED_COUNT,
        "operational_rule": (
            "launch shortlist 124; verified 113; unresolved 11 kept for audit and excluded from retrieval "
            "(CLAUDE-CODE-M1-CORRECTION-CLOSEOUT-PROMPT.md §1; supersedes TECHNICAL-DESIGN-retrieval-v0.2 §0)"
        ),
        "launch_shortlist_count": len(launch_ids),
        "retrieval_verified_count": len(allowlist),
        "expected_retrieval_verified_count": RETRIEVAL_VERIFIED_COUNT,
        "unresolved_count": len(UNRESOLVED_IDS & set(launch_ids)),
        "launch_ids": launch_ids,
        "unresolved_ids": sorted(UNRESOLVED_IDS),
        "retrieval_allowlist": allowlist,
        "routes": {
            "MEANING": "enabled",
            "STRUCTURE": "enabled",
            "SOURCE": SOURCE_ROUTE_STATUS,
        },
        "first_29_recovery": {
            "source": str(FIRST_29_RECOVERY),
            "note": "original approved YAML not physically recovered; recovered fields are reconstructed from registry",
            "records": {
                fid: {
                    "batch": r.batch,
                    "recovery_status": r.fields.get("recovery_status"),
                    "old_yaml_status": r.fields.get("old_yaml_status"),
                    "registry_row_recovered": r.registry_recovered,
                    "fields_reconstructed": (
                        ["work", "location", "perspective", "coordinates", "tensions"]
                        if r.registry_recovered
                        else []
                    ),
                }
                for fid, r in recovery.items()
            },
        },
        "historical": {
            "unresolved_status_v2_0": sorted(v20_unresolved),
            "unresolved_textual_pass": sorted(tp_unresolved),
            "operation_audit_113_ids": sorted(audit),
            "textual_pass_card_ids": sorted(cards),
            "textual_pass_source_corrections": src.textual_pass_status.get("source_corrections", []),
        },
        "source_documents": src.hashes,
        "import_notes": notes,
        "content_observations": _content_observations(fragments),
    }
    return fragments, manifest


def _content_observations(fragments: list[Fragment]) -> dict:
    """Descriptive statistics for the human reviewer. Nothing here changes data."""
    with_card = [f for f in fragments if f.technical.has_textual_pass_card]
    templated = {
        field: sorted(f.id for f in with_card if (getattr(f, field) or "").startswith(prefix))
        for field, prefix in TEMPLATE_PREFIXES.items()
    }
    coord_sets = Counter(tuple(f.coordinates or ()) for f in with_card)
    return {
        "cards_with_textual_pass": len(with_card),
        "templated_interpretation_fields": {k: len(v) for k, v in templated.items()},
        "templated_interpretation_ids": templated,
        "most_common_coordinate_sets": [
            {"coordinates": list(k), "count": v} for k, v in coord_sets.most_common(5)
        ],
        "cards_with_empty_tensions": sum(1 for f in with_card if f.tensions == []),
    }


def launch_move_question(move: str) -> str:
    """Move-specific question in the textual-pass convention (see the 95 textual-pass cards)."""
    return f"Какой философский ход совершает текст в ситуации: {move.strip().rstrip('.')}?"


def load_curation(root: Path) -> list[tuple[Path, dict]]:
    directory = root / CURATION_DIR
    if not directory.exists():
        return []
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(directory.glob("*.json"))]


def apply_curation(
    fragments: list[Fragment], curations: list[tuple[Path, dict]], src: SourceBundle, manifest: dict
) -> list[Fragment]:
    """Apply curation files as the last layer. Every change is recorded; nothing is silent."""
    by_id = {f.id: i for i, f in enumerate(fragments)}
    applied: dict[str, list[str]] = {}
    for path, cur in curations:
        cid = cur["curation_id"]
        for fid, spec in cur["fragments"].items():
            if fid not in by_id:
                raise ValueError(f"{path}: curation targets unknown Fragment {fid}")
            frag = fragments[by_id[fid]]
            update: dict = {}
            notes: dict[str, str] = dict(frag.technical.curation or {})
            prov = dict(frag.technical.field_provenance)

            registry_fields = spec.get("from_registry", [])
            if registry_fields:
                reg = src.registry.get(fid)
                if reg is None:
                    raise ValueError(f"{path}: {fid} has no CORPUS-FULL-1090 row")
                values = {
                    "perspective": reg.perspective or None,
                    "coordinates": map_coordinates(list(reg.coordinates_en)),
                    "tensions": map_tensions(list(reg.tensions_en)),
                }
                for field in registry_fields:
                    update[field] = values[field]
                    prov[field] = (
                        f"RECOVERED level 2 from {REGISTRY_1090} row ({cid}); not original approved YAML"
                        + ("; EN labels mapped 1:1 to TAXONOMY v1.1" if field != "perspective" else "")
                    )
                    notes[field] = f"{cid}: from CORPUS-FULL-1090. {spec.get('corroboration', '')}".strip()

            if spec.get("questions_from_launch_move"):
                move = frag.technical.launch_philosophical_move
                if not move:
                    raise ValueError(f"{path}: {fid} has no launch philosophical move")
                update["philosophical_questions"] = [launch_move_question(move)]
                prov["philosophical_questions"] = (
                    f"RECONSTRUCTED ({cid}) from the launch philosophical move using the textual-pass question convention"
                )
                notes["philosophical_questions"] = f"{cid}: single move-specific question; generic template questions not added"

            for field, value in spec.get("set", {}).items():
                old = getattr(frag, field)
                update[field] = value
                prov[field] = f"EDITORIAL RECONSTRUCTION ({cid}): {spec.get('basis', '')}".strip()
                notes[field] = f"{cid}: {spec['reason']}. Replaced value: {old!r}"

            technical = frag.technical.model_copy(update={"field_provenance": prov, "curation": notes})
            fragments[by_id[fid]] = Fragment.model_validate(
                {**frag.model_dump(), **update, "technical": technical.model_dump()}
            )
            applied.setdefault(cid, []).append(fid)
        manifest.setdefault("curation", []).append(
            {"curation_id": cid, "file": str(CURATION_DIR / path.name), "sha256": sha256(path),
             "fragments": applied.get(cid, [])}
        )
    manifest["content_observations"] = _content_observations(fragments)
    return fragments


def write_corpus(root: Path, out_dir: Path, force: bool = False) -> tuple[Path, Path]:
    src = load_sources(root)
    fragments, manifest = assemble(src)
    fragments = apply_curation(fragments, load_curation(root), src, manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = out_dir / "fragments.jsonl"
    manifest_path = out_dir / "launch-manifest.json"
    if corpus_path.exists() and not force:
        raise FileExistsError(
            f"{corpus_path} already exists. The canonical JSONL is the source of truth once "
            "curated; re-import only with --force after confirming no manual edits would be lost."
        )
    with corpus_path.open("w", encoding="utf-8") as fh:
        for f in fragments:
            fh.write(json.dumps(f.model_dump(mode="json"), ensure_ascii=False) + "\n")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return corpus_path, manifest_path
