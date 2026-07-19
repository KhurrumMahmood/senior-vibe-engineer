# Validated-neutral orchestration skills — TypeScript host handoff

Validation revisions: `d841441` (`test(validated-neutral): prove TypeScript
orchestration outcomes`) plus `a92d996` (`fix(project-interview): bundle
installed evidence closure`). Evidence date: 2026-07-19 UTC.

## Outcome and invariant

`converge`, `harvest-learnings`, `organize-project-structure`, `orient`, and
`project-interview` have language-independent core outcomes. On one locked,
runnable TypeScript 5.9.3 webhook-delivery host, the exact five-skill stock
copy install supports these durable results without changing `src/` bytes:

| Skill | Proven core outcome |
| --- | --- |
| `converge` | Artifact-cited fixed `repair` verdict with one next step, success gate, stop condition, and refusal list. |
| `harvest-learnings` | Proposal-only Markdown/JSON harvest with three portable items, one domain-bound item, activation tags, provenance, and N=1 caveats. |
| `organize-project-structure` | Plan-only inventory, three-level abstraction, ideal/constrained topology, naming decisions, move/manual split, and validation stop. |
| `orient` | Human-confirmed `(first-users, external)` state in the fixed canonical JSON schema. |
| `project-interview` | Human-answered draft profile, readable summary, unresolved questions, and evidence manifest. |

None parses TypeScript syntax, resolves modules, chooses a Node framework, or
implements host code. TypeScript supplies a realistic host, paths, native
checks, and source-immutability boundary; the judgment and output contracts
remain useful in another host language.

## Stock installation and dependency truth

The focused replay runs this pinned install from a temporary host outside the
checkout and asserts that exactly five copied directories exist:

```bash
npx --yes skills@1.5.19 add <checkout> \
  --skill converge --skill harvest-learnings \
  --skill organize-project-structure --skill orient \
  --skill project-interview --agent codex --copy -y
```

`harvest-learnings/knowledge/output-schema.md`, the local `orient` inference
script/knowledge, and both `project-interview/scripts/` helpers are copied
correctly. Two unrelated workflows still expose honest closure gaps:

- `converge` does not receive root `scripts/log_effectiveness.py`; its verdict
  and report render, but effectiveness logging is explicitly not claimed.
- `organize-project-structure` does not receive sibling
  `_common/structural-design-principles.md` or `/move-path`; the plan uses the
  principles embedded in `SKILL.md` and does not claim a doctrine read, dry
  run, or applied move.

The first independent D6 replay correctly rejected `project-interview` because
its root `scripts/project_adapt.py` and `scripts/evidence_gate.py` dependencies
were absent. Revision `a92d996` closes that blocker with focused skill-local,
stdlib-only helpers. From the exact copied install, the draft helper now:

- discovers objective TypeScript repo facts without importing human intent;
- writes `user_approved: false` and unanswered interview questions;
- refuses durable apply until a visible-answer edit sets the sole top-level
  approval field to true; and
- leaves application source unchanged.

The installed evidence helper demonstrably fails at `2/3` when `profile.md` is
hidden, then prints `OK: 3/3 required evidence shapes present.` after the
artifact is restored. It also passes against the committed human-answered
scan. No repository-level project-adapt/evidence-gate helper or toolkit venv is
used at runtime.

The two remaining items are installed UX and closeout gaps, not
TypeScript-language gaps. No
broad runtime, copied repository helper layer, or custom installer was added.

## Fixture and final-output proof

`tests/fixtures/validated-neutral-typescript/orchestration/host/` is the one
locked host. It contains ordinary `.ts` entry, metric, and worker modules; a
native Node test and host lint; two ADRs, one known issue, a phase record, and
historically named source/output roots. Five natural tasks live beside it and
contain facts and user intent but not the expected classification, verdict,
translation verdicts, target paths, or profile fields.

`tests/test_validated_neutral_typescript_orchestration.py`:

1. Runs `npm ci --offline --ignore-scripts`, `npm run typecheck`, and `npm test`.
2. Runs the exact pinned copied install and checks local closure and absent
   repository-owned dependencies.
3. Runs the installed project-interview draft helper, proves no invented human
   answers, verifies premature apply refusal, exercises evidence-gate red and
   green, and records the prescribed passing summary.
4. Materializes each captured final result and validates its skill-specific
   output contract rather than a parser/helper surrogate.
5. Rechecks the full `src/` SHA-256 after installation and after every result,
   checks the five source skill directories did not change, and reruns the
   native typecheck at the end.

Focused repair evidence at `a92d996`:

```text
<repo>/.venv/bin/python -m pytest -q \
  tests/test_validated_neutral_typescript_orchestration.py
1 passed in 5.53s

<repo>/.venv/bin/ruff check \
  tests/test_validated_neutral_typescript_orchestration.py
All checks passed!
```

The combined focused run with `tests/test_project_adapt.py` passed 10 tests.
The ecosystem smoke/import gate passed 11 explicit smokes and 45 import-floor
checks. The commit's explicit-file pre-commit run also passed Ruff, YAML,
whitespace, repository lints, host-reference checks, artifact drift, and diff
checks. The generic skill-creator quick validator is inapplicable because it
rejects this repository's required extended frontmatter; repository metadata
lint passed all 76 skills instead.

## What generalized cleanly

- Artifact-cited convergence needs no host-language semantic model.
- Provenance, portability translation, activation, and proposal-only harvest
  semantics apply equally to TypeScript-forged lints, ADRs, and incidents.
- Folder lifecycle, navigation keys, framework/tool floors, and naming context
  are language-neutral judgments; only the concrete constraints differ.
- Maturity and stakes are human facts, so the fixed state contract does not
  become more correct by parsing Python or TypeScript.
- Purpose, critical workflows, tradeoffs, known-bad patterns, and do-not-break
  surfaces are human-intent facts; a TypeScript repo can carry the same profile.
- Natural-task fixtures, final-artifact oracles, exact installed-set checks,
  and source fingerprints are reusable validation procedure.

## What remains host-language or host-facility dependent

The only TypeScript-specific mechanism is the native validation command and
the fixture's actual file/tool paths. Future languages need a locked native
host and its compiler/test command, not a variant of these five skills.
The project-interview discovery/apply and evidence gate are now self-contained
skill facilities. The remaining optional effectiveness logger, move helper,
and shared structure doctrine stay installation/facility dependencies as
listed above. Their absence must remain visible until an installed journey
demonstrates a small, product-worthy repair.

Do not extract a generic prompt executor, artifact-materialization runtime, or
helper bundle. The captured outputs are validation evidence, not an executable
agent implementation, and no second runtime consumer exists.

## Next-language guidance

For Rust, Go, Java/Kotlin, C#, or Ruby, reuse the same five natural outcome
shapes on one idiomatic locked host, substitute `cargo test`, `go test`, the
chosen Gradle/Maven task, `dotnet test`, or the locked Bundler/Rake command, and
fingerprint the application source roots. Reassess repository/tool discovery
constraints for the structure plan; do not claim compiler or framework support
because the prompt workflow stayed neutral.

## Residual risks and next decision

D6 re-review remains pending: the first independent fresh-user agent produced
the correct draft but failed honestly on missing helpers. The repaired exact
stock replay now proves the previously blocked commands and prescribed gate;
an independent rerun should confirm the agent journey without the captured
answer.

The integrator can mark the five core outcomes `validated-neutral` after that
fresh rerun, retaining only the two unrelated closure disclosures. Only
measured confusion in the rerun should trigger another focused repair. UX work
remains later priority.
