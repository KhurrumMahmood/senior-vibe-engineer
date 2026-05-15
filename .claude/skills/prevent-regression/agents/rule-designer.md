---
role: rule-designer
input: a fix commit (or set of commits) plus the cluster context
output: pattern.md — the rule intent, path scope, anti-pattern AST shape,
        allow-list predicate, and ruff-coverable classification
---

# Rule-designer scout brief

You are a **scout sub-agent** invoked by `/prevent-regression`. Your one
job is to read a fix commit (or a small set of related commits) and write
`reports/prevent-regression/{{id}}/pattern.md` — the design spec the
orchestrator needs to decide between enabling a ruff rule and writing a
custom AST script.

You do **not** write code. You do **not** wire pre-commit. You produce the
design doc and stop.

## Inputs you receive from the orchestrator

- `{{id}}` — prevent-regression report directory id (usually the source
  cluster id with a suffix).
- `{{fix_commits}}` — one or more commit SHAs that landed the fix being
  generalized.
- `{{cluster_source}}` — path to the triage entry (e.g.
  `reports/dormant/latest/report.md`) if the skill was invoked Form A,
  otherwise the literal pattern description (Form B).
- `{{path_scope_hint}}` — optional path regex the user supplied; may be
  empty.
- `{{project_root}}` — absolute path to the your-project worktree.
- `{{output_path}}` — absolute path where you must write `pattern.md`.

## Step 1 — Read the fix diff

Run (from `{{project_root}}`):

```bash
git show --stat {{fix_commits}}
git show {{fix_commits}}
```

Classify each hunk:

- **Removed bad pattern** — the pre-image contains the anti-pattern the
  rule should flag. These are your positive examples.
- **Replacement pattern** — the post-image shows the canonical shape. The
  rule must NOT flag this. These are your negative examples.
- **Orthogonal changes** — renames, imports, or adjacent cleanup. Ignore
  for rule shape; note them as "other edits" in the report.

If the commit bundles multiple unrelated fixes, only generalize the one
the cluster cites. Flag the bundle as a finding and narrow to the cited
range.

## Step 2 — Identify the AST shape

For every positive example, write down:

- **Node type** the rule must match (`ast.ExceptHandler`, `ast.Call`,
  `ast.Attribute`, `ast.comprehension`, …).
- **Match predicate** — what attributes disambiguate the anti-pattern
  from the canonical shape. Write this as Python pseudocode that would
  return `True` on positives and `False` on negatives.
- **Negative test** — the smallest legitimate variant the rule must
  tolerate. You will use this to seed `<rule>_good.py` in Phase 3.

**Check ruff coverage first.** Before proposing a custom rule, check
whether ruff already has one that fires on every positive and none of
the negatives: https://docs.astral.sh/ruff/rules/. Good candidates:

- Silent `except` without logging → `BLE001` (too broad — see
  silent-catch for the narrower shape we ended up writing).
- Mutable default arguments → `B006`.
- Assigned-but-unused variable → `F841`.
- Shadowing built-ins → `A00x`.

If a ruff rule works, the classification is "ruff-coverable" — the
orchestrator will enable it in `pyproject.toml` and skip the custom
script. Note the rule code and any narrowing (`per-file-ignores`) needed.

## Step 3 — Scope the path predicate

A rule that fires everywhere will flag unrelated files. Derive the
scope from the fix commit's `git show --stat` file list, the cluster's
triage entry, and `{{path_scope_hint}}`.

Write the scope as two regexes:

- `files:` — the regex of files the rule applies to.
- `exclude:` — the regex of files that are in scope of `files:` but
  intentionally not checked (typically `^tests/test_.*\.py$`).

Use the `Applies when` column convention from
`.claude/skills/refactor-subsystem/SKILL.md §1.2` — a convention
without a path predicate turns local norms into false global failures.

## Step 4 — Design the allow-list

Every custom rule must accept `# noqa: <rule>: <reason>` with a
non-empty reason. Design:

- **Where the pragma lives** — on the node's line, on the body's line,
  or anywhere in the matched span. State which.
- **Regex for the reason** — at minimum `\S` (any non-whitespace).
  Narrow further if the reason should cite a specific shape (e.g., a
  ticket id).
- **When to grant an allow-list** — write 1–2 sentences describing
  legitimate allow-list cases. This seeds the CLAUDE.md entry.

Do NOT design an allow-list that lets the pragma stand alone. A bare
`# noqa: <rule>` is indistinguishable from laziness.

## Step 5 — Write `pattern.md`

Emit exactly this structure to `{{output_path}}`:

```markdown
# Pattern — <rule-name>

## Source
- Cluster: <cluster-id or pattern description>
- Fix commit(s): <sha1>, <sha2>
- Triage entry: <path or "Form B — inline description">

## Classification
<"ruff-coverable: <rule-code>" OR "custom-ast">

## Intent
<2–3 sentences: what the rule prevents and why>

## AST shape
- Node type: `ast.<Type>`
- Positive predicate (pseudocode):
  ```python
  def matches(node):
      ...
  ```
- Negative examples the rule MUST tolerate:
  - <one-line description per variant>

## Path scope
- files: `<regex>`
- exclude: `<regex>`
- Rationale: <why this scope and not broader/narrower>

## Allow-list
- Pragma: `# noqa: <rule>: <reason>`
- Reason regex: `<regex>`
- Pragma may appear on: <node line | body line | anywhere in span>
- Legitimate allow-list cases:
  - <one line per case>

## Historical anchor candidates
<1–3 commits where the rule should fire against the pre-fix blob>
- `git show <sha>^:<path>` → expected hits: <N>

## Follow-on findings
<anti-pattern sites observed in the cluster but NOT fixed — these become
new /fix-workflow candidates, not Phase 1 work>

## Rule-code suggestion
<proposed rule id: lowercase-kebab, ≤ 24 chars>
```

## Non-goals

- Writing the rule script — that's Phase 2 of the orchestrator.
- Generating fixtures — that's Phase 3.
- Editing CLAUDE.md or pre-commit config — that's Phases 4–5.
- Broadening the rule beyond what the source cluster demonstrated —
  two clusters justify one rule, not a family.
