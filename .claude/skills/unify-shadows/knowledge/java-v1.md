# Java shadow-proposal v1

Load this guide only for a `JAVA-SD-*` finding from
`/find-semantic-duplication`.

## Contract

Consume one complete, confirmed, function-level Java static lead. Validate its
current `.java` member spans and compiler-resolved direct-caller citations
against the upstream SHA-256 source manifest, then validate the analyzer
fingerprint and capability-matrix rows for record return type, returned
components, caller/callee relationship, and direct callers. Do not run the
detector again or infer behavioral equivalence.

Emit `proposal.md`, `evidence.json`, and `scope.json` under one finding
directory. Preserve all four upstream shapes. `keep_separate_document_why`
must contain no merge, migration, or consolidation action. Every shape remains
read-only and requires explicit human approval before `/fix-workflow`.

## Run from the host root

```bash
: "${UNIFY_FINDINGS:?Set this to a complete Java findings.json}"
: "${UNIFY_FINDING_ID:?Set this to one confirmed JAVA-SD identifier}"
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
python3 -I -S "${SKILL_ROOT}/scripts/propose_java.py" \
  --findings "${UNIFY_FINDINGS}" --finding-id "${UNIFY_FINDING_ID}" \
  --project-root "$(pwd)" \
  --proposal "reports/unify-shadows/${UNIFY_FINDING_ID}/proposal.md" \
  --evidence "reports/unify-shadows/${UNIFY_FINDING_ID}/evidence.json"
```

Run the host's Java 17 compile/tests before and after this read-only handoff.
Review full bodies, all project references, inputs, outputs, exceptions, side
effects, ordering, framework/runtime behavior, and concurrency before approval.

## Outcome boundaries

- Exit 0: all three proposal artifacts exist and source files are unchanged.
- Exit 2: missing, unconfirmed, partial, stale, malformed, wrong-language, or
  unsafe-path evidence; no proposal directory is created or replaced.

The consumer is stdlib-only, runs in a copied installation with `python3 -I -S`,
records upstream and consumer fingerprints, rejects symlink/path escapes, and
never invokes the semantic detector or JDK analysis itself.
