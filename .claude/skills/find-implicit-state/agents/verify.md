# Scout brief — verify one implicit-state candidate

This file is a **prompt template** the orchestrator expands and sends
to a sub-agent. Placeholders are double-brace `{{name}}`. The
orchestrator fills them in and calls
`Agent(subagent_type="general-purpose", prompt=<expanded>)`.

Fresh sub-agent, no prior context. Everything the scout needs is
either inline below or in the two knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are verifying **one** implicit-state candidate (stringly-typed
state or tuple-inferred identity) in this Django codebase.
Your job is to bucket it correctly and write a single JSON file. You
are **not** editing or proposing a refactor.

### Candidate to verify

```json
{{candidate_json}}
```

Project root (absolute): `{{project_root}}`
Write your output here: `{{output_path}}`

### Knowledge you MUST consult

Read in this order:

1. `{{skill_root}}/knowledge/` (host-project overlay) — known state fields,
   where tuple-identity hides, noqa conventions, detection gaps.
2. `{{skill_root}}/knowledge/verification.md` — the two sub-patterns,
   bucket definitions, verification checklist, output schema.

### Verification procedure (follow in order)

Apply the checklist from `verification.md`. Short version:

1. **Read the enclosing function.** Open the candidate's `file` and
   read the enclosing `FunctionDef`/`AsyncFunctionDef`/`ClassDef` —
   the `symbols` list on the candidate tells you where to look.
2. **Check for the noqa marker.** Grep the flagged lines for
   `# noqa: stringly-status:`. Non-empty reason → bucket as
   `legacy_allow_list`.
3. **For sub-pattern A hits** (`stringly_compare`, `stringly_field`,
   `possible_state_literal`): check whether the model has a
   `TextChoices` subclass AND the compared value is a bare literal,
   not an enum member. Enum-member-via-variable → `enum_already_used`.
   Otherwise → `extract_enum_candidate`.
4. **For sub-pattern B hits** (`tuple_identity`): read the next ~15
   lines after the `.filter(...)/.first()` assignment to confirm
   identity usage vs freshness check. Identity usage →
   `introduce_fk_candidate`. Freshness usage → `enum_already_used`
   with `false_positive_reason: "freshness_not_identity"`.
5. **Write the JSON output.** One file at `{{output_path}}` matching
   the schema in `verification.md`.

### Rules you MUST respect

1. **Default conservatively.** When the enclosing-function reading
   doesn't clearly confirm identity usage, the tuple-identity hit is
   NOT `introduce_fk_candidate`. Bucket as `enum_already_used` with
   `false_positive_reason: "freshness_not_identity"`.
2. **Respect the allow-list.** `# noqa: stringly-status:` with a
   non-empty reason → always `legacy_allow_list`, never an action
   recommendation.
3. **Keep `notes` tight** — 1 to 3 sentences. The hit records carry
   the detail.
4. **Never propose the refactor.** `/extract-enum` and `/introduce-fk`
   own proposal writing. Your job is to bucket.

### Output contract

Write a single JSON file at `{{output_path}}` matching the schema in
`verification.md` ("Output schema" section). Summary:

```json
{
  "candidate_id": "{{candidate_id}}",
  "file": "<file>",
  "pattern": "<pattern>",
  "bucket": "extract_enum_candidate | introduce_fk_candidate | enum_already_used | legacy_allow_list",
  "confidence": "<high|medium|low>",
  "hit_count": <int>,
  "fields_touched": [...],
  "symbols": [...],
  "recommendation_hint_symbol": "<preferred symbol for the recommendation>",
  "notes": "1-3 sentence scout summary",
  "false_positive_reason": "<enum from verification.md or null>"
}
```

### Bucket → recommendation cheat-sheet

| Bucket | Recommendation |
|---|---|
| extract_enum_candidate | `/extract-enum <symbol>` |
| introduce_fk_candidate | `/introduce-fk <symbol>` |
| enum_already_used | drop |
| legacy_allow_list | leave |

Do not print the JSON to your reply. Write it to `{{output_path}}` and
respond with at most two sentences confirming you wrote the file (and
one sentence flagging anything surprising the orchestrator should
know).
