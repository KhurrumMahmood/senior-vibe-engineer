# find-semantic-duplication — learnings

Rule provenance and judgment-call precedents. Read when facing ambiguity during investigation.

This skill is newer than `/find-duplication`, so the cluster archive is thinner. Precedents below are drawn from observations during skill design and cross-referenced with `/find-duplication` learnings where the lessons transfer.

## Rules

### R1. Workflow-first, function-second

Semantic duplication usually lives at the workflow level. Two field-extraction pipelines may share zero function names but follow the same shape: fetch → parse → validate → persist. The workflow is the duplication; the functions are its steps.

Run Compare at the workflow level first. Function-level comparison is the drill-down once overlapping workflows are identified. Comparing functions first (without workflow context) produces noise: many "same purpose" functions are different steps of different workflows.

### R2. Summary similarity ≠ body similarity

A purpose line like "extracts fields from HTML" could describe 50 functions. Confirmation (Step 5) is **mandatory** — never promote a candidate to confirmed status based on summary similarity alone. The scout must read both full bodies.

Provenance: same failure mode that drove Rule 12 in `/find-duplication`. "Identical N-line bodies" claims must be verified by reading.

### R3. Different APIs serving the same purpose is the finding, not the problem

The finding is "you have two ways to do X." The problem is "they might drift, and maintaining both costs double." Report framing should reflect this — **don't argue that duplication is inherently wrong**. Some duplication is load-bearing (different policies, different callers, different isolation needs). The capability matrix exists to expose the tradeoff, not to advocate for merging.

### R4. Consolidation is not always the right answer

Sometimes "document why both exist" is the correct output. When the divergence is load-bearing (different retry policies, different output shapes, different deployment contexts), unifying forces a compromise that hurts at least one caller. Flag as `consolidation_shape: "keep_separate_document_why"` and stop.

Provenance: `knowledge/` agent-bridge vs direct-service split is a standing example.

### R5. Caller-callee is decomposition, not duplication

If A calls B, they aren't duplicates. This is the most common false positive in function-level comparison and the #1 rejection class in `false-positives.md`. Grep check costs 2 seconds; always do it.

### R6. The fragmented-concern finding is separate from a function finding

"This concern has two homes" is a **structural** finding. The remediation is "designate a canonical home and migrate the other," not "merge two functions." These land first in the triage (higher-value than individual function merges) and don't use capability matrices.

Signals of structural findings: two test modules covering the same feature, two benchmark result sets measuring the same thing, two report directories tracking the same analysis.

### R7. Cross-domain pairs are the highest-value findings

Domain-based grouping partitions candidates. The most interesting duplicates usually cross boundaries — a JSON-LD parser in `discovery` and another in `extraction`, a retry helper in `crawling` and another in `proxy`. After within-domain comparison completes, always run the cross-domain pass (Step 3d-cross).

Provenance: `knowledge/` lists cross-domain sibling implementations observed across prior scans.

### R8. Log format is behavior

Lifted from `/find-duplication` Rule 7. Log strings are contracts with aggregators, dashboards, and humans reading tail output. When the capability matrix shows "identical log output with different message strings," treat the log line as a divergence point, not a consolidation point. The recommendation should lift the surrounding logic, not the log format.

### R9. Three-way+ semantic clusters need union-find merging

Scouts compare pairs. If workflows A, B, and C are all mutually semantic-duplicates, the comparator may emit (A,B), (A,C), (B,C) as three separate candidates. The collapse stage unions candidates that share a site into a single N-way cluster.

Provenance: `/find-duplication` had the identical issue — jscpd emitted (A,B) and (A,C) as separate pair findings. Union-find merge (`_union_shared_sites` in the duplication collapse) fixed it. Same pattern applies here.

### R10. Compare summaries for nomination, bodies for confirmation

Step 3 (compare) uses summaries. It's a **nomination** pass with a lower bar — better to over-nominate than to miss. Step 5 (confirm) does the real filtering with source code.

If Step 3's threshold feels too strict, lower it. If Step 5's rejection rate is too high, raise Step 3's threshold on the next run. They're tunable independently.

### R11. Name normalization matters across detector stages

jscpd uses `Class.method`; Python AST visitors often use bare `method`. When cross-referencing findings from different sources, normalize to the last dotted segment.

Provenance: `/find-duplication` collapse had a silent cross-reference failure for this reason (no overlaps were ever annotated). Verified fix: `method.rsplit(".", 1)[-1]`.

## What to do when these rules conflict

R3 says "don't argue duplication is wrong." R9 says "merge clusters." These aren't contradictory — R3 is about framing in the report, R9 is about correctly identifying the cluster. Always identify the full cluster (R9), then let R3 guide whether the right recommendation is "merge" or "document why both exist" (R4).

## Adding new entries

When a run surfaces a judgment call not covered here, append a new rule (Rn). Include:

- The observation (what the scout saw)
- The decision (what it classified it as)
- The rationale (why that classification was right)
- Any counter-cases (when the rule doesn't apply)

Keep each rule to <8 lines. The terseness is deliberate — this file must stay scan-able.
