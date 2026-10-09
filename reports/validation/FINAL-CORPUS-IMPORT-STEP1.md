# Final corpus 2026-10-07 — первый технический шаг (импортёр / валидатор)

**Дата:** 2026-10-07. Выполнен первый шаг из `HANDOFF-FINAL-CORPUS-TO-CLAUDE-CODE-2026-10-07.md`:
- импортёр и валидатор `FINAL-CORPUS-ACTIVE-v1.csv`;
- прогон существующих тестов поиска и карточек на новом snapshot.

Runtime **ещё не переключён** на финальный корпус: прототип по-прежнему работает на `data/corpus` (compact).

## 1. Проверка пакета

- Пакет положен в `corpus/final-2026-10-07/` **байт в байт**. Все 10 файлов совпадают с `MANIFEST-SHA256.txt` по sha256 и размеру.
- Независимая проверка инвариантов handoff и contract:
  - ACTIVE 967 строк, 967 уникальных ID, формат `C0000`;
  - EVIDENCE 970;
  - ACTIVE ⊂ EVIDENCE, и строки совпадают полностью;
  - только в EVIDENCE: C0364, C0365 (`REJECTED_MOVE_SOURCE_MISMATCH`) и C0656 (`AMBIGUOUS`);
  - ACTIVE ∩ EXCLUSIONS = ∅;
  - ID с `PRESENT_VERIFIED` в RECONCILIATION = ACTIVE.
- **Платон:** ровно 19 ID — C0837–C0847, C0851–C0852, C0857–C0858, C0859–C0862. Критона C0848–C0850 нет. C0293 и C0351 отсутствуют, C0364 и C0365 не активны.
- Пустых `philosophical_move`, `quote`, `translator`, `work` и `location` нет. Значений с лишними пробелами нет. UTF-8 с BOM.

## 2. Импортёр / валидатор

- `src/navigator/corpus/final_corpus.py` — `load_final_active()` (967 карточек `FinalCard`, значения дословно) и `verify_manifest()`.
- `final_snapshot_fragments()` — адаптер к текущей модели `Fragment`.
- Команда `navigator validate-final-corpus` → `status=PASS manifest=ok active=967 unique_ids=967`.
- **Падает с `FinalCorpusError` (все нарушения сразу) при:**
  - пустом или повторном `card_id`, а также ID не вида `C0000`;
  - пустом `philosophical_move` или `quote`;
  - `verification_status` ∈ {`REJECTED_MOVE_SOURCE_MISMATCH`, `AMBIGUOUS`};
  - активной строке из `EXCLUSIONS-AND-UNRESOLVED-v1.csv`;
  - Платоне вне замороженного scope (в том числе Критон);
  - наличии C0293, C0351, C0364 или C0365;
  - заголовке, отличном от колонок контракта.
- Ничего не дозаполняется и не перенумеровывается. Отсутствующие master ID не выводятся.
- Адаптер берёт только то, что есть в CSV: id, author, work, location; quote → `fragment`; translator; edition_source → `source`; ход мысли.
  - MEANING-вопрос строится из хода мысли по существующему детерминированному шаблону проекта.
  - Традиции, перспективы, координат, напряжений и операции в CSV нет, и они **остаются пустыми**.
- Тесты: `tests/test_final_corpus_import.py` — 20 (каждое нарушение контракта роняет импорт; значения и порядок ID сохраняются; адаптер ничего не заполняет).

## 3. Существующие тесты поиска и карточек на финальном snapshot

Переключатель `tests/corpus_snapshot.py`: по умолчанию compact. `NAVIGATOR_TEST_CORPUS=final` — те же 14 модулей (M2.2–M3.4.2) на 967 карточках.

- По умолчанию: **402 passed**.
- `NAVIGATOR_TEST_CORPUS=final`: **119 failed, 24 errors, 110 passed**. Из них **109** — одна причина, ещё 2 ошибки HTTP 422 почти наверняка по ней же через сервер. Остальные 32 упираются в причины ниже.

### Причина 1 — блокер: защита `UNRESOLVED_IDS`

В коде зашит список 11 ID, которые в 2026-09 не прошли текстуальный проход: C0215, C0230, C0258, C0377, C0396, C0398, C0703–C0707. Движок поиска, модели результатов поиска и композиции, трасса и поток падают, если такой ID попадает в выдачу. **В финальном корпусе все 11 активны и проверены:** `VERIFIED_WEB_LITERAL`, `VERIFIED_CLEAN`, `FIXED_OCR_VERIFIED`. Корпус и старая защита противоречат друг другу.

### Причина 2 — что за блокером (диагностика)

Диагностика `NAVIGATOR_TEST_CORPUS=final-diagnostic` — тот же snapshot без этих 11, только чтобы заглянуть за блокер. Результат: **241 passed, 12 failed**. Весь конвейер карточек M3.x проходит. 12 оставшихся:

| причина | тестов | суть |
|---|---|---|
| зашитые числа старого корпуса (113 / 124) | 5 | ожидания compact-корпуса; не дефект финального |
| в MEANING-документе нет перспективы | 4 | в CSV нет `perspective`; документ = только вопрос из хода мысли |
| STRUCTURE пустой | 2 | в CSV нет координат и напряжений → структурный маршрут ничего не находит |
| инвентарь готовности цитат | 1 | аудит M3.3 построен на старых 113; в финальном корпусе цитаты уже проверены по источникам |

## 4. Решения, которые нужны до переключения runtime

1. **`UNRESOLVED_IDS`.** Рекомендую считать «неразрешёнными» то, что исключено в самом пакете (`EXCLUSIONS-AND-UNRESOLVED-v1.csv`), а для старого корпуса — его статусы. Список из 11 ID для финального корпуса не применять.
2. **Смысловой и структурный слои.** В CSV есть только ход мысли и цитата. Варианты:
   - (а) только ход мысли — так сейчас в snapshot; STRUCTURE не работает;
   - (б) добавить в MEANING дословную цитату — источник теперь есть;
   - (в) подтянуть перспективу и координаты из `CORPUS-FULL-1090` по `card_id` — ход совпадает у 926 из 935 общих ID, но это выход за «единственный источник истины», а у 32 активных ID строки в реестре нет.

   Это вопрос качества поиска: его стоит решать A/B-прогоном, а не в импортёре.
3. **Политика цитат.** Цитаты теперь проверены (`VERIFIED_*`). SOURCE и показ цитат остаются выключенными, пока вы не решите иначе. Аудит готовности цитат нужно переделать под финальный корпус.

## 5. Что изменено

- **Новые:**
  - `corpus/final-2026-10-07/` (пакет);
  - `src/navigator/corpus/final_corpus.py`;
  - `tests/test_final_corpus_import.py`;
  - `tests/corpus_snapshot.py`;
  - этот отчёт.
- **Изменённые:**
  - `src/navigator/models/fragment.py` — статусы `final_2026_10_07` / `final_active`;
  - `src/navigator/corpus/readiness.py` — `final_active` в retrieval universe;
  - `src/navigator/cli.py` — `validate-final-corpus`;
  - фикстуры корпуса в 10 тестовых модулях → `load_test_fragments()`, по умолчанию прежний корпус.
- **Не менялись:** `data/corpus`, `data/corpus-full`, код поиска, Selection, Writer, валидатор, UI, политика цитат и SOURCE.

## 6. Команды

```bash
cd "/Users/hovichkov/Documents/Навигатор по самоанализу" && .venv/bin/navigator validate-final-corpus
```

```bash
cd "/Users/hovichkov/Documents/Навигатор по самоанализу" && NAVIGATOR_TEST_CORPUS=final .venv/bin/python -m pytest -q --tb=line tests/test_m2_2_retrieval.py tests/test_m3_3_1_human_language.py
```
