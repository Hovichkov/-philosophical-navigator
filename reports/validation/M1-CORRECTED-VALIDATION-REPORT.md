# Milestone 1 — corrected validation report (closeout)

**Дата:** 2026-09-27 · **corpus_version:** `launch-124/0.2.0-m1-closeout` · **schema:** `fragment-schema/0.2.0` · **validator:** `corpus-validator/0.2.0`
**Основание:** `CLAUDE-CODE-M1-CORRECTION-CLOSEOUT-PROMPT.md`, `CORPUS-LAUNCH-FIRST-29-recovery-source-v0.2.md`.
Машинный отчёт: [`corpus-validation.json`](corpus-validation.json), сводка [`corpus-validation.md`](corpus-validation.md).
Исходный отчёт M1 и снимок данных до коррекции сохранены: [`M1-VALIDATION-REPORT.md`](M1-VALIDATION-REPORT.md), `reports/validation/m1-initial/`, `data/archive/m1-initial/`.

**Итог валидатора:** `PASS` · blocking errors: **0** · warnings: 563 · index build allowed: `true`
**Тесты:** 65 passed.

---

## 1. Подтверждение launch / retrieval universe

| показатель | ожидалось | факт |
|---|---|---|
| launch shortlist | 124 | **124** (все проходят typed-схему, ID уникальны) |
| retrieval verified (allowlist) | 113 | **113** |
| unresolved | 11 | **11** |
| набор unresolved совпадает с правилом | да | **да** |
| unresolved в retrieval universe | 0 | **0** |

Unresolved (хранятся в корпусе и manifest для аудита, `operational_status = unresolved`, `retrieval_eligible = false`):
C0215, C0230, C0258, C0377, C0396, C0398, C0703, C0704, C0705, C0706, C0707.

**Retrieval universe = 113.** Список хранится в `launch-manifest.json → retrieval_allowlist`. Валидатор сверяет правило, manifest и записи. Если unresolved попадёт в allowlist или расхождение затронет любую из трёх сторон, это blocking error.

Правило `124 verified / unresolved = 0` из TECHNICAL-DESIGN v0.2 §0 и старого START-PROMPT отменено. Базовый статус записан в `technical.operational_status_basis`.

## 2. Blocking errors

**Нет.**

Какие проверки остаются blocking:
- **Схема и идентичность:** schema/type, неизвестные поля, run-specific поля (D02), count ≠ 124, duplicate/missing ID, отсутствие tradition/work/location.
- **Значения:** неизвестные taxonomy-значения, операция вне словаря v0.1, malformed `question_structures`, broken/self relations, плейсхолдер в текстовом поле.
- **Retrieval:** отсутствие operation/question_structures у retrieval-eligible Fragment, любое нарушение правила 113/11.

## 3. Non-blocking warnings

| код | кол-во | смысл |
|---|---|---|
| `FRAGMENT_TEXT_ABSENT` | 124 | полного текста fragment нет ни у одной карточки; SOURCE route = `disabled_pending_full_fragment_text` |
| `RECOVERY_GAP` | 273 | невосстановленные поля первых 29 (см. §4) |
| `TEMPLATED_INTERPRETATION` | 95 | шаблонные context / commentary / perspective у 95 textual-pass карточек; массово не переделывалось |
| `CONTENT_GAP` | 49 | 28 Thought-плейсхолдеров (17 verified + 11 unresolved), 21 translation-плейсхолдер |
| `CARD_VERIFICATION_FLAG_FALSE` | 18 | verified-карточки с `source_verified: false` в самой карточке: C0004 C0008 C0020 C0023 C0025 C0027 C0028 (Семенцов), C0274 C0275 C0281 C0296 C0308 C0333 C0339 C0341 C0345 (Таронян), C0990 (Сыркин), C0577 |
| `MEANING_ROUTE_INPUT_EMPTY` | 4 | C0937, C0949, C0957, C1105: нет ни thought, ни philosophical_questions, ни perspective |

Info-уровень: `COPYRIGHT_PENDING` 95, `RELATIONS_UNAVAILABLE` 29, `EXCLUDED_UNRESOLVED_NO_OPERATION` 22 (11 карточек × 2 поля), сохранённые плейсхолдеры Thought 28 и translation 21. `author = null` не отчитывается как проблема.

**Готовность routes для 113:**
- **SOURCE:** отключён.
- **STRUCTURE:** все входы у 109 из 113. У 4 невосстановленных нет coordinates и tensions; operation и question_structures есть у всех 113.
- **MEANING:** все три входа у 67 из 113. Thought отсутствует у 46 (29 первых + 17 плейсхолдеров), philosophical_questions — у 29 первых, perspective — у 4.

## 4. Recovery gaps первых 29

Оригинальный утверждённый YAML ни одной из 29 карточек не найден. Реконструированные поля не выдаются за оригинал. Provenance хранится в `technical.recovery_status` / `recovery_batch` / `old_yaml_status` / `field_provenance` и в `launch-manifest.json → first_29_recovery`.

**25 карточек с восстановленной registry-строкой** (`recovery_status = source_registry_recovered`):
C0001 C1108 C0871 C0778 C0444 · C0930 C0527 C0798 C0806 C0579 C0013 · C0170 C0144 C0404 C0786 C0553 C0648 · C0807 C0793 C0633 C0813 C0246 C0571 C0167 C0056.
- **Реконструировано:** work, location, perspective, coordinates, tensions. Английские метки реестра переведены 1:1 в значения TAXONOMY v1.1, квалификатор `(potential)` сохранён.
- **Recovery gap:** thought, context, commentary, philosophical_questions, translation, source, copyright_status, source_verified, interpretation_verified, relations.

**4 карточки без восстановленной registry-строки** (`approved_batch_membership_confirmed_but_registry_row_not_yet_extracted`): **C1105, C0957, C0937, C0949**.
- Используются только launch-метаданные: tradition, work, location, move, а также operation и question_structures из аудита.
- Recovery gap: все semantic, TEXT и VERIFICATION поля. Для STRUCTURE route у них есть operation и question_structures, для MEANING route входов нет.

**Решения и находки при импорте:**
- **C0246 → Sallatha Sutta, SN 36.6.** Исправление сохранено; старая атрибуция СН 56.11 в canonical-полях отсутствует. Исправления C0215 (SN 22.59), C0230 (MN 21) и C0258 (AN 6.55) тоже сохранены, эти три карточки остаются unresolved.
- **Tradition у C0579, C0553, C0571.** Recovery-source даёт старое registry-значение «библейская / иудейская традиция». Launch shortlist, аудит и 95 карточек используют «иудаизм / библейская традиция». Взято launch-значение, расхождение записано в `import_notes` (`SOURCE_CONFLICT_RESOLVED_BY_LAUNCH`).
- **25 из 25 recovery-строк побуквенно совпадают с `CORPUS-FULL-1090`** (кроме принятой правки C0246). В 1090 есть строки и для 4 невосстановленных карточек (perspective, coordinates, tensions). Я их **не** применял, потому что recovery-source прямо называет исходную строку невосстановленной. Строки лежат в `technical.registry_reference` как кандидат для решения.
- **Два recovery-поля выглядят не как содержательные значения:**
  - `perspective` у C0527 — редакторская пометка («сильный кандидат для `ожидание ↔ действительность`. Сохранять притчу целиком.»);
  - move у C0871 — заголовок («философия и смерть»).

  Оба импортированы как есть.

## 5. Что вынесено владельцу (не блокирует M1)

1. Применять ли строки `CORPUS-FULL-1090` для C1105, C0957, C0937 и C0949. Без этого у 4 verified Fragment пустой MEANING route и нет coordinates/tensions.
2. Thought для 46 verified Fragment. Среди них C0339, который в Golden Set (сценарий A) отмечен как STRONG. Эти пробелы ослабят MEANING route в Milestone 2.
3. Флаги `source_verified: false` у 18 verified-карточек, особенно C0577: Thought у неё есть, но флаг false.
4. Правка perspective у C0527.

---

M1_CLOSEOUT_STATUS: PASS
