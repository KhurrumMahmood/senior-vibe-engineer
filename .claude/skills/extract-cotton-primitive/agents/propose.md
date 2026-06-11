# Scout brief — propose a cotton primitive from profiled callsites

This file is a **prompt template** the orchestrator expands and sends to a
sub-agent. Placeholders are double-brace `{{name}}`. The orchestrator fills
them in and calls `Agent(subagent_type="general-purpose", prompt=<expanded>)`.

Fresh sub-agent, no prior context. Everything the scout needs is either
inline below or in two knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are designing **one** cotton primitive proposal for this codebase
so the main orchestrator can wrap it into a reviewable proposal.md.
You are not extracting anything. You are not editing
`templates/cotton/`. You produce one Markdown file and nothing else.

### Target

- Target slug: `{{target_slug}}`
- Category: `{{category}}`
- Profile JSON: `{{profile_path}}`
- Census JSON: `{{census_path}}`
- Project root (absolute): `{{project_root}}`
- Write your output here: `{{output_path}}`

### Knowledge you MUST consult

In this order:

1. `{{skill_root}}/knowledge/cotton-conventions.md` — every cotton
   primitive must satisfy `<c-vars>` declaration, `{{ attrs }}` root
   pass-through, the tone-prop pattern, idempotent JS init guards if
   carrying scripts, and named-slot conventions. Your proposal must
   pass every item in the doctrine compliance check; if it can't,
   recommend `defer_doctrine_gap` and explain.
2. `{{skill_root}}/knowledge/migration-patterns.md` — how to write the
   "before / after" callsite migration entries in a way the human can
   sanity-check without re-reading the original markup.

You should also Read:
- `{{project_root}}/templates/cotton/` — at least 2 existing primitives
  whose category is closest to your target (e.g. `card.html` and
  `pill.html`). Match their style: indentation, attribute ordering,
  comment density. **Do not invent new conventions.**
- The profile JSON's full callsite list (each has 30+ lines of
  surrounding markup).
- The candidate's `existing_primitive` field — if non-null, this is an
  **adoption** proposal, not an extraction. Section 4 of your output
  changes accordingly.

### Investigation steps (in order)

**1. Read the census.** The census JSON has the variant histogram
across every occurrence the candidate carries. Note:

- `dominant_variant` — the canonical token chain that wins the
  frequency rank. This is your **doctrine target** — the primitive's
  defaults must match this shape.
- `dominant_share` — the % of occurrences that match dominant.
  Anything < 0.6 sets `high_variance: true` and means the chain has
  no canonical shape; the proposal must call out that the sweep
  ships the strict shape and grandfathers the tail.
- `tail_count` — occurrences outside the dominant variant. These are
  the future "lint says yes but visual diff says no" callsites; flag
  them so the human knows what's deferred.
- `sample_only` — when true, the candidate has fewer per-occurrence
  rows than its full scan count. Treat dominance as a lower-bound and
  re-grep the chain across `templates/` before committing to a
  reconciliation call.

**2. Read the profile.** The profile JSON has up to 6 representative
callsites with surrounding markup. Identify:

- The **root element** shape — `<div>`, `<button>`, `<span>`, `<a>`?
- The **structural slots** — single `{{ slot }}` for body, or named
  slots like `{{ actions }}`, `{{ header }}`, `{{ footer }}`?
- The **prop axes** — what varies across callsites? Tone (color
  family)? Size (sm/md/lg)? Icon? Title? Subtitle? A boolean toggle?
- The **JS partner**, if any — does the markup carry `data-*`
  attributes or onclick handlers? Is there an init function in
  `static/js/` bound to it? Is it idempotent?

**3. Reconcile primitive defaults against the dominant variant.**
This is the Phase G `<c-alert>` lesson encoded as a step:

- **New primitive** — design the body's class string to match the
  `dominant_variant` token set. If your proposed defaults differ from
  dominant (e.g. dominant is `p-4` but you proposed `px-4 py-3`),
  rewrite the proposal to use dominant. The fact that one outlier
  callsite uses `px-4 py-3` is not a reason to set the *default*
  there — outliers ride `{{ attrs }}` class-merge.
- **Existing primitive** (when `existing_primitive` is non-null) —
  read the primitive's current body and compare its class string to
  `dominant_variant`. If they match, your recommendation is
  `adopt_existing_primitive`. If they diverge (the primitive was
  extracted from a non-dominant subset), your recommendation is
  `change_primitive_defaults_first`: ship the default change as its
  own PR, then the migration sweep is a follow-up.

**4. Decide the API surface.** A good cotton primitive has 0-4
required props and 0-6 optional props. If you find yourself proposing
8+ props, the primitive is doing too much — split it into two or
recommend `defer_doctrine_gap`.

**5. Detect structural variations the primitive must absorb.** If
half the callsites have a header and half don't, the header should be
optional (`{% if title or subtitle %}` block in the body, like
`<c-card/>`). If the variations are mutually exclusive (some are
buttons, some are anchors), use a single `as` prop or split into two
primitives.

**6. Write the migration table.** For each profiled callsite, show:
- the **before** snippet (raw markup, ~5-10 lines)
- the **after** snippet (`<c-name ... />` callsite)

Show every profiled callsite. The orchestrator will paste these
verbatim into proposal.md.

**7. Propose a lint name.** After the primitive lands, regressions
must be blocked. Propose a lint name like `no_inline_modal`,
`no_inline_dropdown`, `no_inline_filter_pill`. The lint detection
shape (regex pattern, AST walk, etc.) goes in your output's "Lint
proposal" section. The orchestrator will not write the lint — that's
part of the execution PR.

### Output contract

Write a single Markdown file at `{{output_path}}` with this structure:

```markdown
# Cotton primitive: <c-name/> — `templates/cotton/<file>.html`

## Role
One paragraph: what is this primitive, what intent does it capture,
and why does it deserve to be its own component?

## Census summary
- Total occurrences: <scan_count> (sampled: <occurrences_in_sample>)
- Variants observed: <V>; dominant <dominant_share>% — `<dominant_variant>`
- Tail outside dominant: <tail_count> callsite(s)
- High variance: yes / no
- Sample-only: yes / no — if yes, note that dominance is a lower bound

## Primitive defaults reconciliation

State which of the three cases applies and justify in one paragraph:

- **Match** — proposed (or existing) defaults match the dominant
  variant. No pre-sweep doctrine change needed.
- **Drift — change defaults first** — existing primitive's defaults
  don't match the dominant variant. Migration sweep would force every
  callsite to override the default; ship the default change as its
  own PR first, then sweep. Show the diff between current and
  proposed defaults.
- **High variance — strict shape only** — dominant share < 60%; no
  canonical shape exists. Proposal ships the strict (dominant) shape
  and grandfathers the tail. State the tail count and what's deferred.

## API

\`\`\`html
<c-vars
    required_prop1
    required_prop2
    optional_prop1=""
    optional_prop2="default-value"
    :typed_prop="[]"
/>
\`\`\`

| Prop | Required? | Type | Default | Purpose |
|---|---|---|---|---|
| required_prop1 | yes | str | — | ... |
| optional_prop1 | no | str | "" | ... |

Default slot: <yes/no — what content goes here>
Named slots: <list, or "none">

## Body

\`\`\`html
<root-element {{ attrs }} class="...">
    {% if condition %}
    <header>...</header>
    {% endif %}
    {{ slot }}
</root-element>
\`\`\`

(Full body — match the indentation style of `<c-card/>`.)

## JS partner (if any)

If the primitive carries scripts, show the idempotent-init shape:

\`\`\`html
<script>
(function () {
    if (window.__appFooInit) return;
    window.__appFooInit = true;
    function init() {
        document.querySelectorAll('[data-foo]').forEach(...);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
</script>
\`\`\`

If no JS partner is needed, write "No JS partner — primitive is
purely presentational."

## Migration table

For each profiled callsite (every one — don't skip):

### `<file>:<line>` — <one-line role>

Before:
\`\`\`html
<full markup, 5-10 lines>
\`\`\`

After:
\`\`\`html
<c-name prop="value">slot content</c-name>
\`\`\`

## Doctrine compliance check
- [ ] `<c-vars>` declared — yes/no
- [ ] `{{ attrs }}` pass-through on root — yes/no
- [ ] Tone prop using `{tone}-` Tailwind family — yes / no / N/A
- [ ] No raw `alert()` / `confirm()` / `prompt()` in JS — yes / N/A
- [ ] Idempotent JS init guard if scripts present — yes / N/A
- [ ] 3+ callsites across 2+ templates — yes (<N> across <K>)

## Lint proposal

After this primitive lands, add a diff-scoped lint:

- **Name:** `no_inline_<category>`
- **Detection shape:** <regex / AST pattern>
- **Allow-list:** the primitive itself, plus `# noqa: no-inline-<category>: <reason>` for legitimate exceptions
- **Path:** `scripts/lint/no_inline_<category>.py`

## Recommendation

Pick exactly one:

| recommendation | When |
|---|---|
| `extract_new_primitive` | Profile satisfies threshold, doctrine compliant, defaults match census dominant variant. |
| `extend_existing_primitive` | Existing primitive almost covers it — add a prop instead. Specify which prop. |
| `adopt_existing_primitive` | Existing primitive already covers it AND its defaults match the dominant variant. Migration table is the entire deliverable; no new primitive file. |
| `change_primitive_defaults_first` | Existing primitive covers the case but its defaults diverge from the census dominant variant. The proposal is to update the primitive's defaults as a standalone PR; the migration sweep is a follow-up `/extract-cotton-primitive` invocation after the default change lands. |
| `defer_low_callsite_count` | <3 callsites, or <2 templates. Skill should not have been invoked; proposal is the abort note. |
| `defer_doctrine_gap` | Cotton's `<c-vars>` / slot model can't capture this primitive cleanly. Explain. |

## Follow-on findings

If profiling surfaced *separate* primitive opportunities (e.g. the
modal panel and modal close-button could each be their own
primitive), list them here as one-line entries. Each is a future
`/extract-cotton-primitive` invocation.
```

### Rules for your output

1. **The `<c-vars>` shape must match an existing primitive's style.**
   Read `templates/cotton/card.html` and `templates/cotton/pill.html`
   before writing. Match indentation (4 spaces), attribute ordering
   (required first, then optional, then `:typed`), and quote style
   (double quotes).
2. **Migration entries must be verbatim.** The "before" snippet is
   pasted from the profile, not reconstructed. The "after" snippet
   uses cotton's exact callsite syntax — `<c-name prop="value">slot
   content</c-name>` for default-slot, `<c-name>...content...</c-
   name>` for nested.
3. **Skip nothing in the migration table.** If 6 callsites are
   profiled, all 6 must appear. The human reviewer reads them all.
4. **Don't propose props that aren't observed in the callsites.**
   Speculative props ("maybe someone will want a `disabled` prop one
   day") are a doctrine violation. Only props the profiled callsites
   demonstrate.
5. **If `existing_primitive` is non-null on the candidate**, walk
   the three-step decision tree:
   1. Read the existing primitive's body and compare its class string
      to `census.dominant_variant`. **Re-canonicalize the primitive's
      class string before comparing** — strip `{{ tone }}` /
      `{{ size }}` placeholders to `{tone}` / `{size}` and re-run the
      same canonicalization the census did (sort + dedup tokens, tone
      collapse). The census variant is `bg-{tone}-50 p-4`; the
      primitive's raw template is `bg-{{ tone }}-50 p-4`. They match
      only after re-canonicalization.
   2. If they match → `adopt_existing_primitive` (unless a prop is
      missing, in which case `extend_existing_primitive`).
   3. If they diverge → `change_primitive_defaults_first`. Show the
      current vs proposed defaults in the reconciliation section.
      Adoption proceeds *after* the default change lands.

Do not print the Markdown to your reply. Write it to `{{output_path}}`
and respond with at most two sentences confirming you wrote the file.
