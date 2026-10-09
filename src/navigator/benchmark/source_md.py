"""Extract the M2.1 benchmark from its canonical Markdown specification.

The Markdown document (``M2.1-RETRIEVAL-BENCHMARK-v0.1.md``) is the product
source of truth. This parser only transcribes it: the single normalisation is
undoing pandoc artefacts (hard line breaks, ``---`` → «—», ``--`` → «–»,
trailing ``\\``). No wording is changed; ``tests/test_benchmark.py`` re-parses
the Markdown and checks the machine-readable file against it.
"""

from __future__ import annotations

import re
from pathlib import Path

BENCHMARK_MD = Path("M2.1-RETRIEVAL-BENCHMARK-v0.1.md")

_FIELD_RE = re.compile(r"\*\*(?P<label>[^*]+?):\*\*\s*(?P<value>.*?)(?=\s*\*\*[^*]+?:\*\*|\Z)", re.S)


def normalize(text: str) -> str:
    text = text.replace("\\\n", "\n").rstrip("\\")
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("---", "—").replace("--", "–")


def _split(value: str, sep: str) -> list[str]:
    return [v.strip() for v in value.split(sep) if v.strip()]


def _sections(text: str, level: str) -> list[tuple[str, str]]:
    """Return (heading, body) for headings of exactly ``level`` ('## ' etc.)."""
    parts = re.split(rf"^{re.escape(level)}(.+)$", text, flags=re.M)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


def _field_list(body: str) -> list[tuple[str, str]]:
    """Bold-labelled fields in document order (labels may repeat, e.g. CP2 «Expected»)."""
    return [(m.group("label").strip(), normalize(m.group("value"))) for m in _FIELD_RE.finditer(body)]


def _fields(body: str) -> dict[str, str]:
    return dict(_field_list(body))


def parse_expected_structure(value: str) -> dict:
    """Split «Expected structure» into node / coordinates / tensions / distinctions.

    Labels used in the document: optional «смысловой узел —», «coordinates —»,
    «tensions —», «различение —» or «важное различение —».
    """
    m = re.match(
        r"^(?:смысловой узел — )?(?P<node>.*?); coordinates — (?P<coords>.*?); tensions — (?P<tensions>.*?); "
        r"(?:важное )?различение — (?P<dist>.*?)\.?$",
        value,
    )
    if not m:
        raise ValueError(f"unrecognised expected structure: {value[:80]}…")
    return {
        "semantic_node": m.group("node").strip(),
        "coordinates": _split(m.group("coords"), ","),
        "tensions": _split(m.group("tensions"), ","),
        "distinctions": [m.group("dist").strip()],
    }


def parse_cases(text: str) -> list[dict]:
    block = text.split("# 3. Benchmark cases", 1)[1].split("# 4. Контрастные пары", 1)[0]
    cases = []
    for heading, body in _sections(block, "## "):
        m = re.match(r"^(B\d{2})\. (.+)$", heading)
        if not m:
            raise ValueError(f"unexpected case heading: {heading}")
        f = _fields(body)
        cases.append(
            {
                "id": m.group(1),
                "title": m.group(2).strip(),
                "circumstance": f["Circumstance"],
                "experiences": _split(f["Experiences"], ","),
                "center": f["Center"],
                "narrative": f["Narrative"],
                "expected_structure": parse_expected_structure(f["Expected structure"]),
                "failure_traps": _split(f["Failure traps"].rstrip("."), ";"),
            }
        )
    return cases


def parse_contrast_pairs(text: str) -> list[dict]:
    block = text.split("# 4. Контрастные пары", 1)[1].split("# 5. Evaluation rubric", 1)[0]
    pairs = []
    for heading, body in _sections(block, "## "):
        m = re.match(r"^(CP\d)\. (.+)$", heading)
        if not m:
            raise ValueError(f"unexpected contrast-pair heading: {heading}")
        pairs.append({"id": m.group(1), "title": m.group(2).strip(), "fields": _field_list(body)})
    return pairs


def section_text(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def parse_rubric(text: str) -> list[tuple[str, list[tuple[int, str]]]]:
    """«**Relevance:** 0 — …; 1 — …; 2 — ….» → [(label, [(0, …), (1, …), (2, …)])]."""
    block = section_text(text, "# 5. Evaluation rubric", "# 6. Set-level evaluation")
    out = []
    for label, value in _field_list(block):
        body = value.split("Единый итоговый балл", 1)[0].strip()
        levels = re.split(r"(?:^|;\s)([012]) — ", body)
        pairs = [(int(levels[i]), levels[i + 1].strip().rstrip(".").strip()) for i in range(1, len(levels), 2)]
        out.append((label, pairs))
    return out


def parse_list_section(text: str, start: str, end: str) -> list[str]:
    block = text.split(start, 1)[1].split(end, 1)[0]
    items = re.split(r"^\s*(?:-|\d+\.)\s+", block, flags=re.M)[1:]
    return [normalize(i) for i in items]


def load(root: Path) -> str:
    return (root / BENCHMARK_MD).read_text(encoding="utf-8")
