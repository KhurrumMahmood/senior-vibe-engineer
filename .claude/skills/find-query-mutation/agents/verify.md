# Scout brief — verify one query-mutation candidate

This file is a **prompt template** the orchestrator expands and sends
to a sub-agent. Placeholders are double-brace `{{name}}`. The
orchestrator fills them in and calls
`Agent(subagent_type="general-purpose", prompt=<expanded>)`.

Fresh sub-agent, no prior context. Everything the scout needs is
either inline below or in the two knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are verifying **one** query-mutation candidate (a read-named
function — `get_*`, `fetch_*`, `load_*`, `list_*`, `find_*`,
`check_*` — that contains a mutation call in its body) in this Django
codebase. Your job is to bucket it correctly and write
a single JSON file. You are **not** editing or proposing a refactor.

### Candidate to verify

```json
{{candidate_json}}
```

Project root (absolute): `{{project_root}}`
Write your output here: `{{output_path}}`

### Knowledge you MUST consult

Read in this order:

1. `{{skill_root}}/knowledge/` (host-project overlay) — the three receiver
   false-positive shapes (dict.update, set.update, CBV context),
   known legitimate cache-warming sites, `# hidden-mutation:`
   convention, detection gaps.
2. `{{skill_root}}/knowledge/verification.md` — the smell, the four
   buckets, the verification checklist, the output schema.

### Verification procedure (follow in order)

Apply the checklist from `verification.md`. Short version:

1. **Read the enclosing function.** Open the candidate's `file` and
   read the `def <symbol>(...)` block starting at `func_lineno`,
   through to its block end.
2. **Resolve the receiver of every mutation call.** For each hit in
   the candidate's `hits` list, walk backward to find where
   `<receiver>` is bound:
   - `dict()` / `set()` / `{}` / `super().get_context_data(...)` /
     any stdlib container → `false_positive_stdlib_wrapper`.
   - `<Model>.objects.get(...)` / `.filter(...).first()` / `self`
     inside a `models.Model` subclass → genuine instance receiver.
3. **Check for `# hidden-mutation:` markers** the detector may have
   missed on continuation lines. If found, bucket as
   `legitimate_cache_warming` with
   `false_positive_reason: "hidden_mutation_marker_missed"`.
4. **Classify the mutation's role** for genuine receivers:
   - Singleton populator / first-call warmer →
     `legitimate_cache_warming`.
   - Every caller wants the mutation → `rename_to_mutator`.
   - Some callers want a pure read → `split_reader_and_mutator`.
5. **Write the JSON output.** One file at `{{output_path}}` matching
   the schema in `verification.md`.

### Rules you MUST respect

1. **Default conservatively.** When you cannot resolve the receiver
   with confidence, bucket as `rename_to_mutator`. Under-reporting is
   worse than over-reporting — `/fix-workflow` catches genuine false
   positives in code review.
2. **Respect the allow-list.** A `# hidden-mutation: <reason>` marker
   with a non-empty reason → always `legitimate_cache_warming`, never
   a refactor recommendation.
3. **Keep `notes` tight** — 1 to 3 sentences. The hit records carry
   the detail.
4. **Never propose the refactor.** `/fix-workflow cluster:<symbol>`
   owns the rename / split proposal. Your job is to bucket.

### Output contract

Write a single JSON file at `{{output_path}}` matching the schema in
`verification.md` ("Output schema" section). Summary:

```json
{
  "candidate_id": "{{candidate_id}}",
  "file": "<file>",
  "symbol": "<symbol>",
  "func_lineno": <int>,
  "bucket": "rename_to_mutator | split_reader_and_mutator | legitimate_cache_warming | false_positive_stdlib_wrapper",
  "confidence": "<high|medium|low>",
  "hit_count": <int>,
  "mutation_methods": [...],
  "recommendation_hint_symbol": "<preferred symbol for the recommendation>",
  "notes": "1-3 sentence scout summary",
  "false_positive_reason": "<enum from verification.md or null>"
}
```

### Bucket → recommendation cheat-sheet

| Bucket | Recommendation |
|---|---|
| rename_to_mutator | `/fix-workflow cluster:<symbol>` — rename |
| split_reader_and_mutator | `/fix-workflow cluster:<symbol>` — split |
| legitimate_cache_warming | add `# hidden-mutation: cache warming` |
| false_positive_stdlib_wrapper | drop |

Do not print the JSON to your reply. Write it to `{{output_path}}` and
respond with at most two sentences confirming you wrote the file (and
one sentence flagging anything surprising the orchestrator should
know).
