# C# staged exact property-type guard

Run this only after the accepted enum migration exists, a fresh C# semantic fact
pack proves that migrated tree, and a separate content-addressed
`csharp-enum-migration-acceptance-v1` artifact binds the enum proposal, migrated
facts/inventory, exact property signature, boundary verdicts, and a complete
buildable String-reversion tree.

```bash
python3 -I -S scripts/stage_csharp_state_guard.py \
  --project-root "$PWD" \
  --facts reports/csharp-semantic/facts.json \
  --targets reports/extract-enum/csharp/job-status/targets.json \
  --accepted-migration reports/extract-enum/csharp/job-status/accepted-migration.json \
  --output-dir reports/prevent-regression/csharp/job-status
```

The output stages `ExactAcceptedStateGuard.cs`; it never installs the file. The
proof reruns direct-csc native compile/test/smoke for the accepted migrated tree,
compiles the guard there, applies the accepted String reversion only in a
disposable copy, proves that copy still passes without the guard, and proves the
guard rejects it. The host source inventory must remain byte-identical.
