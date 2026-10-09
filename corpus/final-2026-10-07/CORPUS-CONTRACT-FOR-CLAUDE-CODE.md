# CORPUS CONTRACT FOR CLAUDE CODE

1. Runtime source of truth: `FINAL-CORPUS-ACTIVE-v1.csv`.
2. `card_id` immutable. Never regenerate or renumber IDs.
3. Never silently substitute a quotation, translator, work, location or philosophical_move.
4. Rows marked rejected/ambiguous/unresolved/scope-excluded must not enter retrieval.
5. Preserve Unicode and CSV UTF-8.
6. On import, assert:
   - card_id unique;
   - card_id nonblank;
   - philosophical_move nonblank;
   - quote nonblank;
   - verification_status is not `REJECTED_MOVE_SOURCE_MISMATCH` or `AMBIGUOUS`.
7. Do not infer missing master IDs. The reconciliation file is audit metadata, not a request to generate them.
8. Plato scope is frozen: Apology + Euthyphro + Protagoras + Meno only. Crito is explicitly excluded.
9. C0293/C0351 remain historical gaps. C0364/C0365 remain rejected.
10. Keep the full evidence registry separately from the runtime corpus so provenance is never lost.

## Product caveat
Some older branches were operationally closed before the final source-level re-audit standard was introduced. Historical handoff notes flag source-level caveats for Gospels, Early Pali, Dao, Torah C0948, and Job/Ecclesiastes C0610. Do not rewrite those quotations automatically. If a future strict re-audit is commissioned, treat it as a new corpus version.
