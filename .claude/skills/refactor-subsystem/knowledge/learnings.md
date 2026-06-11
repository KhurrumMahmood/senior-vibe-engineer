# Learnings distilled from prior refactor dogfoods (R1-R43)

This file is loaded by the orchestrator **when stuck on a judgment
call** — not front-to-back on every run. Each rule has provenance
back to the shakedown or dogfood that surfaced it (L-N tags refer to
the original lesson entries from the async-tasks, crawling-views,
and tasks-decomp dogfoods).

SKILL.md body references `(L-N)` are shorthand for these rules. Use
the index at the bottom to resolve a specific L-number.

## R1 — The spec is the plan. The plan is the spec.

Drift between the two is the signal that the refactor went off-rails.
The coverage tool (`scripts/specs.py coverage`) is not optional.

**How to apply:** If `coverage <spec-id>` reports drift at any phase
gate, fix the spec or fix the code before proceeding. Never silence
the check.

## R2 — Three outputs per scout, not one

Findings.md and extracted-behaviors.md are not bonus features. They
are the skill's memory — the only record of why a piece of code
exists once `git blame` is scrambled by the split.

**How to apply:** Re-dispatch any scout that returns only the
primary brief. Missing outputs = silent failure; do not accept
partial returns.

## R3 — Conservative default for unknowns

If a scout returns an "Investigate" entry you can't resolve by
Phase 3, the code **stays**. Deletion of uncertain code is a larger
blast radius than keeping dead code. `/find-dormant` can handle
cleanups later, after the subsystem is back in a known-good state.

**How to apply:** Never demote unknowns to Remove candidates without
explicit human approval at Phase 4.

## R4 — Git archaeology before split

`git log --follow -p` is worth 1000 commits of future confusion.
Capture rationale BEFORE the split destroys blame history, not
after.

**How to apply:** Phase 1.4 is mandatory for files with ≥ 50
commits — at least 3 load-bearing LR-T extractions per file with
`<!-- archaeology: <hash> -->` cross-references.

## R5 — Characterization tests are temporary scaffolding

They exist to make Phase 5 safe. Phase 7 deletes them (or promotes
a few into real tests / LR-T items). Do not treat them as permanent
coverage — they were written against an interface you just changed.

**How to apply:** Mark the test file with `# spec:<id>::characterization`
so future agents know it's transient. Delete at Phase 7 unless a
test encodes durable behavior worth promoting.

## R6 — Batches commit-or-revert atomically

A batch that leaves the repo in a partially-green state is a bug.
Every commit in Phase 5 must pass its test scope independently;
every commit must be individually revertable.

**How to apply:** If Phase 5 Batch N breaks Batch N-1's tests, revert
Batch N and re-plan. Do not accumulate broken state across batches.

## R7 — Two-commit discipline for surfaced bugs

A refactor that "also fixes" a bug is a refactor whose diff will be
unreadable in six months. Fix commits and refactor commits are
separate, always, even when the user approved both in the same
Phase 4 sign-off.

**How to apply:** After a batch lands clean, add a separate fix
commit for any P1 finding bundled with it. Each commit must be
green in isolation.

## R8 — Behavior preservation is a property of the refactor, not the code

If the code is broken on HEAD, the refactor preserves broken behavior
— and flags the bug as a P1 finding for the separate fix commit. The
refactor is not the place to argue about correctness.

**How to apply:** Characterization tests pin current behavior, not
desired behavior. If a characterization test asserts a broken
return, that's correct.

## R9 — Spec-first enforcement means spec markers move BEFORE code moves

Phase 5.1's order is not arbitrary. If the code lands before the
spec is updated, `coverage` flags it as `orphan_refs` and the gate
blocks. The workflow forces the spec to lead.

**How to apply:** Edit the spec (`[ ]` → `[~]`) and add
`# spec:<id>::IM-N` comments in new files BEFORE populating them
with real code.

## R10 — Ledger updates are live state

Don't batch them into Phase 7 as an afterthought. `scripts/ledger.py
update` at the moment the decision is made — during Phase 5 for
monitor findings, during Phase 7 for file status changes.

**How to apply:** The ledger is how the NEXT refactor finds this
work. Update it inline, not as a post-step cleanup.

## R11 — "Looks dead" at Phase 2 is a Remove candidate, not a deletion

Every "remove" is an explicit human choice at Phase 4. This prevents
the cluster 10 failure mode (95% confidence "dead code" that was
actually reachable via dispatch dict).

**How to apply:** Remove candidates are REM entries in the extracted
file. They stay in the code until Phase 4 sign-off approves deletion.

## R12 — The extraction pass is the most expensive step. Budget for it.

For large subsystems, Phase 2.2 takes longer than Phase 5. Rushing
it silently discards load-bearing behavior. A refactor that ends
with "the new file is half the size, and nobody knows why the old
file had the other half" has failed.

**How to apply:** Treat Phase 2.2 as the load-bearing phase. Don't
compress it to make room for Phase 5 speed.

## R13 — Read toward the standard

Conventions live in CLAUDE.md's "Canonical Patterns" section and in
the majority behavior of `core/services/` + `core/input_utils.py`.
When a scout finds a file using a local shadow instead of the
canonical helper, that is a convention violation — a P2 finding,
recorded and surfaced, not silently accepted as "the current
behavior".

**How to apply:** The refactor enforces adopted conventions in
Phase 5.4 via the micro-fix swarm (5.3.5); 45%-compliance "canonical"
helpers mean the spec is lying and the refactor is the place to fix
the lie.

## R14 — Inventory gate is mandatory

Phase 1.1.5 exists because the shakedown found a 40%-incomplete
spec that would have silently orphaned 11 tasks. A spec marked
`status: draft` or containing a "re-scan before committing" note is
a time bomb.

**How to apply:** Run `specs.py inventory-check` before any chunking
decisions. If drift > 10%, update the spec BEFORE dispatching scouts.
The rule is "spec guides the refactor" — which presupposes the spec
is current.

## R15 — Chunk oversized files with a tool, not by eye

Files > 2,000 LOC get chunked via `scripts/chunk_file.py` at
Phase 1.3.0. Single-scout-per-file on a 10K-LOC target produces
shallow output that silently misses half the file.

**How to apply:** Hand-chunking is acceptable only when the tool
errors out on a non-Python file.

## R16 — Provisional spec-item IDs carry chunk prefixes

Parallel scouts cannot coordinate ID assignment without paying either
an orchestrator round-trip or a serial bottleneck. Every extracted
candidate is `<chunk-id>-AR-1` / `<chunk-id>-EX-2` until Phase 2.2
consolidation reassigns to canonical numbers.

**How to apply:** Scout brief must enforce the chunk-prefixed ID
pattern. Collision reconciliation without it is Phase 2.2 wall-clock.

## R17 — Archaeology is mandatory for high-churn files

≥ 50 commits triggers Phase 1.4 as non-optional with ≥ 3 load-bearing
LR-T extractions and `<!-- archaeology: <hash> -->` cross-references
in the final spec. Commit messages on high-churn files encode
invariants that live nowhere else.

**How to apply:** Skipping archaeology on a high-churn file is
indistinguishable from the "discards load-bearing code" failure
mode (R12).

## R18 — Cross-scout dedup before tiering

At Phase 2.3, identical findings from parallel scouts (same file,
same line, same convention) merge into one entry with a
`**Reported by:**` provenance list. Counting a single violation N
times because N scouts overlapped on it inflates compliance metrics
and wastes micro-fix swarm dispatch slots.

**How to apply:** Dedup BEFORE computing violation counts that drive
Phase 5.4 enforcement decisions.

## R19 — Micro-fix swarm for mechanical bulk fixes

5+ instances of the same mechanical fix → parallel sub-agent
dispatch, one per file. Sub-agents edit only — the orchestrator
stages and commits serially after all agents return (parallel
agents share a git index, so concurrent staging causes cross-
contamination).

**How to apply:** Only use when fixes are genuinely mechanical.
Judgment calls go back to the orchestrator as P1 findings.

## R20 — Convention enforcement lives inside the refactor

Phase 5.4 runs `specs.py violations` and either fixes inline (≤ 10
violations per convention) or opens a ledger `split_queued` follow-up
(11+). The refactor that cements an AR item and leaves half the
call sites non-compliant is a refactor that lied about its own scope.

**How to apply:** Enforcement is not scope creep — it's part of what
"the subsystem is done" means.

## R21 — Canonical six-bucket short codes are mandatory (L-23)

The extracted-behaviors file uses `IM, AR, EX, LR-T, REM, INV` as
fixed section headers and provisional ID prefixes — never scout-
invented variants (`REMOVE`, `RM`, `INVESTIGATE`, `I`). Parallel
scouts diverging on abbreviations forces the orchestrator to write
per-scout normalization passes at Phase 2.2.

**How to apply:** The six-bucket vocabulary is part of the scout
contract, not a stylistic preference. Reject scout outputs that
use non-canonical abbreviations.

## R22 — Chunk-map descriptions are advisory, not authoritative (L-24)

The per-class summaries in the chunker's declaration list (or an
orchestrator-annotated chunk map) are derived from docstrings and
first-body-line heuristics. They can be wrong.

**How to apply:** Scouts MUST verify behavior from the actual code
and, when a summary is inaccurate, record the correction in their
primary brief under `## Chunk-map corrections`. Orchestrator
reconciles at Phase 2.2 so Phase 3's disposition decisions use the
true behavior, not the misread name.

## R23 — Dedup audits find dead/broken code at subsystem scale (L-26)

Phase 1 on `core/views_crawling.py` surfaced 6 P0 production bugs
in ~10 minutes of parallel scout work. Cluster 1's "dedup finds
dead code 2x" learning generalizes from individual file refactors
to full-subsystem audits.

**How to apply:** Phase 1 should **expect** to find P0s — they are
not an aberration. Two-commit discipline (R7) absorbs them: separate
commits for each fix, separate from the structural refactor.

## R24 — LOC is a symptom, SOLID violations are the disease

Phase 6.3 uses four quality gates (SRP, DRY, linear flow, size
advisory), not a raw LOC threshold. A 600-LOC file that passes SRP,
DRY, and linear-flow is healthier than a 300-LOC file that fails
SRP.

**How to apply:** The 500-LOC soft limit is a signal to check
cohesion — "check" meaning run the gates, not "split automatically."
Hard ceiling (1000) remains because files above it are practically
unreadable regardless of structure.

## R25 — Decomposition mode for single large files

When `code_roots` names one file ≥ 2,000 LOC with 3+ SRP "and"s, the
skill switches to decomposition mode: Phase 1 adds a SOLID audit
(SKILL.md §1.2.5), Phase 3 organizes by domain→file (SKILL.md §3.2.1),
Phase 5 adds a dedicated caller-update wave (execution-playbook §5.6).

**How to apply:** The 7-phase workflow and safety net are unchanged;
what changes is the analysis lens and plan shape, not the scaffolding.

## R26 — Cross-cutting concerns consolidate as Batch 1

In decomposition mode, shared patterns (task lifecycle decorators,
progress abstractions, proxy setup sequences) consolidate into a
shared module BEFORE domain-split batches run. This prevents N
copies of the same boilerplate from being cloned into N new files.

**How to apply:** The DRY gate (Phase 6.3) would catch this at
verification, but it's far cheaper to prevent it at execution. Phase
5's Batch 1 is the consolidation wave; domain splits come after.

## R27 — Text-hash DRY detection is nearly useless (L-37)

Real code duplication uses different variable names for the same
structural pattern. `scripts/specs.py solid` normalizes `ast.dump()`
output before hashing. Tasks-decomp dogfood: text hashing found
1 group / 2 instances in 10K LOC; AST normalization found 7 groups
/ 17 instances.

**How to apply:** Always use structural comparison; text hashing is
not a useful signal.

## R28 — Three-level SOLID harness validates as designed (L-38)

Level 1 (artifact gate) catches "agent skipped the audit"; Level 2
(automated DRY + size) catches mechanical violations; Level 3 (sub-
agent judgment) catches SRP and linear-flow failures the orchestrator
would rubber-stamp on its own work.

**How to apply:** Two dogfood runs (crawling-views, tasks-decomp)
confirmed all three levels produce actionable results. Do not skip
any level.

## R29 — Directory packages over flat naming for decompositions (L-40)

Prefer `tasks/__init__.py` + `tasks/crawling.py` over
`tasks_crawling.py`. The `__init__.py` is the natural re-export
shim, directory grouping aids navigation, and it matches Django
conventions.

**How to apply:** Match existing flat naming for consistency if the
codebase already uses it (e.g., `views_crawling.py`), but use
directories for new decompositions.

## R30 — `__all__` is mandatory in shared modules (L-42)

Python's `from X import *` silently skips `_prefixed` names. If
`common.py` exports helpers like `_build_data_with_retry` or
constants like `_EXPORT_DB_RETRY_MAX`, they vanish without an
explicit `__all__`. This caused 3 separate `NameError` failures in
the tasks-decomp dogfood.

**How to apply:** Every shared module that contains `_prefixed`
exports needs an explicit `__all__`. The fix takes 30 seconds; the
debugging takes 30 minutes.

## R31 — Mock patching splits into two categories after a decomposition (L-45)

`.delay()` patches work through the shim (they patch the task
object). Synchronous call patches must target the actual domain
module (`core.tasks_export.func`), not the shim (`core.tasks.func`).

**How to apply:** Phase 5.6 must grep for `@patch` references and
classify each one. Standard Python mock rule applies: patch where
it's looked up.

## R32 — `from .common import *` beats auto-import detection (L-41)

Attempting to auto-detect which imports each function needs by
scanning function bodies for model names fails on real code:
substring matching misses indirect usage, hardcoded name guesses
produce `ImportError`, cross-cluster module-level imports create
circular dependencies.

**How to apply:** The robust pattern: put the original file's
entire import block in `common.py` and use `from .common import *`
in every domain module. Simple, zero failures.

## R33 — 2:1 preparation-to-execution ratio is the healthy shape

The tasks-decomp dogfood spent two sessions on preparation (SOLID
audit, characterization tests, cluster mapping, caller inventory,
splitter script) and one session on execution.

**How to apply:** Phases 1-4 feel slow because they don't produce
code changes, but they prevent Phase 5 from becoming whack-a-mole.
Skipping preparation to "save time" costs more time in debugging —
every shortcut in Phase 1 becomes a `NameError` or `ImportError`
in Phase 5.

## R34 — One-shot splitter scripts need hand-finishing

An AST-based script can place 90% of functions correctly, but it
misses code that isn't a `def` statement: module-level reassignments
(`task = shared_task(task)`), constants between functions, and
cross-cluster import statements.

**How to apply:** Plan for 10% manual cleanup after the script runs.
The script is still worth writing because manual splitting of 76
functions is error-prone, but don't trust the output without running
the characterization tests.

## R36 — Pre-dispatch coverage check for micro-fix swarm (L-48)

The Phase 5.3.5 swarm dispatches one sub-agent per file with a
per-file `verification_cmd`. If the `verification_cmd` does not
actually exercise the target file (easy default: views file paired
with a site-capabilities suite that never imports from that view),
the sub-agent's "tests pass" is a false green for the edited code
paths. The orchestrator's final baseline run also passes — because
it runs the same untouching suite — and a regression can land
silently.

**How to apply:** Before dispatch, grep each test module in
`verification_cmd` for an import, `from ... import`, or
`patch("core.<module>")` reference to the target file. If no
reference is found, either swap the suite for one that does touch
the file, write a one-test characterization module, or escalate the
file out of the swarm into a P1 finding.

Never trust "green" from a test suite that has no path into the
edited code.

## R35 — Basename-qualify every chunk ID before dispatch (L-47)

`scripts/chunk_file.py` emits raw chunk IDs (`C-01`, `C-02`,
`orphan-1`) local to the file it chunked. When a refactor spec covers
more than one chunked file, two files can each produce a `C-01`:
scouts write to the same `reports/refactor/<spec>/inventory/C-01__*.md`
path, silently clobbering each other's outputs, and Phase 2.2's
provisional-ID regex `C-\d+-(IM|AR|EX|LR-T|REM|INV)-\d+` matches both
files' candidates as if they were the same chunk.

**How to apply:** Between chunker run and chunk-map write, rewrite
every raw chunk ID to `<basename>__<raw-id>` (e.g., `tasks__C-01`,
`services__orphan-1`). Apply uniformly — even files that skip chunking
get `<basename>__C-01` — so every downstream filename, provisional
item ID, and regex works without a special case. The regex for
provisional IDs becomes
`^[a-z0-9_]+__(C-\d+|orphan-\d+)-(IM|AR|EX|LR-T|REM|INV)-\d+$`.

Never dispatch a scout with a bare `C-01` — the collision is silent,
not an error, and the first completed scout's output survives.

## R37 — Scan the ownership family, not only the retired file

After a split, the old file can be clean while a sibling module, package
member, registered prototype route, template, or JS bundle still owns the
same responsibility. The acceptance check follows the new ownership
boundary.

**How to apply:** For a `site_config.py` split, scan
`core/views/site_config*.py`, `templates/core/site_config*.html`, loaded
`static/js/site-config*.js`, URL registrations, and any new
`core/services/site_*` owner. Report "target clean" separately from
repo-wide legacy findings.

## R38 — Registered prototypes are product surface

A prototype route is not dead because its name says prototype. If it is
registered in URLconf and reachable by users, it participates in the
same contract as the main route and can carry duplicated logic.

**How to apply:** Scope refactor verification from URL registration and
template/JS loading, not from the human-facing page name. Either migrate
the prototype to the canonical owner, quarantine it explicitly, or delete
it through the dormant-code workflow.

## R39 — Endpoint and renderer matrices make view splits safe

View modules are dangerous when they mix authority, credentials,
diagnostics, templates, network calls, persistence, and profile behavior.
The code may not be algorithmically hard; the contract matrix is hard.

**How to apply:** Before splitting a view module, list every endpoint
with auth/staff/public, method, CSRF expectation, side effects, response
shape, and external boundary. Also list parallel presenters of the same
concept (dashboard, polling JSON, sidebar, prototype rows) before
extracting a canonical producer.

## R40 — Service extraction can create a new omnibus

Moving logic out of views is not automatically healthy. A service that
absorbs dashboard, polling, sidebar, prototype, export, and admin
presentation policy can become the new place that answers too many
questions.

**How to apply:** After extraction, run SRP/DRY/linear-flow checks over
the new service owner. Prefer one behavior-backed responsibility per
service method, and add a Phase 7 follow-up if the service is cohesive
enough for now but trending toward an omnibus.

## R41 — Guard tests are cleanup deliverables

The lasting win from a cleanup is often the test that blocks the old
responsibility from returning: no raw SQL in a view, no retired flat
file, no fake production fallback, no public admin diagnostic, no bare
dispatch path without failure cleanup.

**How to apply:** Treat `refactor -> guard` as incomplete until the
plan names a negative guard. A lint is useful when the pattern is
lexically stable; a test is better when the invariant is a route,
auth/CSRF behavior, import surface, or configured-value policy.
For ExternalSource-style view extractions, a good negative guard is: raw
ExternalSource SQL/cursors/mysql calls, direct ExternalSource API ownership, and
direct import/export writes must not return to the view layer.

## R42 — Delete production fake fallbacks, inject fixtures in tests

Behavioral safety fixes sometimes remove fake production data paths.
That is correct only when tests keep explicit fixture injection so the
code remains testable without restoring the fake fallback.

**How to apply:** When deleting production sample/fake data paths,
replace any tests that depended on them with injected fixtures, fakes, or
mocked service responses. The invariant is "no fake fallback in
production," not "tests stop covering the branch."

## R43 — Async boundary conversions need failure cleanup tests

Moving work from daemon threads or inline calls to Celery changes the
failure boundary. Broker dispatch failure must leave domain state in a
known terminal or retryable state.

**How to apply:** Every `safe_dispatch` conversion that replaces an
inline/thread path gets a dispatch-failure test. Assert that the owning
record is marked failed/cleanup-complete and that the user-visible
status endpoint does not advertise a running job that never started.

## R44 — Package renames split references into three buckets

When a Django/Python package moves on disk, its references split into
three categories with different rules — and conflating them is the
classic source of "the rename compiled but production broke." Before
any package move, enumerate each bucket explicitly:

1. **Python import paths follow the rename.** `from old.X import Y` →
   `from new.X import Y`. `mock.patch("old.X.func")` → `"new.X.func"`.
   These describe *where the code lives* on disk and must track it.
2. **Wire identifiers stay frozen.** Strings that encode external
   identity, not location: `@shared_task(name='old.tasks.X')` (Celery
   broker registry), FK string literals `'old.Model'` (resolved via
   `AppConfig.label`), URL namespace `app_name='old'`, ContentType
   app_label, migration `to='old.X'` references, signal sender strings.
   These are queried at runtime by systems outside this Python process
   (broker, database, URL reverse, migration graph). Renaming them
   orphans queued messages, breaks FK resolution, invalidates URL
   reverses, and corrupts migration history.
3. **Doc/prose references follow the rename.** Architecture docs,
   mock examples in workflow docs, comments naming module paths,
   READMEs. These mirror the import-path bucket.

**Why:** Wire identifiers survive a rename via *decoupling* (Django's
`AppConfig.name='new', label='old'` is the canonical mechanism), not
via transformation. The lesson is from a `core/` → `app/` rename
(ADR 0011): the on-disk package became `app/`, but the Django app-label,
all FK strings, all URL namespaces, all Celery wire names, and the
migration graph stayed on `'core'`. ADRs 0010/0011 + a per-file lint
(`core-wire-name-preservation`) codify the contract so future moves
inherit the categorization.

**How to apply:** During `/scope-feature` or `/impact-feature` for any
package-rename work, produce a three-column inventory: `(reference,
bucket, action)`. Bucket 1 entries get rewritten; Bucket 2 entries get
a no-op confirmation plus a guardrail (lint, ADR, or both); Bucket 3
entries get rewritten. A rename plan that doesn't enumerate Bucket 2
is a high-risk operation — surface it as an Open Decision in §6 of the
plan and resolve via `/decide` before promotion.

## L-number index

SKILL.md body references `(L-N)` shorthand. Use this to resolve:

| L-N | Closest rule(s) | One-line |
|---|---|---|
| L-1 | (`knowledge/`) | Worktree venv resolution — never fall back to a sibling worktree's venv |
| L-3 | R15 | Single scout on 10K LOC blows the thoroughness budget |
| L-4 | R6 + execution-playbook §5.2.0 | Re-check main worktree dirty set before EVERY batch, not just the first |
| L-5 | R14 | 40%-incomplete spec inventory would have silently orphaned 11 tasks |
| L-6 | R2 | Phase 1.5 gate is chunk-level, not file-level |
| L-7 | — | Archaeology ownership split by churn (scout vs orchestrator) |
| L-8 | R4 | Subject-word-biased `git log` recipe for archaeology |
| L-9 | R16 | Chunk-prefixed provisional IDs prevent collision at Phase 2.2 |
| L-10 | — | INV is not a catch-all for ambiguity — classify the observation |
| L-11 | R20 | `safe_dispatch` was ~55% compliant; enforcement is part of the refactor |
| L-12 | R14 + R2 | Orphan chunks (whole file spans) are higher-ROI scout targets |
| L-13 | R17 | ≥ 50 commits → mandatory archaeology, ≥ 3 load-bearing LR-T extractions |
| L-14 | — | Finding-or-not decision tree (action/EX/prose/INV/P-tier) |
| L-16 | (`knowledge/`) | Don't silently fall back to `.venv/` in the wrong worktree |
| L-17 | R19 | Micro-fix swarm for 5+ mechanical fixes, parallel sub-agent dispatch |
| L-18 | R20 | Convention enforcement is first-class, not scope creep |
| L-19 | R15 | AST-based chunker respects decorators and class boundaries |
| L-21 | (tooling) | Chunker uses OR-gated token + LOC caps, not AND |
| L-22 | — | Tile-the-file chunk-coverage invariant (chunks fill `[1, total_loc]` gap-free) |
| L-23 | R21 | Canonical six-bucket short codes (IM/AR/EX/LR-T/REM/INV) |
| L-24 | R22 | Chunk-map descriptions are advisory; verify behavior in the code |
| L-25 | R4 | Subject-word recipe validated on `core/views_crawling.py` (102 commits → 7 load-bearing) |
| L-26 | R23 | Dedup audits find dead/broken code at subsystem scale |
| L-37 | R27 | Structural AST normalization vs text-hash DRY detection |
| L-38 | R28 | Three-level SOLID harness (artifact / automated / sub-agent judgment) |
| L-40 | R29 | Directory packages over flat naming |
| L-41 | R32 | `from .common import *` beats auto-import detection |
| L-42 | R30 | `__all__` mandatory in shared modules |
| L-44 | — | Decomposition-mode characterization tests pin structure, not behavior |
| L-45 | R31 | Mock patches split two ways after a decomposition |
| L-47 | R35 | Basename-qualify chunk IDs — bare `C-01` collides across files |
| L-48 | R36 | Pre-dispatch coverage check — verify `verification_cmd` touches target file |

Entries with `—` are inlined into SKILL.md body near their use site.
