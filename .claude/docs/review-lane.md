# Adversarial review lane

> This file is optional. When absent, `/mature-existing-ideas
> --adversarial` uses the `general-purpose` sub-agent (universally
> available across Claude Code / Codex / Augment). Copy this file
> into your host project and replace the sub-agent type if you have a
> project-specific reviewer.

Optional host config for `/mature-existing-ideas --adversarial`. When
present, the override below names a project-specific adversarial
reviewer.

Trigger: read this when authoring or calibrating the
`/mature-existing-ideas --adversarial` gate, or when the host project
maintains a custom review agent that should run as the second-look
lane.

## Why this exists

The adversarial gate in `/mature-existing-ideas` is a second-look pass
that runs *between* Stage 1 (orchestrator research) and Stage 2
(ledger writes). The default `general-purpose` sub-agent is universal
but offers no model or corpus diversity — its independence comes from
not seeing the orchestrator's chain-of-thought plus a deterministic
enrichment payload. A host project may choose a different sub-agent
type (e.g. a Codex-driven reviewer) when calibration evidence shows
the default is too weak.

## Sub-agent type

The first non-empty, non-comment line under this heading is taken as
the sub-agent type name. Anything else is documentation.

<!-- Uncomment the override that matches your host project's reviewer
     (or leave the section empty to use `general-purpose`): -->

<!--
general-purpose
codex-rescue
code-reviewer
-->

## Notes

- Cross-model adversarial review (e.g. a Codex reviewer against a
  Claude orchestrator) is the true independence lane and lives in the
  host project's two-lane review block in `CLAUDE.md` / `AGENTS.md`.
  The `/mature-existing-ideas --adversarial` gate is the lightweight
  calibration step before the ledger write — not a replacement for
  the two-lane review.
- The override here applies only to `/mature-existing-ideas`. Other
  skills that introduce their own gates should declare their own
  single-topic config file under `.claude/docs/`.
