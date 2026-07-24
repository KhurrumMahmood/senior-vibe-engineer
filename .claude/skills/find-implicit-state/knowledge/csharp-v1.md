# C# semantic implicit-state review

Run the copied `_csharp-semantic/csharp_semantic_facts.py` provider first, then:

```bash
python3 -I -S scripts/detect_csharp_state.py \
  --project-root "$PWD" --facts reports/csharp-semantic/facts.json
```

The final JSON and Markdown artifacts are written below
`reports/find-implicit-state/csharp/`. Candidates require a selected string
property named state/status/phase and at least two compiler-resolved direct
literal values. The observed set is not a closed domain or migration plan;
serialization, reflection, generated code, external callers, frameworks, and
binary compatibility require human review.
