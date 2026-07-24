# C# semantic incomplete-sweep review

Run the copied `_csharp-semantic/csharp_semantic_facts.py` provider first, then:

```bash
python3 -I -S scripts/detect_csharp_incomplete_sweep.py \
  --project-root "$PWD" --facts reports/csharp-semantic/facts.json
```

The final JSON and Markdown artifacts are written below
`reports/find-incomplete-sweep/csharp/`. A lead requires one resolved optional
constructor parameter explicitly supplied at least twice and omitted exactly
once among three or more selected direct calls. This is call-shape evidence,
not change chronology, intent, or automatic edit authority.
