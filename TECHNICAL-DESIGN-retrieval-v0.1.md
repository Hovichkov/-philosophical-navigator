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

# Часть X. Что ещё НЕ спроектировано

До передачи реализации в Claude Code необходимо закончить:

1. **Personal Link + One Question**
   - вход;
   - structured output;
   - ограничения;
   - защита от advice-first generation.

2. **Logging / observability**
   - run trace;
   - candidate trace;
   - версии corpus/prompts/models/index;
   - причины recall/selection/rejection.

3. **Eval**
   - превращение шести эталонных сценариев в regression suite;
   - expected candidate behavior;
   - recall metrics;
   - gate metrics;
   - selection/coverage checks;
   - подбор `EVAL PARAMETERS`.

4. **Minimal MVP stack**
   - runtime;
   - storage;
   - embedding storage/search;
   - LLM API boundary;
   - deployment;
   - cost/latency constraints.

5. **Implementation handoff**
   - финальный Technical Design;
   - acceptance criteria;
   - порядок implementation;
   - стартовый пакет и промпт для Claude Code.

---

## 40. Статус документа

Архитектурно зафиксированы:

- physical corpus storage;
- canonical Fragment boundary;
- semantic representations;
- Query Representation;
- broad recall;
- candidate pool;
- situational relevance;
- dynamic required_assumption;
- source-fidelity gate;
- STRONG / POSSIBLE / REJECT;
- operation-aware diversity;
- coverage-of-question-structure;
- targeted second recall;
- sufficiency gate.

**Технический дизайн ещё не достаточен для начала разработки.**

Следующий проектируемый блок:

> **PERSONAL LINK + ONE QUESTION после окончательного выбора Fragment.**

После Personal Link, logging, eval и minimal stack будет подготовлен финальный implementation-ready пакет для Claude Code.
