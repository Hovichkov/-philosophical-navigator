# Milestone 1 — validation report

**Дата:** 2026-09-27 · **corpus_version:** `launch-124/0.1.0-m1` · **schema:** `fragment-schema/0.1.0`
**Итог валидатора:** `FAIL` · **index build allowed: `false`** (D49)
Машинные результаты: [`corpus-validation.json`](corpus-validation.json), сводка [`corpus-validation.md`](corpus-validation.md).

---

## 1. Удалось ли получить ровно 124 Fragment

**Да, по составу и ID — 124/124.** Все 124 записи проходят typed-схему Pydantic, ID уникальны (`C\d{4}`), дубликатов нет, состав совпадает с launch-таблицей. Все 124 имеют `technical.operational_status = verified`: валидатор не понижает карточку до unverified из-за пробелов в метаданных.

**Нет, по содержанию.** Canonical JSONL собран, но структурно неполон: 543 blocking-пробела обязательных полей. Цифра «124 verified» верна как операционное решение, но физические данные его пока не подкрепляют (см. §3).

Где физически лежат данные:

| источник | что даёт | покрытие |
|---|---|---|
| `Архив/CORPUS-LAUNCH-124-v.md` (заголовок внутри: «Editorial Review v2») | ID, tradition, work, location, philosophical move | 124 |
| `Архив/CORPUS-LAUNCH-124-v1-final-textual-pass.md` | полные YAML-карточки (TEXT / MEANING / RELATIONS / VERIFICATION) | **95** («continuation after 29 approved cards») |
| `OPERATION-AUDIT-launch-113-v0.1.md` §7 | `philosophical_operation`, `question_structures` | 113 |
| `CORPUS-FULL-1090-v1.md` | строка реестра, только для трассировки (`technical.registry_reference`), в canonical-поля не используется | 124 |

Сверка между источниками: tradition, work, location и move в аудите и в launch-таблице совпадают для всех 113 карточек. Операции распределены точно по счётчикам словаря аудита (26/13/7/…; сумма 113).

## 2. Какие schema gaps найдены (blocking)

| поле | есть | нет | причина |
|---|---|---|---|
| `fragment` | **0** | **124** | ни в одной карточке нет текста фрагмента, только `storage_status: verified_semantic_boundary` |
| `thought` | 67 | 57 | 29 карточек без YAML-карточки + 28 плейсхолдеров `[FINAL TEXTUAL PASS: вставить…]` |
| `context`, `commentary`, `philosophical_questions`, `coordinates`, `tensions`, `perspective` | 95 | 29 | нет карточки |
| `philosophical_operation`, `question_structures` | 113 | 11 | вне аудита 113 |
| `translation` | 74 | 50 | 29 без карточки + 21 плейсхолдер «зафиксировать по утверждённому реестру источников» |
| `source`, `copyright_status`, `source_verified`, `interpretation_verified` | 95 | 29 | нет карточки |
| `author` (optional) | 0 | 124 | во всех карточках `author: null`; значения есть только в реестре 1090 |
| `relations` (optional) | 95 | 29 | у всех 95 `relations: []` → графа связей нет |

**29 карточек без textual-pass карточки** (у всех есть только SOURCE и operation-слой):
C0001 C0013 C0056 C0144 C0167 C0170 C0246 C0404 C0444 C0527 C0553 C0571 C0579 C0633 C0648 C0778 C0786 C0793 C0798 C0806 C0807 C0813 C0871 C0930 C0937 C0949 C0957 C1105 C1108.

**28 плейсхолдеров Thought:** C0004 C0008 C0020 C0023 C0025 C0027 C0028 (Семенцов) · C0274 C0275 C0281 C0296 C0308 C0333 C0339 C0341 C0345 (Таронян) · C0990 (Сыркин) · C0215 C0230 C0258 · C0377 C0396 C0398 · C0703–C0707. Текст плейсхолдера сохранён в `technical.thought_placeholder`, в `thought` его нет.

Полный список пробелов по каждому Fragment — в `corpus-validation.json → fragments_with_gaps`.

## 3. Есть ли operation / question_structures у всех 124

**Нет: у 113 из 124.** Историческим 11 не хватает обоих полей:

`C0215, C0230, C0258, C0377, C0396, C0398, C0703, C0704, C0705, C0706, C0707`

Это ровно 11 бывших unresolved из `operational-status-v2.0`. Разметку я не придумывал. Карточки остаются `verified`, пробел отчитан как retrieval-metadata gap (TD §76). Невалидных операций и malformed `question_structures` нет. Маркер `open / context-dependent` стоит как единственное значение у 18 карточек.

## 4. Broken relations

**Нет**, но проверять нечего: у 95 карточек `relations: []`, у 29 relations отсутствуют. Граф связей в данных не существует (для MVP TD это допускает).

## 5. Конфликты между ожидаемой и фактической схемой / документами

1. **`fragment` не хранится.** CORPUS v0.1 и TD §4 и §9 требуют текст Fragment; SOURCE representation строится из `fragment`. Фактическая схема хранит только статус границы.
2. **Операционное «124 verified» против данных.** 29 карточек имеют `source_verified: false`: 28 unresolved по textual pass и C0577, у которой Thought есть, но флаг false и translation — плейсхолдер. UX-SELF-ANALYSIS пишет, что 17 карточек Семенцова, Сыркина и Тароняна верифицированы вручную после pass, но их дословные Thought ни в одном файле не найдены. Флаги в карточках сохранены как есть и отчитаны как warning.
3. **Интерпретационный слой шаблонный.** Во всех 95 карточках `context`, `commentary` и `perspective` собраны из launch move по шаблону («Launch-кандидат фиксирует…», «Рассмотреть ситуацию через операцию…»). `philosophical_questions` — те же 2–3 шаблонных вопроса. У 43 карточек `coordinates = [действие, отношение к себе]`, у 86 — пустые `tensions`. Для MEANING и STRUCTURE representations это почти нулевой сигнал. Содержательные `perspective` и `coordinates` из реестра 1090 лежат только в `technical.registry_reference`: использовать их без решения нельзя (invariant 4).
4. **Атрибуция сутт.** В launch-таблице у C0215, C0230 и C0258 указано «Дхаммачаккаппаваттана сутта — СН 56.11», а location — тематический заголовок. В карточках это исправлено на SN 22.59, MN 21 и AN 6.55; canonical следует карточкам. **C0246** исправлен «в предыдущем batch» на SN 36.6, но этого batch нет, поэтому canonical содержит старую ошибочную атрибуцию: СН 56.11 / «Первая и вторая стрелы».
5. **Неоднозначные locations у досократиков:** C0703, C0704, C0706, C0707 — тематические, не номера фрагментов; C0705 и C0712 — оба «Фр. 1» без имени философа.
6. **Язык taxonomy.** Карточки используют русские значения TAXONOMY v1.1: все 13 встречающихся coordinates и 3 tensions валидны. Реестр 1090 и `question_structures` — на английском; у `question_structures` нет закрытого словаря ни в одном документе. Валидатор проверяет их форму, а незнакомые значения помечает как warning.
7. **C0969** в реестре 1090 помечен `reserve / RESERVE`, но входит в launch и в аудит.
8. **Технические исправления при импорте, без изменения содержания.**
   - Во всех 95 YAML-блоках первый вопрос содержит «…в ситуации: …» и разбирался как словарь. Пункты списков экранированы дословно; проверено, что остальные значения не меняются.
   - YAML превращал локации `12.1` и `2.10` в числа. Используется loader, оставляющий их строками.
   - Мелочь: заголовок `TECHNICAL-DESIGN-retrieval-v0.2.md` называет документ «v0.1».

## 6. Что требует решения человека до Milestone 2

1. **29 карточек «предыдущих batch'ей»:** найти и передать файл(ы). Без них у 29 Fragment нет TEXT, MEANING и VERIFICATION.
2. **`fragment`:** хранить полный текст фрагмента (нужен для SOURCE route и source fidelity) или официально принять «semantic boundary + location» и изменить схему. Решение меняет TD §4 и §9, поэтому оно за владельцем.
3. **57 Thought:** предоставить дословные Thought — в первую очередь 17 уже «вручную верифицированных» и 11 бывших unresolved. Иначе решить, допустим ли Fragment без Thought в retrieval: MEANING representation строится на `thought`.
4. **Operation-слой для 11 карточек:** выполнить разметку `philosophical_operation` и `question_structures` редакторски (словарь v0.1) и утвердить её.
5. **Шаблонный интерпретационный слой 95 карточек:** считать его утверждённым или сначала переписать `perspective`, `commentary` и `coordinates`. Отдельно — можно ли использовать `perspective` из реестра 1090.
6. **Translation и copyright:** утвердить переводы для 21 карточки с плейсхолдером (Тора, Евангелия, Иов/Экклезиаст, сутты) и закрыть `copyright_status = check_per_approved_source_registry` у всех 95.
7. **Флаги `source_verified: false`** у 29 карточек: обновить в данных под решение «124 verified» или оставить как историю.
8. **Атрибуции:** подтвердить исправление C0246 на SN 36.6; разрешить locations C0703–C0707 и C0712.
9. **Мелкие:** нужен ли `author`, если в карточках он везде null; семантика `open / context-dependent`; статус reserve у C0969.

Пока открыты пункты 1–4, валидатор блокирует index build. Это ожидаемое поведение по D49.

---

## Что сделано в Milestone 1 (и чего нет)

- Сделано: Pydantic-схемы, импортёр из документов (с provenance по полям и запретом тихой перезаписи canonical-файла), валидатор, CLI `navigator import-corpus` и `navigator validate-corpus`, 45 тестов (все проходят).
- **Не** реализованы embeddings, recall, LLM, API и UI.
