# C# semantic rename assessment

Run the copied `_csharp-semantic/csharp_semantic_facts.py` provider first, then:

```bash
python3 -I -S scripts/assess_csharp_rename.py OldName NewName \
  --project-root "$PWD" --facts reports/csharp-semantic/facts.json
```

The final JSON and Markdown artifacts are written below
`reports/rename-concept/csharp/`. The command assesses selected Roslyn-resolved
type declarations/references and never mutates source. Reflection/runtime
names, dynamic and virtual dispatch, partial/generated/vendor inputs, external
consumers, serialization, frameworks, and binary compatibility prevent a
whole-project completion claim without separate evidence.
