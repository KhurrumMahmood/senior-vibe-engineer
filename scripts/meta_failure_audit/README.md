# Meta-Failure Audit Kit

A reusable, **disinterested** lens-set that audits a plan, methodology, conclusion,
or measurement system for the class of reasoning failure that object-level review
misses: motivated, self-referential, and proxy-blind errors. Point it at any
artifact; it returns specific, quote-anchored findings + fixes, then audits its own
confidence.

It is **signal, not verdict** — a second mind that runs whether or not the first
thinks to ask.

---

## Where this came from (and the one principle worth keeping)

This kit is the durable output of an investigation into a different question —
*"Does a system-prompt 'note' describing a disposition actually improve a model's
real-world decisions?"* The investigation's honest answer reshaped the goal:

- **A calibrated *trigger* at the decision point works; an aspirational *note* mostly
  doesn't.** A one-sentence imperative delivered where the decision happens
  ("before answering, what could kill this — do that first; *if the plan is sound,
  just help*") lifted a weak model's risk-first planning a lot (~+1.3 on 0–3).
  Content-matched passive prose barely moved it (~+0.3). Delivery at the decision
  point is the lever — not the eloquence of the description.
- **Identity / combative framing backfires.** "I am someone who…" eroded calibration
  (~doubled *unwarranted* challenge); a combative voice produced *intensity-cosplay*
  — tone up, decisions flat. Measure decision-change, not voice-change.
- **The highest-value failures are meta-level** — motivated reasoning, proxy metrics,
  unfalsifiable setups, instrument = object, decided-but-never-done. Object-level
  review (including the author's own) reliably misses them. The fix isn't a better
  self-description; it's a **disinterested external check.** This kit is that check.

So the best "instruction" the investigation produced wasn't a better disposition —
it was a tool for catching the flaws a disposition can't.

---

## The six lenses (+ a novel-failure critic)

| # | Lens | Catches |
|---|------|---------|
| 1 | **Falsifiability-of-setup** | Could it have come out the other way? Inherited/tractable frames, unenforced gates, internal incoherence (dates/counts that contradict the data). |
| 2 | **Inference-discipline** | Does the claim follow, by ONE symmetric standard? Sub-threshold promoted, asymmetric bars, circular metric, confabulated procedure, motion-not-progress. |
| 3 | **Construct-validity** | Does the metric measure the *construct*, or a proxy that moves independently (length, tone, presence-of-the-commanded-behavior, an LLM judge's impression)? |
| 4 | **Honest-self-account** | When the work explains its OWN choices, is it the truest story or the cleanest one? Reactive-as-deliberate, flattering frame, post-hoc rationalization. |
| 5 | **Reflexivity / instrument-object** | Is the measurer the measured? Self-validation, sign-ambiguous results, evaluator-with-a-stake, confidence peaking where independence is lowest. |
| 6 | **Audit-the-evaluation** | Does the test's own design predetermine its result? Rigged success path, evidence co-authored by the evaluator, a critic rewarded for firing. |
| + | **Novel critic** | A failure none of the six would catch — and coverage gaps in the lens-set itself. |

The full sub-checks and a no-agents version are in **`LENS-CHECKLIST.md`**.

---

## How to use it

**1. As a Claude Code workflow (fan-out, strongest):**
```
Workflow({ scriptPath: ".../meta-failure-audit.workflow.js", args: "<your artifact text>" })
```
Each lens runs cold and in parallel; a synthesis pass dedups, counts the distinct
root failures, and runs a premature-confidence check on itself. With no `args` it
audits a **built-in worked example** (the original investigation) so a first run
demonstrates the tool — pass `args` to audit your own artifact.

**2. As a portable checklist (anywhere, incl. plain chat):** run `LENS-CHECKLIST.md`
as six sequential passes (or a six-voice simulated debate). No agents required.

**3. As a skill:** `SKILL.md` wraps it as `/meta-audit` for one-command use in a
Claude Code project.

---

## When to use it

Its niche is the *unrecognized* case — the artifact that looks fine and is about to be
acted on. Procedures need you to recognize you need them; this doesn't. Three modes, by cost:

| mode | when | form |
|---|---|---|
| **Reflex** (highest value) | before committing anything that *looks* fine | the 6-lens checklist, a 2-minute skim |
| **Gate** (non-optional) | auto-fire on a class of artifact | a hook/CI on plans, ADRs, metric definitions, eval designs |
| **Deliberate** | a thing already known to be high-stakes | the full fan-out workflow |

Earns its keep on: **plans & decisions** before building; **analyses & conclusions**
before you present them; **metrics / KPIs / dashboards** (activity-not-outcome,
Goodhart-bait); **AI/LLM evals & rubrics** (criterion contamination, judge-as-proxy);
**self-reviews, retros, audits** (instrument=object).

Where it is *not* the tool: not a code reviewer (won't find bugs); not worth it on
simple/throwaway work (over-applying it is a failure it would flag in others); not a
substitute for domain knowledge (it catches reasoning *shape*, not domain-wrong facts).

## Limits, and how to strengthen it

*(Draft ledger — correct freely. The honest read: this tool has the exact gap it audits
others for, and that points at how to improve it.)*

- **It doesn't measure its own outcomes — fix this first.** It emits findings but never
  tracks whether they turn out *real*, so its "effectiveness" is unmeasured *activity*,
  not validated *outcome* — the `construct-validity` / `proxy-for-outcome` failure it
  flags in others. **Strengthen:** a judged-closure loop on its own output — record per
  finding whether it was later confirmed or a false positive; derive its precision (and,
  against a known-flaw corpus, recall). Validate the validator.
- **The harness leaks; it isn't transfer-proven.** A clean transfer test was never
  achieved — the audit agents **read the pre-registration files off disk**, so
  independence wasn't preserved. **Strengthen:** sandbox the agents from any
  prediction/solution files, and run the lenses with an *out-of-family* model so they
  don't share the author's blind spots.
- **Activation still needs recognition.** Its value is for *unrecognized* complexity,
  yet invoking it still requires recognizing-to-invoke. **Strengthen:** a non-optional
  **gate** that auto-fires on plans/ADRs/metric-defs (you don't have to know it's complex
  if it always runs), plus a 30-second pre-filter that escalates to the full pass only
  when warranted.
- **Named lenses are confirmatory; the novel critic carries the new ground.**
  **Strengthen:** log the novel critic's hits, promote a recurring one to a named lens
  (how v1→v4 happened), with a periodic correlation check to merge/retire lenses that
  stop earning their place (the "too much noise" guard).
- **Not a code reviewer; not domain knowledge.** **Strengthen:** pair it with code +
  domain review; add domain lens-packs (LLM-eval, metrics, plan) with sharper sub-checks.
- **Signal, not verdict.** It is told not to manufacture problems — "not present here" is
  a valid answer — but its false-positive rate is unmeasured (closes under improvement #1).
- **Self-refined, with the bias that implies.** The lens-set was tuned by running on
  itself (v1 six correlated → v2 merge → v3 restored construct-validity → v4 added
  reflexivity + audit-the-evaluation). Useful and battle-tested — not statistically
  validated.

---

## Files

- `meta-failure-audit.workflow.js` — the audit (6 lenses + novel critic + synthesis).
- `LENS-CHECKLIST.md` — the no-agents rubric.
- `SKILL.md` — the `/meta-audit` Claude Code skill wrapper.
- `README.md` — this file.
