# Java semantic-duplication v1

Load this guide only when the target is Java.

## Supported claim

Report conservative function-level static review leads from JDK 17 compiler
facts. Consider only direct `static` production methods that explicitly return
one canonical construction of the same project `record`, populate the same two
or more declared record components, do not directly call each other, and each
have at least one compiler-resolved caller in eligible production source.

`confirmed` means those bounded facts passed. It never means the methods are
behaviorally equivalent, safe to share, or part of one workflow. Instance and
abstract methods, indirect returns, builders, generated/test/vendor source,
dynamic dispatch, reflection, side effects, exceptions, ordering, framework
behavior, and whole-repository runtime caller coverage remain unavailable.

## Run from the host root

```bash
: "${TARGET:=src/main/java}"
REPORT_NAME="${REPORT_NAME:-java-scan}"
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
python3 -I -S "${SKILL_ROOT}/scripts/detect_java_semantic.py" \
  --target "${TARGET}" --project-root "$(pwd)" \
  --report-dir "reports/semantic-duplication/${REPORT_NAME}"
```

Run the host's native Java 17 compile/tests before and after. Judge only
`findings.json`, `triage.md`, and the cited capability matrix. The copied skill
contains the complete stdlib-Python/JDK closure and records its source
fingerprint. Pass one complete confirmed finding to `/unify-shadows`; never
start a mutation workflow directly from detector output.

## Outcome boundaries

- Exit 0, `status=complete`: bounded source/type/caller facts completed.
- Exit 2, `unsupported`: `java`/`javac` is missing or older than 17.
- Exit 2, `failed`: unsafe paths, malformed source, or unavailable type facts;
  no replacement report is published.

The launcher writes atomically only beneath
`reports/semantic-duplication/<name>/`, rejects path escapes/symlinks, excludes
test/generated/vendor source, and never modifies `.java` files.
