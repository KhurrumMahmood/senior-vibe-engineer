# Scout brief — verify one transaction-overreach candidate

This file is a **prompt template** the orchestrator expands and sends
to a sub-agent. Placeholders are double-brace `{{name}}`. The
orchestrator fills them in and calls
`Agent(subagent_type="general-purpose", prompt=<expanded>)`.

Fresh sub-agent, no prior context. Everything the scout needs is
either inline below or in `knowledge/verification.md`.

---

## Prompt template (starts below the `---`)

You are verifying **one** transaction-overreach candidate (a
`with transaction.atomic():` block — or a function decorated with
`@transaction.atomic` — that contains at least one slow-op call in its
body) in this Django codebase. Your job is to bucket it correctly and
write a single JSON file. You are **not** editing or proposing a
refactor.

### Candidate to verify

```json
{{candidate_json}}
```

Project root (absolute): `{{project_root}}`
Write your output here: `{{output_path}}`

### Knowledge you MUST consult

Read in this order:

1. `{{skill_root}}/knowledge/verification.md` — the smell, the five
   buckets, the verification checklist, and the output schema.
2. Any additional `{{skill_root}}/knowledge/*.md` files if the host has
   supplied them. Additional files are optional; if none exist, use only
   `verification.md` and do not invent host conventions.

### Verification procedure (follow in order)

Apply the checklist from `verification.md`. Short version:

1. **Read the enclosing block.** Open the candidate's `file` and read
   from `block_lineno` through `block_endline`. For `block_kind:
   "decorator"`, this is the whole function body; for
   `block_kind: "with"`, this is the `with transaction.atomic():`
   block.
2. **Confirm each slow-op hit is genuinely slow.** Walk each entry in
   `hits`. For `category: http` / `ai` / `cloud` / `subprocess` /
   `sleep`, the call IS slow — proceed. For `category: celery`, check
   whether the dispatch is wrapped in `transaction.on_commit(lambda:
   ...)` (the canonical safe pattern); if so, this hit is a false
   positive (the detector should have caught it but may have missed
   a less common shape). For `category: network_helper`, open the
   helper's definition and confirm whether it does HTTP/AI work
   internally.
3. **Check for `# atomic-overreach:` markers** the detector may have
   missed on continuation lines. If found, bucket as
   `legitimate_long_transaction` with `false_positive_reason:
   "atomic_overreach_marker_missed"`.
4. **Classify the candidate** for genuine overreach:
   - The slow op happens *before* any DB write, or *after* and only
     consumes (not produces) the DB rows → `narrow_transaction`
     (move the slow op outside).
   - The block has DB writes both before and after the slow op, and
     they don't need to be atomic with each other →
     `split_transaction`.
   - The slow op is a side-effect-only call (Celery dispatch, audit
     event, notification) that could run after commit →
     `defer_via_on_commit`.
   - The block must be one atomic transaction AND the slow op
     genuinely belongs inside (rare — e.g. a transactional outbox
     write that includes the payload to send) →
     `legitimate_long_transaction`.
   - The flagged helper does not actually do external I/O →
     `false_positive`.
5. **Write the JSON output.** One file at `{{output_path}}` matching
   the schema in `verification.md`.

### Rules you MUST respect

1. **Default conservatively.** When you cannot resolve whether a
   helper is doing real external work, bucket as `false_positive` and
   note the helper name. Better to under-report than chase ghosts.
   The lint catches direct calls; helpers can be re-evaluated when
   the helper itself gets refactored.
2. **Respect the allow-list.** A `# atomic-overreach: <reason>`
   marker with a non-empty reason → always
   `legitimate_long_transaction`, never a refactor recommendation.
3. **Keep `notes` tight** — 1 to 3 sentences. The hit records carry
   the detail.
4. **Never propose the refactor.** `/fix-workflow cluster:<symbol>`
   owns the narrow / split / defer proposal. Your job is to bucket.
5. **Watch for the row-locking pattern.** A block that opens with
   `<Model>.objects.select_for_update().get(...)` and only mutates
   the locked row + adjacent rows is the canonical "I need atomicity
   for a small critical section" pattern. If the only "slow" hit is
   a Celery dispatch wrapped in `transaction.on_commit`, that's
   `false_positive`.

### Output contract

Write a single JSON file at `{{output_path}}` matching the schema in
`verification.md` ("Output schema" section). Summary:

```json
{
  "candidate_id": "{{candidate_id}}",
  "file": "<file>",
  "enclosing_symbol": "<symbol>",
  "block_kind": "with | decorator",
  "block_lineno": <int>,
  "bucket": "narrow_transaction | split_transaction | defer_via_on_commit | legitimate_long_transaction | false_positive",
  "confidence": "<high|medium|low>",
  "hit_count": <int>,
  "categories": [...],
  "recommendation_hint_symbol": "<preferred symbol for the recommendation>",
  "notes": "1-3 sentence scout summary",
  "false_positive_reason": "<enum from verification.md or null>"
}
```

### Bucket → recommendation cheat-sheet

| Bucket | Recommendation |
|---|---|
| narrow_transaction | `/fix-workflow cluster:<symbol>` — move slow op outside |
| split_transaction | `/fix-workflow cluster:<symbol>` — split into two atomic blocks |
| defer_via_on_commit | `/fix-workflow cluster:<symbol>` — wrap dispatch in `transaction.on_commit(lambda: …)` |
| legitimate_long_transaction | add `# atomic-overreach: <reason>` |
| false_positive | drop |

Do not print the JSON to your reply. Write it to `{{output_path}}` and
respond with at most two sentences confirming you wrote the file (and
one sentence flagging anything surprising the orchestrator should
know).

Your output will be judged only by the file at `{{output_path}}`: it must
be valid JSON, carry exactly one of the five bucket values, preserve the
candidate identity/span, and cite the evidence you actually read in
`notes`. A conversational claim without the JSON file does not count.
