---
name: converge
description: After-phase convergence gate. Models the work-in-progress as a small value graph (every dimension must hold at once for "done"), then emits a fixed verdict — phase_status (advance/repair/branch/park/discard), strongest/weakest nodes, the single next necessary step, why that step, the success gate, the stop condition, and an explicit do-not-do-next list. Routes effort toward the next NECESSARY move instead of the next available one; refuses fan-out. Advisory and read-only against production code.
argument-hint: "[what phase just finished | --graph dim1,dim2,… | --report]"
allowed-tools: Read, Bash
user-invocable: true
tier: cross-cutting
job: triage
language: any
framework: any
best_for: |
  The moment AFTER a meaningful phase — a refactor executed, a cleanup sweep
  finished, a design pass produced, a feature milestone reached — when the
  next move is about to be chosen by momentum. Answers: is this thread done,
  what is the single next necessary action, when do we stop, and what do we
  refuse to do next. Also the periodic "are we converging or just active?"
  check on a long-running body of work.
not_for: |
  Forward routing before work starts (/which-shape then /which-skill).
  Diff-driven cleanup selection at closeout (/which-cleanup — complementary:
  it picks WHICH quality skills to run on what changed; /converge decides
  whether and where the work itself continues). Global, periodic debt
  triage over cached reports (/triage-debt). Trivial single-edit tasks —
  a one-line fix does not need a convergence gate. Executing anything:
  this skill emits a verdict and stops.
escalate_to: |
  Whatever the verdict names: /which-cleanup for a guard-tail before close,
  /decide when phase_status=branch exposes a material fork, /track-idea to
  park a nugget, /fix-workflow or /refactor-subsystem when next_step is a
  concrete repair.
delegate_from: |
  /which-cleanup and /refactor-subsystem closeouts may point here when the
  question is "should this thread continue at all?" rather than "which
  cleanup applies to this diff?".
lanes: [routing]
stage: verify
entrypoint: true
consumes: [phase_artifacts, latest_verdicts]
produces: [convergence_verdict]
risk_triggers: [post-change, long-running-thread, fan-out, decided-but-unbuilt]
max_overhead: "One verdict per phase. Small phases: inline verdict only, no scan dir, no sub-agents."
---

# /converge — after-phase convergence gate

After a phase of work, do the next *necessary* thing, not the next
*available* interesting thing. This skill is the structured pass that makes
that choice explicit: name the value dimensions that must ALL hold for the
work to be done, find the weakest one, and emit a fixed verdict with a stop
condition and a do-not-do-next list. A verdict missing the stop condition
or the do-not-do-next list does not count as a convergence gate.

## Stage 1 — Name the value graph

Establish the small set of value dimensions for THIS work. Default
engineering graph (use when the caller supplies none):

| node | holds when |
|---|---|
| `correct` | the change does what was intended; failures reproduced then fixed |
| `wired-in` | the change is reachable from the real entry points — not built but unplugged |
| `guarded` | a test / lint / hook exists so the fixed problem cannot silently return |
| `no-parallel-path` | no second writer / duplicate mechanism was introduced alongside the old one |
| `demonstrated` | the outcome is shown at the output boundary (run, render, report), not asserted |

The caller may override with `--graph dim1,dim2,…` or by naming dimensions
in prose. Honesty rule: **a graph that omits a real dimension will pass
work that is not done.** If a dimension feels missing while assessing,
add it — do not squeeze evidence into the wrong node.

## Stage 2 — Assess each node with evidence

For every node, find the strongest available evidence and cite it: a test
run, a diff, a report path, a rendered output, a grep proving call sites.
Rules:

- **Unknown counts as weak.** A node nobody checked is a weak node, not a
  passing one.
- **Authorship is not evidence.** Do not advance a node on the author's
  assertion alone — this gate is self-assessed (the same actor judges and
  is judged), so bias the call toward `repair` whenever evidence is thin.
- Read what exists (reports under `reports/`, test output, the diff); do
  not re-execute expensive scans just to feed the gate.

## Stage 3 — Emit the verdict

Fixed shape — every field, every time:

```json
{
  "phase_status": "advance | repair | branch | park | discard",
  "strongest_nodes": ["…"],
  "weakest_nodes": ["…"],
  "next_step": "the single next necessary action",
  "why_this_step": "names the weakest node this step closes",
  "success_gate": "the observable evidence that will prove next_step worked",
  "stop_condition": "the observable condition under which work on this thread stops",
  "do_not_do_next": ["the tempting-but-not-necessary moves to refuse now"]
}
```

Status vocabulary (total — pick exactly one):

- **advance** — the phase passed its gate; move to the next-weakest node.
- **repair** — promising, but a specific node is weak; fix THAT before
  anything new.
- **branch** — multiple genuinely distinct routes exist and choosing now
  would discard value; split deliberately (and surface the fork to
  `/decide` if it is material).
- **park** — useful later, not necessary now; shelve explicitly
  (`/track-idea`) so it is neither lost nor pursued prematurely.
- **discard** — expensive or clever but advances no value node; stop.

Render the verdict in the conversation as the JSON block plus one short
paragraph of plain-language justification. For substantial phases, or when
invoked with `--report`, also write it to
`reports/converge/scan-<TS>/verdict.json` (with the paragraph in
`verdict.md`) and append an effectiveness record:

```bash
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p "reports/converge/scan-${TS}" && ln -sfn "scan-${TS}" reports/converge/latest
# after writing verdict.json / verdict.md, log one record keyed by the status:
python3 scripts/log_effectiveness.py --skill converge --scan-id "scan-${TS}" \
  --target "<thread or phase name>" --findings-total 1 \
  --buckets '{"status_repair": 1}'   # bucket key = status_<phase_status>
```

## Stage 4 — Enforce the verdict's discipline

- The `next_step` is ONE action. If two feel necessary, the weaker-node one
  wins; the other goes to `do_not_do_next` or `park`.
- `stop_condition` must be observable ("the suite passes and the report
  regenerates in CI"), never aspirational ("when it feels solid").
- `do_not_do_next` is a refusal list, not a backlog — entries are moves that
  are *tempting now*; parking-worthy items go through `/track-idea` instead.
- Do not execute the next step inside this skill. Emit, hand off, stop.

## Known limits

- **Self-assessed gate.** Until outcome/reader telemetry exists, the judge
  and the judged are the same actor (ADR 0031's named limit). The Stage 2
  bias rules are the mitigation, not a cure.
- First implementation — the verdict shape is committed; the default graph
  and the bias rules are expected to be tuned by dogfood use.

---

Source decision: `core:value-graph-next-step-router` (ADR 0031) —
provenance, not required reading; do not load the ADR during execution.
