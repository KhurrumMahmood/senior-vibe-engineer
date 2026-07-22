# Go incomplete-sweep v1

Load this guide only when the target is Go.

## Supported claim

The Go detector produces a human-review lead, not an automatic correction. It
uses Go 1.22+ `go list`, `go/parser`, and `go/types` and considers only direct
calls that resolve to a project **top-level function**. The called parameter at
one position and every observed argument at that position must be keyed struct
literals. A field becomes a candidate only when:

- the call group has at least four sites, with a 75% strong-majority threshold;
- exactly one literal omits the field;
- every present literal supplies the same compile-time comparable value; and
- Git blame shows every present call line is newer than the omitted call line.

The generated `manifest.json` includes the resolved `present_sites`; run
`scout.py --scan-dir ... --project-root ...` without `--paths`. It flows into
the normal one-verdict-per-packet `scout_verdicts.json` contract and then
`triage.py`. A `forgotten` verdict may hand off to `/fix-workflow`; detection
does not modify Go source.

## Run from the host root

Resolve a copied installation (or the ambient checkout) before invoking the
family-local launcher:

```bash
: "${TARGET:=.}"
REPORT_NAME="${REPORT_NAME:-go-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-incomplete-sweep" \
  ".agents/skills/find-incomplete-sweep" \
  ".claude/skills/find-incomplete-sweep"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-incomplete-sweep is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
python3 "${SKILL_ROOT}/scripts/detect_go_incomplete_sweep.py" \
  --target "${TARGET}" --project-root "$(pwd)" \
  --report-dir "reports/find-incomplete-sweep/${REPORT_NAME}"
python3 "${SKILL_ROOT}/scripts/scout.py" \
  --scan-dir "reports/find-incomplete-sweep/${REPORT_NAME}" --project-root "$(pwd)"
```

Run `go test ./...` before and after this read-only scan. A copied installation
contains both the Python launcher and Go helper; `manifest.json` records a
`source_fingerprint` for that exact runtime pair.

## Deferred boundaries

Never infer through methods or interface dispatch, function values, reflection,
dynamic/unresolved calls, external functions, unkeyed or dynamic struct
literals, multiple possible stragglers, or inconsistent/non-comparable field
values. They are emitted as deferred records, not candidates. Build-tagged or
otherwise inactive selected Go files make the manifest `partial`; they never
silently count as covered source.

Git evidence is mandatory. A no-repository, missing-blame, or failed-blame
candidate is deferred and the manifest is `partial`, with
`project_resolution.git_evidence` set to `insufficient` or `failed`. A group
where all evidence is available but not all present lines are newer is
`gated_out` as likely deliberate.

## Outcome boundaries

| Outcome | Meaning | Action |
|---|---|---|
| Exit 0, `status=complete` | Active-build semantic and Git facts completed. | Judge only the generated packets. |
| Exit 0, `status=partial` | Inactive source or insufficient/failed Git evidence withheld some leads. | Keep the visible deferments; do not claim a clean sweep. |
| Exit 2, `unsupported` | Go is missing or older than 1.22. | Install/use a supported host Go; do not substitute a non-host dependency. |
| Exit 2, `failed` | Unsafe path, malformed source, or unavailable type facts. | Fix the invocation/source issue; no replacement report is published. |

The launcher rejects target/report paths that escape the project or traverse a
symbolic link. Broad source walks skip links rather than following them. It
writes an atomically staged report only below
`reports/find-incomplete-sweep/<name>/`.
