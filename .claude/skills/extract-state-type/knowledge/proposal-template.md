# /extract-state-type — proposal template

Every `reports/extract-state-type/<target-slug>/proposal.md` follows
the same ten-section shape. The orchestrator fills it from
`targets.json` + `profile.md`; the scout does NOT write this file.

This doc is the canonical reference — section order, headings, and
the content rules for each section. The proposal is the handoff
artifact; it must be self-contained enough that a human reviewer (and
eventually `/fix-workflow`) can act on it without loading the scout's
profile.

## Section order

1. Target metadata (code-block table).
2. Summary (≤5 sentences).
3. Current shape (implicit dict).
4. Proposed type definition.
5. Migration plan.
6. Caller table.
7. Characterization tests.
8. Test matrix.
9. Stop condition.
10. Follow-on findings.
11. Authorization.

(The Summary is a thin section, not a numbered stage — it sits
between metadata and current shape so a reviewer absorbs the "why"
before the tables.)

## 1. Target metadata

```markdown
# Proposal — extract-state-type — agentic_discovery_service__discover

| Field | Value |
|---|---|
| Target | `core/services/agentic_discovery_service.py::AgenticDiscoveryService.discover` |
| Slug | `agentic_discovery_service__discover` |
| Shape | `@dataclass` |
| Dict variable (before) | `state` |
| Top-level fields | 9 |
| Nested shapes | 1 (`BudgetState`) |
| Callers | 2 |
| Regenerated | 2026-04-19T23:45:00Z |
```

Timestamp is UTC. `Shape` is `@dataclass`, `TypedDict`, or
`do_not_typeify` (the last one short-circuits the proposal at the
Summary section with a one-paragraph explanation).

## 2. Summary (≤5 sentences)

A paragraph stating:

- What dict-state the target owns today.
- What the proposal converts it to.
- Why that shape (the classification rule that applied).
- The migration's caller footprint (how many call sites touch the
  dict vs. the return).
- The non-goal fence (what this proposal explicitly does NOT do).

Example:

```markdown
## Summary

`AgenticDiscoveryService.discover` drives a ten-helper discovery
pipeline whose state lives in a single `state = {...}` dict mutated
across every helper. The proposal converts `state` to a
`@dataclass DiscoveryState` (with a nested `BudgetState`) in a new
`core/services/agentic_discovery/state.py` module. `@dataclass` is
the right shape because the state is mutated in place by private
helpers across multiple phases; `TypedDict` would freeze the mutation
pattern. Two call sites read the return value and three private
helpers mutate the dict; the migration's external cost is adding a
`to_dict()` call at the two return-consuming sites. The proposal
does NOT rewrite the ten private helpers — their edits fall out of
the dataclass migration mechanically and belong to `/fix-workflow`.
```

## 3. Current shape (implicit dict)

A table of every key the profile identified, plus nested-shape
subsections.

```markdown
## Current shape (implicit dict)

| Key | Type | Required | Default | Mutated | First write | First read |
|---|---|---|---|---|---|---|
| `base_url` | `str` | yes | arg | no | `discover` setup | every helper |
| `site_name` | `str` | no | `""` | no | `discover` setup | `_classify_sitemaps` |
| `include_sitemap_urls` | `bool` | no | `False` | no | `discover` setup | `_sample_candidate_urls` |
| `iteration` | `int` | yes | `0` | yes | `discover` setup | `_should_continue` |
| `budget` | `BudgetState` | yes | factory | yes | `discover` setup | every helper |
| `sitemaps_found` | `list[str]` | no | `[]` | yes | `discover` setup | `_compile_results` |
| `url_patterns` | `list[dict]` | no | `[]` | yes | `_classify_sitemaps` | `_compile_results` |
| `pages_checked` | `int` | yes | `0` | yes | `_sample_candidate_urls` | `_should_continue` |
| `errors` | `list[str]` | no | `[]` | yes | any helper on exception | `_compile_results` |

### Nested: `BudgetState`

| Key | Type | Required | Default | Mutated |
|---|---|---|---|---|
| `pages_remaining` | `int` | yes | `100` | yes |
| `ai_calls_remaining` | `int` | yes | `30` | yes |
| `sitemaps_remaining` | `int` | yes | `20` | yes |
```

`First write` / `First read` are symbolic anchors — the helper or
branch, never a line number (see `_common/skill-conventions.md`'s "No raw line
numbers in prose" rule).

If the target has `do_not_typeify` classification (dynamic keys, or
the scout found no implicit state), this section is replaced by a
one-paragraph "Current shape is dynamic" note and the proposal skips
to section 10 (follow-on findings).

## 4. Proposed type definition

A complete, paste-ready code block. Include all imports, all nested
types, all fields with `default_factory` for mutable defaults.

```markdown
## Proposed type definition

New file: `core/services/agentic_discovery/state.py`.

\```python
"""Typed state for AgenticDiscoveryService.discover.

Converted from the implicit `state = {...}` dict by /extract-state-type.
"""
from dataclasses import dataclass, field


@dataclass
class BudgetState:
    pages_remaining: int = 100
    ai_calls_remaining: int = 30
    sitemaps_remaining: int = 20


@dataclass
class DiscoveryState:
    base_url: str
    site_name: str = ""
    include_sitemap_urls: bool = False
    iteration: int = 0
    budget: BudgetState = field(default_factory=BudgetState)
    sitemaps_found: list[str] = field(default_factory=list)
    url_patterns: list[dict] = field(default_factory=list)
    pages_checked: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return the state as a dict for callers that still consume the
        legacy shape. Remove once all callers migrate to attribute access.
        """
        return {
            "base_url": self.base_url,
            "site_name": self.site_name,
            "include_sitemap_urls": self.include_sitemap_urls,
            "iteration": self.iteration,
            "budget": {
                "pages_remaining": self.budget.pages_remaining,
                "ai_calls_remaining": self.budget.ai_calls_remaining,
                "sitemaps_remaining": self.budget.sitemaps_remaining,
            },
            "sitemaps_found": list(self.sitemaps_found),
            "url_patterns": list(self.url_patterns),
            "pages_checked": self.pages_checked,
            "errors": list(self.errors),
        }
\```
```

Rules for this block:

- **Every mutable default uses `field(default_factory=...)`.** No
  bare `= []` / `= {}`. Nested dataclass defaults use the class
  itself as the factory (`default_factory=BudgetState`) when the
  class's own defaults are valid; otherwise use a lambda.
- **Include a `to_dict()` method** iff at least one caller reads the
  dict (bucket `reads_return` in the profile's caller table). The
  method's docstring names the removal condition ("remove once all
  callers migrate").
- **Docstring names the source** — "Converted from the implicit
  `state = {...}` dict by /extract-state-type" — so a future reader
  can trace back.
- **Module name matches the convention** — see
  `knowledge/state-conventions.md`.

## 5. Migration plan

Numbered steps. Each step names the file it touches and (when
relevant) the test that pins the behavior.

```markdown
## Migration plan

1. **Add the type module.** Create
   `core/services/agentic_discovery/` package if it does not exist
   (move `agentic_discovery_service.py` into it and add a thin
   re-export shim per the Directory-packages convention). Create
   `core/services/agentic_discovery/state.py` with the code in
   section 4.
2. **Write characterization tests** (section 7). Must pass against
   the CURRENT implementation before any further edit.
3. **Update the target.** Replace `state = {...}` with
   `state = DiscoveryState(base_url=base_url, ...)`. Translate every
   `state['k']` to `state.k` and every nested `state['budget']['k']`
   to `state.budget.k`. Preserve every branch.
4. **Update private helpers.** Each of `_fetch_robots`,
   `_classify_sitemaps`, `_sample_candidate_urls`, `_compile_results`,
   `_should_continue`, `_report_progress`, `_ai_analyze_robots`,
   `_normalize_robots_analysis_urls`, `_call_llm`,
   `_absolute_url` updates its `state` parameter annotation to
   `DiscoveryState` and its body to attribute access.
5. **Update the return path.** `_compile_results` currently returns
   the dict verbatim; either (a) return `state.to_dict()` to
   preserve the caller contract, or (b) return the dataclass and
   update the two callers. Section 6 (caller table) picks one and
   cites why.
6. **Update callers** per section 6. Each row has an exact change.
7. **Re-run characterization tests.** They must pass unchanged — no
   test updates allowed in this phase.
8. **Remove the legacy `to_dict()`** once all callers migrate to
   attribute access. This can be a follow-up commit.
```

The plan is **not** a rewrite of the target; it is a sequence of
edits that preserves behavior and changes the shape.

## 6. Caller table

One row per caller file with the exact change required.

```markdown
## Caller table

| Caller | Kind | Keys touched | Change |
|---|---|---|---|
| `core/views/sitemaps.py:RunAgenticDiscoveryView.post` | `reads_return` | `sitemaps`, `patterns`, `samples`, `errors` | No change if target returns `state.to_dict()`. If target returns `DiscoveryState`, switch to attribute access: `result.sitemaps_found` etc. |
| `core/tasks.py:agentic_discovery_task` | `reads_return` | `sitemaps`, `errors` | Same as above |
```

Rules:

- **Every caller from `targets.json` appears** — no sampling. If the
  caller count exceeds 20, show the first 10 and summarize the rest
  by subsystem (one row per subsystem).
- **Callers marked `mutates` or `constructs`** get a dedicated paragraph
  below the table describing the construction site's changes — those
  are migration-heavy and can't fit in a row.
- **Change-cost column** is implicit in the Change cell's wording
  (one-line = low; multi-step = medium; "restructure" = high). If
  more than two callers are medium/high, the Summary flags the cost
  up front.

## 7. Characterization tests

Describe (do NOT write) the test shape `/fix-workflow` must write at
its Phase 2.1, BEFORE touching the target. Four labeled paragraphs:

```markdown
## Characterization tests

**Input fixture.** One `SiteConfig` row for a known site
(reuse `tests.test_agentic_discovery.setUpTestData`), seeded
`ProxyPlatform` with a mocked ScraperAPI key, `base_url` pointing at
a fixture HTML file served via `unittest.mock` of `requests.get`.
Budget caps set to their defaults.

**Observable output.** The test pins the exact dict keys in the
return value and the values for two of them: `sitemaps` length > 0,
`errors` == []. For a new dataclass return, pin
`result.sitemaps_found` + `result.errors` with the same semantics.

**Side-effect observation.** The test asserts that the
`progress_callback` mock was invoked ≥3 times (one per phase) with
dicts whose key set includes `phase` and `detail`. It does NOT pin
the exact phase strings — those are incidental.

**Mocks required.** `openai.OpenAI.chat.completions.create` returns
a canned sitemap classification. `requests.get` returns the fixture
HTML for `robots.txt` and two sitemaps. No DB mocks beyond the
`setUpTestData` rows. No Celery dispatch — the target is a direct
method call.
```

This section is **non-optional**. If the scout couldn't design a
test shape (rare — only happens when the target has no observable
behavior), the proposal notes that and warns that `/fix-workflow`
will block at Phase 2.1.

## 8. Test matrix

Derived from `_common/skill-conventions.md`'s baseline plus the per-file table.
For the discovery subsystem:

```markdown
## Test matrix

Baseline (from `_common/skill-conventions.md`):

\```bash
.venv/bin/python manage.py test \
  tests.test_site_capabilities tests.test_hydration_detector \
  --settings=app.settings_test_sqlite -v 2
\```

Subsystem-specific (from the File(s) touched table, for
`core/services/discovery_*.py`):

\```bash
.venv/bin/python manage.py test \
  tests.test_discovery_field_matcher \
  tests.test_agentic_discovery \
  tests.test_run_discovery_limits \
  --settings=app.settings_test_sqlite -v 2
\```

Characterization test (new module, per section 7):

\```bash
.venv/bin/python manage.py test \
  tests.test_agentic_discovery_state \
  --settings=app.settings_test_sqlite -v 2
\```
```

Always include both baseline and subsystem-specific blocks. The
characterization block is only present if section 7 names a new test
module; if it extends an existing module, fold the command into the
subsystem-specific block.

## 9. Stop condition

A checklist — `/fix-workflow` (or the human executor) checks each
box before declaring the migration complete.

```markdown
## Stop condition

- [ ] `core/services/agentic_discovery/state.py` exists and passes
      `ruff check`.
- [ ] `AgenticDiscoveryService.discover` uses `DiscoveryState`;
      the string `state = {` no longer appears in the function body.
- [ ] Every private helper accepts `state: DiscoveryState` and uses
      attribute access. (Grep: `state\[` inside
      `agentic_discovery_service.py` returns zero matches.)
- [ ] All callers listed in section 6 updated; their own test
      modules pass.
- [ ] Characterization tests from section 7 pass unchanged.
- [ ] `/find-implicit-state` re-run on the target file shows zero
      `implicit_dict_state` hits. (When that sub-shape ships;
      until then, this checkbox is aspirational.)
- [ ] Baseline test matrix (section 8) passes.
- [ ] Subsystem test matrix (section 8) passes.
```

Every checkbox is **observable** — a human or CI can verify it
without reading the proposal's prose. Subjective checkboxes ("code
is cleaner") do not belong here.

## 10. Follow-on findings

One-line entries for adjacent candidates surfaced during profiling.

```markdown
## Follow-on findings

- `core/services/field_extraction_compiler.py::compile` appears to
  own a similar implicit state dict (`compiler_state`); candidate
  for `/extract-state-type core/services/field_extraction_compiler.py::compile`.
- `AgenticDiscoveryService._call_llm` is one of the
  `keep_separate_document_why` shadows from `/find-semantic-duplication`
  (SC-3 family); already tracked there — no action here.
- `state['errors']` is written from four helpers but only read from
  `_compile_results`; after migration, consider replacing with a
  dedicated `ErrorLog` helper class. Not a blocker.
```

Omit the section entirely if nothing adjacent surfaced. Empty
sections are noise.

## 11. Authorization

One line, always present.

```markdown
## Authorization

Human review required before `/fix-workflow extract-state-type:agentic_discovery_service__discover`
or manual execution. The proposal is read-only; any correction is
re-run, not hand-edit.
```

## Worked example (tiny target)

For a hypothetical `core/services/example_service.py::ExampleService.run`
that owns a 3-key mutable state dict with one caller:

```markdown
# Proposal — extract-state-type — example_service__run

| Field | Value |
|---|---|
| Target | `core/services/example_service.py::ExampleService.run` |
| Slug | `example_service__run` |
| Shape | `@dataclass` |
| Dict variable (before) | `state` |
| Top-level fields | 3 |
| Nested shapes | 0 |
| Callers | 1 |
| Regenerated | 2026-04-19T23:45:00Z |

## Summary
`ExampleService.run` threads a three-key dict through two helpers.
The proposal converts it to a `@dataclass ExampleState` in
`core/services/example/state.py`. `@dataclass` applies because the
helpers mutate the state in place. One caller reads the return value
as a dict and needs a `to_dict()` call. This proposal does not
rewrite the helpers — their edits fall out of the dataclass
mechanically.

## Current shape (implicit dict)
| Key | Type | Required | Default | Mutated | First write | First read |
|---|---|---|---|---|---|---|
| `counter` | `int` | yes | `0` | yes | `run` setup | `_helper_one` |
| `items` | `list[str]` | no | `[]` | yes | `run` setup | `_compile` |
| `done` | `bool` | yes | `False` | yes | `_helper_two` | `run` exit check |

## Proposed type definition
New file: `core/services/example/state.py`.

\```python
from dataclasses import dataclass, field

@dataclass
class ExampleState:
    counter: int = 0
    items: list[str] = field(default_factory=list)
    done: bool = False

    def to_dict(self) -> dict:
        return {"counter": self.counter, "items": list(self.items), "done": self.done}
\```

## Migration plan
1. Add `state.py`.
2. Write characterization test (section 7).
3. Replace `state = {...}` with `state = ExampleState()` in `run`.
4. Convert helper signatures + bodies to attribute access.
5. `run` returns `state.to_dict()` to preserve caller contract.
6. Update caller per section 6.
7. Re-run characterization test (must pass unchanged).
8. Follow-up commit removes `to_dict()` when caller migrates.

## Caller table
| Caller | Kind | Keys touched | Change |
|---|---|---|---|
| `core/views/example.py:ExampleView.get` | `reads_return` | `counter`, `done` | No change (returned dict shape preserved via `to_dict()`) |

## Characterization tests
**Input fixture.** One unit-test row; no external services.
**Observable output.** Pin `result['counter'] == 3`,
`result['done'] == True`.
**Side-effect observation.** None.
**Mocks required.** None.

## Test matrix
Baseline + `tests.test_example` (new module) + `tests.test_example_state`
(new, for the dataclass fixture).

## Stop condition
- [ ] `state.py` exists.
- [ ] `run` uses `ExampleState`.
- [ ] Caller unchanged (return shape preserved).
- [ ] New characterization test passes.
- [ ] Baseline + subsystem tests pass.

## Authorization
Human review required before `/fix-workflow extract-state-type:example_service__run`.
```

## Rendering rules

- **UTC timestamps** in the metadata table. `YYYY-MM-DDTHH:MM:SSZ`.
- **Tables use right-alignment on numeric columns** where possible.
- **Every key, helper, caller, branch cited by symbolic name** —
  never a raw line number.
- **Section headings are `##`** (or `###` for nested shapes). No
  deeper nesting.
- **If a section would be empty AND the scout ran without error,
  omit the section header entirely.** Empty sections are noise. The
  exception: **Characterization tests**, **Stop condition**, and
  **Authorization** are always present.
- **Code blocks specify the language** (```python, ```bash).
- **The proposal does NOT embed the full current function body** —
  the reader can open the file. The proposal is about the contract,
  not the code bytes.
- **Never include an emoji.** See repo-wide convention in CLAUDE.md.
