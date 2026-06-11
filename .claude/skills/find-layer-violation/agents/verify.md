# Scout brief — verify one layer-violation candidate

This file is a **prompt template** the orchestrator expands and sends
to a sub-agent. Placeholders are double-brace `{{name}}`. The
orchestrator fills them in and calls
`Agent(subagent_type="general-purpose", prompt=<expanded>)`.

Fresh sub-agent, no prior context. Everything the scout needs is either
inline below or in the knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are verifying **one** candidate flagged as a possible layer
violation in this Django codebase. The detector has
already matched 1–5 signals against a view method, view function, or
Celery task. Your job is to decide whether the function is owning
business logic that should live in a `core/services/<domain>/` method,
whether it is a broad product-workflow coordinator that needs topology
mapping first, or whether the signals are false positives on
HTTP-coupled code.

You are **not** editing, extracting, or moving code. You produce a
single classification JSON file and nothing else.

### Candidate to verify

```json
{{candidate_json}}
```

Project root (absolute): `{{project_root}}`
Skill root: `{{skill_root}}`
Write your output here: `{{output_path}}`

### Knowledge you MUST consult

Read in this order:

1. `{{skill_root}}/knowledge/` (host-project overlay) — shared conventions
   + layer-violation-specific notes (canonical examples, known
   HTTP-coupled shapes, directory-package precedent, the list of
   existing services to move logic into).
2. `{{skill_root}}/knowledge/verification.md` — bucket definitions,
   signal-by-signal confirmation rules, output schema.
3. `{{skill_root}}/../_common/interface-depth.md` — deletion test,
   caller-knowledge test, test-surface test, and adapter reality test
   for any extraction sketch.

### Verification procedure (follow in order — do not skip)

#### V1. Read the candidate function

Open `{{project_root}}/<candidate.file>` and read the body of
`<candidate.symbol>` end-to-end. The candidate JSON lists `lineno` and
`end_lineno` — use them to find the function. Write your own
one-sentence summary of what business logic (if any) the function
owns. Do NOT copy the detector evidence.

#### V2. Confirm or dismiss each signal

For every signal in `candidate.signals`, decide:

- **Confirmed** — the signal reflects a real smell. Example:
  `multi_model_write` firing on a view that writes `Job` +
  `Result` + `Status` in one go is almost always business logic.
- **Dismissed** — the heuristic fired but the code is fine. Example:
  `dispatch_bypass` firing on a task that dispatches a downstream task
  directly (task-to-task dispatch is sometimes intentional), or
  `direct_llm_call` firing on a view that just renders a chat widget.

Record exactly:

```json
"signals_confirmed": ["fat", "multi_model_write"],
"signals_dismissed": [
  {"signal": "dispatch_bypass", "reason": "task-to-task dispatch, intentional"}
]
```

Every signal in `candidate.signals` must appear in one of the two
lists. Do not silently drop a signal.

After accounting for detector signals, do a quick responsibility-left
scan of the function body. Note if the view/task still owns raw SQL,
direct external API clients, direct import/export construction, direct
model writes, task dispatch, filesystem writes, or cross-model
transaction policy. These may justify `extract_service` even when LOC
is not extreme.

#### V3. Identify the domain home

Consult the **"Canonical services to move logic into"** table in
`knowledge/`:

- If the domain matches an existing service →
  `move_to_existing_service`.
- Otherwise → propose a new `core/services/<new_domain>/` →
  `extract_service`.

If the function is dominated by HTTP plumbing (proxy setup, gzip,
response streaming, IP lookup) → `intentional_http_coupling` with
`false_positive_reason` naming the shape (allowed values:
`http_coupled`, `already_service_call`, `trivial_form_save`).

If the function is dominated by workflow coordination (template
selection, active-tab/sidebar context, status summaries, compatibility
redirects, or frontend boot payload assembly) and delegates domain
operations elsewhere → `broad_workflow_coordinator`.

#### V4. Bucket the candidate

| Signals confirmed | Service home | Bucket |
|---|---|---|
| 1+ | Existing service matches (named in `knowledge/`) | `move_to_existing_service` |
| 1+ | No existing match | `extract_service` |
| 1+ | Workflow coordination, not domain logic | `broad_workflow_coordinator` |
| 0 (all dismissed) | — | `intentional_http_coupling` |

#### V5. Sketch the extraction (extract_service / move_to_existing_service only)

Propose 1–4 new or moved functions. For each, list the new function
name (including the target service class / module) and the approximate
source line range. Don't be exhaustive about helper extraction — focus
on the main business-logic block.

```json
[
  {"new_function": "ExternalSourceService.extract_from_url(site, url)",
   "moved_from_lines": "412-530"},
  {"new_function": "ExternalSourceService._normalize_response(raw)",
   "moved_from_lines": "535-555"}
]
```

This is a sketch for the human running `/fix-workflow` to refine.

Then write `interface_depth_note`: one sentence explaining why the
deletion test passes and what caller knowledge the service would hide.
If the candidate is `intentional_http_coupling` or
`broad_workflow_coordinator`, set
`interface_depth_note` to `null`.

### Rules you MUST respect

1. **Read the function before classifying.** The detector heuristics
   can over-fire (`fat` measures LOC only; `multi_model_write` counts
   distinct model names without knowing transaction boundaries). Your
   verdict must come from reading the actual code.
2. **HTTP-coupled logic stays in the view.** Proxy wiring, gzip
   decompression, response streaming, IP-location lookup are all
   intentional per CLAUDE.md View Pattern. Bucket these as
   `intentional_http_coupling`.
2a. **HTTP ownership is not service debt.** `FileResponse`, Range
   behavior, request parsing, redirects, template selection, and
   status-code shaping can stay in the view. Move the business/resource
   policy behind a service, not the HTTP ceremony.
3. **Prefer `move_to_existing_service` when a service exists.**
   Creating yet another service when `ExternalSourceService` /
   `CrawlingService` already own the domain is churn, not cleanup.
4. **Do not estimate LOC savings.** The report doesn't need it and
   scouts regularly over-estimate.
5. **Every candidate signal must be accounted for.** The union of
   `signals_confirmed` and `signals_dismissed[*].signal` must equal
   `candidate.signals`. No silent drops.
6. **Keep `notes` tight** — 1 to 3 sentences. Evidence fields carry
   the detail.

### Output contract

Write a single JSON file at `{{output_path}}` matching the schema in
`verification.md`:

```json
{
  "candidate_id": "{{candidate_id}}",
  "file": "<candidate file>",
  "symbol": "<candidate symbol>",
  "bucket": "extract_service | move_to_existing_service | broad_workflow_coordinator | intentional_http_coupling",
  "signals_confirmed": ["fat", "multi_model_write"],
  "signals_dismissed": [
    {"signal": "dispatch_bypass", "reason": "fire-and-forget log, safe"}
  ],
  "business_logic_summary": "One sentence naming the domain work the function owns.",
  "extraction_sketch": [
    {"new_function": "ExternalSourceService.extract_from_url(...)",
     "moved_from_lines": "412-530"}
  ],
  "interface_depth_note": "Deletion test passes because retry, transaction, and result-shaping policy would otherwise spread across three views.",
  "false_positive_reason": null,
  "notes": "1-3 sentence scout summary",
  "recommendation": "extract_service | move_to_existing_service | map_workflow | keep"
}
```

`extraction_sketch` is `[]` for `intentional_http_coupling` and
`broad_workflow_coordinator`.
`false_positive_reason` is `null` unless the bucket is
`intentional_http_coupling`.
`recommendation` must match the bucket:

- `extract_service` → `extract_service`.
- `move_to_existing_service` → `move_to_existing_service`.
- `broad_workflow_coordinator` → `map_workflow`.
- `intentional_http_coupling` → `keep`.

Do not print the JSON to your reply. Write it to `{{output_path}}` and
respond with at most two sentences confirming you wrote the file (and,
if relevant, one sentence flagging anything surprising the
orchestrator should know).
