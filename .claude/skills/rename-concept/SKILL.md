---
name: rename-concept
description: |
  Assess a domain-concept rename against its full lifecycle and a mandatory
  two-band completeness gate, read-only. Renaming a concept that lives in the
  glossary spans many surfaces — identifiers, docs, the cross-tool agent
  mirrors — and is executed from tribal knowledge with no front door and no
  completeness gate, so renames land half-applied. This skill (v0, assess-only)
  reports the scope-gate verdict, blast radius, a per-step lifecycle status
  table, and the completeness gate. It performs strict lexical assessment of
  Python, JavaScript, TypeScript, and TSX text. For `.ts` and `.tsx`, a
  host-pinned TypeScript Compiler API resolves glossary identifier candidates,
  declarations, and references; it does not claim whole-project type-checking,
  JSX runtime behavior, or codemod safety.
  The old and new names must not co-occur lexically in
  live code (/find-concept-divergence superseded_co_occurrence, band 3) AND no
  retired phrasing may remain (/find-concept-divergence avoid_term_hit, band 1)
  — both must be CLEAN for a lexical candidate assessment to pass. A
  TypeScript/TSX host additionally needs a successful Compiler API evidence
  run that resolves old/new identifier candidates. Definition of done is the
  two-band gate, every lifecycle step resolved, and that evidence where
  TypeScript/TSX is in scope — NOT a codemod having run. Drives the two
  rename-relevant /find-concept-divergence bands through a required coupled
  installation; the assessment logic does not duplicate their matching rules.
  The write half (author + dry-run a codemod plan, scaffold a reintroduction
  lint, --apply) is a v1 gap pending a codemod harness in this
  ecosystem (see Deferred, below).
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
  /move-path — if the concept rename also requires moving/renaming files or
  directories and updating path references as a deterministic batch.
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
language: any
framework: any
scans: [python, javascript, typescript, markdown, templates]
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
.venv/bin/python .claude/skills/rename-concept/scripts/assess.py <old> <new> \
  [--min-blast N] [--project-root DIR] [--output assessment.json]
```

Install this skill together with its detector companion,
`find-concept-divergence`. Its installed `scan.py` is the single authority for
both lexical bands; `rename-concept` does not copy or fork its matching logic.
Repository development may use the source-tree sibling. A
copied `rename-concept` without that installed companion is inconclusive.

## Installed with the stock CLI

Set `ENGINEERING_SKILLS_SOURCE` to the published source URI or a local checkout
when testing a revision. The one installation command below projects the two
required skills; assessment remains read-only.

<!-- installed-command:install:start -->
```bash
: "${ENGINEERING_SKILLS_SOURCE:?Set this to the engineering-skills source URI or local checkout}"
DO_NOT_TRACK=1 npx --yes skills@1.5.19 add \
  "$ENGINEERING_SKILLS_SOURCE" \
  --skill rename-concept find-concept-divergence --agent codex --copy -y
```
<!-- installed-command:install:end -->

For a TypeScript/TSX host, the project must pin `typescript` in its own
`package.json` and lockfile. Install that declared host dependency before
assessment; it must resolve from inside the project root. The skill never
downloads or substitutes an ancestor compiler.

<!-- installed-command:typescript-preflight:start -->
```bash
npm ci --offline --ignore-scripts
```
<!-- installed-command:typescript-preflight:end -->

<!-- installed-command:assess:start -->
```bash
PROJECT_ROOT="$PWD"
RENAME_CONCEPT_SKILL="$PROJECT_ROOT/.agents/skills/rename-concept"
(
  cd "$RENAME_CONCEPT_SKILL"
  python3 scripts/assess.py \
  "${OLD_CONCEPT:?Set the deprecated glossary concept}" \
  "${NEW_CONCEPT:?Set its canonical glossary concept}" \
    --project-root "$PROJECT_ROOT" \
    --output "$PROJECT_ROOT/reports/rename-concept/assessment.json"
)
```
<!-- installed-command:assess:end -->

The scanner interprets scan targets and exclusions relative to `--project-root`.
It excludes an ignored directory or file even when passed directly, and never
follows a symlink that resolves outside the target project. This protects a
host nested under a path named `node_modules` while still excluding its own
`node_modules/`, `dist/`, and migration trees.

On a project containing `.ts` or `.tsx`, assessment runs the host-pinned
Compiler API after the lexical scan. It reports the compiler version, resolved
old/new declaration/reference counts, and a classification for every lexical
old/new candidate. If the host compiler is unavailable, an old-concept symbol
remains, a candidate cannot be resolved, or no new-concept declaration exists,
or parsing/relevant resolution diagnostics are present, the verdict stays
incomplete. `--output` persists this exact read-only evidence as JSON; it
creates only the report path, never alters a host source file.

Reports, read-only:

- **scope-gate** — is `<old>` a glossary concept and/or a wide-blast rename
  (≥ `--min-blast` live files, default 3), or a trivial local one the skill
  should bail on? Anchored at `--project-root` (default: git toplevel of the
  cwd, else the cwd) so the verdict never depends on where inside the target
  repo the caller sits — and never silently inspects the kit's own repo.
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
`/find-concept-divergence` band is dirty, any lifecycle step is unresolved, or
TypeScript/TSX identifier completeness is unproven. `assess.py` requires the
host-pinned Compiler API result in addition to a green lexical scan.
`assess.py` runs the coupled detector ONCE and consumes only its two
rename-relevant bands for this rename:

- **Band 3 — `superseded_co_occurrence`** (lexical old/new candidates): the old
  name and the new name must not co-occur as glossary terms in a scanned file.
  This is an actionable text candidate. The Compiler API evidence section maps
  it to an old-concept symbol, a shadowed local, import alias, property key,
  string, comment, or unresolved identifier before the verdict uses it.
  *Caveat:* when the old
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

For a non-TypeScript project, the lexical gate is GREEN only when **both** bands
ran and are empty. A band-1 hint alone — with band 3 green — turns the verdict
to HALF-APPLIED / INCOMPLETE. For a TypeScript/TSX project, both bands must be
green and the Compiler API must resolve the expected new declaration with zero
old-concept references or unresolved identifier candidates, and no parsing or
candidate-resolution diagnostics. The authority surface is intentionally
limited: only matching **top-level exported** declarations can establish the
old/new concept symbols. Same-named internal declarations never certify a
rename.

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
- **path moves** that are part of the rename should use `/move-path` with a
  reviewed `moves.yml` plan; it updates filesystem/path references, not
  identifier or prose terminology;
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

## TypeScript / TSX boundary

Treat `.ts` and `.tsx` as a two-stage surface. The lexical bands find a
glossary-listed old/new term pair or exact retired phrase, including JSX text
and comments. The bundled runner then uses the host's pinned TypeScript Compiler
API on root-contained TS/TSX files selected by the coupled scanner's default
surface and classifies each lexical old-name candidate:
`old_concept_symbol`, `shadowed_local`, `import_alias`, `property_key`,
`string_literal`, `comment_text`, or `unresolved_identifier`.

Only matching top-level exported declarations establish rename authority;
internal/unexported declarations are reported but cannot establish completion.
The runner reads the host `tsconfig.json` when available and blocks completion
on invalid `tsconfig`/parser diagnostics or semantic diagnostics that affect
candidate/module/name resolution. It never mutates source. It does not make a
whole-project type-check pass a completion condition, rewrite identifiers/imports, resolve
dynamic behavior, or prove an IDE codemod is safe. Keep code mutation outside
this assess-only skill.

Pairs with `/find-incomplete-sweep`: this **assesses** whether a rename is
done; that **catches** a half-done sweep after the fact.
