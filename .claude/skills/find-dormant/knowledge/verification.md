# Verification procedure + flavor/bucket taxonomy

This file is loaded by **scouts**, not by the orchestrator. It tells a
verifier exactly what to check and how to classify the result.

## The four flavors of dormant

| Flavor | Definition | Deletion risk |
|---|---|---|
| **1. Literal dead** | Zero inbound references anywhere in the repo. | Low. |
| **2. Orphan endpoint** | Wired in `urls.py`/`admin.py` but no UI/JS/test references. May be reachable by direct URL. | Medium — external consumers may exist. |
| **3. Silently broken** | Runs but every path raises a handled exception (hidden inside `except Exception: pass`). "Live" in the linter's eyes. | High — may be load-bearing for untested paths. |
| **4. Orphan entry + live internals** | Entry point is orphan, but downstream tasks/services are still wired. Deletion requires end-to-end call-chain analysis. | Medium-high. |

Flavor 3 is invisible to vulture. Flavor 4 was Cluster 10's trap
(`StartCrawlView → start_crawling_task → scrapers.py` — the triage
flagged the downstream as dead, but only the entry point was).

## The 6-step verification (apply to every candidate)

### 6a. URL-pattern check (FIRST — gates orphan classification)

Read the `url_patterns.jsonl` that the detector wrote. If the candidate's
file:line or qualified name appears in a URL pattern, record:
- `url_wired: true`
- `url_path: "/api/foo/"`
- `url_name: "foo_api"`

If not URL-wired, set `url_wired: false` and skip to 6b.

### 6b. Template cross-reference

`git grep` for:
- `{% url '<url_name>' %}` (if URL-wired)
- `{% include 'template_name.html' %}` (if the candidate is a template)
- Direct reference to the view class name

Record counts. Non-zero → **not dormant**.

### 6c. JS/static grep

`git grep` in `core/static/`, `static/`, `assets/` for:
- Hardcoded URL strings (`"/api/foo/"`)
- `reverse('<url_name>')`
- `axios.get('/foo/')` / `fetch('/foo/')`

Non-zero → **not dormant**.

### 6d. Import/call-site grep

`git grep -w <name>` across the whole repo.

Classify hits:
- **Definition site** (`def <name>` / `class <name>`): expected 1 per def.
- **Import sites** (`from X import <name>`, `import <name>`): record
  files.
- **Call sites** (`<name>(` or `obj.<name>(` or `self.<name>(`): record
  files.
- **String references** (`'<name>'` or `"<name>"`): used by dispatch
  tables, URL names, `getattr` — potentially live.

**Rule:** If any non-definition hit exists **outside** `urls.py`/URL
modules → **not dormant**. If hits are only in URL modules → still
dormant as **orphan endpoint** (bucket 2), pending 6b/6c.

**Caution:** webhook and partner-API endpoints may have zero in-repo
references but be production-critical external APIs. Flag with
`"external_api_risk": true` when bucketing as orphan endpoint.

### 6e. Admin / management-command / signal check

- `core/admin.py`: grep for the name or its containing class.
- `core/management/commands/`: grep for the name.
- `@receiver(...)` decorators: if the candidate is the receiver, it's
  dispatched by signal — not dormant.

Non-zero → **not dormant**.

### 6f. Git-log recency

```bash
git log --all --follow --oneline -- <file>
git log --all -S '<name>' --oneline
```

Look for:
- **No meaningful edits since file creation** → corroborating evidence.
- **Only formatter/rename commits** → corroborating evidence.
- **Single-author history** → corroborating evidence.

Recency is **never primary evidence**. Stable-and-live code can be
untouched for years. Use it only to strengthen an already-zero-reference
case.

## Flavor 3 (silently broken) — extra investigation

When the detector tagged a candidate from the `silent_catches`
source, read 20 lines above the `except` statement and look for:

- Reference to a model field that doesn't exist on the model (check
  `core/models.py`).
- String-formatted URL paths that could be wrong.
- `Model.objects.get(...)` calls with no explicit `DoesNotExist` handler —
  the generic `except Exception` swallows it.
- `import` calls inside the try block — `ImportError` is silently
  swallowed.
- `.save()` calls whose return value is never checked.

Skip trivial catches around log writes or cleanup. Focus on high-value
surfaces: export paths, pricing calculations, authentication, data
mutations.

## Bucket assignment (after 6a-6f)

| Bucket | Criteria | Recommendation |
|---|---|---|
| **certain_delete** | All six checks returned zero inbound; git-log corroborates. | Recommend deletion. Still requires user authorization. |
| **orphan_endpoint** | URL-wired, but 6b/6c/6d (outside URLs) all zero. | Recommend deletion **with URL path + name** — user may recognize it as an internal-only API. Flag `external_api_risk: true` if webhook-shaped. |
| **quasi_dead_broken** | Code is called (non-zero 6d) but detector found `silent_catches` and the Flavor-3 investigation found a real smell. | Do NOT recommend deletion. Recommend `/fix-workflow fix:<name>`. |
| **false_positive** | Any dynamic-dispatch evidence: `@receiver`, `.as_view()` URL, template URL name, `getattr`, registry dict membership. | Drop from candidates. Note the reason so future scans can tune detection. |

## Output schema

Write one JSON file per candidate at
`${REPORT_DIR}/scout/<candidate_id>.json`:

```json
{
  "candidate_id": "dormant-0001",
  "name": "<bare name>",
  "qualified_name": "<Class.method or module.function>",
  "file": "core/views_foo.py",
  "line": 42,
  "kind": "function | method | class",
  "flavor": "1 | 2 | 3 | 4",
  "bucket": "certain_delete | orphan_endpoint | quasi_dead_broken | false_positive",
  "source": "vulture | unreferenced | silent_catches",
  "evidence": {
    "url_wired": true,
    "url_path": "/foo/",
    "url_name": "foo",
    "template_hits": 0,
    "js_hits": 0,
    "import_sites": [],
    "call_sites": [],
    "admin_refs": 0,
    "command_refs": 0,
    "signal_refs": 0,
    "git_last_touched": "abc1234 2024-09-14 Alice",
    "git_only_rename_commits": false,
    "external_api_risk": false
  },
  "false_positive_reason": "<if bucket=false_positive, one of: django_handler | cbv_dispatch | as_view_url | template_url_name | signal_receiver | registry_dispatch | template_tag | meta_class | dunder | admin_action | management_handle>",
  "notes": "<1-3 sentence scout summary: what you verified, what caller evidence you found, any caveat>",
  "recommendation": "delete | fix | document | none"
}
```

`false_positive_reason` is `null` when bucket != `false_positive`.

## Rules for your output

1. **Never recommend deletion with `uncertain: true`.** If any check
   returned ambiguous evidence (e.g., a `getattr` hit with a dynamic
   string), bucket as `false_positive` with reason `registry_dispatch`
   or similar, and note what to investigate if the user wants to
   reconsider.
2. **Flag webhook/partner APIs explicitly.** External-API risk is the
   #1 cause of orphan-endpoint false deletions. When in doubt, flag.
3. **Do not estimate LOC savings.** The report stage adds that.
4. **Keep `notes` short.** 1-3 sentences. The evidence object carries
   the detail.
