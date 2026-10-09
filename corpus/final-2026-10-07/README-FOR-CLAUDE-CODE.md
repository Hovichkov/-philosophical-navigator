# Philosophical Navigator — FINAL CORPUS PACKAGE
Дата: 2026-10-07

## Что использовать Claude Code
**Главный продуктовый файл:** `FINAL-CORPUS-ACTIVE-v1.csv`

В нём **967 активных карточек**. Это единственный файл, из которого приложение должно выбирать карточки.

`FINAL-EVIDENCE-REGISTRY-v1.csv` — полный накопительный evidence registry: **970 строк**. Он содержит также 2 отклонённые строки и 1 ambiguous для сохранения истории аудита. Не использовать его напрямую как runtime corpus.

`RECONCILIATION-1140-FINAL-v1.csv` / `.xlsx` — контроль всех **1 140 master ID**.
`EXCLUSIONS-AND-UNRESOLVED-v1.csv` — всё, что не должно попадать в runtime.
`SOURCE-SUMMARY-FINAL-v1.csv` — сводка по 17 источникам.
`CORPUS-CONTRACT-FOR-CLAUDE-CODE.md` — обязательные правила импорта.

## Финальные числа
- Master IDs: 1 140
- В evidence registry: 970
- Активны для продукта: 967
- Present rejected: 2
- Present ambiguous: 1
- Отсутствуют / исключены из runtime: 173
- Duplicate IDs в evidence: 0

## Платон — окончательный scope
В продукте сохранены только:
- «Апология Сократа» C0837–C0847 — 11;
- «Евтифрон» C0851–C0852 — 2;
- «Протагор» C0857–C0858 — 2;
- «Менон» C0859–C0862 — 4.

«Критон» C0848–C0850 исключён. Остальные платоновские ID не брать.

## Важное различие
«Корпус завершён» означает завершён **согласованный продуктовый scope**. Это не означает, что каждый из 1 140 исходных candidate ID стал активной карточкой. Reconciliation фиксирует причину для каждого ID.

## Исторические инварианты
C0293 и C0351 — исторические gaps.
C0364 и C0365 — `REJECTED_MOVE_SOURCE_MISMATCH`, не активировать.
Ни один `card_id` не перенумеровывать.
