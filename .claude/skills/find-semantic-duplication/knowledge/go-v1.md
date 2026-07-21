# Go semantic-duplication v1

Load this guide only when the target is Go.

## Supported claim

The skill reports conservative function-level static review leads. It considers
only top-level production functions whose active package facts resolve through
Go 1.22+ `go list`, `go/parser`, and `go/types`. A candidate pair must return
the same named struct type, directly return the same two-or-more named fields,
avoid a resolved caller/callee relationship, differ enough to stay outside
lexical-clone triage, and expose the same visible panic/recover/defer/goroutine
policy. Function-value calls make the pair uncertain.

`confirmed` means the bounded static checks passed. It does not mean the
functions are behaviorally equivalent, safe to merge, or part of the same
workflow. Methods, interface dispatch, reflection, generated/test code,
framework behavior, side-effect equivalence, concurrency behavior, and safe
refactoring remain unavailable.

Inactive build-constrained source makes the scan `partial`. Keep its inventory
visible; `/unify-shadows` refuses partial evidence.

## Run from the host root

Use the router-supplied guide and tooling path when this skill lives in the
on-demand library. The fallback search also supports an explicit ambient copy.

```bash
: "${TARGET:=.}"
REPORT_NAME="${REPORT_NAME:-go-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-semantic-duplication" \
  ".agents/skills/find-semantic-duplication" \
  ".claude/skills/find-semantic-duplication"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-semantic-duplication guide/tooling is unavailable" >&2
  exit 2
fi
python3 "${SKILL_ROOT}/scripts/detect_go_semantic.py" \
  --target "${TARGET}" \
  --project-root "$(pwd)" \
  --report-dir "reports/semantic-duplication/${REPORT_NAME}"
```

Run `go test ./...` before and after the read-only scan. Judge the result from
`findings.json`, `triage.md`, and the cited capability matrix. A confirmed lead
may be passed to `/unify-shadows`; do not invoke a mutation workflow directly.

## Outcome boundaries

- Exit 0, `status=complete`: bounded facts are usable.
- Exit 0, `status=partial`: some selected source was inactive under the current
  build; retain the report but do not synthesize a proposal.
- Exit 2: malformed source, unavailable/old Go, unsafe paths, or unavailable
  type facts; no replacement report is published.
