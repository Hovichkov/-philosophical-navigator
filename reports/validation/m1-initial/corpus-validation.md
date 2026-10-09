# Corpus validation — machine summary

- status: **FAIL** · index build allowed: **False**
- corpus: `data/corpus/fragments.jsonl` · version `launch-124/0.1.0-m1` · sha256 `4e935c4f6294b6af…`
- records: 124 / expected 124 · schema-valid 124 · unique IDs 124 · operationally verified 124
- blocking codes: MISSING_REQUIRED_FIELD

## Issues by code

| severity | code | count |
|---|---|---|
| error | MISSING_REQUIRED_FIELD | 543 |
| warning | COPYRIGHT_PENDING | 95 |
| warning | RELATIONS_UNAVAILABLE | 29 |
| warning | CARD_VERIFICATION_FLAG_FALSE | 29 |
| info | THOUGHT_PLACEHOLDER_PRESERVED | 28 |
| info | TRANSLATION_PLACEHOLDER_PRESERVED | 21 |

## Field coverage

| field | layer | present | missing |
|---|---|---|---|
| tradition | SOURCE | 124 | 0 |
| work | SOURCE | 124 | 0 |
| location | SOURCE | 124 | 0 |
| fragment | TEXT | 0 | 124 |
| thought | TEXT | 67 | 57 |
| context | TEXT | 95 | 29 |
| commentary | TEXT | 95 | 29 |
| philosophical_questions | MEANING | 95 | 29 |
| coordinates | MEANING | 95 | 29 |
| tensions | MEANING | 95 | 29 |
| perspective | MEANING | 95 | 29 |
| philosophical_operation | OPERATION | 113 | 11 |
| question_structures | OPERATION | 113 | 11 |
| translation | VERIFICATION | 74 | 50 |
| source | VERIFICATION | 95 | 29 |
| copyright_status | VERIFICATION | 95 | 29 |
| source_verified | VERIFICATION | 95 | 29 |
| interpretation_verified | VERIFICATION | 95 | 29 |
| author | SOURCE (optional) | 0 | 124 |
| relations | RELATIONS (optional) | 95 | 29 |

## Operation layer

- with philosophical_operation: 113 / 124
- with question_structures: 113 / 124
- missing operation: C0215, C0230, C0258, C0377, C0396, C0398, C0703, C0704, C0705, C0706, C0707

| historical unresolved ID | operation | question_structures | operational status |
|---|---|---|---|
| C0215 | NO | NO | verified |
| C0230 | NO | NO | verified |
| C0258 | NO | NO | verified |
| C0377 | NO | NO | verified |
| C0396 | NO | NO | verified |
| C0398 | NO | NO | verified |
| C0703 | NO | NO | verified |
| C0704 | NO | NO | verified |
| C0705 | NO | NO | verified |
| C0706 | NO | NO | verified |
| C0707 | NO | NO | verified |

## Fragments with required-field gaps

| id | missing fields |
|---|---|
| C0001 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0004 | TEXT: fragment, thought |
| C0005 | TEXT: fragment |
| C0008 | TEXT: fragment, thought |
| C0013 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0014 | TEXT: fragment |
| C0020 | TEXT: fragment, thought |
| C0023 | TEXT: fragment, thought |
| C0025 | TEXT: fragment, thought |
| C0027 | TEXT: fragment, thought |
| C0028 | TEXT: fragment, thought |
| C0043 | TEXT: fragment |
| C0044 | TEXT: fragment |
| C0049 | TEXT: fragment |
| C0050 | TEXT: fragment |
| C0055 | TEXT: fragment |
| C0056 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0058 | TEXT: fragment |
| C0060 | TEXT: fragment |
| C0068 | TEXT: fragment |
| C0081 | TEXT: fragment |
| C0121 | TEXT: fragment |
| C0123 | TEXT: fragment |
| C0125 | TEXT: fragment |
| C0130 | TEXT: fragment |
| C0144 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0165 | TEXT: fragment |
| C0167 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0168 | TEXT: fragment |
| C0170 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0215 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures; VERIFICATION: translation |
| C0230 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures; VERIFICATION: translation |
| C0246 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0258 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures; VERIFICATION: translation |
| C0274 | TEXT: fragment, thought |
| C0275 | TEXT: fragment, thought |
| C0281 | TEXT: fragment, thought |
| C0296 | TEXT: fragment, thought |
| C0308 | TEXT: fragment, thought |
| C0333 | TEXT: fragment, thought |
| C0339 | TEXT: fragment, thought |
| C0341 | TEXT: fragment, thought |
| C0345 | TEXT: fragment, thought |
| C0377 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures |
| C0396 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures |
| C0398 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures |
| C0404 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0436 | TEXT: fragment |
| C0437 | TEXT: fragment |
| C0438 | TEXT: fragment |
| C0439 | TEXT: fragment |
| C0440 | TEXT: fragment |
| C0441 | TEXT: fragment |
| C0442 | TEXT: fragment |
| C0443 | TEXT: fragment |
| C0444 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0445 | TEXT: fragment |
| C0446 | TEXT: fragment |
| C0447 | TEXT: fragment |
| C0511 | TEXT: fragment; VERIFICATION: translation |
| C0512 | TEXT: fragment; VERIFICATION: translation |
| C0513 | TEXT: fragment; VERIFICATION: translation |
| C0514 | TEXT: fragment; VERIFICATION: translation |
| C0515 | TEXT: fragment; VERIFICATION: translation |
| C0518 | TEXT: fragment; VERIFICATION: translation |
| C0527 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0533 | TEXT: fragment; VERIFICATION: translation |
| C0535 | TEXT: fragment; VERIFICATION: translation |
| C0539 | TEXT: fragment; VERIFICATION: translation |
| C0542 | TEXT: fragment; VERIFICATION: translation |
| C0545 | TEXT: fragment; VERIFICATION: translation |
| C0553 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0555 | TEXT: fragment; VERIFICATION: translation |
| C0571 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0577 | TEXT: fragment; VERIFICATION: translation |
| C0579 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0583 | TEXT: fragment; VERIFICATION: translation |
| C0618 | TEXT: fragment |
| C0619 | TEXT: fragment |
| C0620 | TEXT: fragment |
| C0621 | TEXT: fragment |
| C0622 | TEXT: fragment |
| C0623 | TEXT: fragment |
| C0624 | TEXT: fragment |
| C0633 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0648 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0653 | TEXT: fragment |
| C0659 | TEXT: fragment |
| C0670 | TEXT: fragment |
| C0703 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures |
| C0704 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures |
| C0705 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures |
| C0706 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures |
| C0707 | TEXT: fragment, thought; OPERATION: philosophical_operation, question_structures |
| C0708 | TEXT: fragment |
| C0709 | TEXT: fragment |
| C0710 | TEXT: fragment |
| C0711 | TEXT: fragment |
| C0712 | TEXT: fragment |
| C0713 | TEXT: fragment |
| C0778 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0779 | TEXT: fragment |
| C0780 | TEXT: fragment |
| C0781 | TEXT: fragment |
| C0786 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0793 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0797 | TEXT: fragment |
| C0798 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0806 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0807 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0813 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0821 | TEXT: fragment |
| C0871 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0930 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0937 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0942 | TEXT: fragment; VERIFICATION: translation |
| C0948 | TEXT: fragment; VERIFICATION: translation |
| C0949 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0952 | TEXT: fragment; VERIFICATION: translation |
| C0957 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C0969 | TEXT: fragment; VERIFICATION: translation |
| C0990 | TEXT: fragment, thought |
| C1105 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |
| C1108 | TEXT: fragment, thought, context, commentary; MEANING: philosophical_questions, coordinates, tensions, perspective; VERIFICATION: translation, source, copyright_status, source_verified, interpretation_verified |

## Import notes (source cross-checks)

- `YAML_REPAIRED` C0969 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0948 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0345 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0583 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0004 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0068 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0215 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0577 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0258 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0005 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0014 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0027 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0555 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0043 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0055 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0165 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0533 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0230 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0341 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0653 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0008 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0020 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0023 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0025 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0028 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0044 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0049 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0050 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0058 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0121 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0123 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0125 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0130 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0296 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0333 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0339 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0396 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0447 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0514 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0518 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0535 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0539 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0542 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0545 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0619 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0623 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0659 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0670 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0168 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0281 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0308 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0942 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0952 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0990 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0274 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0275 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0436 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0437 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0438 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0439 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0440 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0441 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0442 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0443 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0445 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0446 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0511 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0512 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0513 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0515 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0618 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0620 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0621 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0622 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0624 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0703 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0704 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0705 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0706 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0707 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0708 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0709 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0710 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0711 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0712 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0713 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0779 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0780 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0781 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0797 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0398 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0060 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0377 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0081 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `YAML_REPAIRED` C0821 — YAML block failed strict parsing or turned prose list items into mappings (unquoted ':' or '`'); list items were quoted verbatim and re-parsed
- `REGISTRY_STATUS` C0969 — CORPUS-FULL-1090 marks this launch card as status=reserve, decision=RESERVE
- `SOURCE_CORRECTION` C0215 — work: textual pass «Anattalakkhaṇa Sutta / Сутта о признаке не-самости» vs launch table «Дхаммачаккаппаваттана сутта — СН 56.11»
- `SOURCE_CORRECTION` C0215 — location: textual pass «SN 22.59» vs launch table «То же исследование пяти совокупностей»
- `SOURCE_CORRECTION` C0258 — work: textual pass «Soṇa Sutta» vs launch table «Дхаммачаккаппаваттана сутта — СН 56.11»
- `SOURCE_CORRECTION` C0258 — location: textual pass «AN 6.55» vs launch table «Неудача при большом старании не обязательно означает неверность пути»
- `SOURCE_CORRECTION` C0230 — work: textual pass «Kakacūpama Sutta / Притча о пиле» vs launch table «Дхаммачаккаппаваттана сутта — СН 56.11»
- `SOURCE_CORRECTION` C0230 — location: textual pass «MN 21, эпизод Ведехики и Кали» vs launch table «Репутация спокойного человека проверяется неприятностью»

## Content observations (not validated, for human review)

- templated interpretation fields among textual-pass cards: {'context': 95, 'commentary': 95, 'perspective': 95} of 95
- coordinates ['действие', 'отношение к себе']: 43 cards
- coordinates ['действие']: 6 cards
- coordinates ['желание']: 5 cards
- coordinates ['отношение к себе']: 5 cards
- coordinates ['отношение к другому']: 5 cards
- cards with empty tensions: 86
