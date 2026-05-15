# Extraction thresholds

When does a class-chain bucket or markup pattern actually warrant a
cotton primitive vs. just being "Tailwind being Tailwind"?

## The three-callsite, two-template rule

A new cotton primitive should land **only** when:

1. **3 or more structural occurrences** of the pattern exist across
   `templates/`. Class-chain count alone is insufficient — what
   matters is the *role* (alert frame, pill chip, modal panel) being
   repeated.
2. The occurrences span **2 or more separate template files**. Three
   variants of the same shell within one page are usually a local
   pattern, not a primitive candidate.
3. The structure is **stable**: same wrapping element shape (`<div>` /
   `<span>` / `<button>`), same nesting (single-slot vs. titled-with-
   actions), same control flow (`{% if %}` branches don't differ
   meaningfully across callsites).

If any of these is missing → recommend `skip_intentional` or
`skip_coincidental`.

## What is *not* a primitive candidate

- **Layout utility chains.** `flex items-center justify-between`
  appears in 30+ files because that's how every flex container sits.
  These are Tailwind atoms, not extractable shells. The collapse stage
  already classifies them as `category: layout-utility` and the rank
  stage skips them.
- **Form-field labels.** `block font-medium text-sm text-gray-700`
  matches the Tailwind UI form-label convention. Extracting this would
  be a `<c-field-label>` — defensible if it gains a `required` flag, a
  help-tip slot, or other prop. Otherwise extraction adds indirection
  without value.
- **Spinner snippets.** `fa-spin fa-spinner fas mr-2` — a 4-token
  inline icon. A `<c-spinner/>` only earns its keep if it adds
  state-aware variants (idle/active/error tones).
- **Single-page widgets.** A bespoke chart legend used once does not
  belong in `templates/cotton/`. Cotton primitives are *cross-page*
  primitives.

## What *is* a primitive candidate

- **Modal shells.** `fixed inset-0 z-50 ... bg-black opacity` overlays
  are duplicated across multiple templates with the same close-button
  and content-panel structure. These warrant a `<c-modal>` (overlay +
  panel + close + size). 5+ instances across 3+ templates is enough.
- **Pill chips.** `bg-{tone}-100 text-{tone}-800 rounded-full px-2.5
  py-0.5 inline-flex` is the Tailwind UI badge convention. The repo
  already has `<c-pill/>` — bypasses are an `adopt_existing` finding.
- **Alert frames.** `bg-{tone}-50 border-{tone}-200 rounded-lg`
  wrapping a leading icon and a message. Already covered by
  `<c-alert/>`.
- **Dropdown menus.** `absolute right-0 mt-2 ... shadow-lg ring-1
  ring-black ring-opacity-5 z-50` — only `<c-user-menu/>` exists for a
  narrow case. A general `<c-dropdown/>` is justified once 4+ generic
  dropdowns exist.
- **Filter pills with active/inactive state.** Found ~14× in the
  audit, with a stateful `is-active` toggle. A `<c-filter-pill
  active="..."/>` would absorb them.

## Adopt-existing vs. extract-new

When `primitive_bypass: true`:

- The existing primitive covers the bypass → **adopt_existing**.
- The bypass uses a prop the primitive doesn't support → either
  **extend the primitive** (preferred — single PR adding the prop +
  migrating callsites) or **extract_new_primitive** if the prop space
  has diverged so far that one component would carry two distinct
  variants. Doctrine prefers extension over fork.

## When to recommend `defer_doctrine_violation`

Cotton's API constraints (declared `<c-vars>` props, `{{ attrs }}`
pass-through, no Python in templates beyond Django syntax) cannot
express:

- Components that need *runtime configuration objects* — these belong
  in JS modules with template containers, not in cotton.
- Components with *recursive composition* (a tree of identical nodes)
  — django-cotton doesn't support recursive includes cleanly.
- Components that require *more than one named slot* with
  state-dependent rendering — possible but ugly; defer until cotton
  upgrades.

If the candidate hits one of these, recommend `defer_doctrine_violation`
and propose a different consolidation surface (a JS module, a Django
template tag, a partial template).
