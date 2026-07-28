# Stage 1 frame review: `adapt-project` on real repositories

## Review basis

This review separates two states explicitly:

- **Intake baseline:** commit `584688bb1ea82a98886509d108d25ad9ba60c89a` and the four `scan-20260727-19000*` artifacts. These are the artifacts that demonstrate the reported failures.
- **Current minimal repair:** the uncommitted working tree observed with `scripts/project_adapt.py` SHA-256 `6dcdcb85a7121ed2654a0a9356f22adc1b754a22e4e10701c4bdee224b79f2f9` and the four `scan-20260727-19100*` artifacts. This state fixes the headline stack/command/root omissions, but retains material contract defects described below.

The pinned inputs are Requests `414f0513c33883adf6f2b46901d4f0b38a455851`, Got `e3924aa1e53a6ca3eb93a43618ce532442a89b40`, Chi `8b258c7bb28f97a5f2a856ff7ef962578fec9215`, and Spring PetClinic `f182358d02e4a68e52bdbabf55ca7800288511e7` (`.claude/tasks/real-repository-corpus.json:4-35`).

I read the complete `adapt-project` tree, its Java reference, the frame-review rubric, the provider guides to which the skill delegates, and the provider-owned parsers needed to establish wrapper contracts. Every Python help invocation below was run with `.venv/bin/python`. PHP's entrypoint was run with `php`; `--help` is not a supported help mode and exits 64 with `options must be supplied as --name value pairs`.

## Actual CLI inventory

| Entrypoint | Actual contract from source plus `--help` |
|---|---|
| `scripts/project_adapt.py` | Required subcommand: `discover`, `interview`, `evaluate`, `validate-adapter`, or `validate-profile`. `discover`/`interview`: optional `--project-root`, `--artifact-root`, `--timestamp`, `--apply`, `--no-host-write`. `evaluate`: optional `--project-root`, required `--artifact-root`, optional `--reference`. Validators each take one positional path (`scripts/project_adapt.py:857-895`). |
| `scripts/check_evidence.py` | Required `--scan-dir` (`.claude/skills/adapt-project/scripts/check_evidence.py:34-37`). |
| `scripts/discover.py` | Optional `--project-root`, `--artifact-root`, `--timestamp`, `--apply`, `--no-host-write` (`.claude/skills/adapt-project/scripts/discover.py:763-770`). |
| `scripts/discover_c.py` | Required `--project-root`, `--output-dir`; optional `--clang`, `--make`, `--test-target`, `--smoke`; zero or more targets (`.claude/skills/adapt-project/scripts/discover_c.py:26-32`; provider-added options confirmed by help). |
| `scripts/discover_cpp.py` | Required `--project-root`, `--output-dir`; optional `--clangxx`; zero or more targets. The wrapper delegates all parsing to `_cpp/cpp_consumers.py` (`.claude/skills/adapt-project/scripts/discover_cpp.py:5-12`). |
| `scripts/discover_csharp.py` | Required `--project-root`, `--output-dir`; optional `--dotnet`; zero or more targets. Parsing is provider-owned (`.claude/skills/adapt-project/scripts/discover_csharp.py:5-12`). |
| `scripts/discover_dart.py` | Required `--project-root`, `--output-dir`, `--direct-test`, `--smoke-entrypoint`, `--expected-smoke`; optional `--dart` (`.claude/skills/adapt-project/scripts/discover_dart.py:28-33`; provider-added options confirmed by help). |
| `scripts/discover_kotlin.py` | Required `--project-root`, `--output-dir`; optional `--kotlinc`, `--java`; zero or more targets. Parsing is provider-owned (`.claude/skills/adapt-project/scripts/discover_kotlin.py:5-12`). |
| `scripts/discover_php.php` | Required name/value pairs `--project-root`, `--target`, `--output-dir`; optional `--php`, `--composer`, `--minimum-php`, `--minimum-composer` (`.claude/skills/adapt-project/scripts/discover_php.php:7-16`). |
| `scripts/discover_ruby.py` | Required `--project-root`, `--output-dir`; optional `--ruby`, `--bundler`, `--test`, `--smoke`; zero or more targets (`.claude/skills/adapt-project/scripts/discover_ruby.py:26-32`). |
| `scripts/discover_rust.py` | Required `--project-root`, `--output-dir`; optional `--rustc`, `--cargo`, `--rustfmt`; zero or more targets (`.claude/skills/adapt-project/scripts/discover_rust.py:26-32`). |
| `scripts/discover_swift.py` | Required `--project-root`, `--output-dir`, `--check-product`, `--expected-check`, `--smoke-product`, `--expected-smoke`; optional `--swift`, `--swiftc`, `--swift-format`; zero or more targets (`.claude/skills/adapt-project/scripts/discover_swift.py:28-34`; provider-added options confirmed by help). |

## Findings

### F1 — P0 — The completion gates prove file presence, not a useful or truthful adapter

**Class:** GOAL, LOAD-BEARING TEST, artifact-reality drift. **Baseline defect; still present after the minimal repair.**

The skill defines the adapter as the operational stack/commands/tests/CI/source-root half of project localization (`.claude/skills/adapt-project/SKILL.md:93-97`), but its generic success criteria are primarily four files plus an evidence mapping and a zero exit from `check_evidence.py` (`SKILL.md:104-118`). Only Go and Java receive semantic success clauses (`SKILL.md:119-123`); Python and JavaScript-family usefulness is not gated.

The evidence gate checks the manifest identity and that `adapter.yml`, `adapter.json`, and `report.md` exist beneath the scan directory; it never parses adapter content, checks status, compares the YAML/JSON payloads, or tests marker-to-stack/source/command invariants (`.claude/skills/adapt-project/scripts/check_evidence.py:34-62`). The repo-level validator is similarly structural: six top-level keys and two mapping types are sufficient (`scripts/project_adapt.py:703-714`). The repo-level adapter does not emit `status` or per-language analysis at all (`scripts/project_adapt.py:440-459`), despite the skill's atomic-status claim (`SKILL.md:125-129`).

This is demonstrated, not hypothetical: `check_evidence.py` and `project_adapt.py validate-adapter` both exited 0 for all four baseline `1900` scans. They accepted Chi with empty tests, roots, languages, markers, and package managers (`.../chi/.../scan-20260727-190003/adapter.json:8-52`), and PetClinic with empty tests/stack and a zero-language `src` row (`.../spring-petclinic/.../scan-20260727-190004/adapter.json:10-61`). Requests' empty test command (`.../requests/.../scan-20260727-190001/adapter.json:15-23`) and Got's empty roots/lint/setup (`.../got/.../scan-20260727-190002/adapter.json:8-15,75-90`) also passed.

**Execution failure:** the skill can report done on exactly the condition its deliverable exists to prevent: an adapter that gives the next agent no executable project workflow and omits obvious declared stack facts.

**Smallest responsible fix:** create one semantic adapter validator and make both `check_evidence.py` and `validate-adapter` call it. At minimum require (1) a declared status and per-language analysis status; (2) YAML/JSON semantic equality; (3) known root markers mapping to a language, marker, manager/build system, and source-role inventory; and (4) an executable test/build command or a specific `limitations` entry explaining why none can be named. For configured pytest/test scripts, a nonempty command must be required. The validator should fail the old `1900` artifacts. Do not add a real-repo-only oracle that leaves the ordinary completion gate unchanged.

### F2 — P0 — Two independent discovery engines claim one product contract

**Class:** FRAME, text/script alignment, workflow trap. **This caused the baseline failure and remains structurally unfixed.**

The installed skill's documented pipeline unconditionally executes `.claude/skills/adapt-project/scripts/discover.py` (`SKILL.md:221-260`). Real-repository validation instead exercised the shipped repo helper `scripts/project_adapt.py discover`, whose baseline stack detector recognized only Python and package.json-based JavaScript-family projects (`scripts/project_adapt.py@584688b:151-200`), whose command detector handled only Django and package scripts (`@584688b:203-229`), and whose roots counted only Python and TypeScript under a small fixed directory list (`@584688b:257-268`). That directly explains why the already-implemented Go/Java behavior in installed `discover.py` did not protect Chi or PetClinic.

The current minimal repair copies more heuristics into `project_adapt.py`, but the two contracts still disagree:

- Repo helper: one `javascript/typescript` language; installed helper: separate `typescript` and `javascript` labels (`scripts/project_adapt.py:188-203`; installed `discover.py:399-428`).
- Repo helper: `ts_files`, raw suffix counts, `go-modules`, React/Vite/Spring inference, YAML `adapter.yml`, and no status/analysis (`scripts/project_adapt.py:63-70,188-224,328-365,440-459,619-620`).
- Installed helper: `typescript_files` plus kind breakdown and `source_languages`, `go`, no Node/Java framework inference, JSON-compatible YAML, and atomic status/analysis (`discover.py:260-396,399-462,590-617,722-733`).

**Execution failure:** a fix/test can pass on one entrypoint while the user-visible sibling remains broken; downstream consumers see different schemas and claims for the same skill. The baseline is already one occurrence of this failure mode.

**Smallest responsible fix:** designate one discovery/domain module and one adapter schema as canonical. Make both CLIs thin wrappers over it, preserving only packaging/output-format differences. Run every adapter fixture and the four pinned real-repo oracles through both entrypoints and assert semantic equivalence. If the repo helper is not a supported `/adapt-project` entrypoint, remove or rename its `discover` surface and stop using it as product validation evidence; maintaining two products under one name is not a stable option.

### F3 — P1 — The current source-root repair restores directories by counting files the skill explicitly excludes

**Class:** SURVEY, false-positive source evidence. **Remaining current-tree defect.**

The skill's JavaScript-family contract excludes test descendants, declarations, generated/minified files, and `dist`/`build`/`generated`/`vendor` (`SKILL.md:131-146`). Its Go contract excludes tests, fixtures, dependencies, generated files, and canonical generated markers (`SKILL.md:148-163`). The Java reference likewise excludes build, generated, test, fixture, vendor, and symlinked source (`references/java.md:5-18`). Installed `discover.py` has language-specific predicates that implement these boundaries (`discover.py:127-241`).

The current repo helper instead maps suffixes and counts every matching regular file not under a short generic skip list (`scripts/project_adapt.py:63-86,328-365`). The new regression even requires `test/client.test.ts` to count as a TypeScript source root (`tests/test_project_adapt.py:112-121`), which codifies the opposite of the skill contract.

The repaired real artifacts expose the mismatch:

- Chi reports 10 root Go files and 49 under `middleware` (`.../chi/.../scan-20260727-191003/adapter.json:52-79`); the pinned tree contains only 5 and 30 respectively after excluding `*_test.go`.
- PetClinic reports 49 Java files under `src` (`.../spring-petclinic/.../scan-20260727-191004/adapter.json:51-60`); those are 30 under `src/main` plus 19 under `src/test`.
- Got reports all 52 files under `test` as a source root (`.../got/.../scan-20260727-191002/adapter.json:77-104`) even though the documented JavaScript-family source count excludes test descendants.

The generic top-level fallback will also admit `vendor`, `dist`, `build`, fixtures, and generated folders because those names are absent from `SKIP_PARTS` (`scripts/project_adapt.py:77-86,354-364`).

**Execution failure:** authored-source counts, large-root cautions, and candidate workflow roots become inflated or semantically ambiguous. A later maintenance skill can treat tests/generated/vendor content as production architecture.

**Smallest responsible fix:** reuse the installed helper's language-specific authored-source predicates instead of raw suffix counts. Preserve useful breadth by emitting separate role rows/counts (`source`, `test`, `example`, `generated`, `vendor`) rather than calling all of them `source_roots`. Add exclusions to the focused tests and pin the observed real counts above; do not merely assert that a directory appears.

### F4 — P1 — Command discovery does not survey declared workflows, so the repaired command closure is not proven executable

**Class:** SURVEY, HALLUCINATION-INVITED, execution usefulness. **Baseline omissions partly fixed; material current defect remains.**

The current code uses raw substring tests and conventional guesses (`scripts/project_adapt.py:247-300`). For Python it chooses `python3` when the host has no pre-existing `.venv`, then emits setup commands that create and populate `.venv` (`project_adapt.py:249-264`). Thus the emitted test command and emitted setup environment do not compose. It emits `ruff check` for every `pyproject.toml`, whether or not Ruff is configured (`project_adapt.py:265-268`). It recognizes pytest by any `pytest` substring rather than structured TOML (`project_adapt.py:254-259`). It inventories only CI filenames, not their declared commands (`project_adapt.py:368-373`).

For Requests, the repaired artifact now says `python3 -m pytest` after `.venv/bin/python -m pip install -e .` (`.../requests/.../scan-20260727-191001/adapter.json:15-26`). The pinned project explicitly declares `python -m pip install -r requirements-dev.txt` followed by `python -m pytest tests` in its Makefile (`requests/Makefile:2-5`), and its test dependency group contains pytest plus required plugins (`requests/pyproject.toml:58-68`). Installing only the editable package does not establish that test environment, and running system `python3` bypasses the venv just created.

Got's baseline empty setup was real and is repaired to `npm install`, while its `npm run test` commands were already correctly discovered. The remaining empty `lint` list is not, by itself, proof of a missing project command: Got's declared `test` script runs `xo` and `tsc --noEmit`, and it also declares `build`/`prepare` (`got/package.json:17-22`). The adapter currently has no way to report that composite verification coverage or the declared build command (`.../got/.../scan-20260727-191002/adapter.json:8-18`).

**Execution failure:** a consumer following setup then test can still fail for environmental reasons the adapter created; meanwhile an empty category is indistinguishable from “surveyed and no standalone command exists.” Conventional guesses can displace stronger project-owned commands.

**Smallest responsible fix:** establish a source-of-truth order and record provenance: explicit package scripts / structured `pyproject.toml` / Make or task-runner targets / wrapper commands / CI, then conventional fallback marked `inferred`. Keep setup and test on the same interpreter. For Requests, emit the project-declared dev/test closure or an exact dependency-group equivalent. Add a `build`/`check` facet (or structured verification facets) so Got can show that `npm run test` covers lint and typecheck without inventing a nonexistent `npm run lint`. Parse TOML/JSON structurally, and add a `limitations` reason when no command is found.

### F5 — P1 — Framework and sensitive-surface heuristics are presented as facts without evidence or confidence

**Class:** false positives, FRAME, text/script contradiction. **Baseline defect; expanded by the current repair.**

The skill explicitly says package metadata does not establish a Node framework (`SKILL.md:141-146`), and the Java reference says the adapter does not infer frameworks (`references/java.md:33-37`). The repo helper nonetheless scans raw package/build text and writes React, Vite/Vitest, or Spring directly into `stack.frameworks` (`scripts/project_adapt.py:196-203`). Current tests make those contradictory claims required (`tests/test_project_adapt.py:89-98,140-151`). A dependency or build plugin is objective declared evidence; an unqualified project-framework conclusion is a stronger claim.

The sensitive-surface detector applies an unbounded substring regex to the entire relative path (`scripts/project_adapt.py:71-75,388-402`). In baseline Got this labeled the `documentation/migration-guides` directory and three Markdown pages as sensitive alongside the genuinely security-relevant `strip-url-auth.ts` (`.../got/.../scan-20260727-190002/adapter.json:45-70`). `migration`, `key`, and `auth` can also match ordinary documentation or larger words, and noisy parent/child duplicates consume the 80-item cap.

**Execution failure:** the adapter raises false risk alarms and contradicts its own non-claims; low-value documentation matches can crowd out sensitive code. Framework labels can become accidental doctrine in `/project-interview` because the profile copies stack wholesale (`scripts/project_adapt.py:475-499`).

**Smallest responsible fix:** either keep `frameworks` empty for these families or rename the evidence to `declared_framework_markers` with path, declaration kind, and confidence; align tests and prose to that choice. Match sensitive terms as normalized path-segment/token rules with reason-specific categories, suppress or downgrade documentation-only migration matches, and deduplicate parent/child rows. Keep exact `.env` handling.

### F6 — P1 — The human report omits several load-bearing outputs, including source roots

**Class:** LOAD-BEARING TEST, reporting alignment. **Baseline defect; still present.**

The deliverable promise names stack, commands, tests, CI, source roots, docs, domain terms, sensitive surfaces, guardrails, and overlays (`SKILL.md:93-97`). The repo helper computes all of these (`scripts/project_adapt.py:440-459`) but `adapter_markdown` renders only stack, commands, sensitive surfaces, cautions, and open questions (`project_adapt.py:526-551`). It omits status, analysis/limitations, source roots and roles/counts, CI, docs, domain terms, guards, and overlays. The skill then tells the executor to read `adapter.yml` and `report.md` and surface high-confidence facts, but neither the report nor reply contract proves those omitted facts were inspected (`SKILL.md:247-263`).

**Execution failure:** even after the current repair, a user reading `report.md` cannot see that Got's `source/` was restored, cannot detect the overcounted test roots, and cannot tell which command was declared versus inferred. The reporting stage is therefore not load-bearing for much of the promised adapter.

**Smallest responsible fix:** render the validated canonical adapter's status, limitations, source-role inventory, command provenance, CI, and guard summary in `report.md`. Require the final reply to name the scan path plus the exact language, root, command, and limitation values it is accepting. This makes the mandated read/surface stage observable rather than ceremonial.

### F7 — P1 — The advertised multi-language skill has no single dispatch path, and most specialized branches cannot honor dogfood mode

**Class:** WORKFLOW TRAP, text/script alignment, unexecutable-against-reality. **Current tree defect outside the initial four-language slice.**

The frontmatter advertises fourteen scanned languages and one `--apply|--no-host-write` form (`SKILL.md:1-34`), while the only numbered pipeline always invokes general `scripts/discover.py` (`SKILL.md:221-260`). That general script recognizes only Python, JavaScript, TypeScript, Go, and Java (`discover.py:399-462`). The other languages require the executor to notice prose branches and manually substitute separate wrappers; there is no stage-0 marker dispatch, ambiguity rule, or back-edge when the general result is empty.

Those wrappers do not share the dogfood contract. C, Ruby, and Rust reject `--output-dir` outside the project (`discover_c.py:33-38`; `discover_ruby.py:33-38`; `discover_rust.py:33-38`). C++, C#, and Kotlin use provider helpers with the same inside-project restriction (`_cpp/cpp_consumers.py:47-53,72-82`; `_csharp/csharp_consumers.py:47-53,72-82`; `_kotlin/kotlin_consumers.py:49-55,74-84`). Dart requires artifacts under host `reports/` (`_dart/dart_project_snapshot.py:92-113`); Swift rejects artifacts outside the host (`_swift-project-lexical/swift_project_facts.py:101-114`); PHP requires output inside the project (`_php-project-lexical/php_project_lexical.php:102-121`). None exposes `--no-host-write`. This conflicts with the general claim that dogfood artifacts stay outside the evaluated host (`SKILL.md:280-296`).

Specialized command schemas also vary (`lint` versus `check`, `format`, `compile`, `smoke`), and several insert non-command prose such as `native test not supplied` into command arrays (`discover_ruby.py:74-81`). `check_evidence.py` ignores specialized manifest status, so a partial/failed artifact closure can still pass F1's gate.

**Execution failure:** `/adapt-project --no-host-write` is deterministic for only the general five-language path. On an advertised external language, the executor must improvise and either runs the wrong scanner or writes into the host. There is no uniform downstream command/status contract.

**Smallest responsible fix:** add an explicit marker-based dispatch stage that selects one entrypoint/provider closure, refuses ambiguous/unsupported cases with an exact limitation, and normalizes artifact root, status, evidence, and command facets. Give every branch the same external artifact/no-host-write contract. Until that exists, narrow the advertised `scans` and no-host-write claim to the general scanner and label the other wrappers as separately invoked experimental closures.

### F8 — P1 — Repo-helper scan IDs are not validated or contained despite a defined regex

**Class:** host-write safety, artifact-reality drift. **Current tree defect.**

`TIMESTAMP_RE` is defined but never used (`scripts/project_adapt.py:34-36`). `scan_id` accepts arbitrary text including path separators (`project_adapt.py:93-98`), `_scan_dir` concatenates it without resolution/containment (`project_adapt.py:590-591`), and `write_discovery` creates that path (`project_adapt.py:606-621`). The installed scanner already has the correct model: one safe `scan-<id>` component plus resolved containment checks (`discover.py:90-106,693-712`). Current tests exercise only safe fixed timestamps (`tests/test_project_adapt.py:165-180`).

**Execution failure:** a crafted `--timestamp` can escape the expected `reports/adapt-project` directory, undermining the stated artifact containment guarantee even in `--no-host-write` mode.

**Smallest responsible fix:** use the existing regex (prefer the installed scanner's safe-component regex), reject separators/traversal, resolve the final scan path, and require its parent to be the resolved reports root before creating it. Add refusal tests for `../`, absolute-looking, overlong, and symlinked paths.

### F9 — P2 — `evaluate` reports success and “no false inference” without an oracle

**Class:** HALLUCINATION-INVITED, ceremonial reporting. **Current tree defect.**

Unless `--reference` contains the hard-coded string `host-a`, `evaluate_dogfood` has no expectations. It then states that stack/docs/source-root discovery completed, that no false inference was mechanically identified, and that no required marker was missing (`scripts/project_adapt.py:729-778`). The test asserts only section headings (`tests/test_project_adapt.py:240-250`). The baseline Chi/PetClinic adapters could therefore receive a reassuring evaluation even though their stack and commands were empty.

**Execution failure:** a product-evaluation command can generate affirmative prose with no acceptance oracle, exactly the assertion-without-action pattern in the frame rubric.

**Smallest responsible fix:** require an expectation set (at least expected language and required command class), feed it through the semantic validator from F1, and report observed values plus pass/fail evidence. If no oracle is supplied, label the output `unassessed` and do not emit “completed,” “none identified,” or “no marker missing.”

## Load-bearing stage audit

| Mandated stage | Consumed downstream? | Assessment |
|---|---|---|
| Resolve project/artifact roots | Yes, by discovery | Load-bearing and generally sound; external-root refusal works in both general entrypoints (`scripts/project_adapt.py:140-144`; installed `discover.py:693-704`). |
| Run discovery | Yes, artifacts feed report/gate | Load-bearing, but entrypoint ambiguity in F2/F7 means the executed product is not stable. |
| Read `adapter.yml` and `report.md` | Nominally by final surfacing | No observable proof; report omits major promised facts (F6). |
| Surface facts/cautions/sensitive surfaces/questions | Only the final reply | No acceptance schema or provenance requirement; easy to satisfy narratively. |
| Run `check_evidence.py` before done | Yes, controls the done claim | Mechanically wired but semantically non-load-bearing because it checks only file closure (F1). |
| Read Java/provider guides | Not consumed by an artifact or gate | Hallucination-invited. A selected branch should record provider/version/boundary in `analysis` rather than rely on an asserted read. |
| Replay fixture/native checks | Used in development, not runtime | Valuable, but they protect installed branch implementations, not the duplicate repo helper that failed on real hosts (F2). |

## What works

- The frame separating objective repository facts from human intent is strong and repeated near the standardization decision: `SKILL.md:93-102,298-304`. The generated profile also keeps `user_approved: false` and explicit interview questions (`scripts/project_adapt.py:475-523`).
- The general no-host-write guard correctly rejects artifact roots inside the target (`scripts/project_adapt.py:140-144`; installed `discover.py:693-704`). The real scans were written outside the pinned repositories.
- Installed `discover.py` has careful JavaScript-family, Go, and Java authored-source predicates and explicit non-claims (`discover.py:127-241`; `SKILL.md:131-169`). Those are the right primitives to reuse in F3.
- `check_evidence.py` safely rejects absolute paths, `..`, missing targets, and evidence symlink escapes (`check_evidence.py:11-31`). Its containment work is useful even though its semantic gate is incomplete.
- The current minimal repair does restore the four headline baseline omissions: the `1910` artifacts now identify Requests/Python with a test command, Got's `source/` and setup, Chi's Go marker/manager/commands, and PetClinic's Java/build markers/test commands. Focused `tests/test_project_adapt.py` passed `13 passed in 0.12s`.
- All Python wrapper help contracts are executable in the repo venv, and the specialized providers generally record status, native evidence, source preservation, and bounded non-claims. Their remaining problem is orchestration/normalization, not an absence of useful language work.

## Repair order

1. F1 and F2: one canonical schema/detector and a semantic completion gate that fails all four `1900` scans.
2. F3 and F4: preserve the current headline detections while making source roles and command closures truthful/executable.
3. F5 and F6: remove unqualified false inferences and make the report carry the facts the user must accept.
4. F7 and F8: normalize advertised branch execution and close the host-write safety gap before broader real-repository claims.
5. F9: make evaluation evidence-backed or explicitly unassessed.
