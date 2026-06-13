# Stage 7 — Dogfood substitution record

Date: 2026-06-12. No foreign host repo was available to this run, so
per the protocol the real-host dogfood was **substituted with live
probes of every script the repaired skill text tells an executor to
run** (substitution declared in intake.md). Never simulated.

| Probe | Command | Result |
|---|---|---|
| Documented effectiveness invocation (SKILL.md Step 5) | `python3 scripts/log_effectiveness.py --skill fix-workflow --scan-id "cluster-probe" --target core/services/parsing.py --findings-total 1 --buckets '{"dedup": 1}' --notes "stage-7 live probe" --log /tmp/probe-effectiveness.jsonl` | exit 0; appended sorted-key JSON line with all documented fields |
| Buckets validation failure path | same with `--buckets 'not-json'` | exit 1; `error: --buckets must be a JSON dict: ...` — matches scout §3 contract |
| jscpd re-scan command (new `knowledge/verification.md`) | `.venv/bin/python scripts/lint/run_jscpd.py --help` | accepts exactly the documented surface: positional `targets`, `--output`, `--offline-ok` |

Probe log written to a temp path (`--log /tmp/...`) so no fake
telemetry entered `reports/_meta/effectiveness.jsonl`.

Verdict: every executable command the repaired text mandates runs
against its real contract. The host-bound commands in §2c remain
unrunnable here by design — they now carry explicit absence
fallbacks (C4) rather than a runnable claim.
