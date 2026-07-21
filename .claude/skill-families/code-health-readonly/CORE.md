# Read-only code-health family

Use this bounded family only for a broad TypeScript or checked-JavaScript
health audit. It combines three independent evidence lenses; it is not a
general review, a framework audit, or permission to edit source.

## Execution contract

- The project root, source target, language, and on-demand library root are
  explicit. `find-standard-gaps` also requires a host-owned standards JSON.
- Run only members whose dependencies are available. Report every skipped
  member and reason. A skipped, failed, `partial`, `language_unsupported`, or
  `no_files_matched` lane is incomplete evidence, never a clean result.
- The launcher may run at most three members concurrently because all members
  are read-only. Any source mutation is a family failure. Never parallelize a
  mutation or infer permission to fix a finding.
- Treat generated, vendored, test, fixture, build-output, minified, declaration,
  and symlink exclusions exactly as the member contract states. Unsupported
  syntax or missing native tooling stays visible.
- Judge each member from its final artifact and captured exit status, not from
  reassuring stdout. Do not reuse a prior report when this run fails.

## Synthesis contract

Return one `family-result.json` plus `summary.md`. Preserve each member's
semantic projection and completeness state. Deduplicate only findings with the
same kind, path, line/symbol, and evidence; never merge merely similar claims.
Order actionable findings by lane order, then path and location. Name clean
lanes separately from incomplete lanes. The synthesis can recommend a next
investigation but cannot claim runtime impact, framework behavior, or a fix.

The family launcher owns deterministic execution and synthesis. A fresh
non-context sub-agent may read this core plus only the concise member guides,
run the launcher, inspect the final artifacts, and report the result to the
root agent. Individual full skills remain directly invocable for narrower work.
