# Scout brief — verify one dormant-code candidate

This file is a **prompt template** the orchestrator expands and sends
to a sub-agent. Placeholders are double-brace `{{name}}`. The
orchestrator fills them in and calls
`Agent(subagent_type="general-purpose", prompt=<expanded>)`.

Fresh sub-agent, no prior context. Everything the scout needs is
either inline below or in three knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are verifying **one** dormant-code candidate in this Django codebase.
Your job is to decide whether it is truly dormant, and
if so which flavor/bucket. You are **not** deleting or editing code.
You produce a classification JSON file and nothing else.

### Candidate to verify

```json
{{candidate_json}}
```

Project root (absolute): `{{project_root}}`
URL patterns file: `{{url_patterns_path}}`
Write your output here: `{{output_path}}`

### Knowledge you MUST consult

Read in this order:

1. `{{skill_root}}/knowledge/` (host-project overlay) — where to grep, Django
   false positives, dynamic-dispatch patterns, candidate skip list.
2. `{{skill_root}}/knowledge/verification.md` — the four flavors, the
   6-step verification, bucket assignment table, output schema.
3. `{{skill_root}}/knowledge/learnings.md` — the 11 rules from prior
   audits. Read on ambiguity; Rules R3, R4, R8, R10, R11 are the most
   commonly load-bearing.

### Verification procedure (follow in order — do not skip)

Apply 6a → 6f from `verification.md`. Short version:

- **6a. URL check** — grep `{{url_patterns_path}}` for the candidate's
  qualified name or bare name. Record `url_wired`, `url_path`, `url_name`.
- **6b. Template cross-reference** — `git grep` templates for
  `{% url '<url_name>' %}`, `{% include '<template>' %}`, or the view
  class name.
- **6c. JS/static grep** — `git grep` `core/static/`, `static/`,
  `assets/` for hardcoded URL paths, `reverse('<name>')`, axios/fetch.
- **6d. Import / call-site grep** — `git grep -w <name>` across the
  whole repo. Classify hits (definition vs import vs call vs string).
  URL-module-only hits do NOT disqualify; they're evidence of wiring.
- **6e. Admin / management / signal check** — `core/admin.py`,
  `core/management/commands/`, `@receiver(...)` decorators.
- **6f. Git-log recency** — `git log --all -S '<name>' --oneline | head`
  and `git log --all --follow --oneline -- <file>`.

If the candidate's `kind` is `except_handler` (Flavor 3 silent catch):
apply the extra investigation from `verification.md` — read 20 lines
above the `except`, look for the specific smells (undefined model
fields, wrong URL strings, unhandled `DoesNotExist`, silent
`ImportError`, unchecked `.save()`). Skip trivial catches around log
writes or cleanup.

### Rules you MUST respect

1. **Never recommend deletion when uncertain.** If any check returned
   ambiguous evidence (dynamic dispatch hint, `getattr`, registry dict
   membership, unusual decorator), bucket as `false_positive` with a
   `false_positive_reason` that names the mechanism. User can
   override; your default must be conservative.
2. **Flag webhook/partner APIs.** External-API risk is the #1 cause of
   orphan-endpoint false deletions. Set `evidence.external_api_risk:
   true` when the path/name looks webhook-shaped (`/webhook/`,
   `/callback/`, `/api/v1/<partner>/`, `.well-known/`, etc.).
3. **Do not estimate LOC savings.** The report stage adds that.
4. **Keep `notes` tight** — 1 to 3 sentences. The evidence object
   carries the detail.
5. **Use `.venv/bin/python`** for any Django-touching command. For
   pure `git grep` / file reads, plain shell is fine.
6. **Read both the protected block and the enclosing function** when
   classifying a silent catch. A `pass` in isolation is not evidence
   of broken behavior — the pattern above it is.

### Output contract

Write a single JSON file at `{{output_path}}` matching the schema in
`verification.md` ("Output schema" section). Summary:

```json
{
  "candidate_id": "{{candidate_id}}",
  "name": "<bare>",
  "qualified_name": "<Class.method or module.function>",
  "file": "<file>",
  "line": <int>,
  "kind": "function | method | class | except_handler",
  "flavor": "1 | 2 | 3 | 4",
  "bucket": "certain_delete | orphan_endpoint | quasi_dead_broken | false_positive",
  "source": "vulture | unreferenced | silent_catches",
  "evidence": {
    "url_wired": <bool>,
    "url_path": "<path or null>",
    "url_name": "<name or null>",
    "template_hits": <int>,
    "js_hits": <int>,
    "import_sites": [],
    "call_sites": [],
    "admin_refs": <int>,
    "command_refs": <int>,
    "signal_refs": <int>,
    "git_last_touched": "<sha date author> or null",
    "git_only_rename_commits": <bool>,
    "external_api_risk": <bool>
  },
  "false_positive_reason": "<enum from verification.md or null>",
  "notes": "1-3 sentence scout summary",
  "recommendation": "delete | fix | document | none"
}
```

The `source` field comes from the input candidate's `sources[0]`; if
the candidate has multiple sources (e.g. `["vulture", "unreferenced"]`)
pick whichever first surfaced the issue — they describe the same
underlying def.

### Flavor → bucket → recommendation cheat-sheet

| Flavor | Bucket | Recommendation |
|---|---|---|
| 1 (literal-dead) | certain_delete | delete |
| 2 (orphan endpoint, not webhook-shaped) | orphan_endpoint | delete |
| 2 (orphan endpoint, webhook-shaped) | orphan_endpoint | document |
| 3 (silently broken) | quasi_dead_broken | fix |
| 4 (orphan entry + live internals) | orphan_endpoint | delete (entry only) |
| Dynamic dispatch detected | false_positive | none |

Do not print the JSON to your reply. Write it to `{{output_path}}` and
respond with at most two sentences confirming you wrote the file (and,
if relevant, one sentence flagging anything surprising the orchestrator
should know).
