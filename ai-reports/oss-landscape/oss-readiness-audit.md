# Open-Source Readiness Audit (historical)

This report is preserved as historical context for the framework's
portability work.

The original audit was performed on the source project (an internal
Django host) before the skill ecosystem was extracted into a
project-agnostic mirror. It enumerated the project-specific bindings
that needed to be cut: hardcoded paths, project-specific lint names,
project-specific workflow topology, host-project-only `_common/`
modules, and the absence of installer scaffolding.

The work the audit recommended has substantially landed in this
mirror:

- The skill ecosystem now lives in a standalone repository.
- `_common/skill-conventions.md` is project-agnostic.
- `_common/portability-roadmap.md` documents the eventual
  `_lib/{core,language,framework,repo}/` reorganization.
- Project-specific brand names, model names, and workflow steps have
  been generalized to placeholders.
- `_common/product_topology.py` keeps its Django-flavored scanner
  shape but uses generic workflow step names; host projects override
  via configuration.
- The diff-scoped lint catalogue documents canonical names
  (`silent-catch`, `stringly-status`, `query-mutation`, `fat-view`,
  `safe-dispatch`, `comment-drift`, `codegen-emits-new-paths`) that
  host projects extend rather than replace.

Outstanding work (deferred to future PRs):

- An `init` / installer that drops the skills, ADR/plan/spec
  registries, and a starter ADR into a new repo.
- A path-config file (`.claude/skills.toml` or similar) so users can
  relocate `ai-docs/`, `reports/`, and `decisions_dir`.
- A `topology.yaml` or equivalent so `_common/product_topology.py`
  can read its workflow steps from configuration rather than the
  hardcoded `SITE_WORKFLOW_STEPS` tuple.
- A README, LICENSE, CONTRIBUTING, CI templates, and a worked example
  showing a decide -> scope -> plan -> spec flow end to end.

The single biggest adoption risk identified in the original audit
remains true: the framework's value is the **discipline of framing
before solving** (problem-class, canonical practices, decision
registry, scout fan-out), not the individual skills. Users who install
the package and run a single skill in isolation will not feel the
benefit. The MVP slice (decide / plan / spec / triage) is the cut
that demonstrates the process value before introducing host-specific
detectors.

See `_common/portability-roadmap.md` for the staged path and
`development-workflow.md` / `senior-engineer-posture.md` for the
process discipline this ecosystem is built around.
</content>
</invoke>
