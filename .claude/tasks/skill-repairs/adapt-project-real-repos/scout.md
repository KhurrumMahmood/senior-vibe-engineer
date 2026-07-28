# Scout — adapt-project real-repository repair (Stage 2)

Date: 2026-07-27 PDT. Repository:
`<repo>`. Assignment-time
HEAD: `584688bb1ea82a98886509d108d25ad9ba60c89a` on
`codex/real-repo-validation`.

This was an independent read-only implementation audit. I read the complete
`.claude/skills/adapt-project/` tree (the guide, Java reference, evidence gate,
portable `discover.py`, and all nine language-branch launchers), all of
`scripts/project_adapt.py`, and all of `tests/test_project_adapt.py`. Python
commands below used
`<repo>/.venv/bin/python`.

## Concurrent-worktree warning

`scripts/project_adapt.py`, the portable `discover.py`, and their tests changed
in the shared worktree while this scout was running. Therefore:

- claim verdicts below are pinned to assignment-time HEAD and the original
  `scan-20260727-19000*` artifacts;
- the baseline was re-executed from `git show HEAD:<path>` in memory, so later
  unstaged edits could not alter the result;
- the exact timestamped artifact paths are authoritative. `latest` was moved by
  concurrent reruns to `scan-20260727-19100*` and is not evidence for the
  original claims; and
- the final section separately audits the live unstaged repair shape.

## 1. Corpus integrity and reproduction

The corpus command completed with exit 0:

```bash
.venv/bin/python scripts/real_repo_corpus.py verify --slice 1
```

It verified clean, detached checkouts at exactly:

| Host | Revision |
|---|---|
| `psf/requests` | `414f0513c33883adf6f2b46901d4f0b38a455851` |
| `sindresorhus/got` | `e3924aa1e53a6ca3eb93a43618ce532442a89b40` |
| `go-chi/chi` | `8b258c7bb28f97a5f2a856ff7ef962578fec9215` |
| `spring-projects/spring-petclinic` | `f182358d02e4a68e52bdbabf55ca7800288511e7` |

`git status --porcelain --untracked-files=all` was empty in every checkout
before and after discovery.

I reproduced assignment-time `scripts/project_adapt.py` in memory from HEAD:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import json, subprocess
source = subprocess.run(
    ['git', 'show', 'HEAD:scripts/project_adapt.py'],
    check=True, capture_output=True, text=True,
).stdout
ns = {
    '__file__': str(Path('scripts/project_adapt.py').resolve()),
    '__name__': 'baseline_project_adapt',
}
exec(compile(source, ns['__file__'], 'exec'), ns)
base = Path('.engineering/local/real-repo-corpus').resolve()
for repo in ('requests', 'got', 'chi', 'spring-petclinic'):
    adapter = ns['discover_project'](base / repo)
    print(repo, json.dumps({
        key: adapter[key]
        for key in ('stack', 'commands', 'source_roots')
    }, sort_keys=True))
PY
```

That output matched the original `19000*` JSON artifacts on every claimed
field. Separately, I ran the documented/load-bearing installed implementation
against all four hosts:

```bash
.venv/bin/python -I -S \
  .claude/skills/adapt-project/scripts/discover.py \
  --project-root "$HOST" \
  --artifact-root "$PWD/.engineering/local/real-repo-validation/scout-installed/$NAME" \
  --timestamp "installed-$NAME" \
  --no-host-write
```

Every invocation exited 0, wrote the four declared artifacts, preserved the
host, and passed:

```bash
.venv/bin/python -I -S \
  .claude/skills/adapt-project/scripts/check_evidence.py \
  --scan-dir "$SCAN_DIR"
# adapt-project evidence OK
```

## 2. Claim verdicts

The first two claims expose two producers with the same artifact name. A
single unqualified TRUE/FALSE would hide the central defect, so their overall
verdict is PARTLY: true for the saved legacy-helper scan, false for the
documented skill implementation.

### C1 — go-chi/chi is detected with no language, markers, or commands — PARTLY

**TRUE for the original saved artifact and HEAD `scripts/project_adapt.py`.**
`scan-20260727-190003/adapter.json` contains:

```json
"stack": {
  "frameworks": [], "languages": [], "markers": [],
  "package_json_paths": [], "package_managers": []
},
"commands": {"dev": [], "lint": [], "setup": [], "test": []},
"source_roots": []
```

The mechanism is exact. At HEAD, `scripts/project_adapt.py:162-181` recognizes
only Python and package-json languages/managers; lines 187-197 list only
Python/Node markers; lines 203-229 emit only Django/package-json commands; and
lines 257-268 inventory a fixed root list with only Python/TS/Markdown counts.
The repository has a root `go.mod`, five eligible root `.go` files, and a
domain-named `middleware/` package, none of which that producer reads.

**FALSE for the installed skill named by `SKILL.md`.** The baseline portable
producer emitted:

```json
"stack": {
  "languages": ["go"], "markers": ["go.mod"],
  "package_managers": ["go"], "frameworks": []
},
"commands": {"test": ["go test ./..."], "lint": [], "dev": [], "setup": []},
"analysis": {"go": {"status": "complete", "analyzer": "filesystem-source-inventory"}}
```

That behavior is promised verbatim by `SKILL.md:119-120` and `:148-163` and
implemented in portable `detect_stack`/`detect_commands`. There is still a
real, narrower defect: the baseline portable source-root list reports only the
five root files. Its own eligibility predicate finds 54 files: 5 root, 30
under `middleware/`, and 19 under `_examples/`. A Go-module-aware inventory
should include the arbitrary `middleware` package and exclude Go-tool-ignored
`_examples`; fixed `cmd/internal/pkg` names are not the Go package model.

### C2 — spring-petclinic is likewise detected with no language, markers, or commands — PARTLY

**TRUE for the original saved artifact and HEAD `scripts/project_adapt.py`.**
`scan-20260727-190004/adapter.json` contains empty languages, markers,
managers, and commands. It has a `src` row, but every count is zero because the
legacy row has no Java field.

**FALSE for the installed skill.** The portable producer emitted Java,
`pom.xml`, `mvnw`, `build.gradle`, `settings.gradle`, `gradlew`, Maven and
Gradle, `./mvnw test`, `./gradlew test`, `analysis.java.status: complete`, and
a `src` row with 30 authored Java files. This is the exact contract at
`SKILL.md:121-123`, `references/java.md`, and the portable Java tests.

Spring framework inference is not required to repair this claim and is outside
the portable contract. `references/java.md` explicitly says discovery does not
"infer frameworks". The correct objective facts are Java/build markers,
commands, and source inventory; adding `spring` from a dependency substring
would broaden and contradict the selected contract.

### C3 — sindresorhus/got omits its `source/` root — TRUE

This is true in both assignment-time producers:

- original `scan-20260727-190002/adapter.json`: `"source_roots": []`;
- portable baseline: also no source roots, and consequently falls back to
  stack language `javascript` instead of the observed `typescript`.

The host has 25 eligible `.ts` files under `source/`; `package.json` declares
`test` and `test:coverage`, which were correctly emitted. The cause is the
fixed candidate tuple: legacy `scripts/project_adapt.py:45-57` and portable
`discover.py:23-35` contain `src` but not the equally conventional `source`.
The JavaScript-family exclusion contract correctly keeps the separate `test/`
tree out; a repair must not turn tests into a production source root.

### C4 — psf/requests has no inferred test command — TRUE

This is true in both assignment-time producers:

```json
"stack": {"languages": ["python"], "markers": ["pyproject.toml"], ...},
"commands": {"test": [], ...}
```

The host gives direct project-owned evidence:
`pyproject.toml` contains `[tool.pytest.ini_options]`, `testpaths = ["tests"]`,
and 15 test Python files. Both producers only emit a Python test command for
`manage.py`; neither reads pytest configuration. The smallest sound inference
is `<selected-python> -m pytest` when a root `pytest.ini` or a structurally
recognized `[tool.pytest.*]` table exists. A generic substring search for
`pytest` is too broad because a dependency mention is not itself command
configuration.

Original claim artifacts (do not replace these with `latest`):

- `.engineering/local/real-repo-validation/requests/adapt/reports/adapt-project/scan-20260727-190001`
- `.engineering/local/real-repo-validation/got/adapt/reports/adapt-project/scan-20260727-190002`
- `.engineering/local/real-repo-validation/chi/adapt/reports/adapt-project/scan-20260727-190003`
- `.engineering/local/real-repo-validation/spring-petclinic/adapt/reports/adapt-project/scan-20260727-190004`

## 3. Smallest general rules and exact edit anchors

### Authoritative repair surface

Repair `.claude/skills/adapt-project/scripts/discover.py`, because that is the
implementation the guide names and copied-install tests execute. Do not
independently grow `scripts/project_adapt.py` into a second 13-language
adapter. If that legacy helper must remain, either make it delegate to the
canonical producer or remove its stale claim to implement `/adapt-project`.

1. **Conventional `source/` alias for JavaScript-family/Python inventory.**
   Baseline anchor: `SOURCE_ROOT_CANDIDATES`, immediately after `"src"`
   (`discover.py:23-35`). Add `"source"`. The existing language-specific
   filters then count Got's 25 TypeScript files and exclude `test/`, generated,
   vendor, build, declaration, spec, and test files. This is a layout synonym,
   not a repository-name special case.

2. **Go package roots follow module contents, not three reserved names.**
   Baseline anchor: in `source_roots`, after the fixed candidate loop and
   before the nested Java `src/main/java` loop (`discover.py` around
   `rows.append(row)` / comment "Maven and Gradle multi-module repositories").
   For a root Go module, inspect safe direct child directories for at least one
   `is_go_source` file, add one row per child, and exclude hidden/underscore,
   example, fixture, testdata, dependency, vendor, build, and generated trees.
   Keep the existing root `.` row. This handles `middleware`, `transport`, or
   any domain package without knowing `chi`.

3. **Infer test commands only from explicit native configuration.**
   Baseline anchor: the Python branch of `detect_commands`, immediately after
   the `manage.py` handling and before setup commands (`discover.py` around
   lines 455-466 at HEAD). Parse `pyproject.toml` with stdlib `tomllib` and emit
   `<python> -m pytest` when `tool.pytest` exists; also accept root
   `pytest.ini`. Malformed TOML should not create a false command. Preserve an
   empty list plus `(none inferred)` when no declaration exists.

4. **Keep manifest-native rules already present.** No new Go/Java stack rules
   are needed in the authoritative producer: root `go.mod` already yields Go,
   manager `go`, marker `go.mod`, and `go test ./...`; root Maven/Gradle markers
   already yield Java, wrapper-aware tests, and Java analysis. Retain the
   explicit no-framework-inference boundary.

5. **Do not broaden setup behavior accidentally.** Adding `npm install`,
   changing command order, or inventing `go vet`/`go mod download` is not
   needed for the four discovery failures. If clean-host executability is a
   separate acceptance requirement, define it explicitly: Requests' editable
   install does not install its `[dependency-groups].test` group, and a test
   command using global `python3` is not paired with a newly created `.venv`.
   That is a separate setup contract, not a reason to smuggle unrelated
   commands into this repair.

### Other exact anchors

- `tests/test_adapt_project_typescript.py`: add the `source/` and pytest
  reduced-host cases beside the existing TypeScript/Python reference cases;
  run through `_discover` so final `adapter.json` is tested, not a helper
  function only.
- `tests/test_adapt_project_go_g1.py`: add an arbitrary top-level
  `middleware/auth.go` plus `_examples/demo.go` case after the current
  exclusion/large-root test.
- `tests/test_adapt_project_java_j2a.py`: existing final-artifact and nested
  Maven/Gradle cases already guard the canonical Java path. Add only a small
  dual-wrapper case if preserving the exact PetClinic marker combination is
  desired.
- `.claude/skills/adapt-project/SKILL.md:84,181,188,232,285`: normalize the
  three conflicting skill-root pointer shapes (see drift audit below).
- `.claude/contracts/skills/adapt-project.yaml`: regenerate/update stale
  structural and intent facts after the implementation is settled.
- `.claude/tasks/real-repository-validation-plan.md`: record the canonical
  external-library `skill_root` command, not `scripts/project_adapt.py`, in the
  evidence row. Re-run the identical canonical command after repair.

## 4. Reduced regression fixtures needed

| Fixture | Minimal files | Required oracle |
|---|---|---|
| TypeScript `source` layout | `package.json` with a `test` script, `tsconfig.json`, `source/client.ts`, `test/client.test.ts` | language exactly includes TypeScript; `source` count 1; `test` absent; declared test command preserved; final report/evidence pass |
| Python pytest config | `pyproject.toml` with `[tool.pytest.ini_options]`, `src/library/__init__.py`, `tests/test_library.py` | exact pytest command; no command for a sibling negative fixture with only a pytest dependency string; final artifacts pass |
| Go arbitrary package | `go.mod`, root `router.go`, `middleware/auth.go`, `_examples/demo.go`, `middleware/auth_test.go` | root and `middleware` each counted once; examples/tests excluded; `go test ./...`; status/analysis complete |
| Java dual-wrapper no-regression | `pom.xml`, `build.gradle`, `mvnw`, `gradlew`, `src/main/java/example/App.java` | Java + both managers/markers + both wrapper test commands; framework list remains empty; analysis complete |
| Producer/provenance guard | Copy only `.claude/skills/adapt-project`, run its documented command, then gate | `adapter.yml == adapter.json` semantically, top-level `status`, expected `analysis`, all four files, and exact producer path captured by the test |

The first three are repair regressions. The Java case is a compact
no-regression/provenance case; current canonical Java behavior already passes.
Do not use `tests/test_project_adapt.py` alone as the repair oracle because it
imports the noncanonical shared helper.

## 5. Actual argparse, exit, and artifact contracts

### Installed/canonical `.claude/skills/adapt-project/scripts/discover.py`

Verified `--help` exit 0. There is no subcommand:

```text
discover.py [-h] [--project-root PROJECT_ROOT]
            [--artifact-root ARTIFACT_ROOT] [--timestamp TIMESTAMP]
            [--apply] [--no-host-write]
```

- defaults: project root = cwd; artifact root = project root;
- valid success: exit 0, stdout is exactly the absolute scan directory;
- argparse usage failure: exit 2;
- write/containment/timestamp `ValueError`: exit 2 with
  `error: status=failed: ...` on stderr;
- `--apply` and `--no-host-write` conflict: exit 2;
- dogfood artifact root inside project: exit 2;
- timestamp must form one safe `scan-<id>` path component;
- success writes JSON-compatible `adapter.yml`, byte-equivalent-payload
  `adapter.json`, `report.md`, and `evidence.json` under
  `<artifact-root>/reports/adapt-project/scan-<id>/`;
- `--apply` additionally writes `.engineering/project/adapter.yml`;
- `latest` must be a replaceable file/symlink and is replaced with a contained
  symlink; a nonreplaceable directory fails before a scan is claimed.

This producer includes top-level `status: complete` and Go/Java `analysis`.
Those fields are part of the guide's success claim.

### Evidence gate

Verified `--help` exit 0; `--scan-dir` is required. Actual returns from
`check_evidence.py`:

- 0 and stdout `adapt-project evidence OK`: correct skill, contained existing
  adapter/report declarations, and existing contained `adapter.json`;
- 1: absent/escaped manifest, wrong skill, absent evidence mapping, missing or
  escaped required evidence, or absent/escaped `adapter.json`;
- 2: argparse failure or unreadable/malformed evidence JSON.

The gate verifies closure/containment, not adapter schema, status, analysis,
producer identity, or equality of YAML/JSON. That is why it accepts legacy
helper artifacts that violate the installed skill's stronger success contract.

### Legacy `scripts/project_adapt.py`

Verified `--help` exit 0. It has five required subcommands:

```text
{discover,interview,evaluate,validate-adapter,validate-profile}
```

`discover` accepts the same five flags, but both roots default independently
to cwd. Success exits 0 and prints the scan path; caught `ValueError` exits 2
with `error: ...`; argparse/no-subcommand exits 2. `validate-*` returns 0 for a
shallow valid mapping, 1 for schema diagnostics, and 2 for read/parse errors.

Its discovery writer differs materially:

- PyYAML-styled `adapter.yml`, JSON `adapter.json`, report, and evidence;
- no top-level `status` or `analysis` at HEAD;
- `scan_dir.mkdir(..., exist_ok=True)` silently reuses/overwrites a scan id;
- `latest` replacement errors are swallowed because the timestamped directory
  is declared load-bearing;
- `TIMESTAMP_RE` is defined but never used; `scan_id` accepts arbitrary text,
  and `_scan_dir` performs no containment check. Do not port this artifact
  writer into the installed skill.

Observed error contract examples:

```text
project_adapt conflict: exit 2, stderr "error: --apply and --no-host-write are mutually exclusive"
installed conflict:     exit 2, stderr "error: status=failed: --apply and --no-host-write are mutually exclusive"
missing evidence scan:  exit 1, stderr "error: missing or escaped evidence.json"
```

The language-specific launchers under the adapt-project tree are separate
selected branches with provider-owned CLI/status contracts; the main portable
`discover.py` does not dispatch to them for these four hosts. They are not edit
anchors for this repair.

## 6. Pointer and artifact-drift audit

| Surface | Ground truth | Verdict |
|---|---|---|
| `SKILL.md:104-123` success | Names installed `scripts/discover.py`; requires four files, gate pass, and Go/Java status/analysis behavior | Canonical pointer |
| `SKILL.md:226-260` pipeline | Executes family-local `scripts/discover.py` then `scripts/check_evidence.py` | Canonical pointer |
| `scripts/project_adapt.py` docstring | Claims it is helper for `/adapt-project` and `/project-interview` | Stale: neither current guide points to it; both skills own family-local helpers |
| Original `19000*` adapter serialization | Block-style PyYAML; no `status`/`analysis`; helper-only `skills` key | Proven legacy-helper artifacts, not installed-skill artifacts |
| Original evidence manifests | Say only `"skill": "adapt-project"` and relative evidence paths | Insufficient provenance; gate passes the wrong producer |
| Original reports | Legacy report has no Source Roots section | Cannot satisfy Go/Java final-report count claim even when gate is green |
| `.claude/contracts/skills/adapt-project.yaml` | Says intent is Python/TS and evidence says `has_scripts=false / has_fixtures=false` | Stale: tree has many scripts/references and Go/Java/etc. contracts |
| Dart/Rust examples (`SKILL.md:84,181,188`) | `.agents/skills/on-demand/...` | Does not match router handoff, which points to external library `.claude/skills/...` |
| Main/default path (`SKILL.md:232,285`) | `.agents/skills/adapt-project` | Valid only after optional ambient selected-skill install; not the default external-library handoff |
| `latest` in validation dirs | Concurrently points to `19100*`, not original `19000*` | Drift; exact timestamp path is required evidence |

The current router topology's handoff builds `skill_root` from
`<external-library>/.claude/skills/adapt-project` and exposes its bundled
tooling. A real-repository journey should execute that returned root. Invoking
the repository-level helper bypasses the product architecture and creates a
false Go/Java blocker.

## 7. Load-bearing audit

| Surface/stage | Downstream consumer | Verdict |
|---|---|---|
| Portable `source_roots` | stack language inference, size caution, adapter, report | Load-bearing; Got and Chi gaps materially corrupt output |
| Portable `detect_stack` | command inference, `analysis`, adapter/report | Load-bearing |
| Portable `detect_commands` | adapter/report and C1 executable-command acceptance | Load-bearing |
| `adapter.yml` + `report.md` | declared evidence tokens and human handoff | Load-bearing |
| `adapter.json` | hard-required by `check_evidence.py` even though not declared as an evidence token | Load-bearing |
| `evidence.json` | final gate | Load-bearing for closure, but not semantic truth/provenance |
| top-level `status` / Go+Java `analysis` | explicit skill success and language final-artifact tests | Load-bearing; absent from helper output |
| timestamped scan directory | direct read/check and helper fallback if symlinks fail | Load-bearing |
| `latest` | convenience only; guide says pass exact path for prior shells | Not load-bearing and currently drifted |
| `scripts/project_adapt.py` discovery | its own legacy unit tests and ad-hoc validation command | Not load-bearing for the installed `/adapt-project` journey |
| specialized C/C++/C#/Dart/Kotlin/PHP/Ruby/Rust/Swift launchers | only exact manifest-selected language branches | Not load-bearing for this four-host generic discovery slice |
| `.claude/contracts/skills/adapt-project.yaml` | audits/metadata readers | Load-bearing as governance evidence, currently stale |

Existing canonical tests are the correct execution boundary:
`tests/test_adapt_project_typescript.py`,
`tests/test_adapt_project_go_g1.py`, and
`tests/test_adapt_project_java_j2a.py` invoke/copied-install the family-local
skill and prove final artifacts. `tests/test_project_adapt.py` imports
`scripts/project_adapt.py`; making only that suite green does not repair the
documented product.

## 8. Audit of the live unstaged repair shape

The concurrent changes contain useful canonical fixes (`source`, pytest
configuration, arbitrary Go package roots) and matching canonical regression
cases. Preserve those on the authoritative producer, subject to the command
configuration/setup caveat above.

The parallel expansion of `scripts/project_adapt.py` should not be treated as
proof of the same repair. It currently creates further schema/contract drift:

- helper Go manager `go-modules` vs canonical `go`;
- helper Spring inference vs canonical explicit no-framework claim;
- helper `test/` as a TypeScript source root vs canonical test exclusion;
- helper broad top-level counting without the canonical generated/vendor/test
  language predicates; and
- helper artifacts still lack canonical `status`/`analysis` and provenance.

The smallest responsible closeout is: fix and test the portable producer,
execute it by its exact routed `skill_root` on the four pinned hosts, gate the
exact timestamped scans, and record that command. Treat consolidation or
retirement of `scripts/project_adapt.py` as a deliberate follow-up unless it is
required to prevent the validation harness from choosing the wrong producer
again.
