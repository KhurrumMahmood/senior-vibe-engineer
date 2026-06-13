# Change spec — /fix-workflow repair

Date: 2026-06-12. Inputs: frame-review.md (F1–F9, all scout-verified
TRUE), scout.md (anchors, contracts, load-bearing audit), three
pre-established campaign defects D1–D3 (class-sweeps-spec.md). No
finding was marked FALSE; nothing dropped. Scout corrections folded
in (line cites F2/F7 off-by-one; argparse range F8; `track.py` has no
`note` subcommand — closeout uses `event`/`lesson`).

## Declared verdict (how the verifier judges)

A C-item is RESOLVED only if ALL hold:

1. The anchored text reads as specified below, verified by quote
   against the working tree (not paraphrase).
2. **No invention:** every added sentence traces to this spec, a
   scout-quoted fragment, or pre-existing skill text. Host-specific
   facts the repo cannot ground appear ONLY inside
   `<!-- host-adapter: ... -->` slots or "birth host:" parentheticals
   quoting text that already existed.
3. All eight bare `` `knowledge/` `` references (scout §2 inventory)
   now name `knowledge/verification.md`, and that file exists with
   the four blocks of C1.
4. No reference to `reports/duplication/learnings.md` remains
   anywhere under `.claude/skills/fix-workflow/`.
5. `.venv/bin/python scripts/skill_meta.py lint` passes.
6. New-defect sweep of the same classes (bare directory refs, dead
   artifact mandates, host paths without fallback, stop-condition-less
   shapes) finds nothing newly introduced.

Overall PASS requires every C-item RESOLVED and a clean no-invention
diff audit.

## Constraints

- Smallest anchored edits; preserve the skill's voice and structure.
- No renumbering of R1–R14, §2a–2d, or Steps 1–7.
- Nothing invented: unreconstructable host content becomes a
  host-adapter slot, never plausible filler.
- Judgment calls go in `implementation.md`. Implementer does not
  commit. Run the lint named above; record "no skill-local validate
  command found" if grep confirms absence.

---

## C1 (F1) — Restore the missing knowledge file; re-point all 8 bare refs

Create `.claude/skills/fix-workflow/knowledge/verification.md` with
EXACTLY this content (orchestrator-authored; every block traces to a
named fragment):

````markdown
# Verification & commit reference

Verification machinery `SKILL.md` delegates here: worktree +
cleanliness guard commands, the test matrix, commit verbs + message
template, and the jscpd re-scan command. Host-specific content is
marked with a host-adapter slot, never guessed.

## Worktree & cleanliness guard

Run wherever invoked; confirm the root first:

```bash
git rev-parse --show-toplevel
```

Target files must not carry unrelated uncommitted edits:

```bash
git status --porcelain -- <target files>
```

Abort conditions:

- Any target file shows edits you did not make → abort and report
  the dirty files. Do not stash, discard, or commit around them.
- `git status` shows conflicting edits to the same files from
  another worktree (concurrency collision) → abort. Do not rebase
  or merge.

## Verification test matrix

Baseline + per-subsystem rows. The matrix is host-specific.

<!-- host-adapter: fill this table for the host project — one
baseline row (fast cross-cutting suite) plus one row per subsystem
mapping source paths to test modules, including any test-settings
flag. Birth-host example: baseline = tests.test_site_capabilities +
tests.test_hydration_detector under --settings=app.settings_test_sqlite. -->

| Subsystem / path | Test modules | Notes |
|---|---|---|
| _(unfilled — apply the absence fallback below)_ | | |

**Absence fallback (mandatory when the table is unfilled):** the
matrix does not exist on this host yet. Do NOT invent rows or report
"the matrix says". Run the narrowest meaningful suite for the
touched files (the host's `docs/testing.md` or project adapter names
it), and state in the execution plan that the matrix was absent and
which suite you chose. If unsure, run the superset for the file's
subsystem.

## Commit verbs & message template

Verbs: `Dedup` / `Delete` / `Fix` / `Promote` / `Migrate`. The
commit title starts with the verb (the §2c and §2d stop conditions
check this).

```
<Verb> <what>: <cluster name or target>

- Behavior preserved (R1); a latent bug left in place is named:
  "Behavior preserved, including <bug>".
- Reordered side effects name the new order and the crash
  implication (R8).
```

## Post-cluster jscpd re-scan (dedup shapes — R14)

```bash
.venv/bin/python scripts/lint/run_jscpd.py <touched-subdir> \
  --output reports/duplication/rescan --offline-ok
```

Diff the clone count against `reports/duplication/latest/jscpd/`.
Fewer clones = the refactor landed. Same-or-more = it didn't;
investigate before closing. Record the before/after counts in the
cluster entry's Tests section so a skipped re-scan is visible.
````

Fragment trace (for the no-invention audit): guard commands ←
SKILL.md:112-117 + failure-modes lines 350-351; matrix description ←
SKILL.md:198-200 + R10 + fix-shapes.md:183-186 (birth-host example
inside the adapter slot only); verbs ← SKILL.md:219; title-verb rule
← fix-shapes.md:199, 242; template bullets ← R1 ("Behavior preserved,
including <bug>") and R8; jscpd command ← the repo's real wrapper
`scripts/lint/run_jscpd.py` as invoked by find-duplication Stage 1;
"record before/after counts" ← frame-review load-bearing table
(wires R14 so skipping is detectable).

Then re-point the eight bare refs (anchors in scout §2):

- SKILL.md:42-43 → `` - `knowledge/verification.md` — worktree + cleanliness guard commands, test matrix (host-adapter), commit verbs + message template, jscpd re-scan command. ``
- SKILL.md:116-117 → `` `knowledge/verification.md` has the exact commands and abort conditions. ``
- SKILL.md:199-200 → `The matrix lives in `knowledge/verification.md` (baseline + per-subsystem rows). If the host table is unfilled, follow its absence fallback — run the narrowest meaningful suite for the touched subsystem and name the choice in your plan. If unsure, run the superset for the file's subsystem.`
- SKILL.md:206 → `` Command + rationale in `knowledge/verification.md`. ``
- SKILL.md:220-221 → `` ...and the commit-message template live in `knowledge/verification.md`. ``
- SKILL.md:334-335 → `` (use `knowledge/verification.md` subsystem mapping). ``
- fix-shapes.md:66-67 → `` (see `knowledge/verification.md` test matrix) ``
- learnings.md:112 → `` the test matrix in `knowledge/verification.md` — it maps cluster subsystems ``

Consistency edits in the same class: SKILL.md:38 stays "three
knowledge files" (now true — fix-shapes, verification, learnings; the
fourth bullet is the shared `_common` reference; if the implementer
prefers, "three knowledge files plus one shared reference:" is
acceptable). Repository-layout tree (SKILL.md:362-368): add
`verification.md` line with comment `# guard commands, test matrix, commit template, jscpd`.

## C2 (F2) — Wire the `layer:` entry point

- SKILL.md:55-56 pattern list: add `layer:<name>` →
  `Pattern: `cluster:<name>`, `delete:<name>`, `fix:<name>`, `semantic:<name>`, `layer:<name>`, or a short id like `P0-1`, `P1-agent-extract`.`
- New loading bullet after SKILL.md:58:
  `` - `layer:<name>` → load `reports/layer-violation/latest/report.md` (emitted by `/find-layer-violation`; per-candidate evidence at `scout/<candidate_id>.json`, machine view in `findings.json`). ``
- Abort list SKILL.md:70-73: add `/find-layer-violation` to the
  named detection skills.
- Step-1 shape table: add row after line 139:
  `| **Extract service (layer violation)** | entry point owns business logic — from `/find-layer-violation` | `fix-shapes.md` §2a applied at service scope + `_common/interface-depth.md`; if the extraction spans multiple commits/files, hand off to `/refactor-subsystem` |`
  (The multi-commit boundary restates the existing `not_for`.)

## C3 (F3 + D1) — Retire the orphan cross-cluster log; keep the wired promotion path

Scout-supported remediation: **(a)** — zero readers anywhere,
parent dir never created, path gitignored; the only consumed
learnings surface is `knowledge/learnings.md` via the existing
human-gated promotion callout; Step 7 needs only current-run inputs.

- Frontmatter description (SKILL.md:3): replace
  ``updates `reports/duplication/learnings.md`,`` with
  ``writes a cluster learnings entry,``.
- SKILL.md:233-235: retitle Step 5 `## Step 5 — Write the cluster learnings entry`
  and replace the append mandate with:
  `Write a cluster entry and present it in your closing reply — it is the run's record: Step 6 adds follow-on findings to it, and Step 7's recommendation and the user's next-cluster choice consume it.`
  Template block (237-260) unchanged.
- SKILL.md:262-267: delete the LOC-delta-table sentence and the
  `reports/duplication/learnings.md` parenthetical; keep the
  promotion callout:
  `If the cluster taught something not already in the skill's `knowledge/learnings.md` R1–R14, call it out in the entry — the user decides whether to update the skill.`
- Verify no other `reports/duplication/learnings` reference remains
  under the skill dir (declared-verdict item 4). The
  `reports/duplication/latest/...` triage/jscpd pointers are a
  different artifact — keep them.

## C4 (F4) — Host-bound commands get explicit absence fallbacks

fix-shapes.md §2c:

- Before the grep block (after "Run BOTH checks:", line ~143) insert:
  `The roots below are the birth host's (Django). If the host lacks them, substitute the host's source/template/static roots and name the substitution in your execution plan.`
- Prune list 169-170: rewrite the two bullets host-neutrally:
  `- URL patterns in the host's URL modules (birth host: `core/urls.py`) if it was a view`
  `- Admin registrations (birth host: `core/admin.py`) if it was a model admin`
- Before the baseline test block (step 5, line ~180) insert:
  `The command below is the birth host's. No `manage.py` on the host → run the host's baseline equivalent per the `knowledge/verification.md` absence fallback and name the substitution.`
- Step 6 heading (189): `6. **Run the framework's dangling-reference check** (birth host: `django-admin check`) to catch dangling URL patterns:` — command block stays; append:
  `No host equivalent → state that explicitly in the stop-condition check; do not claim the check passed.`
- Stop condition (196-198) → property-named:
  `- Fresh re-grep returned zero new inbound references.`
  `- The framework's dangling-reference check passes (birth host: `manage.py check`) — or the named host substitute, or its absence is stated.`
  `- Baseline + subsystem tests pass (substitutions named).`
- SKILL.md:79-80 Form B: `Pattern: matches an existing path in the repo (birth-host example: `core/services/parse_json_body_helper.py`).`
- SKILL.md:188-191 registry checklist:
  `- Verification must include the host's site-workflow tests (birth host: the site workflow Django tests and, when a dev server is running, `testing/test_site_pages.py`).`
  `- Do not touch the host's AI-sidecar surface (birth host: `core/services/ai_sidecar/`) or unified AI workflow behavior unless the user explicitly scopes that work in.`
- NO-EDIT: learnings.md R13 `tests_custom_site` and the cluster
  provenance examples — illustrative provenance, not commands
  (learnings.md:8 declares rules provenance-anchored). Record in
  implementation.md.

## C5 (F5) — Stop condition for the workflow-registry shape

Insert after SKILL.md:191 (before `## Step 3`):

```
### Stop condition (workflow registry cleanup)

- Boot-payload characterization tests written before production
  edits, and green.
- Every endpoint-registry key asserted equal to its `reverse(...)`
  (or the host router's equivalent).
- Cache-busting bumped on every touched JS include.
- Diff-scoped guard added, or deferred with a named reason in the
  cluster entry.
- URL routes and view names unchanged, or the user explicitly
  authorized route migration.
```

(Every box restates a checklist mandate — no new obligations.)

Reconciliation: SKILL.md:163-165 append `(The workflow-registry shape uses the checklist below instead; its stop condition follows the checklist.)`. fix-shapes.md table (6-13): add row
`| Workflow registry cleanup | inline checklist in `SKILL.md` Step 2 |`.
Counts: SKILL.md:40 → `Step-2 playbooks for the seven shapes routed there (the eighth — workflow registry cleanup — uses the inline checklist in this file).`; SKILL.md:366 tree comment → `# Step-2 playbooks (7 of the 8 shapes)`.

## C6 (F6) — Inline Form B's investigation; drop the phantom stage pointer

SKILL.md:82-86 → replace with:

```
Treat the file as the scope. No triage context — investigate from
scratch, answering at minimum: who calls each suspect symbol (grep
all call sites); where the duplicate or suspect bodies actually
diverge; whether a canonical equivalent already exists; and what
tests cover the area. **Before any edits**, run Step 1 on that scope
and present its execution plan (file list, fix shape, helper name)
to the user; wait for confirmation.
```

(The last sentence is shared with C9 — implement together.)

## C7 (F7) — No fuzzy-matching of cluster IDs

After SKILL.md:75-76 add:

`If no exact ID match exists in the loaded report, list the available IDs and abort — do not fuzzy-match to the closest-looking entry.`

## C8 (F8) — Shape→bucket mapping

Replace SKILL.md:285-286 with:

```
Where `<shape>` is one of: `dedup`, `delete`, `fix`, `promote`,
`migrate`, `shadow`, mapped from the Step-1 shape:

| Step-1 shape | bucket |
|---|---|
| Pure duplication / Three-way+ clone / Policy-flag clone / Template triplication | `dedup` |
| Shadow helper | `shadow` |
| Dead code | `delete` |
| Quasi-dead / broken | `fix` |
| Workflow registry cleanup | `migrate` |
| Extract service (layer violation) | `promote` |
```

## C9 (F9) — Step 1 runs before Form B/C approval

- Form C (SKILL.md:90-97) → replace with:
  ```
  The description is your brief. Run Step 1 on it — the execution
  plan it produces (file list, fix shape, expected changes per file)
  is what you present. **Present this plan and wait for explicit
  user confirmation before making any edits.** Ask for clarification
  if target file(s) or fix shape can't be inferred.
  ```
- Form B: covered by C6's replacement sentence.
- SKILL.md:153-156 → `**Form A** → plan is a self-check; proceed after writing it. **Forms B/C** → the plan was already produced and approved during argument parsing (Step 1 ran early); don't re-present it or wait for a second confirmation.`

## C10 (D2) — "How success is judged" block

Insert between SKILL.md:36 and :38 (anchor in scout §2):

```
## How success is judged

- A regression/characterization test exists **before** the fix and
  is green at commit time (R2; §2d writes the failing test first).
- The behavior-preserving refactor commit is separate from any
  bug-fix commit (R1).
- The verification matrix ran green for the touched subsystem
  (Step 3) — plus the jscpd re-scan for dedup shapes (R14).
- The playbook's stop condition has every box checked; no commit
  otherwise.
Work toward these gates from Step 1.
```

## C11 (D3) — Class-lift gate in Step 7

In Step 7, insert a new item 2 (renumber "Next cluster" to 3 — list
renumbering here is required and allowed; R-rules/sections/steps stay):

```
2. **Class lift.** Name the fixed defect's class in one sentence,
   define the cheapest detector for it (usually a grep), and RUN the
   detector across the codebase before closing. Paste the hit count
   in the recommendation. Siblings found → name them as one batch
   sweep candidate, not N future clusters; class mechanizable → that
   is the `/prevent-regression` candidate from item 1 (the
   two-clusters-justify-one-rule threshold gates the lint, not the
   detector run — running the detector is free).
```

Preserve item 1's threshold language verbatim (scout D3 nuance).

## OUT-OF-SCOPE (route to ledger at Stage 8)

1. `refactor-subsystem` appends to the same dead
   `reports/duplication/learnings.md` path (SKILL.md:1263,
   knowledge/operations.md:178) — sibling repair, separate campaign.
2. Full host-adapter parametrization of fix-workflow's
   `language: python` / `framework: django` frontmatter (portability
   roadmap / /plan-skill scope); C4 adds fallbacks only.
3. Whether `/find-duplication` should seed a learnings surface —
   moot under remediation (a); revisit only if a cross-run consumer
   ever appears.
4. fix-shapes.md anchor-link fragments (`#2a-extract-helper-shapes`)
   — cosmetic; not execution-affecting.
