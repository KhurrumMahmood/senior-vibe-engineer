# Java incomplete-sweep v1

Load this guide only when the target is Java.

## Supported claim

Produce one narrow human-review lead from JDK 17 compiler facts. Group only
compiler-resolved direct `new` calls to the same project `record`. The record
must have a prefix overload that delegates to its canonical constructor with a
literal default for the final component. Admit a candidate only when at least
three canonical calls pass the same comparable non-default literal, exactly one
call uses the overload, and Git blame shows every canonical call line is newer
than the overload call line.

This does not cover builders, setters, methods, reflection, dependency classes,
framework binding, non-literal values, multiple missing sites, or semantic intent.
The compiler result is a scout lead, not an automatic correction.

## Run from the host root

```bash
: "${TARGET:=src/main/java}"
REPORT_NAME="${REPORT_NAME:-java-scan}"
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
  printf '%s\n' "find-incomplete-sweep guide/tooling is unavailable" >&2
  exit 2
fi
python3 -I -S "${SKILL_ROOT}/scripts/detect_java_incomplete_sweep.py" \
  --target "${TARGET}" --project-root "$(pwd)" \
  --report-dir "reports/find-incomplete-sweep/${REPORT_NAME}"
python3 -I -S "${SKILL_ROOT}/scripts/scout.py" \
  --scan-dir "reports/find-incomplete-sweep/${REPORT_NAME}" --project-root "$(pwd)"
```

Write exactly one fixed-vocabulary record per packet to
`scout_verdicts.json`, then run `triage.py` with `python3 -I -S`. Run the
host's native Java 17 compile/test command before and after. A copied skill
contains the launcher, compiler helper, scout, and triage closure; the manifest
fingerprints the exact launcher/helper pair.

## Outcome boundaries

- Exit 0, `status=complete`: compiler and Git facts completed; judge packets.
- Exit 0, `status=partial`: Git evidence was missing or failed; candidates are
  withheld and deferments remain visible.
- Exit 2, `unsupported`: `java`/`javac` is missing or older than 17.
- Exit 2, `failed`: unsafe paths, malformed source, or unavailable type facts;
  no replacement report is published.

Test/generated/vendor paths are inventoried but excluded. Broad walks do not
follow links; direct symlink targets and report paths are rejected. The detector
writes atomically only below `reports/find-incomplete-sweep/<name>/` and never
modifies `.java` source.
