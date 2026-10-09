# Corpus validation — machine summary

- status: **PASS** · index build allowed: **True**
- corpus: `data/corpus/fragments.jsonl` · version `launch-124/0.2.0-m1-closeout` · sha256 `266ed0513f084aa9…`
- launch shortlist: 124 / expected 124
- retrieval universe (verified): 113
- unresolved (excluded): 11 — C0215, C0230, C0258, C0377, C0396, C0398, C0703, C0704, C0705, C0706, C0707
- unresolved set matches rule: True · unresolved in retrieval universe: none
- blocking codes: —

## Routes

- SOURCE: `disabled_pending_full_fragment_text` (Fragment with full text: 0)
- MEANING: all inputs for 67 / 113; no inputs: C0937, C0949, C0957, C1105
- STRUCTURE: all inputs for 109 / 113

## Issues by code

| severity | code | count |
|---|---|---|
| warning | RECOVERY_GAP | 273 |
| warning | FRAGMENT_TEXT_ABSENT | 124 |
| warning | TEMPLATED_INTERPRETATION | 95 |
| warning | CONTENT_GAP | 49 |
| warning | CARD_VERIFICATION_FLAG_FALSE | 18 |
| warning | MEANING_ROUTE_INPUT_EMPTY | 4 |
| info | COPYRIGHT_PENDING | 95 |
| info | RELATIONS_UNAVAILABLE | 29 |
| info | THOUGHT_PLACEHOLDER_PRESERVED | 28 |
| info | EXCLUDED_UNRESOLVED_NO_OPERATION | 22 |
| info | TRANSLATION_PLACEHOLDER_PRESERVED | 21 |

## Field coverage

| field | present (124) | missing (124) | present (113) | missing (113) |
|---|---|---|---|---|
| fragment | 0 | 124 | 0 | 113 |
| tradition | 124 | 0 | 113 | 0 |
| work | 124 | 0 | 113 | 0 |
| location | 124 | 0 | 113 | 0 |
| philosophical_operation | 113 | 11 | 113 | 0 |
| question_structures | 113 | 11 | 113 | 0 |
| thought | 67 | 57 | 67 | 46 |
| context | 95 | 29 | 84 | 29 |
| commentary | 95 | 29 | 84 | 29 |
| philosophical_questions | 95 | 29 | 84 | 29 |
| coordinates | 120 | 4 | 109 | 4 |
| tensions | 120 | 4 | 109 | 4 |
| perspective | 120 | 4 | 109 | 4 |
| translation | 74 | 50 | 66 | 47 |
| source | 95 | 29 | 84 | 29 |
| copyright_status | 95 | 29 | 84 | 29 |
| source_verified | 95 | 29 | 84 | 29 |
| interpretation_verified | 95 | 29 | 84 | 29 |

## First-29 recovery

| id | batch | recovery_status | reconstructed | gaps |
|---|---|---|---|---|
| C0930 | Production batch 01 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0527 | Production batch 01 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0798 | Production batch 01 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0806 | Production batch 01 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C1108 | Тестовый батч | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C1105 | Production batch 01 | approved_batch_membership_confirmed_but_registry_row_not_yet_extracted | — | thought, context, commentary, philosophical_questions, coordinates, tensions, perspective, translation, source, copyright_status, source_verified, interpretation_verified |
| C0957 | Production batch 01 | approved_batch_membership_confirmed_but_registry_row_not_yet_extracted | — | thought, context, commentary, philosophical_questions, coordinates, tensions, perspective, translation, source, copyright_status, source_verified, interpretation_verified |
| C0579 | Production batch 01 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0013 | Production batch 01 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0170 | Production batch 02 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0144 | Production batch 02 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0937 | Production batch 02 | approved_batch_membership_confirmed_but_registry_row_not_yet_extracted | — | thought, context, commentary, philosophical_questions, coordinates, tensions, perspective, translation, source, copyright_status, source_verified, interpretation_verified |
| C0404 | Production batch 02 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0786 | Production batch 02 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0949 | Production batch 02 | approved_batch_membership_confirmed_but_registry_row_not_yet_extracted | — | thought, context, commentary, philosophical_questions, coordinates, tensions, perspective, translation, source, copyright_status, source_verified, interpretation_verified |
| C0001 | Тестовый батч | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0553 | Production batch 02 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0648 | Production batch 02 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0807 | Production batch 03 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0793 | Production batch 03 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0633 | Production batch 03 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0813 | Production batch 03 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0246 | Production batch 03 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0571 | Production batch 03 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0167 | Production batch 03 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0056 | Production batch 03 | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0871 | Тестовый батч | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0444 | Тестовый батч | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |
| C0778 | Тестовый батч | source_registry_recovered | work, location, perspective, coordinates, tensions | thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified |

## Import notes (source cross-checks)

- `RECOVERY_CANDIDATE_NOT_APPLIED` C1105 — CORPUS-FULL-1090 has a registry row for this ID (kept in technical.registry_reference); not applied because the recovery source marks the original row as not recovered
- `RECOVERY_CANDIDATE_NOT_APPLIED` C0957 — CORPUS-FULL-1090 has a registry row for this ID (kept in technical.registry_reference); not applied because the recovery source marks the original row as not recovered
- `SOURCE_CONFLICT_RESOLVED_BY_LAUNCH` C0579 — tradition: recovery source «библейская / иудейская традиция» vs launch table «иудаизм / библейская традиция»; launch shortlist value used
- `RECOVERY_CANDIDATE_NOT_APPLIED` C0937 — CORPUS-FULL-1090 has a registry row for this ID (kept in technical.registry_reference); not applied because the recovery source marks the original row as not recovered
- `RECOVERY_CANDIDATE_NOT_APPLIED` C0949 — CORPUS-FULL-1090 has a registry row for this ID (kept in technical.registry_reference); not applied because the recovery source marks the original row as not recovered
- `SOURCE_CONFLICT_RESOLVED_BY_LAUNCH` C0553 — tradition: recovery source «библейская / иудейская традиция» vs launch table «иудаизм / библейская традиция»; launch shortlist value used
- `SOURCE_CORRECTION` C0246 — work: recovery source «Sallatha Sutta» vs launch table «Дхаммачаккаппаваттана сутта — СН 56.11»
- `SOURCE_CORRECTION` C0246 — location: recovery source «SN 36.6» vs launch table «Первая и вторая стрелы»
- `SOURCE_CONFLICT_RESOLVED_BY_LAUNCH` C0571 — tradition: recovery source «библейская / иудейская традиция» vs launch table «иудаизм / библейская традиция»; launch shortlist value used
- `REGISTRY_STATUS_SUPERSEDED` C0969 — CORPUS-FULL-1090 marks this card status=reserve, decision=RESERVE; launch shortlist takes precedence
- `SOURCE_CORRECTION` C0215 — work: textual pass «Anattalakkhaṇa Sutta / Сутта о признаке не-самости» vs launch table «Дхаммачаккаппаваттана сутта — СН 56.11»
- `SOURCE_CORRECTION` C0215 — location: textual pass «SN 22.59» vs launch table «То же исследование пяти совокупностей»
- `SOURCE_CORRECTION` C0258 — work: textual pass «Soṇa Sutta» vs launch table «Дхаммачаккаппаваттана сутта — СН 56.11»
- `SOURCE_CORRECTION` C0258 — location: textual pass «AN 6.55» vs launch table «Неудача при большом старании не обязательно означает неверность пути»
- `SOURCE_CORRECTION` C0230 — work: textual pass «Kakacūpama Sutta / Притча о пиле» vs launch table «Дхаммачаккаппаваттана сутта — СН 56.11»
- `SOURCE_CORRECTION` C0230 — location: textual pass «MN 21, эпизод Ведехики и Кали» vs launch table «Репутация спокойного человека проверяется неприятностью»
- `YAML_REPAIRED` — 95 textual-pass blocks (prose list items quoted verbatim)
