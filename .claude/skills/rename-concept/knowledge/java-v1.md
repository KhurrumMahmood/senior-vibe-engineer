# Java 17 concept-rename assessment

Load this guide only when eligible production `.java` source exists.

## Authority and impact contract

Run the installed `find-concept-divergence` companion's strict-text rules over
eligible Java source and accept an optional root-contained candidate JSON or
JSONL artifact. Treat those records as lexical leads only. Establish old/new
rename authority solely from compiler-resolved, public, top-level `TypeElement`
identity produced by `JavacTask.parse()` plus `analyze()`.

Require exactly one public new authority, at most one public old authority,
zero resolved old-authority references, zero unresolved matching identifiers,
and clean compiler diagnostics for completion. Keep same-spelled locals and
unrelated types classified separately. Emit the resolved declaration/reference
impact in the assessment JSON and Markdown handoff; never rewrite source.

Defer every matching reflection string, ordinary string/dynamic lookup,
annotation-mediated framework reference, and generated/test/vendor/build
source hit. Do not infer a framework contract. A missing or pre-17 JDK, a
malformed/unresolved compilation unit, an ambiguous authority, a source
symlink, or any deferred reference prevents a clean verdict.

## Installed command

Run from the Java project root after copying `rename-concept` together with its
declared `find-concept-divergence` companion. The host needs `java`, `javac`,
and Python 3 on `PATH`; the skill uses no Maven, Gradle, JAR, language server,
network, toolkit virtual environment, or shared Java helper.

<!-- installed-command:java-assessment:start -->
```bash
PROJECT_ROOT="$(pwd)"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/rename-concept" \
  ".claude/skills/rename-concept"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "rename-concept is not installed" >&2
  exit 2
fi
STRICT_ARGS=()
if [ -n "${RENAME_STRICT_CANDIDATE:-}" ]; then
  STRICT_ARGS=(--strict-candidate "${RENAME_STRICT_CANDIDATE}")
fi
python3 -I -S "${SKILL_ROOT}/scripts/assess.py" \
  "${OLD_CONCEPT:?Set the deprecated glossary concept}" \
  "${NEW_CONCEPT:?Set the canonical glossary concept}" \
  --project-root "${PROJECT_ROOT}" \
  --output "${PROJECT_ROOT}/reports/rename-concept/java-assessment.json" \
  --report "${PROJECT_ROOT}/reports/rename-concept/java-assessment.md" \
  "${STRICT_ARGS[@]}"
```
<!-- installed-command:java-assessment:end -->

Before and after any separately approved manual/IDE rename, compile the same
first-party source surface with `javac --release 17 -proc:none` and run the
project's existing native Java tests. The assessment itself is read-only.
