# Installation and on-demand library development

Status: contributor guide for the accepted router-only topology, shipped
schema-3 host-state migration chain, completed Codex lifecycle evidence, and a
deferred host-instruction integration proposal

## Sources of truth and working records

- ADR 0038 is binding for the exact-three-router default and external
  on-demand library.
- This file explains how to preserve that topology while changing installer,
  host-instruction, task-packet, or model/effort behavior. Sections explicitly
  labeled proposed are not current product claims.
- `.claude/tasks/language-support-and-productization-execution-plan.md` is the
  completed execution ledger and owns the final release/lifecycle evidence.
  `.claude/tasks/multilanguage-support-backlog.md` owns deferred language and
  framework follow-ups. `productization-restart-plan.md` is retained only as
  historical restart evidence.
- `tests/test_installed_routers.py` owns the runnable installed-boundary
  contract.
- `.claude/docs/cross-tool-agent-governance.md` owns instruction-surface and
  enforcement placement across Claude, Codex, Gemini/Cursor, and Augment.

## Existing binding decision

ADR 0038 already establishes the desired default topology:

1. install only `which-skill`, `which-shape`, and `which-cleanup` into agent
   discovery;
2. bootstrap the full engineering-skills repository into a project-scoped
   sibling library outside the target repository and discovery roots;
3. route to exact guide/tool closures in that library; and
4. prefer a fresh non-context sub-agent for non-trivial routed work, while
   keeping selected task-skill installation explicit and optional.

This design does not replace that decision. It defines the smallest useful
extension: optional integration of selected engineering guidance into a host
project's native agent-instruction surfaces.

The shipped `which-skill/scripts/bootstrap_library.py` action also initializes
the fresh host's toolkit-owned `.engineering/.gitignore` with `/local/`. It
does not edit project source or agent instructions. If that file already exists
without the rule, or either path is unsafe, bootstrap stops instead of guessing;
the migration runner therefore never relies on an undocumented manual file.

## Release updates and host-state migrations

Distributed toolkit code and projected host state have separate version axes:

- the stock agent-skill installer installs or replaces the three routers at an
  exact Git ref;
- ordinary Git bootstrap/replacement updates the external on-demand library;
- `.engineering/manifest.json` records the host-state schema and applied
  migration IDs; and
- `scripts/host_migrations.py` previews, applies, or restores only the
  toolkit-owned paths declared by the shipped ordered migrations.

The migration runner is not a package manager. It never fetches code, installs
dependencies, updates routers, or rewrites project source. `status` and `plan`
are read-only. `apply` is the explicit mutation boundary. `restore` is allowed
only while the machine-local recovery journal still exists and every touched
byte matches the state recorded immediately after apply.

Run the new library's runner from the host project:

```bash
LIBRARY_ROOT="${ENGINEERING_SKILLS_LIBRARY:?Set the external library root}"
HOST_PYTHON="${ENGINEERING_SKILLS_PYTHON:-${LIBRARY_ROOT}/.venv/bin/python}"

"${HOST_PYTHON}" "${LIBRARY_ROOT}/scripts/host_migrations.py" \
  --project-root "$PWD" status
"${HOST_PYTHON}" "${LIBRARY_ROOT}/scripts/host_migrations.py" \
  --project-root "$PWD" plan

# Mutating commands: run only after reviewing the plan.
"${HOST_PYTHON}" "${LIBRARY_ROOT}/scripts/host_migrations.py" \
  --project-root "$PWD" apply
"${HOST_PYTHON}" "${LIBRARY_ROOT}/scripts/host_migrations.py" \
  --project-root "$PWD" restore 0002-subsystem-maps-home
```

The current schema is 3 and contains two real ordered migrations:

1. `0001-subsystem-registry-home` moves the regular toolkit-owned
   `.claude/subsystems.yaml` to `.engineering/subsystems.yaml`.
2. `0002-subsystem-maps-home` moves the toolkit-authored
   `.claude/docs/subsystems/` tree to `.engineering/docs/subsystems/`.

Both moves preserve bytes and directory modes, preserve unrelated files, and
record the migration in the committed manifest. The runner refuses destination
collisions, symlinks/non-regular path shapes, malformed or inconsistent
manifests/journals, a missing `/local/` ignore rule, and hosts newer than the
running toolkit. Readers prefer the canonical paths and retain one visible,
bounded legacy fallback for older hosts. Producers write only canonical paths.

The recovery journal lives under `.engineering/local/migrations/` and therefore
does not travel with a clone. The committed manifest is the durable application
record; restore data is deliberately machine-local. A process stop before or
after the manifest write can be resumed by running `apply` again. A repeated
successful `apply` is a no-op.

The focused migration suite proves schema 1→2→3 skipped-release composition,
schema-2-only upgrade, schema-3 no-op replay, interruption recovery around both
schema writes, exact reverse restore, and older-tool refusal. P8 subsequently
proved the public Codex two-ref stock-router/library update, explicit migration,
route, final selected artifact, closeout, scoped uninstall, and preservation
journey. Its evidence is retained in
`.claude/tasks/p8-stock-update-replay-evidence.json`.

## Product principle and deferred host-instruction integration

Installing skills and adopting project guidance are different permissions.
The default installation should remain three routers plus the external
library. Host instruction changes require an explicit selection and a preview.

No host-instruction integration mode shipped: measured P8 use did not establish
enough friction to justify that extra mutation surface. If a future measured
consumer reopens the proposal, it should evaluate these modes:

| Mode | Host effect |
|---|---|
| `routers-only` | No host instruction files changed; current default |
| `signpost` | Add a short managed pointer explaining the three routers, external library, project profile, and on-demand/sub-agent execution model |
| `selected-guidance` | Add the signpost plus user-selected shared policies such as verification, planning discipline, language commands, or delegation guidance |
| `project-template` | Explicit opt-in for a new/minimal repository that wants a fuller generated starting point; never overwrite an established instruction file |

`signpost` is the provisional recommended interactive choice for that future
experiment, not current product behavior or a silent default. It would keep
always-loaded context small while teaching agents how to reach the richer
library.

## Neutral guidance and surface adapters

Store each selectable guidance unit once as neutral content with metadata:

- stable id and version;
- purpose and activation trigger;
- shared vs agent/model-specific applicability;
- supported host surfaces;
- whether it is advisory or backed by a repository check/hook;
- dependencies on project profile, language profile, or native commands; and
- a compact delegation form.

Render that content through thin adapters for `AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, Cursor/Augment surfaces, or later agents. Shared behavioral rules
stay shared. Agent-specific blocks exist only where capabilities or invocation
mechanics actually differ.

The installer must detect existing files and symlinks, show the proposed diff,
and modify only a clearly marked managed block. Re-running is idempotent.
Update/repair changes only managed content; uninstall removes only the managed
block and never rewrites unrelated user text.

## Project policy and local state

Keep two categories separate:

- **committed project policy:** selected guidance ids, language/framework
  profile, native verification commands, and any team-approved delegation
  policy;
- **machine-local state:** resolved external-library path, installed tool
  locations, caches, and locally available model/tool capabilities.

Routers should consume a compact generated project profile rather than parse
large host instruction files or load all guidance. The external library remains
the authority for full guides and supporting tools.

## Model- and effort-aware delegation

A non-context sub-agent cannot be assumed to inherit `AGENTS.md`, `CLAUDE.md`,
the parent conversation, or the same model. Every routed handoff therefore
needs a compact task packet containing:

- task, project root, owned paths, mutation authority, and stop condition;
- selected skill closure and relevant shared/language/framework guidance;
- native tool and verification commands;
- required final artifact and evidence;
- applicable cross-agent rules; and
- an execution-role recommendation.

Model names and effort enums should not be embedded throughout skill bodies.
Define stable execution roles, then let an agent adapter map those roles onto
currently available models and effort settings:

| Role | Default intent |
|---|---|
| `inventory` | cheap, fast, read-only enumeration with deterministic output |
| `implementation` | capable coding model with enough effort for the bounded contract |
| `semantic-review` | independent strong reasoning over final behavior and language boundaries |
| `adversarial-review` | high-effort fresh-context challenge, constrained by current product goals |
| `verification` | light model only when checks are deterministic and the worker cannot approve its own implementation |

The selected adapter may map these to model-specific values such as
`medium`, `high`, `xhigh`, or `max`, but it must first check availability and
must record the actual model/effort in the outcome. Effort is a task-role
policy, not a claim that vendors' similarly named levels are equivalent.

Rules that materially constrain correctness, privacy, external code sharing,
mutation, or benchmark validity must be included directly in every applicable
task packet even if the parent host file also contains them. Advisory style
preferences may be omitted when irrelevant.

## Deferred implementation slices

1. Define the neutral guidance-unit schema and three small exemplars:
   router/library signpost, verification policy, and non-context delegation.
2. Add a preview-only renderer for existing `AGENTS.md`, `CLAUDE.md`, and
   `GEMINI.md` files, including symlink detection and managed-block ownership.
3. Add explicit apply/update/remove operations for the managed block.
4. Add committed-policy and machine-local-state schemas without requiring a
   central execution service.
5. Extend router handoffs with selected compact guidance and an execution role;
   keep concrete model selection in the host-agent adapter.
6. Prove one clean Codex host and one Claude or Gemini host through install,
   route, fresh non-context execution, update, and uninstall.

## Promotion criteria if revisited

- Default discovery still contains exactly the three routers.
- `routers-only` changes no host instruction file.
- Every mutating guidance mode shows a diff and requires explicit approval.
- Apply/update/remove are idempotent and preserve all non-managed bytes.
- Symlinks and multiple existing instruction surfaces are reported rather than
  silently duplicated or replaced.
- Router output loads only selected guidance metadata/body fragments, not the
  full skill catalog.
- A fresh non-context worker using only the emitted task packet follows the
  selected cross-agent guidance and reaches a representative final outcome.
- A worker using a different model receives the same binding task rules plus a
  valid model-specific execution-role mapping; the actual model and effort are
  recorded.
- Removing the integration leaves the external library and user-authored
  instruction content intact unless the user separately requests library
  removal.

## Non-goals

- Installing all task skills or guidance into agent discovery.
- Treating instruction context as enforcement when a repo check or permission
  boundary is required.
- A universal agent runtime, workflow DAG, or autonomous mutation coordinator.
- Hard-coding one vendor's current model catalogue into every skill.
- Editing user instruction files without preview and explicit consent.
- Reviving content attestation or the discarded transactional platform.

## Deferred storage decision

If measured evidence justifies implementation, first decide whether the
committed project-policy file should be a new neutral engineering-skills config
or an extension of the existing project profile. Do not resolve that storage
fork merely to make the deferred proposal appear more complete.
