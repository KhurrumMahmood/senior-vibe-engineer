---
type: "always_apply"
---

# Testing Enforcement

- Use `.venv/bin/python` for Django and pytest commands.
- After sidecar, AI runtime, benchmark, or agent-policy changes, run focused
  tests or clearly state what was not run and why.
- For extraction, discovery, export, or AI data-pipeline changes, candidate or
  harness tests alone are insufficient; include an end-to-end output-boundary
  proof where feasible.
- Friction summaries are available with
  `python3 scripts/agent_policy/friction.py summarize --since 14d`.
- Local friction logs live under `logs/agent_policy/` and are ignored; do not
  commit raw friction logs.
