# Skill effectiveness dashboard

_Aggregated from `reports/_meta/effectiveness.jsonl` — 5 run(s)._

## Runs by skill

| Skill | Runs | Total findings |
|---|---:|---:|
| find-comment-drift | 1 | 83 |
| find-folder-topology-drift | 1 | 3 |
| find-omnibus | 1 | 6 |
| find-rule-surface-drift | 1 | 14 |
| find-stale-artifacts | 1 | 0 |

## Trend by month

| Month | find-comment-drift | find-folder-topology-drift | find-omnibus | find-rule-surface-drift | find-stale-artifacts |
|---|---:|---:|---:|---:|---:|
| 2026-05 | 1 | 1 | 1 | 1 | 1 |

## Most-scanned targets

| Target | Runs |
|---|---:|
| `.claude (+ONBOARDING.md)` | 1 |
| `.claude/skills + scripts/` | 1 |
| `scripts/ + .claude/skills` | 1 |
| `scripts/ + .claude/skills/*/scripts/` | 1 |
| `ai-docs/ + reports/` | 1 |

## Five most recent runs

- **2026-05-16T02:08:46Z** `find-rule-surface-drift` scan `scan-20260516-015741` — target `.claude (+ONBOARDING.md)`, 14 findings, buckets: {'dormant_in_onboarding': 11, 'missing_doc': 1, 'unreferenced_doc': 2}. Dogfood self-scan: 11 dormant_in_onboarding info-level, 2 unreferenced_doc actionable, 1 missing_doc false positive (repo-root-relative CLAUDE.md table row not resolved).
- **2026-05-16T02:08:46Z** `find-folder-topology-drift` scan `scan-20260516-015858` — target `.claude/skills + scripts/`, 3 findings, buckets: {'flat_prefix_cluster': 2, 'sparse_folder_package': 1}. Dogfood self-scan: 3 findings on substrate dirs; did NOT fire on the flat .claude/skills/ tree (planned exemption moot — detector never triggers there).
- **2026-05-16T02:08:46Z** `find-omnibus` scan `scan-20260516-020044` — target `scripts/ + .claude/skills`, 6 findings, buckets: {'borderline': 1, 'confirmed_omnibus': 0, 'coordination_omnibus': 1, 'facets_not_domains': 4, 'unverified': 0}. Dogfood self-scan: specs.py = coordination_omnibus -> EXPLAIN proposal (no blind refactor); 4 facets_not_domains false positives; 1 borderline (find-frontend-contract-drift detect.py).
- **2026-05-16T02:08:46Z** `find-comment-drift` scan `scan-20260516-020251` — target `scripts/ + .claude/skills/*/scripts/`, 83 findings, buckets: {'detached_section_banner': 56, 'malformed_doc_reference': 1, 'missing_public_class_docstring': 11, 'obvious_narration_comment': 14, 'stale_comment_term': 1}. Dogfood self-scan: 56 detached_section_banner + 14 obvious_narration + 11 missing-docstring (advisory style); 2 false positives (malformed_doc_reference, stale_comment_term) — host-tuned stale-term list.
- **2026-05-16T02:08:46Z** `find-stale-artifacts` scan `scan-20260516-020146` — target `ai-docs/ + reports/`, 0 findings. Dogfood self-scan: clean — no stale plans/specs or stale scan directories.
