# Language-support development

Status: durable contributor guide synthesized after TypeScript, JavaScript,
Go, and Java coverage

Use this guide before starting another language or changing shared
language-analysis tooling. It captures the tooling shape that repeated across
the completed ports without treating language semantics as interchangeable.
Per-skill evidence remains under
`.claude/tasks/multilanguage-learnings/`; this file is the durable reusable
entry point.

## Sources of truth and working records

- `.claude/tasks/language-support-and-productization-execution-plan.md` is the
  sole active execution ledger for unfinished installation and language work.
- This file owns the reusable development contract and native-tooling
  selection principles.
- `.claude/tasks/multilanguage-skill-matrix.json` owns current per-skill
  language capability claims.
- `.claude/tasks/multilanguage-typescript-transfer-guide.md` and
  `.claude/tasks/multilanguage-learnings/` retain completed-port evidence.
- `.claude/tasks/multilanguage-support-backlog.md` owns proposed follow-ups and
  their promotion triggers.
- `.claude/tasks/cross-language-tool-evaluation-plan.md` retains bounded tool
  experiment results; it is evidence, not the current contributor entry point.
- `.claude/skills/_common/portability-roadmap.md` describes the longer-term
  core/language/framework/repository layering direction.

## Boundary learned from completed ports

Share the mechanics that every language adapter must perform. Keep the facts
that establish a skill's final claim native to the language and local to the
relevant contract family.

The reusable layers are:

1. source discovery and role classification;
2. native-tool discovery, version checks, and offline preflight;
3. process execution, batching, terminal status, and artifact lifecycle;
4. source manifests, fingerprints, and proposal-to-source lineage;
5. copied/on-demand closure resolution; and
6. conformance fixtures that prove the documented user command.

Do not create one universal AST, symbol, call-graph, proposal, or rewrite
schema. Java confirmed that lexical/filesystem, syntax, semantic/project, and
proposal/guard are useful contract cohorts, but their facts and final artifacts
are not one stable interface.

## The language-support kit

### 1. Declarative language profile

One small profile per language should declare:

- suffixes and project/build markers;
- source, test, generated, vendor, declaration, migration, configuration, and
  tooling conventions;
- available lexical, syntax, semantic, and proposal/rewrite providers;
- native verification commands and offline flags;
- minimum tool versions and resolution order;
- complete, partial, unsupported, and failed boundaries; and
- supplementary framework profiles, when selected explicitly.

The source inventory, capability matrix, router support explanation, and
future `--help` output should be generated from this source of truth. Static
suffix tables in individual tools are transition code, not another authority.

### 2. Toolchain doctor

A read-only doctor should locate project-local tools before system tools,
report exact versions, and emit normalized capabilities. It must distinguish:

- available and supported;
- available but too old;
- unavailable;
- available only for syntax or project facts; and
- present but unusable for this repository because required project metadata
  is absent, such as a C/C++ compilation database.

The doctor may print install guidance. It must not silently install compilers,
analyzers, language servers, or dependencies into a user's project. Development
bootstrap and product execution are separate concerns: contributors may use a
pinned setup/cache, while routed skills should prefer tools already owned by
the host project.

### 3. Narrow provider contracts

Providers implement only the fact tiers they can support honestly:

- **inventory:** files, roles, exclusions, roots, and project units;
- **syntax:** declarations, imports, direct calls, comments, branches, and
  source spans;
- **semantic:** resolved symbols, references, types, call targets, and project
  graph edges; and
- **proposal/rewrite:** resolved edit spans, preconditions, compatibility
  impact, native verification, and rollback obligations.

A provider may return `partial` or `unsupported` for a higher tier while still
providing a useful lower tier. Consumers own their final report/proposal/diff
schema; providers do not claim that syntax facts prove semantic outcomes.

### 4. Shared execution and artifact lifecycle

The reusable runner should own tool probing, batched file input, timeout and
exit propagation, atomic output, stale-artifact removal, source fingerprints,
and terminal status. It must prove valid-to-failed and failed-to-valid reruns at
the same destination so an old clean report cannot survive a failed analysis.

Keep the runner small enough to copy into an exact on-demand closure. Do not
make selected skills depend on an undeclared repository runtime.

### 5. Conformance harness and scaffolder

Every language/provider tier should be tested against the same outer contract:

- positive, clean, malformed, and tool-missing/old fixtures;
- first-party, test, generated, vendor, build, declaration, and symlink roles;
- source-root and multi-project boundaries;
- exact documented commands from each supported copied layout;
- same-destination terminal-state transitions;
- native build/test/analysis obligations; and
- one representative input reaching the skill's final artifact or mutation
  boundary.

A scaffolder may create a profile, provider skeleton, fixture roster, and test
stubs. It must not generate a semantic implementation or mark a language
supported before the final-outcome checks pass.

### 6. Batched fact production

When several read-only skills need genuinely identical native facts, run the
provider once per project snapshot and let family consumers read a
content-addressed bundle keyed by source manifest, provider version, and
options. Preserve each consumer's independent outcome and failure status.

Do not batch mutations. Do not introduce a cache or shared provider until two
real consumers demonstrate identical facts and a measured reduction in total
adapter-plus-test cost.

## Native foundations for queued languages

| Language | Preferred foundations | Honest boundary |
|---|---|---|
| PHP | native `php -l`; PHP Parser or the bounded tree-sitter pack for syntax; project-local PHPStan/Psalm for semantics | Composer/project configuration controls semantic completeness |
| Ruby | Prism and `ruby -c`; project-local Sorbet or Steep when already configured | dynamic reference/type claims otherwise remain partial |
| C# | Roslyn plus `dotnet build --no-restore` | strong syntax, semantic, and rewrite support requires a pinned .NET SDK/project graph |
| Rust | `cargo metadata`, `cargo check`, Clippy; rust-analyzer for bounded reference operations | prefer stable Cargo JSON/LSP boundaries over private compiler APIs |
| Swift | SwiftSyntax, SourceKit-LSP, and SwiftPM | indexed cross-module facts may require a recent build |
| Dart | analyzer/Analysis Server plus `dart analyze` and native tests | pin to the SDK and treat analyzer API churn explicitly |
| Kotlin | compiler/Gradle first; Analysis API selectively; KSP for declaration-only work | do not use KSP for expression/call semantics; standalone semantic support may remain partial |
| C/C++ | Clang/LibTooling or clangd plus native build/test commands | project semantics are partial without trustworthy compile commands |

Use established language and framework analyzers instead of reproducing their
checks. Idiom/best-practice profiles should name and invoke tools such as
Clippy, PHPStan, RuboCop, or native compiler analyzers where appropriate; the
skill ecosystem should add orchestration, interpretation, and final-outcome
contracts rather than reimplementing them.

## Promotion gate

Before using the kit for a broad language pass, prove it on two materially
different ecosystems: PHP is the first syntax/dynamic-language pilot, and C#
is the preferred typed semantic/rewrite pilot once the .NET SDK is available.

Promote a shared component only when:

- at least two real consumers use the same contract;
- callers no longer need to know tool-resolution, lifecycle, or source-role
  policy;
- durable tests exercise the public interface and final outcome;
- copied closure completeness remains explicit; and
- the ML-025 comparison reduces maintained adapter-plus-test LOC by at least
  25% without increasing closure size or median latency by more than 10%.

Stop and keep the implementation family-local when reuse would normalize
incompatible semantic schemas, hide partial/unsupported states, require
ambient network downloads, or save little once fixture and closure code is
counted.

## Work packet for a language lane

Give a fresh non-context worker only:

- project root and explicit runtime/tool paths;
- the target language profile and contract tier;
- owned skills/files and forbidden shared surfaces;
- final artifacts and negative boundaries to preserve;
- exact on-demand closure and native verification commands;
- conformance/benchmark commands; and
- a required learning packet describing what generalized, what did not, tool
  acquisition/setup, reusable facts, and guidance for the next language.

Shared skill-family integration, router/matrix publication, and cross-language
regression remain serial root-owned work. Framework support begins as a
supplementary profile after the underlying language contract is honest.
