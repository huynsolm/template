# M2 implementation ledger

Spec: CODEX_TASK_M2.md, AGENTS.md; task order follows spec 0–10.

- [x] 0 M1 font deduplication and browser resolution; rerun M1 and portable comparison.
- [x] 1 ProductFacts models and original fictional sample.
- [x] 2 CopyDraft: strict copy-only schema with fact_ids at every copy unit.
- [x] 3 Versioned prompts with schema and filled example; repairs and locks.
- [x] 4 Unambiguous JSON extraction and bounded preserved attempts.
- [x] 5 Evidence review and deterministic assembly validated by M1.
- [x] 6 New-job regeneration with locked sections preserved exactly.
- [x] 7 Paste/CLI providers, help-verified defaults, fake-process tests.
- [x] 8 Backwards-compatible M1 command and M2 subcommands.
- [x] 9 M1+M2 tests including actual Chromium and fake CLI only.
- [x] 10 Nondeveloper README, background decision, samples, final review, push.

Interfaces: ProductFacts; CopyDraft; make_prompt(facts, locked=None); extract_json(answer); assemble(facts, copy, locked=None) -> (Document, review list); create_job(...), ingest_job(...), regenerate_job(...), generate_job(...). Provider.generate(prompt_text)->answer_text.

Rulings: spec facts contain free text rather than label/value pairs, so spec table uses fact.id as label and fact.text verbatim as value. Empty fact_ids permitted but flagged for manual review. Unknown fact IDs are review items, never schema errors. No model copy truncation. Regeneration child jobs snapshot image files; locks are captured from previous draft.json using edits.json IDs, with unknown lock IDs rejected. Prompt regeneration still requests complete CopyDraft; locked units are reference-only and overwritten by original locked Document sections during assembly. Missing CLI help means no guessed default command: explicit user configuration required for unverified providers.

Size before: tracked path bytes 39,501,951; expected font 19,484,784 bytes. Git blob objects deduplicate identical fonts; historical Git size is not reduced by deleting one path.

Review findings: repeated-generation locks now persist via edits.json; manually replaced locked images are validated and copied preserving relative paths; API-auth env fails closed before CLI launch. All fixes have reproducing regression tests.

Final verification: 109 passed, 0 failed, 0 skipped (M1 48, M2 workflow 28, fake providers 33). Sample outputs/m2/job-iu7kao09 ingested fixed samples/answer.txt and rendered actual Chromium JPG. Scoped reviewer confirmed both important fixes. Official CLI generation not executed; codex help/version and ChatGPT login status only.
