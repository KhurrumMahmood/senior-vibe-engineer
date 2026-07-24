# C# accepted semantic-shadow disposition

Produce the C# semantic facts and final duplication analysis first. A reviewer
must then write a content-addressed `csharp-duplication-acceptance-v1` artifact
selecting one exact pair, a disposition (`keep_separate_document_why`,
`share_utilities`, `complete_migration`, or `merge_at_workflow`), and the exact
boundary verdict map from `_csharp-semantic/csharp_accepted_evidence.py`.

```bash
python3 -I -S scripts/propose_csharp.py \
  --project-root "$PWD" \
  --facts reports/csharp-semantic/facts.json \
  --analysis reports/semantic-duplication/csharp/analysis.json \
  --acceptance reports/semantic-duplication/csharp/accepted-duplication.json \
  --output-dir reports/unify-shadows/csharp/CSD-01
```

The consumer re-resolves both exact producer-selected definitions and their
distinct direct callers from the accepted fact pack; it performs no new
detection. The result is either a read-only proposal or a documented
keep-separate disposition. Matching Roslyn contracts/body shape never claims
runtime or behavioral equivalence, and source mutation always requires separate
authority.
