# Source applicability at selection — 2026-10-22

Base: `codex/mvp-quality-baseline-2026-10-22` @ 6519475. One bounded pass; no live generations were run.

## Error categories found (editorial hypotheses checked against corpus text)
- **Subject substitution.** The source speaks of one thing or one agent (one's own past form; moral cultivation; God's
  love or hate; bodily pain), the application silently swaps in another (another person; quality of a work; a
  specific person's motives; an event). A shared word ("memory", "action", "labour") carried the link.
- **Generic phrase.** A card whose move fits almost any question was reused across unrelated cases without giving a
  distinction specific to the question.
- **Value → verdict.** A value of the source (e.g. togetherness) came close to judging the person's way of life.
- **Padding.** The selection prompt said "2 or 3" while the final schema already allowed 1, inviting a weak second card.
- Strong moves kept subject, agent and sense (wealth vs joy in work; knowing what is enough; action without attachment
  to results) — the rule must not reject them for a different setting.

## Change (minimal)
- Selection prompt `composition-prompt/0.12.0`: applicability is checked by the source's SUBJECT, AGENT and SENSE, not
  by shared words; new considered decisions `subject_shift`, `generic_only`; a source's value is not a verdict; one
  strong card is a full answer on the final corpus; an empty selection is allowed when nothing applies.
- Final selection schema: `minItems` 0, required internal `fit` ("the source is about X of Y; the same in the
  question: Z"); empty `fit` is sent back for repair. Legacy schema/behaviour unchanged.
- The prompt's count is consistent throughout: without `corpus_version` in the package 2 or 3 (legacy, unchanged);
  with it (final corpus) 1, 2 or 3, or none when nothing applies.
- Empty final selection raises `NoApplicablePerspective` (no retry, no extra model call). The API returns
  `no_fit: true` with «Не удалось подобрать подходящую перспективу к этому вопросу…»; the page stays on the result
  screen with the existing «Изменить вопрос» and the other questions from the story (story and feelings kept). Technical
  failures keep the ordinary «Попробовать ещё раз».

## Unchanged
Corpus, embeddings, cache, pool size, author exclusion (735 of 967), verified quotes, language policy, themes, design,
landing, model, writer and independent grounding validator. No author blacklist, no rotation, no new model calls.

## Limits
Tests are contract/structure checks with invented examples; they do not prove the quality of live model choices.
The prompt change needs a separate live run on the stored private cases. The `fit` field is checked only for presence. The no-fit
screen is covered by an HTTP scenario test and page-source checks, not by a browser run.
