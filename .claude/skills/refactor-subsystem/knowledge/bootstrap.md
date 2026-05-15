# Phase 0 — Bootstrap playbook

Loaded only when `scripts/specs.py show <spec-id>` exits non-zero at Phase
1 start. If the spec already exists, Phase 0 is skipped and this file is
never read.

Goal: produce `ai-docs/specs/<spec-id>.md` before Phase 1 runs. The
scaffolded spec is intentionally a stub — Phase 1 and Phase 2 turn it
into a real spec.

## 0.1 Decide whether to scaffold

```bash
python3 scripts/specs.py show <spec-id>
```

- **Exit 0** — spec exists. Skip to Phase 1.
- **Exit 1 / "no spec with id"** — spec does not exist. Proceed to 0.2.
- **Any other non-zero exit** — abort and report.

Before scaffolding, confirm scope with the human. The scaffold locks in
`code_roots` — if the cluster boundary is wrong, every subsequent phase
is wrong. Ask (or infer from args):

1. Which files / directories make up the subsystem? These become
   `--code-roots`.
2. Does the human want a `--title` override, or is the default derived
   from `<spec-id>` fine?

## 0.2 Scaffold the stub spec

```bash
python3 scripts/specs.py init <spec-id> \
    --code-roots <path1> \
    --code-roots <path2> \
    [--title "Human-readable Title"] \
    [--date 2026-04-10]
```

`init` creates the spec file with frontmatter, empty narrative sections,
and auto-generated `## Known <kind> inventory (stub)` tables for each
`.py` code_root. Explicit stub-warning language makes `inventory-check`
report `status: STUB`.

**The scaffolded spec is NOT a finished spec.** It has no Goals, no AR
items, no IM targets, no EX notes, no LR entries. Phase 1 and Phase 2
turn the stub into a real spec.

## 0.3 Verify the stub round-trips

```bash
python3 scripts/specs.py inventory-check <spec-id>
python3 scripts/specs.py inventory-check <spec-id> --strict  # exit 1 — expected
```

Expected: `status: STUB`, `--strict` exits 1. If `--strict` exits 0, the
scaffold lost its stub markers — investigate.

## 0.4 Hand off to Phase 1

Commit the scaffolded spec as a single-file commit before starting Phase 1:

```
ai-docs/specs/<spec-id>.md: scaffold stub via `specs.py init` (Phase 0)

Bootstrapping a spec for <short description of the cluster> as
part of /refactor-subsystem <spec-id>. This is a stub — all
narrative sections are empty placeholders and the inventory
table is an auto-generated AST dump. Phase 1.1 (scout dispatch)
will populate the real content.
```

## Why a separate file

Phase 0 is the rarest codepath — scaffolds run once per subsystem,
maybe once per quarter. Keeping the detail out of SKILL.md's always-on
context saves tokens on every normal run; loading `bootstrap.md` on the
exit-1 branch is cheap.
