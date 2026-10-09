"""Parsers for the Markdown source-of-truth documents of the launch corpus.

Parsers only extract; they never repair content. The single mechanical
normalisation applied is undoing pandoc typography artefacts in the
OPERATION-AUDIT table (``---`` → «—», ``--`` → «–», backticks around codes).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

LAUNCH_TABLE = Path("Архив/CORPUS-LAUNCH-124-v.md")
TEXTUAL_PASS = Path("Архив/CORPUS-LAUNCH-124-v1-final-textual-pass.md")
OPERATION_AUDIT = Path("OPERATION-AUDIT-launch-113-v0.1.md")
OPERATIONAL_STATUS = Path("CORPUS-LAUNCH-124-operational-status-v2.0.md")
REGISTRY_1090 = Path("CORPUS-FULL-1090-v1.md")
FIRST_29_RECOVERY = Path("CORPUS-LAUNCH-FIRST-29-recovery-source-v0.2.md")

SOURCE_FILES = (LAUNCH_TABLE, TEXTUAL_PASS, OPERATION_AUDIT, OPERATIONAL_STATUS, REGISTRY_1090, FIRST_29_RECOVERY)

_ID_RE = re.compile(r"C\d{4}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _pandoc_typography(text: str) -> str:
    return text.replace("---", "—").replace("--", "–").replace("`", "")


def _pipe_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if re.match(r"^\| C\d{4} \|", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


# --------------------------------------------------------------------------- launch table


@dataclass(frozen=True)
class LaunchRow:
    id: str
    tradition: str
    work: str
    location: str
    philosophical_move: str


def parse_launch_table(path: Path) -> list[LaunchRow]:
    """«Состав ядра после ревизии» in CORPUS-LAUNCH-124-v.md (ID | Tradition | Work | Location | Move)."""
    rows = []
    for cells in _pipe_rows(path.read_text(encoding="utf-8")):
        if len(cells) != 5:
            raise ValueError(f"{path}: unexpected column count {len(cells)} in row {cells[0]}")
        rows.append(LaunchRow(*cells))
    return rows


# --------------------------------------------------------------------------- textual pass


class _TextLoader(yaml.SafeLoader):
    """SafeLoader that resolves only null and booleans implicitly.

    Default YAML would turn locations such as ``12.1`` / ``2.10`` into floats
    (and ``2.10`` into ``2.1``), silently corrupting source addresses.
    """


_TextLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag in ("tag:yaml.org,2002:null", "tag:yaml.org,2002:bool")]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _load_yaml(text: str):
    return yaml.load(text, Loader=_TextLoader)  # noqa: S506 — SafeLoader subclass


@dataclass
class TextualPassCard:
    id: str
    data: dict
    yaml_repaired: bool = False


def _quote_list_items(block: str) -> str:
    """Quote plain YAML list items so ':' or '`' inside prose cannot break parsing.

    Only used as a fallback for blocks that fail strict parsing; the text of
    each item is preserved exactly.
    """
    out = []
    for line in block.splitlines():
        m = re.match(r"^(\s*- )(.*)$", line)
        if m and m.group(2) and not m.group(2).startswith(('"', "'", "[", "{")):
            line = m.group(1) + json.dumps(m.group(2), ensure_ascii=False)
        out.append(line)
    return "\n".join(out) + "\n"


def _has_non_text_list_items(node) -> bool:
    if isinstance(node, dict):
        return any(_has_non_text_list_items(v) for v in node.values())
    if isinstance(node, list):
        return any(not isinstance(item, str) for item in node)
    return False


def parse_textual_pass(path: Path) -> tuple[list[TextualPassCard], dict]:
    text = path.read_text(encoding="utf-8")
    cards = []
    for block in re.findall(r"```\s*yaml\n(.*?)```", text, re.S):
        repaired = False
        try:
            data = _load_yaml(block)
            # "- text: more text" is valid YAML but becomes a mapping, not prose.
            if _has_non_text_list_items(data):
                raise yaml.YAMLError("non-text list item")
        except yaml.YAMLError:
            data = _load_yaml(_quote_list_items(block))
            repaired = True
        cards.append(TextualPassCard(id=data["candidate_id"], data=data, yaml_repaired=repaired))

    status: dict = {"unresolved_ids": [], "source_corrections": []}
    tail = text.split("# FINAL TEXTUAL PASS STATUS", 1)
    if len(tail) == 2:
        status_text = tail[1]
        m = re.search(r"Unresolved IDs:(.*?)\n\n", status_text, re.S)
        if m:
            status["unresolved_ids"] = _ID_RE.findall(m.group(1))
        corr = status_text.split("## Preserved source corrections", 1)
        if len(corr) == 2:
            status["source_corrections"] = [
                _collapse(line.lstrip("- ")) for line in corr[1].splitlines() if line.strip().startswith("-")
            ]
    return cards, status


# --------------------------------------------------------------------------- operation audit


@dataclass(frozen=True)
class AuditRow:
    id: str
    tradition: str
    work_location: str
    operation: str
    question_structures: tuple[str, ...]
    philosophical_move: str


def parse_operation_audit(path: Path) -> list[AuditRow]:
    """Fixed-width pandoc table of OPERATION-AUDIT §7 («Полная разметка 113 verified»)."""
    lines = path.read_text(encoding="utf-8").split("\n")
    header = next(i for i, line in enumerate(lines) if re.match(r"^\s+ID\s+Tradition\s+Work", line))
    spans = [m.start() for m in re.finditer(r"-+", lines[header + 1])]

    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines[header + 2 :]:
        if re.match(r"^\s*-{20,}\s*$", line):
            break
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)

    rows = []
    for block in blocks:
        cols: list[list[str]] = [[] for _ in spans]
        for line in block:
            for k, start in enumerate(spans):
                end = spans[k + 1] if k + 1 < len(spans) else len(line)
                seg = line[start:end].strip()
                if seg:
                    cols[k].append(seg)
        joined = [_pandoc_typography(_collapse(" ".join(c))) for c in cols]
        structures = tuple(_collapse(s) for s in joined[4].split(";") if s.strip())
        rows.append(AuditRow(joined[0], joined[1], joined[2], joined[3], structures, joined[5]))
    return rows


# --------------------------------------------------------------------------- operational status v2.0


def parse_operational_status_unresolved(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    section = text.split("Unresolved:", 1)[1].split("Все unresolved", 1)[0]
    return _ID_RE.findall(section)


# --------------------------------------------------------------------------- registry 1090


@dataclass(frozen=True)
class RegistryRow:
    id: str
    status: str
    tradition: str
    author_speaker: str
    work: str
    location: str
    philosophical_move: str
    perspective: str
    coordinates_en: tuple[str, ...]
    tensions_en: tuple[str, ...]
    decision: str


def _split_tags(cell: str) -> tuple[str, ...]:
    return tuple(t.strip() for t in cell.split(",") if t.strip() and t.strip() != "—")


def parse_registry(path: Path) -> dict[str, RegistryRow]:
    out = {}
    for c in _pipe_rows(path.read_text(encoding="utf-8")):
        if len(c) != 11:
            raise ValueError(f"{path}: unexpected column count {len(c)} in row {c[0]}")
        out[c[0]] = RegistryRow(
            c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], _split_tags(c[8]), _split_tags(c[9]), c[10]
        )
    return out


# --------------------------------------------------------------------------- first-29 recovery source


@dataclass(frozen=True)
class RecoveryRecord:
    """One ``### CXXXX`` section of the first-29 recovery source.

    ``fields`` holds the section's ``- **key:** value`` pairs verbatim; records
    whose registry row was not recovered carry only recovery/old_yaml status.
    """

    id: str
    batch: str
    fields: dict[str, str]

    @property
    def registry_recovered(self) -> bool:
        return "tradition" in self.fields


def parse_first_29_recovery(path: Path) -> dict[str, RecoveryRecord]:
    out: dict[str, RecoveryRecord] = {}
    batch = ""
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            batch, current = line[3:].strip(), None
        elif m := re.match(r"^### (C\d{4})\s*$", line):
            current = m.group(1)
            if current in out:
                raise ValueError(f"{path}: duplicate recovery section {current}")
            out[current] = RecoveryRecord(current, batch, {})
        elif current and (m := re.match(r"^- \*\*(\w+):\*\* (.*)$", line)):
            out[current].fields[m.group(1)] = m.group(2).strip()
    return out


@dataclass
class SourceBundle:
    launch: list[LaunchRow]
    textual_pass: list[TextualPassCard]
    textual_pass_status: dict
    audit: list[AuditRow]
    unresolved_v2_0: list[str]
    registry: dict[str, RegistryRow]
    recovery: dict[str, RecoveryRecord] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)


def load_sources(root: Path) -> SourceBundle:
    missing = [str(p) for p in SOURCE_FILES if not (root / p).exists()]
    if missing:
        raise FileNotFoundError(f"missing source documents: {missing}")
    cards, tp_status = parse_textual_pass(root / TEXTUAL_PASS)
    return SourceBundle(
        launch=parse_launch_table(root / LAUNCH_TABLE),
        textual_pass=cards,
        textual_pass_status=tp_status,
        audit=parse_operation_audit(root / OPERATION_AUDIT),
        unresolved_v2_0=parse_operational_status_unresolved(root / OPERATIONAL_STATUS),
        registry=parse_registry(root / REGISTRY_1090),
        recovery=parse_first_29_recovery(root / FIRST_29_RECOVERY),
        hashes={str(p): sha256(root / p) for p in SOURCE_FILES},
    )
