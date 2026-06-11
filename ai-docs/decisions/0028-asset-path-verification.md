---
id: "0028"
namespace: core
title: Refactors that move files must prove path-derived references still resolve
status: proposed
date: 2026-06-09
provenance: "Promoted from a private host adaptation where this pattern is accepted and enforced; offered to core as a calibrated default."
revisit_when: ["a disk-anchored post-move-scan detector is built in core"]
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [.claude/skills/refactor-subsystem/, .claude/skills/propose-folder-reorganization/]
tags: [refactor, safety, path-integrity]
related_smell: null
related_pattern: null
---

# Refactors that move files must prove path-derived references still resolve

## Context

When a refactor moves or restructures source files, an automated rewrite pass can fix
the references a parser can see: imports, dotted-path string literals, patch targets,
templates, and script paths. There is one class it routinely misses — references
computed *at runtime* from the file's own location on disk.

The canonical shape is a self-anchored path: an expression that takes "the directory this
file lives in" and walks up or down a fixed number of levels to locate a sibling asset (a
prompt template, a data file, a fixture). In many languages this looks like deriving a
base directory from the current source file and appending literal path segments — for
example a `Path(__file__)`-rooted chain that climbs `N` parent levels and then joins
`"assets" / "template.txt"`.

The trap is that this expression encodes the *depth* of the file in the tree, not the
*target* it is trying to reach. Move the file one directory deeper and the parent-walk
count is now wrong, yet the expression still parses and compiles, imports still succeed,
and nothing fails until the moment the asset is actually read at runtime. So the breakage
is invisible to a compiler, invisible to an import smoke check, and invisible to any test
that does not exercise the specific code path that reads the asset. It surfaces in
production as a "file not found" raised far from the move that caused it — sometimes days
later, in a workflow nobody associated with the refactor.

A refactor workflow whose safety gates pin *public behavior* will not catch this. A
behavior test only exercises the asset path indirectly, and only if that path happens to
run in the always-on suite — which, for assets read deep inside a runtime workflow, it
frequently does not. The reference is also undocumented as a known blind spot, so a human
reviewer reading the plan has no checklist item that names runtime path expressions.

## Decision

Any refactor that moves files must prove path-derived references still resolve, at **three
independent layers**, before the refactor is marked complete:

1. **Mechanical rewrite, where the shape is tractable.** The move tool re-derives the
   parent-walk depth of self-anchored path expressions with literal segments, so the same
   filesystem target is reached from the file's new location. Shapes it cannot safely
   rewrite — non-literal or interpolated segments, mixed up-and-down walks, computed depths
   — are **logged to the reviewer as unhandled, never silently skipped**.
2. **Characterization pin-test, where the tool cannot help.** Before behavior tests run,
   enumerate every self-anchored path expression in each moving file. For each, author a
   test that resolves the constant and asserts the target exists on disk (`is_file()` /
   `exists()` or the language equivalent). A missing pin-test blocks the refactor from
   advancing. The reorganization-proposal step records, per file cluster, whether any
   self-anchored paths are present, so this work is planned rather than discovered.
3. **Disk-anchored post-move scan.** After the move, run a detector over every file changed
   since the pre-refactor revision that computes the filesystem target of each self-anchored
   path chain and reports any whose target does not exist on disk (missing file, missing
   directory, or a directory where a file was expected). Non-empty output blocks completion.

Supporting requirements:

- The move tool's documentation enumerates **every reference class it deliberately does NOT
  rewrite**, so the blind spot is explicit. The refactor workflow reads this before planning.
- A cheap per-batch import smoke asserts that every exported path constant in every moved
  file still resolves — the lowest-cost catch with the smallest blast radius (one batch).
- Whenever any of these gates fires, the rule and its cause are promoted to the project's
  running lessons log, so future refactors that brush this class re-encounter the lesson.

## Alternatives considered

- **A. Rely on existing characterization tests.** Rejected: the characterization layer pins
  the behavior of the public API, not import-time path constants. A behavior test catches the
  break only if it happens to exercise the function that reads the asset — and assets read
  inside runtime workflows are exactly the ones the default suite does not exercise. Tests
  targeting asset paths must be authored deliberately; layer 2 mandates that.
- **B. Make the disk scan a repo-wide blocking lint.** Rejected for now: the
  self-anchored-path detector is a heuristic with legitimate false-positive cases (fixtures,
  scratch code, intentionally lazy paths). Wiring it into every commit invites whack-a-mole.
  The constraint binds where it matters — at refactor boundaries — gated by the post-move scan.
- **C. Refuse to move any file containing a self-anchored path.** Rejected: the idiom is
  legitimate and the tool now handles its common shapes. The correct gate is *correctness*,
  not *avoidance*.
- **D. Leave it to human review.** Rejected: this class ships precisely under that regime — a
  reviewer with no checklist, reading a plan that names imports and patch targets but not
  runtime path expressions, will not spot a one-level-deeper move buried in a large plan.

## Consequences

**Easier:**
- File moves that include asset paths succeed by default — the mechanical rewriter handles
  the common literal-segment cases automatically.
- The failure mode shifts from "ships broken, found in production later" to "blocked at the
  pin-test gate or the post-move scan."
- The disk-anchored detector is useful beyond refactors: it catches path bit-rot from any
  source — manual edits, merge conflicts, partial reverts.

**Harder:**
- Authors of new self-anchored paths must prefer a depth-agnostic form, or accept that a
  refactor will rewrite the parent-walk mechanically. Mixed up-and-down styles are out of
  scope for the rewriter and are logged as unhandled.
- Each moving file with a self-anchored path now requires a pin-test — real additional work
  on a large refactor, but each runs in milliseconds and catches the canonical failure directly.

**Now disallowed:**
- Moving a file containing a self-anchored path expression without either (a) the mechanical
  rewriter handling it, or (b) a pin-test asserting the target resolves.
- Marking the refactor complete while any unhandled-shape was logged, absent a reviewer note
  explaining why each unhandled case is safe.
- Marking the refactor complete while the post-move scan reports any broken-file,
  broken-directory, or directory-where-file-expected finding on the diff range.

## Verification

**Mechanical:**
- The move tool's rewrite suite covers the self-anchored-path shape: one-level-deeper extends
  the parent walk, shallower collapses it, depth-agnostic forms are preserved untouched,
  non-literal segments are logged unhandled, plus idempotency and project-root validation.
- The detector ships with a fixture smoke test asserting bad fixtures produce the expected
  findings and good fixtures produce none.

**Process gates (enforced by the refactor workflow):**
- Planning reads the move tool's documentation of non-rewritten reference classes.
- The enumerate-and-pin step is mandatory before behavior tests; a missing pin-test blocks progress.
- The reorganization-proposal records, per cluster, whether self-anchored paths are present.
- The post-move disk scan runs over the full diff range and blocks completion on any finding.

**Operational lesson:**
- The running lessons log carries a "refactor-induced path breaks" entry recording the rule,
  its cause, and how to apply it, re-surfaced whenever a future refactor brushes this class.
