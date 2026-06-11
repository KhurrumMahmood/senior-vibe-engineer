# OSS Landscape Comparison

_Generated: 2026-05-01. Sub-agent transcript: `a0587a6cd923f9387.output`._

---

I have plenty of evidence. Here's the comparative landscape.

---

# Comparative Landscape: Senior-Engineer Skill Ecosystem

## 1. Direct Competitors / Overlapping Projects

The Claude Code skill ecosystem exploded in late 2025 / 2026. December 2025 saw Anthropic open the SKILL.md spec, and OpenAI / Cursor / GitHub Copilot adopted it — so a single skill bundle can target many agents. Marketplaces (claudemarketplaces.com, skillsmp.com, lobehub.com/skills) now list 4,200+ skills.

Closest-shape competitors:

- **obra/superpowers** (175k stars, updated daily). The dominant "agentic methodology" plugin — 14 skills covering TDD / debugging / brainstorming / writing-plans / executing-plans / parallel agents / code review / git worktrees / `writing-skills`. **No** ADR, debt-scanning, omnibus detection, semantic-duplication, workflow registry, or canonical-pattern lints. It is a discipline framework, not a maintenance / governance one.
- **buildermethods/agent-os** (4.4k stars, v3 active). Closest *philosophy* match: "inject codebase standards into spec-driven dev." v3 added `/discover-standards` (extracts patterns from your code) and `/inject-standards` (bakes them into subagents/skills). Lacks ADR lifecycle, tech-debt scanners, or shadow-then-promote enforcement.
- **bmad-code-org/BMAD-METHOD** (46k stars). Multi-agent agile framework: Analysis → Planning → Solutioning → Implementation, with personas. Spec-driven and human-in-the-loop, but no decision registry, no debt loop, no skill-routing meta-skill.
- **Pimzino/claude-code-spec-workflow** (3.7k stars). Pure spec workflow — Requirements → Design → Tasks → Implementation. Narrower than your surface.
- **shinpr/claude-code-workflows**, **CloudAI-X/claude-workflow-v2** — generic multi-agent workflow plugins.
- **Project Constitution skill** (mcpmarket) — closest to `audit-decisions` shape: discovers rules from codebase, classifies L1/L2/L3, ties to evidence. No spec-first refactor lifecycle around it.
- **ksimback/tech-debt-skill** — single skill, file-cited debt audit. Much narrower than your `triage-debt` + 8 SUSPECT skills + topology smells.
- **finereli/refactoring** plugin, **citypaul/.dotfiles refactoring skill**, **l-mb/python-refactoring-skills** — single-skill refactor disciplines.

**Official Anthropic skills** (anthropics/skills): 17 skills — `algorithmic-art`, `brand-guidelines`, `canvas-design`, `claude-api`, `doc-coauthoring`, `docx`, `frontend-design`, `internal-comms`, `mcp-builder`, `pdf`, `pptx`, `skill-creator`, `slack-gif-creator`, `theme-factory`, `web-artifacts-builder`, `webapp-testing`, `xlsx`. **None target architectural governance.** Anthropic is explicitly leaving senior-engineer methodology to the community (which is why Superpowers/Agent OS are sponsored adjacent).

Nothing in any awesome list (`hesreallyhim/awesome-claude-code` 42k stars, `ComposioHQ/awesome-claude-skills`, `VoltAgent/awesome-agent-skills`, `alirezarezvani/claude-skills`) bundles ADR + spec + plan + refactor + topology smells under one roof.

## 2. Adjacent Tools (Different Shape, Same Goal)

- **ADR**: `npryce/adr-tools` (5.4k stars, bash CLI), `thomvaill/log4brains` (1.5k stars, gives you a static-site renderer for ADRs), MADR template, ADR Manager. Single-purpose — they manage ADR files, none of them link decisions to code references, smells, or specs.
- **Spec-driven**: GitHub Spec-Kit (MIT), Amazon Kiro IDE (EARS-format three-doc specs), Tessl (living-spec). All structure-the-spec; none bind it to a debt-loop or pattern lints.
- **Tech-debt scanners**: SonarQube (static rules), CodeScene (behavioral / hotspot analysis, "6x more accurate", now ships ACE refactor agent), CodeClimate, CodeAnt. Industrial-grade but built for human-driven cleanup; not designed as agent-callable skills.
- **Docs-as-code**: Backstage TechDocs (Spotify, plugin family pattern, two build modes); Diátaxis. Aimed at human discoverability; no agent metadata contract.

The closest *integrated* match in the ecosystem is **Agent OS** (standards extraction + spec injection) plus **Project Constitution** (rule discovery and severity tiering), but you would still have to bolt on ADRs, semantic-duplication detection, omnibus-module detection, workflow-registry extraction, and lint enforcement to reach the same surface area.

## 3. Where This Surface Is Differentiated

- **Integrated maintenance loop** (MAP → SUSPECT → EXPLAIN → REFACTOR → GUARD) with concrete skills at each phase. No competitor ties find-* detection, ADR backrefs, spec scaffolding, refactor execution, and lint promotion under one mental model.
- **Decision + spec + plan + refactor as one lifecycle**. Tiered (Quick / Feature / System) with status transitions (`proposed` → `scoped` → `impacted` → `architected` → `promoted`). ADR tools + spec tools elsewhere are siloed.
- **AI-agent-first frontmatter contracts**. `which-skill` reading `tier / job / best_for / not_for / language / framework` to defend against misapplication is a unique anti-pattern guardrail. No marketplace skill we found uses `not_for` as a routing signal.
- **Shadow-then-promote enforcement** (`prevent-regression` + diff-scoped lints). Competitors either teach via prompt only, or rely on existing CI tools — none promote captured findings into AST/ruff guardrails as a skill output.
- **Topology smells + workflow registry** (`find-route-sprawl`, `find-doc-route-drift`, `extract-workflow-registry`, `find-workflow-duplication`, `find-frontend-contract-drift`). Genuinely novel; nothing in the ecosystem treats product-workflow scattering as a first-class smell.
- **Tooling depth**: ~1500 LOC of supporting Python (`scripts/specs.py`, `decisions.py`, `plans.py`, `skill_meta.py`) is unusual; most marketplace skills are SKILL.md + maybe one helper script.

## 4. Where Existing Tools Are Stronger

- **No static-site renderer for decisions** — log4brains has searchable interactive ADR sites with status / author / date filters and decision graphs.
- **No marketplace presence** — Superpowers (175k stars) and BMAD (46k) have the discoverability flywheel; this surface is project-private.
- **No behavioral / hotspot analysis** — CodeScene's commit-coupling analysis catches drift this surface can't.
- **No multi-language coverage** — current skills are Python/Django-aware (AST lints, Django models). Agent OS, Superpowers, and Spec-Kit are language-agnostic by design.
- **No org-tier sharing** — Cursor Teams, Backstage TechDocs, Codacy Guardrails ship enterprise admin / privacy / shared-rule features.
- **No deterministic hook layer** — Anthropic's recommended pattern for non-negotiable rules is hooks, not skills. This surface relies on Claude's compliance with documented rules + diff-scoped lints; it isn't a pre-commit + CI hook bundle.

## 5. Adoption Signals

Strong demand:
- "Skills ecosystem grew from empty to flooded in six months." Marketplaces list 4,200+ skills. Claude Code hit #1 on HN with a `.claude/` deep-dive (556 points).
- Superpowers' rocket trajectory (175k stars in months) is the most direct demand signal: **disciplined methodology** is the most-installed category. Buyers self-describe "Claude got 100x better with discipline."
- Agent OS v3 (Apr 2026) explicitly pivoted to "extract patterns from your codebase" — same instinct as `audit-decisions` and `teach-pattern`.
- 2026 industry framing has moved from speed to governance; "multi-agent validation chains" and "guardrails before capability shopping" are the dominant op-eds (the-main-thread, tfir.io, IBM, Coder.com).

What's missing in public discourse: no one talks about ADR + spec + smell-detection + lint-promotion as one surface. The gap is real; this surface is a category of one in scope, but a category of many in *individual* primitives.

---

**Bottom line.** The closest competitor is Agent OS (~4.4k stars) for "extract standards from your code"; the dominant Claude Code methodology plugin is Superpowers (~175k stars) but it has zero overlap with the maintenance / governance half of this surface. Differentiation lies in (a) the integrated decision-spec-plan-refactor lifecycle with explicit status transitions, (b) topology smells (workflow registry, route sprawl, frontend contract drift) that nobody else names, and (c) `which-skill` + `not_for` frontmatter as anti-misapplication routing. Weakness vs. mature tools: no rendered ADR site, no marketplace presence, no behavioral hotspot analysis, no hook-based deterministic enforcement.

Sources:
- [Anthropic skills repo](https://github.com/anthropics/skills)
- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Equipping agents with Agent Skills (Anthropic engineering)](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [obra/superpowers](https://github.com/obra/superpowers)
- [buildermethods/agent-os](https://github.com/buildermethods/agent-os)
- [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)
- [Pimzino/claude-code-spec-workflow](https://github.com/Pimzino/claude-code-spec-workflow)
- [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)
- [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills)
- [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills)
- [thomvaill/log4brains](https://github.com/thomvaill/log4brains)
- [npryce/adr-tools](https://github.com/npryce/adr-tools)
- [ADR tooling index](https://adr.github.io/adr-tooling/)
- [Project Constitution skill](https://mcpmarket.com/tools/skills/project-constitution)
- [ksimback/tech-debt-skill](https://github.com/ksimback/tech-debt-skill)
- [Martin Fowler — Spec-Driven Development tools](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [Kiro by Amazon](https://kiro.dev/)
- [GitHub Spec-Kit guide (IntuitionLabs)](https://intuitionlabs.ai/articles/spec-driven-development-spec-kit)
- [Backstage TechDocs](https://backstage.io/docs/features/techdocs/)
- [CodeScene](https://codescene.com/)
- [Claude Code & the Productivity Panic of 2026 (HN)](https://news.ycombinator.com/item?id=47467922)
- [AI Coding Tools 2026 — working with agents without losing control](https://www.the-main-thread.com/p/ai-coding-tools-2026-java-developers-agents-control)
- [AI Code Quality 2026 — Guardrails for AI-Generated Code](https://tfir.io/ai-code-quality-2026-guardrails/)
- [Superpowers — Builder.io review](https://www.builder.io/blog/claude-code-superpowers-plugin)
- [Top 10 Claude Code skills (Composio)](https://composio.dev/content/top-claude-skills)
- [Skills marketplace (claudemarketplaces.com)](https://claudemarketplaces.com/)
