# Inventory: ~/Projects/host-a/.engineering/

Timestamp: 2026-06-12

## docs

Host-authored descriptors for the cross-agent skill toolkit's subsystem detection, workflow mapping, and hygiene instrumentation.

| file | what it is | kind | second-look? |
|---|---|---|---|
| product-workflows.md | Grammar + route/step mapping for per-Site setup pipeline (setup → extraction → pages → images → PartShare → PTID → export) rooted at `/sites/{site_id}/...`. Route names use `site_*` prefix per ADR 0012; templates under `templates/core/` app-label namespace, not retired `core/` Python package. `SiteWorkflowRegistry` is source of truth. | design | N |
| todo-tuning.md | Config for `/find-orphaned-ideas --todo` with path-skip globs (.claude/worktrees/\*\*, static/admin/js/vendor/\*\*, \*\*/migrations/\*\*) and min_words=4 threshold. | config | N |
| find-layer-violation-scope.md | Path roots declaring **view** (app/views, app/pages, app/api) and **task** (app/tasks) layers for `/find-layer-violation`, implementing ADR-0011 post-refactor split. | design | N |
| find-route-sprawl-scope.md | (read header only; substantial file not sampled) | design | N |
| ignore.md | (read header only; substantial file not sampled) | tool | N |

## experiments

Skill-conform measurement harness: deterministic grading of /prevent-regression guard proposals by side-effect (artifacts on disk + skill verifiers), not by claimed output.

| file | what it is | kind | second-look? |
|---|---|---|---|
| STAGE1.md | Measurement-instrument design + build-and-validate protocol for conformance harness. Builds no-model-in-loop scorer; four stdlib pieces: seed_fixture.py (throwaway mini-host-a repo with guard infrastructure + target anti-patterns + correct forms), install_proposal.py, score_conformance.py, validate.py. Seeded repo mirrors: bare `int(request.POST.get(...))` / `int(request.GET.get(...))` without `safe_int` in two view files; `safe_int` helper + correct call sites; guard plumbing (scripts/lint/, .pre-commit-config.yaml, .github/workflows/ci.yml); empty tests/lint/. Antitheatre principle: **grade only by artifacts + skill rerun verifiers, never by run claims.** | method | Y |
| STAGE2.md | (not read) | method | ? |
| validate.py | End-to-end validation: per proposal under fixtures/, seed fresh repo → install → score → assert verdict (conformant=all-pass; defective=fail-on-specific-check). Stdlib-only, self-cleaning. | method | Y |
| score_conformance.py | (not read) | method | ? |
| install_proposal.py | (not read) | method | ? |
| seed_fixture.py | (not read) | method | ? |
| fixtures/{conformant,defective,poisoned-good,over-broad,wrong-name}/ | Five test cases spanning verdict space: conformant (pass), defective (fail C4 matcher drift), poisoned-good (pass despite poisoned fixture), over-broad (fail too-broad rule), wrong-name (fail naming). Each has proposal.md, pattern.md, conformance.json, proposal_manifest.json, plus scripts/lint/ and tests/lint/ subdirs. | data | Y |
| runs/stage1b-sonnet/ | Output of one E2E run (proposal artifacts + lint rule + test fixtures for that run). | run-history | N |

## local

Working state, per-run output, reference code, scratch intake, project-health state cache.

| dir | what it is |
|---|---|
| intake/ | Proposed ideas / findings awaiting triage |
| project-health/ | State snapshot (34 cached results) from last `scripts/project_health.py --refresh --include-slow` run |
| reference/ | (not explored) |
| reference-code/ | oreillyauto/ (695KB+ reference implementations from external projects), pronto/ (pytest.ini, requirements.txt) |
| reports/ | Raw per-scan output (gitignored unless promoted to `.engineering/reports/`) |
| review-assets/ | (not explored) |

## project-health

Committed rollup: project-health drift queue (unfinished structural work visible as one queue).

| file | what it is | kind | second-look? |
|---|---|---|---|
| README.md | Run `.venv/bin/python scripts/project_health.py --refresh --include-slow`. Outputs: plan.json (critical path, parallel lanes, closure criteria), current.json (findings conforming to schema.json), current.md (health bar), execution-queue.json (grouped next-action queue), root-layout.json (root-level layout contract). Finding states: open, fixed, deferred_with_trigger, false_positive, guarded. Split tracked evidence (`.engineering/reports/`) from raw/bulky output (`.engineering/local/`). | design | N |
| current.md | Human-readable health bar (snapshot). | run-history | N |
| current.json | Normalized findings conforming to schema.json (snapshot). | data | N |
| plan.json | Critical path + parallel lanes + completion criteria (snapshot). | data | N |
| execution-queue.json | Grouped next-action queue (snapshot). | data | N |
| schema.json | Finding shape validator. | design | N |
| root-layout.json | Root-level layout contract for detecting unclassified/misplaced entries (snapshot). | data | N |

## reports

Durable tracked evidence: accepted proposals, distilled queues, inventories cited by specs/ADRs, review findings, run-level telemetry.

| file | what it is | kind | second-look? |
|---|---|---|---|
| BACKLOG.md | Working index of open work grouped by intent (bugs, extraction quality, design decisions, tooling, performance, security, data, workflow, extraction, UI, docs). Conventions: one-liners with file paths inline for grep-ability; follow memory: links for substantial content; git history is the audit trail; items surface in round reports, merge actionable ones here. **Path drift note:** `core/` Python package retired (ADR 0011, 2026-05-08); code now under `app/`. Django app-label, URL namespace, Celery task names, FK strings remain `core` deliberately. File paths/line numbers predate restructure; grep by filename/symbol if 404s. | run-history | N |
| _meta/README.md | Skill effectiveness log: `.engineering/reports/` holds durable evidence; raw output belongs `.engineering/local/reports/` unless promoted. `effectiveness.jsonl` (append-only, one line per skill run: `{skill, scan_id, ts, findings_total, buckets, notes, target}`). `dashboard.md` (aggregated view; regenerate after appending). Working backlog at `BACKLOG.md`. | design | N |
| _meta/effectiveness.jsonl | Append-only skill-run telemetry ledger (cross-time signal for maintenance-skill quality). | data | N |
| _meta/dashboard.md | Aggregated view from effectiveness.jsonl (regenerated per new runs). | run-history | N |
| _meta/triage-audit-latest.md | (not read) | run-history | N |
| frontend-helpers/inventory.json | (not read) | data | N |
| harness-design-framework/*.md | Review findings on harness design (two reviews). | review | N |
| refactor/core-models/\*-inventory.md, \*-solid-audit.md, \*-split-plan.md | Phase 1 inventory, SOLID audit, phase 3 split plan for core models refactor. | design | N |
| refactor/core-models/inventory/\*-chunks.{md,json} | Chunked inventory of core models. | data | N |
| omnibus/scan-20260611-*/omnibus.jsonl, report.md, findings.json, candidates.jsonl | Most-recent omnibus scan (2026-06-11 08:49:52): raw candidates, findings shape, human-readable report. | run-history | N |
| layer-violation/scan-20260611-*/report.md, findings.json, candidates.jsonl | Most-recent layer-violation scan (2026-06-11 08:50:11). | run-history | N |

## research

Investigation into emerging concerns: product-data enrichment, PIES 8.0 upgrade, brand-hierarchy data modeling, AI-coding-agent quality, AI failure modes, role-agents as long-lived QA capability.

| file | what it is | kind | second-look? |
|---|---|---|---|
| pies8_field_analysis.md | PIES 7.2 → 8.0 upgrade research. Analyzes official schema, sample, production export, requirements docs, current app models, export services. Complete element inventory (header segment, item segment, pricing, supply, fit data, media, etc.) showing **what is captured vs required/optional in PIES 8.0.** Hardcoded "7.2" in export service needs update; many header/item fields missing from PiesProductData. Maps current extraction to PIES 8.0 required/optional/conditional. **Reusable upgrade spec candidate.** | research | Y |
| data_enrichment_sources.md | How to fill missing PIES fields (GTIN, sub_brand_id, container_type, hazmat). Catalogs industry approaches: PIM + manual enrichment (Epicor, JNPSoft PartCat, PDM Automotive, APA Engineering), API integrations (Epicor PartExpert, AutoCare data subscriptions), 3PL lookups (GS1 GTIN database, HAZMAT registries). Model gaps: gtin, sub_brand_id, container_type, product_category_code, aces_applications, package dimensions/weight/hazmat. **Reusable source map for data-enrichment roadmap.** | research | Y |
| ai-code-failure-modes.md | ChatGPT Deep Research (2026-05-01): AI + junior code fail in same places (boundaries, ambiguity, context > local function). Evidence: Sonar 2026 (96% distrust AI; 48% skip checks; 38% review cost higher), DORA (higher AI adoption = lower throughput/stability), 2026 wild-repo study (484k distinct AI issues; 22.7% survive to latest revision). Root causes: context failure (undefined vars, insecure defaults, hallucinated packages), overconfidence (40% vulnerable security code despite AI help), missing operational thinking (no timeouts/retries/cancellation/observability). **Senior counter-moves frame as control: validate at boundaries, type inside, bound all external work, require assertions + runtime telemetry, separate domain/transport/persistence.** Anti-pattern catalog + control table. | research | Y |
| ai-agent-quality-roadmap.md | ChatGPT Deep Research (2026-05-01): SWE-bench 76.8%, but SWE-EVO 21% on long-horizon tasks; CodeClash loses every round vs experts. Quality is **systems-engineering problem** (evals, sandbox, tests, static/security analysis, repo-aware retrieval, typed specs, planner/executor decomp, PR-native review). **Highest-ROI interventions ranked:** (1) continuous evals + internal golden tasks, (2) sandboxed test/build/repair loops, (3) static analysis + enforceable gates, (4) repo-aware retrieval + structure mapping, (5) spec-first + structured outputs, (6) planner/executor decomp. Fine-tuning/RLHF secondary unless stable evals + internal trajectory data exist. **Reusable quality framework for AI-assisted feature work.** | research | Y |
| brand_hierarchy_analysis.md | AAIA brand table structure (partshare.aaia_brands): 29.9k rows, 28.1k unique BrandIDs, 18.8k ParentIDs, 2.2k SubBrandIDs. Denormalized one-row-per-sub-brand. Self-parented brands (ParentID=BrandID): 715; OEM brands: 224. Revision date range 1997-12-31 → 2026-02-05. (First 40 lines; substantial data-modeling content below.) | research | Y |
| role-agents/README.md | Experimental research direction: long-lived agent roles to improve project health when implementation is AI-assisted. Working hypothesis: inspection/drafting/review cost drop unlocks addressable work, but only with clear jurisdiction, memory, handoff rules, stop conditions. **Separated from active skill system to avoid persona drift, memory rot, automation churn.** Subdirs: memory-index.md, operating-model.md, role-contract-template.md, handoff-template.md, takeover-charter-template.md, pilot-protocol.md, outcome-log.md, backlog.md. | design | Y |
| role-agents/operating-model.md | Role-agent capability contract (not persona): long-lived agents for addressable QA work. **AI-addressability gate:** bounded (name jurisdiction + stop condition), repeatable (recurs across tasks/PRs/projects), reviewable (judge without replaying session), verifiable (test/lint/checklist/witness). Role contract: role_id, jurisdiction, decision_rights, memory_sources, escalation_path, handoff_shape, stop_condition. **Reusable contract template for future role pilots.** | design | Y |
| role-agents/pilot-protocol.md | (not read) | design | ? |
| role-agents/outcome-log.md | (not read) | run-history | ? |
| role-agents/backlog.md | (not read) | design | ? |
| role-agents/simulation-2026-05-13.md | (not read) | run-history | ? |
| role-agents/review-notes.md | (not read) | review | ? |
| role-agents/handoff-template.md | (not read) | design | ? |
| role-agents/takeover-charter-template.md | (not read) | design | ? |
| role-agents/roles/\{role\}/identity.md, memory.md, review.md | (not read; subdirs for staff-principal-reviewer, security-risk-engineer, quality-engineer-reviewer, tooling-platform-steward) | design | ? |
| role-agents/tools/message_bus.py | (not read) | tool | ? |

## review-assets

UI screenshots for review and documentation (pages-page.png, brands-page.png, site-config variants, sites-modal variants, crawl_history.png, sites-search mobile/desktop before/after, rowmenu, sites-mobile-final, etc.).

| type | count | kind |
|---|---|---|
| PNG | 25 | review |

---

## Files flagged second-look: 9 of 9 read

Y-marked files are reusable methods, experiment protocols, worked-out unbuilt designs, or quality instruments:

1. **STAGE1.md** — skill-conform measurement harness protocol (deterministic grading by side-effect)
2. **validate.py** — E2E validation harness (stdlib-only, self-cleaning)
3. **fixtures/** — five test cases spanning verdict space
4. **pies8_field_analysis.md** — complete PIES 7.2→8.0 field mapping + inventory (upgrade spec candidate)
5. **data_enrichment_sources.md** — industry data-enrichment source catalog (enrichment roadmap reference)
6. **ai-code-failure-modes.md** — ChatGPT research: AI/junior failure patterns + senior counter-moves (quality framework)
7. **ai-agent-quality-roadmap.md** — ChatGPT research: ranked ROI interventions for AI-assisted quality (quality framework)
8. **README.md** (role-agents/) — role-agent governance + AI-addressability gate (capability-contract pattern)
9. **operating-model.md** (role-agents/) — role capability contract + jurisdiction framework (role-pilot template)
