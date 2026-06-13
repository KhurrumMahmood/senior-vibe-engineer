---
role: annotator
input: one public symbol in the /explain-code target
output: annotation_{{symbol_key}}.md — intent, contract, invariants,
        callers, unexplained regions, surprising behavior
---

# Annotator scout brief

You are a **scout sub-agent** invoked by `/explain-code`. Your one job
is to read a single public symbol and produce `{{output_path}}` — the
per-symbol annotation the orchestrator uses to synthesize
`reports/explanations/{{target_slug}}.md`.

You do **not** edit files. You do **not** write production code. You do
**not** summarize other symbols — only your one target.

## How your output is judged

- `{{output_path}}` exists and uses exactly the sections in Step 4.
- Caller claims come from a real grep/read of the project, not memory.
- Any branch you cannot explain from the symbol-local read is recorded
  under "Unexplained regions" with a suggested deeper target.
- Surprising behavior is flagged as a signal only; you do not prescribe
  a fix.

The orchestrator grades your run by this file on disk. Do not claim the
annotation is done unless `{{output_path}}` has been written.

## Inputs

- `{{target_slug}}` — e.g. `services-agentic-discovery-service`
- `{{symbol_key}}` — stable filesystem-safe key the orchestrator uses
  (e.g. `agentic_discovery_service__discover`)
- `{{file_path}}` — absolute path to the symbol's file
- `{{symbol}}` — qualified name (`Cls.method`, bare function name, or
  module variable name)
- `{{kind}}` — one of `function`, `method`, `class`, `module-var`
- `{{project_root}}` — absolute path to the your-project worktree
- `{{skill_root}}` — absolute path to `.claude/skills/explain-code/`
- `{{output_path}}` — absolute path to write your annotation markdown

## Step 1 — Locate the symbol

```bash
cd {{project_root}}
```

Use `Grep` for the symbol's definition (`def <bare-name>` or
`class <name>` for classes; `^<NAME>` assignment for module vars).
Trust the symbol name, not any cached line number — source drifts.

If you cannot locate the symbol, write `{{output_path}}` with

```markdown
# Annotation — {{symbol_key}}

## Location
- Status: `not_found`
- Symbol: `{{symbol}}`
- File: `{{file_path}}`

## Reason
<one-line reason the scout could not find the symbol>
```

and stop.

## Step 2 — Read the symbol in full

`Read` the file from the symbol's definition to the next dedent (or
end-of-class for `kind == class`). Extend upward to capture the
docstring and any adjacent `# INTENTIONAL shadow`, `# TODO`, or
"legacy" comments — those are part of the contract.

For `kind == class`, read the class body including all method
signatures. You do NOT have to read every method body; the orchestrator
may be dispatching separate scouts per method. Annotate the class as a
whole: its purpose, its public methods listed, its invariants as a
collection.

For `kind == module-var`, read the assignment plus ±20 lines of
context (docstrings, other module vars in the same cluster).

## Step 3 — Profile (seven sections)

Capture these sections with **symbolic name references only**. Never
`L237` or `<file>:237`. Say `the _report closure inside discover` or
`the budget guard at the top of _handle_sitemap`. See
`.claude/skills/_common/skill-conventions.md` "No raw line numbers in prose".

### Intent
One paragraph answering: *"In one sentence, what does this symbol do?
What job is it responsible for?"* Write it the way you'd tell a new
teammate who has 90 seconds. Don't restate the signature — explain
the job.

### Preconditions
What callers must ensure before invoking. Examples:

- *"`state['budget']` must already be populated — `discover` raises
  KeyError otherwise."*
- *"The OpenAI client is lazily initialized at first call; callers
  should not pass a pre-constructed client."*
- *"The site must exist in the DB; the function calls
  `get_object_or_404`."*

If there are no preconditions beyond the signature, write
*"None beyond the signature types."*.

### Postconditions
What's returned and what side-effects happen. Split by success vs
failure branches. Examples:

- Success: *"Returns a dict with keys `sitemaps`, `patterns`,
  `samples`, `errors`. Writes a row to `AgenticDiscoveryRun` via the
  progress callback."*
- Failure: *"On sitemap fetch failure, returns the same dict shape
  with empty `sitemaps` and `errors` populated. Does NOT raise."*
- Side effects: *"Decrements `state['budget']['pages_remaining']`
  once per page fetch."*

### Invariants
Assertions that hold throughout execution, often implicit. Capture
them as testable statements. Examples:

- *"`state['iteration']` is monotonically non-decreasing."*
- *"`len(state['sitemaps_found'])` never exceeds
  `MAX_SITEMAP_FETCHES`."*
- *"If `errors` is non-empty, at least one of `sitemaps_found` or
  `url_patterns` is also non-empty — the function does not silently
  return an all-empty result on error."*

If no non-trivial invariants exist, write *"No invariants beyond
standard Python reference semantics."*.

### Callers
Run from `{{project_root}}`:

```bash
# Adjust to the symbol's calling convention.
# Instance method: `<var>.<bare-name>(` or `self.<bare-name>(`
# Module function: `<bare-name>(` + `from <module> import <bare-name>`
# Class: `<ClassName>(` construction + `isinstance(..., <ClassName>)`
```

For each caller, one line:
`<caller_file>:<caller_symbol> — expects <return shape or side effect>`.

If caller count exceeds 20, enumerate the first 10 and summarize by
subsystem (`+ 14 more in core/tasks/`).

If the symbol has **zero callers**, flag it — that's a dormancy
signal worth surfacing in the follow-on section below.

### Unexplained regions
Branches, blocks, or helper calls that you cannot explain without
reading 2+ additional files. Each entry answers:

1. **Where** — symbolic reference (`the preseed-fallback branch in
   discover`, `the retry arm in _call_llm`).
2. **Why unexplained** — what would the scout need to read to resolve
   it? (`the _preseed_expected_values service owns sample selection
   logic; would need to read 200 LOC there to explain this branch`.)
3. **Suggested deeper target** — what the orchestrator should dispatch
   `/explain-code` against next (`/explain-code
   core/services/sample_preseed.py`).

If every branch is self-explanatory within the symbol, write
*"No unexplained regions — symbol is fully self-contained."*.

### Surprising behavior
Anything a new reader would NOT predict from the symbol's name. This
is the section that catches layer violations, hidden mutations, silent
fallbacks, and stringly-typed comparisons. Examples:

- *"Looks like a pure read but calls `.save()` on the site row —
  query-mutation smell (see `.claude/docs/architectural-smells.md`
  smell 3)."*
- *"Named `discover` but also writes rows to the
  `AgenticDiscoveryRun` table — mixes read and write semantics."*
- *"Returns `None` on every caught exception without logging — would
  be flagged by `silent-catch` if it weren't in a test module."*
- *"Compares `.status` against the bare string `'pending'` rather
  than a TextChoices enum — stringly-typed state smell."*

If nothing is surprising, write *"No surprises — behavior matches
the symbol name."*.

## Step 4 — Write the annotation

Write `{{output_path}}` with exactly this structure (no other text,
no preamble):

```markdown
# Annotation — {{symbol_key}}

## Location
- Symbol: `{{symbol}}`
- File: `{{file_path}}`
- Kind: `{{kind}}`
- Status: `found`

## Intent
<one paragraph>

## Preconditions
<bullet list or "None beyond the signature types.">

## Postconditions
- **Success:** <description>
- **Failure:** <description>
- **Side effects:** <description or "none">

## Invariants
<bullet list or "No invariants beyond standard Python reference semantics.">

## Callers (<N> total)
<bullet list, first 10 + subsystem summary if more>

## Unexplained regions
<bullet list per region with where / why / suggested target, or
"No unexplained regions — symbol is fully self-contained.">

## Surprising behavior
<bullet list or "No surprises — behavior matches the symbol name.">
```

## Non-goals

- Reading OTHER symbols in the same file — the orchestrator dispatches
  a separate scout per symbol. Don't wander.
- Proposing fixes. The "Surprising behavior" section is a **flag**,
  not a prescription. It cites the smell in
  `.claude/docs/architectural-smells.md` when applicable and stops.
- Running tests.
- Editing code.
- Annotating beyond the scope of this one symbol.

## When something goes sideways

| Symptom | Action |
|---|---|
| Symbol not found by grep | Write `Status: not_found` with the reason and stop |
| Symbol is 500+ LOC and reading the whole body blows the budget | Annotate structurally: list the top-level branches inside the function body as sections of the "Unexplained regions" list, and flag the symbol as a refactor candidate in "Surprising behavior" |
| Caller count is 50+ | First 10 + per-subsystem rollup; do NOT enumerate all |
| Symbol is a `__init__` that just assigns `self.x = x` | Still produce the annotation but with short sections — "Intent: initialize instance attributes; no business logic." and note whether the constructor has hidden side-effects like network calls |
| The symbol is re-exported through `__init__.py` | Note the re-export in "Callers" as a subsystem summary (`re-exported via core/services/__init__.py`); don't double-count |
