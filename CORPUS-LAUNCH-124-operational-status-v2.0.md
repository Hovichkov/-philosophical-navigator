# CORPUS-LAUNCH-124 --- operational status

**Версия:** 2.0\
**Дата:** 2026-09-27\
**Назначение:** актуальная operational-фиксация статуса launch-корпуса
для retrieval.

## 1. Актуальный статус

-   launch-кандидатов: **124**
-   verified: **113**
-   unresolved: **11**

Unresolved:

-   `C0377`
-   `C0396`
-   `C0398`
-   `C0215`
-   `C0230`
-   `C0258`
-   `C0703`
-   `C0704`
-   `C0705`
-   `C0706`
-   `C0707`

Все unresolved-карточки исключены из пользовательского candidate
universe.

`CORPUS-FULL-1090` остаётся резервом и сейчас не используется.

## 2. Отношение к final textual pass

`CORPUS-LAUNCH-124-v1-final-textual-pass.md` является историческим
отчётом конкретного текстуального прохода. Его раздел
`FINAL TEXTUAL PASS STATUS`, фиксирующий более раннее состояние 96
verified / 28 unresolved, сохраняет историческую ценность и не должен
переписываться задним числом.

Для текущей работы retrieval operational source of truth по статусу
карточек --- этот файл и зафиксированный здесь список 11 unresolved.

Карточка, которая была unresolved в историческом textual-pass, но
отсутствует в нынешнем списке 11 unresolved, считается verified для
operational retrieval.

## 3. Retrieval rule

Перед формированием candidate pool система применяет allowlist:

``` text
all 124 launch candidates
        ↓
exclude current 11 unresolved
        ↓
113 verified candidate universe
```

Unresolved не получают понижающий коэффициент и не остаются «запасными»
кандидатами. Они полностью исключаются до смыслового поиска.

## 4. Связанные источники истины

-   `CORPUS-philosophical-navigator-v0.1.md` --- архитектура Fragment /
    Thought / Commentary / Context и правила source → interpretation.
-   `TAXONOMY-philosophical-navigator-v1.1.md` --- taxonomy, coordinates
    / tensions.
-   `RETRIEVAL-philosophical-navigator-v0.1.md` --- содержательная
    механика выбора итоговых 2--3 Fragment.
