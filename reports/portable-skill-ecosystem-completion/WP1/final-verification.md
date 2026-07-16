# WP1 final verification

Verifier: `/root/wp1_concise_verifier`, Codex/GPT-5. Revision:
`8b8b09a4b5633d59eacc8b8058cd15beae662e6f`; implementation revision
`14eaa3a7c2b7101f8d50ab157335def520306c01`. Workspace was clean at
start. Required commands appended four automatic records only to
`logs/agent_policy/test_runs.jsonl`; the verifier preserved and hashed the
patch, and the coordinator removed it afterward. Platform: macOS 26.5.1 /
Darwin 25.5.0 / arm64.

Overall: **PASS — WP1 may advance from `implemented` to `verified`.**

| AC | Verdict | Independent basis |
|---|---|---|
| AC-1.1 | PASS | Versioned registry distinctly models runtime, subjects, frameworks, tools, roots, layers, bindings, scans, capabilities, support, and evidence; data-only future-language registration passed. |
| AC-1.2 | PASS | All seven required consumers use one registry. The guard rejected dictionary, nested/constructor, split/zip, comprehension, generator, computed-receiver, and `dict.fromkeys` attacks. |
| AC-1.3 | PASS | Invalid capability/layer/binding, fabricated/shared/unexecuted `any` evidence, unrelated/mismatched scans, support ceilings, and React/Vite confusion failed; distinct Python/TypeScript experimental evidence executed and passed. |
| AC-1.4 | PASS | States/transitions are mechanical; stale/false/timeout/hash/platform/tool attacks demoted. Claim-time `PATH` prepending after module import could not redefine discovery. The process-start trust boundary and WP8 caller-sanitation ownership do not contradict the AC. |
| AC-1.5 | PASS | Accepted ADRs 0038–0042 resolve D1–D5 with rejected alternatives, migration/compatibility, costs, and revisit triggers; audits passed. Spike commit `fe0f226` precedes D3 acceptance commit `f396c54`. |
| AC-1.6 | PASS | Matrix v1 defines 44 required cells across five stacks and five pinned surfaces. Missing, unsupported, labels, generic/reused evidence, old versions, structural-only mode, and claimant issuer overrides failed. `verified` remains blocked by the registry-owned WP8 issuer while it is unavailable. |
| AC-1.7 | PASS | Fresh pinned spike preserved the corpus and unsupported candidates; every supported family scored precision/recall 1.0 and met runtime/install budgets. |

## Commands and results

```text
.venv/bin/python -m pytest -q
446 passed, 1 skipped

.venv/bin/python -m pytest -q \
  tests/test_capability_registry_guard.py \
  tests/test_capability_registry.py \
  tests/test_capability_consumers.py
36 passed

exact retained attack replay
21 passed

.venv/bin/python scripts/skill_meta.py lint --quiet
OK — 76 skills, 76 declaring new contract

.venv/bin/python scripts/plans.py audit
OK — 5 plans, no drift

.venv/bin/python scripts/decisions.py audit
OK — 34 decisions, no drift

.venv/bin/python scripts/decisions.py link-check
OK — 34 decisions, all links resolve, 22 host-scoped

.venv/bin/python scripts/check_capability_registry_consumers.py
OK — 7 consumers use the canonical capability registry

.venv/bin/ruff check scripts tests
All checks passed!
```

D1 generated all five projections and the Codex plugin validator passed. D3
used the pinned `/tmp/engineering-skills-d3-spike-20260716` dependencies:

```text
corpus: da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f
tree-sitter: 0.062291 s / 5,089,280 bytes
ast-grep: 0.091878 s / 154,339,105 bytes
TypeScript API: 0.629429 s / 23,625,066 bytes
all supported precision/recall: 1.0; all budgets: PASS
```

Key hashes:

```text
87efcec9402cb5c17fcc41c305a035d2e3166cc5fea11ad0d2ea5cbf99372508  capability-registry.yml
f55506a5a800309f58e098c0906751db8378bee4ef026939293495f696be4d39  capability_registry.py
2b9a68efd10f5bb7b0c92675a775ab2f932840ca59c809751cab4d054785a503  support_evidence.py
de78e2757eb31a0c37296ee057fcb43095359988608d7c54eeaf41b58b906e08  consumer guard
4f60de8aeb65abefcc3f2195d711feee89294c72dfb0320259d2933e76c74d91  fresh D3 report
```

Limitations remain explicit: D3 executed on macOS arm64 with reused pinned
dependencies; other platforms remain unverified until the matrix runs them.
D1 is a projection prototype, not WP3's cold-host installer proof. The guard's
threat model covers ordinary and simple statically computed duplicate enums,
not deliberately obfuscated arbitrary Python. No blocker, missing evidence, or
unsupported WP1 claim remains.
