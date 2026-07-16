# WP3 Slice 3 evidence — foundation boundary

Generated at: `2026-07-16T18:51:45Z`
Working-tree revision: `a676ec9621282d5f32322364940650df8e9bd1ff`
Functional implementation revision: `ccc6a5dd1166809003d52eba2e11ed05c33deead`
Platform: `Darwin-25.5.0-arm64`
Python: `3.11.10`; pytest: `9.0.3`; Ruff: `0.6.9`
Lane: `/root/wp3_core_deflavor`
Agent/model visibility: Codex based on GPT-5. No more specific model variant
or reasoning-effort setting was exposed; the launcher exposed no model
selector.

## Implemented boundary

- IM-5: `scripts/lint/no_core_framework_leakage.py` reads framework terms from
  the canonical capability registry and checks every active prose/code field
  in each `foundation-ready` core `SKILL.md`, including frontmatter prose,
  links, URLs, and code fences. Case-insensitive matches use token boundaries.
  Structural selection/evidence fields are metadata, not prose.
- The lint rejects non-`any` framework metadata, undeclared or nested binding
  files, and normalized core procedure paragraphs copied into a binding.
  Staged and revision diff modes inspect both the old and new blob for a
  rename/copy; `--all` is the read-only registry-wide acceptance mode.
- The only exception surface is
  `_common/core-framework-leakage-allowlist.yml`. Its exact entry schema is
  `path`, `term`, `owner`, `reason`, and `expires_on`; unknown/missing fields,
  empty ownership/reason, expired dates, dates more than 90 days away,
  non-canonical terms, non-migrated targets, and verified-claim exceptions all
  fail closed. Inline compatibility prose and `noqa` comments are not waivers.
- IM-6: exactly the frozen 14-name AR-3 set was evaluated. The six already
  neutral bodies were unchanged. The eight contaminated bodies (`decide`,
  `design-it-twice`, `fix-workflow`, `organize-project-structure`,
  `prevent-regression`, `propose-folder-reorganization`,
  `refactor-subsystem`, and `which-skill`) now keep the universal procedure in
  core and place Django/Celery examples/defaults in their declared one-level
  `bindings/django.md` overlays. `fix-workflow` and `refactor-subsystem` now
  honestly declare `framework: any`, with the authoritative inventory updated
  to match.
- No tracked path moved. The WP3 move gate was therefore not invoked.
  `which-shape` and `engineer-init` were regression/routing surfaces only and
  were not edited. Their observed SHA-256 values are
  `1da37d77c8879425bc76a72a7ab0e37b978772c239c8caa7de3bdfdb768ab320`
  and `90bc4e47fc815b3dd7d785299e47b0abf2ed5e44e3ca4438fc55cfef0bc19e2b`.
- No binding loader, `extract-enum` split, distribution projection, installer,
  master-plan status, successor-spec checkmark, or ADR status/embodiment work
  was performed.

## Test-first and adversarial record

Before the lint module existed, the dedicated command

```text
.venv/bin/python -m pytest -q tests/test_core_framework_leakage.py
```

failed during collection with
`ModuleNotFoundError: No module named 'lint.no_core_framework_leakage'`.
After the first implementation, the repository-clean characterization test
failed with all 19 frozen Django/Celery occurrences, proving the fixture and
real-catalog boundary fired before the de-flavor edits.

The final dedicated tests cover neutral prose, declared binding content,
case variants, word boundaries, body prose, active frontmatter fields, fenced
code, link text/targets/URLs, dishonest metadata, undeclared/nested bindings,
normalized procedure duplication, exact allowlist schema and dates, verified
claim rejection, exact path/term suppression, and rename before/after blobs.
The focused routing set also replays TypeScript exclusion behavior, capability
activation, `/which-skill`, and `/which-shape` characterization.

## Final commands and output addresses

Each SHA-256 is over concatenated stdout then stderr bytes.

| Command | Exit | Bytes | Output SHA-256 | Result |
|---|---:|---:|---|---|
| `.venv/bin/python -m pytest -q tests/test_core_framework_leakage.py tests/test_skill_catalog_layers.py tests/test_skill_meta_jobs.py tests/test_which_skill_recommendations.py tests/test_which_shape.py tests/test_skill_activation.py tests/test_capability_consumers.py` | 0 | 180 | `8b1dded2d8cff5060424ad40b581a57c1315e23bae152c4be4bc7987f3642b4f` | `88 passed in 12.07s` |
| `.venv/bin/python scripts/lint/no_core_framework_leakage.py --all` | 0 | 124 | `a5b40a26e2f412f3ad433cb0861ba3171fe25de2fb3ee6f37f7cb9bf3bf7af03` | 15 migrated core skills clean |
| `.venv/bin/python scripts/skill_meta.py lint --strict --quiet` | 0 | 44 | `2badb5016d4f1cd99837de4e36bf24f4756cbbccdf13151085c26ee54427bb6b` | 76/76 contracts clean |
| `.venv/bin/ruff check scripts/lint/no_core_framework_leakage.py tests/test_core_framework_leakage.py` | 0 | 19 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | all checks passed |
| `.venv/bin/python scripts/specs.py coverage portable-skill-layer-distribution` | 0 | 3,065 | `b018a9c817809a66c3ba4cc1bfc6c6c5ee7ea754a889cc9e2ae151e7b6721488` | 4/30 recorded; zero lag/ahead/orphans; coordinator-owned IM-5/IM-6 remain unchecked |
| `.venv/bin/python scripts/specs.py inventory-check portable-skill-layer-distribution` | 0 | 204 | `9f0a04ef0e2ade22f09025cb2f92bb983d5329e12752435aa9d180e975864965` | clean; no stubs |

`git diff --check -- . ':!logs/**'` also exited 0. The full project suite was
not run in this shared dirty worktree; the focused 87-test routing/boundary
suite is the verification for this slice.

## Principal content addresses

| Path | SHA-256 |
|---|---|
| `scripts/lint/no_core_framework_leakage.py` | `57f5202d9793b64da34abe7d454835fac167433164e767f218ddb5579e72a8e3` |
| `tests/test_core_framework_leakage.py` | `c69d9398009f3c2fe1b1e93f9d3fb1ad8f601251ea02537825251750c93bf2b8` |
| `.claude/skills/_common/core-framework-leakage-allowlist.yml` | `b218c39c7c565788d6b8751740455f30f0969725675bb986513bccde1dcc8074` |
| `.claude/skills/_common/capability-registry.yml` (committed WP3 blob) | `27a4fb1060ce70564b2a4810bfcfc628b3fea43cc5b804612d003da20aaedff4` |
| `.claude/skills/_common/skill-catalog-inventory.yml` | `bec0e6c92d32e77433a24c02403dcd0eba0c50f7033104e47de400e4621216dc` |

The coordinator staged only the `core_leakage_terms` hunk in the functional
commit; concurrent WP5 native-sweep registry work remains outside this slice.
