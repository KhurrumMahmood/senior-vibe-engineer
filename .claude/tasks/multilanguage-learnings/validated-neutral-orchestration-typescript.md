# Validated-neutral orchestration skills — TypeScript host handoff

Validation revision: `d841441` (`test(validated-neutral): prove TypeScript
orchestration outcomes`). Evidence date: 2026-07-19 UTC.

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

`harvest-learnings/knowledge/output-schema.md` and the local `orient` inference
script/knowledge are copied correctly. The install also exposes honest closure
gaps:

- `converge` does not receive root `scripts/log_effectiveness.py`; its verdict
  and report render, but effectiveness logging is explicitly not claimed.
- `organize-project-structure` does not receive sibling
  `_common/structural-design-principles.md` or `/move-path`; the plan uses the
  principles embedded in `SKILL.md` and does not claim a doctrine read, dry
  run, or applied move.
- `project-interview` does not receive root `scripts/project_adapt.py` or
  `scripts/evidence_gate.py`; the draft/evidence paths are validated by the
  focused oracle, but repo discovery and the prescribed gate transcript are
  explicitly not claimed.

These are installed UX and closeout gaps, not TypeScript-language gaps. No
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
3. Materializes each captured final result and validates its skill-specific
   output contract rather than a parser/helper surrogate.
4. Rechecks the full `src/` SHA-256 after installation and after every result,
   checks the five source skill directories did not change, and reruns the
   native typecheck at the end.

Focused evidence at `d841441`:

```text
<repo>/.venv/bin/python -m pytest -q \
  tests/test_validated_neutral_typescript_orchestration.py
1 passed in 17.80s

<repo>/.venv/bin/ruff check \
  tests/test_validated_neutral_typescript_orchestration.py
All checks passed!
```

The commit's explicit-file pre-commit run also passed Ruff, YAML, whitespace,
repository lints, host-reference checks, and diff checks.

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
Optional repo helpers and shared doctrine remain installation/facility
dependencies as listed above. Their absence must remain visible until an
installed journey demonstrates a small, product-worthy repair.

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

D6 remains pending: an independent fresh-user agent has not yet received only
the raw host, installed skill, and natural prompt and produced one of these
artifacts without the captured answer. The automated replay proves install
shape, native host validity, final artifact contracts, and immutability, not
independent model judgment.

The integrator can mark the five core outcomes `validated-neutral` with the
three named closure disclosures. The next useful action is a fresh-user replay;
only measured confusion in that replay should trigger a focused installation
repair. UX work remains later priority.
