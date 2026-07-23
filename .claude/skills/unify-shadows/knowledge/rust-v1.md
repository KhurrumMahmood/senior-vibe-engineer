# Rust shadow-proposal v1

Load this guide only for an `RSD-*` lead from the accepted Rust branch of
`/find-semantic-duplication`.

## Contract

Consume one complete `rust-semantic-duplication-v1` `analysis.json`, the exact
content-addressed `rust-semantic-facts-v1` pack it cites, and the adjacent
capability matrix. The adapter validates the full source/configuration
snapshot, per-source hashes, stable-LSP boundary, Cargo 2024 target set,
function/caller citations, matrix rows, and upstream non-claims before writing
anything.

`--shape` is explicit operator input for the structure of a read-only draft.
It is not a detector conclusion, evidence of behavioral equivalence, human
approval, or permission to consolidate source. All four proposal shapes stay
behind a second explicit human review before `/fix-workflow`.

The accepted static evidence does not resolve traits or blanket impls,
generics/monomorphization, macro or procedural-macro expansion, unselected
`cfg`/feature/target variants, unsafe/FFI behavior, runtime reachability or
behavior, external API ownership/compatibility, or semver compatibility. The
consumer accepts only top-level, non-generic free-function leads outside those
recorded boundaries.

## Run from the host root

```bash
: "${RUST_UNIFY_ANALYSIS:?Set this to complete Rust analysis.json}"
: "${RUST_UNIFY_FACTS:?Set this to the exact accepted Rust semantic fact pack}"
: "${RUST_UNIFY_FINDING_ID:?Set this to one confirmed RSD identifier}"
: "${RUST_UNIFY_SHAPE:?Select keep_separate_document_why, share_utilities, complete_migration, or merge_at_workflow}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/unify-shadows" \
  ".agents/skills/unify-shadows" \
  ".claude/skills/unify-shadows"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "unify-shadows guide/tooling is unavailable" >&2
  exit 2
fi
python3 -I -S "${SKILL_ROOT}/scripts/propose_rust.py" \
  --analysis "${RUST_UNIFY_ANALYSIS}" \
  --facts "${RUST_UNIFY_FACTS}" \
  --finding-id "${RUST_UNIFY_FINDING_ID}" \
  --shape "${RUST_UNIFY_SHAPE}" \
  --project-root "$(pwd)" \
  --proposal "reports/unify-shadows/${RUST_UNIFY_FINDING_ID}/proposal.md" \
  --evidence "reports/unify-shadows/${RUST_UNIFY_FINDING_ID}/evidence.json"
```

The independently copied closure is this skill directory plus the accepted
analysis, fact pack, and adjacent capability matrix. It uses only the Python standard library and never imports,
reruns, or embeds the Rust semantic detector, map runtime, Cargo, rust-analyzer,
or repository helpers.

## Outcome boundaries

- Exit 0: `proposal.md`, `evidence.json`, and `scope.json` atomically replace
  one finding directory; source bytes remain unchanged and the proposal still
  requires human approval.
- Exit 2: clean/no-selected-lead, uncertain, rejected, partial, failed, stale,
  malformed, boundary-crossing, mismatched, or unsafe-path evidence; no new
  proposal directory is created and a prior valid directory is preserved.

Before and after any separately approved implementation, run locked/offline
Cargo metadata, check, test, Clippy with warnings denied, rustfmt check, and an
exact executable smoke. Those native checks characterize the selected build;
they do not turn static similarity into behavioral equivalence.
