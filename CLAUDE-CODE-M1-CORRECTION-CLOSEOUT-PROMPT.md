# CLAUDE CODE — M1 CORRECTION / CLOSEOUT PROMPT

Продолжай существующий проект после завершённого Milestone 1. Не начинай Milestone 2, пока не закончишь описанную ниже коррекцию и не выдашь новый validation report.

## 1. Исправление источника истины по launch corpus

Предыдущее указание `124 verified / unresolved = 0` считать отменённым.

Текущее MVP-правило:

- launch shortlist: 124;
- `verified`: 113;
- `unresolved`: 11;
- unresolved IDs:
  `C0377`, `C0396`, `C0398`, `C0215`, `C0230`, `C0258`, `C0703`, `C0704`, `C0705`, `C0706`, `C0707`;
- эти 11 должны храниться в корпусе/manifest для истории и аудита, но **не должны попадать в retrieval candidate universe**;
- retrieval allowlist = 113 verified Fragment.

При конфликте с `TECHNICAL-DESIGN-retrieval-v0.2.md` и старым `CLAUDE-CODE-M1-START-PROMPT.md` это правило имеет приоритет. Не меняй 11 unresolved на verified автоматически.

## 2. Первые 29 карточек

Добавлен восстановительный файл:

`CORPUS-LAUNCH-FIRST-29-recovery-source-v0.2.md`

Используй его как recovery-source для первых 29 ранее утверждённых карточек.

Важно:

- старый финальный YAML этих 29 физически не найден;
- не выдавай реконструированные поля за найденный оригинал;
- 25/29 имеют восстановленные registry-поля: source/tradition/work/location/philosophical move/perspective/coordinates/tensions;
- для `C1105`, `C0957`, `C0937`, `C0949` подтверждено членство в ранее утверждённых батчах, но старая registry-запись не восстановлена;
- для этих четырёх используй только уже существующие в проекте source/launch metadata и ранее сохранённые данные. Не придумывай semantic fields;
- если обязательное semantic поле этих четырёх невозможно восстановить из локальных источников, пометь его как recovery gap и не блокируй из-за этого весь M1, если поле не нужно для MVP retrieval.

Сохрани provenance, например отдельным служебным полем/manifest metadata:
`recovery_status = reconstructed_from_registry`
или эквивалентно. Не добавляй это поле в runtime Fragment, если оно нарушает утверждённую runtime schema; тогда храни его в manifest/report.

## 3. Исправление C0246

Сохрани уже принятое исправление:

- `C0246` → **Sallatha Sutta, SN 36.6**.

Не возвращай старую ошибочную атрибуцию `Дхаммачаккаппаваттана сутта / SN 56.11`.

Также сохраняются ранее принятые исправления:

- `C0215` → Anattalakkhaṇa Sutta, SN 22.59;
- `C0230` → Kakacūpama Sutta, MN 21;
- `C0258` → Soṇa Sutta, AN 6.55.

Последние три при этом остаются среди 11 unresolved и не входят в retrieval allowlist.

## 4. `fragment` больше не блокирует MVP

Для Milestone 1 и ближайшего MVP полный `TEXT.fragment` **не является обязательным blocking field**.

Причина: SOURCE route является дополнительным recall-route. Пока полных текстов Fragment нет, MVP строится на:

- MEANING route;
- STRUCTURE route.

Сделай следующее:

- разреши `fragment` быть отсутствующим / `null` / иметь только boundary metadata;
- validator не должен давать общий FAIL только из-за отсутствия полного `fragment`;
- SOURCE index/route пока считать `disabled_pending_full_fragment_text`;
- не синтезировать и не пересказывать source text вместо отсутствующего Fragment;
- `thought` остаётся source text и не должен автоматически заменяться paraphrase.

Это временное MVP-решение. Не удаляй SOURCE route из архитектуры окончательно.

## 5. Что НЕ является блокером M1

Следующее не должно останавливать закрытие M1:

- `author = null`, если источник по природе не имеет простого author field;
- пустой `relations`;
- copyright metadata вида `check_per_approved_source_registry` для локального прототипа;
- отсутствие SOURCE embeddings/index;
- recovery provenance первых 29;
- отсутствие operation/question_structures у 11 unresolved, потому что они исключены из retrieval;
- старый reserve-status C0969, если C0969 присутствует в утверждённом launch shortlist: launch shortlist имеет приоритет.

Не заполняй отсутствующие данные догадками только ради прохождения validator.

## 6. Semantic layer

Не переделывай сейчас массово semantic layer 95 карточек только потому, что часть `coordinates` или вопросов выглядит шаблонно.

Для MVP это soft retrieval metadata, а не hard filter.

Validator может выдавать warning о низком разнообразии / шаблонности, но это не должно быть blocking error.

## 7. Validator: ожидаемая логика

После коррекции validator должен различать:

1. `launch_shortlist_count = 124`;
2. `retrieval_verified_count = 113`;
3. `unresolved_count = 11`;
4. exact unresolved ID set совпадает с указанным выше;
5. retrieval candidate universe содержит только 113;
6. unresolved никогда не проходят в retrieval allowlist;
7. schema/ID uniqueness/source identity остаются валидными;
8. отсутствие полного `fragment` даёт warning/status, но не blocking FAIL;
9. отсутствие operation metadata у excluded unresolved не является blocking error;
10. реальные ошибки schema, duplicate IDs, неизвестные taxonomy values, сломанный allowlist и попадание unresolved в retrieval должны оставаться blocking errors.

## 8. Что сделать сейчас

1. Внести минимальные изменения в importer/schema/validator/manifest, необходимые для этих правил.
2. Импортировать recovery-source первых 29 настолько полно, насколько позволяют локальные данные, без выдумывания недостающего.
3. Пересобрать:
   - `data/corpus/fragments.jsonl`
   - `data/corpus/launch-manifest.json`
4. Перезапустить все тесты.
5. Добавить/обновить тесты для правила 113/11 и отсутствующего Fragment.
6. Перезапустить corpus validation.
7. Создать:
   - `reports/validation/M1-CORRECTED-VALIDATION-REPORT.md`
   - машинный JSON validation report.
8. В отчёте отдельно перечислить:
   - blocking errors;
   - non-blocking warnings;
   - recovery gaps первых 29;
   - подтверждение, что retrieval universe = 113.

## 9. Критерий завершения

Milestone 1 можно считать закрытым, если:

- тесты проходят;
- launch shortlist = 124;
- retrieval universe = 113;
- unresolved = ровно 11 и они исключены;
- нет blocking schema/integrity errors;
- отсутствие полного Fragment и прочие перечисленные MVP gaps отражены как warnings, а не как искусственно заполненные данные.

Если эти условия выполнены, в конце отчёта напиши:

`M1_CLOSEOUT_STATUS: PASS`

Если остаётся настоящий blocking error:

`M1_CLOSEOUT_STATUS: FAIL`

и перечисли только реальные блокеры.

После отчёта **остановись. Milestone 2 не начинай.**
