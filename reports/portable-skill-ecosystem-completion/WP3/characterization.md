# WP3 characterization — portable skill layers and distribution

Status: **characterization complete; implementation not started**. This report
freezes AR-1 through AR-12 for
`ai-docs/specs/portable-skill-layer-distribution.md`. It is an oracle and gap
record, not acceptance evidence for any IM or AC.

## Provenance and bounds

- Characterized revision: `ce9a181f98d107351bc5c2c3982aaca80f760f57`
  (`git rev-parse HEAD`). The shared worktree was dirty in unrelated WP4 and
  agent-policy surfaces; no dirty path was used as a WP3 implementation claim.
- Platform: macOS 26.5.1 (build 25F80), arm64.
- Agent/model visible to this lane: Codex based on GPT-5. A more specific model
  variant and reasoning-effort setting were not exposed.
- Lane: `/root/wp3_characterization_bounded`.
- Enumeration was bounded to `git ls-files`, `git grep`, explicit named files,
  and explicit named skill directories. No repository `find`, no untracked-tree
  scan, and no `Path.rglob` was executed. The existing
  `extract-enum/scripts/collect.py` contains a `Path.rglob` implementation; it
  was read but deliberately not run for this characterization.
- The auto-mutating tracked telemetry file `logs/agent_policy/test_runs.jsonl`
  is excluded from the reference oracle. Including it would make the oracle
  change merely by running its own evidence commands. The WP3 report itself is
  also excluded to avoid self-reference.

## AR disposition summary

| AR | Disposition | Frozen result / implementation gap |
|---|---|---|
| AR-1 | characterized | 76 canonical top-level skills; exact inventory, metadata/content hashes, 1,176 source-reference records, and the 76-name Django-applicable set pinned below. |
| AR-2 | characterized | Every row has exactly one proposed layer, declared binding IDs, rationale code, and readiness. No domain layer is selected. The machine-readable authority/validator does not exist yet. |
| AR-3 | characterized | Exact 14-skill de-flavor set and separate 15-skill foundation-ready distribution set pinned; no runtime wildcard remains. |
| AR-4 | characterized | N=1 shipping boundaries, >=3 domains, concept+binding default, N=2 rejection, and the missing `/plan-skill` question pinned. No domain qualified. |
| AR-5 | characterized | Nineteen case-insensitive Django/Celery body occurrences in the AR-3 set plus fixture expectations pinned. Leakage lint/fixtures do not exist yet. |
| AR-6 | characterized | Current selector positives and failures pinned. It is global rather than per-root, ignores incompatible registered overrides, and permits a required-zero-match Ruby profile. |
| AR-7 | characterized | Django input, semantic final proposal oracle, invalid-routing result, and hashes pinned. There is no existing final-boundary fixture/test. |
| AR-8 | characterized | Exact allowed normalizations and semantic non-normalizations pinned. Comparator does not exist yet. |
| AR-9 | characterized | Five-surface/version matrix, projection paths, structural hash, locally available discovery commands, and observed gaps pinned. Cursor/Augment proof is unavailable; no runtime surface is certified. |
| AR-10 | characterized | Four complete cold-host manifests and tree hashes pinned. Fixture directories and installer do not exist yet. |
| AR-11 | characterized | Stable-root proposal and all self-anchors in foundation/exemplar code pinned. Current move tool does not document or rewrite `Path(__file__)...parents[N] / asset`. |
| AR-12 | characterized | `/which-shape` read-only useful-output oracle, 0.200381-second local run, and dynamic kernel deny-read proof pinned. Install-inclusive replay remains impossible because the installer is absent. |

## AR-1 and AR-2 — catalog, metadata, references, and placement inventory

Canonical discovery means only tracked immediate children matching
`.claude/skills/<name>/SKILL.md`. Four deeper tracked fixture `SKILL.md` files
are not catalog entries. Current metadata counts are exactly 33 `any/any`, 5
`any/django`, 15 `python/any`, and 23 `python/django`. Because a Django host
matches both `any` and `python` plus both `any` and `django`, the exact current
Django-applicable name set is all 76 names in the table.

Content addresses:

- exact `path + NUL + raw frontmatter + NUL` stream, sorted by path:
  `db43fd0e4c89b41402fd4b0789e063d8b5fba8d7859bf69627cd9ae85d4c6bb9`;
- exact `path + NUL + complete SKILL.md bytes + NUL` stream:
  `60608fdf74eca2f8076b60661587728d9c0a60b6f3bb51edb438ece2408a8d93`;
- sorted Django-applicable names, one LF-terminated name per line:
  `e7ed28551e071089e2f11c76713f1c1ec7c2d342107109a22630c6f9828ff138`;
- every exact literal top-level skill-root reference from tracked source,
  sorted as complete `git grep -n` records: 1,176 records in 208 files,
  SHA-256 `6bba6d72256eda9d8ba372bf7c0bbf929bce64ec3c78a8080bb05221c5f146e4`.

`fm16` is the first 16 hex characters of that row's raw-frontmatter SHA-256;
the full-stream digest above is authoritative. `refs` is the row's contribution
to the 1,176-record reference oracle. Placement rationale codes are: U =
universal concept/procedure; P = Python subject mechanics belong in a `python`
binding; D = Django idiom/examples belong in a `django` binding; L =
irreducibly Python runtime bootstrap; F = irreducibly django-cotton-native.
Toolkit implementation language alone does not create a subject-language
binding.

| Name | Canonical path | Current language/framework | fm16 | refs | Proposed layer | Declared binding IDs | Readiness | Why |
|---|---|---|---:|---:|---|---|---|---|
| `adapt-project` | `.claude/skills/adapt-project/SKILL.md` | `any/any` | `4e5b40ce82ea1d5c` | 6 | `core` | `core` | `deferred-to-wp8` | U |
| `architecture-fit` | `.claude/skills/architecture-fit/SKILL.md` | `any/any` | `926e5f56d1341afa` | 3 | `core` | `core` | `foundation-ready` | U |
| `audit-decisions` | `.claude/skills/audit-decisions/SKILL.md` | `any/any` | `776c6fdf0d147255` | 9 | `core` | `core` | `deferred-to-wp8` | U |
| `brainstorm-ideas` | `.claude/skills/brainstorm-ideas/SKILL.md` | `any/any` | `6d2c7b491a4fdcb5` | 9 | `core` | `core` | `deferred-to-wp8` | U |
| `check-ecosystem-consistency` | `.claude/skills/check-ecosystem-consistency/SKILL.md` | `any/any` | `4bb9b751156be922` | 13 | `core` | `core` | `deferred-to-wp8` | U |
| `converge` | `.claude/skills/converge/SKILL.md` | `any/any` | `644cee7868ecd4d1` | 7 | `core` | `core` | `deferred-to-wp8` | U |
| `decide` | `.claude/skills/decide/SKILL.md` | `any/any` | `95edbc081af755b1` | 7 | `core` | `core,django` | `foundation-ready` | UD |
| `design-it-twice` | `.claude/skills/design-it-twice/SKILL.md` | `any/any` | `03d7e2972ca15869` | 2 | `core` | `core,django` | `foundation-ready` | UD |
| `diagnose` | `.claude/skills/diagnose/SKILL.md` | `any/any` | `00df19bde9467e14` | 8 | `core` | `core` | `deferred-to-wp8` | U |
| `engineer-init` | `.claude/skills/engineer-init/SKILL.md` | `python/any` | `1031ce9f5cc563ad` | 2 | `language` | `python` | `deferred-to-wp8` | L |
| `explain-code` | `.claude/skills/explain-code/SKILL.md` | `python/django` | `d5d8bb73f38f9021` | 23 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `extract-cotton-primitive` | `.claude/skills/extract-cotton-primitive/SKILL.md` | `python/django` | `08f16e57eab6431d` | 10 | `framework` | `django` | `deferred-to-wp8` | F |
| `extract-enum` | `.claude/skills/extract-enum/SKILL.md` | `python/django` | `491e7223cf996e0d` | 13 | `core` | `core,python,django` | `exemplar-ready` | PD |
| `extract-existing-ideas` | `.claude/skills/extract-existing-ideas/SKILL.md` | `any/any` | `2c0f48a233836a01` | 12 | `core` | `core` | `deferred-to-wp8` | U |
| `extract-state-type` | `.claude/skills/extract-state-type/SKILL.md` | `python/django` | `397c0e91bca621ba` | 12 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `extract-workflow-registry` | `.claude/skills/extract-workflow-registry/SKILL.md` | `python/django` | `9cab1d9d9b4da6ab` | 3 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-async-lifecycle-drift` | `.claude/skills/find-async-lifecycle-drift/SKILL.md` | `any/django` | `def2b3c197826a82` | 7 | `core` | `core,django` | `deferred-to-wp8` | UD |
| `find-comment-drift` | `.claude/skills/find-comment-drift/SKILL.md` | `any/django` | `6fe138595f6ea948` | 20 | `core` | `core,django` | `deferred-to-wp8` | UD |
| `find-complexity-hotspots` | `.claude/skills/find-complexity-hotspots/SKILL.md` | `python/django` | `fde2818c497ba9b9` | 23 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-concept-divergence` | `.claude/skills/find-concept-divergence/SKILL.md` | `python/any` | `0a6ca20d7d30b365` | 23 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-contract-drift` | `.claude/skills/find-contract-drift/SKILL.md` | `any/django` | `3867b8e804f4b7a5` | 18 | `core` | `core,django` | `deferred-to-wp8` | UD |
| `find-dead-route-surface` | `.claude/skills/find-dead-route-surface/SKILL.md` | `any/django` | `b9c0339e1fb28631` | 6 | `core` | `core,django` | `deferred-to-wp8` | UD |
| `find-doc-route-drift` | `.claude/skills/find-doc-route-drift/SKILL.md` | `python/django` | `7ada09f37997970a` | 11 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-dormant` | `.claude/skills/find-dormant/SKILL.md` | `python/django` | `3074ffddbdcdcbc4` | 11 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-duplication` | `.claude/skills/find-duplication/SKILL.md` | `python/django` | `525f59b355070cfb` | 11 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-folder-topology-drift` | `.claude/skills/find-folder-topology-drift/SKILL.md` | `python/any` | `3e4db6b660639f23` | 21 | `core` | `core,python` | `deferred-to-wp8` | P |
| `find-frontend-contract-drift` | `.claude/skills/find-frontend-contract-drift/SKILL.md` | `python/django` | `fe9e6cce46922221` | 30 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-frontend-duplication` | `.claude/skills/find-frontend-duplication/SKILL.md` | `python/django` | `c10878b8d7bce617` | 18 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-implicit-state` | `.claude/skills/find-implicit-state/SKILL.md` | `python/django` | `5561c299705b760f` | 14 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-incomplete-sweep` | `.claude/skills/find-incomplete-sweep/SKILL.md` | `python/any` | `9bea257ed86aeecf` | 28 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-layer-violation` | `.claude/skills/find-layer-violation/SKILL.md` | `python/django` | `ccf5c9198c8cd675` | 14 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-omnibus` | `.claude/skills/find-omnibus/SKILL.md` | `any/any` | `dcbee064b2a59a2a` | 19 | `core` | `core` | `deferred-to-wp8` | U |
| `find-orphaned-ideas` | `.claude/skills/find-orphaned-ideas/SKILL.md` | `any/any` | `07b014229b98c7d8` | 18 | `core` | `core` | `deferred-to-wp8` | U |
| `find-perimeter-gaps` | `.claude/skills/find-perimeter-gaps/SKILL.md` | `any/any` | `3a85ce20b4fba3fa` | 18 | `core` | `core` | `deferred-to-wp8` | U |
| `find-query-mutation` | `.claude/skills/find-query-mutation/SKILL.md` | `python/django` | `d929cec9c415beef` | 11 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-route-sprawl` | `.claude/skills/find-route-sprawl/SKILL.md` | `python/django` | `f2787424b823d7a3` | 11 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-rule-surface-drift` | `.claude/skills/find-rule-surface-drift/SKILL.md` | `python/any` | `7f45f75c6b5d18f2` | 14 | `core` | `core,python` | `deferred-to-wp8` | P |
| `find-semantic-duplication` | `.claude/skills/find-semantic-duplication/SKILL.md` | `python/django` | `acd089a0e26bf418` | 28 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-skill-artifact-drift` | `.claude/skills/find-skill-artifact-drift/SKILL.md` | `python/any` | `37793012cdc2276d` | 24 | `core` | `core,python` | `deferred-to-wp8` | P |
| `find-skill-intent-drift` | `.claude/skills/find-skill-intent-drift/SKILL.md` | `python/any` | `3752a8975ec74494` | 13 | `core` | `core,python` | `deferred-to-wp8` | P |
| `find-stale-artifacts` | `.claude/skills/find-stale-artifacts/SKILL.md` | `python/any` | `9a91de4fc4bb89c4` | 6 | `core` | `core,python` | `deferred-to-wp8` | P |
| `find-standard-gaps` | `.claude/skills/find-standard-gaps/SKILL.md` | `python/any` | `41344713180d3bbe` | 41 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-test-obligation-drift` | `.claude/skills/find-test-obligation-drift/SKILL.md` | `any/django` | `375a7853131d3f2b` | 34 | `core` | `core,django` | `deferred-to-wp8` | UD |
| `find-transaction-overreach` | `.claude/skills/find-transaction-overreach/SKILL.md` | `python/django` | `91c1b7f39ba5652f` | 26 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-workflow-duplication` | `.claude/skills/find-workflow-duplication/SKILL.md` | `python/django` | `6f5da0fbfee3144c` | 18 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `find-workflow-state-gaps` | `.claude/skills/find-workflow-state-gaps/SKILL.md` | `any/any` | `9077a32df1011bdf` | 32 | `core` | `core` | `deferred-to-wp8` | U |
| `fix-workflow` | `.claude/skills/fix-workflow/SKILL.md` | `python/django` | `2d06c99d7c1b3294` | 82 | `core` | `core,python,django` | `foundation-ready` | PD |
| `gut-check` | `.claude/skills/gut-check/SKILL.md` | `any/any` | `82768a19aca442ce` | 7 | `core` | `core` | `deferred-to-wp8` | U |
| `harvest-learnings` | `.claude/skills/harvest-learnings/SKILL.md` | `any/any` | `4113e47b6c7e627a` | 10 | `core` | `core` | `deferred-to-wp8` | U |
| `impact-feature` | `.claude/skills/impact-feature/SKILL.md` | `any/any` | `6646c029230ae112` | 10 | `core` | `core` | `foundation-ready` | U |
| `introduce-fk` | `.claude/skills/introduce-fk/SKILL.md` | `python/django` | `0da9f1729d594522` | 26 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `map-product-workflow` | `.claude/skills/map-product-workflow/SKILL.md` | `python/django` | `b749ccc55c23d579` | 13 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `map-subsystem` | `.claude/skills/map-subsystem/SKILL.md` | `python/any` | `d967532fa4bf5ad1` | 21 | `core` | `core,python` | `deferred-to-wp8` | P |
| `mature-existing-ideas` | `.claude/skills/mature-existing-ideas/SKILL.md` | `any/any` | `63583d76b96761e1` | 10 | `core` | `core` | `deferred-to-wp8` | U |
| `move-path` | `.claude/skills/move-path/SKILL.md` | `python/any` | `90913183713a8e7a` | 7 | `core` | `core,python` | `deferred-to-wp8` | P |
| `organize-project-structure` | `.claude/skills/organize-project-structure/SKILL.md` | `any/any` | `bf17282b20410abd` | 1 | `core` | `core,django` | `foundation-ready` | UD |
| `orient` | `.claude/skills/orient/SKILL.md` | `any/any` | `580261b7cbd56ca0` | 19 | `core` | `core` | `deferred-to-wp8` | U |
| `plan-feature` | `.claude/skills/plan-feature/SKILL.md` | `any/any` | `c312c19499190ff9` | 18 | `core` | `core` | `foundation-ready` | U |
| `plan-skill` | `.claude/skills/plan-skill/SKILL.md` | `any/any` | `ee0e774ab26623ac` | 3 | `core` | `core` | `foundation-ready` | U |
| `plan-spec` | `.claude/skills/plan-spec/SKILL.md` | `any/any` | `e4dc45c684f058f6` | 6 | `core` | `core` | `foundation-ready` | U |
| `prevent-regression` | `.claude/skills/prevent-regression/SKILL.md` | `python/any` | `666aadcbe3b418d6` | 23 | `core` | `core,python,django` | `foundation-ready` | PD |
| `project-interview` | `.claude/skills/project-interview/SKILL.md` | `any/any` | `f03b27f302e3e286` | 1 | `core` | `core` | `deferred-to-wp8` | U |
| `propose-boundary` | `.claude/skills/propose-boundary/SKILL.md` | `python/any` | `6a4740fe9ebd377f` | 9 | `core` | `core,python` | `deferred-to-wp8` | P |
| `propose-folder-reorganization` | `.claude/skills/propose-folder-reorganization/SKILL.md` | `python/any` | `d93b1613bfbd3bac` | 17 | `core` | `core,python,django` | `foundation-ready` | PD |
| `query-patterns` | `.claude/skills/query-patterns/SKILL.md` | `any/any` | `699c78c678fb7007` | 9 | `core` | `core` | `deferred-to-wp8` | U |
| `refactor-subsystem` | `.claude/skills/refactor-subsystem/SKILL.md` | `python/django` | `10059b566b03585e` | 24 | `core` | `core,python,django` | `foundation-ready` | PD |
| `rename-concept` | `.claude/skills/rename-concept/SKILL.md` | `python/any` | `f8bfce7bed1cb7a2` | 8 | `core` | `core,python` | `deferred-to-wp8` | P |
| `repair-skill` | `.claude/skills/repair-skill/SKILL.md` | `any/any` | `fa70f6b1399d7fe8` | 27 | `core` | `core` | `deferred-to-wp8` | U |
| `scope-feature` | `.claude/skills/scope-feature/SKILL.md` | `any/any` | `da0b6baf4ec509a0` | 8 | `core` | `core` | `foundation-ready` | U |
| `teach-pattern` | `.claude/skills/teach-pattern/SKILL.md` | `any/any` | `d95d3e1a33290258` | 7 | `core` | `core` | `deferred-to-wp8` | U |
| `track-idea` | `.claude/skills/track-idea/SKILL.md` | `any/any` | `a35d78c91afacd3b` | 25 | `core` | `core` | `deferred-to-wp8` | U |
| `triage-debt` | `.claude/skills/triage-debt/SKILL.md` | `any/any` | `de0cf1470cff2694` | 7 | `core` | `core` | `deferred-to-wp8` | U |
| `unify-shadows` | `.claude/skills/unify-shadows/SKILL.md` | `python/django` | `ae8451cff21b02c5` | 12 | `core` | `core,python,django` | `deferred-to-wp8` | PD |
| `which-cleanup` | `.claude/skills/which-cleanup/SKILL.md` | `any/any` | `4a707bff573a9511` | 14 | `core` | `core` | `deferred-to-wp8` | U |
| `which-shape` | `.claude/skills/which-shape/SKILL.md` | `any/any` | `9cb1adc49cd15c9b` | 29 | `core` | `core` | `foundation-ready` | U |
| `which-skill` | `.claude/skills/which-skill/SKILL.md` | `any/any` | `f7a8440f6c476a69` | 16 | `core` | `core,django` | `foundation-ready` | UD |

Coverage disposition: 76 unique discovered names, 76 unique rows, no unknown
row, no duplicate row, one layer per row. Readiness counts are 15
`foundation-ready`, 1 `exemplar-ready`, 60 `deferred-to-wp8`, and 0
`inventory-only`. Proposed layer counts are 74 core, 1 language, 1 framework,
and 0 domain/host-overlay. This is a characterization decision, not a verified
portable-support claim.

## AR-3 — frozen foundation sets

The exact `plan-*` members are `plan-feature`, `plan-skill`, and `plan-spec`.
The complete planning chain also includes `scope-feature`, `impact-feature`,
and `architecture-fit`.

The exact AC-3.1/IM-6 de-flavor set is these 14 names, with no implementation-
time wildcard:

```text
architecture-fit
decide
design-it-twice
fix-workflow
impact-feature
organize-project-structure
plan-feature
plan-skill
plan-spec
prevent-regression
propose-folder-reorganization
refactor-subsystem
scope-feature
which-skill
```

The six non-explicit siblings were selected because their procedure is
stack-neutral while the current body/default/example surface is Django/Celery
flavored: `decide`, `design-it-twice`, `fix-workflow`,
`organize-project-structure`, `propose-folder-reorganization`, and
`which-skill`. Detector/extractor rows with framework-bound executable
mechanics are not incidental siblings; they remain WP8-deferred except for the
named `extract-enum` exemplar. `which-shape` is the fifteenth
`foundation-ready` distribution row solely for AR-12 first value; it is already
framework-neutral and is not part of IM-6's de-flavor edit set.

## AR-4 — placement rules

The frozen validator behavior is:

1. A shipping-contract layer (`language`, `framework`, or host overlay) is
   valid at N=1.
2. A `domain/<id>` cohesion group is valid only at N>=3.
3. A two-member domain group is invalid, even if both proposed rows agree.
4. Framework-flavored general concepts default to `core` plus thin declared
   bindings. Only an irreducibly native concept enters `framework/<id>`.
5. `/plan-skill` must ask: “Which shipping layer owns the concept, and if the
   content is language/framework-flavored, why is this concept+binding rather
   than native? If domain is proposed, name at least three cohesive members.”

No domain qualified in the 76-row inventory, so there is no domain ID or domain
loader behavior to register in WP3. Current registry IDs already cover
`core`, `python`, `javascript-typescript`, `rust`, `go`, `django`, and `react`.
The current `/plan-skill` body has no placement/layer/domain question; its only
binding occurrence is “binding dogfood” at line 172. This is an IM-2 gap.

## AR-5 — core-boundary oracle

Case-insensitive `django|celery` scan of only the 14 AR-3 bodies produces 19
body occurrences:

- `decide:96` (`celery-safe-dispatch`);
- `design-it-twice:145-146` (Django ORM example);
- `fix-workflow:213` (Django test baseline); current frontmatter also says
  `framework: django` at line 21;
- `organize-project-structure:147` (Django app layout);
- `prevent-regression:297` (Django/unit-test example);
- `propose-folder-reorganization:60,101,323` (Django boundary/import/runner);
- `refactor-subsystem:123,286,297,663,669,755,818,865,919` (Django/Celery
  defaults and examples); current frontmatter says `framework: django` at line
  21;
- `which-skill:137` (Django-bound routing example).

The six planning-chain bodies are clean today. The future lint fixture oracle
is exact:

| Fixture | Expected |
|---|---|
| neutral core prose, honest `language:any/framework:any` | pass |
| core declares `bindings:[django]`, body stays neutral | pass |
| `bindings/django.md` contains Django/Celery idioms | pass |
| `Django` or `Celery` in core prose | fail |
| `django`, `DJANGO`, `celery`, or mixed-case variants | fail |
| framework term inside a fenced code block | fail |
| framework term in Markdown link text, target, or URL | fail |
| “compatibility exception: Django ...” inline in core | fail; no inline waiver |
| core body neutral but frontmatter claims `framework:django` without a native framework layer | fail dishonest metadata |
| framework-native body labeled `framework:any` | fail dishonest metadata |
| binding repeats normalized core procedure paragraphs | fail duplication |
| undeclared file under `bindings/` | fail |

`scripts/lint/no_core_framework_leakage.py` and its tests/fixtures are absent.

## AR-6 — binding-selection oracle

Current `scripts/installer_selection.py` evidence:

| Case | Frozen expected oracle | Current result |
|---|---|---|
| Django root (`python`/`django`) | `core -> python -> django`, with root identity and hashes | selects `core,python,django`, but emits no root/evidence hashes |
| TS/React root | `core -> javascript-typescript -> react` | passes structurally |
| TS + Vite, framework `none` | no React inference | selects only `core,javascript-typescript` (pass) |
| zero required match | fail closed | registered Ruby profile returns core-only (gap) |
| same-precedence ambiguity | fail unless exactly one compatible explicit selection | mixed Python/TS fails at language ambiguity (pass) |
| incompatible registered override | fail | explicit Django on TS and explicit React on Django are silently ignored (gap) |
| unknown override | fail | fails (pass) |
| root A binding used for root B | fail | no per-root API/evidence exists (gap) |
| directory/registry order as tiebreaker | forbidden | ambiguity blocks mixed candidates, but successful output ordering still follows registry insertion order and is not evidenced independently |

The future evidence must name canonical root, profile hash, core hash, ordered
overlay IDs/hashes, rendered hash, and all rejection details. It must evaluate
each root independently; passing one global mixed-stack dictionary is not an
acceptable substitute.

## AR-7 and AR-8 — `extract-enum` semantic oracle

Pinned Django fixture input bytes:

```python
# app/models.py — sha256 abcedb51dab2814f7b8d9b3c99c10d5c9c74efd782f8352397dd25ef5eb1a3bd
from django.db import models

STATUS_CHOICES = (("pending", "Pending"), ("running", "Running"), ("done", "Done"))

class Job(models.Model):
    status = models.CharField(max_length=16, default="pending", choices=STATUS_CHOICES)
```

```python
# app/services.py — sha256 6bbea6f11b8036fa1730d8c957da195ca374ec2a128b9eef8ea206cb3ef7e93b
from app.models import Job

def is_pending(job: Job): return job.status == "pending"
def has_case_variant(job: Job): return job.status == "Pending"
def is_done(job: Job): return "done" == job.status
def vendor_bridge(job: Job): return job.status == "vendor_pending"
def start(job: Job): job.status = "running"
```

The target is `app/models.py::status::Job`; field symbol `Job.status`; current
kwargs are exactly `max_length=16`, `default="pending"`, and
`choices_ref="STATUS_CHOICES"`. The semantic final-output oracle has SHA-256
`75feed33e714824011879933131a1b2637024373a2e16a3698e5ce7a328b8f36`
over compact sorted-key JSON and pins:

- five distinct literals: `Pending` (count 1, variant of `pending`), `done`,
  `pending`, `running`, and `vendor_pending` (each count 1);
- 1 case variant, 4 comparisons, 1 assignment, 1 caller file;
- confirmed sites `is_pending` and `is_done`; bridge site `vendor_bridge`;
  legacy/case-risk site `has_case_variant`; assignment site `start`; no dynamic
  sites;
- enum members/wire values in order: `PENDING="pending"`,
  `RUNNING="running"`, `DONE="done"`; `Pending` and `vendor_pending` are not
  members;
- risks: normalize/audit persisted `Pending`; keep/map `vendor_pending` at the
  bridge; reconcile declared choices against collected literals;
- stop decision: do not execute until every site is migrated, production
  distinct values are a subset of member wire values, characterization tests
  remain green, and the stringly-status lint is clean.

The invalid Form-A input hash is
`3f59100f90a9993f661d1979ad3925979cc87a34925426e76f5ba7cb745e0e0b`.
It pins exit 2, no output, and stderr:

```text
error: finding implicit-state-0001 is introduce_fk_candidate; run /introduce-fk instead of /extract-enum
```

Existing retained smoke evidence (`.claude/tasks/skill-repairs/wave2-extract.md`)
agrees on the current routing result and proves only collector output, not the
final proposal boundary. No tracked Django fixture or final-output test exists.

Allowed AR-8 normalizations are only: replace temporary absolute roots with one
token; remove timestamps/scan IDs; normalize Markdown whitespace; and sort only
tables whose order is semantically irrelevant. Identifiers, target paths,
literals, counts, sites, site classifications, kwargs, member names/order,
wire values, risks, and stop decisions may not be added, removed, folded, or
changed. In particular, a comparator may not normalize away `Pending`,
`vendor_pending`, a missing caller, a changed wire value, or a weaker stop.

## AR-9 — supported surface oracle

Registry hash:
`87efcec9402cb5c17fcc41c305a035d2e3166cc5fea11ad0d2ea5cbf99372508`.
Probe source skill `plan-feature` hash:
`6abdbd8c758a42ebc08a260c19195403a98ec2a8d51e4b42b72197e0cd486d66`.
Projection script hash:
`69a80654d3eb0a2a151254774d55984a383c895597f3d624937d15ef514e84e0`.
The current five-path structural manifest exits 0 and hashes to
`7a7064d5453f52a5e0a867355c6746ec1e2fd0ed2b1c4e4ab1f67e4ab50c9546`.

| Surface | Pinned version / contract | Current projection path and format | Available discovery observation | Current invocation result |
|---|---|---|---|---|
| Claude Code | 2.1.211 / `claude-skill-directory-v1` | `claude-code/.claude/skills/plan-feature/SKILL.md`, exact Markdown copy | binary exactly 2.1.211; help says skills resolve via `/skill-name`; a real isolated command would be `claude --bare -p '/plan-feature ...'` from fixture root | not run: it is a model call and no content-addressed isolated host was installed; `claude plugin list` is not skill-discovery proof |
| Codex | 0.144.1 / `codex-plugin-manifest-v1` | `codex/.codex-plugin/plugin.json` plus `codex/skills/plan-feature/SKILL.md` | binary exactly 0.144.1; `codex plugin list` exists | projected plugin was not installed; list output contains no engineering-skills probe; no invocation proof |
| Augment | `imported-rules-v1` / `augment-imported-rules-v1` | `augment/.augment/rules/imported/plan-feature.md`, hash-attestation Markdown only | `augment` binary unavailable | explicitly unavailable, not clean |
| Cursor | `project-rules-v1` / `cursor-project-instructions-v1` | `cursor/.cursor/rules/plan-feature.mdc`, hash-attestation MDC only | `cursor` binary unavailable | explicitly unavailable, not clean |
| Gemini | 0.45.0 / `gemini-project-instructions-v1` | `gemini/.gemini/plan-feature.md`, hash-attestation Markdown only | binary exactly 0.45.0; `gemini skills list` is available | observed `No skills discovered.` in the current repo; the projection was not installed and current path is not proven compatible |

The structural prototype copies full procedure text only for Claude/Codex; the
other three files contain a source hash, not an executable procedure. Therefore
the structural pass satisfies none of IM-11, AC-3.2, or runtime discovery.

## AR-10 — cold-host ownership oracle

Canonical file hash is SHA-256 of exact UTF-8 content. A tree hash is SHA-256
of sorted lines `<file_sha256><two spaces><path><LF>`. Common files/content in
all four trees are:

| Path | Exact content (`\n` = LF) | SHA-256 |
|---|---|---|
| `.claude/hooks/preflight.sh` | `#!/bin/sh\n# HOST_HOOK_SENTINEL\nexit 0\n` | `3ef7a8cf21f011016beefaac961b1cf3314dd0a4f458662b8d0fbd5601f8f9c9` |
| `.claude/settings.json` | `{"host_setting":true}\n` | `221c30962e8f1b22e2cd55bf0db3c6efedc615437a553d3ff48cf4d45787f573` |
| `.gitignore` | `.engineering/local/\n` | `ea99da70c783dd67434764e5c07a8fd7b55660f54f961abfa6fa751baaa32e47` |
| `AGENTS.md` | `# HOST_SENTINEL: do-not-overwrite\n` | `42f2ef2a3f31a0a6f2109609227dbe791e16d1a24605053aed64530506baff3c` |
| `collision-seed/which-shape.SKILL.md` | `# HOST_COLLISION_SENTINEL\n` | `96cd4d0dff68cbcddd58268cbc2b1df1fb7d007b97a05d47751ce0a35604c273` |

The collision test copies `collision-seed/which-shape.SKILL.md` to the
surface-specific target immediately before install and requires a no-mutation
failure.

| Fixture | Additional complete tree entries (`path` = SHA-256) | Files | Tree SHA-256 |
|---|---|---:|---|
| core-only | `.engineering/project/host-profile.json` = `b02e5a1554c65fd33373e797fae9dc3f2e1a4c5821b6d5d99ea4cdeca9b99127`; `README.md` = `4a6181614dc4f36b5a8c5c7d3c7fc7ca60b0f411df33b27278f6aac44e19db9a` | 7 | `5dcea3c8bc121b1a9423db27a62c5533bd7c438f1d17a42952d2fa72ff061f35` |
| typescript-react | `package.json` = `501857354e465c2426c79487e7db8e66c9f6ce610e5bc879c0ac3d432b91b19d`; `src/App.tsx` = `b54f76ff922c01cb538a579f5e3876951781071dc4b6672a59c584d9869849bd`; `tsconfig.json` = `cf360fc18586b3eb63e7f6dfb5996026fdface516714e6459e7bf696b96ba200` | 8 | `55f4243dd0253330b9f6ab8361b642cba9c00878cc7e3af01ebdefb0ef8df00e` |
| django | `app/models.py` = `6644d6309bd5ae45d21bf65819b38fd0b7d2f7b960ff77de433feccb2a521f7f`; `manage.py` = `ebc79813d7d67ab83088db1f4db88636ace549c8cbe1dac47772cb7333f0ee66`; `requirements.txt` = `494e66d8724c025039b2689e6e5ea167f57e484c5b3d996f2038d858de5438b2` | 8 | `cb34b51e8716a5e837903105d92a2cf4b0320667b2570512bd3483c249f566d9` |
| mixed | `.engineering/toolkit-owned/v1.txt` = `400323a64419cf03a125e2ebc3dc4ef20ab3e2a3614f669b658e58e6aab5ebd7`; `.engineering/toolkit/manifest.json` = `c90f02cda11e4e6614af15ad58583d34f65a68eabf24060270a5ba65ad34d335`; `backend/manage.py` = `d682cbdb4c8b07518bf486c58990fc391783aa20a916bfb27ad211eb1d5c3642`; `backend/requirements.txt` = `494e66d8724c025039b2689e6e5ea167f57e484c5b3d996f2038d858de5438b2`; `frontend/package.json` = `a7f93a0214532ceeb666f0c12dc0e6627d8e8879a2ffb48dfe7e197e82cd95ba`; `frontend/tsconfig.json` = `c42fa568b11e5ac27de30206509ef6e1f5e33915138942a7892cd47bef3884dc` | 11 | `64cd0f41a26308c9100329faf8689de8d102eaa80cecec0bb940c87b86770766` |

Additional exact contents are the strings used by the hash oracle: core profile
`{"schema_version":2,"project_roots":[],"languages":[],"frameworks":[],"tools":[]}\n`;
TypeScript package pins React 19.1.0, TypeScript 5.9.3, Vite 7.0.0 and has a
strict React-JSX tsconfig plus `export const App = () => <main>host</main>;`;
Django pins 5.2.4 and declares the `Job.status` field shown in AR-7; mixed has
separate `backend`/`frontend` markers and a v1 manifest whose owned-file digest
is exactly `400323...`. These baselines require byte-for-byte preservation of
all common host files before/after every lifecycle operation.

The specified `tests/fixtures/wp3/hosts/...` trees are absent today.

## AR-11 — move-safety oracle

Physical path proposal: keep every 15-row foundation-ready root and the
`extract-enum` root at its current `.claude/skills/<name>/` target. No canonical
root move is proposed in WP3. New, non-move overlay targets are
`bindings/python.md` and/or `bindings/django.md` exactly where the AR-2 row
declares those IDs; the de-flavor rows that need a Django overlay are `decide`,
`design-it-twice`, `fix-workflow`, `organize-project-structure`,
`prevent-regression`, `propose-folder-reorganization`, `refactor-subsystem`,
and `which-skill`; `extract-enum` gets both Python and Django overlays.

All current self-anchors in those roots are:

| File:line | Expression / resolved target now | If script moved |
|---|---|---|
| `extract-enum/scripts/collect.py:94` | `parents[2]/_common` -> `.claude/skills/_common` directory | parent depth must be re-derived |
| `extract-enum/scripts/collect.py:100` | `parents[4]/scripts` -> repository `scripts/` directory | parent depth must be re-derived |
| `extract-enum/scripts/collect.py:771` | `parents[4]/scripts/_lib/artifact_scope.py` -> file | canonical broken-asset risk |
| `propose-folder-reorganization/scripts/inspect.py:46` | `parents[4]` -> repository root | parent depth must be re-derived |
| `propose-folder-reorganization/scripts/inspect.py:47` | `.parent` -> its scripts directory | remains self-local |
| `which-skill/scripts/match.py:29-31` | `SCRIPT_PATH` then five `.parent` hops -> repo root; `.claude/skills` target | parent chain must be re-derived |
| `which-shape/scripts/route.py:21-25` | `parents[1]` skill root, `parents[4]` repo root, `parents[2]` skills root, then `shapes.yml` | every pinned target must be re-proven |

Current targets all exist with the expected file/directory type. The current
move tool documents only Markdown links/images, HTML refs, backtick paths,
exact path text, and ignored code imports. It says ambiguous prose and
unsupported imports are not rewritten. It neither documents self-anchored
runtime expressions in its non-rewrite list nor detects/rewrites
`Path(__file__).resolve().parents[N] / asset`; its parser has no `__file__`
handling. Therefore a move could pass its reference rewrite while breaking
`collect.py:771`. This exact inability and a negative fixture must be carried
into IM-3/IM-4 before any tracked move. ADR 0024/0028 remain proposed and are
not changed or claimed embodied here.

## AR-12 — first-value oracle

The frozen useful, read-only invocation is:

```bash
.venv/bin/python .claude/skills/which-shape/scripts/route.py \
  'fix a reproducible bug in one workflow' \
  --json --skip-log \
  --status /tmp/wp3-intentionally-absent-status.json
```

It exits 0, writes 1,820 stdout bytes, no stderr, and hashes to
`cb2171291351f95c36fc7c06667b9401aa117d1079fd95eec8042f93ef5f5c86`.
The useful oracle is `recommendation.shape="bug-fix"`, confidence `high`, score
46, `first_next="reproduce the failure"`, and the four-step reproduce -> root
cause -> verify -> `/prevent-regression` loop. The timed local execution took
0.200381 seconds.

A dynamic harness replaced both `builtins.open` and `pathlib.Path.open` with a
guard that raises on the resolved
`.claude/docs/quality-coordination-kernel.md`. The same invocation returned 0,
the same stdout hash, observed 79 path reads, and `kernel_read=False`.

The install-inclusive clock must start before `skill_installer.py install`,
then cover `verify`, discovery/selection, the command above, semantic hash
comparison, and deny-read assertion, stopping only after the comparison. The
whole sequence must be <=1,200 seconds. Current result is **not** AC-3.6 proof:
`scripts/skill_installer.py` and the offline bundle are absent, so installation,
surface discovery, and verification could not be timed.

## Exact evidence commands

The following are the material characterization commands (all repository
enumeration is tracked/bounded):

```bash
git ls-files '.claude/skills/**' |
  rg '^\.claude/skills/[^/]+/SKILL\.md$'

.venv/bin/python - <<'PY'
import subprocess, pathlib, hashlib, yaml
rev = 'ce9a181f98d107351bc5c2c3982aaca80f760f57'
paths = sorted(p for p in subprocess.check_output(
    ['git','ls-files','.claude/skills/**'], text=True).splitlines()
    if p.count('/') == 3 and p.endswith('/SKILL.md'))
meta = bytearray(); catalog = bytearray(); names = []; refs = []
for p in paths:
    body = pathlib.Path(p).read_bytes()
    raw = body.split(b'---', 2)[1]
    names.append(yaml.safe_load(raw)['name'])
    meta.extend(p.encode() + b'\0' + raw + b'\0')
    catalog.extend(p.encode() + b'\0' + body + b'\0')
    root = p[:-len('/SKILL.md')]
    proc = subprocess.run([
        'git','grep','-n','-I','-F',root,rev,'--',
        ':!reports/portable-skill-ecosystem-completion/WP3/characterization.md',
        ':!logs/agent_policy/test_runs.jsonl'], text=True, capture_output=True)
    refs.extend(line.split(':', 1)[1] for line in proc.stdout.splitlines())
print(len(paths), hashlib.sha256(meta).hexdigest(),
      hashlib.sha256(catalog).hexdigest())
print(hashlib.sha256(('\n'.join(sorted(names))+'\n').encode()).hexdigest())
print(len(refs), hashlib.sha256(
    ('\n'.join(sorted(refs))+'\n').encode()).hexdigest())
PY

rg -n -i 'django|celery' \
  .claude/skills/{architecture-fit,impact-feature,plan-feature,plan-skill,plan-spec,scope-feature,decide,design-it-twice,fix-workflow,organize-project-structure,prevent-regression,propose-folder-reorganization,refactor-subsystem,which-skill}/SKILL.md

.venv/bin/python - <<'PY'
import json, sys
sys.path.insert(0, 'scripts')
from installer_selection import select_install
for stack in [
    {'languages':['python'],'frameworks':['django'],'tools':['pytest']},
    {'languages':['typescript'],'frameworks':['react'],'tools':['vite']},
    {'languages':['typescript'],'frameworks':['none'],'tools':['vite']},
    {'languages':['ruby'],'frameworks':['none'],'tools':[]},
    {'languages':['python','typescript'],'frameworks':['django','react'],
     'tools':['pytest','vite']},
]:
    try: print(json.dumps(select_install(stack), sort_keys=True))
    except Exception as exc: print(type(exc).__name__, str(exc))
PY

.venv/bin/python -c 'import subprocess,tempfile,sys,hashlib; d=tempfile.TemporaryDirectory(prefix="wp3-surface-probe-"); p=subprocess.run([sys.executable,"scripts/distribution_probe.py",".claude/skills/plan-feature/SKILL.md",d.name],capture_output=True); print(p.returncode,hashlib.sha256(p.stdout).hexdigest(),len(p.stdout),len(p.stderr))'

for c in claude codex augment cursor gemini; do
  p=$(command -v "$c" 2>/dev/null || true)
  if [ -n "$p" ]; then printf '%s PATH %s\n' "$c" "$p"; "$c" --version; else printf '%s UNAVAILABLE\n' "$c"; fi
done
claude plugin list
codex plugin list
gemini skills list

rg -n 'Path\(__file__\)|__file__|parents\[[0-9]+\]' \
  .claude/skills/{architecture-fit,impact-feature,plan-feature,plan-skill,plan-spec,scope-feature,decide,design-it-twice,fix-workflow,organize-project-structure,prevent-regression,propose-folder-reorganization,refactor-subsystem,which-shape,which-skill,extract-enum} \
  --glob '*.py' --glob '*.md' --glob '*.yml' --glob '*.yaml'

.venv/bin/python .claude/skills/which-shape/scripts/route.py \
  'fix a reproducible bug in one workflow' --json --skip-log \
  --status /tmp/wp3-intentionally-absent-status.json
```

No automated project suite was run: this lane changed documentation only.
Post-write verification is limited to bounded report/inventory consistency,
Markdown whitespace, and diff inspection.
