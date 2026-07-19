---
name: move-path
description: Deterministically plan, dry-run, apply, and verify standalone TypeScript/TSX file or directory moves while updating identity-resolved Markdown, HTML, config, backtick, and exact path references. Use for a reviewed move map with JSON plans, dry-run reporting, Git-aware moves, and explicit ignored-import risk. TypeScript/TSX source imports are never rewritten in v1; import-safe module moves need a resolver-aware follow-up.
argument-hint: "--plan moves.json --dry-run|--apply|--check"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: maintenance
job: refactor
best_for: |
  Everyday but high-blast path moves: moving or renaming Markdown docs,
  directories, fixtures, scripts, or mixed repo surfaces where references
  should update in one batch. Best when a move map can be reviewed first
  and the desired behavior is "compute a virtual after-tree, rewrite safe
  references once, apply with git-aware moves, then verify."
not_for: |
  Domain-concept terminology renames in prose (use /rename-concept).
  Python/TypeScript import refactors unless a language adapter has been
  explicitly added and enabled. Large behavior-changing subsystem splits
  that need characterization tests and human Phase 4 sign-off (use
  /refactor-subsystem). Blind global find-and-replace.
language: typescript
framework: any
---

# /move-path

You are the orchestrator for safe batched standalone TypeScript/TSX path
moves. The deterministic script owns filesystem moves, path normalization,
reference resolution, patch generation, and verification. Your job is to
prepare or inspect the plan, run dry-run first, review uncertainty buckets and
ignored-import risk, then apply only when the report is clean enough for the
intended change.

## Core Contract

The script computes a **virtual after-tree** before touching disk:

```text
plan -> virtual after-tree -> rewrite refs against after-tree -> apply moves + patches -> verify
```

It updates references by resolved identity, not by hopeful text replacement.
A Markdown link is auto-updated only when its target resolves to a file or
directory being moved. Ambiguous prose is reported, not rewritten.

## TypeScript v1 Boundary

Support standalone `.ts` and `.tsx` file or directory moves and rewrite
identity-resolved Markdown/HTML/config/backtick/exact text references. Use a
stdlib JSON plan as the guaranteed installed format. The script never rewrites
TypeScript or TSX source imports, including relative imports whose target or
referrer is moved; it emits those as `code_imports.ignored` risk records in
the JSON report and under **Ignored TypeScript Imports** in the Markdown report.
Treat remediation as unknown until a TypeScript module resolver proves the
correct spelling. The advisory scanner covers common single-line and multiline
static `import`/`export ... from` forms. For risk identity only, it follows
TypeScript's emitted-file substitution precedence: `.js` probes `.ts`, `.tsx`,
then `.d.ts`; `.mjs` probes `.mts`, then `.d.mts`; `.cjs` probes `.cts`, then
`.d.cts`; the emitted runtime file follows those substitutions. It is not an
exhaustive import inventory.

Do not claim an import-safe module move. Python import rewrites, TypeScript
path aliases, package exports, project references, barrel compatibility,
dynamic imports, and framework-specific routing are out of scope. They need a
named `tsconfig`-aware resolver and separate acceptance evidence.

## Commands

```bash
python3 .claude/skills/move-path/scripts/move_path.py --plan moves.json --dry-run
python3 .claude/skills/move-path/scripts/move_path.py --plan moves.json --apply
python3 .claude/skills/move-path/scripts/move_path.py --plan moves.json --check
python3 .claude/skills/move-path/scripts/audit_path_residue.py --plan moves.json
python3 .claude/skills/move-path/scripts/audit_path_residue.py --plan moves.json --exclude 'source-materials/input-bundles/**'
```

Useful options:

- `--project-root DIR` — default is git toplevel, else cwd.
- `--report-dir DIR` — default `.engineering/local/move-path/`.
- `--stage` — stage moved and rewritten paths after apply.
- `--allow-dirty-touched` — bypass dirty touched-file refusal.
- `--json` — print the JSON report to stdout.

## Plan Shape

```json
{
  "version": 1,
  "moves": [
    {
      "id": "rename-source",
      "from": "src/legacy/report.ts",
      "to": "src/reports/current.ts"
    }
  ],
  "reference_scope": {
    "include": ["**/*.md", "**/*.html", "**/*.json", "**/*.yml", "**/*.yaml"],
    "exclude": [".git/**", ".engineering/local/**", "node_modules/**"]
  },
  "rewrite": {
    "markdown_links": "update",
    "markdown_images": "update",
    "html_href_src": "update",
    "backtick_paths": "update",
    "exact_text_paths": "suggest",
    "code_imports": "ignore"
  },
  "safety": {
    "require_clean_touched_files": true,
    "fail_on_broken_links": true,
    "fail_on_blocked": true
  }
}
```

`.yml` and `.yaml` plans remain compatible only when PyYAML is installed.
They are not part of the guaranteed copied-skill path; choose `.json` for a
stdlib-only installation.

## Confidence Buckets

- `auto` — resolved identity, safe to update.
- `suggest` — likely path/reference, requires review.
- `ignore` — outside configured scope or explicitly unsupported.
- `blocked` — unsafe ambiguity; apply fails unless the plan relaxes the
  relevant safety gate.

For directory moves, `exact_text_paths: update` also rewrites nested
plain-text path tokens such as `inputs-1/kb` when they are rooted under
the moved directory. Use `suggest` first when historical prose may be
describing the old layout rather than linking to the current identity.

## Workflow

1. Write or inspect a move plan. Include many moves in one plan when the
   intended transform is one conceptual batch.
2. Run `--dry-run`.
3. Read `.engineering/local/move-path/report.md` and
   `.engineering/local/move-path/report.json`.
4. Resolve `blocked` findings. Review `suggest` findings and every ignored
   TypeScript import that resolves to a move target.
5. Run `--apply` only after the dry-run report matches the intended
   transform.
6. Run `--check` after manual follow-up edits or before commit.
7. When moved areas include machine-readable manifests, scripts, command
   examples, generated reports, or absolute local paths, run
   `audit_path_residue.py` and review its assumptions, samples, and spot
   checks.

## Git Rules

- Tracked paths move with `git mv`.
- Untracked paths move with filesystem rename and are reported as
  untracked.
- Case-only renames use a temporary path internally.
- Dirty touched files block apply by default.
- `--stage` stages changed old and new paths after apply; otherwise the
  tool leaves the index alone.
- After manual reference or signpost edits, run `--check` before commit. If
  `--stage` was not used, stage the move and rewrite surfaces together so the
  commit is a coherent topology change.
- Keep generated reports under `.engineering/local/move-path/` or clean them
  before handoff. Reports are review artifacts, not source files, unless the
  project explicitly wants to retain them.
- Review low-similarity renames with `git diff -M10 --find-renames` when
  content rewrites make Git show a moved file as delete/add at the default
  threshold.

## Operational Residue Audit

Use `scripts/audit_path_residue.py` when a move touches operational artifacts
that may store paths outside Markdown links: JSON/CSV manifests, lockfiles,
scripts, notebooks, generated reports, command examples, or copied absolute
paths. The helper scans the move plan's reference scope for old relative,
root-relative, absolute POSIX, and Windows-style path spellings, then writes:

The selected move plan is an authority input. Both the mover and residue audit
exclude its exact resolved path even when `reference_scope` matches it; never
rewrite or report the plan's required `from` values as stale residue.

- assumptions that define what the scan can and cannot prove;
- machine-readable findings in
  `.engineering/local/move-path/path-residue-audit.json`;
- a Markdown review report with sampled contexts and spot checks showing
  whether old and new paths exist.

Use repeated `--exclude` flags for known preserved provenance areas when the
goal is operational cleanup rather than source-history rewriting.

When a repeatable residue pattern appears during manual cleanup, prefer adding
or refining a deterministic micro-tool here over relying on an LLM-only sweep.
Keep the helper narrow, fixture-backed, and explicit about what would disprove
its assumptions.

## AI Review

Keep the core deterministic. Use AI review only around the report:

- Are any moves conceptually wrong?
- Are skipped or suggested references likely real breakages?
- Does an ignored TypeScript import require a resolver-aware refactor rather
  than this standalone path/text move?
- Is the scope too broad for one commit?
- Are source snapshots or historical records intentionally excluded?

Do not let an LLM perform unstructured rewrites. If the script cannot
prove identity, the reference is a human review item.
