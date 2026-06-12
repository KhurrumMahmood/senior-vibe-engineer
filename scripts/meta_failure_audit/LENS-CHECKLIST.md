# Meta-Failure Audit — portable checklist (no agents required)

Run this on a plan, methodology, conclusion, or measurement system when you want to
catch the failures object-level review misses. Use it as **six sequential passes**,
or simulate **six skeptics in one thread** each owning one lens.

**Stance for every pass:** you are a *disinterested* auditor with no stake in the
work being right. Don't be polite, don't credit it, don't soften — but don't
manufacture a failure where none exists. **"Not present here" is a valid, valuable
answer.** Anchor every finding to a specific quote or decision, and tag it with the
sub-check it came from.

---

## 1 · Falsifiability-of-setup — *could it have come out the other way?*
- **could-not-falsify** — for each conclusion, could the design/metric as built have
  produced the opposite result? Flag conclusions drawn from cells where the
  alternative was structurally unmeasurable (ceiling/floor, ~100% baselines).
- **inherited-frame** — was a plan/metric/scenario adopted from a prior choice and
  executed without re-deriving that it fits the goal?
- **tractable-over-relevant** — chosen because it was clean/easy/measurable rather
  than because it could answer the live question?
- **gate-not-enforced** — a precondition or control named but not actually enforced
  before spending or concluding.
- **internal-incoherence** — do the work's own dates/counts/claims contradict each
  other or the data (an aggregate dated before its inputs; header count ≠ row count;
  a verdict asserted for a test described as not-yet-run)?

## 2 · Inference-discipline — *does the claim follow, by ONE symmetric standard?*
- **sub-threshold-promoted** — an effect at/below the work's own noise floor stated as
  real or causal.
- **asymmetric-standard** — a null reported with a strong verb ("refuted") while a
  same-sized wanted result is accepted. Different bars for wanted vs unwanted.
- **circular-metric** — a metric that restates the intervention, so a "win" is partly
  tautological. (Whether it measures the right construct is lens 3.)
- **confabulated-procedure** — a check/gate asserted to yield a verdict with no
  mechanism underneath; a conclusion declared without running the thing that tests it.
- **did-not-update / motion** — a signal clear enough to act on, padded with more data
  instead; or experiments that couldn't discriminate the live hypotheses.

## 3 · Construct-validity — *does the metric measure the construct, or a proxy?*
- **proxy-for-target** — is the headline construct measured by a stand-in (length,
  tone/intensity, presence of the exact behavior just commanded, an LLM judge's
  impression) that can move without the real target moving?
- **metric-named-for-wrong-thing** — named for one thing (challenge_*intensity*,
  output length) while the conclusion is about another (decisions, capability).
- **proxy-detaches (in-data proof)** — is there a case in the work's *own* results
  where the proxy moves but the outcome doesn't?
- **unvalidated-key** — were ground-truth labels/partitions (warranted-vs-unwarranted,
  correct-vs-incorrect) asserted but never independently validated?
- *For each, name the proxy-independent, outcome-level measure that would close the gap.*

## 4 · Honest-self-account — *the truest story of its own process, or the cleanest?*
- **reactive-as-deliberate** — a correction forced by hitting a wall, narrated as
  planned design ("started with the crux", "improved Run 2" for a run that produced
  the same null).
- **flattering-frame** — events framed as more principled/intentional than they were.
- **post-hoc-rationalization** — a justification produced after the fact to make a
  motivated choice look reasoned.
- *Compare the self-description against what the work's own sequence of events implies.*

## 5 · Reflexivity / instrument-object — *is the measurer the measured?*
- **instrument-is-object** — is a tool/metric validated by applying it to itself or to
  the very system whose quality it is meant to prove? Flag where one datum means two
  opposite things at once (the detector worked / the system failed).
- **sign-ambiguous-result** — a result equally consistent with success and failure
  because subject and instrument share identity (a clean/zero reading = "nothing
  wrong" OR "instrument insensitive").
- **evaluator-has-stake** — does whoever ran it benefit from one outcome; is
  "disinterested" asserted while the runner is a party to the conclusion?
- **confidence-peaks-where-least-independent** — is the work most confident exactly
  where measurer and measured are least separable?
- *Name the external reference (independent corpus, third party, known ground truth)
  that would break the identity.*

## 6 · Audit-the-evaluation — *does the test's design predetermine its result?*
  *(Apply to any self-evaluation inside the work AND to your own audit.)*
- **rubric-rigged** — is the success/failure verdict reachable only through one slot,
  or structured so a particular result is near-guaranteed?
- **contamination** — was the evidence produced, annotated, or pre-decomposed by the
  same party that built the evaluation, so a "discovery" is partly recall of seeded
  material? Flag shared authorship of target + instrument + prediction.
- **critic-incentive-to-fire** — is a critic rewarded by the scoring rules for
  returning a finding over a null, so its output is motivated?
- **predetermined-verdict** — is the conclusion entailed by the setup (the edit
  guarantees the result; the gate's verdict is pre-stated) so the run couldn't inform?

## + Novel critic — *what none of the six would catch.*
Hunt for a failure type that falls *between* or *beyond* the six lenses — motivated
reasoning the analysts had a stake in, broad claims from a narrow proxy,
self-referential blind spots where the work is most confident exactly where it is
least checked, a load-bearing conclusion the stated caveats undermine more than
admitted, and any coverage gap in the lens-set itself.

---

## Then synthesize (required)

1. **Bottom line** (2–3 sentences): does the work commit meta-failures its own
   review would miss, and the single most important one?
2. **Confirmed** failures, ranked by severity × confidence × load-bearingness — each
   with the quote, why it matters, and the fix.
3. **Held with low confidence / possibly overreaching** — a premature-confidence check
   on the audit itself.
4. **Correlation & coverage check** — are the lenses' findings independent or
   restating one root cause? Estimate the count of *distinct* root failures vs the
   surface count. Did the novel critic surface anything the six missed?
5. **One conclusion to downgrade** in confidence.
