# /map-subsystem — output format

Every `.claude/docs/subsystems/<name>.md` follows the same shape so a
reader can scan it without the skill loaded. `scripts/render_doc.py`
produces this layout from the Stage 1–5 scratch files; this doc is the
canonical reference for what it emits.

## Front matter

A short YAML block + one-paragraph header. Do NOT include the skill
name or invocation — the doc is for a human reader who doesn't care
how it was produced.

```markdown
---
subsystem: views-crawling
target: core/views/crawling.py
regenerated: 2026-04-19T22:30:00Z
prior_run: 2026-03-22T14:10:00Z
files: 1
public_symbols: 14
clusters: 3
compliance_violations: 4
---

# views-crawling

Single-file view module covering crawl-job lifecycle endpoints. Part
of the `core/views/` package; inbound callers are the URL router and
four JS bundles under `static/bundles/`.
```

If this is the first run, omit `prior_run`. If `--refresh` was used,
include it and follow the header with the **Diff since last run**
section (below).

## Section order

1. Front matter + header paragraph.
2. **Diff since last run** (only on `--refresh`).
3. **Files** — table.
4. **Public surface** — grouped by file.
5. **Responsibility clusters** — table.
6. **Dependency graph** — two lists (internal, external) + inbound.
7. **Workflow participation** — links to product workflow maps when the
   scratch data names any.
8. **Convention compliance** — per-rule table.
9. **Open questions** — flagged unexplained regions.
10. **How to regenerate** — single line: the exact command.

Do not add marketing prose, architectural rationale, or "notes on future
work." Those belong in `reports/explanations/<target>.md` (the
`/explain-code` artifact), not here.

## Diff section (refresh only)

```markdown
## Diff since 2026-03-22T14:10:00Z

- **Public symbols added (3):** `CrawlResumeView`, `crawl_job_cancel`,
  `_job_status_json` (promoted from private).
- **Public symbols removed (1):** `legacy_crawl_restart` — deleted in
  `a238b83`.
- **Cluster count:** 4 → 3 (lifecycle + status + admin merged into
  lifecycle).
- **Compliance delta:** `silent-catch` 4 → 0 (fixed in `fffe505`);
  `BLE001` 2 → 2 (unchanged).
- **Inbound callers:** 18 → 19 (one new admin command references
  `bulk_recrawl`).
```

Every bullet answers one question a reader of a stale doc would have:
*what's new*, *what's gone*, *what moved*. No speculation about why —
that's an explanation-skill job.

## Files table

```markdown
## Files

| Path | LOC | Symbols | Public | Last commit | Last author |
|---|--:|--:|--:|---|---|
| core/views/crawling.py | 412 | 22 | 14 | `a238b83` 2026-03-18 | Khurrum Mahmood |
```

One row per file in the subsystem. For a single-file subsystem, one
row; for a directory package, one row per `*.py` file plus a total
row at the bottom.

Columns:

- **Path** — relative to repo root.
- **LOC** — raw line count from `wc -l` (includes blanks/comments —
  don't try to be clever).
- **Symbols** — top-level declarations (functions, classes, module
  vars).
- **Public** — subset of Symbols that pass the public-surface test
  from Stage 2.
- **Last commit / Last author** — from `git log -1 --format=...`.

If chunking was skipped for a file (non-Python, or the chunker
errored), the Symbols/Public cells show `—` and a footnote explains.

## Public surface

Grouped by file. Each file becomes a `###` subsection. Inside, symbols
are listed by kind (class, function, var) with a one-line purpose
lifted from the docstring's first sentence. If there is no docstring,
the line is `(no docstring)` — and the symbol also appears in **Open
questions**.

```markdown
### core/views/crawling.py

**Classes (3):**
- `CrawlJobDispatchView(View)` — POST entry point that validates
  payload and calls `CrawlJobService.dispatch`.
- `CrawlResumeView(View)` — (no docstring)
- `CrawlJobStatusView(View)` — GET JSON status for a running job.

**Functions (11):**
- `bulk_recrawl(request)` — admin bulk action; dispatches N resume
  tasks via `TaskDispatchService.safe_dispatch`.
- `_job_status_json(job)` — shared formatter used by status view +
  admin.
- … (8 more)

**Module vars (0):**
```

"No docstring" is a **finding**, not a bug. The map records it;
`/explain-code` reads the record and decides whether to write an
explanation.

## Responsibility clusters

One row per cluster from Stage 3. The SRP "and"-count gets its own
column so a reader can see the omnibus signal without re-reading the
cluster names.

```markdown
## Responsibility clusters

| Cluster | Symbols | LOC | Domain hint |
|---|--:|--:|---|
| lifecycle | 6 | 180 | dispatch / resume / cancel |
| status | 4 | 95 | JSON + HTML status renderers |
| admin | 4 | 137 | bulk recrawl, force-stop, audit-log |

**SRP sentence:** "This file handles crawl-job lifecycle **and**
status rendering **and** admin bulk actions." → 2 `and`s.
```

If the SRP count is 3+, add a one-liner after the table: `→
omnibus candidate (see .claude/docs/architectural-smells.md smell 1).
Run /find-omnibus for triage, or decompose directly via
/refactor-subsystem driven by a spec in ai-docs/specs/`. No other
interpretation — MAP points at the smell catalog and the next skill
in the loop; it does not pre-empt SUSPECT triage.

## Dependency graph

Two top-level lists plus inbound. No ASCII graph drawings — they rot.

```markdown
## Dependency graph

**Internal imports (8):**
- `core.models` → `CrawlJob`, `SiteConfig`, `Site`
- `core.services.crawl_job_service` → `CrawlJobService`
- `core.services.task_dispatch_service` → `TaskDispatchService`
- `core.input_utils` → `safe_int`
- `core.views._common` → `json_response`, `require_login`
- … (3 more)

**External imports (4):**
- `django.views.View`
- `django.http.JsonResponse`
- `django.shortcuts.get_object_or_404`
- `logging` (stdlib)

**Inbound (19 files, truncated at 200):**
- `core/urls.py` (URL routing)
- `core/admin.py` (bulk_recrawl action)
- `core/tasks/crawling.py` (shared formatter reuse)
- `static/bundles/crawl-dashboard.js` (fetch URL reference — grep'd, not AST)
- … (15 more — see `reports/map/<name>/latest/deps.json` for the full list)
```

Link the first column of inbound to the calling subsystem's map page
when one exists (`[core/urls.py](urls.md)`-style). If no map page,
leave the path plain.

## Workflow participation

Optional. Render only when Stage 4 wrote `workflows.json` in the scratch
directory.

```markdown
## Workflow participation

- [crawl-dashboard](../workflows/crawl-dashboard.md) — owns status JSON
  read path and dashboard template include.
```

If no workflow map names this subsystem, omit the section entirely.

## Convention compliance

One row per rule from Stage 5. Raw counts only. Never sum across
rules — the sum is meaningless.

```markdown
## Convention compliance

| Rule | Source | Count | Action |
|---|---|--:|---|
| F401 (unused-import) | ruff | 1 | `/fix-workflow` quick-fix |
| E501 (line-too-long) | ruff | 3 | informational — narrow fix opportunistically |
| B008 (function-call-in-default-argument) | ruff | 0 | — |
| BLE001 (blind-except) | ruff | 2 | review — may be legitimate with logging |
| silent-catch | scripts/lint/silent_catch.py | 0 | — |

**Total violations:** 6 across 3 rules. Run `.venv/bin/ruff check
core/views/crawling.py` for line-level detail.
```

The "Action" column is a hint, not a decision. `—` for zero-count rows.

## Open questions

Auto-generated from:

- Public symbols with no docstring AND LOC > 20.
- Functions whose cyclomatic complexity (approximated via branch count)
  exceeds 12.
- Classes that expose 5+ public methods without a class-level
  docstring.

```markdown
## Open questions

- `CrawlResumeView` (16 LOC, 2 methods) — no class docstring; caller
  contract unclear.
- `_job_status_json` (44 LOC, 11 branches) — high branch count, no
  docstring. Candidate for `/explain-code`.
- `bulk_recrawl` (61 LOC, 8 branches, 3 DB writes) — likely layer
  violation. Flag as a `fat-view` candidate
  (`scripts/lint/no_fat_view.py`) and review against
  `.claude/docs/architectural-smells.md` smell 4.
```

Non-empty "Open questions" section → hints live inline in the doc.
The Stage 8 summary can point at the next skill in the loop (e.g.,
`/explain-code`, `/find-layer-violation`) when one clearly fits;
otherwise the map is the artifact. Zero items → omit the section
entirely.

## How to regenerate

```markdown
## How to regenerate

```bash
/map-subsystem views-crawling --refresh
```
```

Literal single-line code block. Nothing else.

## Worked example

A complete rendered doc for a small single-file subsystem — treat as
the canonical output shape.

```markdown
---
subsystem: input-utils
target: core/input_utils.py
regenerated: 2026-04-19T22:30:00Z
files: 1
public_symbols: 3
clusters: 1
compliance_violations: 0
---

# input-utils

Single-file helpers for parsing untrusted request data. Called from
every view that accepts user input.

## Files

| Path | LOC | Symbols | Public | Last commit | Last author |
|---|--:|--:|--:|---|---|
| core/input_utils.py | 62 | 4 | 3 | `1046ef4` 2026-04-02 | Khurrum Mahmood |

## Public surface

### core/input_utils.py

**Functions (3):**
- `safe_int(value, default, min_val, max_val)` — clamp user int input
  to an optional range; fall back to `default` on parse failure.
- `safe_str(value, default, max_len)` — coerce to string with length
  cap.
- `parse_json_body(request)` — decode JSON body with a typed error
  response on failure.

**Module vars (0):**

## Responsibility clusters

| Cluster | Symbols | LOC | Domain hint |
|---|--:|--:|---|
| input-parsing | 3 | 62 | safe coercion helpers |

**SRP sentence:** "This file handles user-input coercion." → 0 `and`s.

## Dependency graph

**Internal imports (0):**

**External imports (2):**
- `json` (stdlib)
- `django.http.JsonResponse`

**Inbound (34 files, truncated at 200):**
- `core/views/crawling.py`
- `core/views/field_config.py`
- … (32 more — see `reports/map/input-utils/latest/deps.json`)

## Convention compliance

| Rule | Source | Count | Action |
|---|---|--:|---|
| F401 (unused-import) | ruff | 0 | — |
| E501 (line-too-long) | ruff | 0 | — |
| B008 (function-call-in-default-argument) | ruff | 0 | — |
| BLE001 (blind-except) | ruff | 0 | — |
| silent-catch | scripts/lint/silent_catch.py | 0 | — |

**Total violations:** 0.

## How to regenerate

```bash
/map-subsystem input-utils --refresh
```
```

## Rendering rules

- UTC timestamps in front matter. `YYYY-MM-DDTHH:MM:SSZ` exactly.
- Tables use right-alignment (`--:`) on numeric columns.
- Never inline code from the subsystem into the doc — link to file:line
  if a reader needs the actual code. The map is a pointer, not a copy.
- If any section would be empty AND the scan ran without error, omit
  the section header entirely. Empty sections are noise.
- If a section failed to generate (e.g. ruff exited non-zero), include
  the header with a one-line error: `**Error:** ruff exited 2; re-run
  .venv/bin/ruff check core/views/crawling.py for detail.`
