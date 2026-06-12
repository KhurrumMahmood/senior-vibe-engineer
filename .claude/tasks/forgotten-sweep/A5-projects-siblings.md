# Projects Siblings Inventory — Read-Only Audit

12 sibling projects under `~/Projects/` identified and classified.

---

## engineering-skills-2

**What it is:** Clone/near-copy of main engineering-skills ecosystem — "A portable **senior-engineer skill ecosystem** for AI coding agents." Latest commit Jun 8.

**Relationship:** Clone/copy of engineering-skills. Main difference: engineering-skills-2 has 63 skills, more reports (20 vs 17 in es3), actively synced ~1 week ago. Second-look? **Y** — it has newer reports and may include refinements post-main branching. Check if es2 has improvements not yet in main.

---

## engineering-skills-3

**What it is:** Clone/near-copy of main engineering-skills ecosystem — same preamble, "A portable **senior-engineer skill ecosystem**." Latest commit May 22.

**Relationship:** Clone/copy of engineering-skills, older than es2 (last commit May 22 vs Jun 8). Fewer tests (19 vs 26), fewer reports (17 vs 20). Second-look? **Y** — check git history to understand divergence trajectory between es1, es2, es3; may reveal which branch is canonical or where features went.

---

## claude-skill-ecosystem

**What it is:** Design document-only repo, not git-initialized — "Skill Ecosystem — Productization Backlog." Single file `backlog.md` (12 KB). Records ecosystem productization conversations from host-a.

**Relationship:** External design document / idea ledger. Tracks "30+ skills covering map → suspect → explain → refactor → guard" intended "for the ecosystem itself, not any one project." Second-look? **Y** — may contain prior design decisions and blockers relevant to es1/es2/es3 direction; canonical vs experimental choices.

---

## content-extracted-learnings

**What it is:** "A **fiction-production skill ecosystem** extracted from research dumps... knowledge base → subsystem maps → contract-bearing skills → execution harnesses." Active as of Jun 12 (1 hour ago).

**Relationship:** Original project — parallel ecosystem modeled on engineering-skills architecture but for fiction craft (copyrighting, scene composition, character sheets, comics). Not a copy; distinct domain. Second-look? **Y** — demonstrates ecosystem portability to non-engineering domain; learnings about skill contracts and state separation may feed back.

---

## skills

**What it is:** Two subdirectories containing image-generation skill definitions: `banana-pro-director-2.0` and `cinema-worldbuilder-pro-2.0`. Each is a single SKILL.md file (~100 KB each) with locked prompt grammars for AI image tools.

**Relationship:** External third-party code / tool specs. Photorealistic image prompts for Higgsfield / Soul Cinema / Banana Pro and GPT-2 models. Not ecosystem-related. Second-look? **N** — isolated tool reference material.

---

## experiments

**What it is:** Research and evaluation specs in `claude-instructions/` subfolder. Main file: `philosophy-stabilizes-execution-spec.md` (30 KB). Tests whether system-prompt "Philosophy frame" stabilizes execution under strain in isolated sub-agents.

**Relationship:** Original research experiment — measures whether instruction design (philosophy notes) stabilizes Claude behavior under multi-agent orchestration. Not code. Second-look? **Y** — findings may inform how es1/es2/es3 prompt strategies should work; mediation hypothesis.

---

## mini

**What it is:** Two small CLI tools: `loom-dl` (download public Loom videos as MP4), `whisper` (likely speech recognition). Loom-dl has a git repo and tests.

**Relationship:** External third-party / personal utility code. Python scripts. Second-look? **N** — utilities not related to skill ecosystem.

---

## success-game

**What it is:** Conversation transcript (`initial-chat.md` and related) discussing design principles for AI agents and system prompts in the context of host-a project. Dated Mar 17.

**Relationship:** Data dump / design notes. Transcribed conversation exploring requirements systems, tool invocation patterns, and agent behavior for a larger system. Second-look? **Y** — captures early strategy for host-a that may inform what became engineering-skills; traces thinking about agent governance.

---

## gemini-summarizer

**What it is:** Next.js + Vercel AI SDK chatbot template. "An Open-Source AI Chatbot Template Built With Next.js and the AI SDK by Vercel." Supports Gemini, OpenAI, Anthropic, Cohere.

**Relationship:** External third-party code / template fork. Actively modified (commits up to Dec 2025). Node.js + TypeScript. Second-look? **N** — standard boilerplate, not unique to this project.

---

## x-algorithm-main

**What it is:** X (Twitter) For You Feed algorithm — "core recommendation system powering the 'For You' feed on X." Contains Grok-1-derived transformer, retrieval, ranking, home mixer, thunder, phoenix, candidate pipeline components.

**Relationship:** External third-party code — public release from xAI/X. Published May 15, 2026. No modifications. Second-look? **N** — read-only reference for recommendation ML.

---

## atlas

**What it is:** Screenshot dump + design research. ~70 PNG files (calculator UI variants, desktop/mobile mockups, netlify deployment snapshots) + HTML prototype + research docs. No meaningful code; mostly asset gallery and design notes.

**Relationship:** Data dump / design exploration. Web design research synthesis (Figma, Playcode, Awwwards, YouTube sources). Created May 25. Second-look? **N** — visual design reference, not structural code.

---

## server

**What it is:** AWS EC2 credentials and connection file. Two files: `.rdp` file and `Worker.pem` (private key).

**Relationship:** External secrets / credentials dump. Not a project. Second-look? **N** — infrastructure config, should probably be .gitignore'd or deleted.

---

## courses

**What it is:** Single PDF + README: "Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems by Antonio Gulli."

**Relationship:** External third-party content — educational material. Git-tracked PDF. Second-look? **N** — reference course material.

---

## Summary

- **Dirs audited:** 12
- **Second-look candidates:** 6
  - engineering-skills-2 (branch divergence tracking)
  - engineering-skills-3 (branch divergence tracking)
  - claude-skill-ecosystem (productization decisions & blockers)
  - content-extracted-learnings (cross-domain portability proof & lessons)
  - experiments (philosophy/execution hypothesis findings for prompt strategy)
  - success-game (early host-a agent design conversation trace)
