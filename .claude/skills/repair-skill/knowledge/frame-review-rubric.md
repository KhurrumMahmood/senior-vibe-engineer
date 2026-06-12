# Frame-review rubric

Calibrated on the 2026-06-12 reviews (scope-feature calibration run,
then diagnose / which-shape / refactor-subsystem fresh-agent runs) and
the two repair campaigns that followed. The reviewer reads SKILL.md +
knowledge/ + the script contracts, then answers six questions. Per
finding: cite the stage/line, name the failure it produces in
execution, give the smallest fix. Honesty bar: also report what the
skill gets right — the goal is calibration, not indictment.

1. **GOAL** — stated deliverable vs. real success property. Does any
   stage test the property (artifact truth), or only existence/format?
   The canonical anti-pattern: the headline deliverable passes every
   gate as a plausible narrative because the gates check that files
   exist, not what they prove.
2. **FRAME** — where is the frame established? Is it re-activated at
   the write/act/accept site, or preamble-only? A frame ~150 lines
   above the decision point has decayed by the time it matters.
3. **SURVEY** — is there a mandated read/inventory phase before work
   (survey-then-extract)? Is there a phase-0 over conversation context
   for context-rich invocations (inventory what is already answered;
   quarantine the reporter's theory as one hypothesis)?
4. **WORKFLOW TRAPS** — ordering that fights incentives (tier/abort
   checks after sunk cost), missing stop conditions, unbounded loops,
   missing back-edges (what happens when every hypothesis dies, when
   verification fails, when the gate blocks?).
5. **LOAD-BEARING TEST** — list every mandated verification or
   reporting stage; mark whether its output is consumed downstream (a
   later stage, the reply contract, or a gate). Pure ceremony gets
   skipped under load at ~100% — flag it for wiring or deletion.
6. **HALLUCINATION-INVITED** — phrasing an executor can satisfy by
   assertion rather than action ("read X end-to-end", "verify Y",
   "run the loop enough times to trust it") with no artifact that
   proves the action happened. Fix shape: demand an output that
   cannot be produced without the action (pasted transcript, named
   binding priors, exact command + observed output).

Two execution-time classes the rubric alone does not reach (the scout
and dogfood stages exist for them):

- **Artifact-reality drift** — artifacts no step produces, flags that
  do not exist, two formats sharing one path, counts that disagree.
  Found by auditing every pointer against the filesystem and script
  contracts, not by reading prose.
- **Unexecutable-against-reality** — contracts that fail on a host the
  skill was not written on: read-only agent types ordered to write
  files, convention sources with no absence fallback, chunker/tool
  output shapes the text never anticipated, unconditional steps that
  collide with no-commit environments. Found only by executing.
