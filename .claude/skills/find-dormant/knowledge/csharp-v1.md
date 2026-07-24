# C# semantic dormant review

Run the copied `_csharp-semantic/csharp_semantic_facts.py` provider first, then:

```bash
python3 -I -S scripts/detect_csharp_dormant.py \
  --project-root "$PWD" --facts reports/csharp-semantic/facts.json
```

The final JSON and Markdown artifacts are written below
`reports/find-dormant/csharp/`. A lead means a selected private method has no
resolved selected-project call/reference. It is never safe-delete authority:
delegates, reflection, dynamic/override/interface dispatch, generated inputs,
external callers, and runtime registration remain unresolved.
