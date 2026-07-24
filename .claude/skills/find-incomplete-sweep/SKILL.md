---
name: find-incomplete-sweep
description: |
  Advisory SUSPECT scan for incomplete sweeps — multi-site changes that were
  started but never finished, leaving a forgotten sibling call site at the old
  shape ("updated N-1 of N"). Python retains the keyword-argument omission
  band; TypeScript/TSX and checked JavaScript use the host-pinned TypeScript Compiler API to group
  resolved project function calls by object-option property presence; Go uses host Go `go/types`
  for one direct top-level function / keyed struct-option shape; Java 17 uses the JDK
  compiler tree API for one direct record/options-constructor shape; PHP uses
  bounded Composer PSR-4 direct constructions; Ruby requires project-authored
  RBS constructor contracts; Kotlin/JVM uses pinned direct constructor-call
  facts; Rust uses
  compiler-resolved direct calls for one struct-option omission shape; Dart
  uses SDK-LSP-resolved top-level calls for one named-argument omission shape. Gated on a git-trajectory
  signal: a divergence counts as a forgotten sweep only when the
  kwarg-present sites were touched more recently than the straggler (the sweep
  landed after the straggler was last edited). A straggler edited just as
  recently is reported separately as likely-deliberate. Distinguishes
  abandoned partial work from legitimate post-completion cleanup via residue
  direction. Detection-only — never edits code; hands off to /fix-workflow.
argument-hint: "Python: [--band kwarg|placeholder|all] --paths scripts ...; TypeScript/JavaScript: --target src --tsconfig <config>; Go/Java/Rust/Dart: --target . --report-dir reports/find-incomplete-sweep/<name>"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: suspect
language: any
framework: any
scans: [python, typescript, javascript, go, java, kotlin, csharp, php, ruby, rust, dart, c, cpp]
install_with: [map-subsystem]
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

## C# semantic branch

Run the sibling `_csharp-semantic` provider from its guide, then enter through
`scripts/detect_csharp_incomplete_sweep.py`; `knowledge/csharp-v1.md` gives
the exact consumer command. A lead is one bounded optional-constructor-
parameter omission shape among selected direct calls. It does not establish
change chronology, developer intent, project-wide completeness, or edit
authority.

## Kotlin/JVM 2.4.10 branch

Trigger this branch only for an exact `kotlin-semantic-project.json` target.
Keep sibling `_kotlin-semantic`, read
[`../_kotlin-semantic/GUIDE.md`](../_kotlin-semantic/GUIDE.md), produce its
pinned fact pack, then enter through
`scripts/detect_kotlin_incomplete_sweep.py`. It reports one omitted defaulted
parameter across resolved direct selected-source constructor calls; the
deprecated K1 API is not a stable Analysis API. Factories,
callable references, overrides/delegation, reflection, generated/plugin inputs,
Gradle variants, Java/external callers, runtime behavior, history, and fixes
remain unresolved.

## C++20 branch

Use `scripts/detect_cpp_incomplete_sweep.py` with `_cpp-semantic` and a
candidate-hash-bound human verdict; run it with `--help` for the exact CLI. It
checks one direct designated-aggregate return shape under a current complete
C++20 compiler-owned graph with exact namespace/signature/overload identity.
ODR/ABI, specialization, dispatch, external variants, and automatic fixes stay
outside the claim.

## C17 branch

Use `scripts/detect_c_incomplete_sweep.py` with the sibling `_c-semantic`
provider and a candidate-hash-bound human verdict; run the script with `--help`
for the exact CLI. This external-library branch supports one direct designated-
initializer omission shape only; macros, aliases, wrappers, external callers,
incomplete history, variants, and automatic fixes remain unresolved.

## PHP and Ruby

For a selected PHP or Ruby run, load `../_php-semantic/GUIDE.md` or
`../_ruby-semantic/GUIDE.md`. These branches admit only bounded direct
constructor omissions; dynamic/framework call sites and automatic fixes remain
outside the contract.

## Dart v1

Dart v1 uses the sibling `map-subsystem` SDK-LSP provider to group direct
calls that resolve to one top-level function. It admits one narrow shape: at
least three of four sites pass the same comparable named-argument value, one
omits it, and every present site is newer in Git than the straggler. The
detector writes candidates only; `scout.py` and `triage.py` preserve the fixed
human-verdict workflow. Copy sibling `map-subsystem` with this skill.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-incomplete-sweep"
REPORT_DIR="$PWD/reports/find-incomplete-sweep/dart"
python3 "${SKILL_ROOT}/scripts/detect_dart_incomplete_sweep.py" \
  --project-root "$PWD" --target lib --report-dir "$REPORT_DIR"
python3 "${SKILL_ROOT}/scripts/scout.py" \
  --scan-dir "$REPORT_DIR" --project-root "$PWD"
# Write one fixed-vocabulary verdict per packet, then:
python3 "${SKILL_ROOT}/scripts/triage.py" --scan-dir "$REPORT_DIR"
```

Wrappers, aliases, methods, cascades, extension/dynamic dispatch, runtime
behavior, generated/test/vendor/example code, incomplete Git evidence, and
automatic fixes remain outside this contract.

## Rust v1

Rust v1 emits one compiler-resolved direct-call/struct-option omission
manifest, then preserves the existing scout packet and fixed human-verdict
triage. Dynamic calls, unresolved types, macros/cfg, traits/generics, optional
targets, and missing Git evidence remain deferred. Copy sibling
`map-subsystem` with this skill.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-incomplete-sweep"
REPORT_DIR="$PWD/reports/find-incomplete-sweep/rust"
python3 "${SKILL_ROOT}/scripts/detect_rust_incomplete_sweep.py" \
  --project-root "$PWD" --target . --report-dir "$REPORT_DIR"
python3 "${SKILL_ROOT}/scripts/scout.py" --scan-dir "$REPORT_DIR" --project-root "$PWD"
python3 "${SKILL_ROOT}/scripts/triage.py" --scan-dir "$REPORT_DIR"
```

Detects **forgotten call sites** — a change applied to N-1 of N
structurally-similar sites, leaving one sibling at the old shape. The
straggler still works and is still referenced, so nothing else flags it.

The architectural framing — why "looks unfinished" is the wrong target and
"dangling edge in recently-touched code" is the right one, and how the
git-trajectory gate separates *abandonment* from *post-completion cleanup* —
is captured in the bands and gate sections below.

## How success is judged

- Every gated-in packet in `scout_packets.json` receives exactly one
  Step B verdict record in `<scan-dir>/scout_verdicts.json` from the fixed
  vocabulary (`forgotten` / `deliberate` / `optional` / `not-applicable`)
  with a one-line rationale — leaves are recorded with their why, never
  silently dropped.
- `<scan-dir>/triaged.md` is written forgotten-first; each `forgotten`
  carries the suggested completion and hands off to `/fix-workflow
  cluster:<finding>`.
- The git-trajectory gate ran (unless `--no-gate` was explicit);
  likely-deliberate divergences stay in their own section.
- Zero production-code edits — detection-only. The only writes are scan
  artifacts under the requested `--out` directory.
- The closeout pastes detector output (`wrote ...` or the Markdown report),
  scout packet count, and the `triaged.md` path. Claims without artifacts do
  not count.
Write toward these gates from the first detector run.

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

## Go v1

Load `knowledge/go-v1.md`. The family-local `go list` + `go/parser` + `go/types`
analyzer admits direct project top-level calls with one keyed struct-option omission,
identical comparable values, and **every** present line newer in Git. It defers
ambiguous/dynamic calls and unavailable evidence. Use manifest `present_sites`,
the fixed verdict, and `triage.py`. Run the copied-install command and outcome boundaries in that guide.
## Java 17 v1

Load `knowledge/java-v1.md` for the direct record-construction, three-to-one,
mandatory-Git, scout → fixed human verdict → `triaged.md` contract.

## TypeScript / TSX v1

Use this separate branch only with a named project-local `tsconfig` and a
`typescript` package installed under the target host. The family-local **TypeScript Compiler API** resolves aliases, resolved object-literal spreads, overloads, and defaults to the precision required for one narrow invariant:
among calls that resolve to the same project function declaration, an object
option/property passed by a strong majority but omitted by a straggler.

The detector follows import aliases and a local constant object literal used in
`...spread`; it keeps overload signatures distinct, and only promotes an
omitted destructured option with a default when all present sites pass the
same comparable non-default value. Its final output is still the existing
candidate → scout packet → explicit human verdict → `triaged.md` journey.

Method/framework APIs, external declarations, runtime dispatch, dynamic
receivers, unresolved object spreads, JSX/React conventions, and route/ORM
semantics are explicitly deferred. They never become lexical candidates or
automatic fixes. Missing/invalid `tsconfig`, an unavailable project-local
compiler, or TypeScript syntax errors exit 2. An unresolved static module, a
dynamic callee, or an unresolved spread writes a visibly `partial` manifest;
it is never represented as a clean scan.

The TypeScript detector accepts a `.ts`/`.tsx` file or directory target. Its
project-root-relative exclusions apply both to a broad source traversal and a
direct excluded directory/file. It never follows internal or external symbolic
links, and it writes only beneath `reports/find-incomplete-sweep/<scan>/`;
source paths and report paths through a symlink are rejected before any write.
It does not modify source.

## Checked JavaScript v1

Use the same detector with `--language javascript` only when the host supplies
an explicit `jsconfig.json` or `tsconfig.json` with `allowJs` and `checkJs`
enabled and the host-local `typescript` package. The supported fact is narrow:
Compiler-API-resolved **direct** calls to project function declarations and
explicit object-literal option shapes. Dynamic/method/framework APIs and
unresolved spreads are deferred rather than inferred. The final manifest
distinguishes checked JavaScript, JSDoc, and compiler-inferred direct-call
evidence; it records config, diagnostics, unresolved modules, and uncovered
files. Missing tools/configs are unsupported, malformed selected JS is a
syntax-error, and unresolved/excluded sources are partial—not clean. Never
fall back to `npx`, a global compiler, or framework conventions.

The checked-JavaScript manifest follows the same human handoff as the
TypeScript compiler manifest: the detector writes gated-in findings plus their
compiler-resolved `present_sites`; `scout.py` converts only those findings into
`scout_packets.json` without `--paths`; a judge writes one fixed-vocabulary
record per packet to `scout_verdicts.json`; then `triage.py` validates that
accounting and writes forgotten-first `triaged.md`. The compiler output is a
lead, not a completion or an automatic code change.

<!-- installed-command:javascript-scan:start -->
```bash
: "${TARGET:?Set TARGET to the checked-JavaScript file or directory to inspect}"
JSCONFIG="${JSCONFIG:-jsconfig.json}"
REPORT_NAME="${REPORT_NAME:-javascript-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-incomplete-sweep" \
  ".agents/skills/find-incomplete-sweep" \
  ".claude/skills/find-incomplete-sweep"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-incomplete-sweep is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/detect_typescript_sweep.mjs" \
  --target "${TARGET}" --project-root "$(pwd)" --tsconfig "${JSCONFIG}" \
  --report-dir "reports/find-incomplete-sweep/${REPORT_NAME}" \
  --language javascript
python3 "${SKILL_ROOT}/scripts/scout.py" \
  --scan-dir "reports/find-incomplete-sweep/${REPORT_NAME}" \
  --project-root "$(pwd)"
```
<!-- installed-command:javascript-scan:end -->

This standalone host-root command resolves the selected skill itself and stops
at packets. It does not inherit `SKILL_ROOT` from the TypeScript command below.
After the required human/scout verdicts are written, use Step C to create
`triaged.md`.

### Installed TypeScript command

Set `FIND_INCOMPLETE_SWEEP_SOURCE` to the pinned source/ref, then install this
selected skill. The installed command needs only Node, the host-local compiler,
and the included scout/triage scripts—no toolkit venv, repository helper,
sibling skill, or network access after installation.

<!-- installed-command:stock-install:start -->
```bash
: "${FIND_INCOMPLETE_SWEEP_SOURCE:?Set this to the pinned skill source/ref}"
npx --yes skills@1.5.19 add "${FIND_INCOMPLETE_SWEEP_SOURCE}" \
  --skill find-incomplete-sweep --agent codex --copy -y
```
<!-- installed-command:stock-install:end -->

<!-- installed-command:typescript-scan:start -->
```bash
: "${TARGET:?Set TARGET to the TypeScript/TSX file or directory to inspect}"
TSCONFIG="${TSCONFIG:-tsconfig.json}"
REPORT_NAME="${REPORT_NAME:-typescript-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-incomplete-sweep" \
  ".agents/skills/find-incomplete-sweep" \
  ".claude/skills/find-incomplete-sweep"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-incomplete-sweep is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/detect_typescript_sweep.mjs" \
  --target "${TARGET}" \
  --project-root "$(pwd)" \
  --tsconfig "${TSCONFIG}" \
  --report-dir "reports/find-incomplete-sweep/${REPORT_NAME}"
python3 "${SKILL_ROOT}/scripts/scout.py" \
  --scan-dir "reports/find-incomplete-sweep/${REPORT_NAME}" \
  --project-root "$(pwd)"
```
<!-- installed-command:typescript-scan:end -->

The command stops at packets because only a human/scout can supply the required
verdict records. Write one fixed-vocabulary verdict per packet to
`scout_verdicts.json`, then run `triage.py` as Step C below. Run the host's
native typecheck and tests before and after this read-only scan.

## Invocation

`--paths` is required — there is no default scan root, so a wrong default can
never silently scan nothing. Pass one or more source roots (e.g. `scripts`).
Relative paths anchor on `--project-root` (default: git toplevel of the cwd,
else the cwd). The kwarg band records the resolved root in `manifest.json` so
`scout.py` re-anchors the same way; the placeholder band uses the same resolved
root for path walking, report labels, reference checks, and
`placeholder_manifest.json`.

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
duplicated. Compiler manifests for TypeScript and checked JavaScript carry the
compiler-resolved present-site locations, so their scout invocation omits
`--paths`. The judge reads packets; it does **not** re-derive evidence.
(`--paths` must match the original Python scan so the present-site index is
identical.)

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

Write the collected judge outputs to `<scan-dir>/scout_verdicts.json`:

```json
{
  "scan_dir": "reports/find-incomplete-sweep/scan-<TS>",
  "verdicts": [
    {
      "id": "SW-01",
      "verdict": "forgotten|deliberate|optional|not-applicable",
      "rationale": "<one line>",
      "completion": "<kwarg to add, only when forgotten>"
    }
  ]
}
```

The dispatch prompt must tell each judge that this JSON record is the judged
artifact and that `triaged.md` will be built from it. A judge reply without a
record for its packet is incomplete; do not merge until every packet id is
accounted for.

The full decision rubric — including the dominant trap that the
result-shape and optional-dataclass classes mimic a forgotten sweep — is in
`reference/scout-rubric.md`. Keep it out of the orchestrator's context; it is
the judge's brief.

### Step C — rank and hand off

Run the fixed writer after collecting `<scan-dir>/scout_verdicts.json`:

```bash
: "${SCAN_DIR:?Set SCAN_DIR to reports/find-incomplete-sweep/<scan>}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-incomplete-sweep" \
  ".agents/skills/find-incomplete-sweep" \
  ".claude/skills/find-incomplete-sweep"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-incomplete-sweep is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
python3 "${SKILL_ROOT}/scripts/triage.py" --scan-dir "${SCAN_DIR}"
```

It rejects duplicate, missing, unknown, invalid-vocabulary, or rationale-free
verdicts. The resulting `<scan-dir>/triaged.md` is
**forgotten-first** (then `deliberate` / `optional` / `not-applicable`, each
with rationale). Forgotten findings hand off to `/fix-workflow
cluster:<finding>`; a recurring forgotten *type* graduates to
`/prevent-regression`. `deliberate` / `optional` / `not-applicable` are the
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

## When things go sideways

| Symptom | Action |
|---|---|
| `--paths` is omitted | Stop; the scanner requires an explicit root so it cannot silently scan the wrong tree |
| Relative paths resolve to the wrong tree | Re-run with `--project-root DIR`; paste the detector output that records the intended root |
| `manifest.json` is missing before `scout.py` | Re-run the kwarg band with `--out`; do not fabricate scout packets |
| `scout_packets.json` has zero packets | Write an empty `scout_verdicts.json`, skip `triaged.md` findings, and report "no gated-in findings" |
| A judge omits a packet id or uses a verdict outside the fixed vocabulary | Re-dispatch that packet only; do not merge partial or invented verdicts |
| Placeholder band reports old stable stubs only | Treat them as gated-out accepted debt; do not route to `/fix-workflow` without a gated-in hit |

## Replay case

Replay the script fixture suite after detector changes:

```bash
.venv/bin/python .claude/skills/find-incomplete-sweep/scripts/test_scan.py
```

For project-root anchoring changes, also run the placeholder band from a
different cwd against a tiny fixture with `--project-root` set and paste the
real `wrote .../placeholder_findings.md` line plus the report header showing
`files scanned`.
