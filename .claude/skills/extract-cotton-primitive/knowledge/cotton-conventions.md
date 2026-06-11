# Cotton primitive conventions

This is the authoritative checklist a new `templates/cotton/<name>.html`
must satisfy. Every item below is doctrine — the proposed primitive
fails the doctrine compliance check if any item is missing or
violated.

## 1. `<c-vars>` declaration

Every primitive starts with a `<c-vars>` line declaring its props.
Pattern:

```html
<c-vars
    required_prop1
    required_prop2
    optional_with_default="default-value"
    empty_optional=""
    :typed_optional="[]"
/>
```

Rules:
- Required props have no `=` and no value.
- Optional string props have `=""` or `="default"`.
- `:` prefix means Python-evaluated (`:actions="[]"`, `:items="[1,2,3]"`).
- Indentation: 4 spaces, one prop per line if the declaration spans
  multiple lines. Inline form is fine for ≤3 props (`<c-vars
  tone="gray" icon="" />`).
- Required props come first, then optional, then `:typed`.

## 2. `{{ attrs }}` pass-through on the root element

The root element of the body MUST include `{{ attrs }}` so callsites
can layer their own classes / `data-*` attributes / `id` onto the
component without wrapping it.

✅ `<div {{ attrs }} class="bg-white shadow rounded-lg">`
✅ `<button {{ attrs }} type="button" class="...">`
❌ `<div class="bg-white shadow rounded-lg">` — no pass-through
❌ `<div class="bg-white {{ attrs }} shadow">` — `{{ attrs }}` must be
   a standalone attribute group, not inside `class=""`

## 3. Tone-prop convention for color variants

Color variants are exposed via a `tone` prop that interpolates into
Tailwind's tone families. Default to `gray` or `blue`:

```html
<c-vars tone="gray" />

<div {{ attrs }} class="rounded-lg bg-{{ tone }}-100 text-{{ tone }}-800">
```

Don't accept arbitrary color tokens like `tone="red-500"` — accept
only the family name (`red`, `blue`, `green`, ...) and let the
primitive choose the shade. This keeps the API minimal and matches
existing primitives (`<c-pill tone="green">`, `<c-alert tone="red">`).

## 4. Default slot for body content

Use `{{ slot }}` for the default body. If the primitive has a
required-content area (e.g. an alert message), `{{ slot }}` is the
right home.

## 5. Named slots for optional secondary content

When the primitive needs a *separate* content region (e.g. a card with
both body and an action buttons row), use a bare named-slot reference:

```html
<div {{ attrs }} class="...">
    {% if title or subtitle %}
    <header>
        <h3>{{ title }}</h3>
        {% if subtitle %}<p>{{ subtitle }}</p>{% endif %}
    </header>
    {% endif %}
    {{ slot }}
    {% if actions %}<footer>{{ actions }}</footer>{% endif %}
</div>
```

Callsite:

```html
<c-card title="Settings">
    <c-slot name="actions">
        <button>Save</button>
    </c-slot>
    Body content here.
</c-card>
```

Rules:
- Named slots are *bare* `{{ name }}` in the body.
- Wrap with `{% if name %}` so callsites without that slot render
  cleanly.
- Cap at 2 named slots. More slots = doctrine gap.

## 6. Idempotent JS init guard

If the primitive carries a `<script>` block, the init shape MUST be:

```html
<script>
(function () {
    if (window.__appFooInit) return;
    window.__appFooInit = true;
    function init() {
        document.querySelectorAll('[data-foo]').forEach(function (root) {
            if (root.dataset.fooBound === '1') return;
            root.dataset.fooBound = '1';
            // ... per-instance binding
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
</script>
```

Required:
- `window.__app<Name>Init` guard against re-running init when the
  primitive renders multiple times on the same page.
- `data-foo-bound="1"` per-instance guard against re-binding the same
  DOM node.
- Bind by `data-*` attribute, not by `id` (multiple instances on a
  page).
- IIFE wrapper so internal helpers don't leak.
- DOMContentLoaded handling for early-loaded scripts; immediate call
  for late-loaded.

See `templates/cotton/user_menu.html` for the canonical example.

## 7. No raw native dialogs in JS partner

If the primitive's JS partner needs to confirm / prompt / toast, use
`AppDialog`:

```js
AppDialog.confirm({ message: 'Delete this item?' }).then(function (ok) { ... });
AppDialog.toast({ tone: 'success', message: 'Saved.' });
```

NOT `confirm()`, `alert()`, or `prompt()`. The `native-dialogs` lint
blocks these.

## 8. Class-chain style

Match existing primitives' class-chain style:
- Tailwind utilities ordered roughly: layout → spacing → typography →
  color → effects.
- One class chain per element. Don't split via `{% if %}` unless the
  variant is structurally different (e.g. `<c-user-menu variant="...">`
  has two distinct chains for `light` vs default; both are reasonable).
- Keep chain length ≤12 tokens per element. Longer chains signal the
  primitive is doing too much.

## 9. No production code in templates beyond Django syntax

Cotton primitives are templates — they can use `{% if %}`, `{% for %}`,
`{{ var }}`, but NOT custom template tags that aren't already loaded
in the project. If the primitive needs more logic than `if` and `for`,
the logic belongs in the calling view's context, not in the primitive.

## 10. File naming

Filename → callsite name:
- `templates/cotton/foo_bar.html` → `<c-foo-bar />`
- Underscores in filenames become hyphens in callsite tags.
- Use lowercase + underscores, no camelCase or PascalCase.

## Doctrine gaps that justify `defer_doctrine_gap`

If the proposed primitive would need any of:
- 3+ named slots
- Conditional slot rendering based on slot content presence (cotton
  doesn't support `{% if slot has content %}`)
- Recursive composition (a tree of identical primitives)
- Runtime-injected configuration objects beyond simple props

…then recommend `defer_doctrine_gap` in the proposal. Don't try to
hack around it; cotton's expressiveness has a ceiling and the codebase
deserves to know when that ceiling is hit.
