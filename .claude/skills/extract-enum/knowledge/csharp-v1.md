# C# accepted enum proposal

Produce `reports/csharp-semantic/facts.json` and the final
`reports/find-implicit-state/csharp/findings.json` first. A reviewer must then
write a content-addressed `csharp-state-acceptance-v1` artifact selecting one
exact property symbol, the exact enum member/wire-value mapping, and every
boundary verdict required by `_csharp-semantic/csharp_accepted_evidence.py`.

```bash
python3 -I -S scripts/collect_csharp_state.py \
  --project-root "$PWD" \
  --facts reports/csharp-semantic/facts.json \
  --findings reports/find-implicit-state/csharp/findings.json \
  --acceptance reports/find-implicit-state/csharp/accepted-state.json \
  --output-dir reports/extract-enum/csharp/job-status
```

The consumer does no detection. It freshness-checks the fact pack, project
manifest, every manifest source, the provider/helper, pinned SDK/Roslyn tools,
reference pack, producer artifact, and separate human acceptance. A successful
`targets.json` is read-only and review-required; it is not migration authority.
Refusal replaces earlier success artifacts, and a later valid run replaces the
refusal.
