# Swift project/lexical family

Use this guide only for a selected Swift A1 skill. Keep this directory beside
the selected skill in the external on-demand library; a consumer-only ambient
install is incomplete.

The provider requires Swift, `swiftc`, and Swift Format. Optional
project-owned check/smoke products with exact expected output strengthen the
native gate when the host actually provides them:

```bash
SWIFT_NATIVE_ARGS=(
  ${SWIFT_CHECK_PRODUCT:+--check-product "$SWIFT_CHECK_PRODUCT"}
  ${SWIFT_CHECK_PRODUCT:+--expected-check "$SWIFT_CHECK_OUTPUT"}
  ${SWIFT_SMOKE_PRODUCT:+--smoke-product "$SWIFT_SMOKE_PRODUCT"}
  ${SWIFT_SMOKE_PRODUCT:+--expected-smoke "$SWIFT_SMOKE_OUTPUT"}
)
```

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run the matching command:

- `adapt-project`: `python3 -I -S "$SKILL_ROOT/scripts/discover_swift.py" --project-root "$PWD" --output-dir "$PWD/reports/adapt-project/swift" "${SWIFT_NATIVE_ARGS[@]}" .`
- `explain-code`: `python3 -I -S "$SKILL_ROOT/scripts/explain_swift.py" --project-root "$PWD" --target Sources --output "$PWD/reports/explanations/swift.md" "${SWIFT_NATIVE_ARGS[@]}"`
- `find-comment-drift`: `python3 -I -S "$SKILL_ROOT/scripts/analyze_comments_swift.py" --project-root "$PWD" --target Sources --output-dir "$PWD/reports/find-comment-drift/swift" "${SWIFT_NATIVE_ARGS[@]}"`
- `find-concept-divergence`: `python3 -I -S "$SKILL_ROOT/scripts/scan_swift.py" --project-root "$PWD" --glossary "$PWD/.claude/contracts/concepts.yaml" --output "$PWD/reports/find-concept-divergence/swift/findings.jsonl" --report "$PWD/reports/find-concept-divergence/swift/report.md" "${SWIFT_NATIVE_ARGS[@]}" Sources`
- `find-duplication`: `python3 -I -S "$SKILL_ROOT/scripts/run_swift.py" --project-root "$PWD" --target Sources --output-dir "$PWD/reports/duplication/swift" "${SWIFT_NATIVE_ARGS[@]}"`
- `find-folder-topology-drift`: `python3 -I -S "$SKILL_ROOT/scripts/detect_swift.py" --project-root "$PWD" --swift-root Sources --output "$PWD/reports/find-folder-topology-drift/swift/detections.jsonl" "${SWIFT_NATIVE_ARGS[@]}"`
- `audit-decisions`: `python3 -I -S "$SKILL_ROOT/scripts/audit_swift.py" --project-root "$PWD" --target . --output-dir "$PWD/reports/audit-decisions/swift" "${SWIFT_NATIVE_ARGS[@]}"`
- `find-complexity-hotspots`: `python3 -I -S "$SKILL_ROOT/scripts/run_swift.py" --project-root "$PWD" --target Sources --output-dir /tmp/find-complexity-hotspots/swift --no-host-write "${SWIFT_NATIVE_ARGS[@]}"`
- `find-standard-gaps`: `python3 -I -S "$SKILL_ROOT/scripts/scan_coverage_swift.py" --project-root "$PWD" --target Sources --ideas "${SWIFT_STANDARDS:?}" --output-dir "$PWD/reports/find-standard-gaps/swift" "${SWIFT_NATIVE_ARGS[@]}"`

The provider runs restrictive SwiftPM, per-file compiler parse, strict format,
direct-check, smoke, roles, fingerprints, and lifecycle gates. These outcomes
do not establish resolved symbols, cross-module semantics, macros, framework
conventions, runtime behavior, equivalence, or safe consolidation/moves.
The syntax consumers additionally make no callee identity, exception-flow,
runtime-cost, ADR-applicability, general-lint, or refactor-authority claim.
For complexity dogfood, a package dependency/plugin/target-shape gate may
leave the run `partial` while retaining hash-bound lexical leads. Those leads
are useful scouts, not compiler-validated or clean project conclusions.
