// META-FAILURE AUDIT (6 owned lenses + novel critic)
// A reusable disinterested lens-set that audits a plan / methodology / conclusion for
// META-level reasoning failures (motivated, self-referential, deference-laden) that
// object-level review misses. Pass the artifact via args (string, or {artifact}).
// Run with: Workflow({ scriptPath: ".../meta-failure-audit.workflow.js", args: "<artifact text>" })
// Defaults to auditing this investigation itself.
//
// Lens design (tuned by running this audit on itself):
//   v1 had 6 lenses; its own self-check found them correlated (two root causes restated many ways).
//   v2 merged to 3 + novel critic; that recovered all critical findings ~40% cheaper, but the
//     novel critic revealed the merge had dropped CONSTRUCT VALIDITY (no owner) — the most
//     important error class for proxy-heavy, LLM-judge work.
//   v3 (this file) restores construct-validity as an owned lens => 4 orthogonal lenses + novel critic:
//     1 Falsifiability-of-setup   (could it have come out the other way? inherited/tractable frames, unenforced gates)
//     2 Inference-discipline      (does the claim follow, by ONE symmetric standard? sub-threshold, asymmetric bars, circular metric, confabulated procedure, failure-to-update / motion)
//     3 Construct-validity        (does the metric measure the construct, or a proxy that moves independently?)
//     4 Honest-self-account       (truest vs cleanest story of your OWN process)
//   v4 (this file) adds the two lenses the v3 novel-critic had to carry ALONE when this audit was run on an
//     external target (the engineering-skills ecosystem): every genuinely new finding there came from the
//     novel slot, exposing a real coverage gap. Promoted into owned lenses (warranted: the coverage check
//     proved these clusters were orthogonal to lenses 1-4, not restatements):
//     5 Reflexivity/instrument-object (is the measurer the measured? self-validation, sign-ambiguous results, evaluator-with-stake)
//     6 Audit-the-evaluation          (does the test/rubric predetermine its result? rigged success path, co-authored evidence, critic incentivized to fire)
//     + Novel critic              (a failure none of the SIX would catch; coverage gaps in the lens-set itself)

export const meta = {
  name: 'meta-failure-audit',
  description: 'Disinterested lens-set auditing a plan/methodology/conclusion for meta-level reasoning failures (motivated, self-referential, proxy-blind). 6 owned lenses + novel critic. Pass artifact via args; defaults to auditing this investigation.',
  phases: [
    { title: 'Audit', detail: 'six orthogonal disinterested lenses + a novel-failure critic, run cold on the target' },
    { title: 'Synthesize', detail: 'dedup, prioritize, count distinct root failures, apply premature-confidence check to itself' },
  ],
}

const DEFAULT_TARGET = `INVESTIGATION UNDER AUDIT — "Does a system-prompt 'note' describing a disposition improve a model's real-world decisions?"

METHOD: Multi-agent workflow experiments. A subject model (mostly Haiku 4.5; some Opus 4.8) is given a "note" (or a trigger, or nothing) as injected context, then responds to real-world planning/decision scenarios; separate Opus agents score the responses blind. ~40M tokens across ~12 experiments.

KEY MEASURED FINDINGS & CURRENT CONCLUSIONS (the things to pressure-test):
1. The model's competence is "native": baseline holds positions under pressure (~100%) and reasons risk-first on planning (Opus ~2.5/3). The note's only robust measured effect was ~15-20% more output. Concluded: "the note's value is articulation, not capability."
2. Triggers beat prose: a one-sentence imperative ("before answering, what could kill this, do it first") lifted a weak model's risk-first planning a lot (~+1.3 on 0-3); the full passive note did almost nothing (~+0.3).
3. A crude "say the hard truth" trigger produces INDISCRIMINATE challenge; a one-sentence calibration clause ("if the plan is sound, just help") preserves discrimination. Measured via discrimination = challenge(warranted) - challenge(unwarranted), Opus judge rating challenge_intensity blind to warrant.
4. Identity framing ("I am someone who...") erodes calibration (~doubles unwarranted challenge); combative identity = "intensity-cosplay" (tone up, decisions flat).
5. Noise/mood/delivery factorial: de-noising prose into bullets barely changed risk-first (+0.1); moving the SAME rules from background note to appended-at-response was the largest activation jump (+0.37); explicit if-then conditionals preserved calibration where identity prose eroded it. Concluded: "the blocker is delivery; the calibration-protector is the explicit IF; 'too much noise' is refuted."
6. Meta-conclusion: the high-value failures (committed by the experiment process itself) are self-referential/motivated, not object-level; the solution is disinterested external lenses, ideally non-optional.

CAVEATS REPEATEDLY FLAGGED: N=10-15 per cell; an identical-design baseline arm scored discrimination 0.8 in one run and 0.2 in another (0.6 null-swing); single subject model (Haiku) for most lift findings; single-turn; the "note" was injected as context, not a true API system prompt; scorers were the same model family (Opus) as the strong subject; stated rule "only gaps of ~0.4+ are trustworthy."

DECISIONS MADE: ran the clean low-relevance strain (S1, social-pressure) first and the relevant strains (planning/standards) last; adopted a "discrimination framework" of warranted/unwarranted scenarios and reused it across later experiments; concluded "articulation not capability" before two headroom domains were tested; pivoted strain only after Run 1 + an improved Run 2 both showed baseline ceilings.`

const target = (typeof args === 'string' && args.trim()) ? args
  : (args && typeof args === 'object' && args.artifact) ? String(args.artifact)
  : DEFAULT_TARGET

const FINDINGS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['lens', 'present', 'findings'],
  properties: {
    lens: { type: 'string' },
    present: { type: 'boolean', description: 'does this failure class appear in the target at all' },
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'subtype', 'severity', 'evidence', 'fix', 'confidence'],
        properties: {
          title: { type: 'string' },
          subtype: { type: 'string', description: 'which sub-check of the lens this is (so distinct failures within a lens stay visible)' },
          severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
          evidence: { type: 'string', description: 'specific quote or pointer in the target' },
          fix: { type: 'string' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
  },
}

const baseCtx = `You are a DISINTERESTED auditor. You did not produce the work below and you have NO stake in its conclusions being correct — your only job is to find a specific class of reasoning failure in it. Do not be polite, do not credit it, do not soften. But do NOT manufacture a finding where the failure is genuinely absent ("not present here" is a valid, valuable answer; fabricated findings are their own failure). Anchor every finding to a specific quote or decision in the target, and tag each with the sub-check it came from.

THE WORK UNDER AUDIT:
"""
${target}
"""
`

const LENSES = [
  { key: 'falsifiability-of-setup', label: 'audit:falsifiability', prompt: `${baseCtx}
YOUR LENS — FALSIFIABILITY OF THE SETUP: was the work arranged so it could have come out the other way? Sub-checks (tag each finding):
- could-not-falsify: for each conclusion, could the design/task/metric as built have produced the OPPOSITE result? Flag conclusions drawn from cells where the alternative was structurally unmeasurable (ceiling/floor, ~100% baselines, no headroom).
- inherited-frame: was a plan, sequencing, scenario-set, metric, or assumption ADOPTED from a prior choice/spec/convention and EXECUTED without independently re-deriving it was right for the goal?
- tractable-over-relevant: were tasks/strains chosen because they were clean/easy/measurable rather than because they could answer the live question?
- gate-not-enforced: was a stated precondition or control (a headroom/calibration gate, a trust threshold) named but not actually enforced before spending or concluding?
- internal-incoherence: do the work's OWN dates, counts, or claims contradict each other or the data they summarize (an aggregate dated before its inputs; a header count that disagrees with the row count; a verdict asserted for a test described as not-yet-run)?`,
  },
  { key: 'inference-discipline', label: 'audit:inference', prompt: `${baseCtx}
YOUR LENS — INFERENCE DISCIPLINE: does each claim follow from its evidence, by ONE standard applied symmetrically? Sub-checks (tag each finding):
- sub-threshold-promoted: any effect at or below the work's own stated noise floor (or below its observed null-swing) that is nonetheless stated as a real effect or a causal mechanism.
- asymmetric-standard: a null or near-zero reported with a strong verb ("refuted", "shows") while similarly-sized results in the wanted direction are accepted — different evidentiary bars for wanted vs unwanted conclusions.
- circular-metric: a metric/rubric that is NOT independent of the thing it scores — it restates the intervention so a "win" is partly tautological. (Whether the metric measures the right CONSTRUCT at all is the construct-validity lens's job; here, only independence.)
- confabulated-procedure: a check/adjudication/gate asserted to yield a verdict with no concrete mechanism underneath; a conclusion declared without running the thing that would test it.
- did-not-update / motion: a signal clear enough to act on that was padded with more data instead; OR experiments run that could not discriminate between the live hypotheses (motion past the answer, or motion that never could have answered).`,
  },
  { key: 'construct-validity', label: 'audit:construct-validity', prompt: `${baseCtx}
YOUR LENS — CONSTRUCT VALIDITY / OPERATIONALIZATION: does each metric actually measure the construct the work claims to be about, or a PROXY that can move independently of it? This is the single most important error class for proxy-heavy, LLM-judge work, and it is distinct from "is the inference disciplined" — a metric can be measured and analyzed flawlessly and still be measuring the wrong thing. Sub-checks (tag each finding):
- proxy-for-target: is the headline construct (e.g. "real-world decision quality", "calibration") measured by a stand-in — verbosity/length, tone or intensity, presence of the exact behavior an instruction just commanded, or an LLM judge's impression — that can move without the real target moving?
- metric-named-for-wrong-thing: is a metric named for one thing (e.g. challenge_INTENSITY, tone, output length) while the conclusion is about another (decisions, capability)?
- proxy-detaches (in-data proof): is there evidence in the work's OWN results of a condition where the proxy moves but the decision/outcome does not (direct proof the proxy is not the target)?
- unvalidated-key: were ground-truth labels or partitions (warranted-vs-unwarranted, correct-vs-incorrect, the "right" answer) asserted but never independently validated?
For each, name the proxy-independent, outcome-level measure that would close the gap.`,
  },
  { key: 'honest-self-account', label: 'audit:self-account', prompt: `${baseCtx}
YOUR LENS — HONEST SELF-ACCOUNT: when the work explains its OWN choices, errors, ordering, or results, is it telling the truest story or the cleanest/most-flattering one? Sub-checks (tag each finding):
- reactive-as-deliberate: a correction FORCED by hitting a wall (a ceiling, a reviewer, a failure) narrated as if it were planned design ("started with the crux", "by design", "improved Run 2" for a run that produced the same null).
- flattering-frame: events framed to look more principled, rigorous, or intentional than they likely were.
- post-hoc-rationalization: a justification produced after the fact to make a convenient or motivated choice look reasoned.
Compare the work's self-description of its decisions against what its own stated sequence of events implies actually happened.`,
  },
  { key: 'reflexivity', label: 'audit:reflexivity', prompt: `${baseCtx}
YOUR LENS — REFLEXIVITY / INSTRUMENT-OBJECT IDENTITY: is the thing doing the measuring the same as (or a stakeholder in) the thing being measured, in a way that makes results uninterpretable? The other lenses assume the target is a found object measured from outside; this one does not. Sub-checks (tag each finding):
- instrument-is-object: is a tool/skill/metric validated by applying it to itself, or to the very system whose quality it is meant to prove? Flag where one datum carries two opposite meanings at once (the detector worked / the system failed).
- sign-ambiguous-result: is a result equally consistent with success and failure because subject and instrument share identity (a clean or zero reading = "nothing wrong" OR "instrument insensitive")?
- evaluator-has-stake: does whoever ran the evaluation benefit from one outcome — is "disinterested" asserted while the runner is a party to the conclusion?
- confidence-peaks-where-least-independent: is the work MOST confident exactly where measurer and measured are least separable?
For each, name the external reference (independent corpus, third party, known ground truth) that would break the identity and make the result interpretable.`,
  },
  { key: 'audit-the-audit', label: 'audit:meta-eval', prompt: `${baseCtx}
YOUR LENS — AUDIT THE EVALUATION APPARATUS: does the design of the test, rubric, or evaluation predetermine its own result regardless of the truth? Apply this BOTH to any self-evaluation INSIDE the target AND reflexively to THIS audit and how its target was prepared. Sub-checks (tag each finding):
- rubric-rigged: is the success or failure verdict reachable only through one slot, or structured so a particular result is near-guaranteed? Does a "win" require something the design cannot deliver, or a "pass" require something that cannot fail?
- contamination: was the evidence the evaluation reasons over produced, annotated, selected, or pre-decomposed by the same party that built the evaluation — so a "discovery" is partly recall of seeded material? Flag shared authorship of target + instrument + prediction.
- critic-incentive-to-fire: is any evaluator or critic rewarded by the scoring rules for returning a finding over a null, so its output is motivated rather than disinterested?
- predetermined-verdict: is the conclusion entailed by the setup (the edit guarantees the result; the gate's verdict is pre-stated) so the run could not have been informative either way?
Name the change to the apparatus (independent curation, blinding, a null-rewarding rule) that would let it actually fail.`,
  },
  { key: 'novel', label: 'audit:novel', prompt: `${baseCtx}
YOUR LENS — NOVEL FAILURE CRITIC. Find a meta-level reasoning failure that the six lenses above (falsifiability-of-setup, inference-discipline, construct-validity, honest-self-account, reflexivity/instrument-object, audit-the-evaluation) would NOT catch — a new type. Hunt especially for: motivated reasoning where the analysts had a stake in a particular conclusion; broad claims generalized from a narrow proxy (single weak model, single-turn, context-injection rather than a real system prompt); self-referential blind spots where the work is MOST confident exactly where it is LEAST checked; a load-bearing conclusion the stated caveats actually undermine more than admitted; and any failure type that falls BETWEEN the four named lenses (a coverage gap in the lens-set itself).`,
  },
]

phase('Audit')
const results = (await parallel(LENSES.map((l) => () =>
  agent(l.prompt, { label: l.label, phase: 'Audit', schema: FINDINGS_SCHEMA })
    .then((r) => ({ ...r, key: l.key }))))).filter(Boolean)

phase('Synthesize')
const block = results.map((r) => {
  const fs = (r.findings || []).map((f) => `  - [${f.severity}/${f.confidence}] (${f.subtype}) ${f.title}\n      evidence: ${f.evidence}\n      fix: ${f.fix}`).join('\n')
  return `### lens: ${r.key}  (present=${r.present})\n${fs || '  (no findings)'}`
}).join('\n\n')

const synthesis = await agent(
  `You are the lead auditor writing the final meta-failure audit. You have findings from SEVEN lenses: falsifiability-of-setup, inference-discipline, construct-validity, honest-self-account, reflexivity/instrument-object, audit-the-evaluation, and a novel-failure critic.

Requirements:
- Lead with a 2-3 sentence BOTTOM LINE: does the work commit meta-failures its own object-level review would miss, and the single most important one?
- "Confirmed meta-failures" ranked by severity x confidence x load-bearingness. Each: what it is, the specific evidence (quote the target), why it matters, the fix.
- "Held with low confidence / possibly overreaching": findings where a lens may be manufacturing a problem (premature-confidence check on the audit itself).
- "Correlation & coverage check" (REQUIRED): (a) Are the seven lenses' findings genuinely independent, or restating the same root cause? Estimate how many DISTINCT root failures there really are vs the surface count. (b) Did the novel critic surface anything the six named lenses missed — i.e. is there still a coverage gap in the lens-set? (c) Did the two newest named lenses (reflexivity, audit-the-evaluation) each earn their place by catching something no other lens did?
- One line on which of the work's stated conclusions should be DOWNGRADED in confidence.
- Be specific; quote the target. Clean markdown, no preamble about your task.

LENS FINDINGS:
${block}

THE WORK UNDER AUDIT (for reference):
"""
${target}
"""`,
  { label: 'audit:synthesize', phase: 'Synthesize' },
)

return {
  version: 'owned-6-lens+novel',
  lenses_run: results.length,
  findings_by_severity: results.flatMap((r) => r.findings || []).reduce((a, f) => ((a[f.severity] = (a[f.severity] || 0) + 1), a), {}),
  findings_by_lens: results.reduce((a, r) => ((a[r.key] = (r.findings || []).length), a), {}),
  audit: synthesis,
}
