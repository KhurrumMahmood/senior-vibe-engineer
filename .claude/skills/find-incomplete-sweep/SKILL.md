---
name: find-incomplete-sweep
description: |
  Advisory SUSPECT scan for incomplete sweeps — multi-site changes that were
  started but never finished, leaving a forgotten sibling call site at the old
  shape ("updated N-1 of N"). v0 implements one band: keyword-argument
  omission — among the call sites of one callee, a keyword the strong majority
  of siblings pass but one straggler does not. Gated on a git-trajectory
  signal: a divergence counts as a forgotten sweep only when the
  kwarg-present sites were touched more recently than the straggler (the sweep
  landed after the straggler was last edited). A straggler edited just as
  recently is reported separately as likely-deliberate. Distinguishes
  abandoned partial work from legitimate post-completion cleanup via residue
  direction. Detection-only — never edits code; hands off to /fix-workflow.
argument-hint: "[--band kwarg|placeholder|all] --paths scripts ... [--min-callsites 4] [--majority-frac 0.75] [--min-present 3] [--max-age-days 120] [--out DIR] [--no-gate]"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: suspect
language: python
framework: any
best_for: |
  Reviewing a human- or AI-authored multi-file change where a sweep across
  sibling call sites may have stopped short: a new keyword argument threaded
  through some callers, a proxy/config param added to some call sites, an
  option passed at most but not all of a callee's call sites. The straggler is
  fully live (old shape still referenced and executing), so /find-dormant
  cannot see it. The git-trajectory gate keeps the signal to recently-swept
  divergences rather than long-stable intentional asymmetry.
not_for: |
  Single-site / one-line changes (no cluster, no sweep) — proceed directly.
  Declared-intent vs realized-state drift at the plan / idea / ADR / contract
  granularity (use /find-orphaned-ideas, /find-stale-artifacts,
  /audit-decisions).
  Implemented-but-unwired dead code (use /find-dormant) — that is the
  unreferenced half; this is the over-referenced-at-old-shape half.
  Sameness-based duplication to unify (use /find-semantic-duplication or
  /unify-shadows) — this is divergence-within-cluster, not both-live sameness.
  Missing enum TYPE declaration (use /find-implicit-state).
  Refactor execution (this is detection only; hand off to /fix-workflow).
escalate_to: |
  /fix-workflow cluster:<finding> — completes the sweep (applies the majority
  shape to the straggler) under regression-test-first, two-commit discipline.
  /prevent-regression — when a forgotten-sweep type recurs, graduate the
  invariant to a diff-scoped lint so the next omission is caught at commit
  time, not by a later scan.
delegate_from: |
  /which-cleanup — a diff that looks like a multi-site sweep routes here.
  /triage-debt — debt aggregation may direct here.
---

# /find-incomplete-sweep

Detects **forgotten call sites** — a change applied to N-1 of N
structurally-similar sites, leaving one sibling at the old shape. The
straggler still works and is still referenced, so nothing else flags it.

The architectural framing — why "looks unfinished" is the wrong target and
"dangling edge in recently-touched code" is the right one, and how the
git-trajectory gate separates *abandonment* from *post-completion cleanup* —
is captured in the bands and gate sections below.

## Bands

Two detector bands, selected with `--band` (default `kwarg`):

- **`kwarg`** (v0, default) — *keyword-argument omission*. Among a callee's call
  sites, a keyword the strong majority pass but one straggler does not, gated on
  git-trajectory. Output: `findings.md` + `manifest.json` (the files `scout.py`
  consumes).
- **`placeholder`** — *placeholder residue*. A concrete (non-ABC/Protocol/
  `@abstractmethod`) function/method scaffolded but never filled in
  (`raise NotImplementedError`, `pass`/`...`/docstring-only body,
  `return None  # TODO` stub, empty test body), gated by recency + reference-
  asymmetry. Output: `placeholder_findings.md` + `placeholder_manifest.json`
  (separate files, so the kwarg band's scout input is never disturbed).
- **`all`** — run both.

## Invocation

`--paths` is required — there is no default scan root, so a wrong default can
never silently scan nothing. Pass one or more source roots (e.g. `scripts`).
Relative paths anchor on `--project-root` (default: git toplevel of the cwd,
else the cwd); the resolved root is recorded in `manifest.json` so `scout.py`
re-anchors the same way.

```bash
# Codebase audit (default): cluster every callee, flag kwarg-omission stragglers
.venv/bin/python .claude/skills/find-incomplete-sweep/scripts/scan.py \
  --band kwarg --paths scripts --out reports/find-incomplete-sweep/scan-$(date +%Y%m%d-%H%M%S)

# Placeholder-residue band (recent referenced stubs in concrete code)
.venv/bin/python .claude/skills/find-incomplete-sweep/scripts/scan.py \
  --band placeholder --paths scripts --out reports/find-incomplete-sweep/scan-$(date +%Y%m%d-%H%M%S)

# Faster pass without the git-trajectory discriminator (raw candidates only)
.venv/bin/python .claude/skills/find-incomplete-sweep/scripts/scan.py \
  --paths scripts --no-gate

# From outside the target repo, anchor explicitly
.venv/bin/python .claude/skills/find-incomplete-sweep/scripts/scan.py \
  --paths scripts --project-root /path/to/target
```

Output (kwarg band): `findings.md` (gated-IN forgotten sweeps + gated-OUT
likely-deliberate) and `manifest.json`.

### Detector pre-filters (kwarg band, deterministic — never reach the scout)

Before the git-trajectory gate, the kwarg band sets aside divergences that are
valid *by construction*, so the scout's residual is real-straggler-dense.

**Hard drops** (not a forgotten sweep by definition — never surface):

- **query-lookup callees** (`.get`/`.filter`/`get_object_or_404`/…) — kwargs
  select WHICH row, not a convention. (These names are Django-flavored but
  inert on non-Django code — they simply never match.)
- **optional-by-nature kwargs** (`args`/`kwargs`/`using`/`update_fields`).
- **arg-count-illegal kwargs** (`values_list(flat=True)` with >1 column).

**Down-rank** (reported in a separate section, never gated in): **dataclass-/
signature-default fields** — when the callee resolves (within the scanned paths)
to a `@dataclass` whose omitted field has a declared default, or a class
`__init__` / function whose omitted param has a default, the straggler simply
took the default. This is the dominant residual false-positive class (result-
shape `error=`, optional builder fields whose value defaults). It is
**down-ranked, not dropped**: these land in the **Down-ranked** section of
`findings.md`, excluded from gated-in.

**Value-awareness** (the flagship promoter, *implemented*): the detector
captures each call site's argument VALUE (via `ast.unparse`) and the callee's
declared default value. A down-ranked finding is **promoted back to a normal
gated-in candidate** when the kwarg-present siblings ALL pass the *same* value
**and** it differs from the default — the straggler then took a *different*
(default) value, which is the flagship forgotten override (`country_code='us'`
on 6/7 calls where the default isn't `'us'`; `list_mode='full'` where the
default is `'per_element'`). When the siblings' values vary, equal the default,
or aren't comparable (`default_factory`, name collisions), it stays down-ranked.
Promoted findings carry a `value-override:` line in the report.

## Scout stage — judge each gated-in finding

The detector is deterministic and gates noise hard, but its surviving
gated-in set still **mixes two kinds**: genuine forgotten stragglers (a kwarg
the sweep should have threaded but missed) and divergences that are valid by
nature — an optional dataclass field the straggler legitimately omits, a
result-shape success/error branch, a semantically-equivalent idiom. Telling
those apart is irreducibly judgment — so it is a **scout fan-out**, exactly
like `/find-duplication` and `/find-semantic-duplication`: the script detects,
the scouts judge, the orchestrator ranks.

### Step A — build scout packets (deterministic)

```bash
.venv/bin/python .claude/skills/find-incomplete-sweep/scripts/scout.py \
  --scan-dir reports/find-incomplete-sweep/scan-<TS> --paths scripts \
  [--project-root DIR]
```

`scout.py` reads the scan's `manifest.json`, takes only the **gated-in**
findings, and for each writes a self-contained **packet** to
`<scan-dir>/scout_packets.json`: the straggler's code window (`>>`-marked
call line ± 8 lines), 1–2 present-site windows (siblings that DO pass the
kwarg, so shapes are comparable), and the divergence metadata (callee, kwarg,
`majority_frac`, `group_size`, trajectory note). It re-derives present-site
locations by importing `scan.py`'s collector — detection logic is never
duplicated. The judge reads packets; it does **not** re-derive evidence.
(`--paths` must match the original scan so the present-site index is identical.)

### Step B — fan out one judgment per packet

This is the **only stage where judgment runs**. Dispatch one investigation per
packet (`subagent_type=general-purpose`, batch in a single message; or, on a
small set, judge them inline). Each judge reads its packet plus
`reference/scout-rubric.md` and returns one verdict from this fixed vocabulary:

| verdict | meaning | action |
|---|---|---|
| `forgotten` | real straggler — the sweep should have reached it | complete the sweep |
| `deliberate` | intentional exception — straggler is a different code path (success-vs-error branch, equivalent idiom, ABC override) | leave; note why |
| `optional` | the kwarg is optional-by-nature; the present sites pass a *non-default* value, the straggler is fine with the default | leave |
| `not-applicable` | the kwarg is illegal / impossible at this site (wrong arity, multi-column select, type clash) | leave |

Each verdict carries a one-line rationale; `forgotten` also carries a
suggested completion (the exact kwarg to add).

The full decision rubric — including the dominant trap that the
result-shape and optional-dataclass classes mimic a forgotten sweep — is in
`reference/scout-rubric.md`. Keep it out of the orchestrator's context; it is
the judge's brief.

### Step C — rank and hand off

Write `<scan-dir>/triaged.md`, **forgotten-first** (then `deliberate` /
`optional` / `not-applicable`, each with rationale). Forgotten findings hand
off to `/fix-workflow cluster:<finding>`; a recurring forgotten *type* graduates
to `/prevent-regression`. `deliberate` / `optional` / `not-applicable` are the
proof the scout layer collapses the detector's residual false-positive class —
they are recorded, not actioned.

## The gate is the point

A raw "these sites differ" list is mostly natural variation — noise. The
**git-trajectory gate** is what makes a finding trustworthy: it keeps only
divergences where the kwarg-present siblings were touched *after* the
straggler, i.e. a sweep that landed after the straggler was last edited.
Divergences where the straggler is just as fresh are surfaced separately as
likely-deliberate (an intentional exception), not asserted as bugs.

## Placeholder-residue band (`--band placeholder`) — experimental

The placeholder band catches the *other* incomplete-execution residue: a
concrete function/method scaffolded but never filled in, while the surrounding
code moved on and now calls it as if done. It is **not** `/find-dormant`
(unreferenced code) or `/find-orphaned-ideas --todo` (raw TODO markers) — its
niche is *referenced-but-stub in recently-touched concrete code*.

Two precision gates, both required to gate IN (or it just spews noise):

1. **Recency** — a stub stable longer than `--max-age-days` (default 120) is
   accepted design debt, not abandonment. Gated OUT.
2. **Reference-asymmetry** — the stub must be referenced by name elsewhere
   (called as if complete) OR be an empty method among same-name siblings that
   *are* implemented. A stub that is neither is dead scaffolding → route to
   `/find-dormant`, not here.

Abstract contracts (`@abstractmethod`/`@overload`, ABC/Protocol bodies) are
excluded outright — they are intentional, not residue.

**Honest precision posture (kept behind `--band`, marked experimental).** The
band is verified to *fire* on a recent referenced stub (regression test
`test_ph5_recency_reference_gate`), but a codebase whose stubs are all stable
base-class template methods will report clean rather than inventing noise
(precision over coverage). Because its real-world hit count is unproven, it
stays an opt-in band, not part of the default run, until a real recent stub
validates it in the field. Output is written to separate `placeholder_*` files;
there is no scout layer for it yet (the gates are decisive enough that a
gated-in hit is directly actionable).

## Roadmap (still unbuilt)

- **broken structural bonds** — migration↔field, serialize↔deserialize,
  written-but-never-read. The fourth bond, *referenced-but-stub*, is
  already built — it **is** the placeholder band's gated-in criterion. The
  remaining three are heterogeneous and lower-precision: each needs cross-file
  dataflow / schema correlation that is FP-prone without real ownership
  resolution, so they are deferred rather than shipped half-precise.

This skill **catches** a half-done sweep after the fact; the natural complement
is a guard that **prevents** a half-done sweep up front — graduate a recurring
forgotten-sweep type to a diff-scoped lint via `/prevent-regression`.

Pairs with `/rename-concept`: this **catches** a half-done sweep; that
**prevents** a half-done concept rename (same failure — partial execution — at
two altitudes).
