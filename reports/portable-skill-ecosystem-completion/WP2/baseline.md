# WP2 pre-change baseline

Date: 2026-07-16
Characterization revision: `db0fed19c7c783d04314dacbc4da73b7a4b3bbf7` (`Promote WP2 and WP4 execution specs`)
Platform: macOS 26.5.1 arm64; Python 3.11.10; pytest 9.0.3; PyYAML 6.0.3

## Scope and workspace state

This is a read-only characterization of WP2 code at `db0fed1`; it is not an
acceptance result. At task start, `git status --short` contained exactly:

```text
 M ai-docs/plans/portable-skill-ecosystem-completion.md
```

That pre-existing 6-addition/5-deletion tracker diff only starts WP2/WP4 and is
excluded from the baseline. Its observed SHA-256 was
`f32c3732a5a00553b3986ee72d368440afd1ac235ca7085fe02cbfce7cb3c814`.
Parallel WP4 implementation paths appeared later in the shared worktree; they
were not inspected as WP2 evidence. The clean perimeter replay below used a
`git archive db0fed1`, so those concurrent changes cannot affect its result.

## Commands and results

```bash
.venv/bin/python --version
.venv/bin/python -c 'import pytest,yaml,platform; print("pytest", pytest.__version__); print("PyYAML", yaml.__version__); print(platform.platform())'
```

Result: exit 0; versions/platform are recorded above.

```bash
.venv/bin/python -m pytest -q \
  tests/scripts/test_project_root_debaking.py \
  tests/scripts/test_which_cleanup_roots.py \
  tests/test_scope.py tests/test_route_topology.py \
  tests/test_project_adapt.py tests/test_perimeter_gaps.py \
  tests/test_engineering_home.py tests/test_which_skill_recommendations.py \
  tests/test_which_shape.py
```

Result: exit 0, `127 passed in 4.50s`.

```bash
.venv/bin/python -m pytest -q \
  tests/test_capability_consumers.py::test_activation_manifest_validates_capability_selection \
  tests/test_capability_registry.py::test_stack_validation_rejects_react_vite_category_confusion \
  tests/test_capability_registry_guard.py::test_all_load_bearing_consumers_import_one_registry
```

Result: exit 0, `3 passed in 0.13s`.

```bash
.venv/bin/python -m pytest --collect-only -q \
  tests/scripts/test_project_root_debaking.py \
  tests/scripts/test_which_cleanup_roots.py
```

Result: exit 0, `16 tests collected in 0.02s`.

Route-sprawl clean replay (outputs were under `/tmp`):

```bash
.venv/bin/python .claude/skills/find-route-sprawl/scripts/detect.py \
  --project-root . --output "$TMP_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-route-sprawl/scripts/report.py \
  --detections "$TMP_DIR/detections.jsonl" \
  --output-md "$TMP_DIR/report.md" --output-json "$TMP_DIR/findings.json" \
  --scan-id baseline --target engineering-skills --project-root . \
  --skip-effectiveness-log
```

Result: both exit 0; `0 findings (no urls.py found)` and Markdown
`Findings: 0`. Output hashes: empty `detections.jsonl`
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
`report.md` `ff59f32e6cbcc92b3b3c4b9581ec1fe3d6fc4768bcf91fabbb33f09b55ba1abd`,
and `findings.json`
`82204fb5cd21a374ba9ec084f7a3f18b98f724a7f8795b1ad395ca7adf9e555f`.

Clean committed perimeter replay:

```bash
BASE=$(mktemp -d /tmp/wp2-db0fed1.XXXXXX)
git archive db0fed1 | tar -x -C "$BASE"
.venv/bin/python "$BASE/.claude/skills/find-perimeter-gaps/scripts/scan.py" \
  --project-root "$BASE" --skills-root "$BASE/.claude/skills" \
  --min-loc 3000 --output "$OUT" --fail-on-gap
```

Result: exit 0; 31 suspect declarations, 8 cells, no gaps. Significant
cells were `scripts/python` (18,934 LOC, 23 declaring detectors),
`ai-docs/markdown` (8,170 LOC, 4), and `tests/python` (7,284 LOC, 23).
JSON SHA-256:
`49e04b1bfff8b6a364ad8d9dd8950db7d75c84815b6b7b847518159b869b157c`.
This is a declaration-based result, not executable coverage evidence.

Two disposable `.venv/bin/python - <<'PY'` fixture probes also exercised the
public functions/CLIs without writing the repository:

- Applying adaptation twice to a seeded Django host reused the same stable
  scan path but produced different adapter bytes when `generated_at` changed;
  a pre-existing `host_owned_marker` in `.engineering/project/adapter.yml`
  was overwritten. Seeded `AGENTS.md` and `.claude/CLAUDE.md` hashes were
  unchanged.
- Five synthetic hosts (Django, TypeScript/React, Rust, Go, and mixed) all
  returned validator-clean adapter payloads, but Rust/Go commands were empty
  and the mixed profile had one root (`.`) and only npm tooling.
- A TypeScript/React adapter followed by `/which-skill` recommended
  `find-duplication` (`language: python`, `framework: django`); the top five
  included two Django-bound skills.
- Component inventory returned the canonical empty payload when undeclared
  (SHA-256 `84bb149df94821cc1e20e2df64b8704a4483e5b0b1c48ecf00f1da2d8fbf09d0`)
  and found one Cotton primitive under a non-seed `ui/components` profile
  (SHA-256 `b1a74fdf71f31f14e6cfd5b7d09f14879a9af3201e0e5f10043e8d00fb028d6d`).

## Existing Class A inventory

The committed Class A regression baseline associated with target-project-root
de-baking is 16 tests in two modules:

- `tests/scripts/test_project_root_debaking.py` (8): git-toplevel default;
  foreign-repo track list; foreign ledger write/no kit write; explicit-root
  precedence; concept-divergence target/label anchoring; missing glossary path;
  outside-target label degradation; incomplete-sweep manifest root.
- `tests/scripts/test_which_cleanup_roots.py` (8): explicit root; git-toplevel
  from subdir; non-git cwd fallback; foreign-repo run anchoring; subdir run;
  explicit-root precedence; foreign coverage audit; kit catalogue lookup from
  a foreign host.

All 16 passed in the focused run. Their hashes are respectively
`2983556097334845b7955729d89d25fa58808254732ef699e55480679e9ab5ad`
and `46fa58f87ae0e72fbbd87c8359572397c390160fbf1dacd48f4644c274400a98`.

The earlier two-file Class A remainder (`propose-folder-reorganization` and
`extract-enum`) is documented in `.claude/tasks/class-a-remainder-notes.md`
(SHA-256 `cc7e1fa2a1bb1c660c42b253d8c832549ed7a54459cca78127885fd8660f0a8c`),
but that note explicitly says no committed skill-specific tests existed. It is
therefore implementation provenance, not an additional green test inventory.

## Route-sprawl ignore-first oracle

The current selector is:

1. `scope.scan(project_root, "find-route-sprawl", extensions={".py"})`.
2. Keep only files named `urls.py`.
3. Prefer a candidate adjacent to one of `settings.py`, `settings`, `wsgi.py`,
   or `asgi.py`; otherwise choose the shallowest path deterministically.
4. If none remains, write an empty JSONL and exit 0.

The repository descriptor has no `## Roots` narrowing and ignores
`.claude/skills/*/fixtures`, `reports/`, and `ai-reports/`, in addition to the
shared built-in/repo ignores. At the baseline it selected 264 Python files,
zero `urls.py` candidates, and no root URLconf. The only two physical
`urls.py` files are under `find-dead-route-surface/fixtures/{good,bad}` and are
correctly excluded. This is the clean comparison oracle for Class C work.

Key hashes: descriptor
`ac2a1ee3c36e274631e5b74d9848bcd91b1b9c97a10e1e53fd3d1895afab5577`;
detector `eb64a528c1843c5d14377c3b681b11bb916862a4bd7573657336e7ff753b2c1a`;
`product_topology.py`
`bbdf7f1051e6e56397c0177d5a0d70348832adc7e8dfb359386992e76461fde6`;
`scope.py` `79d4b8809e686f6c8c57be6f3c79b842e4000ba10859a684abc65ca5f20ed862`;
scope tests `53e78c5059029af45750661c2dc2eef3158bb37e57e6aa851fc7430a8a16df70`;
route-topology tests
`1772ebad12ef411cc9f47a0448f4212bbbc309cdd03ac2c72bb18adf06466dc9`.

## Current guarantees and limitations

### Project adaptation and profiling

- `project_adapt.py` consumes the canonical registry and generated adapter/
  interview payloads validate. An injected `bogus` adapter language is
  rejected as unregistered.
- Current tests cover Django and React discovery, human-unapproved interview
  drafts, opt-in host writes, external no-host-write artifacts, schema-valid
  generated artifacts, and dogfood report sections (9 tests, all green).
- The output is an adapter plus a separate interview profile, not the WP2
  canonical multi-root host profile. It hard-codes one `project_roots: [{path:
  "."}]`, a fixed `SOURCE_ROOT_CANDIDATES` list, and implicit `SKIP_PARTS`.
  Exclusions and per-assertion evidence are not serialized.
- The five-host probe detected language IDs, but Rust and Go had no inferred
  build/test commands. A mixed repository collapsed Rust, Go, and TypeScript
  into global lists; nested Cargo/go markers did not select tools or roots.
  `generated_at` and the absolute project root also make raw output
  nondeterministic.
- Host instruction ownership is safe only because adaptation never writes
  `AGENTS.md`/`CLAUDE.md`. Durable adapter/profile files are unconditional
  rewrites, not merges; existing host-owned content there is lost. A rerun is
  not byte-idempotent because `generated_at` changes.
- Adaptation never calls the perimeter audit and can report success with no
  perimeter result.

### Routing and activation

- `engineering_home.is_skill_active` is a manual, name-based manifest gate:
  absent/malformed state defaults active; normal mode is default-active with
  an opt-out map; a flipped allowlist is supported. Reasons are optional.
- The current toolkit manifest manually deactivates only
  `find-frontend-duplication`, `find-frontend-contract-drift`, and
  `find-route-sprawl`.
- Manifest `capability_selection` validates registry IDs, layers, and bindings,
  but the activation accessor ignores it.
- `/which-skill` rejects unregistered frontmatter and filters manual inactive
  names. It merely emits language/framework/layer/binding fields; it does not
  compare them or required capabilities to an adapter/profile. Consequently a
  TypeScript/React fixture receives Django/Python recommendations.
- `/which-shape` chooses a loop independently. It annotates exact named steps
  that the manual manifest deactivates but leaves the original sequence in the
  result. Generic text such as `selected /find-* skill` cannot be checked; the
  broad-audit fixture showed no inactive annotation.
- `/which-cleanup` has no profile/manifest input. A fixture roster containing
  manually inactive `find-frontend-duplication` still returned it in
  `post_sweep`.
- No current cross-surface conformance test asks all four surfaces for one
  profile-derived activation decision.

### Perimeter evidence and exclusions

- Source language recognition uses the canonical registry. The existing tests
  correctly pin that exact `language` or explicit `scans` declarations cover a
  cell, `language: any` covers none, below-threshold cells are not gaps,
  `--fail-on-gap` is enforceable, and large/data/fixture paths are skipped.
- Coverage is nevertheless only a frontmatter declaration join. The audit does
  not require an installed/version-compatible executable, execute a scan, or
  validate evidence hashes/tool versions. The clean self-scan therefore means
  “some declarations name these languages,” not “these cells were scanned.”
- `--accept root:language` is visible as a boolean and human suffix, but accepts
  no reason and emits no reason-bearing exclusion record.
- Neither `/adapt-project` nor the whole-codebase `/which-shape` entry point
  invokes the audit before concluding.

### Inherited Class B/C paths

- Component inventory is already profile-selected through
  `engineering_home.component_profile`; undeclared or missing definitions
  return an empty inventory. This is executable and the disposable probe
  passed, but there is no committed component-profile regression test.
- `find-folder-topology-drift` already enumerates directories from shared
  ignore-first `scope.iter_paths`; no baked `app` root remains.
- `find-frontend-contract-drift` already enumerates `.html`/`.js` from the
  shared scope; optional roots only narrow that universe.
- Neither migrated Class C detector has a committed equivalence fixture against
  route-sprawl's root/scope/extension/marker-selection oracle.
- Executable seed-host semantics remain. `product_health.infer_surface` maps
  `app/pages/sites`, `templates/core/site_config`, `app/site_management`,
  `app/api`, `app/services/sites`, and `static/js` to `sites_*`, defaulting to
  `sites_surface`. The frontend detector still hard-codes `SITES_CONFIG`,
  `templates/core/site_config`, `static/js/site-config`, `sites_workflow`, and
  a `static/js/<asset>` expansion. Thus the hard-coded-root/search and neutral
  surface-label requirements are not met.

Key Class B/C source hashes: component inventory
`b90a6da398c4793705961418ffc5917ac18960224bce3f9a2a9f3793ff968858`;
folder detector `dc8d0d8c7a6e51c761a51c5ef60b021de6ac57c03b86b8a8f0f5afeac83adb88`;
frontend detector
`f771efc63663173ab4a9cbbe6367c2f769e881abdd9479cfe24ad9f884368860`;
product health
`71690e289826ebd7a7cbc2a6b1fbfa8650354473db0b56de26f02d8bf7cfb5fa`.

## AR characterization status

| AR | Baseline captured | Current gap exposed |
|---|---|---|
| AR-1 | Yes: seeded Django adapter stack, commands, roots, validation, and rerun behavior recorded. | It is an adapter, not the canonical deterministic profile. |
| AR-2 | Yes: instruction hashes remained stable; durable adapter overwrite and timestamp drift recorded. | No merge preservation for project adaptation files; no byte-idempotency test/guarantee. |
| AR-3 | Partial oracle: registry/manifest tests and injected invalid adapter ID reject unknown values. | No negative fixture pins every profile/adaptation boundary. |
| AR-4 | Yes: 16 existing Class A tests inventoried and green. | The older two-file remainder has no committed dedicated tests. |
| AR-5 | Yes: exact scope, `.py` filter, `urls.py` selector, marker preference, zero output, and hashes recorded. | Class C equivalence fixtures do not exist. |
| AR-6 | Yes: current declaration-only semantics and clean self-scan recorded. | Missing/incompatible/uninstalled/non-executable evidence states do not exist, so they cannot become gaps. |
| AR-7 | Yes: accepted blind spots are visible today. | Acceptance is reasonless in both CLI and JSON. |
| AR-8 | Yes: manifest, `/which-skill`, `/which-shape`, and `/which-cleanup` answers characterized. | They do not share one decision and demonstrably diverge. |

## Acceptance gap at `db0fed1`

| AC | Baseline verdict | Blocking gaps |
|---|---|---|
| AC-2.1 | FAIL | No canonical deterministic five-host profile; no per-root mixed composition, serialized exclusions/evidence, or Rust/Go commands. |
| AC-2.2 | FAIL | Adaptation consumes its own adapter discovery, not the WP2 profile; perimeter is bypassable/absent; durable state overwrites; reruns vary. Registry-valid generated IDs and no instruction writes are only partial guarantees. |
| AC-2.3 | FAIL | `/which-skill` does not filter capabilities/layers/bindings or host stack and recommends Django skills for TypeScript. Material exclusions are limited to manual inactive high scorers. |
| AC-2.4 | FAIL | Manual activation is consumed inconsistently and `/which-cleanup` ignores it; no shared decision/conformance test. |
| AC-2.5 | FAIL | Perimeter coverage is declaration-only, accepted exclusions have no reason, and adaptation/whole-codebase routing do not invoke the audit. |
| AC-2.6 | FAIL (partial groundwork) | Component-profile empty fallback and shared Class C enumeration are present; neutral profile-derived product surfaces, removal of remaining seed paths, committed good/bad Class B fixtures, hard-coded-path guard, and Class C equivalence fixtures are absent. Class A and route-sprawl baselines are now pinned by this report. |

## Key implementation/test pointers

- `scripts/project_adapt.py` SHA-256
  `e130e874c935064f47346658060144d85fbd99237819e5ef8d497be38cf50328`;
  `tests/test_project_adapt.py`
  `bd77ff9b4f20eb9d836fd6eb9d77c56697fb7fbe1b5a78bf040af7e0b2b668e6`.
- Perimeter scanner
  `3a0a06ec6913a12e620aada6d23df25b0818b031b744abc64f3cf46d8816881a`;
  tests `c3495db31d6104275f2d33038bef0f39c894e94813239dbc2f026c837b7d58a9`.
- Manifest CLI
  `5bb843bdb8ad30c21fe210ce7a74145a9b558535fc379386969d0b60cbdee5b0`;
  activation tests
  `5538ff2f1d8484403d958a1b2b6cc441672103810882bde9fa6096422c46f188`.
- `/which-skill`
  `acf4f54bdd0334eea23fb2d79a6a4f8c15107ee72f200b5ab0d48a6321cb2a69`;
  `/which-shape`
  `533135be73e29fe6a3c479d44d2ddc3b1450053492da054a9bfb32a0d6572839`;
  `/which-cleanup` runner
  `6a42f2d64f8afec4d494a9ac20ff22da75feeb1e7e2747268eb88f2e501c9ec2`.
- WP2 spec SHA-256
  `4648749a557f37ae32f576deac85cddf74d88330e8020e174b23b3000bbb5bee`;
  canonical registry
  `87efcec9402cb5c17fcc41c305a035d2e3166cc5fea11ad0d2ea5cbf99372508`.
