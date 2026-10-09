# CLAUDE CODE — START PROMPT
## Philosophical Navigator / Retrieval MVP — Milestone 1

Ты работаешь над проектом «Инструмент самоанализа / Философский навигатор».

Твоя задача сейчас — **только Milestone 1: canonical corpus + schemas + validation**.

Не реализуй retrieval, embeddings, LLM pipeline, API или UI. После validation report остановись.

---

## 1. Сначала прочитай источники истины

Найди в репозитории и прочитай актуальные версии:

1. `PROJECT-philosophical-navigator-v0.9.md`
2. `TAXONOMY-philosophical-navigator-v1.1*.md`
3. `UX-SELF-ANALYSIS-v0.2.md`
4. `CORPUS-philosophical-navigator-v0.1*.md`
5. `CORPUS-LAUNCH-124-v1-final-textual-pass*.md`
6. `CORPUS-LAUNCH-124-operational-status-v2.0.md`
7. `OPERATION-AUDIT-launch-113-v0.1.md`
8. `RETRIEVAL-philosophical-navigator-v0.2.md`
9. `RETRIEVAL-VALIDATION-6-SCENARIOS-v0.1.md`
10. `TECHNICAL-DESIGN-retrieval-v0.2.md`

Если filename слегка отличается, найди актуальный файл по содержанию/версии.

`TECHNICAL-DESIGN-retrieval-v0.2.md` является источником истины по уже принятым техническим решениям retrieval. Не перепроектируй их самостоятельно.

---

## 2. Важное позднее решение

Для текущей реализации считать:

> **Launch corpus = 124 verified Fragment. Unresolved = 0. Все 124 участвуют в retrieval.**

Это решение имеет приоритет над историческими статусами `113 verified / 11 unresolved`, `96/28` и т.п.

Однако `verified` и наличие retrieval metadata — разные вещи.

`OPERATION-AUDIT-launch-113-v0.1.md` исторически покрывал 113 карточек. Поэтому нужно отдельно проверить, есть ли у всех 124:

- `philosophical_operation`;
- `question_structures`.

Если у 11 карточек эти поля отсутствуют, **не придумывай их** и не объявляй карточки unverified. Отчитай это как structural/retrieval-metadata gap.

---

## 3. Что нужно сделать

### A. Осмотреть реальные данные

Установи:

- где физически находятся 124 launch Fragment;
- какова их фактическая текущая schema;
- какие поля есть у всех/части карточек;
- как соотносятся launch corpus и operation audit;
- есть ли duplicate IDs / broken relations / missing fields.

Не изменяй философское содержание, чтобы оно соответствовало ожидаемой schema.

### B. Создать canonical corpus

Целевая форма:

`data/corpus/fragments.jsonl`

Одна строка = один Fragment.

Ожидается 124 записи.

Canonical Fragment должен сохранять существующее утверждённое содержание и metadata, включая по наличию в источниках:

SOURCE:
- id
- tradition
- author
- work
- location

TEXT:
- fragment
- thought
- context
- commentary

MEANING:
- philosophical_questions
- coordinates
- tensions
- perspective

OPERATION-AWARE:
- philosophical_operation
- question_structures

RELATIONS:
- contrasts_with
- resonates_with
- complicates

VERIFICATION/SOURCE:
- translation
- source
- copyright_status
- source_verified
- interpretation_verified
- существующие необходимые source/technical metadata.

Не создавай run-specific поля (`required_assumption`, STRONG/POSSIBLE/REJECT, relevance, coverage, similarity и т.д.) внутри Fragment.

### C. Реализовать typed schemas

Используй Python + Pydantic.

Схемы должны отражать реальные source data и архитектуру Technical Design.

Если реальные данные требуют осторожной нормализации, сохрани семантику исходных полей. Не заполняй неизвестное выдуманными значениями.

### D. Реализовать corpus validator

Validator должен проверить минимум:

- expected count = 124;
- unique stable IDs;
- required fields/types;
- duplicate IDs;
- relations ссылаются на существующие Fragment IDs;
- закрытые taxonomy values соответствуют source-of-truth taxonomy;
- `philosophical_operation` соответствует утверждённому рабочему словарю;
- presence/shape `question_structures`;
- structural gaps;
- source/verification fields согласно фактической canonical schema.

Рабочий словарь operation v0.1 бери из Technical Design / Operation Audit, не расширяй самостоятельно.

### E. Tests

Добавь unit tests для основных validator failures:

- duplicate ID;
- missing required field;
- broken relation;
- invalid taxonomy/operation value;
- malformed question_structures;
- wrong corpus count.

### F. Validation outputs

Создай:

1. machine-readable validation output (JSON);
2. human-readable короткий report (Markdown).

Report должен явно ответить:

- удалось ли получить ровно 124 Fragment;
- какие schema gaps найдены;
- есть ли operation/question_structures у всех 124;
- какие именно Fragment имеют gaps;
- есть ли broken relations;
- есть ли конфликт между ожидаемой и фактической schema;
- что требует решения человека до Milestone 2.

---

## 4. Hard constraints

Не делай на этом milestone:

- embeddings;
- embedding provider;
- vector index;
- semantic search;
- Query Representation LLM;
- candidate evaluation;
- required_assumption runtime logic;
- source-fidelity evaluator;
- STRONG/POSSIBLE/REJECT runtime;
- diversity selection;
- coverage;
- targeted recall;
- Personal Link;
- HTTP API;
- UI;
- vector DB;
- LangChain/LlamaIndex/agent framework.

Не меняй архитектурные решения D01–D51 без отдельного указания.

Не придумывай отсутствующие философские данные.

Не заменяй отсутствующий утверждённый источник другим переводом или реконструкцией.

Не исправляй молча содержательные противоречия между документами. Зафиксируй их в report.

---

## 5. Acceptance criteria

Milestone завершён только когда:

- canonical JSONL создан либо точно доказано, какой source gap этому мешает;
- ожидаемые 124 Fragment учтены;
- Pydantic schemas реализованы;
- validator реализован;
- tests проходят;
- validation JSON создан;
- validation Markdown report создан;
- gaps у исторических 11 карточек явно проверены;
- retrieval/embeddings/API/UI не реализованы.

---

## 6. Как закончить работу

В конце:

1. перечисли созданные/изменённые файлы;
2. дай итог validator;
3. отдельно перечисли blockers/gaps;
4. отдельно перечисли вопросы, требующие решения владельца проекта;
5. **остановись**.

Не переходи к Milestone 2 без отдельной команды.
