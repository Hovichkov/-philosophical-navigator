# HANDOFF — FINAL CORPUS → CLAUDE CODE
Дата: 2026-10-07

Корпусная фаза Philosophical Navigator закрыта в согласованном scope.

## Передать Claude Code
Положить содержимое этого пакета в репозиторий проекта, например `corpus/final-2026-10-07/`.
Runtime должен читать только `FINAL-CORPUS-ACTIVE-v1.csv` (967 строк).

## Что уже решено и не обсуждается при импорте
- Master = 1 140 исторических candidate ID.
- Final evidence registry = 970 строк.
- Runtime active corpus = 967 строк.
- Presocratics/Lebedev = 75/75.
- Upanishads/Syrkin = 95/95.
- Quran canonical-ID repair выполнен.
- Plato final scope = Apology 11 + Euthyphro 2 + Protagoras 2 + Meno 4.
- Crito удалён.
- C0293/C0351 не восстанавливать искусственно.
- C0364/C0365 не активировать.

## Первый технический шаг Claude Code
Сделать импортёр/валидатор `FINAL-CORPUS-ACTIVE-v1.csv`, который падает с ошибкой при duplicate ID, пустой quote/philosophical_move или запрещённом verification_status. После этого прогнать существующие retrieval/card tests на новом corpus snapshot. Никакого автоматического «дозаполнения» отсутствующих master ID.

## Не делать
Не брать `master-registry` как runtime источник; это candidate registry.
Не смешивать excluded/unresolved строки с активным retrieval.
Не менять цитаты ради стилистического единообразия.
