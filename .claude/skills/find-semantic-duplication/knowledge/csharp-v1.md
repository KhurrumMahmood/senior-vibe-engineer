# C# semantic duplication review

Run the copied `_csharp-semantic/csharp_semantic_facts.py` provider first, then:

```bash
python3 -I -S scripts/detect_csharp_semantic.py \
  --project-root "$PWD" --facts reports/csharp-semantic/facts.json
```

The final JSON and Markdown artifacts are written below
`reports/semantic-duplication/csharp/`. Leads require exactly two selected
non-override/non-partial methods with matching resolved parameter/return types,
normalized source bodies, and direct selected callers. Static shape never
proves behavioral equivalence, substitutability, or refactor safety.
