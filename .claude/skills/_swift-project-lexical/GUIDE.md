# Swift project/lexical family

Use this guide only for a selected Swift A1 skill. Keep this directory beside
the selected skill in the external on-demand library; a consumer-only ambient
install is incomplete.

The provider requires Swift, `swiftc`, and Swift Format plus dependency-free
host check/smoke products with exact expected output. Every command needs:

```bash
SWIFT_NATIVE_ARGS=(
  --check-product "${SWIFT_CHECK_PRODUCT:?}"
  --expected-check "${SWIFT_CHECK_OUTPUT:?}"
  --smoke-product "${SWIFT_SMOKE_PRODUCT:?}"
  --expected-smoke "${SWIFT_SMOKE_OUTPUT:?}"
)
```

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run the matching command:

- `adapt-project`: `python3 -I -S "$SKILL_ROOT/scripts/discover_swift.py" --project-root "$PWD" --output-dir "$PWD/reports/adapt-project/swift" "${SWIFT_NATIVE_ARGS[@]}" .`
- `explain-code`: `python3 -I -S "$SKILL_ROOT/scripts/explain_swift.py" --project-root "$PWD" --target Sources --output "$PWD/reports/explanations/swift.md" "${SWIFT_NATIVE_ARGS[@]}"`
- `find-comment-drift`: `python3 -I -S "$SKILL_ROOT/scripts/analyze_comments_swift.py" --project-root "$PWD" --target Sources --output-dir "$PWD/reports/find-comment-drift/swift" "${SWIFT_NATIVE_ARGS[@]}"`
- `find-concept-divergence`: `python3 -I -S "$SKILL_ROOT/scripts/scan_swift.py" --project-root "$PWD" --glossary "$PWD/.claude/contracts/concepts.yaml" --output "$PWD/reports/find-concept-divergence/swift/findings.jsonl" --report "$PWD/reports/find-concept-divergence/swift/report.md" "${SWIFT_NATIVE_ARGS[@]}" Sources`
- `find-duplication`: `python3 -I -S "$SKILL_ROOT/scripts/run_swift.py" --project-root "$PWD" --target Sources --output-dir "$PWD/reports/duplication/swift" "${SWIFT_NATIVE_ARGS[@]}"`
- `find-folder-topology-drift`: `python3 -I -S "$SKILL_ROOT/scripts/detect_swift.py" --project-root "$PWD" --swift-root Sources --output "$PWD/reports/find-folder-topology-drift/swift/detections.jsonl" "${SWIFT_NATIVE_ARGS[@]}"`

The provider runs restrictive SwiftPM, per-file compiler parse, strict format,
direct-check, smoke, roles, fingerprints, and lifecycle gates. These outcomes
do not establish resolved symbols, cross-module semantics, macros, framework
conventions, runtime behavior, equivalence, or safe consolidation/moves.
