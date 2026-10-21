# Baseline for source applicability work — 2026-10-22

Current local MVP changes have been copied explicitly into this branch. No historical file deletions, private session traces, model caches, or unrelated website work are included.

Included: October 20 language policy shared by interpreter/writer; chosen UI with embedded licensed fonts and light/dark preference; October 21 temporary Epictetus+Epicurus exclusion before final-corpus retrieval. Source corpus unchanged: 967 originals, 735 searchable by MVP default. Explicit --exclude-author none is a diagnostic comparison mode.

Existing verification: 79 relevant tests passed on October 21; theme browser checks covered 1280x900, 1280x720, 390x844, 320x700, preserved state and failure/retry. Do not regenerate the old baseline merely to rediscover it. No claim that source applicability is solved.

Six real stored questions received 12 newly written cards after exclusion. Before: Epictetus/Epicurus 7/12. After: 0/12; Ecclesiastes 4, Gita 3, early Buddhist suttas 3, Laozi 1, Confucius 1. Exact quotations were preserved, but applicability remained weak. Editorial concerns are hypotheses to independently assess against actual corpus text, not preassigned rejection labels:
- C0013 / Gita 4.17 is generic and repeated in unrelated cases.
- C0254: memory of one's past bodily form was applied to bereavement.
- C0634: moral cultivation was mapped to quality of creative work.
- C0246: bodily/mental sensation was mapped to event/interpretation.
- C0599: uncertainty about love/hate in Ecclesiastes was applied to a friend's current motives.
- C0587: mutual help was close to becoming a verdict about financial independence; validator repaired a false attribution.

The career case using C0590 and C0066 was the strongest editorial example and should not be lost by overstrict filtering. Different names do not prove different useful perspectives. Relevant original user records are provided privately in Claude, not in this public repository. Do not commit private prompts, stories, or full model traces. Public regression fixtures should be newly invented and nonidentifying.

Goal: minimal repair of source-to-question applicability during selection, preserve language/quotes and author exclusion, allow one genuinely relevant card rather than forced count. Do not redesign the UI, rewrite the corpus, rotate authors randomly, add architecture, or bypass grounding validation. Existing show/patron preparation remains paused pending content quality checks.
