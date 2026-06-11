# Migration patterns — writing the before/after table

For each profiled callsite, the migration table entry shows two
snippets: the **before** (raw markup currently in the template) and
the **after** (the cotton primitive callsite that replaces it).

The human reviewer will paste the after snippets into the actual
templates during execution, so they must be exact, including
whitespace, attribute order, and any preserved per-callsite specifics.

## Before snippet — verbatim from the profile

The "before" is *literal* markup from the cited line and ~5-10 lines
of context. Don't reformat. Don't strip blank lines. Don't fix
inconsistent indentation. Whatever the file actually contains, that's
what the human will be replacing.

Read the `context_before`, `highlight`, and `context_after` fields of
the profile callsite and reconstruct the original block.

## After snippet — exact cotton callsite

The "after" snippet uses cotton's standard callsite shape.

### Default-slot only

```html
<c-pill tone="green">Active</c-pill>
```

### Default slot with multiline body

```html
<c-card title="Settings" subtitle="Configure your account">
    <p>Body content...</p>
    <p>More body content...</p>
</c-card>
```

### Named slot

```html
<c-card title="Settings">
    <c-slot name="actions">
        <button class="...">Save</button>
        <button class="...">Cancel</button>
    </c-slot>
    Body goes here.
</c-card>
```

Rules:
- Use `<c-name>` not `<c-name />` when there's a default slot body.
- Use `<c-name />` (self-closing) only when both default and named
  slots are unused.
- Named slots use `<c-slot name="...">...</c-slot>`.
- Indent body content one level deeper than the cotton tag.

## When to preserve per-callsite specifics

Some attributes from the original markup don't fit any prop and
should pass through via `{{ attrs }}`:

- `id="something-specific"` — passes through
- `data-test-id="..."` — passes through
- `aria-*` attributes that aren't part of the primitive's contract — pass through
- A specific `class` token that adds page-specific positioning (e.g.
  `mt-4`) — passes through

Cotton's `{{ attrs }}` will merge these onto the root element. The
after snippet should show them at the cotton tag:

```html
<!-- before -->
<div id="settings-card" class="mt-4 bg-white shadow rounded-lg p-6">
    Body content
</div>

<!-- after -->
<c-card id="settings-card" class="mt-4">
    Body content
</c-card>
```

(The primitive's body absorbs `bg-white shadow rounded-lg p-6` since
those are doctrine; only the page-specific `mt-4` and `id` survive on
the callsite.)

## When the per-callsite specifics don't fit the primitive

If a callsite has structural deviation that can't be expressed via the
primitive's props or `{{ attrs }}` (e.g. an extra `<div>` wrapping
the entire thing for some legacy reason), record it as
`structural_deviation` in the migration table and recommend either:

1. **Drop the deviation** — if it's incidental, the migration removes
   it and the human verifies in PR review.
2. **Skip this callsite** — exclude it from the migration; leave the
   raw markup in place. Note in the proposal that the callsite is
   "structurally distinct from the others."

Don't propose primitives with a `wrap_in_extra_div` boolean prop just
to absorb one outlier — that's a doctrine smell.

## CSRF / event-handler attributes

If the original markup has `hx-post="..."`, `onclick="..."`, or
`x-data="..."` (Alpine, HTMX, Tailwind UI snippets), those pass
through via `{{ attrs }}`:

```html
<!-- before -->
<button onclick="openSettingsDialog()" class="inline-flex items-center px-3 py-2 ...">
    Open Settings
</button>

<!-- after -->
<c-button onclick="openSettingsDialog()">Open Settings</c-button>
```

(Assuming `<c-button>` exists; otherwise use whichever button
primitive you proposed.)

## Sanity checks for each migration entry

For each before/after pair, confirm:

- [ ] After snippet uses an existing or proposed `<c-*>` tag.
- [ ] All required props are populated.
- [ ] Optional props that differ from the default are populated.
- [ ] Default slot content matches the before snippet's body content.
- [ ] Named-slot content matches the before snippet's secondary
      content blocks.
- [ ] Per-callsite specifics (id, data-*, page-specific classes) are
      passed through.
- [ ] No doctrine prop (e.g. tone-shade combinations the primitive
      hard-codes) is being asserted in `{{ attrs }}` to override the
      primitive's defaults — that's a smell.

If any check fails, the migration entry needs revision before the
proposal is reviewable.
