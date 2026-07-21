# Go v1: convention-aware package-split proposals

Read this reference only for a Go folder-reorganization proposal.

## Contract

Go directories are packages, so a filename cluster does not by itself justify
creating a folder. The helper separates four kinds of evidence, in precedence
order:

1. an explicit project convention;
2. a detected framework/tool convention;
3. hard Go package and runtime constraints;
4. the generic navigation heuristic that three prefix siblings suggest a
   cluster.

The current bounded implementation accepts an explicit JSON project profile
and records the other layers in the output. It does not yet infer a framework
convention. Without an applicable project rule it emits
`defer_project_convention_required`. Language-safety evidence always wins over
an allow rule. V1 is restricted to `internal/` packages so the module-local
impact table cannot misrepresent unknown external consumers as complete.

Profile schema:

```json
{
  "schema_version": 1,
  "rules": [
    {
      "parent": "internal/legacy",
      "prefix": "billing",
      "action": "allow_package_split",
      "destination": "internal/legacy/billing",
      "rationale": "Billing is the project's chosen navigation boundary."
    }
  ]
}
```

`action` is `allow_package_split` or `deny_package_split`. Matching conflicting
rules block. An allowed destination must equal `<parent>/<prefix>` in v1.

The helper uses the host's `go list`, `go/parser`, and `go/types` evidence. It
enumerates selected production and matching test moves plus qualified external
references to selected exported declarations. It blocks or defers package-
private/cross-boundary references, package initialization, ambiguous imports,
cgo/external-test configurations, inactive cluster files, unresolved package
or type graphs, malformed source, unsafe paths, and unsupported toolchains.
It never edits source.

## Installed command

Run from the target module root after copying this selected skill. The command
checks for the host Go tool before `go run` and emits an honest unsupported
result when the tool is absent.

<!-- installed-command:go-proposal:start -->
```bash
PFR_PARENT="${PFR_PARENT:-internal/legacy}"
PFR_PREFIX="${PFR_PREFIX:-billing}"
PFR_NAME="${PFR_NAME:-${PFR_PARENT//\//-}__${PFR_PREFIX}}"
PFR_CONVENTIONS="${PFR_CONVENTIONS:-}"
PFR_MINIMUM_GO="${PFR_MINIMUM_GO:-1.22}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/propose-folder-reorganization" \
  ".claude/skills/propose-folder-reorganization"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "propose-folder-reorganization is not available" >&2
  exit 2
fi
REPORT_ROOT="reports/propose-folder-reorganization/${PFR_NAME}"
if ! command -v go >/dev/null 2>&1; then
  mkdir -p "${REPORT_ROOT}"
  printf '%s\n' '{"schema_version":1,"skill":"propose-folder-reorganization","language":"go","status":"unsupported","recommendation":"defer_tool_missing","failure_kind":"go_tool_missing"}' \
    > "${REPORT_ROOT}/inspection.json"
  printf '%s\n' '# Go folder reorganization proposal' '' '**Status:** `unsupported`' '' 'Go was not found on PATH.' \
    > "${REPORT_ROOT}/proposal.md"
  exit 0
fi
PFR_CONVENTION_ARGS=()
if [ -n "${PFR_CONVENTIONS}" ]; then
  PFR_CONVENTION_ARGS=(--conventions "${PFR_CONVENTIONS}")
fi
go run "${SKILL_ROOT}/scripts/propose_go.go" \
  --parent "${PFR_PARENT}" \
  --prefix "${PFR_PREFIX}" \
  --cluster-judgment split \
  --project-root "$(pwd)" \
  "${PFR_CONVENTION_ARGS[@]}" \
  --minimum-go "${PFR_MINIMUM_GO}" \
  --inspection "${REPORT_ROOT}/inspection.json" \
  --proposal "${REPORT_ROOT}/proposal.md"
```
<!-- installed-command:go-proposal:end -->

## Human handoff

Treat `ready` as move-plan evidence, not execution authority. Before and after
the separately reviewed move, run `go test ./...` and `go vet ./...`. Re-run
the proposal if the source or convention profile changes.
