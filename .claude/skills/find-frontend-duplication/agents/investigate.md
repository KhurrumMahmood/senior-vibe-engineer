# Scout brief — investigate a frontend duplication candidate

This file is a **prompt template** the orchestrator expands and sends to a
sub-agent. Placeholders are double-brace `{{name}}`. The orchestrator fills
them in and calls `Agent(subagent_type="general-purpose", prompt=<expanded>)`.

Fresh sub-agent, no prior context. Everything the scout needs to act on the
candidate is either inline below or in three knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are investigating **one** frontend-duplication candidate in this
codebase so the main orchestrator can decide whether to dispatch an
extraction. You are not extracting anything. You are not editing
templates or JS. You produce a classification JSON file and nothing
else.

### Candidate to investigate

```json
{{candidate_json}}
```

Project root (absolute): `{{project_root}}`
Write your output here: `{{output_path}}`

### Knowledge you MUST consult

In this order:

1. `{{skill_root}}/knowledge/extraction-thresholds.md` — when does a
   class-chain bucket actually warrant a cotton primitive vs. just being
   "Tailwind being Tailwind". The threshold rule (3+ callsites across
   2+ templates with stable structure) is **mandatory** before
   recommending an extraction.
2. `{{skill_root}}/knowledge/false-positives.md` — repeated layout
   atoms (`flex items-center justify-between`), Tailwind utility
   clusters, and template structures that LOOK duplicated but encode
   genuinely different intent.
3. `{{skill_root}}/knowledge/` (host-project overlay) — known canonical
   primitives (AppDialog, SiteConfigCore, .form-input class,
   c-pill / c-alert / c-card), the cotton-components doctrine, and the
   `<c-vars>` / `{{ attrs }}` conventions a new primitive must follow.

### Investigation steps (in order)

**1. Inspect the cotton inventory.** The candidate JSON includes
`existing_primitive` if a cotton primitive matches the category. Read
`{{project_root}}/templates/cotton/<name>.html` to understand the
existing primitive's prop shape. If `primitive_bypass` is `true`, the
recommendation will be **adopt-existing** unless the bypass exists
because the primitive doesn't cover a real prop the bypass needs.

**2. Read the actual occurrence sites.** The candidate evidence has up
to 8 sample occurrences. Read each cited file at the cited line, plus
~10 lines of surrounding markup, to confirm the duplication is
structural (same role, same wrapping, same intent) and not just
class-chain-coincidental.

**3. Verify the duplication is structural, not incidental.** Two
elements with the same Tailwind class chain may serve different
structural roles. Apply this test:

- *Same role* (both are alert frames, both are pill chips, both are
  modal panels) → real duplication
- *Different role, coincidental class match* (a card is using
  `bg-white rounded-lg shadow` and so is an unrelated hover popover) →
  **skip_coincidental**

**4. Check JS partner code for helper-fork candidates.** For
`helper-fork` and `csrf-fetch` candidates, read each cited definition.
Distinguish:

- *True fork* — same function name, different bodies, called from the
  same external context. **extract_canonical**.
- *Module-local IIFE entry* — `init()` / `close()` / `start()` defined
  inside a top-level IIFE pattern. Each is correctly module-scoped.
  **skip_module_local**.
- *Different signatures, different bodies* — same name but unrelated
  semantics. **skip_name_collision**.

**5. Read the cotton-components doctrine.** Confirm a proposed new
primitive can satisfy the conventions: `<c-vars>` declaration,
`{{ attrs }}` pass-through, optional `tone` prop using Tailwind tone
families, idempotent JS init guard if the primitive carries scripts.
If the proposed primitive can't satisfy these conventions, recommend
**defer_doctrine_violation** and explain.

**6. Decide the recommendation.** Pick exactly one:

| recommendation | When |
|---|---|
| `adopt_existing` | An existing `<c-name/>` covers this. Migrate raw markup → primitive callsite. |
| `extract_new_primitive` | 3+ callsites across 2+ templates, stable structure, no existing primitive covers it. Hands off to `/extract-cotton-primitive`. |
| `extract_js_helper` | Helper-fork candidate where 2+ definitions are true forks. Hands off to a JS-helper consolidation (manual edit + lint). |
| `extract_csrf_wrapper` | Inline-CSRF candidate with stable shape across all callsites. Propose `App.csrfFetch`. |
| `skip_coincidental` | Class chain matches but structural role differs. |
| `skip_module_local` | Same-name JS function but each is correctly module-scoped IIFE. |
| `skip_intentional` | Repetition is doctrine-required (e.g. each form template has its own `.form-input` for a reason). |
| `skip_name_collision` | Same name, unrelated semantics. |
| `defer_doctrine_violation` | Extraction is desirable but cotton's `<c-vars>` / `{{ attrs }}` conventions can't capture this primitive's API cleanly. |

### Output contract

Write a single JSON file at `{{output_path}}` with this shape:

```json
{
  "id": "{{candidate_id}}",
  "investigation_status": "reviewed | skipped | defer",
  "recommendation": "<one of the values from the table>",
  "confidence": "low | medium | high",
  "rationale": "2-5 sentences citing file:line evidence — what you read, what convinced you",
  "blockers": "<short description, or null>",
  "next_skill": "extract-cotton-primitive | prevent-regression | null",
  "verified_files": ["templates/...", "static/js/..."]
}
```

Do not add keys beyond this schema. Do not wrap the JSON in markdown.

### Rules for your output

1. **Three-callsite rule is mandatory.** Single-callsite or
   double-callsite chains are **not** extractable — recommend
   `skip_intentional` or `skip_coincidental`.
2. **Read the markup before recommending.** Class-chain similarity
   alone is not enough. Two elements with the same chain but different
   structure are not duplication.
3. **For `primitive_bypass: true` candidates**, the recommendation
   should usually be `adopt_existing` — existing primitive coverage is
   a strong signal. If you recommend `extract_new_primitive` instead,
   you must cite a prop the existing primitive doesn't support.
4. **Helper-fork candidates with 6+ files require extra care.**
   `init()` and `close()` collisions are nearly always module-scoped
   IIFE patterns, not real forks. Read the surrounding 10 lines of
   each definition before calling it a fork.
5. **Keep rationale tight.** 2-5 sentences, with at least one
   `file:line` reference.

Do not print the JSON to your reply. Write it to `{{output_path}}` and
respond with at most two sentences confirming you wrote the file.
