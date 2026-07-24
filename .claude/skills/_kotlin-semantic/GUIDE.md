# Kotlin/JVM pinned semantic read-only family

Use this guide only for a selected Kotlin semantic skill. Keep
`_kotlin-semantic` beside the consumer in the external on-demand library. The
host must provide an exact `kotlin-semantic-project.json`, dependency-free
sources/tests, native test and smoke mains with expected stdout, the Homebrew
Kotlin/JVM 2.4.10 compiler distribution, and JDK 17.

First produce one content-addressed fact pack:

```bash
SEMANTIC_ROOT=".agents/skills/on-demand/_kotlin-semantic"
KOTLINC="${KOTLINC:?Set the absolute Homebrew Kotlin/JVM 2.4.10 compiler}"
JAVA="${JAVA:?Set the absolute JDK 17 java executable}"
python3 -I -S "$SEMANTIC_ROOT/kotlin_semantic_facts.py" \
  --project-root "$PWD" \
  --manifest kotlin-semantic-project.json \
  --output reports/kotlin-semantic/facts.json \
  --kotlinc "$KOTLINC" --java "$JAVA"
```

Then set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run one consumer:

- `find-dormant`: `python3 -I -S "$SKILL_ROOT/scripts/detect_kotlin_dormant.py" --project-root "$PWD" --facts reports/kotlin-semantic/facts.json`
- `find-implicit-state`: `python3 -I -S "$SKILL_ROOT/scripts/detect_kotlin_state.py" --project-root "$PWD" --facts reports/kotlin-semantic/facts.json`
- `find-incomplete-sweep`: `python3 -I -S "$SKILL_ROOT/scripts/detect_kotlin_incomplete_sweep.py" --project-root "$PWD" --facts reports/kotlin-semantic/facts.json`
- `find-semantic-duplication`: `python3 -I -S "$SKILL_ROOT/scripts/detect_kotlin_semantic.py" --project-root "$PWD" --facts reports/kotlin-semantic/facts.json`
- `rename-concept`: `python3 -I -S "$SKILL_ROOT/scripts/assess_kotlin_rename.py" "${OLD_CONCEPT:?}" "${NEW_CONCEPT:?}" --project-root "$PWD" --facts reports/kotlin-semantic/facts.json`

The native K2 CLI compile/test/smoke gates a deprecated K1 `BindingContext`
read pinned to exact compiler, stdlib, helper-source, manifest, and input
hashes. This is not the stable Analysis API. Facts cover only selected direct
declarations, calls/references, assignments, constructor arguments, explicit
overrides, and extensions. Reflection, callable references, delegated
properties, generated/KAPT/KSP sources, compiler plugins, Gradle variants,
Java sources/callers, expect/actual, `.kts`, framework registration, runtime
reachability, deletion, behavioral equivalence, codemod safety, and mutation
remain unavailable. Stale or mismatched facts produce a partial artifact with
no promoted findings.
