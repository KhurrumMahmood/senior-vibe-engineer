# Learnings from prior dormant-code audits (R1-R11)

This file is loaded by **scouts**, not by the orchestrator. Read on
ambiguity. Every rule has provenance so you know why it matters.

## R1 — Never delete unilaterally

Every candidate needs user authorization. Cluster 1b's sub-agent
correctly flagged `DownloadComprehensiveExportView` +
`DebugProductDataView` as orphans and refused to delete. User had to
approve first. That's the right shape.

**How to apply:** Your recommendation is `delete`, `fix`, `document`,
or `none`. Never emit a JSON with `bucket: certain_delete` that
claims the deletion has been done.

## R2 — Fix first, ask about deletion later

If a function is quasi-dead (Flavor 3 — broken in practice) but the
fix is smaller than the deletion, recommend fix + test. The deletion
can follow as a separate commit once the user confirms the endpoint
isn't needed. Keeps blast radius small.

**How to apply:** When bucket = `quasi_dead_broken`, set
`recommendation: "fix"`, not `"delete"`.

## R3 — Silent `except Exception` is a detection signal, not just a bug

It's where Flavor-3 dormant code hides. The detector greps for it
deliberately. Don't dismiss flavor-3 candidates as "probably fine
logging" without reading the protected block.

**How to apply:** For flavor-3 candidates, read 20 lines above the
`except`. Look for specific smells (see `verification.md` Flavor 3
section). If no smell surfaces, bucket as `false_positive` with
reason `log_catch_no_smell`.

## R4 — Grep for THREE things, not one

A view class can be referenced by (a) class name, (b) URL name,
(c) URL path. All three must return zero for "orphan endpoint"
status. Missing any of the three has bitten previous audits.

**How to apply:** 6b + 6c + 6d together are the orphan test. Don't
claim `orphan_endpoint` until all three return zero.

## R5 — Git-log recency is corroborating, not primary, evidence

A function last touched 18 months ago isn't automatically dead —
some code is stable-and-live. But combined with zero inbound
references, it strongly supports deletion.

**How to apply:** Fill `git_last_touched` always. Only escalate
bucket from `false_positive` to `certain_delete` based on git-log;
never demote.

## R6 — Don't grow test coverage for code you're about to delete

Inverse of `/find-duplication`'s rule. If deletion is authorized,
scrap any regression tests that exercise the deleted code. Cluster 3
deleted 349 LOC of Cluster 1b's regression tests alongside the
production code — correct behavior.

**How to apply:** List test files that reference the candidate in
`evidence.call_sites`, so `/fix-workflow delete:` knows to scrap
them in the same commit.

## R7 — Dead-code scales with bug blast radius of a neglected file

A file with one dead function probably has more. Grep upward, not
just around the candidate. The top of `core/utils.py` held 138 LOC
of bonus dead code that Cluster 1 would have missed without a whole-file
read.

**How to apply:** When confirming a candidate, note in `notes` if
the containing file has other dormant-looking defs nearby. The
orchestrator can use that to expand the candidate set.

## R8 — "Looks dead" is not "verified to be dead"

Standard for deletion: demonstrable absence of call sites across
core/, templates/, JS, urls.py, admin.py, management/commands/. If
there's any ambiguity (dynamic dispatch, `getattr`, custom template
tags), **escalate — don't delete**.

**How to apply:** When in doubt, bucket as `false_positive` with
reason `registry_dispatch` or `dynamic_call`. User can override; the
default must be conservative.

## R9 — URL patterns are load-bearing for detection, not correctness

A Django view wired in `urls.py` but not reachable from any template
or API consumer is the classic orphaned-endpoint shape. It *runs* if
you hit the URL directly, but nothing does. Report as orphan, not
"in use".

**How to apply:** URL-wired + zero template/JS/test refs =
`orphan_endpoint`, not `false_positive`.

## R10 — Django false positives are predictable

The detector pre-filters these, but if one slips through, bucket as
`false_positive`:

- CBV handler methods (`get`/`post`/`form_valid`/`dispatch`)
- Signal receivers (`@receiver(...)`)
- Management command `handle` methods
- Template tags/filters (`@register.tag`, `@register.filter`)
- Model `Meta` inner classes
- DRF viewset actions (`list`/`retrieve`/...)
- Admin actions (methods on `ModelAdmin` subclasses)

**How to apply:** When verification finds one of these patterns,
bucket as `false_positive` with `false_positive_reason` set to the
matching class. Even if no inbound references, these are live via
Django dispatch.

## R11 — Flavor 4 (orphan entry + live internals) requires end-to-end analysis

When the entry point (view, task, command) is orphan but the
downstream code it calls is still wired to other entry points, only
the entry is deletable. Deleting the whole chain breaks everything
hanging off the downstream paths.

**How to apply:** If the candidate is a view/task/command, follow
its call graph once. If any downstream function has **other**
callers (found via 6d grep), bucket as `orphan_endpoint` (entry only)
and note in `notes` that downstream code remains in use. If
downstream is exclusively reached via this entry, bucket as
`certain_delete` with `notes: "deletion must include <downstream
names>"`.
