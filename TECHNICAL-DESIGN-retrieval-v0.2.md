# TECHNICAL DESIGN — retrieval MVP v0.1

**Проект:** «Инструмент самоанализа / Философский навигатор»  
**Статус:** промежуточный источник истины по уже принятым техническим решениям retrieval  
**Назначение:** зафиксировать архитектуру до этапов Personal Link, logging, eval и финального MVP stack. Документ предназначен для последующей передачи в Claude Code вместе с остальными источниками истины.

---

## 0. Приоритет и изменение operational status

Для дальнейшего технического проектирования принято более позднее решение:

> **Launch corpus = 124 verified Fragment. Unresolved = 0. Все 124 Fragment допускаются в retrieval.**

Это решение имеет приоритет над историческими данными `113 verified / 11 unresolved` в `CORPUS-LAUNCH-124-operational-status-v2.0.md`, `RETRIEVAL-philosophical-navigator-v0.2.md`, `OPERATION-AUDIT-launch-113-v0.1.md` и других более ранних документах.

Содержательная архитектура этих документов сохраняется. Меняется только operational assumption о candidate universe.

---

## 1. Источники истины

Технический дизайн не заменяет содержательные документы проекта.

При интерпретации требований использовать:

1. `PROJECT-philosophical-navigator-v0.9.md` — общая концепция, принципы и состояние проекта.
2. `TAXONOMY-philosophical-navigator-v1.1.md` — источник истины по внутренней таксономии.
3. `UX-SELF-ANALYSIS-v0.2.md` — источник истины по пользовательскому пути первого сценария и границе начала retrieval.
4. `CORPUS-philosophical-navigator-v0.1.md` — источник истины по архитектуре корпуса и структуре Fragment.
5. launch corpus — содержательные 124 Fragment.
6. `OPERATION-AUDIT-launch-113-v0.1.md` — источник рабочего слоя `philosophical_operation / question_structures`; его разметка относится к исторически аудированным 113 карточкам, а техническая модель распространяется на launch corpus 124.
7. `RETRIEVAL-philosophical-navigator-v0.2.md` — главный источник истины по содержательной механике retrieval после подтверждения вопроса.
8. Этот документ — источник истины по принятым техническим решениям реализации retrieval MVP, если они не противоречат более позднему явному решению проекта.

---

## 2. Неподвижные продуктовые инварианты

Главный принцип:

> Для системы не существует объективно «плохих» и «хороших» жизненных обстоятельств. Предметом исследования становится отношение человека к обстоятельству и представление, посредством которого он это обстоятельство понимает.

Retrieval:

- начинается только после подтверждения пользователем исследуемого вопроса;
- не диагностирует пользователя;
- не сообщает скрытые мотивы как установленные факты;
- не принимает решение за пользователя;
- не ищет философское подтверждение заранее придуманному совету;
- не меняет confirmed question за пользователя;
- ищет несколько первоисточников, каждый из которых способен по-разному преобразовать постановку confirmed question;
- допускает два сильных Fragment как полноценный результат;
- никогда не добавляет слабый третий Fragment ради количества;
- генерирует `PERSONAL LINK + ONE QUESTION` только после окончательного выбора Fragment.

---

# Часть I. Corpus storage

## 3. Canonical corpus

### Решение D01

124 verified Fragment хранятся в репозитории проекта как canonical corpus:

`data/corpus/fragments.jsonl`

Одна строка JSONL = один Fragment.

Canonical JSONL является источником истины для содержимого корпуса. База данных или vector index не являются источником истины и должны полностью воспроизводиться из canonical corpus.

Причины:

- corpus мал;
- Git даёт прозрачную историю изменений;
- данные легко читать и валидировать;
- не требуется преждевременная инфраструктура;
- позднее corpus можно импортировать в любую БД без изменения содержательной модели.

---

## 4. Постоянная схема Fragment

Сохраняется утверждённая структура корпуса.

### SOURCE

- `id` — стабильный технический ID Fragment;
- `tradition`;
- `author` — если применимо;
- `work`;
- `location`.

### TEXT

- `fragment`;
- `thought`;
- `context`;
- `commentary`.

`thought` остаётся текстом самого первоисточника, а не пересказом системы.

### MEANING

- `philosophical_questions`;
- `coordinates`;
- `tensions`;
- `perspective`.

### OPERATION-AWARE RETRIEVAL LAYER

- `philosophical_operation`;
- `question_structures`.

`philosophical_operation` — рабочий retrieval signal, описывающий действие текста над вопросом.  
`question_structures` — retrieval hints, а не hard classifiers.

Рабочий словарь `philosophical_operation v0.1`:

- `REVALUE_GOOD`
- `EXAMINE_DESIRE`
- `DISTINGUISH`
- `CHALLENGE_ASSUMPTION`
- `LIMIT_CONTROL`
- `LIMIT_OBLIGATION`
- `PRESERVE_AGENCY`
- `RELATIONAL_ACCOUNTABILITY`
- `DECOUPLE_RESPONSE`
- `DECOUPLE_ACTION_OUTCOME`
- `HOLD_VALUE_CONFLICT`
- `SHIFT_ATTENTION`
- `ACKNOWLEDGE_FINITUDE`
- `PERSPECTIVE_LIMIT`
- `TRANSFORM_PRACTICE`
- `CHALLENGE_COMPARISON`

Словарь не является окончательной философской онтологией.

### RELATIONS

Сохраняются существующие связи:

- `contrasts_with`;
- `resonates_with`;
- `complicates`.

Полный граф между Fragment для MVP не требуется. Relations не являются основным semantic recall signal на текущем этапе.

### VERIFICATION / SOURCE METADATA

Сохраняются:

- `translation`;
- `source`;
- `copyright_status`;
- `source_verified`;
- `interpretation_verified`;

а также существующие технические/source metadata launch corpus, если они присутствуют в исходных карточках.

Operational assumption MVP: все 124 Fragment считаются verified.

---

## 5. Что НЕ является постоянным свойством Fragment

### Решение D02

В canonical Fragment не хранятся:

- `required_assumption`;
- `STRONG / POSSIBLE / REJECT`;
- situational relevance;
- narrative applicability;
- source fidelity конкретного применения;
- coverage contribution;
- relation to already selected perspective;
- embedding similarity конкретного run;
- selection/rejection reason.

Эти значения существуют только относительно конкретного retrieval run и пары `candidate × narrative`.

Особенно:

> `required_assumption` всегда вычисляется динамически для пары `Fragment × конкретный narrative`.

---

# Часть II. Semantic representations Fragment

## 6. Общий принцип

### Решение D03

Не создавать один embedding всей карточки.

Для каждого Fragment строятся три независимых производных semantic representations.

Они не редактируются вручную и всегда воспроизводимы из canonical corpus.

---

## 7. MEANING representation

Назначение:

> О чём философски говорит этот Fragment?

Состав:

- `thought`;
- `philosophical_questions`;
- `perspective`.

Это основной semantic representation философского смысла Fragment.

---

## 8. STRUCTURE representation

Назначение:

> С какой структурой человеческого вопроса этот Fragment способен работать и какую операцию он совершает?

Состав:

- `coordinates`;
- `tensions`;
- `question_structures`;
- `philosophical_operation`.

Поля сохраняются одновременно:

1. как дискретные metadata;
2. как текстовое semantic representation для embedding recall.

Совпадение coordinate, tension, operation или question_structure никогда не является hard filter.

---

## 9. SOURCE representation

Назначение:

> Что буквально находится в самом источнике?

Состав:

- `fragment`;
- минимально необходимый `context`.

SOURCE является дополнительным recall route и страховкой от недостаточной ручной разметки MEANING/STRUCTURE.

---

## 10. Commentary

На текущем этапе `commentary`:

- хранится в canonical Fragment;
- обязательно доступен downstream LLM для source-fidelity и candidate evaluation;
- не получает отдельный semantic index;
- не включается автоматически в MEANING/SOURCE representation.

Проверка пользы Commentary для recall — `EVAL PARAMETER`.

---

## 11. Что не embedding'уется как самостоятельный retrieval signal

Не создаются отдельные embeddings для:

- tradition;
- author;
- work;
- location;
- translation;
- source bibliography;
- copyright metadata;
- verification metadata;
- technical ID.

`tradition` не используется как классификатор пользователя или hard retrieval filter.

---

## 12. Производные retrieval artifacts

Предлагаемая физическая граница:

```text
data/
  corpus/
    fragments.jsonl

  retrieval/
    embeddings/
    index-metadata/
```

Embeddings и indexes:

- не редактируются вручную;
- могут быть удалены и полностью пересобраны;
- должны иметь версии corpus, representation schema и embedding model.

Для 124 Fragment три representations дают 372 semantic vectors.

---

# Часть III. Retrieval input и Query Representation

## 13. Вход retrieval

Retrieval начинается только после confirmed question.

Он получает:

### Пользовательские данные

- `confirmed_question` — точная подтверждённая формулировка;
- `narrative` — полный свободный рассказ.

### Состояние предыдущего UX

- `circumstance`;
- `experience`;
- `inquiry`;
- уже построенные `coordinates`;
- уже построенные `tensions`;
- другие утверждённые структурированные данные предыдущего этапа, если они существуют.

Приоритет:

1. `confirmed_question` определяет, что исследуется;
2. `narrative` определяет применимость философского хода;
3. `coordinates / tensions` расширяют и структурируют поиск, но не заменяют confirmed question.

После подтверждения вопроса retrieval не создаёт новую рабочую гипотезу о пользователе.

---

## 14. Frozen Query Representation

### Решение D04

До broad recall один LLM-pass создаёт внутренний `Query Representation`.

После создания объект замораживается на весь retrieval run.

Разные кандидаты не получают разные версии интерпретации пользователя.

Query Representation включает:

### `confirmed_question`

Точная копия подтверждённого вопроса без перефразирования.

### `narrative_facts[]`

Только факты, явно поддержанные narrative.

Запрещено превращать предположение модели в факт.

### `representations[]`

Явно выраженные пользователем представления, ожидания или предпосылки.

Не являются диагностикой скрытых убеждений.

### `primary_coordinates[]`

Из утверждённой taxonomy.

### `secondary_coordinates[]`

Из утверждённой taxonomy.

### `tensions[]`

Из утверждённой taxonomy.

Дополнительное tension допустимо только если оно явно поддерживается narrative; оно остаётся secondary retrieval signal и не меняет confirmed question.

### `question_aspects[]`

Техническая декомпозиция существенных сторон confirmed question, необходимых для будущего coverage check.

Это не новая классификация личности пользователя.

### `narrative_constraints[]`

Факты/ограничения narrative, которые особенно важны для проверки применимости кандидата и `required_assumption`.

### `retrieval_summary`

Короткое нейтральное представление ситуации исключительно для semantic recall.

Не показывается пользователю и не заменяет confirmed question.

---

## 15. Facts vs inference

### Решение D05

Query Representation не является психологическим анализом.

Допустимо извлечь:

- сообщённый факт;
- явно выраженный страх;
- явно выраженное ожидание;
- явно сформулированное представление.

Недопустимо без поддержки narrative утверждать:

- скрытый мотив;
- чувство, которого пользователь не называл и которое не следует прямо из текста;
- обязанность;
- вину;
- зависимость;
- намерение другого человека;
- психологический диагноз.

Если применение Fragment требует такого утверждения, оно должно появиться позже как `required_assumption`, а не как факт Query Representation.

---

## 16. Query Representation и semantic routes

### MEANING query

Основные сигналы:

- confirmed question;
- явно поддержанные representations.

### STRUCTURE query

Основные сигналы:

- coordinates;
- tensions;
- question_aspects.

Query Representation не предсказывает, какая `philosophical_operation` «нужна» пользователю.

### SOURCE query

Основные сигналы:

- confirmed question;
- компактный `retrieval_summary`.

Полный narrative не используется как основной embedding query, чтобы бытовые детали не захватывали semantic recall.

Полный narrative обязательно используется позже при candidate evaluation.

---

# Часть IV. Broad semantic recall

## 17. Три независимых recall route

### Решение D06

Broad recall выполняется независимо по:

1. MEANING;
2. STRUCTURE;
3. SOURCE.

Результаты объединяются в broad candidate pool.

Semantic similarity используется только для recall.

Высокий similarity score:

- не доказывает situational relevance;
- не доказывает source fidelity;
- не даёт STRONG;
- не определяет final selection.

Задача recall — с высокой вероятностью не потерять потенциально хороший Fragment.

---

## 18. Union и provenance

### Решение D07

Если Fragment найден несколькими routes, он существует в pool один раз по `Fragment ID`.

При этом сохраняется retrieval provenance:

- `found_by`;
- similarity каждого route, где candidate был найден;
- ranking position каждого route, если используется.

Не создаётся искусственный единый `global semantic score` с придуманными весами.

---

## 19. Broad pool limiting

После union/deduplication pool ограничивается до размера, пригодного для LLM candidate evaluation.

Не фиксируются заранее:

- число кандидатов от каждого route;
- общий размер broad pool;
- similarity threshold;
- fusion/ranking algorithm;
- веса routes.

Все эти значения — `EVAL PARAMETERS`.

Критерий выбора:

> найти минимальную конфигурацию broad recall, которая практически перестаёт терять релевантные сильные Fragment на eval-наборе.

---

## 20. Metadata filtering

До LLM candidate evaluation не вводятся hard filters по:

- tradition;
- author;
- coordinates;
- tensions;
- philosophical_operation;
- question_structures.

Необычный Fragment не должен быть потерян только из-за несовпадения ручной разметки.

---

# Часть V. Candidate evaluation

## 21. Граница embeddings

После формирования broad candidate pool embeddings заканчивают содержательную работу.

LLM candidate evaluator получает:

### User side

- confirmed question;
- full narrative;
- Query Representation;
- circumstance / experience / inquiry, если нужны для контекста.

### Fragment side

- thought;
- fragment;
- commentary;
- context;
- philosophical_questions;
- coordinates;
- tensions;
- perspective;
- philosophical_operation;
- question_structures.

### Решение D08

LLM candidate evaluator не видит:

- embedding similarity;
- semantic ranking position.

Эти данные остаются только в trace/eval, чтобы не создавать anchoring.

---

## 22. Independent qualification

### Решение D09

Candidate qualification и final selection — разные стадии.

Сначала каждый candidate оценивается независимо:

> Может ли этот Fragment честно и продуктивно работать с данным confirmed question и narrative?

LLM не получает задачу сразу выбрать «лучшие три».

Только после независимой qualification сравниваются прошедшие кандидаты.

---

## 23. Candidate evaluation gates

Каждый candidate проходит четыре содержательных проверки:

1. Question relevance.
2. Situational / narrative applicability.
3. Required assumption.
4. Source fidelity.

Философская продуктивность учитывается внутри relevance/applicability: Fragment должен не просто тематически совпадать, а создавать различение, менять способ постановки вопроса или открывать самостоятельный философский ход.

Для MVP проверки могут выполняться одним LLM-call со structured output, но поля остаются логически независимыми.

---

## 24. Question relevance

Вопрос:

> Работает ли Fragment именно с confirmed question, а не с соседней бытовой или философской темой?

Рабочие состояния:

- `YES`;
- `PARTIAL`;
- `NO`.

`NO` → `REJECT`.

---

## 25. Situational applicability

Вопрос:

> Можно ли применить философский ход Fragment к ситуации, которую пользователь действительно описал?

Полный narrative обязателен на этой стадии.

Semantic similarity не заменяет situational applicability.

---

## 26. Required assumption

### Решение D10

`required_assumption` вычисляется для каждой пары `candidate × narrative`.

Рабочая техническая модель:

- `NONE`;
- `UNSUPPORTED` + текст предпосылки;
- `CONTRADICTED` + текст предпосылки.

`NONE` — narrative уже содержит всё необходимое для применения.

`UNSUPPORTED` — Fragment становится применимым, если принять предпосылку, которую narrative не устанавливает.

`CONTRADICTED` — необходимая предпосылка противоречит известным данным narrative.

### Решение D11

Если `required_assumption != NONE`, candidate не может получить `STRONG`.

### Решение D12

- `UNSUPPORTED` может вести к `POSSIBLE`;
- `CONTRADICTED` ведёт к `REJECT`.

Это различает отсутствие данных и прямое противоречие рассказу пользователя.

---

## 27. Source-fidelity gate

### Решение D13

Source fidelity проверяет не повторную академическую верификацию карточки, а fidelity конкретного применения Fragment к confirmed question.

LLM использует:

- Fragment;
- Thought;
- Commentary;
- Context;
- perspective.

Рабочие состояния:

- `PASS`;
- `UNCERTAIN`;
- `FAIL`.

`FAIL` → `REJECT`.  
`UNCERTAIN` не может дать `STRONG`.

---

## 28. STRONG / POSSIBLE / REJECT

Финальный статус вычисляет orchestrator по structured fields, а не свободное мнение LLM.

### STRONG

Candidate:

- непосредственно работает с confirmed question;
- применим к narrative;
- философски продуктивен;
- не требует отсутствующей предпосылки;
- проходит source-fidelity gate.

### POSSIBLE

Существует содержательная связь, но:

- применимость остаётся неопределённой;
- требуется `UNSUPPORTED` assumption;
- либо source fidelity остаётся `UNCERTAIN`.

### REJECT

Candidate:

- не работает с confirmed question;
- неприменим к narrative;
- требует предпосылки, противоречащей narrative;
- либо искажает источник.

Концептуальная rule table:

| Relevance | Applicability | Assumption | Fidelity | Result |
|---|---|---|---|---|
| YES | YES | NONE | PASS | STRONG |
| YES/PARTIAL | UNCERTAIN | UNSUPPORTED | PASS | POSSIBLE |
| YES | YES | NONE | UNCERTAIN | POSSIBLE |
| NO | any | any | any | REJECT |
| any | NO / contradicted applicability | CONTRADICTED | any | REJECT |
| any | any | any | FAIL | REJECT |

Пограничные комбинации должны быть явно специфицированы перед implementation либо покрыты eval; LLM не должен самовольно менять hard rules.

---

## 29. Candidate reason

Для каждого candidate сохраняется короткое объяснение результата.

Нужна объяснимость уровня:

- почему Fragment применим;
- какая предпосылка отсутствует;
- почему source fidelity нарушена;
- почему candidate отклонён.

Полный chain-of-thought не требуется и не хранится.

---

## 30. Роль POSSIBLE

### Решение D14

В MVP final selection строится из `STRONG`.

`POSSIBLE`:

- сохраняются в trace;
- используются для eval;
- помогают диагностировать corpus gaps;
- не повышаются до финального Fragment только ради заполнения результата.

---

# Часть VI. Diversity + coverage selection

## 31. Anchor Fragment

### Решение D15

Из квалифицированных STRONG сначала выбирается anchor Fragment:

> наиболее непосредственно работающий с центром confirmed question и преобразующий его постановку, не меняя вопрос за пользователя.

Embedding similarity на этой стадии не используется как содержательный критерий.

Сравнительный LLM-pass допустим после independent qualification.

Точный механизм comparative selection — `EVAL PARAMETER`.

---

## 32. Второй Fragment

Второй Fragment не является автоматически кандидатом №2 по semantic или LLM ranking.

Он должен:

- оставаться STRONG;
- совершать самостоятельный философский ход;
- добавлять содержательно отличающуюся или существенно дополняющую перспективу.

---

## 33. Operation-aware diversity

### Решение D16

`philosophical_operation` — signal, а не hard classifier.

Одинаковая operation:

- сильный сигнал возможного дублирования;
- не автоматический запрет.

Разные operations:

- сигнал возможного различия;
- не доказательство реальной философской дистанции.

Сравнение перспектив возвращает рабочее отношение:

- `DISTINCT`;
- `OVERLAPPING`;
- `COMPLEMENTARY`.

Для совместного selection подходят `DISTINCT` и содержательно значимый `COMPLEMENTARY`.

`OVERLAPPING` обычно не добавляется.

Традиция сама по себе не является diversity criterion.

Два Fragment разных традиций могут дублировать одну operation.  
Два Fragment одной традиции могут быть выбраны вместе, если выполняют существенно разные операции.

---

## 34. Coverage of question structure

### Решение D17

Coverage проверяется относительно `question_aspects` конкретного confirmed question.

Главный вопрос:

> Какие существенные стороны противоречия, различения или структуры confirmed question уже получили самостоятельный философский голос?

Coverage не определяется:

- числом coordinates;
- числом traditions;
- числом authors;
- числом operations;
- механическим совпадением tags.

Один Fragment может покрывать несколько aspects.

Каждому aspect не требуется отдельная карточка.

---

## 35. Targeted second recall

### Решение D18

Targeted second recall запускается только если:

1. уже выбраны сильные перспективы;
2. coverage analysis обнаружил существенный uncovered aspect;
3. среди оставшихся STRONG initial pool нет подходящего самостоятельного голоса.

Он не запускается только ради получения третьей карточки.

Вход targeted recall:

- тот же confirmed question;
- тот же frozen Query Representation;
- uncovered `target_aspect`;
- уже выбранные perspectives / operations как контекст для поиска недостающего голоса.

Confirmed question и Query Representation не переписываются.

---

## 36. Gates targeted recall

### Решение D19

Candidate из targeted second recall проходит тот же полный стандарт:

- semantic recall;
- question relevance;
- situational applicability;
- required_assumption;
- source fidelity;
- STRONG / POSSIBLE / REJECT;
- diversity;
- coverage contribution.

Targeted recall изменяет область поиска, но не снижает стандарт доказательства STRONG.

---

## 37. Третий Fragment

Третий Fragment добавляется только если он:

1. `STRONG`;
2. source-faithful;
3. не требует unsupported/contradicted assumption;
4. `DISTINCT` или существенно `COMPLEMENTARY`;
5. закрывает meaningful uncovered aspect либо иначе явно расширяет философское исследование confirmed question.

Слабый третий Fragment не добавляется.

---

# Часть VII. Sufficiency

## 38. Успешный результат

### Решение D20

Sufficiency определяется качеством и различием философских перспектив, а не достижением фиксированного количества карточек.

Полноценный результат:

- два STRONG с содержательно различающимися/дополняющими perspectives;

или

- три STRONG, если третий действительно добавляет самостоятельный философский ход.

Два сильных Fragment — нормальный success state.

---

## 39. Corpus-side insufficient coverage

Если после initial recall и, когда он действительно требуется, targeted second recall:

- найдено меньше двух usable STRONG;
- либо найденные STRONG практически полностью overlapping и не удаётся получить самостоятельную вторую перспективу;

фиксируется `corpus-side insufficient coverage`.

До этого вывода targeted second recall обязателен, если существует конкретная непокрытая существенная сторона вопроса.

При insufficient coverage запрещено:

- придумывать цитату;
- добавлять философа из общих знаний модели;
- повышать POSSIBLE до STRONG ради результата;
- заменять retrieval советом;
- добавлять слабый Fragment ради количества.

---

# Часть VIII. Текущий end-to-end pipeline

```text
124 VERIFIED FRAGMENTS
        ↓
CANONICAL JSONL
        ↓
MEANING / STRUCTURE / SOURCE representations
        ↓
EMBEDDINGS / RETRIEVAL INDEX

CONFIRMED QUESTION
        +
FULL NARRATIVE
        +
circumstance / experience / inquiry
        +
previous UX coordinates / tensions
        ↓
FROZEN QUERY REPRESENTATION
        ↓
3 INDEPENDENT SEMANTIC RECALL ROUTES
        ↓
UNION + DEDUPLICATION + PROVENANCE
        ↓
BROAD POOL LIMIT
        ↓
INDEPENDENT CANDIDATE EVALUATION
        ↓
QUESTION RELEVANCE
        ↓
SITUATIONAL APPLICABILITY
        ↓
REQUIRED ASSUMPTION
        ↓
SOURCE FIDELITY
        ↓
DETERMINISTIC STATUS RULES
        ↓
STRONG / POSSIBLE / REJECT
        ↓
STRONG ONLY
        ↓
ANCHOR SELECTION
        ↓
OPERATION-AWARE DIVERSITY
        ↓
SECOND STRONG
        ↓
COVERAGE OF QUESTION STRUCTURE
        ↓
if needed:
TARGETED SECOND RECALL
        ↓
FULL GATES AGAIN
        ↓
SUFFICIENCY GATE
        ↓
FINAL 2–3 FRAGMENTS
        ↓
ONLY NOW:
PERSONAL LINK + ONE QUESTION
```

---

# Часть IX. EVAL PARAMETERS — сознательно не зафиксировано

Следующие значения нельзя придумывать до eval:

1. embedding model;
2. точный текст serialization для MEANING / STRUCTURE / SOURCE;
3. полезность SOURCE route;
4. полезность Commentary в semantic recall;
5. число кандидатов от каждого route;
6. общий broad candidate pool size;
7. similarity thresholds, если они вообще нужны;
8. fusion/ranking algorithm между routes;
9. любые математические веса routes;
10. comparative mechanism для anchor selection;
11. batch size candidate evaluator;
12. необходимость разделять situational relevance и source fidelity на отдельные LLM calls;
13. конкретная LLM/model для Query Representation и candidate evaluation;
14. пограничные комбинации rule table, не определённые содержательной архитектурой.

Эти параметры должны определяться через eval, а не архитектурное предположение.

---

# Часть X. Personal Link + One Question

## 41. Момент генерации

### Решение D21

`Personal Link + One Question` создаются только после окончательного выбора Fragment и успешного sufficiency gate.

Они не участвуют в recall, qualification или selection.

Это сохраняет причинный порядок:

```text
retrieval → qualification → selection → sufficiency → personal link
```

а не:

```text
interpret user → find a quote supporting the interpretation
```

---

## 42. Personal Link

Назначение:

> показать, каким образом философский ход выбранного Fragment может быть приложен к confirmed question пользователя, сохраняя вопрос открытым.

Personal Link не является:

- советом;
- диагнозом;
- объяснением скрытых мотивов;
- решением вопроса;
- доказательством истинности философской позиции;
- свободной психологической интерпретацией пользователя.

### Решение D22

Personal Link строится только на пересечении:

1. того, что действительно поддержано narrative / Query Representation;
2. философского хода выбранного Fragment.

Модель не имеет права добавлять третью составляющую — собственную теорию о пользователе.

Формулировка должна описывать возможное направление исследования, а не сообщать пользователю истину о нём.

---

## 43. One Question

После каждого Personal Link система задаёт ровно один вопрос.

Его задача:

> помочь пользователю применить философское различение Fragment к собственному confirmed question.

### Решение D23

One Question должен быть открытым и не проверять согласие пользователя с философской перспективой.

Он должен допускать:

- согласие;
- несогласие;
- третье понимание;
- отсутствие ответа.

Риторический вопрос со встроенным выводом запрещён.

### Решение D24

One Question может:

- уточнять confirmed question;
- разделять его компоненты;
- проблематизировать его;
- исследовать его через philosophical_operation выбранного Fragment.

Он не может подменять confirmed question новым вопросом о том, какое решение пользователю следует принять.

---

## 44. Input финального генератора

Для каждого окончательно выбранного Fragment генератор получает:

### User side

- confirmed question;
- full narrative;
- narrative facts;
- representations;
- question aspects.

### Fragment side

- fragment;
- thought;
- commentary;
- context;
- perspective;
- philosophical_operation.

### Retrieval side

- краткую причину STRONG;
- aspects, которые Fragment покрывает.

Embedding scores, ranking positions, rejected candidates и POSSIBLE для этой задачи не нужны.

---

## 45. Output contract

### Решение D25

Пользовательский output для каждого выбранного Fragment ограничен:

- `fragment_id`;
- `personal_link`;
- `question`.

Не создаются поля:

- recommendation;
- advice;
- conclusion;
- diagnosis;
- action_plan.

Выбранные первоисточники и их библиографические данные отображаются из canonical Fragment, а не генерируются заново моделью.

---

## 46. Grounding check

### Решение D26

Перед показом пользователю Personal Link + One Question проходят отдельный grounding check.

Проверяется:

- нет ли утверждения о пользователе, отсутствующего в narrative;
- не добавлен ли скрытый мотив;
- не возник ли совет;
- не приняла ли система решение за пользователя;
- поддерживается ли философский ход самим Fragment;
- сохранён ли confirmed question;
- остаётся ли question открытым.

Рабочий результат:

- `PASS`;
- `FAIL` + краткая причина.

При `FAIL` выбранные Fragment не меняются. Перегенерируется только Personal Link / Question.

---

# Часть XI. Logging / observability

## 47. Retrieval run

### Решение D27

Каждый retrieval после confirmed question получает единый `run_id`.

Один trace связывает:

- input;
- frozen Query Representation;
- semantic recall;
- pool limiting;
- candidate evaluations;
- selection;
- coverage;
- targeted recall;
- sufficiency;
- final fragments;
- Personal Link generation;
- grounding checks.

---

## 48. Версионирование

### Решение D28

Trace должен сохранять версии или полные конфигурации всех компонентов, способных изменить результат:

- corpus version;
- representation schema version;
- embedding model;
- embedding index version;
- retrieval parameters;
- Query Representation prompt version;
- candidate evaluator prompt version;
- selection prompt version;
- coverage prompt version;
- Personal Link prompt version;
- grounding prompt version;
- LLM model/version для каждого stage.

---

## 49. Recall trace

До pool limiting сохраняется результат каждого route:

- candidate ID;
- similarity;
- route position.

После union/deduplication:

- `found_by[]`;
- route similarities;
- route positions;
- `included_in_broad_pool`.

Это позволяет различать:

- `RECALL_MISS`;
- `POOL_LIMIT_MISS`.

---

## 50. Candidate trace

### Решение D29

Для каждого candidate в broad pool сохраняются:

- question relevance;
- situational applicability;
- required assumption status;
- required assumption text;
- source fidelity;
- final STRONG / POSSIBLE / REJECT;
- короткая причина;
- постоянные retrieval metadata Fragment.

Similarity хранится для анализа, но candidate evaluator её не видит.

---

## 51. Selection / coverage / sufficiency trace

Для STRONG сохраняются:

- candidates considered for anchor;
- selected anchor;
- reason;
- pairwise relation: DISTINCT / COMPLEMENTARY / OVERLAPPING;
- selected second/third;
- reason каждого невыбранного STRONG.

Coverage trace:

- question aspects;
- какие Fragment покрывают каждый aspect;
- uncovered aspects;
- был ли targeted recall;
- target aspect;
- полный trace targeted recall.

Sufficiency trace:

- PASS / INSUFFICIENT_COVERAGE;
- структурированная причина.

---

## 52. Final generation trace

Для каждого выбранного Fragment:

- Personal Link;
- Question;
- grounding PASS / FAIL;
- причина FAIL;
- номер generation attempt при регенерации.

---

## 53. Failure taxonomy

### Решение D30

Debugging и eval используют общую taxonomy failure stages:

- `QUERY_REPRESENTATION_ERROR`;
- `RECALL_MISS`;
- `POOL_LIMIT_MISS`;
- `RELEVANCE_FALSE_POSITIVE`;
- `RELEVANCE_FALSE_NEGATIVE`;
- `ASSUMPTION_ERROR`;
- `SOURCE_FIDELITY_ERROR`;
- `DIVERSITY_ERROR`;
- `COVERAGE_ERROR`;
- `TARGETED_RECALL_MISS`;
- `SUFFICIENCY_ERROR`;
- `PERSONAL_LINK_GROUNDING_ERROR`.

Это quality failures, а не обязательно runtime exceptions.

---

## 54. MVP observability

### Решение D31

Внешний observability framework для MVP не требуется.

Достаточно собственного structured retrieval trace, например:

`logs/retrieval/<run_id>.json`

Production storage позднее может быть заменён без изменения trace schema.

---

## 55. Privacy boundary

### Решение D32

Observability не должна технически требовать постоянного хранения полного пользовательского narrative.

Development/eval может хранить полный synthetic trace.

Production trace schema должна позволять:

- не сохранять raw narrative;
- хранить technical trace отдельно;
- применять отдельную retention/privacy policy.

---

# Часть XII. Eval

## 56. Stage-level eval

### Решение D33

Eval проверяет каждый существенный stage отдельно:

```text
QUERY REPRESENTATION
→ RECALL
→ QUALIFICATION
→ DIVERSITY
→ COVERAGE
→ SUFFICIENCY
→ PERSONAL LINK
```

Финальный красивый ответ не может маскировать upstream failure.

---

## 57. Golden Set v0

### Решение D34

`RETRIEVAL-VALIDATION-6-SCENARIOS-v0.1.md` становится основой Golden Set v0.

Golden Set не задаёт единственный правильный набор из 2–3 Fragment.

Для сценария фиксируются только те ожидания, которые действительно установлены validation:

- confirmed question;
- narrative;
- gold relevant candidates, где они известны;
- known bad candidates, где они известны;
- expected question aspects;
- acceptable philosophical operations / distinctions;
- forbidden assumptions;
- minimum sufficient result.

Если исходная validation не устанавливает конкретное поле, его нельзя придумывать только ради заполнения fixture.

---

## 58. Recall eval

Для каждого сценария вручную определяется небольшой `gold_recall` набор: Fragment, которые должны быть доступны системе как хорошие candidates, даже если не все попадут в final selection.

Основная измеримая величина:

`Recall@pool = found gold relevant fragments / all gold relevant fragments`.

### Решение D35

Broad pool size выбирается по empirical recall curve, а не заранее.

Тестируются несколько размеров pool; фиксируется минимальная конфигурация, после которой дальнейшее увеличение почти перестаёт возвращать потерянные gold candidates.

---

## 59. Route ablation

### Решение D36

MEANING / STRUCTURE / SOURCE проверяются отдельно.

Для каждого gold candidate фиксируется, каким route он был найден.

Дополнительный route должен оправдать себя уникальным вкладом в recall.

Таким же способом проверяется необходимость Commentary в semantic representation.

---

## 60. Qualification eval

Для candidates можно задавать ожидания разной строгости:

- `STRONG`;
- `POSSIBLE_OR_REJECT`;
- `MUST_NOT_BE_STRONG`.

Это позволяет отдельно измерять:

- false positive STRONG;
- false negative STRONG.

Численный penalty заранее не задаётся.

---

## 61. Required-assumption contrast tests

### Решение D37

Required-assumption evaluator получает отдельные contrastive tests.

Одна ситуация изменяется минимально так, чтобы ожидаемое состояние было:

- `NONE`;
- `UNSUPPORTED`;
- `CONTRADICTED`.

Это проверяет, что система реагирует на реальные изменения narrative, а не стабильно навязывает одну интерпретацию.

---

## 62. Source fidelity eval

Создаются пары:

- Fragment + source-faithful application;
- тот же Fragment + distorted application.

Ожидание:

- `PASS`;
- `FAIL`.

Особенно важны случаи, где искажённое применение звучит психологически правдоподобно.

---

## 63. Diversity eval

### Решение D38

Для известных пар/троек можно вручную задавать:

- DISTINCT;
- COMPLEMENTARY;
- OVERLAPPING.

Diversity оценивается на уровне philosophical perspectives/operations, а не по разнообразию authors/traditions/metadata.

---

## 64. Coverage / targeted recall eval

Для Golden scenarios фиксируются существенные question aspects там, где это поддерживается validation.

Проверяется:

1. правильно ли Query Representation выделяет aspects;
2. правильно ли selection определяет coverage;
3. запускается ли targeted recall, когда есть meaningful gap;
4. не запускается ли он только ради третьего Fragment.

---

## 65. Sufficiency eval

### Решение D39

Eval специально проверяет способность системы отказаться от слабого результата.

Нужны cases:

- доступны три хорошие перспективы;
- доступны только две хорошие;
- есть одна STRONG + несколько POSSIBLE;
- есть две STRONG, но они overlapping.

Ожидаемое поведение следует D18–D20 и не допускает искусственного заполнения результата.

---

## 66. Personal Link eval

Проверяются свойства:

- grounded in narrative;
- grounded in Fragment;
- no invented motive;
- no diagnosis;
- no advice;
- no decision for user;
- no hidden assumption;
- open question;
- confirmed question preserved.

Используются deterministic checks, где возможно, semantic judge для содержательных свойств и ручной review критических cases.

---

## 67. Порядок tuning

### Решение D40

EVAL PARAMETERS настраиваются в порядке pipeline:

1. Query Representation;
2. recall;
3. qualification;
4. selection / coverage;
5. Personal Link.

Downstream слой не используется для маскировки upstream ошибки.

Шесть сценариев достаточны для первой architecture validation и regression, но не считаются достаточным production eval set.

Для защиты от prompt-overfitting при малом наборе использовать leave-one-scenario-out режим при tuning.

---

# Часть XIII. MVP stack

## 68. Runtime

### Решение D41

Retrieval MVP реализуется на Python.

---

## 69. Vector search

### Решение D42

Vector DB для MVP не используется.

124 Fragment × 3 representations = 372 vectors.

Semantic search выполняется локально in-memory через cosine similarity.

---

## 70. Embedding artifacts

### Решение D43

Derived index хранится как rebuildable artifact:

```text
data/retrieval/
  embeddings.npy
  index.json
```

`embeddings.npy` — vector matrix.

`index.json` связывает строки matrix с:

- Fragment ID;
- representation type;
- corpus version;
- representation schema version;
- embedding model/version;
- build metadata.

Canonical corpus не дублируется в index без необходимости.

---

## 71. Database boundary

### Решение D44

Retrieval MVP не требует database server и не требует SQLite как части semantic engine.

Canonical corpus = JSONL.  
Vectors = NPY.  
Index metadata = JSON.  
Development trace = structured JSON.

Persistence пользователей/sessions/history/feedback относится к следующему production layer.

---

## 72. Typed contracts

### Решение D45

Все границы pipeline имеют typed Pydantic contracts.

Минимальный набор domain objects:

- Fragment;
- QueryRepresentation;
- RecallCandidate;
- CandidateEvaluation;
- SelectedFragment;
- CoverageResult;
- SufficiencyResult;
- PersonalLinkResult;
- RetrievalTrace.

LLM structured output всегда проходит schema validation.

---

## 73. Provider boundaries

### Решение D46

LLM и embeddings скрыты за минимальными собственными interfaces:

- `LLMClient`;
- `EmbeddingClient`.

Retrieval engine не должен зависеть от конкретного provider.

Конкретные модели выбираются eval и не зашиваются в архитектуру заранее.

---

## 74. Orchestration

### Решение D47

MVP использует явный последовательный orchestrator, а не agent framework.

Концептуально:

```text
run_retrieval(input)
  → build_query_representation
  → broad_recall
  → evaluate_candidates
  → select_anchor
  → select_diverse_second
  → check_coverage
  → targeted_recall if needed
  → check_sufficiency
  → generate_personal_links
  → grounding_check
  → save_trace
```

LangChain/LlamaIndex/CrewAI/graph orchestrator не требуются для MVP.

Candidate evaluation может batch'иться, но внутри batch каждый candidate получает независимую structured evaluation. Batch size — EVAL PARAMETER.

---

## 75. Build-time vs runtime

### Решение D48

Indexing корпуса — build-time process.

Build-time:

```text
validate corpus
→ build representations
→ generate embeddings
→ save immutable index
→ corpus/index integrity checks
```

Runtime:

```text
load index
→ build frozen Query Representation
→ embed retrieval queries
→ recall
→ qualification
→ selection
→ Personal Link
```

124 Fragment не embedding'уются заново на пользовательский запрос.

---

## 76. Corpus validator

### Решение D49

Index build запрещён при structural schema gaps.

Validator проверяет минимум:

- ожидаемое число 124 Fragment;
- unique stable IDs;
- required fields;
- duplicate IDs;
- broken relations;
- taxonomy values;
- allowed philosophical_operation;
- presence/shape question_structures;
- source/verification fields согласно canonical schema.

### Implementation prerequisite

Исторический `OPERATION-AUDIT-launch-113-v0.1.md` покрывал 113 карточек.

Позднее принято, что все 124 Fragment verified и участвуют в retrieval.

Перед STRUCTURE index необходимо физически проверить, что все 124 карточки имеют необходимые `philosophical_operation` и `question_structures`.

Если у 11 карточек эти retrieval metadata отсутствуют, это **schema gap**, а не возврат к статусу «unverified». Gap должен быть явно отчитан и затем устранён/утверждён до полноценного STRUCTURE index.

---

## 77. Репозиторий

Целевая логическая структура:

```text
project/
├── data/
│   ├── corpus/
│   │   └── fragments.jsonl
│   ├── retrieval/
│   │   ├── embeddings.npy
│   │   └── index.json
│   └── eval/
│       └── scenarios/
├── src/
│   └── navigator/
│       ├── models/
│       ├── corpus/
│       ├── representations/
│       ├── embeddings/
│       ├── retrieval/
│       ├── evaluation/
│       ├── selection/
│       ├── generation/
│       ├── tracing/
│       └── providers/
├── evals/
├── tests/
└── scripts/
```

Точные filenames и package decomposition могут уточняться в implementation, если архитектурные границы сохраняются.

---

## 78. CLI-first

### Решение D50

Первая implementation milestone — локальный CLI retrieval engine + eval harness, а не HTTP API/UI.

Целевые команды:

- `validate-corpus`;
- `build-index`;
- `run-retrieval`;
- `run-evals`.

HTTP layer добавляется только после стабильной работы core pipeline.

Вероятный следующий transport — FastAPI, но retrieval logic не размещается в route handlers.

---

## 79. Dependencies

Начальный стек:

- Python;
- Pydantic;
- NumPy;
- provider SDK / HTTP client;
- pytest.

FastAPI — позднее, после core engine.

Не вводить без измеримой необходимости:

- LangChain;
- LlamaIndex;
- vector DB;
- agent framework;
- Redis;
- Celery;
- Kafka;
- Elasticsearch;
- knowledge graph.

---

# Часть XIV. Implementation milestones

## 80. Milestone 1 — canonical corpus + schemas

### Решение D51

Первый Claude Code pass заканчивается после:

1. чтения source-of-truth документов;
2. импорта/нормализации canonical 124 Fragment;
3. реализации Pydantic schemas;
4. реализации corpus validator;
5. запуска validator;
6. подготовки validation report.

**STOP.**

На Milestone 1 запрещено реализовывать:

- embeddings;
- vector search;
- Query Representation LLM;
- candidate evaluator;
- selection;
- Personal Link;
- API;
- UI.

Цель milestone — установить фактическое состояние данных до реализации retrieval.

---

## 81. Milestone 2 — semantic recall

После человеческого подтверждения Milestone 1:

- representation builder;
- configurable EmbeddingClient;
- build index;
- local cosine search;
- three recall routes;
- provenance;
- recall diagnostics;
- initial recall eval / route ablation.

На этом milestone не требуется полноценный candidate LLM evaluator.

---

## 82. Milestone 3 — qualification

После подтверждения recall:

- Query Representation;
- candidate evaluation;
- required_assumption;
- source fidelity;
- deterministic STRONG / POSSIBLE / REJECT;
- contrast tests;
- qualification eval.

---

## 83. Milestone 4 — complete retrieval

После qualification:

- anchor selection;
- diversity;
- coverage;
- targeted second recall;
- sufficiency;
- Personal Link;
- grounding check;
- complete retrieval trace;
- end-to-end eval.

---

## 84. Milestone 5 — product integration

Только после стабильного core engine:

- HTTP API;
- production persistence;
- privacy/retention policy;
- session/history integration;
- UI integration;
- production observability.

---

# Часть XV. Hard invariants

Следующие правила не являются EVAL PARAMETERS и не могут быть самовольно изменены реализацией.

1. Retrieval начинается только после confirmed question.
2. Confirmed question не переписывается за пользователя.
3. Launch corpus для текущей архитектуры = 124 verified Fragment.
4. `CORPUS-FULL-1090` не участвует в launch retrieval.
5. Canonical corpus является источником истины; index rebuildable.
6. Tradition не является классификатором пользователя и hard retrieval filter.
7. `philosophical_operation` / `question_structures` — retrieval signals, не hard classifiers.
8. Query Representation строится один раз и замораживается на run.
9. Full narrative обязателен для candidate applicability, но не является основным embedding query.
10. Query Representation не предсказывает требуемую `philosophical_operation`.
11. Semantic similarity используется для recall, не для доказательства relevance или final selection.
12. Candidate evaluator не видит similarity/ranking.
13. Candidates квалифицируются независимо до comparative selection.
14. `required_assumption` вычисляется динамически для `candidate × narrative`.
15. `required_assumption != NONE` запрещает STRONG.
16. `CONTRADICTED` assumption ведёт к REJECT.
17. Source fidelity проверяет конкретное применение Fragment.
18. Final selection строится из STRONG.
19. POSSIBLE не используется для заполнения результата ради количества.
20. Diversity определяется содержательной перспективой, а не metadata diversity.
21. Coverage относится к структуре confirmed question.
22. Targeted second recall запускается только из-за meaningful coverage need.
23. Targeted recall проходит те же qualification gates.
24. Два сильных различающихся Fragment — полноценный success state.
25. Слабый третий Fragment не добавляется.
26. При insufficient coverage система не дополняет corpus знаниями модели.
27. Personal Link создаётся только после final selection.
28. Personal Link не содержит совета, диагноза или скрытого мотива.
29. One Question остаётся открытым и не меняет confirmed question.
30. Final personalized generation проходит grounding check.
31. LLM outputs валидируются typed schemas.
32. Retrieval реализуется explicit orchestrator, не autonomous agent.
33. Corpus indexing отделён от runtime retrieval.
34. Structural schema gaps блокируют index build.
35. Claude Code не меняет эти invariants без отдельного решения владельца проекта.

---

# Часть XVI. Open questions / EVAL PARAMETERS

До сравнительного eval сознательно не фиксируются:

1. embedding model;
2. LLM model(s);
3. точная serialization MEANING;
4. точная serialization STRUCTURE;
5. точная serialization SOURCE;
6. нужен ли SOURCE route;
7. нужен ли Commentary в semantic recall;
8. число candidates на route;
9. общий broad pool size;
10. similarity threshold, если он вообще нужен;
11. fusion/ranking algorithm между routes;
12. математические веса routes — по умолчанию отсутствуют;
13. candidate evaluation batch size;
14. один или несколько LLM calls для candidate gates;
15. comparative mechanism anchor selection;
16. конкретный semantic judge для eval;
17. production latency/cost targets;
18. production retention policy для narrative/trace.

Эти параметры должны определяться экспериментом или отдельным продуктовым решением.

---

# Часть XVII. Consistency / implementation-readiness check

## 85. Проверка на внутренние противоречия

В D01–D51 не обнаружено архитектурного противоречия, блокирующего реализацию.

Ключевые границы согласованы:

- canonical corpus отделён от derived index;
- static Fragment metadata отделены от run-specific judgments;
- recall отделён от qualification;
- qualification отделена от comparative selection;
- selection отделён от personalized generation;
- semantic similarity не протекает в evaluator;
- dynamic assumptions не записываются в Fragment;
- coverage не превращается в требование «обязательно три»;
- targeted recall не снижает standard of evidence;
- observability повторяет реальные stages pipeline;
- eval настраивает pipeline сверху вниз;
- stack не вводит инфраструктуру, не нужную корпусу 124.

## 86. Единственный фактический prerequisite перед semantic implementation

Нужно установить фактическое состояние всех 124 launch cards:

- все ли 124 физически присутствуют;
- все ли проходят canonical schema;
- есть ли у всех 124 `philosophical_operation`;
- есть ли у всех 124 `question_structures`;
- целы ли relations/IDs/source metadata.

Именно поэтому Milestone 1 заканчивается validation report.

## 87. Implementation-readiness verdict

**Технический дизайн достаточен для начала Milestone 1.**

Он пока сознательно **не фиксирует eval-derived параметры**, потому что их выбор является частью последующих milestones, а не prerequisite для corpus normalization/validation.

Claude Code можно подключать сейчас при условии, что первый pass строго ограничен Milestone 1 и заканчивается отчётом без реализации retrieval.

---

# Часть XVIII. Acceptance criteria — Milestone 1

Milestone 1 считается завершённым, если:

1. Claude Code нашёл и прочитал актуальные source-of-truth документы проекта.
2. Создан canonical `data/corpus/fragments.jsonl` с ожидаемыми 124 Fragment либо выдан точный отчёт, почему 124 карточки невозможно собрать из текущих файлов без содержательного решения человека.
3. Каждый Fragment имеет stable unique ID.
4. Canonical schema формализована typed Pydantic models.
5. Validator проверяет required fields и типы.
6. Validator проверяет duplicate IDs.
7. Validator проверяет relations на существующие IDs.
8. Validator проверяет допустимые taxonomy values там, где taxonomy закрыта.
9. Validator проверяет `philosophical_operation`.
10. Validator проверяет presence/shape `question_structures`.
11. Validator отдельно показывает любые gaps у 11 карточек, исторически не входивших в operation audit.
12. Validator не переводит карточки обратно в `unverified` только потому, что у них отсутствует retrieval metadata.
13. Никакой философский текст, Thought, Fragment, Commentary или metadata не выдуманы для заполнения gaps.
14. Создан machine-readable validation output.
15. Создан короткий human-readable validation report.
16. Tests покрывают основные validator failures.
17. Embeddings/retrieval/API/UI не реализованы.
18. Claude Code останавливается и ждёт человеческого решения по обнаруженным gaps.

---

# Часть XIX. Статус

**Версия:** v0.2 — implementation-ready for Milestone 1.

Архитектурно спроектирован полный путь:

```text
CONFIRMED QUESTION
→ FROZEN QUERY REPRESENTATION
→ BROAD RECALL
→ CANDIDATE QUALIFICATION
→ REQUIRED ASSUMPTION
→ SOURCE FIDELITY
→ STRONG / POSSIBLE / REJECT
→ DIVERSITY
→ COVERAGE
→ TARGETED SECOND RECALL
→ SUFFICIENCY
→ FINAL 2–3 FRAGMENTS
→ PERSONAL LINK + ONE QUESTION
→ GROUNDING CHECK
→ TRACE
```

Следующий практический шаг — Milestone 1 в Claude Code.
