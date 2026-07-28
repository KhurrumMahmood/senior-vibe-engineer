# engineering-skills

`engineering-skills` is a senior-engineer skill ecosystem for AI coding agents.
It helps agents choose the right engineering workflow, inspect architectural
debt, refactor deliberately, record material decisions, and turn recurring
problems into tests or guardrails.

The public repository is named `senior-vibe-engineer`; `engineering-skills` is
the ecosystem and command-facing product name.

The default installation is intentionally small:

1. `which-shape` chooses the overall workflow.
2. `which-skill` chooses the most relevant tactical skill.
3. `which-cleanup` reviews recent work and recommends proportionate closeout.

Only those three routers enter the agent's normal skill discovery. The other 73
skills and their tools live in a project-scoped external library and are loaded
only when a router selects them. For non-trivial work, the router recommends a
fresh non-context sub-agent with only the selected guide/tool closure.

The current copy/paste installation journey is verified for **Codex**. The
repository also contains instruction adapters for Claude Code, Augment, Cursor,
and Gemini, but equivalent public installer journeys for those agents are not
yet claimed as verified.

## Requirements

- Git
- Node.js with `npm`/`npx`
- Python 3.11 or newer
- A host project under Git

Selected skills may also need the host language's compiler, analyzer, package
manager, or test runner. Router output reports those requirements and explicit
slow/manual/unsupported paths rather than pretending that an unavailable tool
ran.

## Install in a Codex project

Run these commands from the host project's root:

```bash
ENGINEERING_SKILLS_SOURCE=https://github.com/KhurrumMahmood/senior-vibe-engineer # host-ref-allow: public distribution repository

# Install exactly the three routers into Codex discovery.
DO_NOT_TRACK=1 npx --yes skills@1.5.19 add \
  "$ENGINEERING_SKILLS_SOURCE" \
  --skill which-shape --skill which-skill --skill which-cleanup \
  --agent codex --copy -y

# Materialize the other 73 skills and their tools outside agent discovery.
# This also creates/verifies a Python >=3.11 venv with pinned dependencies.
python3 .agents/skills/which-skill/scripts/bootstrap_library.py \
  --project-root "$PWD" --source "$ENGINEERING_SKILLS_SOURCE"

# Confirm router bytes, library HEAD, and toolkit-owned host-state schema agree.
python3 .agents/skills/which-skill/scripts/status.py --project-root "$PWD"
```

The external library defaults to:

```text
<project-parent>/.engineering-skills/<project-name>
```

It is outside both the target repository and standard skill-discovery roots.
The routers expose the selected library paths and the library's exact
`.venv/bin/python`; delegated work does not need shell activation.

The repository currently publishes from the moving `main` branch and does not
yet have a tagged stable release. Run `status.py` after installation or update;
it fails visibly when the installed routers and library do not describe the
same revision.

## First use

The routers are advisory. They do not initiate the proposed workflow, execute a
selected skill, install additional ambient skills, or modify project source.

Ask the agent in natural language:

- "Use `which-shape` to decide how to approach this inherited TypeScript repo."
- "Use `which-skill` to choose the right skill for repeated status literals."
- "Use `which-cleanup` to review the changes I just made, using diff-line
  scope where it is honest."

For a non-trivial recommendation, ask the agent to follow the returned
on-demand handoff in a fresh non-context sub-agent. Independent read-only lenses
may run concurrently; mutations and final verification remain serial.

Each router also has non-executing help:

```bash
python3 .agents/skills/which-shape/scripts/route.py --help
python3 .agents/skills/which-skill/scripts/match.py --help
python3 .agents/skills/which-cleanup/scripts/route.py --help
```

Direct examples:

```bash
# Overall workflow
python3 .agents/skills/which-shape/scripts/route.py \
  "unknown inherited Java project; where should I start?" \
  --project-root "$PWD"

# One tactical skill
python3 .agents/skills/which-skill/scripts/match.py \
  "find dead code in this Rust crate" \
  --language rust --project-root "$PWD"

# Closeout of the current Git changes
python3 .agents/skills/which-cleanup/scripts/route.py \
  --scope-mode diff-lines --project-root "$PWD"
```

Use `--json` for machine-readable router output. `which-cleanup` additionally
accepts explicit paths, `--staged`, `--changed-from REF`, `--commit SHA`, and
`--range A..B`. Its `--scope-mode` distinguishes changed-line findings,
whole-changed-file analysis, explicit paths, and project-level obligations.

Router JSON also exposes `capability_inventory_tool`. Use it before adding a
new first-party service, helper, module, or package:

```bash
LIBRARY_ROOT="$(dirname "$PWD")/.engineering-skills/$(basename "$PWD")"

# Read-only lookup across the languages present in the host project.
"$LIBRARY_ROOT/.venv/bin/python" \
  "$LIBRARY_ROOT/scripts/capability_inventory.py" \
  --project-root "$PWD" --stdout

# Or generate .engineering/docs/capability-inventory.md for later lookup.
"$LIBRARY_ROOT/.venv/bin/python" \
  "$LIBRARY_ROOT/scripts/capability_inventory.py" \
  --project-root "$PWD"
```

Descriptions are harvested from source documentation. Static `Used by`
counts are bounded local-reference evidence, not runtime usage or reachability;
unsupported attribution remains visibly unavailable.

## Update, repair, and migrate

The stock skill installer owns the three router directories. Git owns the
external library. Toolkit-owned host-state migrations are a separate explicit
operation; there is deliberately no second package manager.

Until a tagged release exists, update to current `main` from the host project:

```bash
ENGINEERING_SKILLS_SOURCE=https://github.com/KhurrumMahmood/senior-vibe-engineer # host-ref-allow: public distribution repository
LIBRARY_ROOT="$(dirname "$PWD")/.engineering-skills/$(basename "$PWD")"

# Update the external library and its pinned runtime.
git -C "$LIBRARY_ROOT" pull --ff-only
python3 "$LIBRARY_ROOT/.claude/skills/which-skill/scripts/setup_runtime.py" \
  --project-root "$LIBRARY_ROOT" --no-hooks

# Replace the three router copies through their owning installer.
DO_NOT_TRACK=1 npx --yes skills@1.5.19 add \
  "$ENGINEERING_SKILLS_SOURCE" \
  --skill which-shape --skill which-skill --skill which-cleanup \
  --agent codex --copy -y

python3 .agents/skills/which-skill/scripts/status.py --project-root "$PWD"
```

If the library was bootstrapped with `--library-root`, set `LIBRARY_ROOT` to
that exact path instead of the default above.

If the library is missing, a normal router invocation prints an exact bootstrap
command without executing it. If the library path exists but is incomplete,
move or remove that specific incomplete directory only after reviewing it, then
rerun `bootstrap_library.py`; bootstrap never overwrites an ambiguous existing
destination.

If status reports pending toolkit-owned host-state migrations, preview before
applying:

```bash
LIBRARY_ROOT="$(dirname "$PWD")/.engineering-skills/$(basename "$PWD")"

"$LIBRARY_ROOT/.venv/bin/python" "$LIBRARY_ROOT/scripts/host_migrations.py" \
  --project-root "$PWD" status
"$LIBRARY_ROOT/.venv/bin/python" "$LIBRARY_ROOT/scripts/host_migrations.py" \
  --project-root "$PWD" plan

# Mutating boundary: run only after reviewing the plan.
"$LIBRARY_ROOT/.venv/bin/python" "$LIBRARY_ROOT/scripts/host_migrations.py" \
  --project-root "$PWD" apply

python3 .agents/skills/which-skill/scripts/status.py --project-root "$PWD"
```

The migration runner changes only declared toolkit-owned `.engineering/`
paths. It does not fetch code, update routers, install dependencies, or rewrite
project source.

## Uninstall

Remove only this ecosystem's three ambient routers from the host project,
never from the engineering-skills source checkout:

```bash
DO_NOT_TRACK=1 npx --yes skills@1.5.19 remove \
  which-shape which-skill which-cleanup -y

DO_NOT_TRACK=1 npx --yes skills@1.5.19 list --json
```

Do not substitute `remove --all`: it removes every skill the CLI discovers for
every agent target, including unrelated skills. At `skills@1.5.19`, explicit
removal may retain prior `skills-lock.json` entries as restoration metadata;
`skills list --json` is the installed-state check and should return `[]`.

The external library, toolkit-owned `.engineering/` state, and user project
files are separate scopes. Uninstalling routers intentionally leaves them
alone. Review and remove the exact external-library directory separately only
if it is no longer needed.

## Current capability model

The ecosystem contains 76 skills in four different portability classes. The
classes matter more than a single headline count:

| Class | Count | Meaning |
|---|---:|---|
| Validated-neutral | 19 | The skill contract does not need language-specific implementation. |
| Language-level | 22 | Each selected language has a separately evidenced bounded implementation for these engineering jobs. |
| Framework-bound | 22 | The skill is intentionally tied to a framework or stack; language support alone does not make it eligible. |
| Ecosystem-runtime | 13 | The skill maintains or governs this toolkit rather than a host-language codebase. |

Python/Django is the ecosystem's original host and remains visible in the lint
substrate and examples. Implementation coverage and real-project validation
are separate claims:

| Language | Implementation coverage | Real-project validation | Important non-claims or prerequisites |
|---|---|---|---|
| Python | Original host contract | journey-validated | The pinned journey uses Requests rather than claiming every Python framework. |
| TypeScript | 22/22 language-level outcomes | journey-validated | Project-local TypeScript configuration and tools govern semantic completeness. |
| JavaScript | 22/22 language-level outcomes | journey-validated | JavaScript and TypeScript remain distinct routing contexts. |
| Go | 22/22 language-level outcomes | journey-validated | Uses Go-native project, syntax, semantic, test, and move evidence. |
| Java | 22/22 standalone-JDK outcomes | journey-validated | Does not imply Spring, Android, or arbitrary build-tool variants. |
| PHP | 22/22 bounded outcomes | journey-validated | Composer and configured PHPStan/Psalm boundaries control project semantics. |
| Ruby | 22/22 bounded outcomes | journey-validated | Dynamic loading/metaprogramming stays explicit; authored RBS is required for selected semantic claims. |
| Swift | 22/22 bounded outcomes | journey-validated | Real SwiftPM packages may yield useful partial syntax evidence; no Xcode/framework or whole-program claim. |
| Rust | 22/22 bounded outcomes | journey-validated | Uses Cargo/rustc and bounded rust-analyzer facts where appropriate. |
| Dart | 22/22 bounded outcomes | journey-validated | Uses the Dart SDK/analyzer boundary; Flutter is separate. |
| C | 22/22 bounded outcomes | journey-validated | Semantic claims require Clang 21+ and a trustworthy current C17 `compile_commands.json`. |
| C++ | 22/22 bounded outcomes | journey-validated | Semantic claims require Clang 21+, C++20, and a trustworthy current compilation database; no general ABI/ODR claim. |
| Kotlin | 22/22 bounded Kotlin/JVM outcomes | journey-validated | Proven at Kotlin 2.4.10/JDK 17; no Android, Multiplatform, arbitrary Gradle variant, or JVM ABI claim. |
| C# | 22/22 bounded outcomes | journey-validated | Ordinary repositories can yield useful source-only partials; stronger native claims require the selected .NET manifest contract. |

“22/22” means the bounded contract for all 22 language-level skills is complete.
It does not mean every one of the 76 skills applies to every language or
framework, nor that a static analysis proves runtime behavior. The generated
[capability matrix](./.claude/tasks/multilanguage-skill-matrix.json) and
per-language coverage files under `.claude/tasks/` are the machine-readable
sources of implementation truth. The matrix's separate `language_validation`
projection records each pinned real-repository journey, exact revision, and
evidence file. Router handoffs expose the relevant implementation row and
required native tools for the selected closure.

One measured broad JavaScript/TypeScript read-only code-health family can run
three independent lenses concurrently. Across five paired product trials, its
parallel launcher preserved semantic parity and reduced median wall time by
57.71%. Mutations are not batched, and there is no universal workflow
coordinator.

## What is and is not independently installable

The three routers are self-contained, stdlib-only installed units. The normal
bootstrap materializes the full repository and prepares its pinned Python
runtime, so selected task skills can use shared helpers from the external
library without becoming ambient skills.

Some older script-backed task skills still assume repository-level paths and
are not claimed as standalone one-skill packages. A router returning a guide
path means that exact on-demand closure is available; it is not a blanket claim
that copying the guide alone will work. Optional ambient-install commands are
emitted only for closures with selected-install evidence and only when the user
explicitly requests that mode.

## Repository development

Contributors should clone the repository and run the same runtime setup used by
the public library bootstrap:

```bash
git clone https://github.com/KhurrumMahmood/senior-vibe-engineer # host-ref-allow: public distribution repository
cd senior-vibe-engineer
python3 .claude/skills/which-skill/scripts/setup_runtime.py --project-root .
```

The helper health-probes Python 3.11+ interpreters, creates or repairs `.venv`,
installs pinned Python requirements and the library-owned TypeScript parser,
verifies both dependency lanes, and installs Git hooks. The JavaScript tooling
requires Node.js >=20 and npm; setup uses the committed `package-lock.json` and
does not add dependencies to the analyzed host project.
Use `.venv/bin/python` explicitly and invoke pip as
`.venv/bin/python -m pip`; venv `pip` shims can retain stale absolute paths after
a checkout is moved.

Repository contributors should continue with [ONBOARDING.md](./ONBOARDING.md).
AI agents working on this repository should start at [AGENTS.md](./AGENTS.md),
which resolves to the canonical [`.claude/CLAUDE.md`](./.claude/CLAUDE.md).

## Repository map

- [`.claude/skills/`](./.claude/skills/) — 76 router, task, and ecosystem
  skills.
- [`.claude/docs/skill-catalog.md`](./.claude/docs/skill-catalog.md) — complete
  skill catalogue and activation guidance.
- [`.claude/docs/language-support-development.md`](./.claude/docs/language-support-development.md)
  — how language support is developed and verified.
- [`.claude/docs/installation-and-on-demand-library.md`](./.claude/docs/installation-and-on-demand-library.md)
  — contributor contract for installation, external-library topology, and
  host-state migrations.
- [`ai-docs/decisions/`](./ai-docs/decisions/) — accepted and proposed
  architectural decisions.
- [`VISION.md`](./VISION.md) — the maintainability destination the ecosystem is
  intended to help projects reach.
- [`CONTEXT.md`](./CONTEXT.md) — domain glossary for contributors.

## License

No open-source license has been selected yet. Public visibility alone does not
grant permission to copy, modify, or redistribute this repository. A license
will be added after the repository owner chooses its terms.
