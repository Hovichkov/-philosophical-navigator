"""Final corpus 2026-10-07: importer / validator of ``FINAL-CORPUS-ACTIVE-v1.csv``.

Source of truth: ``corpus/final-2026-10-07/`` (the package as delivered, byte for byte), governed by
``CORPUS-CONTRACT-FOR-CLAUDE-CODE.md``. The runtime corpus is ONLY ``FINAL-CORPUS-ACTIVE-v1.csv`` (967 rows);
the evidence registry, reconciliation and exclusions are audit data and are only read to cross-check.

The importer fails (``FinalCorpusError`` listing every violation) on anything the contract forbids:
- a blank or duplicate ``card_id`` (and an id outside the ``C`` + 4 digits form — ids are never regenerated);
- a blank ``philosophical_move`` or ``quote``;
- ``verification_status`` ``REJECTED_MOVE_SOURCE_MISMATCH`` or ``AMBIGUOUS``;
- an active row that the package itself lists as excluded / unresolved (EXCLUSIONS-AND-UNRESOLVED-v1.csv);
- the frozen scope broken: Plato outside Apology C0837–C0847 + Euthyphro C0851–C0852 + Protagoras C0857–C0858 +
  Meno C0859–C0862 (Crito C0848–C0850 excluded), the historical gaps C0293 / C0351 or the rejected C0364 / C0365
  present;
- a header different from the contract columns.
Values are kept exactly as delivered (UTF-8, no trimming, no substitution, nothing filled in).
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass, fields
from pathlib import Path

FINAL_DIR = Path("corpus/final-2026-10-07")
PACKAGE_DIR = Path(__file__).resolve().parents[3] / FINAL_DIR  # absolute: independent of the working directory
ACTIVE_CSV = "FINAL-CORPUS-ACTIVE-v1.csv"
EXCLUSIONS_CSV = "EXCLUSIONS-AND-UNRESOLVED-v1.csv"
MANIFEST = "MANIFEST-SHA256.txt"
FINAL_CORPUS_VERSION = "final-corpus-2026-10-07/active-v1"

FORBIDDEN_STATUSES = frozenset({"REJECTED_MOVE_SOURCE_MISMATCH", "AMBIGUOUS"})
PLATO_RANGE = ("C0837", "C0929")
PLATO_SCOPE = frozenset(
    [f"C{n:04d}" for n in range(837, 848)]      # Apology 11
    + ["C0851", "C0852"]                         # Euthyphro 2
    + ["C0857", "C0858"]                         # Protagoras 2
    + [f"C{n:04d}" for n in range(859, 863)]     # Meno 4
)
CRITO = frozenset({"C0848", "C0849", "C0850"})
HISTORICAL_GAPS = frozenset({"C0293", "C0351"})
REJECTED_IDS = frozenset({"C0364", "C0365"})


@dataclass(frozen=True)
class FinalCard:
    card_id: str
    status_in_corpus: str
    author: str
    work: str
    location: str
    philosophical_move: str
    quote: str
    translator: str
    edition_source: str
    verification_status: str
    verification_note: str
    evidence_layer_source: str


COLUMNS = tuple(f.name for f in fields(FinalCard))


class FinalCorpusError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__(f"{len(problems)} contract violation(s):\n- " + "\n- ".join(problems))
        self.problems = problems


def _read(path: Path) -> tuple[list[str], list[dict]]:
    # utf-8-sig: the package files carry a BOM; values are not altered in any other way
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def validate_rows(header: list[str], rows: list[dict], excluded_ids: set[str] | None = None) -> list[str]:
    problems: list[str] = []
    if tuple(header) != COLUMNS:
        problems.append(f"header {header} differs from the contract columns {list(COLUMNS)}")
        return problems
    seen: dict[str, int] = {}
    for n, r in enumerate(rows, start=2):  # line 1 is the header
        cid = r.get("card_id") or ""
        if not cid.strip():
            problems.append(f"line {n}: blank card_id")
            continue
        if not re.fullmatch(r"C\d{4}", cid):
            problems.append(f"line {n}: card_id «{cid}» is not of the form C0000")
        if cid in seen:
            problems.append(f"line {n}: duplicate card_id {cid} (first at line {seen[cid]})")
        seen.setdefault(cid, n)
        if not (r.get("philosophical_move") or "").strip():
            problems.append(f"{cid}: blank philosophical_move")
        if not (r.get("quote") or "").strip():
            problems.append(f"{cid}: blank quote")
        if (r.get("verification_status") or "") in FORBIDDEN_STATUSES:
            problems.append(f"{cid}: forbidden verification_status {r['verification_status']}")
    ids = set(seen)
    if excluded_ids is not None and ids & excluded_ids:
        problems.append(f"rows listed in {EXCLUSIONS_CSV} are active: {sorted(ids & excluded_ids)}")
    plato = {i for i in ids if PLATO_RANGE[0] <= i <= PLATO_RANGE[1]}
    if plato - PLATO_SCOPE:
        problems.append(f"Plato outside the frozen scope (Apology+Euthyphro+Protagoras+Meno): {sorted(plato - PLATO_SCOPE)}")
    for name, group in (("Crito (excluded)", CRITO), ("historical gap", HISTORICAL_GAPS), ("rejected", REJECTED_IDS)):
        if ids & group:
            problems.append(f"{name} ids must not be active: {sorted(ids & group)}")
    return problems


def load_final_active(directory: Path = PACKAGE_DIR) -> list[FinalCard]:
    """The 967 runtime cards, validated against the contract. Raises FinalCorpusError on any violation."""
    header, rows = _read(directory / ACTIVE_CSV)
    excl_path = directory / EXCLUSIONS_CSV
    excluded = {r["card_id"] for r in _read(excl_path)[1]} if excl_path.exists() else None
    problems = validate_rows(header, rows, excluded)
    if problems:
        raise FinalCorpusError(problems)
    return [FinalCard(**{c: r[c] for c in COLUMNS}) for r in rows]


def verify_manifest(directory: Path = PACKAGE_DIR) -> list[str]:
    """Mismatches against MANIFEST-SHA256.txt («sha256  size  name» lines); empty list = the package is intact."""
    bad = []
    for line in (directory / MANIFEST).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 3 or line.startswith("#"):
            continue
        digest, size, name = parts
        p = directory / name
        if not p.exists():
            bad.append(f"{name}: missing")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != digest or str(p.stat().st_size) != size:
            bad.append(f"{name}: sha256/size mismatch")
    return bad


# ------------------------------------------------------------------ snapshot for the current pipeline


def final_snapshot_fragments(cards: list[FinalCard]):
    """The final cards as ``Fragment`` objects for the existing retrieval / card code.

    Only what the CSV gives: id, author, work, location (verbatim); quote → ``fragment`` (TEXT, verbatim);
    translator → ``translation``; edition_source → ``source``; philosophical_move → ``launch_philosophical_move``
    and, by the project's existing deterministic convention, the MEANING question built from it. The CSV has no
    tradition, perspective, coordinates, tensions or operation — they stay EMPTY (nothing is filled in), so the
    STRUCTURE route finds nothing on this snapshot until a decision is taken on those layers.
    """
    from navigator.corpus.importer import launch_move_question
    from navigator.models.fragment import Fragment, FragmentTechnical

    out = []
    for c in cards:
        out.append(Fragment(
            id=c.card_id, author=c.author or None, work=c.work or None, location=c.location or None,
            fragment=c.quote, translation=c.translator or None, source=c.edition_source or None,
            philosophical_questions=[launch_move_question(c.philosophical_move)],
            source_verified=True,
            technical=FragmentTechnical(
                corpus_status="final_2026_10_07", operational_status="final_active", retrieval_eligible=True,
                operational_status_basis=f"{FINAL_DIR / ACTIVE_CSV} (CORPUS-CONTRACT-FOR-CLAUDE-CODE.md)",
                launch_philosophical_move=c.philosophical_move, launch_location=c.location,
                verification_flags=[c.verification_status],
                has_textual_pass_card=False, in_operation_audit_113=False,
                historical_unresolved_status_v2_0=False, historical_unresolved_textual_pass=False,
                field_provenance={"ALL": str(FINAL_DIR / ACTIVE_CSV), "status_in_corpus": c.status_in_corpus,
                                  "verification_status": c.verification_status,
                                  **({"verification_note": c.verification_note} if c.verification_note else {}),
                                  "evidence_layer_source": c.evidence_layer_source},
            ),
        ))
    return out
