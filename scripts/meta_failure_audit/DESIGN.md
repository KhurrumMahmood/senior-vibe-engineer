# meta-failure-audit — disinterested meta-failure review kit (ported design doc)

> **Port note.** Ported verbatim (no content edits) from
> `~/Projects/experiments/claude-instructions/meta-failure-audit-kit/` on
> 2026-06-12 — the surviving artifact of an instruction-design
> investigation into whether system-prompt disposition "notes" improve
> model decisions. Layout here:
> `scripts/meta_failure_audit/{README.md,SKILL.md,LENS-CHECKLIST.md,meta-failure-audit.workflow.js}`.
> All four files are byte-identical to the source (`diff -r` verified).
> This DESIGN.md is the only file authored during the port.
>
> The kit is prose + one Claude Code *Workflow-tool* script. There is no
> Python and no self-test. Per the skill-comply porting pattern
> (`scripts/skill_comply/DESIGN.md`, `.claude/tasks/skill-repairs/skill-comply-port.md`):
> parity first, gaps recorded verbatim, repo wiring proposed but not
> performed.

## What the kit is (source's own summary)

A "reusable, **disinterested** lens-set that audits a plan, methodology,
conclusion, or measurement system for the class of reasoning failure that
object-level review misses: motivated, self-referential, and proxy-blind
errors." Six owned lenses + a novel-failure critic; three usage modes
(Reflex checklist / non-optional Gate / Deliberate fan-out). "It is
**signal, not verdict**."

The validated principle the kit preserves (source README, verbatim): "A
calibrated *trigger* at the decision point works; an aspirational *note*
mostly doesn't. … lifted a weak model's risk-first planning a lot (~+1.3
on 0–3). Content-matched passive prose barely moved it (~+0.3). Delivery
at the decision point is the lever — not the eloquence of the
description." And: "The fix isn't a better self-description; it's a
**disinterested external check.** This kit is that check."

Provenance footnote: the workflow's v4 comment records that the lens-set
was once run against an external target — "the engineering-skills
ecosystem" — i.e. this kit has already audited this repo's ancestor once;
that run is what promoted reflexivity and audit-the-evaluation from
novel-critic findings to owned lenses 5 and 6.

## Inventory: claims vs contents

| README claims | Present in kit | Status |
|---|---|---|
| `meta-failure-audit.workflow.js` — the audit (6 lenses + novel critic + synthesis) | yes | parses only under the Claude Code Workflow tool (see gap 1) |
| `LENS-CHECKLIST.md` — the no-agents rubric | yes | usable as-is, pure prose |
| `SKILL.md` — the `/meta-audit` Claude Code skill wrapper | yes | stored as artifact, NOT installed (see gap 7) |
| `README.md` — this file | yes | verbatim |
| Investigation data behind the headline numbers (+1.3 / +0.3, "~doubled unwarranted challenge") | **no** | only the workflow's `DEFAULT_TARGET` summary describes it (gap 5) |

## KNOWN GAPS (found during port — recorded, NOT fixed)

1. **The workflow is not standalone JavaScript.** It targets the Claude
   Code `Workflow` tool's evaluator: it relies on injected globals
   (`args`, `phase`, `parallel`, `agent`), top-level `await`, and a
   top-level `return`. As an ES module it fails to parse —
   `node --input-type=module --check` says `SyntaxError: Illegal return
   statement` — while a plain `node --check` (Node v22.21.1, automatic
   module detection) exits 0. No `Workflow` tool is available in this
   repo's environment, so the kit's mode 1 ("As a Claude Code workflow
   (fan-out, strongest)") is **not runnable here today**. Modes 2
   (checklist) and 3 (skill wrapper) are prose and need no runtime.
2. **Stale lens-count inside the novel-critic prompt.** Verbatim from
   `meta-failure-audit.workflow.js`: "and any failure type that falls
   BETWEEN the four named lenses (a coverage gap in the lens-set
   itself)." The v4 lens-set is six; "four" is residue from v3. The same
   prompt's opening correctly says "the six lenses above". Left verbatim.
3. **Version-history comment ambiguity.** Both version notes claim to be
   the current file: "v3 (this file) restores construct-validity as an
   owned lens" and "v4 (this file) adds the two lenses the v3
   novel-critic had to carry ALONE". Residue of in-place evolution. Left
   verbatim.
4. **`--quick` has no mechanical definition.** SKILL.md's
   `argument-hint` declares `[--quick]`; the only semantics are prose —
   "**Otherwise (or with `--quick`):** run the six lenses inline as
   `LENS-CHECKLIST.md`". No script parses the flag. (The repo's Band-A
   skill-artifact-drift gate passes because there is no script whose
   argparse could contradict it.)
5. **Headline findings are not reproducible from the kit.** The README's
   measured claims trace to "~40M tokens across ~12 experiments" whose
   artifacts are not in the kit. The source concedes the class of gap
   itself, verbatim: "It doesn't measure its own outcomes — fix this
   first." and "The harness leaks; it isn't transfer-proven. A clean
   transfer test was never achieved — the audit agents **read the
   pre-registration files off disk**, so independence wasn't preserved."
   Also: "Self-refined, with the bias that implies. … Useful and
   battle-tested — not statistically validated."
6. **Placeholder script path in usage docs.** README and the workflow
   header both show `Workflow({ scriptPath:
   ".../meta-failure-audit.workflow.js", … })` — the `.../` placeholder
   was left as-is; SKILL.md's `<this skill dir>` likewise.
7. **SKILL.md is stored, not installed.** `/meta-audit` is not invocable
   in this repo. Verified inert: repo skill tooling globs only
   `.claude/skills/*/SKILL.md` (`scripts/skill_meta.py:182`,
   `scripts/project_adapt.py:310`); the pre-commit `skill-artifact-drift`
   hook *does* match any `SKILL.md` path, and the ported file passes its
   Band-A gate (exit 0, command below).

## Deliberately NOT adapted yet (parity first)

- No installation under `.claude/skills/meta-audit/` — wiring below is a
  proposal only; no existing SKILL.md was edited.
- No Python shim, runner, or test invented around the workflow — the kit
  ships none, and the port does not add code the source never had.
- Gaps 2 and 3 (textual defects in the workflow comments/prompts) left
  byte-identical; fix upstream-and-here together if ever load-bearing.
- No domain lens-packs (the source's own "Strengthen" list) and no
  judged-closure / precision-tracking loop — the source names both as
  future work it never built.

## What runs here (commands + output)

```text
$ diff -r ~/Projects/experiments/claude-instructions/meta-failure-audit-kit/ scripts/meta_failure_audit/   # before DESIGN.md was added
(no output — byte-identical)

$ node --check scripts/meta_failure_audit/meta-failure-audit.workflow.js
(no output; exit 0)

$ node --input-type=module --check < scripts/meta_failure_audit/meta-failure-audit.workflow.js
SyntaxError: Illegal return statement   # expected — Workflow-tool evaluator only, see gap 1

$ .venv/bin/ruff check scripts/meta_failure_audit/
warning: No Python files found under the given path(s)
All checks passed!

$ .venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate scripts/meta_failure_audit/SKILL.md
(exit 0)

$ .venv/bin/python scripts/lint/no_host_references.py   # with ported files staged via git add -N
OK — no private-host references (identity tier: 737 tracked files; structural tier: 33 doc surfaces).
```

The kit ships no self-test; nothing further is mechanically verifiable.
The substantive runnable artifact in this environment is
`LENS-CHECKLIST.md` executed as prose (six sequential passes + required
synthesis).

## Proposed wiring (stub — adversarial-review lane; NOT implemented)

The repo's code-review convention already names an "adversarial review"
lane (`.claude/CLAUDE.md` § Code Review) for *code diffs*. This kit is
the analogous lane for *reasoning artifacts* — change specs and ADRs —
where the failure modes are motivated/self-referential, not bug-shaped.
The source README's "Gate (non-optional)" row names exactly this use:
"auto-fire on a class of artifact — a hook/CI on plans, ADRs, metric
definitions, eval designs."

- **`/repair-skill` change specs.** After the change spec is drafted and
  before it is applied, run `LENS-CHECKLIST.md` inline (mode 2 — the
  `--quick` shape) against the spec in a fresh-context sub-agent. Lenses
  5 (reflexivity/instrument-object) and 6 (audit-the-evaluation) target
  the skill-repairs failure mode directly: the same party authoring the
  skill, the fix, and the evidence of the fix.
- **`/decide` ADR drafts.** Before an ADR advances from draft, run the
  six-lens pass over its Context/Decision/Consequences — especially
  lens 1 (could it have come out the other way?) and lens 4
  (honest-self-account) on the alternatives-considered section.
- **Honor the validated principle in the wiring itself**: the audit step
  must be a *trigger at the decision point* — a named step inside the
  `/repair-skill` and `/decide` bodies at the moment of
  commit/acceptance — not an aspirational note in CLAUDE.md. That is the
  kit's own +1.3-vs-+0.3 finding applied to its installation.
- **Lane discipline**: per repo convention the lane stays local
  (fresh-context sub-agent; no external LLM, no code/diff sharing).
  Output is "signal, not verdict" — findings are leads the human
  verifies; "no meta-failures found" is a valid, unpadded result.
- **Installation path when adopted**: `/plan-skill` intake, then copy
  `SKILL.md` + `LENS-CHECKLIST.md` to `.claude/skills/meta-audit/`,
  resolve gaps 2/4/6 at that point, and decide whether the Workflow
  fan-out mode is worth a runtime or the checklist mode suffices.
