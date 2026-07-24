# Language-support development

Status: durable contributor guide synthesized through TypeScript, JavaScript,
Go, Java, PHP, Ruby, Swift, Rust, and Dart evidence

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
- `.claude/tasks/shared-kit-promotion-decision.md` records the accepted reuse
  decisions and the frozen family-packet index.
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
3. the narrow execution and artifact mechanics that clear the measured reuse
   gate;
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

### 4. Execution and artifact lifecycle

The accepted cross-language foundation currently shares only atomic source-
inventory output. Tool probing is shared through profiles and the read-only
doctor. Stale-artifact removal, source fingerprints, terminal status, and
mutation rollback remain language/skill-family local because the completed
ports have different schemas and no broader component passed the conjunctive
LOC, closure, and latency gate.

Every family must still prove valid-to-failed and failed-to-valid reruns at the
same destination so an old clean report cannot survive a failed analysis.
Extract another mechanic only after two real consumers demonstrate the exact
same contract and all promotion metrics pass. Keep every selected closure
explicit; do not make a skill depend on an undeclared repository runtime.

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

### 7. Cohort A project/lexical evidence

PHP, Ruby, and Swift independently confirmed the same narrow implementation
shape: one language-local external-library provider can own source roles,
native preflight, fingerprints, and terminal lifecycle while each skill keeps
its own final artifact and claim. All three providers cleared ML-025 by more
than 57% maintained LOC, stayed inside the 10% closure/latency caps, and remain
local to their language and immediate consumers. This is evidence for the
family pattern, not for a cross-language runtime or result schema.

The language-specific facts still matter:

- PHP uses Composer validation, per-file `php -l`, and
  `token_get_all(..., TOKEN_PARSE)`; Composer/framework semantics remain a
  later project-aware tier.
- Ruby uses frozen Bundler checks, per-file `ruby -c`, and bundled Prism;
  reopening, dynamic load/dispatch, metaprogramming, Rails, and Zeitwerk remain
  semantic boundaries.
- Swift uses restrictive SwiftPM commands, per-file `swiftc -frontend -parse`,
  strict Swift Format, and explicit direct-check/smoke products. Parse files
  independently: combining multiple executable `main.swift` files in one
  compiler invocation creates a false conflict.

Implementation sharing is not request-level batching. Each current adapter
invokes its provider and native gates for one skill outcome; a multi-lens
request still repeats those costs. Do not claim the user-journey batching
problem is solved until a later measured coordinator reuses one content-bound
snapshot across independent read-only consumers without weakening their final
statuses. The current external-library closure is the honest prerequisite for
that experiment, not the experiment itself.

### 8. Cohort A syntax evidence

The syntax wave preserved language ownership instead of forcing one parser
contract across PHP, Ruby, and Swift. PHP and Ruby use separate on-demand
syntax providers because their token and Prism fact boundaries differ from
their project/lexical providers. Swift extends its existing project/lexical
provider because the same compiler-validated source inventory owns both fact
sets. Detailed commands and non-claims live in the three provider `GUIDE.md`
files rather than every ambient consumer skill.

The measured provider-versus-literal-consumer comparisons passed the retained
ML-025 gates: PHP reduced maintained LOC by `56.55%` with `0%` closure growth
and `+3.70%` median latency; Ruby reduced LOC by `57.91%` with `0%` closure
growth and `+1.068%` median latency; Swift reduced LOC by `45.53%` with `0%`
closure growth and `+2.81%` aggregate latency (its consumer median improved by
`0.75%`). These results justify language-local reuse only. The providers expose
syntax candidates and explicit unresolved boundaries; they do not establish
semantic identity, behavioral equivalence, refactor safety, or request-level
batching.

### 9. Cohort A semantic evidence

PHP and Ruby now have accepted language-local semantic tiers for five
read-only consumers. PHP freezes exact Composer PSR-4 ownership and direct
declared relationships; it remains visibly partial when a configured
PHPStan/Psalm pair is incomplete and never substitutes token matches. Ruby
requires project-authored RBS and uses Prism only for spans and explicit
dynamic boundaries. Projects without authored RBS remain partial rather than
receiving inferred Ruby semantics.

Both providers retain distinct consumer artifacts and hash-bound human
authority. PHP reduces maintained LOC by `62.65%` with negligible closure
growth and a `0.55%` median improvement. Ruby reduces maintained LOC by
`58.76%`, the union closure by `62.39%`, and median repeated-provider latency
by `78.22%`. These economics justify only the two language-local providers.

Swift A3 is not accepted. Its worker evidence passed, but root replay timed out
in a cold/repeated SourceKit-LSP `documentSymbol` path after 360 seconds. A
bounded diagnosis then proved that initialization, explicit indexing, forced
SwiftPM workspace selection, and a readiness wait still produced no response
to the first semantic request under the installed Command Line Tools. The
4,535-line unpublished candidate was removed from `main` and retained on its
language branch for reference. Keep the five rows pending until a different
working semantic foundation—such as a verified full-Xcode SourceKit path or a
bounded SwiftSyntax-based provider—reaches the final artifacts. A passing warm
benchmark does not override a non-reproducible user journey.

### 10. Cohort A accepted-evidence consumers

PHP and Ruby now consume accepted producer evidence for five downstream
outcomes: enum proposal, exact-field regression guard, boundary proposal,
folder proposal, and shadow-unification proposal. These consumers never rerun
detection. Each validates current source and human authority, preserves the
upstream limits, owns a distinct terminal artifact, and treats safe defer,
keep-flat, cohesive, or keep-separate as legitimate completed outcomes.

The PHP helper saves `44.59%` maintained LOC with `0%` closure growth and
`+3.50%` median latency. The Ruby helper saves `43.37%` maintained LOC and
`52.78%` runtime-closure LOC, with a `3.37%` median improvement. Keep both
helpers language-local: Composer/PSR-4 identity and RBS/dynamic Ruby authority
are not one portable evidence schema. Guards are staged and verified but not
installed; proposals remain read-only and require separate mutation approval.

### 11. Ruby mutation evidence

Ruby reaches all 22 bounded language outcomes with one self-contained
`move-path` adapter rather than another shared rewrite platform. The accepted
shape requires explicit old/new constant identity, Prism-attributed static
edits, content-addressed preview approval, per-file syntax, frozen Bundler,
native test/smoke, exact after-tree verification, and full rollback. Unrelated
dynamic Ruby is preserved; dynamic loading or reflection involving the moved
identity refuses. Reuse this transaction shape selectively, but keep each
language's identity and native-verification rules local.

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

The accepted P6 decision is recorded in
`.claude/tasks/shared-kit-promotion-decision.md`. PHP, Rust, and Dart supplied
the materially different evidence that the initial TypeScript/Java comparison
lacked. C# remains a required final language, not a prerequisite for retaining
the already-proven narrow foundation.

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

Start with the family-packet index in
`.claude/tasks/shared-kit-promotion-decision.md`; do not reconstruct completed
family contracts from repository archaeology.

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
