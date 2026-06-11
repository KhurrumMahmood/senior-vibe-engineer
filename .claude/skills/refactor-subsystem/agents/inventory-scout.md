# inventory-scout brief template

Dispatched at Phase 1.3, one sub-agent per chunk, in parallel (one
orchestrator message, N `Agent` tool calls with `subagent_type="Explore"`).

The orchestrator substitutes every `{{placeholder}}` before dispatch. The
template below produces the FULL prompt — do not summarize or elide
sections.

---

## Placeholders

| Placeholder | Source | Example |
|---|---|---|
| `{{file}}` | Chunk map row | `core/tasks.py` |
| `{{line_start}}` | Chunk map row | `1` |
| `{{line_end}}` | Chunk map row | `420` |
| `{{chunk_id}}` | Chunk map row (basename-qualified, R35) | `tasks__C-01` |
| `{{spec_id}}` | Phase 1 argument | `async-tasks` |
| `{{basename}}` | `{{file}}` stem | `tasks` |
| `{{declarations}}` | `scripts/chunk_file.py` output | multiline list of `(line, kind, name, summary)` |
| `{{archaeology_owner}}` | Chunk map row | `scout` or `orchestrator` |
| `{{worktree}}` | `git rev-parse --show-toplevel` | `~/Projects/your-project` |
| `{{venv}}` | `knowledge/` | `.venv/bin/python` (or `$PYTHON_VENV_PATH/bin/python`) |
| `{{branch}}` | `git branch --show-current` | `wip` |

---

## Prompt template

```
You are scouting {{file}} (lines {{line_start}}-{{line_end}}, chunk id {{chunk_id}})
for a refactor driven by spec {{spec_id}}. Your chunk is one of N parallel
scouts; the other chunks are listed in
reports/refactor/{{spec_id}}/inventory/{{basename}}__chunks.md.

Worktree: {{worktree}}
Python:   {{venv}}
Branch:   {{branch}}
Chunk id: {{chunk_id}}  ← use this as your output-file suffix AND as the prefix
                          for every provisional spec-item ID you propose.

Declarations in your chunk (from scripts/chunk_file.py):
{{declarations}}

**Chunk-map descriptions are advisory, not authoritative (R22).** The
per-class summaries above come from docstrings, the first line of the
function body, or an orchestrator-written chunk map. They can be wrong:
a dogfood caught a case where the orchestrator's chunk map said
"ClearUIStateView deletes UI state across many models" when the class
actually returns a hard-coded HTML page whose embedded JS mutates
browser-side localStorage (zero DB writes). **Verify behavior from the
actual code before trusting any summary.** If a summary is wrong, note
the correction in your primary brief under a `## Chunk-map corrections`
heading — the orchestrator reconciles these at Phase 2.2 so Phase 3's
disposition decisions use the true behavior, not the misread name.

Stay strictly within your line range. If a cross-chunk reference comes up
(e.g., a function in your range calls a helper in C-03's range), note it in
your primary brief but do NOT read outside your chunk. The orchestrator
reconciles cross-chunk references at Phase 2.2 consolidation.

Produce THREE outputs, each written to a file (not returned as text):

1. Primary brief — reports/refactor/{{spec_id}}/inventory/{{chunk_id}}__L{{line_start}}-L{{line_end}}.md
   - Top-level symbols in YOUR line range (def / class / constant) with line numbers
   - Public surface: what other modules import from these symbols (grep the repo)
   - Import graph: what this chunk imports (stdlib / third-party / project-local)
   - Decorator usage: @shared_task, @login_required, @cached_property, etc.
   - LOC + complexity hot-spots (functions > 100 LOC, classes > 300 LOC)
   - Cross-chunk references: calls into or out of your range (name + target chunk if known)
   - NO interpretation. Just the shape.

2. Findings — reports/refactor/{{spec_id}}/findings/{{chunk_id}}__L{{line_start}}-L{{line_end}}.md
   - Any P0/P1/P2/P3 findings you notice while reading: half-implemented features,
     silent except blocks, dead branches, TODOs, "XXX" markers, functions that
     reference non-existent fields, any code smell.
   - **Convention violations count as findings.** Read the docs listed in
     `reports/refactor/{{spec_id}}/convention-sources.md` (the orchestrator
     prepared this list from the "Supplementary Documentation" map —
     load only those, not every doc). Extract canonical helpers and rules
     from that narrow set and flag any site in your chunk where the code uses
     a local shadow instead of the canonical (e.g., bare `int(request.POST.get(...))`
     where `safe_int` should be used; `task.delay()` where `safe_dispatch`
     is required; `get_or_create(site=...)` where `ensure_for_site`
     exists). These are P2 findings by default — not P0 unless the violation
     causes an active bug.

   **Finding-or-not decision tree (L-14 — apply in order to every observation):**
     Step 1: Does this require action? No → NOT a finding. Go to step 2.
     Step 2: Does it describe a documented expected behavior (retry shape,
             defensive block with a clear reason)? Yes → **EX candidate** in
             Output 3 Bucket 3. NOT a finding.
     Step 3: Is it just useful context for the orchestrator? Yes → **prose in
             Output 1** (primary brief). NOT a finding.
     Step 4: Does it require cross-module evidence you can't access to classify?
             Yes → **Investigate candidate** in Output 3 Bucket 6. NOT a finding.
             (See Bucket 6 below for narrow Investigate criteria.)
     Step 5: Otherwise → **P-tier finding**. Pick severity.

   ❌ If your recommended disposition is "accept as-is" or "no action needed",
      this is NOT a finding — route it via the tree above instead.

   Schema per entry:
       ## P<0-3>: <title>
       **File:** <path>:<line>
       **Observation:** <what you saw>
       **Convention violated (if any):** <which CLAUDE.md rule / canonical helper>
       **Why it matters:** <consequence if left alone>
       **Recommended disposition:** fix / delete / ledger-monitor
   - Empty file is fine if nothing was noticed.

3. Extracted behaviors — reports/refactor/{{spec_id}}/extracted/{{chunk_id}}__L{{line_start}}-L{{line_end}}.md
   - Behaviors worth preserving but NOT yet in the stub spec.
   - **Also extract conventions and principles**, not just runtime behaviors.
     If the chunk (or a pattern within it) encodes a standard worth documenting
     — a defensive retry shape, a naming rule, a canonical-helper usage, a
     service-layer contract — that is an AR or EX candidate. Conventions are
     the "why the healthy code looks this way" observations.

   **Provisional ID rule (R16).** Every candidate you propose uses a
   **chunk-id prefix**, not a canonical spec-item number:
       ✅ {{chunk_id}}-IM-1, {{chunk_id}}-AR-1, {{chunk_id}}-EX-2, {{chunk_id}}-LR-T-3,
          {{chunk_id}}-REM-1, {{chunk_id}}-INV-1
          (your {{chunk_id}} is already basename-qualified per R35, e.g.
           `tasks__C-01`, so final provisional IDs look like `tasks__C-01-IM-1`)
       ❌ AR-6, EX-3, LR-T-2 ← these collide with other scouts' parallel output
       ❌ C-01-REMOVE-1, C-02-RM-1, C-03-I-1 ← non-canonical short codes
          break Phase 2.2 regex-driven consolidation (R21)
       ❌ C-01-IM-1 (bare, no basename) ← collides with another file's C-01
   The orchestrator reassigns provisional IDs to canonical IDs at Phase 2.2.
   **Canonical six-bucket short codes (R21):** IM, AR, EX, LR-T, REM, INV —
   use these EXACTLY, not your preferred abbreviation. The orchestrator
   consolidation script relies on these being regular expressions like
   `^[a-z0-9_]+__(C-\d+|orphan-\d+)-(IM|AR|EX|LR-T|REM|INV)-\d+$`.

   **Function-purpose summary rule (R16 addendum).** Every extracted entry
   cites file:line AND includes a one-line italic summary pulled from the
   function's docstring (or the first 3 lines of its body if no docstring).
   Format:
       ### {{chunk_id}}-AR-1: <short name>
       **File:** <path>:<line>
       _<one-line purpose summary>_
       **Behavior:** ...
       **Proposed text:** ...
   This lets the orchestrator merge entries by semantic similarity at Phase 2.2.

   Sort each into one of six buckets. The extracted file MUST use these
   exact H2 headers, in this order, even if a bucket is empty (R21):

       ## Bucket 1: IM (implementation candidates)
       ## Bucket 2: AR (architecture rules)
       ## Bucket 3: EX (exceptions / non-obvious rules)
       ## Bucket 4: LR-T (learnings — technical)
       ## Bucket 5: REM (removal candidates)
       ## Bucket 6: INV (investigate)

   Bucket definitions:
       1. **IM** candidate — worth a new IM item in the spec
       2. **AR** candidate — structural constraint worth an AR item (convention
          that the rest of the codebase honors — e.g., "services are static
          methods on a class with no __init__")
       3. **EX** candidate — non-obvious rule worth an EX item (the gotcha a
          newcomer would get wrong — e.g., "use apply_product_url_filter,
          not crawl_url__regex")
       4. **LR-T** candidate — technical lesson (the "why" behind a defensive
          block). If the "why" came from a git commit message (i.e., archaeology),
          add `<!-- archaeology: <hash> -->` inline so Phase 7's crystallization
          can preserve the invariant's origin.
       5. **REM** candidate — code that appears dead. STAYS until Phase 4 sign-off.
       6. **INV** (investigate) — **narrow criterion**: the observation requires
          cross-module evidence your chunk can't access (e.g., "this task writes to
          Site.sitemap_discovery_status but I don't know if the frontend
          reads it"). If you can classify it as an IM/AR/EX/LR-T candidate or a
          P0..P3 finding with the information in your chunk, do THAT instead.
          **INV is NOT a catch-all for ambiguity.**
          ❌ Don't put "max_retries=0 might be wrong" in INV — decide if
            it's an EX candidate (documented choice) or a P2/P3 finding
            (architectural risk). "Might be" is a classification you can make.
          ✅ Put "does the auto-discovery UI poll Site.discovery_progress?"
            in INV — you genuinely cannot decide from your chunk alone.
          Duplicating an item into both INV AND another bucket is prohibited.

   Each entry cites file:line and explains what the behavior is.
   This is the most important output. Be thorough. Do not drop behaviors
   into the primary brief just to keep this file short.

**Archaeology (only if this scout owns archaeology for its range).** If
{{archaeology_owner}} == "scout" (set when the whole file is ≤ 500 LOC
AND ≤ 20 commits — see Phase 1.4), run:
    git log --follow --oneline {{file}} | head -50
    git log --follow -p {{file}} | head -500
and add rationale entries to Output 3 as LR-T candidates. Otherwise skip
archaeology — the orchestrator is handling Phase 1.4 for {{file}} in parallel.

Use only Read, Grep, Glob, Bash. Do not edit anything. Do not produce summaries
beyond the three files above.
```

---

## Completeness contract

A scout output is **complete** only when ALL THREE files exist:

1. `reports/refactor/{{spec_id}}/inventory/{{chunk_id}}__L{{line_start}}-L{{line_end}}.md`
2. `reports/refactor/{{spec_id}}/findings/{{chunk_id}}__L{{line_start}}-L{{line_end}}.md`
3. `reports/refactor/{{spec_id}}/extracted/{{chunk_id}}__L{{line_start}}-L{{line_end}}.md`

Plus (conditional on `{{archaeology_owner}} == "scout"`):

4. Archaeology entries as LR-T candidates in Output 3.

If any required file is missing, the scout output is **incomplete** and
the orchestrator must re-dispatch. Do not proceed to Phase 2 on partial
outputs.

## Phase 1.5 completeness gate

The orchestrator checks the chunk map against the files produced. Every
chunk listed in `{{basename}}__chunks.md` must have all three files.
Orphan chunks (listed but missing files) block Phase 2 dispatch.
