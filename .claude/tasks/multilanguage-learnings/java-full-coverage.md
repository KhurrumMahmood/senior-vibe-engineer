# Java full-coverage learning

Java 17 support is now evidence-backed for all 22 language-level skills. The
useful unit of expansion was a contract cohort—lexical/filesystem, syntax,
semantic/project, or proposal/guard—not one universal Java adapter. Every
skill still reaches its own final report, proposal, mutation, or guard boundary
from a copied on-demand closure.

What transferred well across cohorts:

- one standalone JDK 17 fixture and native `javac --release 17 -proc:none`
  obligation per family;
- explicit first-party/generated/test/vendor/build/symlink source roles;
- typed `complete`, `partial`, `unsupported`, and `failed` terminal states;
- exact documented-command replays from `.agents/skills/on-demand`,
  `.agents/skills`, and `.claude/skills`;
- producer source manifests checked by proposal consumers; and
- metadata-first routing to a fresh non-context execution agent.

What should remain family-local: compiler facts and artifact schemas. A symbol
inventory, call graph, state detector, and move proposal do not share a stable
semantic result contract merely because all use JDK APIs. The only measured
identical work worth consolidating was inside `audit-decisions`, where selected
Java files now share one JDK probe and one helper launch.

The final review exposed a reusable acceptance rule: test the exact documented
shell block through a valid-to-failed rerun at the same destination. A helper
can emit the right unsupported JSON while its wrapper returns success or leaves
an older clean report visible. Candidate-level and first-run tests do not prove
the user journey.

Cost matters. From the staged-expansion baseline `8167ab4` through reviewed
`cf48aa5`, the Java pass added about 11,195 net lines under `.claude/skills/`
and 6,096 net test lines. The coverage is real, but that footprint should not
be copied blindly into C# or later languages. Before the next full pass, compare
one family-local helper and one established native-tool adapter against this
baseline, counting closure and test code as well as runtime latency.

Verification at closeout: 147 integrated Java tests, 157 preserved-language
family tests, 114 fresh adversarial-review tests, and 87 capability/router/
matrix closeout tests passed. The fresh product review returned PROMOTE at
`cf48aa5`; all 22 clear Java requests route to distinct intended skills.
