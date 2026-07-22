# Go shadow-proposal v1

Load this guide only for a Go `GO-SD-*` finding from
`/find-semantic-duplication`.

## Contract

This is a structured consumer, not another detector. It accepts one complete,
confirmed, function-level Go finding and verifies its current `.go` source
spans plus the upstream matrix rows for result type, returned fields, resolved
direct calls, and visible panic/defer/goroutine policy. It emits
`proposal.md`, `evidence.json`, and `scope.json` beneath one finding directory.

The proposal preserves all four allowed shapes. `keep_separate_document_why`
does not contain a merge/migration plan. Every other shape requires a full
reference review, native tests, stop conditions, and explicit human approval.
The consumer never edits Go source or upgrades the static lead into behavioral
equivalence.

## Run from the host root

```bash
: "${UNIFY_FINDINGS:?Set this to a complete Go findings.json}"
: "${UNIFY_FINDING_ID:?Set this to one confirmed GO-SD identifier}"
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
python3 "${SKILL_ROOT}/scripts/propose_go.py" \
  --findings "${UNIFY_FINDINGS}" \
  --finding-id "${UNIFY_FINDING_ID}" \
  --project-root "$(pwd)" \
  --proposal "reports/unify-shadows/${UNIFY_FINDING_ID}/proposal.md" \
  --evidence "reports/unify-shadows/${UNIFY_FINDING_ID}/evidence.json"
```

Run `go test ./...` before and after. Review the full bodies, project-wide
references, side effects, error/panic behavior, ordering, and concurrency
semantics before authorizing any `/fix-workflow` handoff.
