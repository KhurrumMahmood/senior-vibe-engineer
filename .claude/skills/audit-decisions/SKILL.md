---
name: audit-decisions
description: "Read-only, portable decision-registry drift audit. It writes a final drift report, captures registry/link diagnostics, and validates `decision:NNNN` references from Python comments, Markdown/HTML references, and TypeScript/TSX comments."
argument-hint: "[--target PATH]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: guard
best_for: |
  Periodic (monthly / pre-release) decision-registry hygiene and a precise
  check that inline decision references still point at real ADRs.
not_for: |
  Authoring or amending ADRs, resolving a drift row, parsing TypeScript
  identifiers, or inferring runtime/framework semantics.
escalate_to: |
  None. This skill is read-only; each finding names the human's next command.
delegate_from: |
  /which-skill may recommend /audit-decisions for decision-registry hygiene
  and orphaned inline decision references.
language: any
framework: any
scans: [python, markdown, html, typescript]
---

# /audit-decisions

Run a read-only drift scan over `ai-docs/decisions/` and the host's authored
reference files. The final artifact is `drift.md`; `raw-drift.json` preserves
both drift evidence and every resolved reference, so a healthy TypeScript/TSX
reference is visible rather than silently disappearing.

## How success is judged

- Write `drift.md`, `raw-drift.json`, `registry-audit.json`, and
  `link-check.txt` under one requested report directory. Do not claim a scan
  ran without all four artifacts.
- Include valid `decision:NNNN` references from TypeScript and TSX comments in
  both final artifacts. A valid reference prevents an old accepted ADR from
  being reported as unreferenced.
- Preserve Python comment, Markdown, and HTML reference handling additively.
  Registry status/link checks remain visible in their compatibility artifacts.
- Keep the registry and source files read-only. Exit `0` for clean, `1` when
  drift rows are present, and `2` for invalid paths or unsupported/malformed
  decision frontmatter.

## Supported reference contract

### TypeScript and TSX v1

The supported token is lowercase `decision:NNNN`, where `NNNN` is exactly four
digits. It is recognized only in these real comment forms:

- `// decision:0001` line comments;
- `/* decision:0001 */` block comments;
- `/** decision:0001 */` JSDoc comments, including multi-line JSDoc;
- comments inside a template interpolation (`${/* decision:0001 */ ...}`) and
  TSX expression (`{/* decision:0001 */}`).

The lexical scanner ignores string literals, template text, regex literals,
and TSX text nodes. It does not parse identifiers, resolve imports, interpret
types, or infer React/Node/other framework behavior. A TypeScript Compiler API,
package manager, network access, shared parser, and host `tsconfig` are not
required for this comment-only invariant.

### Existing reference forms

- Python: `decision:NNNN` inside a real `#` comment (Python's tokenizer
  distinguishes it from strings).
- Markdown: the established `# decision:NNNN` form.
- HTML: the established `# decision:NNNN` form, normally inside `<!-- -->`.

The selected runner accepts ordinary scalar frontmatter plus inline or block
lists for the registry fields it checks (`supersedes`, `superseded_by`,
`applies_to`, `embodied_by`, `tags`). It fails clearly instead of silently
misreading unsupported frontmatter syntax.

## Source policy

Exclusions are always evaluated relative to `--project-root`, even when a
caller directly targets an excluded directory or file. Generated, vendor,
dependency, build, report, coverage, fixture, and test/spec paths never create
references. The same policy excludes common VCS/venv/cache trees and TypeScript
declarations, `.test`, `.spec`, and minified files.

`--target` narrows the reference scan only. It still validates the registry and
links, but intentionally omits the whole-project `unreferenced-decision`
inverse check because a partial target cannot establish that conclusion.

## Installed workflow

Stock Codex copies this selected skill to `.agents/skills/audit-decisions`.
From the host project root, with Python 3.11+:

```bash
AUDIT_PROJECT_ROOT="$PWD"
AUDIT_SKILL_DIR="$AUDIT_PROJECT_ROOT/.agents/skills/audit-decisions"
AUDIT_SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
AUDIT_REPORT_DIR="$AUDIT_PROJECT_ROOT/reports/audit-decisions/$AUDIT_SCAN_ID"

python3 -I -S "${AUDIT_SKILL_DIR}"/scripts/audit.py \
  --project-root "$AUDIT_PROJECT_ROOT" \
  --output-dir "$AUDIT_REPORT_DIR"
```

For a bounded code-reference check, add a project-relative target:

```bash
python3 -I -S "${AUDIT_SKILL_DIR}"/scripts/audit.py \
  --project-root "$AUDIT_PROJECT_ROOT" \
  --output-dir "$AUDIT_REPORT_DIR" \
  --target src
```

The installed executable imports only Python standard-library modules from this
selected directory. It does not need a toolkit virtualenv, repository helper,
sibling skill, host package manager, or network connection.

## Read the final artifact before acting

`drift.md` lists summary counts, resolved-reference inventory, and every drift
row with a resolution command. `raw-drift.json` is the structured evidence:
`references[]` always includes path, line, language, comment form, ADR id, and
whether the id resolves. `registry-audit.json` and `link-check.txt` retain the
registry status/link diagnostics for direct troubleshooting.

The report can surface these drift classes:

| Symptom | Default severity | Resolution |
|---|---|---|
| `code-ref-orphan` | P0 for code, P1 for docs | `/decide <id>` or remove the stale reference |
| `broken-supersession` | P0 | `/decide --amend <id>` |
| `applies-to-missing` | P1 (P0 when every non-host path is absent) | `/decide --amend <id>` |
| `proposed-too-long` | P1 (P0 after 90 days) | `/decide --amend <id>` |
| `unreferenced-decision` | P2 (P1 for lint/enforced tags) | review whether the ADR remains load-bearing |
| `registry-audit` | P0 | amend the named malformed registry field |

## When things go sideways

| Symptom | Action |
|---|---|
| Exit 2 | Correct the project/target path or frontmatter. Do not treat a failed parse as a clean audit. |
| No TypeScript tooling installed | Continue: this lexical comment scan requires only host Python. |
| A desired reference is in an identifier, string, regex, or JSX text | Do not count it. Add a supported comment at the authoritative location. |
| An excluded tree is supplied directly with `--target` | The scan is clean for references by design; exclusions cannot be bypassed by narrowing the target. |
| A relationship/link diagnostic is present | Read `link-check.txt`, repair the ADR deliberately, then re-run. |

## Installed layout

```
audit-decisions/
├── SKILL.md
└── scripts/
    └── audit.py
```
