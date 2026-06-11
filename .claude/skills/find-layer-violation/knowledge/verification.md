# Verification procedure + bucket taxonomy for `/find-layer-violation`

This file is loaded by **scouts**, not by the orchestrator. It tells a
verifier exactly how to classify a layer-violation candidate.

## The four buckets

| Bucket | Criteria | Recommendation |
|---|---|---|
| **extract_service** | The function owns business logic with no natural home in an existing service. At least one detector signal is confirmed after reading the code. | Recommend `/fix-workflow layer:<candidate_id>` — extract a new `core/services/<domain>/` method and reduce the view to a thin wrapper. |
| **move_to_existing_service** | The logic is business logic, but a matching service already exists (e.g. `ExternalSourceService`, `CrawlingService`). The view is re-implementing work that belongs in the existing service. | Recommend `/fix-workflow layer:<candidate_id>` — move logic into the named existing service; delete the duplicate from the view. |
| **broad_workflow_coordinator** | The function/class coordinates workflow context, sidebar/dashboard status, template selection, compatibility redirects, or boot payloads while delegating domain behavior elsewhere. | Prefer `/map-product-workflow` and `/extract-workflow-registry`; do not extract another domain service until the topology owner exists. |
| **intentional_http_coupling** | All detector signals are explained by genuine HTTP concerns (proxy setup, gzip, IP lookup, response streaming) — the code has no natural service home. Also covers `already_service_call` (body is mostly trivial request-parsing around a 1-line service call). | Drop — the detector fired but the function is correctly HTTP-coupled. Note the `false_positive_reason` so detection can be tuned. |

## The "is this a layer violation?" rule

Copied from CLAUDE.md View Pattern:

> Views should be thin HTTP wrappers:
> 1. Parse request (get site_id, decode JSON body)
> 2. Load the model (`get_object_or_404`)
> 3. Call service method
> 4. Return `JsonResponse`
>
> Don't extract view logic that is deeply HTTP-coupled (proxy setup,
> gzip decompression, IP location checking). Only extract reusable
> business logic.

### The test-for-layer-violation

1. **Could the function body move into a service method, with the view
   reduced to `result = Service.method(model, payload)` +
   `JsonResponse(result)`?** If yes, layer violation.
2. **Is the function body mostly `request.*`, `response.*`,
   gzip/decompression, proxy wiring, IP lookup, or streaming?** If
   yes, HTTP-coupled — leave it.
3. **Does the function write to 2+ models in one go?** That is almost
   always business logic — it needs `transaction.atomic()` + a service
   home.
4. **Does the function dispatch Celery tasks via bare `.delay()`?**
   Should use `TaskDispatchService.safe_dispatch()` — fix in place or
   behind a service.
5. **Is the function mostly workflow coordination?** If it selects
   templates, assembles sidebar/dashboard context, normalizes active-tab
   state, or redirects compatibility routes while delegating domain
   operations, bucket as `broad_workflow_coordinator`.

## Verification steps (apply in order)

### V1. Read the candidate file

Open `{{project_root}}/<candidate.file>` and read the body of the
flagged symbol end-to-end. Write your own one-sentence summary of the
business logic it owns — do NOT copy the detector evidence.

### V2. Confirm or dismiss each signal

For every signal in `candidate.signals`:

1. Decide whether the signal reflects a genuine smell or is a
   false-positive of that detector's heuristic.
2. If confirmed, capture what the scout learned (e.g. "loops over
   300-LOC body writing 3 models").
3. If dismissed, record the reason (e.g. "fire-and-forget audit log;
   `.delay()` is safe here").

Record as:

```json
"signals_confirmed": ["fat", "multi_model_write"],
"signals_dismissed": [
  {"signal": "dispatch_bypass", "reason": "task-to-task dispatch is intentional"}
]
```

### V3. Identify the domain home

Check `knowledge/` "Canonical services to move logic into":

- If an existing service owns this domain → `move_to_existing_service`.
- Otherwise → `extract_service` (propose a new `core/services/<domain>/`
  directory package).

### V4. Check for known HTTP-coupled shapes

If the body is dominated by HTTP plumbing (see `knowledge/`
"Known NOT-layer-violation shapes"), bucket as
`intentional_http_coupling` with the matching `false_positive_reason`.

### V5. Apply the bucket table

| Signals confirmed | Service home known | Bucket |
|---|---|---|
| 1+ | Existing service matches | `move_to_existing_service` |
| 1+ | No existing match | `extract_service` |
| 1+ | Workflow coordination, not domain logic | `broad_workflow_coordinator` |
| 0 (all dismissed) | — | `intentional_http_coupling` |

### V6. Sketch the extraction (extract_service / move_to_existing_service only)

Propose 1–4 new or moved functions. For each:

```json
[
  {"new_function": "ExternalSourceService.extract_from_url(site, url)",
   "moved_from_lines": "412-530"},
  {"new_function": "ExternalSourceService._normalize_response(raw)",
   "moved_from_lines": "535-555"}
]
```

Keep names action-oriented. The human running `/fix-workflow` will
refine signatures during the Explain / Refactor phases.

Also apply `.claude/skills/_common/interface-depth.md`:

- State what caller knowledge the service would hide.
- Reject sketches that are only pass-through wrappers.
- Do not propose a port/adapter unless the adapter reality test passes.
- Prefer a service interface that durable tests can exercise directly.

## Output schema

Write one JSON file per candidate at
`${REPORT_DIR}/scout/<candidate_id>.json`:

```json
{
  "candidate_id": "layer-0001",
  "file": "core/views/external_source.py",
  "symbol": "ExternalSourceExtractView.post",
  "bucket": "extract_service | move_to_existing_service | broad_workflow_coordinator | intentional_http_coupling",
  "signals_confirmed": ["fat", "multi_model_write"],
  "signals_dismissed": [
    {"signal": "dispatch_bypass", "reason": "fire-and-forget log"}
  ],
  "business_logic_summary": "Runs the ExternalSource extraction pipeline against a single URL and writes the result + parent job rows.",
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

Rules:

1. `extraction_sketch` is `[]` for `intentional_http_coupling` and
   `broad_workflow_coordinator`. For coordinators, use `notes` to point
   at the missing workflow registry/context owner.
2. `false_positive_reason` is `null` unless bucket is
   `intentional_http_coupling`. Allowed values: `http_coupled`,
   `already_service_call`, `trivial_form_save`.
3. `recommendation` matches bucket:
   - `extract_service` → recommend `extract_service`.
   - `move_to_existing_service` → recommend `move_to_existing_service`.
   - `broad_workflow_coordinator` → recommend `map_workflow`.
   - `intentional_http_coupling` → recommend `keep`.
4. `signals_confirmed` + dismissed `signals_dismissed[*].signal` cover
   every signal from the candidate (don't silently drop one).
5. `interface_depth_note` is required for `extract_service` and
   `move_to_existing_service`; set it to `null` for keep decisions.
6. Keep `notes` tight — 1 to 3 sentences. The evidence fields carry
   the detail.

## Do NOT do these

- **Do NOT estimate LOC savings.** The report doesn't need them, and
  scouts regularly over-estimate.
- **Do NOT flag code as layer-violating when the domain is HTTP.**
  Proxy configuration and response decompression are HTTP jobs.
- **Do NOT recommend `extract_service` without naming a concrete
  domain.** "Extract a helper" is not a proposal; "extract
  `ExternalSourceService.extract_from_url()`" is.
- **Do NOT re-read the knowledge files between candidates** — they are
  provided once; use them.
