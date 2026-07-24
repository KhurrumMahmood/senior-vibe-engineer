# Kotlin/JVM lexical and syntax family

Use this guide only when the selected target has an exact schema-v1
`kotlin-project.json` and current `.native-build/kotlin-build-evidence.json`.
Keep `_kotlin` beside the selected consumer in the external on-demand library.
Set `KOTLINC` to the absolute Kotlin/JVM 2.4.10 compiler and `JAVA` to the
absolute JDK 17 executable. The host evidence must content-address the exact
manifest inputs, commands, jars, native test, smoke output, and source bytes.

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run one entrypoint:

- `adapt-project`: `python3 -I -S "$SKILL_ROOT/scripts/discover_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --output-dir "$PWD/reports/adapt-project/kotlin" .`
- `audit-decisions`: `python3 -I -S "$SKILL_ROOT/scripts/audit_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --target . --output-dir "$PWD/reports/audit-decisions/kotlin"`
- `explain-code`: `python3 -I -S "$SKILL_ROOT/scripts/explain_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --target . --output "$PWD/reports/explanations/kotlin.md"`
- `find-comment-drift`: `python3 -I -S "$SKILL_ROOT/scripts/analyze_comments_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --target src --output-dir "$PWD/reports/find-comment-drift/kotlin"`
- `find-complexity-hotspots`: `python3 -I -S "$SKILL_ROOT/scripts/run_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --target src --output-dir "$PWD/reports/complexity-hotspots/kotlin"`
- `find-concept-divergence`: `python3 -I -S "$SKILL_ROOT/scripts/scan_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --glossary "$PWD/.claude/contracts/concepts.json" --output "$PWD/reports/concept-divergence/kotlin/findings.jsonl" --report "$PWD/reports/concept-divergence/kotlin/report.md" .`
- `find-duplication`: `python3 -I -S "$SKILL_ROOT/scripts/run_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --target src --output-dir "$PWD/reports/duplication/kotlin"`
- `find-folder-topology-drift`: `python3 -I -S "$SKILL_ROOT/scripts/detect_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --kotlin-root src/main/kotlin --min-cluster-size 3 --output "$PWD/reports/folder-topology/kotlin/detections.jsonl"`
- `find-omnibus`: `python3 -I -S "$SKILL_ROOT/scripts/run_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --target src --output-dir "$PWD/reports/omnibus/kotlin" --scout-dir "$PWD/reports/omnibus/kotlin/scout"`
- `find-standard-gaps`: `python3 -I -S "$SKILL_ROOT/scripts/scan_coverage_kotlin.py" --project-root "$PWD" --kotlinc "$KOTLINC" --java "$JAVA" --target src --ideas "${KOTLIN_STANDARDS:?Set the host-owned Kotlin standards JSON}" --output-dir "$PWD/reports/standard-gaps/kotlin"`
- `map-subsystem`: `python3 -I -S "$SKILL_ROOT/scripts/map_kotlin.py" --name "${MAP_NAME:?}" --target "${MAP_TARGET:?}" --project-root "$PWD" --output "$PWD/.engineering/docs/subsystems/${MAP_NAME}.md" --evidence "$PWD/reports/map/${MAP_NAME}/kotlin-map.json" --kotlinc "$KOTLINC" --java "$JAVA"`

These branches consume authored lowercase `.kt` source syntax only. Tests,
generated, vendor, build, tooling, symlink, and `.kts` roles remain visible but
excluded. Tokens, comments, declarations, body fingerprints, branch keywords,
and direct call spellings do not resolve symbols, calls, overrides, delegation,
reflection, generated members, Java interop, Gradle variants, framework
registration, runtime behavior, equivalence, or refactor safety.

`map-subsystem` additionally requires `_kotlin-semantic`, an exact semantic
manifest over the same selected paths and hashes, and the limits in that
provider's guide.
