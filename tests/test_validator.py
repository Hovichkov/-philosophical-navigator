"""Validator failure modes on synthetic records (test-only data, not corpus content)."""

from __future__ import annotations

import copy
import json

import pytest

from navigator.corpus.validator import validate_corpus_file, validate_records


def make_record(fid: str, **overrides) -> dict:
    record = {
        "id": fid,
        "tradition": "test-tradition",
        "author": None,
        "work": "test-work",
        "location": "1:1",
        "fragment": "synthetic fragment",
        "thought": "synthetic thought",
        "context": "synthetic context",
        "commentary": "synthetic commentary",
        "philosophical_questions": ["synthetic question?"],
        "coordinates": ["желание"],
        "tensions": [],
        "perspective": "synthetic perspective",
        "philosophical_operation": "DISTINGUISH",
        "question_structures": ["desire↔meaning"],
        "relations": {"contrasts_with": [], "resonates_with": [], "complicates": []},
        "translation": "synthetic translation",
        "source": "synthetic source",
        "copyright_status": "public_domain",
        "source_verified": True,
        "interpretation_verified": True,
        "technical": {
            "operational_status": "verified",
            "retrieval_eligible": True,
            "has_textual_pass_card": True,
            "in_operation_audit_113": True,
            "historical_unresolved_status_v2_0": False,
            "historical_unresolved_textual_pass": False,
        },
    }
    record.update(overrides)
    return record


def corpus(n: int = 3) -> list[dict]:
    return [make_record(f"C{9000 + i:04d}") for i in range(n)]


def run(records: list[dict], expected_count: int = 3, expected_unresolved=frozenset(), **kw):
    return validate_records(
        list(enumerate(records, start=1)),
        expected_count=expected_count,
        expected_unresolved=frozenset(expected_unresolved),
        **kw,
    )


def unresolved(record: dict) -> dict:
    record["technical"]["operational_status"] = "unresolved"
    record["technical"]["retrieval_eligible"] = False
    return record


def test_valid_synthetic_corpus_passes():
    result = run(corpus())
    assert result.ok, result.errors
    assert result.codes("error") == set()


def test_wrong_corpus_count():
    result = run(corpus(2), expected_count=3)
    assert "COUNT_MISMATCH" in result.codes("error")


def test_duplicate_id():
    records = corpus()
    records[2]["id"] = records[0]["id"]
    result = run(records)
    assert "DUPLICATE_ID" in result.codes("error")


def test_bad_id_format_is_schema_error():
    records = corpus()
    records[0]["id"] = "X-1"
    assert "SCHEMA_TYPE" in run(records).codes("error")


def test_missing_expected_and_unexpected_ids():
    records = corpus()
    expected = [r["id"] for r in records[:2]] + ["C9999"]
    codes = run(records, expected_ids=expected).codes("error")
    assert {"MISSING_EXPECTED_ID", "UNEXPECTED_ID"} <= codes


@pytest.mark.parametrize("field", ["tradition", "work", "location"])
def test_missing_source_identity_is_blocking(field):
    records = corpus()
    records[1][field] = None
    result = run(records)
    assert [(i.code, i.fragment_id, i.field) for i in result.errors] == [
        ("MISSING_SOURCE_IDENTITY", records[1]["id"], field)
    ]


@pytest.mark.parametrize("field", ["thought", "context", "perspective", "translation", "source_verified"])
def test_missing_content_field_is_non_blocking_gap(field):
    records = corpus()
    records[1][field] = None
    result = run(records)
    assert result.ok
    gaps = [(i.fragment_id, i.field) for i in result.warnings if i.code == "CONTENT_GAP"]
    assert gaps == [(records[1]["id"], field)]


def test_recovery_gap_is_reported_separately():
    records = corpus()
    records[0]["thought"] = None
    records[0]["technical"]["recovery_status"] = "source_registry_recovered"
    result = run(records)
    assert result.ok
    assert "RECOVERY_GAP" in result.codes("warning") and "CONTENT_GAP" not in result.codes("warning")


def test_absent_key_is_reported_as_gap():
    records = corpus()
    del records[0]["commentary"]
    result = run(records)
    assert result.ok and "CONTENT_GAP" in result.codes("warning")


def test_missing_fragment_text_is_warning_not_fail():
    records = corpus()
    for r in records:
        r["fragment"] = None
    result = run(records)
    assert result.ok
    assert [i.code for i in result.warnings].count("FRAGMENT_TEXT_ABSENT") == 3


def test_meaning_route_without_inputs_blocks_eligible_fragment():  # M1.5
    records = corpus()
    for field in ("thought", "philosophical_questions", "perspective"):
        records[0][field] = None
    result = run(records)
    assert [(i.code, i.fragment_id) for i in result.errors] == [("MEANING_NOT_READY", records[0]["id"])]


def test_eligible_fragment_without_coordinates_is_not_structure_ready():  # M1.5
    records = corpus()
    records[0]["coordinates"] = None
    assert "STRUCTURE_NOT_READY" in run(records).codes("error")


def test_empty_tensions_are_allowed_but_empty_coordinates_are_a_gap():
    records = corpus()
    records[0]["tensions"] = []
    records[1]["coordinates"] = []
    result = run(records)
    gaps = [(i.fragment_id, i.field) for i in result.warnings if i.code == "CONTENT_GAP"]
    assert gaps == [(records[1]["id"], "coordinates")]
    assert [i.fragment_id for i in result.errors if i.code == "STRUCTURE_NOT_READY"] == [records[1]["id"]]


def test_wrong_type_is_schema_error():
    records = corpus()
    records[0]["source_verified"] = "yes"
    assert "SCHEMA_TYPE" in run(records).codes("error")


def test_broken_relation():
    records = corpus()
    records[0]["relations"]["contrasts_with"] = ["C1234"]
    assert "BROKEN_RELATION" in run(records).codes("error")


def test_self_relation():
    records = corpus()
    records[0]["relations"]["resonates_with"] = [records[0]["id"]]
    assert "SELF_RELATION" in run(records).codes("error")


def test_valid_relation_passes():
    records = corpus()
    records[0]["relations"]["complicates"] = [records[1]["id"]]
    assert run(records).ok


def test_invalid_coordinate():
    records = corpus()
    records[0]["coordinates"] = ["desire"]  # English label is not a TAXONOMY v1.1 value
    assert "INVALID_TAXONOMY_VALUE" in run(records).codes("error")


def test_invalid_tension_and_potential_qualifier():
    records = corpus()
    records[0]["tensions"] = ["желание ↔ деньги"]
    records[1]["tensions"] = ["желание ↔ долг (potential)"]
    issues = [i for i in run(records).errors if i.code == "INVALID_TAXONOMY_VALUE"]
    assert [i.fragment_id for i in issues] == [records[0]["id"]]


def test_invalid_operation():
    records = corpus()
    records[0]["philosophical_operation"] = "REFRAME"  # not in the v0.1 working dictionary
    assert "INVALID_OPERATION" in run(records).codes("error")


@pytest.mark.parametrize(
    "value",
    [
        "desire↔meaning",  # a string, not a list
        [""],  # empty item
        ["desire meaning"],  # no ↔
        ["a↔b↔c"],  # more than two poles
        ["desire↔meaning", "desire↔meaning"],  # duplicate
        [1],  # not a string
    ],
)
def test_malformed_question_structures(value):
    records = corpus()
    records[0]["question_structures"] = value
    assert "MALFORMED_QUESTION_STRUCTURES" in run(records).codes("error")


def test_empty_question_structures_blocks_eligible_fragment():
    records = corpus()
    records[0]["question_structures"] = []
    issues = [(i.code, i.field) for i in run(records).errors]
    assert ("RETRIEVAL_METADATA_MISSING", "question_structures") in issues


def test_unknown_question_structure_is_only_a_warning():
    records = corpus()
    records[0]["question_structures"] = ["hope↔despair"]
    result = run(records)
    assert result.ok
    assert "UNKNOWN_QUESTION_STRUCTURE" in result.codes("warning")


def test_open_marker_is_accepted():
    records = corpus()
    records[0]["question_structures"] = ["open / context-dependent"]
    assert run(records).ok


@pytest.mark.parametrize("field", ["required_assumption", "source_fidelity", "similarity", "coverage_contribution"])
def test_forbidden_runtime_field(field):
    records = corpus()
    records[0][field] = "anything"
    result = run(records)
    assert "FORBIDDEN_RUNTIME_FIELD" in result.codes("error")
    assert "UNKNOWN_FIELD" not in result.codes("error")


def test_unknown_field_rejected():
    records = corpus()
    records[0]["mood"] = "calm"
    assert "UNKNOWN_FIELD" in run(records).codes("error")


def test_placeholder_text_is_rejected():
    records = corpus()
    records[0]["thought"] = "[FINAL TEXTUAL PASS: вставить короткий дословный Thought]"
    assert "PLACEHOLDER_TEXT" in run(records).codes("error")


def test_eligible_fragment_without_operation_is_blocking():
    records = corpus()
    records[0]["philosophical_operation"] = None
    assert "RETRIEVAL_METADATA_MISSING" in run(records).codes("error")


def test_excluded_unresolved_without_operation_is_not_blocking():
    records = corpus(4)
    unresolved(records[3])
    records[3]["philosophical_operation"] = None
    records[3]["question_structures"] = None
    result = run(records, expected_count=4, expected_unresolved={records[3]["id"]})
    assert result.ok, result.errors
    assert "EXCLUDED_UNRESOLVED_NO_OPERATION" in result.codes("info")


def test_invalid_operational_status_value_is_schema_error():
    records = corpus()
    records[0]["technical"]["operational_status"] = "unverified"
    assert "SCHEMA_TYPE" in run(records).codes("error")


def test_card_flag_false_is_warning_not_error():
    records = corpus()
    records[0]["source_verified"] = False
    result = run(records)
    assert result.ok
    assert "CARD_VERIFICATION_FLAG_FALSE" in result.codes("warning")


# ---------------------------------------------------------------- 113 / 11 rule


def test_allowlist_excludes_unresolved():
    records = corpus(4)
    unresolved(records[1])
    result = run(records, expected_count=4, expected_unresolved={records[1]["id"]})
    assert result.ok, result.errors
    assert result.allowlist == [records[0]["id"], records[2]["id"], records[3]["id"]]


def test_unresolved_marked_verified_is_blocking():
    records = corpus(4)
    result = run(records, expected_count=4, expected_unresolved={records[1]["id"]})
    assert {"OPERATIONAL_STATUS_MISMATCH", "UNRESOLVED_IN_ALLOWLIST", "VERIFIED_COUNT_MISMATCH"} <= result.codes("error")


def test_unresolved_marked_retrieval_eligible_is_blocking():
    records = corpus(4)
    unresolved(records[1])["technical"]["retrieval_eligible"] = True
    result = run(records, expected_count=4, expected_unresolved={records[1]["id"]})
    assert {"RETRIEVAL_ELIGIBILITY_MISMATCH", "UNRESOLVED_IN_ALLOWLIST"} <= result.codes("error")


def test_verified_fragment_marked_unresolved_is_blocking():
    records = corpus(4)
    unresolved(records[1])
    unresolved(records[2])
    result = run(records, expected_count=4, expected_unresolved={records[1]["id"]})
    assert {"OPERATIONAL_STATUS_MISMATCH", "VERIFIED_COUNT_MISMATCH"} <= result.codes("error")


def test_unresolved_must_stay_in_corpus():
    records = corpus(3)
    result = run(records, expected_count=3, expected_unresolved={"C9990"})
    assert "UNRESOLVED_ID_MISSING" in result.codes("error")


def test_manifest_allowlist_leak_and_mismatch_are_blocking():
    records = corpus(4)
    unresolved(records[1])
    ids = [r["id"] for r in records]
    result = run(records, expected_count=4, expected_unresolved={ids[1]}, manifest_allowlist=ids)
    assert {"UNRESOLVED_IN_ALLOWLIST", "ALLOWLIST_MISMATCH"} <= result.codes("error")
    good = run(records, expected_count=4, expected_unresolved={ids[1]}, manifest_allowlist=[ids[0], ids[2], ids[3]])
    assert good.ok


def test_manifest_unresolved_set_mismatch_is_blocking():
    records = corpus(4)
    unresolved(records[1])
    result = run(
        records, expected_count=4, expected_unresolved={records[1]["id"]}, manifest_unresolved=[records[2]["id"]]
    )
    assert "UNRESOLVED_SET_MISMATCH" in result.codes("error")


def test_default_rule_is_124_113_11():
    from navigator.models.vocabularies import LAUNCH_SHORTLIST_COUNT, RETRIEVAL_VERIFIED_COUNT, UNRESOLVED_IDS

    assert (LAUNCH_SHORTLIST_COUNT, RETRIEVAL_VERIFIED_COUNT, len(UNRESOLVED_IDS)) == (124, 113, 11)
    assert UNRESOLVED_IDS == {
        "C0377", "C0396", "C0398", "C0215", "C0230", "C0258", "C0703", "C0704", "C0705", "C0706", "C0707"
    }


def test_file_level_json_parse_error(tmp_path):
    path = tmp_path / "fragments.jsonl"
    lines = [json.dumps(r, ensure_ascii=False) for r in corpus()]
    lines[1] = "{not json"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = validate_corpus_file(path, expected_count=3, expected_unresolved=frozenset())
    assert {"JSON_PARSE", "COUNT_MISMATCH"} <= result.codes("error")


def test_manifest_supplies_expected_ids_and_count(tmp_path):
    records = corpus()
    path = tmp_path / "fragments.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"expected_count": 3, "launch_ids": [r["id"] for r in records]}))
    assert validate_corpus_file(path, manifest, expected_unresolved=frozenset()).ok
    manifest.write_text(json.dumps({"expected_count": 4, "launch_ids": [r["id"] for r in records]}))
    assert "COUNT_MISMATCH" in validate_corpus_file(path, manifest, expected_unresolved=frozenset()).codes("error")


def test_make_record_is_not_shared_state():
    a, b = make_record("C9000"), make_record("C9000")
    a["relations"]["contrasts_with"].append("C9001")
    assert b["relations"]["contrasts_with"] == [] and copy.deepcopy(b) == b
