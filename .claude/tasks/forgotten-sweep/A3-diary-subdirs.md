# Diary subdirectory inventory — host-a/.claude/tasks/

Scanned: 2026-06-12. 6 subdirectories.

---

## consolidation-batch-2026-05-19

**Purpose:** Sub-agent parallel dispatch for maintainability consolidation candidates "parallel sub-agent dispatch addressing the consolidation candidates."

**Files:** 10 (README.md + salvaged-plans/ containing 9 artifacts)

**Content & findings:**
- Harness for coordinating multi-agent worktree work on fixable structural candidates from maintainability experiments (Exp 01, 10).
- Round 1 failed due to worktree `baseRef` inheritance bug; documented root cause.
- Salvaged plans + characterization tests from 5 agents into `salvaged-plans/` subfolder (consolidation-fieldspec-plan, jobstatuspayload-plan, proxy-headers-plan, ptid-shapes, tokenusage-pagecount, plus critique + test files).
- Key lesson captured: sub-agent dispatch requires `worktree.baseRef: head`, absolute venv paths, evidence-file reachability.

**second-look: Y** — Documents repeatable dispatch harness pattern for parallel agent work on consolidation. Salvaged plans are draft-stage work-items, but the coordinate/salvage/retry protocol could be reusable.

---

## discovery-rca

**Purpose:** Root-cause investigation of four extraction quality bugs in live discovery path "read-only root-cause investigation across the live discovery path."

**Files:** 3 (extraction.md, multi-sku.md, url-discovery.md)

**Content & findings:**
- Deep trace of `_run_discovery_auto_match()` through sidecar boundaries (field extraction adapter → site intelligence pipeline).
- **Central finding:** judges in `extraction_judges.py` (collision sanity check, value self-check, plausibility) exist but are **not wired into live discovery path**; chat repair tool uses them exclusively.
- **Secondary finding:** `FIELD_VALUE_CONSTRAINTS` declared but not enforced; conditional PPC stripping is generation-time gated, not value-time gated.
- Concrete audit of E1–E4 quality defects (Permatex cases) pointing to specific missing validators.

**second-look: Y** — RCA is concrete and actionable; names the architectural gap (offline judges vs live validator boundary) and locates specific unwired code. Could inform an extraction-validator consolidation effort.

---

## doclinkrot-worklists

**Purpose:** Distributed doc link-rot repair coordination "doc link-rot repair protocol (shared by all repair agents)."

**Files:** 31 (shared INSTRUCTIONS.md + 10 worklist JSONs + 10 RESULT-*.md repair outputs + 10 detector runs)

**Content & findings:**
- Shared protocol for 10 parallel repair agents. Each repairs broken internal doc references.
- INSTRUCTIONS.md: verification-first protocol (ls → find → git log follow → grep for distinctive symbol), never guess paths, re-run detector post-fix (target 0 findings), report residuals.
- Result files show repairs across architecture.md, impmap-config, known-issues-fieldex, smells, spine pipelines, etc.
- Detector outputs (*.jsonl) track line + ref + text for broken links.

**second-look: N** — Routine run history. The protocol itself (verification-first, never guess, re-verify) is solid but already encoded in INSTRUCTIONS.md. Results are consumed.

---

## integration-gaps-audit

**Purpose:** Audit of Site Intelligence sidecar vs legacy discovery workflow coupling "end-to-end map of the live discovery workflow today."

**Files:** 6 (current-discovery-trace.md, discovery-extraction.md, frontend.md, integration-lift-profiles.md, site-intelligence.md, tasks-dispatch.md)

**Content & findings:**
- **current-discovery-trace.md:** 12-entry table of live discovery entry points (automatic mode, re-run, PartShare, custom analysis, field training, field discovery, auto-match-wws, auto-match-flatteneddata, manage.py refresh, workflow CLI, field-mapping generation, PTID classify), classified as 🟢 legacy / 🟦 sidecar / ⚠️ ignored / ❌ bypassed.
- **integration-lift-profiles.md:** Cost-benefit profiles for 8 sidecar workflows (image-extraction, classification, etc.) that exist but are not integrated into live discovery.
- **site-intelligence.md, discovery-extraction.md, tasks-dispatch.md:** Detailed coverage of specific workflows + call-site anatomy.
- Key insight: multiple adapters exist but are fire-and-forget or bypassed (apply boundary writes ignored, sidecar payload discarded).

**second-look: Y** — This is a thorough integration audit suitable as a reference map for future sidecar unification work. The classification scheme (🟢/🟦/⚠️/❌) and lift-profile template are reusable. Could inform a sidecar consolidation ADR.

---

## maintainability-experiments

**Purpose:** Five-track maintainability lean-cut investigation (scatter detector, churn map, orientation, fieldspec, codegraph analysis, contract inventory, dismissal ledger, synthesis) "track 3 of the lean-cut maintainability plan."

**Files:** 14 (01-scatter-detector through 11-lean-cut-retrospective, plus 2 JSON calibration/churn-data, 2 Python scripts)

**Content & findings:**
- **01–08:** Experiments in AST analysis, churn mapping, concept inventory, fieldspec consolidation, contract artifact discovery, dismissal-ledger prototype, self-maintenance analysis.
- **10-findings-and-dispositions.md:** Consolidation of all experiment findings (16 entries) into fix-now / log-later / monitor / done buckets, ordered by pain.
- **11-lean-cut-retrospective.md:** Ships Track 1 (dismissal ledger + scripts/dismissals.py CLI + .claude/quality/dismissals.jsonl), Track 2 (concepts.yaml + /find-concept-divergence skill), Track 3 synthesis + routing to engineering-skills-2 ledger.
- Key output: new dismissal ledger (AST-normalized, v2 at 90.91% semantic-vs-cosmetic correlation) + concept glossary + 16 dispositions routed to future intakes.

**second-look: Y** — Contains multiple reusable artifacts: (a) AST-fingerprinting dismissal ledger protocol (v2 normalization with calibration data), (b) concept-divergence scanner + concepts.yaml seeding template, (c) findings consolidation + disposition-routing framework. Dismissal ledger especially could be ported.

---

## phase-g-consolidations

**Purpose:** Cotton 2.6.2 extraction + JavaScript-string detection in HTML lint improvements "phase g — learnings log."

**Files:** 1 (learnings.md, 40+ lines)

**Content & findings:**
- **Item 1 — `<c-th-col/>` extraction (landed):**
  - Cotton does not auto-merge `class=` attributes; when primitive body declares `class="...fixed-chain..."` and call site passes `class="w-1/4"`, both attrs render and first one wins. Width variants silently disappear.
  - JS-string detection in HTML lints needs prefix-edge handling (anchor on what prefix *ends with*: `r"['\"`]\s*$"`) not substring search; false-positive rate on prefix-substring was ~18 JS-string callsites.
  - One-shot regex sweeps drift on multi-line splits (`<th\n class="...">\n Label\n </th>`); required v2 migration script.

**second-look: Y** — Three concrete lint guard patterns: (1) Cotton class-merge workaround (declare `class=""` as var), (2) JS-string edge detection for lints (prefix-end anchor), (3) multi-line pattern migration (TH_OPEN_LINE + CLASS_LINE). Each includes why it failed + how to apply, suitable for encoding in a lint or style guide.

---

## Summary

**Subdirectories:** 6
**Second-look: Y:** 5 (consolidation-batch, discovery-rca, integration-gaps-audit, maintainability-experiments, phase-g-consolidations)
**Second-look: N:** 1 (doclinkrot-worklists)

Reusable artifacts:
- Parallel agent dispatch harness + salvage protocol (consolidation-batch)
- Extraction RCA + unwired-judges audit (discovery-rca)
- Integration audit classification + lift-profile template (integration-gaps-audit)
- AST-fingerprinting dismissal ledger + concept-divergence scanner + findings-routing framework (maintainability-experiments)
- Cotton class-merge workaround + JS-string prefix-edge linting + multi-line regex migration (phase-g)
