# M2.3 retrieval diagnosis — summary

Diagnostic artifacts only. Full interpretation: `reports/validation/M2.3-RETRIEVAL-DIAGNOSIS-CLOSEOUT.md`.

| experiment | route | recovered share | unique cards | Gini | C0056 |
|---|---|---|---|---|---|
| baseline | Q0 | 0.5167 | 87 | 0.5151 | 10 |
| baseline | Q1 | 0.85 | 51 | 0.768 | 20 |
| baseline | STRUCTURE | 0.6333 | 63 | 0.6405 | 11 |
| doc A_perspective | Q1 | 0.3567 | 67 | 0.6582 | 14 |
| doc A_perspective | Q0 | 0.4567 | 82 | 0.5415 | 13 |
| doc B_questions | Q1 | 0.01 | 61 | 0.6859 | 0 |
| doc B_questions | Q0 | 0.0833 | 71 | 0.6154 | 0 |
| doc C_persp_questions | Q1 | 0.3533 | 71 | 0.6262 | 14 |
| doc C_persp_questions | Q0 | 0.47 | 85 | 0.531 | 11 |
| doc D_full | Q1 | 0.85 | 51 | 0.768 | 20 |
| doc D_full | Q0 | 0.5167 | 87 | 0.5151 | 10 |
| doc E_full_no_tensions | Q1 | 0.62 | 72 | 0.6397 | 16 |
| doc E_full_no_tensions | Q0 | 0.4867 | 89 | 0.5032 | 12 |
| doc F_full_detemplated | Q1 | 0.82 | 52 | 0.7575 | 19 |
| doc F_full_detemplated | Q0 | 0.5233 | 83 | 0.534 | 11 |
| doc G_coords_tensions | Q1 | 0.85 | 34 | 0.8199 | 17 |
| doc G_coords_tensions | Q0 | 0.29 | 77 | 0.6098 | 3 |
| query Q0_question_only | vs D_full | 0.5167 | 87 | 0.5151 | 10 |
| query QH_question_hypotheses | vs D_full | 0.6167 | 75 | 0.6274 | 16 |
| query QT_question_tensions | vs D_full | 0.98 | 33 | 0.8171 | 20 |
| query Q1_full | vs D_full | 0.85 | 51 | 0.768 | 20 |
| query QTonly_tensions_only | vs D_full | 1.0 | 26 | 0.83 | 20 |

Files: baseline.json, documents.json, field_ablations.json, query_ablations.json, query_lexical_overlap.json, embedding_space.json, c0056.json, structure.json, meta.json.
