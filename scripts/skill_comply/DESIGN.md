# skill-comply — conformance-by-side-effect harness (ported design doc)

> **Port note.** Ported verbatim (host name scrubbed to neutral forms) from a
> private host project's `.engineering/experiments/skill-comply/` harness —
> referred to here only as the source host. Layout here:
> `scripts/skill_comply/{seed_fixture,install_proposal,score_conformance,validate}.py`
> with the five proposal fixtures under `scripts/skill_comply/fixtures/`.
> The source's `runs/stage1b-sonnet/` real-model-run artifacts were NOT
> ported; references to them below describe the source experiment, not files
> in this repo. The throwaway seeded repo is called "mini-host" here (the
> source called it after the host). `conformance.json` files are regenerated
> byproducts and are gitignored, exactly as in the source.
>
> Run it here: `python3 scripts/skill_comply/validate.py` (stdlib-only;
> requires `.claude/skills/prevent-regression/scripts/verify_rule.py`, which
> this repo ships).

## KNOWN GAPS (from the source's own self-assessment — ported, NOT fixed)

Verbatim from the source's Stage 1/2 limitations sections (full prose below):

1. **C8 skip is a silent pass.** C8 presumes a curated `antipattern_files`
   set and skips *silently* without one — "an orchestration that forgets to
   pass it gets a green C8 with the over-firing check quietly gone. A
   production layer must treat 'C8 skipped' as a distinct, surfaced state —
   not a silent pass."
2. **Missing recall axis.** C8 is a precision check; "it cannot see a false
   negative on a variant the rule *should* match but doesn't" (e.g.
   `self.request.POST.get(...)`). A recall fixture is "a different
   mechanism, not built here."
3. **Ruff-coverable branch unmodeled.** The SKILL.md Phase 1 "Ruff-first"
   branch (guard = a `pyproject.toml` ruff-enable, no custom script) "is not
   mechanically scoreable by this instrument" — needs a config-diff +
   rule-id-lookup instrument instead.
4. **Single-skill generality.** "Everything so far is one skill / one
   anti-pattern family; a second skill would test whether the rubric
   travels."

---

# skill-comply — Stage 1a: the measurement core

This stage builds and **validates the measurement instrument** for a
"skill-comply" conformance harness, piloted against one skill:
`/prevent-regression`. It does **not** run the real skill — that is a later,
human-orchestrated stage. The goal here is a deterministic, no-model-in-the-loop
scorer that correctly distinguishes a conformant guard-proposal from a defective
one, graded entirely by side-effect.

## Principle: conformance-by-side-effect, anti-gateguard-theater

We grade a guard run only by (a) the artifacts it leaves on disk and (b) the
result of re-running the skill's **own** verifiers against those artifacts.
Never by what the run claims it did. The proposal text can say "verification
passed"; the scorer ignores that and checks the bug is actually caught.

The load-bearing anti-theater idea: **a guard that does not fire on the very
bug it was built for is theater even if every file exists and its own fixture
verifier passes.** That is exactly the gap the defective fixture exercises.

## What the harness does

Four stdlib-only pieces under `scripts/skill_comply/`:

1. **`seed_fixture.py`** — builds a throwaway "mini-host" git repo in a fresh
   `tempfile.mkdtemp()` (never the real tree). It mirrors the guard
   infrastructure a `/prevent-regression` run operates on:
   - the target anti-pattern — bare `int(request.POST.get(...))` /
     `int(request.GET.get(...))` without `safe_int` — in **two** view files
     (`app/views/products.py`, `app/views/checkout.py`);
   - a `safe_int` helper (`app/utils/parsing.py`) plus an already-correct
     `safe_int(request.GET.get(...))` call site and a non-request `int(x)`, so
     a guard must not false-positive on the correct forms;
   - the guard plumbing: `scripts/lint/run.py` (same `RuleSpec` registry shape
     as the real repo), the shared `scripts/lint/ast_lint.py` +
     `path_utils.py` scaffold (so a rule placed under `scripts/lint/` resolves
     its sibling imports via `sys.path[0]`, exactly as the real
     `silent_catch.py` does), `.pre-commit-config.yaml`,
     `.github/workflows/ci.yml`, a `CLAUDE.md` with a "Canonical Patterns"
     section, and an empty `tests/lint/` package;
   - a **2-commit history**: commit 1 introduces the anti-pattern in both view
     files; commit 2 (the **anchor**) fixes exactly ONE of them
     (`products.py`) to use `safe_int`. The anchor lets the scorer do the
     historical-fire check via `git show <anchor>^:<file>` (pre-fix) vs
     `git show HEAD:<file>` (post-fix).

   It prints the repo path + anchor SHA + fixed-files as JSON on stdout.

2. **`install_proposal.py`** — the deterministic stand-in for the human
   reviewer executing a proposal: copies the proposal's rule + fixtures into
   the repo and applies the wiring edits (a `RuleSpec` in `run.py`, a `local`
   hook in `.pre-commit-config.yaml`, a diff-scoped CI step, a Canonical-
   Patterns bullet in `CLAUDE.md`). Separating install from score keeps the
   scorer honest: it only ever reads the resulting on-disk state.

3. **`score_conformance.py`** — the scorer. Seven checks (below), writes
   `conformance.json`, prints a human summary, and exits 0 (pass /
   pass-with-notes) or 1 (fail).

4. **`validate.py`** — end-to-end harness self-test: for each proposal it seeds
   a **fresh** repo, installs, scores, and asserts the expected verdict. The
   fresh-seed-per-proposal is what stops the two proposals from contaminating
   each other's mutated plumbing.

## Post-condition set (derived from SKILL.md Phase Pre/Post)

| ID | Check | SKILL.md anchor | Consequential? |
|----|-------|-----------------|----------------|
| C1 | `pattern.md` exists & non-empty | Phase 1 Post | cosmetic |
| C2 | rule script exists, stdlib-only, honors CLI contract (exit 2 on empty invocation, 1 on a known-bad input, 0 on clean; output line shape) | Phase 2 Post | cosmetic |
| C3 | fixture pair exists AND the real `verify_rule.py` returns 0 (BAD_RC=1, GOOD_RC=0) | Phase 3 Post | **CONSEQUENTIAL** |
| C4 | historical-fire: for each fixed file the rule FIRES on `git show <anchor>^:<file>` (hits>0) and is CLEAN on HEAD (hits==0) | Phase 6 Verification | **CONSEQUENTIAL** |
| C5 | pre-commit hook + CI step + a `RuleSpec` in `run.py` all reference the rule | Phase 4 Post | cosmetic |
| C6 | `CLAUDE.md` has a canonical-pattern bullet naming the rule | Phase 5 Post | cosmetic |
| C7 | `proposal.md` exists with Phase 6's required sections (Source cluster / Pattern / Artifacts / Verification) | Phase 6 Post | cosmetic |

### Why these two are consequential and the rest are cosmetic

- **C3** re-runs the skill's *own* differential validity gate (`verify_rule.py`,
  invoked via subprocess — never reimplemented). It proves the fixture pair is
  internally valid: the bad fixture fires, the good fixture is clean. This
  catches a rule that is too permissive (good fires) or a fixture that is empty
  (bad doesn't fire).
- **C4** is the anti-theater core. C3 only proves the rule is self-consistent
  with *its own* fixtures. C4 proves it catches the *real bug* by replaying the
  pre-anchor source through the rule and requiring it to fire — and requiring
  the post-fix HEAD to be clean. A rule whose matcher drifted away from the
  actual anti-pattern passes C1/C2/C3/C5/C6/C7 and still fails C4. That is the
  failure mode a naive "do all the files exist?" check (or even "does the
  skill's verifier pass?") cannot see.
- **C1/C2/C5/C6/C7** are *necessary but not sufficient*. Their absence makes a
  proposal incomplete (so they are reported, and a cosmetic-only failure yields
  `pass-with-notes`), but their presence does not prove the guard works.

**Verdict rule:** `fail` if ANY consequential check fails; `pass-with-notes` if
only cosmetic checks fail; `pass` if everything passes. The CLI-contract check
(C2) also verifies stdlib-only via an AST import scan that allow-lists the
stdlib + the two repo-local siblings (`ast_lint`, `path_utils`) and flags any
true third-party import (verified: a planted `import requests` is caught).

## The two proposal fixtures

Both target the seeded repo; both are hand-built, no model.

- **`fixtures/conformant/`** — a complete, correct guard. The rule
  (`no_bare_int_request.py`) matches `int(request.POST/GET.get(...))` via AST,
  ignores `safe_int(...)` (different `func` name), `int(product_id)`
  (non-request arg), and `request.headers.get(...)` (non-POST/GET attr). Bad
  fixture covers four matcher variants; good fixture covers the legitimate
  forms + an allow-listed case. Wiring + CLAUDE.md bullet + pattern.md +
  proposal.md all present.

- **`fixtures/defective/`** — identical structure with ONE injected
  consequential defect: the matcher only recognises the **subscript** form
  `int(request.POST["k"])`, never the `.get(...)` *method* form the real bug
  (and the seeded anchor) uses. Its bad fixture is tailored to the subscript
  form, so it is **self-consistent** — `verify_rule.py` (C3) still passes
  (BAD_RC=1, GOOD_RC=0). Its `proposal.md` even *claims* historical regression
  fired. Every other artifact is present and correct. Only C4 exposes it: the
  rule fires zero times on the pre-anchor `products.py`.

This is the instructive case: the defect looks done, survives file-existence
checks, and survives the skill's own fixture verifier — but is caught by the
historical-fire replay.

## Actual scorer output

Reproduce with (paths absolute; uses the shared `.venv`):

```bash
python3 scripts/skill_comply/validate.py
```

### conformant → all-pass

```
Conformance scorecard — no-bare-int-request
  C1  PASS  [cosmetic]       pattern.md exists & non-empty
        └─ .../conformant/pattern.md present, 1461 bytes
  C2  PASS  [cosmetic]       rule script + CLI contract
        └─ empty_rc=2 (exp 2), bad_rc=1 (exp 1), clean_rc=0 (exp 0), output_format_ok=True, stdlib_only=True
  C3  PASS  [CONSEQUENTIAL]  fixture pair + verify_rule.py
        └─ verify_rule rc=0; bad ... rc=1 hits=4 | good ... rc=0 hits=0 | PASS: BAD_RC=1, GOOD_RC=0, fixtures behave as expected.
  C4  PASS  [CONSEQUENTIAL]  historical-fire
        └─ app/views/products.py: pre-anchor hits=2 (need >0), HEAD hits=0 (need 0) → OK
  C5  PASS  [cosmetic]       pre-commit + CI + run.py wiring
        └─ run.py RuleSpec=yes, pre-commit hook=yes, CI step=yes
  C6  PASS  [cosmetic]       CLAUDE.md canonical-pattern entry
        └─ Canonical Patterns section=yes, rule named in a bullet=yes
  C7  PASS  [cosmetic]       proposal.md exists with required sections
        └─ all required sections present
  VERDICT: PASS
```

### defective → fail on exactly the seeded check (C4)

```
Conformance scorecard — no-bare-int-request
  C1  PASS  [cosmetic]       pattern.md exists & non-empty
  C2  PASS  [cosmetic]       rule script + CLI contract
        └─ empty_rc=2 (exp 2), bad_rc=1 (exp 1), clean_rc=0 (exp 0), output_format_ok=True, stdlib_only=True
  C3  PASS  [CONSEQUENTIAL]  fixture pair + verify_rule.py
        └─ verify_rule rc=0; bad ... rc=1 hits=2 | good ... rc=0 hits=0 | PASS: BAD_RC=1, GOOD_RC=0, fixtures behave as expected.
  C4  FAIL  [CONSEQUENTIAL]  historical-fire
        └─ app/views/products.py: pre-anchor hits=0 (need >0), HEAD hits=0 (need 0) → FAIL
  C5  PASS  [cosmetic]       pre-commit + CI + run.py wiring
  C6  PASS  [cosmetic]       CLAUDE.md canonical-pattern entry
  C7  PASS  [cosmetic]       proposal.md exists with required sections
  VERDICT: FAIL
```

`validate.py` additionally asserts the verdicts and that the *only* failing
consequential check for the defective case is exactly `C4`:

```
  [conformant] expectation check: verdict OK; consequential failures got [] want [] → OK → VALIDATED
  [defective]  expectation check: verdict OK; consequential failures got ['C4'] want ['C4'] → OK → VALIDATED
  OVERALL: PASS
```

Note C3's hit counts differ between the two (conformant bad = 4 variants;
defective bad = 2 subscript variants) — both self-consistently pass their own
verifier. The discriminating signal is entirely C4.

## Reproducibility & isolation

- Each `validate.py` run re-seeds a fresh `mkdtemp` repo per proposal and
  removes it afterward (`--keep` to retain for inspection). The two proposals
  never share a repo, so installing one cannot contaminate the other.
- The seed uses a hermetic git identity (`GIT_AUTHOR_*` env), so it does not
  depend on global git config and produces a stable structure run-to-run (the
  anchor SHA varies by timestamp, which is fine — the scorer is told the SHA).
- All four scripts are stdlib-only and run under the shared
  `.venv/bin/python` (the worktree shares the main checkout's `.venv`).

## Honest limitations — what this does NOT yet prove

- **No real model execution.** This validates the *instrument* against
  hand-built proposals. It has not yet graded an actual `/prevent-regression`
  run by a model. Stage 1b/2 (human-orchestrated) feeds a real run's output
  directory into the same scorer.
- **Single anti-pattern, single skill, single defect.** One rule shape
  (`safe_int`), one seeded bug, one injected defect (matcher drift → C4). Other
  defect classes are not yet exercised: e.g. a good fixture that secretly
  contains a live anti-pattern (would fail C3), a rule that fires on HEAD too
  (over-broad — C4's HEAD-clean clause catches it, but untested here), wiring
  that references a *different* rule name, or a ruff-coverable pattern that
  should not get a custom script at all (Phase 1 "Ruff-first" branch — not
  modeled).
- **Clarification-stall risk is unmodeled.** SKILL.md Phase B/Form-B can pause
  for a clarification round. A real run that stalls asking a question produces
  no artifacts; the scorer would simply fail every check. The harness does not
  distinguish "stalled awaiting input" from "ran and produced nothing" — a real
  orchestration layer must.
- **Install fidelity is a stand-in.** `install_proposal.py` applies wiring the
  way a disciplined human would; a real run might wire differently (different
  hook `files:` regex, CI shape). C5 only greps for the rule name in each
  surface, so it tolerates reasonable variation but would not catch a
  *semantically* wrong scope regex.
- **C2's "known-bad input" is the proposal's own bad fixture.** This keeps C2
  about CLI mechanics, but it means C2 trusts the proposal to ship a bad
  fixture its rule fires on. C3/C4 are the checks that don't extend that trust.
- **No ruff / pyproject branch.** The seed models the custom-AST-rule path
  only. A guard that should be a `pyproject.toml` ruff-enable (SKILL.md
  Phase 1 "Ruff-coverable") has no fixture here.

## Stage 1b: first real model run (uncoached)

A `sonnet` sub-agent followed `prevent-regression/SKILL.md` against a freshly
seeded repo (anchor `c2625b15`), with **no knowledge of the scoring rubric**.
Its proposal was installed through `install_proposal.py` and graded by
`score_conformance.py`. The model's output is preserved verbatim under
`runs/stage1b-sonnet/`.

**Result: VERDICT PASS — all 7 checks, including both consequential gates.**

```
C3  PASS  [CONSEQUENTIAL]  verify_rule rc=0; bad rc=1 hits=6 | good rc=0 hits=0
C4  PASS  [CONSEQUENTIAL]  app/views/products.py: pre-anchor hits=2 (>0), HEAD hits=0 → OK
```

The loop runs end-to-end on a real, non-hand-built artifact: seed → model
follows playbook → install → side-effect score. An uncoached model, given the
skill plus the real fix, produced a guard that genuinely fires on the bug it
was built for (C4) — it did not cut the corner the defective fixture models.

### What the scorer PASS does NOT prove (review findings)

Side-effect conformance is necessary, not sufficient. Reading the produced rule
(`runs/stage1b-sonnet/scripts/lint/no_bare_int_request.py`) surfaces three
things C1–C7 structurally cannot see — exactly the quality axis a review lane
owns:

- **Over-broad match.** It fires on ANY `int(request.<attr>.get(...))` —
  including `request.session.get(...)` / `request.headers.get(...)` /
  `request.COOKIES.get(...)`, not just the user-input `POST`/`GET` the pattern
  targets. Potential false positives on server-trusted request attributes.
- **Under-broad receiver.** It requires the literal name `request`, so
  `self.request.POST.get(...)` (class-based / DRF views) and aliased receivers
  are silently missed. A real recall gap.
- **Non-idiomatic import scaffolding.** It ships a bespoke `_find_scripts_lint`
  parents-walk to resolve `ast_lint`, where every existing rule (`silent_catch`)
  just relies on `sys.path[0]`. This is an artifact of the harness's
  proposal-dir/install split (the rule is tested five levels deep before being
  copied next to `ast_lint`), and it violates "read like the surrounding code."

None of these break the seeded test, and none would be caught by a side-effect
scorer — they need artifact review. **Conclusion:** skill-comply verifies the
consequential *mechanism* fired; it is complementary to, not a replacement for,
a quality review lane. The harness's own install/score split also *induced* the
import workaround — a note for Stage 2 (author the rule in-place under the
repo's real `scripts/lint/`, then test, so the rule reads like its neighbors).
# skill-comply — Stage 2: hardening the instrument (depth pass)

Stage 1 built a measurement instrument and validated it against one conformant
and one defective proposal. Stage 2 chose **depth over breadth**: instead of
adding telemetry around the existing scorer, it adds adversarial defect fixtures
that span the verdict space. That choice paid for itself three ways — it forced
one consequential addition to the rubric (**C8**), it surfaced a real bug in the
scorer itself, and re-grading the Stage-1b Sonnet run under the hardened rubric
**converts review-finding #1 into a deterministic machine catch**.

## What changed at a glance

- **New consequential check `C8` — bounded incidental firing.** A guard that
  over-fires on innocent code now fails, where before it passed.
- **Three new fixtures** (`over-broad`, `poisoned-good`, `wrong-name`) that, with
  the original two, cover the whole verdict space (pass + four distinct failure
  routes).
- **One scorer-robustness fix** — hit-counting now parses the rule **tag field**
  instead of substring-matching the whole line. The `wrong-name` fixture found
  this; without the fix it scored a false PASS.
- **One seed addition** — a benign decoy file (`app/services/cart.py`) that a
  correctly-scoped rule must ignore and an over-broad one trips on.
- **Sonnet re-score** — the Stage-1b run that passed all 7 checks now **fails
  C8** under the hardened rubric.

## C8: bounded incidental firing (the new consequential check)

**What it does.** Run the installed rule across its *whole enforcement scope* —
every `.py` file matching the manifest `include_regex` and not `exclude_regex` —
and require every file it fires on to be in `antipattern_files` (the known
anti-pattern sites). Any hit on an in-scope file *outside* that set is a "stray"
hit and fails the check. C8 is skipped (pass) when no `antipattern_files` are
supplied, and passes vacuously if no in-scope files exist.

**Why it is consequential, not cosmetic.** Stage 1's anti-theater core was C4:
*a guard that does not fire on the bug it was built for is theater.* C8 is the
mirror image, and the definition of "consequential" widens to hold both halves:

> A guard does its job durably only if it **both** (a) fires on the bug (C4)
> **and** (b) stays quiet on clean code (C8). A guard that cries wolf on
> legitimate code gets `# noqa`'d into silence or deleted outright — and then
> protects nothing. Over-firing predicts the guard's *removal*, so it is a
> correctness failure, not a style nit.

**It corrects a Stage-1 assumption.** STAGE1.md's limitations list supposed an
over-broad rule would be caught by "C4's HEAD-clean clause." It is not. C4 only
inspects the *fixed files* (`products.py`), which are clean on HEAD whether or
not the rule is over-broad — the over-breadth manifests on *unrelated* in-scope
files (the decoy), which C4 never examines. C8 is the actual mechanism, and the
Sonnet re-score below is the proof.

**The decision is one line reversible.** C8 is a single `card.add(...)` in
`score()`. Deleting that line reverts to the exact 7-check rubric. The cost of
adopting it is therefore low and the rollback is trivial — which is the bar for
adding a consequential gate rather than leaving a finding to the review lane.

## The benign decoy (seed change)

`seed_fixture.py` now writes `app/services/cart.py`:

```python
def page_size_from_session(request) -> int:
    return int(request.session.get("page_size", 20))   # server-side state, not user input

def retry_budget(config) -> int:
    return int(config.get("retries", 3))                # plain mapping, not request.*
```

Neither line is in `antipattern_files`. A rule correctly scoped to
`int(request.POST/GET.get(...))` ignores both (`.session` is not POST/GET;
`config` is not `request.<attr>`). `cart.py` is in C8's scope via
`^app/(services|views|pages|api)/.*\.py$` but absent from `antipattern_files`,
so *any* hit there is by definition stray. The `conformant` fixture's C8 passing
(cart.py → 0 hits) confirms the decoy is genuinely benign — C8 is not an
always-fail check.

## Verdict-space fixtures (the depth)

| Fixture | Verdict | Consequential fail | What it models |
|---|---|---|---|
| `conformant`   | **pass** | — | a complete, correct guard |
| `defective`    | **fail** | C4 | matcher drift — subscript-only matcher misses the `.get()` bug |
| `over-broad`   | **fail** | C8 | fires on innocent code — the hole C8 closes |
| `poisoned-good`| **fail** | C3 | the "clean" good fixture hides a live anti-pattern (`verify_rule` GOOD_RC=1) |
| `wrong-name`   | **fail** | C4 | emitted tag drifts from the wired name → historical-fire counts 0 |

`defective` and `wrong-name` deliberately share the **C4** failure signature:
both produce zero historical-fire hits, one because the matcher is wrong and one
because the *tag* the scorer counts by is wrong. They are distinguishable only by
the cosmetic **C2** line (output-format/tag check), which `wrong-name` now fails
and `defective` passes. That a tag-drifted rule and a logic-drifted rule look
identical at the consequential layer is itself a finding — see next section.

## The scorer bug the depth pass found (and fixed)

`wrong-name` was designed to fail **C4**: its rule emits the tag
`no-bare-int-req`, drifted from the wired/manifest name `no-bare-int-request`, so
the historical-fire counter — which counts violations tagged with the wired name
— should see **zero** and fail. It initially scored a false **PASS**.

**Root cause.** `_count_hits` / `_hit_files` substring-matched `": <rule_name>: "`
against the *entire* output line. The rule's own message body echoes the wired
name inside its allow-list hint:

```
app/views/products.py:9:18: no-bare-int-req: bare int(...) — ... (allow-list: # noqa: no-bare-int-request: <reason>)
                            └─ emitted tag (drifted)                          └─ wired name, in the MESSAGE
```

The substring `": no-bare-int-request: "` is present *in the message text*, so
the drifted-tag line counted as a hit anyway → C4 saw 2 hits → false pass. The
message masked the very drift the fixture was built to expose.

**Fix.** Parse the **tag field** specifically. `_parse_violation` splits
`path:line:col: tag: msg`, requires the locator (`path:line:col`) to carry
exactly two colons so message text can never masquerade as the tag, and returns
`(path, tag)`. Hit counting now compares `tag == rule_name` exactly; C2's format
check uses the same parse. After the fix `wrong-name` fails C4 (now
`pre-anchor hits=0`) and C2 as designed, and the other four fixtures are
unchanged. This is the depth pass earning its keep: an adversarial fixture found
a real imprecision in the *measurement instrument*, not merely in a rule.

## Re-grading the Stage-1b Sonnet run under the hardened rubric

The Sonnet rule (preserved verbatim under `runs/stage1b-sonnet/`) matches
`int(request.<any-attr>.get(...))` — it requires the receiver be
`request.<something>` but never restricts `<attr>` to `POST`/`GET`. Under the
7-check rubric it **passed** (Stage 1b). Under the hardened rubric it **fails
C8**:

```
C3  PASS  [CONSEQUENTIAL]  bad rc=1 hits=6 | good rc=0 hits=0 → fixtures self-consistent
C4  PASS  [CONSEQUENTIAL]  app/views/products.py: pre-anchor hits=2 (>0), HEAD hits=0 → OK
C8  FAIL  [CONSEQUENTIAL]  scanned 5 in-scope file(s); hit files=['app/services/cart.py',
          'app/views/checkout.py']; allowed (anti-pattern)=['app/views/checkout.py',
          'app/views/products.py']; STRAY (over-broad) hits in: ['app/services/cart.py']
VERDICT: FAIL
```

`cart.py`'s `int(request.session.get(...))` is the stray hit. This is exactly
Stage-1b **review-finding #1** ("over-broad match … potential false positives on
server-trusted request attributes") converted from a human-eyeball note into a
deterministic side-effect catch.

The asymmetry is the point: **C3 and C4 still pass.** The rule *is*
self-consistent with its own fixtures (C3) and *does* fire on the real bug (C4).
The over-breadth is invisible to the skill's self-chosen fixtures — an author who
believes `request.<any>.get` is the pattern writes fixtures that confirm it — and
surfaces only when C8 runs the rule against *independent* in-scope code. That is
why C8 must scan the enforcement scope, not just re-check the proposal's
fixtures. (Reproduce by running the `seed → install → score` pipeline against
`runs/stage1b-sonnet/`; `conformance.json` there is regenerated, gitignored.)

## What Stage 2 still does NOT close (honest limitations)

- **C8 presumes a curated `antipattern_files` set, and skips *silently* without
  one.** In the fixture world the seed manifest supplies the ground-truth "files
  the rule may legitimately fire on," so C8 always runs. A real
  `/prevent-regression` run has no such oracle — "which files genuinely contain
  the pattern" is partly what the rule is *for*. The defensible production
  sources are the anchor's `fixed_files` (∪ reviewer-confirmed follow-on sites)
  or a curated benign-decoy corpus; either way a human or an upstream step must
  commit to the firing scope. Worse, the current contract treats a missing
  allowlist as **pass** (skip), so an orchestration that forgets to pass it gets
  a green C8 with the over-firing check quietly gone. A production layer must
  treat "C8 skipped" as a distinct, surfaced state — not a silent pass.
- **Recall / under-broad — Stage-1b finding #2, still review-only.** The Sonnet
  rule requires the literal name `request`, so `self.request.POST.get(...)`
  (class-based / DRF views) and aliased receivers are silently missed. C8 is a
  **precision** check (no stray *firing*); it cannot see a false **negative** on
  a variant the rule *should* match but doesn't. Catching that needs a *recall*
  fixture — a known anti-pattern instance the rule must fire on and fails to —
  which is a different mechanism, not built here.
- **Style / idiom — finding #3, still review-only.** The bespoke
  `_find_scripts_lint` import walk reads nothing like the neighboring
  `silent_catch`. Side-effect scoring cannot grade "reads like its neighbors."
  (Stage 1 already traced this to the install/score split; the in-place-authoring
  note stands.)
- **The ruff-coverable Phase-1 branch is still unmodeled — deliberately.**
  SKILL.md's Phase 1 "Ruff-first" decision says some guards should be a
  `pyproject.toml` ruff-enable, *not* a custom script. That branch is **not
  mechanically scoreable by this instrument**: there is no rule script, no
  `verify_rule` fixture pair, and no historical-fire replay — the "artifact" is a
  one-line config enablement whose correctness is "ruff already implements this."
  Grading it means asserting a *negative* (no bespoke script should exist) plus
  that the enabled ruff code id actually covers the pattern — a config-diff +
  rule-id-lookup instrument, not this one. Out of scope for the side-effect
  scorer; flagged as a separate future probe rather than forced into a fixture.
- **Still single skill, single anti-pattern family.** The verdict space is now
  well-covered for one rule shape (`safe_int`); cross-skill generality is
  unproven.

## Follow-ups (pended)

Captured here as ideas rather than spun out as separate ledger entries. None
blocks the Stage 1–2 result; each waits on an asset or a decision we don't have
now.

1. **C8 production-readiness + the recall axis (one bundle).** Solve the
   `antipattern_files` oracle — where the legitimate-firing set comes from in a
   real run (anchor `fixed_files` ∪ reviewer-confirmed sites, or a curated
   benign-decoy corpus) — and make "C8 skipped" a surfaced state, not a silent
   pass. Stage-1b finding #2 (under-broad receiver, e.g. `self.request`) is a
   *recall* check that needs the same ground-truth oracle, so it lands here, not
   as a standalone fixture.
2. **Stage 3: real-run orchestration at scale.** Stage 1b proved one uncoached
   model run scores end-to-end; driving many real `/prevent-regression` runs
   needs an orchestration layer — including a way to distinguish "stalled
   awaiting clarification" from "ran and produced nothing."
3. **Ruff-coverable branch as a separate probe.** Needs a different instrument
   (config-diff + ruff-rule-id coverage assertion), not the side-effect scorer.
4. **Cross-skill generality.** Everything so far is one skill / one anti-pattern
   family; a second skill would test whether the rubric travels.

## Actual harness output

`validate.py` runs all five fixtures end-to-end (fresh seed → install → score
per fixture) and asserts each verdict *and* its exact consequential-failure set:

```
== Harness summary ==
  conformant   PASS
  defective    PASS
  over-broad   PASS
  poisoned-good PASS
  wrong-name   PASS

OVERALL: PASS
```

`PASS` here means "scored as expected," not "verdict pass" — four of the five are
expected *fails*, each on its designated consequential check (see the
verdict-space table above). The harness asserts both the verdict *and* the exact
set of failing consequential checks, so a fixture that fails for the wrong reason
is caught too.

## Reproducibility & artifacts

- All five fixtures: `.venv/bin/python scripts/skill_comply/validate.py`.
- Every `conformance.json` (fixtures and the Sonnet run) is a **gitignored
  byproduct**, regenerated each run; the durable results live in this doc. The
  scorer, seed, install, and the five proposal directories are the tracked
  artifacts.
- The harness remains stdlib-only and runs under the shared `.venv`
  (Python 3.10+ — the C2 import scan needs `sys.stdlib_module_names`).
