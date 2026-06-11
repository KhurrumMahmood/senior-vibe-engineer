---
name: rename-concept
description: |
  Assess a domain-concept rename against its full lifecycle and a mandatory
  two-band completeness gate, read-only. Renaming a concept that lives in the
  glossary spans many surfaces — identifiers, docs, the cross-tool agent
  mirrors — and is executed from tribal knowledge with no front door and no
  completeness gate, so renames land half-applied. This skill (v0, assess-only)
  reports the scope-gate verdict, blast radius, a per-step lifecycle status
  table, and the completeness gate: the old and new names must not co-occur in
  live code (/find-concept-divergence superseded_co_occurrence, band 3) AND no
  retired phrasing may remain (/find-concept-divergence avoid_term_hit, band 1)
  — both must be CLEAN for the rename to count as done. Definition of done is
  the two-band gate plus every lifecycle step resolved, NOT a codemod having
  run. Drives /find-concept-divergence; does not reimplement it. The write half
  (author + dry-run a codemod plan, scaffold a reintroduction lint, --apply) is
  a v1 gap pending a codemod harness in this ecosystem (see Deferred, below).
argument-hint: "<old-concept> <new-concept> [--min-blast N]"
allowed-tools: Bash, Read, Grep, Glob
user-invocable: true
tier: maintenance
job: refactor
best_for: |
  Assessing whether a glossary-worthy, wide-blast concept rename is COMPLETE —
  the long tail (string-literal references, the guard lint, the cross-tool
  agent mirrors, the docs) is exactly what a rushed pass forgets, and the
  two-band gate is what catches a rename that is identifier-clean but still
  carries retired prose. Use when the rename is glossary-tracked and the cost
  of a half-applied result is real. Pairs with /find-concept-divergence (which
  DETECTS the drift): this skill consumes that detector and frames it as a
  per-rename definition of done.
not_for: |
  A trivial local-symbol change outside the glossary with a narrow blast
  radius (use an IDE or a scoped find-and-replace) — the scope-gate bails
  these. Bulk drift detection across ALL concepts at once (use
  /find-concept-divergence directly — this skill filters it to ONE rename).
  General module decomposition or service extraction (use /refactor-subsystem).
  Authoring the DECISION itself — the ADR content is human judgment; this skill
  reports lifecycle status, it does not decide. Executing the codemod — there
  is no codemod harness in this ecosystem yet, so the write half is deferred
  (see below).
escalate_to: |
  /decide — to author the ADR content for the decision step of the lifecycle.
  /refactor-subsystem — if the rename needs structural module moves beyond
  identifier/string renames.
  /find-concept-divergence — the completeness gate runs it; escalate if it
  stays red after remediation, or to scan ALL concepts rather than one rename.
delegate_from: |
  /find-concept-divergence — when superseded_co_occurrence or avoid_term_hit
  drift shows a rename was left half-applied, this skill frames it as a
  per-rename completeness check.
  /which-cleanup — a change that looks like a started concept rename routes
  here.
language: python
framework: any
---

# /rename-concept

Read-only **assessment** of a domain-concept rename against its lifecycle and a
two-band completeness gate. Renaming a concept in a glossary-backed codebase is
a multi-step lifecycle (decide → glossary → identifier sweep → guard lint →
cross-tool mirror sync → correct old prose/docs) that, executed from tribal
knowledge with no completeness gate, predictably lands half-applied. This skill
sequences and verifies the existing mechanisms; it does not reimplement them.

The canonical glossary is `.claude/contracts/concepts.yaml`; the detector this
skill drives is `/find-concept-divergence`.

## Mode: assess — read-only lifecycle status + completeness gate

```bash
.venv/bin/python .claude/skills/rename-concept/scripts/assess.py <old> <new>
```

Reports, read-only:

- **scope-gate** — is `<old>` a glossary concept and/or a wide-blast rename
  (≥ `--min-blast` live files, default 3), or a trivial local one the skill
  should bail on? Anchored at the repo root so the verdict never depends on the
  caller's CWD.
- **lifecycle status** — a per-step table: is `concepts.yaml`'s old entry
  marked `superseded_by: <new>`; does a `no_<old>_references` reintroduction
  lint exist under `scripts/lint/`; how many live-code files still mention the
  old token (allowlisted residue — the ADR tree, the glossary, this skill, the
  detector, reports, migrations — excluded).
- **completeness gate** — the two-band `/find-concept-divergence` result,
  filtered to this rename. This is the definition of done.

`--min-blast` tunes the scope-gate threshold.

## Definition of done = the completeness gate (two bands)

The visible part of a rename (the identifier sweep) is the part a rushed pass
stops at. This skill refuses to call a rename complete while EITHER
`/find-concept-divergence` band is dirty, or any lifecycle step is unresolved.
`assess.py` runs the detector ONCE and filters its findings to this rename:

- **Band 3 — `superseded_co_occurrence`** (TERM-level identifiers): the old name
  and the new name must not co-occur in live code. *Caveat:* when the old
  concept declares a `coverage_lint:` in `concepts.yaml`,
  `/find-concept-divergence` **skips this band** (the lint owns identifier
  enforcement) — so for a lint-guarded rename band 3 is structurally empty and
  band 1 is what actually proves the work.
- **Band 1 — `avoid_term_hit`** (TERM-level prose): no file may still use a
  phrasing the glossary's `avoid:` block forbids for this rename. The `avoid:`
  block lives on the **new/canonical** concept (the new slug carries the
  retired phrasings the old name used). This band is **not** skipped for
  coverage_lint concepts, so it sees the comments / docstrings / strings the
  lint and band 3 are both blind to. This is the prose-blindness fix: the gate
  verifies the retired *term* was corrected, not just the identifier.

The verdict is GREEN only when **both** bands ran and are empty. A band-1 hint
alone — with band 3 green — turns the verdict to HALF-APPLIED / INCOMPLETE.
Both bands clean is what makes the skill verify *prevention* of the
half-applied-rename failure rather than merely reproduce it.

### Two-tier model for stale prose

The gate verifies the **term**, not the **substance**:

- **TERM-stale prose** — text still uses the old word. This is
  **gate-enforced**: `/find-concept-divergence` band 1 greps the canonical
  concept's `avoid:` block, and `assess.py` turns the verdict RED on any hit.
- **SUBSTANCE-stale prose** — the explanation is now *wrong* because the rename
  changed what the concept IS, even after the old word is gone. The gate does
  **not** catch this — it is surfaced by `/find-comment-drift` and corrected by
  human / LLM judgment. Running the term gate green is necessary but not
  sufficient; a substance pass is the human's job.

## Deferred (v1 gap): the write half / codemod

This is **v0, assess-only**. The write half that the lifecycle implies —
authoring a dry-run-ready identifier-codemod plan, scaffolding a
`no_<old>_references` reintroduction lint, and emitting a checklist — is **not
yet ported**. It depends on a codemod harness (a `tools/rename`-style runner)
that this ecosystem does not currently ship, so there is nothing to author a
plan *for*. When such a harness exists, a `orchestrate.py` (propose-only:
authors a plan + a lint scaffold, then STOPS before any `--apply`) is the
intended v1 follow-up, gated so a human reviews the plan + the dry-run diff +
the long-tail inventory before applying. Until then:

- the **identifier sweep** is a manual / IDE step the human performs;
- the **guard lint** (`no_<old>_references`) is authored by hand and wired into
  the lint runner by a human;
- the lifecycle steps assess.py *reports on* but does not author are: the ADR
  content (via `/decide`), the cross-tool mirror sync (`.augment/` +
  `AGENTS.md` and the other symlinked mirrors), and correcting old prose/docs —
  the term-stale half is gate-enforced (band 1), the substance-stale half is a
  human `/find-comment-drift` pass.

## Out of scope: `--apply`

Even when the write half lands, applying a wide identifier sweep is
**human-approval-gated by design**: a human reviews the authored plan, the
dry-run diff, and the long-tail inventory, then applies and verifies. The skill
authors and proposes; it does not decide and it does not apply.

Pairs with `/find-incomplete-sweep`: this **assesses** whether a rename is
done; that **catches** a half-done sweep after the fact.
