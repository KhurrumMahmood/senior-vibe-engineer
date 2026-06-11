# False positives — patterns that look like duplication but aren't

## Layout utility clusters

`flex items-center justify-between`, `grid grid-cols-2 gap-4`,
`flex-1 min-w-0` — these are Tailwind atoms. Their re-occurrence is
not duplication. The collapse stage marks them `category:
layout-utility` and the rank stage downgrades them to `skip`. If a
class-chain bucket is dominated by these, recommend
`skip_coincidental`.

## Form-input chains

`.form-input` is the canonical form-input class
(`docs/canonical-patterns.md`). Templates often inline both
`.form-input` and additional Tailwind classes like `text-xs`, `w-32`,
or `mt-2`. The combined chain looks duplicated but the duplication is
inherent to per-form sizing — it's not a primitive candidate. Skip.

## Module-local lifecycle entry points

Cotton primitives and a few `static/js/*.js` modules wrap themselves
in IIFEs:

```js
(function () {
    function init() { /* per-module setup */ }
    function close() { /* per-module teardown */ }
    document.addEventListener('DOMContentLoaded', init);
})();
```

The helper scanner reports `init()`, `close()`, `open()`, `start()`,
`initialize()` defined in 5+ files. **This is not a fork** when the
function is genuinely IIFE-scoped — there's no global name collision.
Recommend `skip_module_local` for these.

**Important — verify the IIFE actually exists.** Several
`static/js/site-config-*.js` files (e.g. `site-config-images.js`,
`site-config-pages.js`) are NOT IIFE-wrapped — they're top-level
globals where `function _foo()` declares `window._foo`. The helper
scanner can't tell from the function declaration alone; the
explanation step has to read the file structure. If two files declare
the same top-level `function _foo()`, the second one wins via
last-loaded-wins — a real fork, not a module-local pattern.

Real forks (consolidate, don't skip):
- Top-level `function init() {}` — global pollution.
- A function whose name signals a **shared utility** rather than a
  lifecycle hook, defined in 2+ files with similar bodies. Confirmed
  examples: `escapeHtml`, `getCookie`, `siteEndpoint`, `csrfFetch`,
  `_setLoading`, `_fmt`, `_setMessage`. The list isn't closed —
  utility-shaped names (`format*`, `parse*`, `_do*`, anything ending
  in `Helper`) should be evaluated on body, not name alone.
- The **leading underscore is not a scope shield**. `_setLoading`
  reads as "module-private by convention" but in a non-IIFE file it's
  a flat global, and even inside an IIFE it's just a private name —
  identical bodies in two modules is still duplication. Consolidate to
  `SiteConfigCore._helper` and forward.

## Idempotent init guards

`static/js/app-dialog.js` and `templates/cotton/user_menu.html`
intentionally re-run their init logic via:

```js
if (window.__appDialogInit) return;
window.__appDialogInit = true;
```

This is a doctrine pattern — every cotton primitive carrying JS
follows it. Multiple files defining the same idempotent-init shape are
**doctrine compliance**, not duplication.

## Status-icon ladders

`<i class="fas fa-check-circle text-green-500"></i>` /
`<i class="fas fa-times-circle text-red-500"></i>` — different tone
encodes different meaning (success vs. error). The class chains
collide under tone-normalization (`fas fa-check-circle
text-{tone}-500`) but the meaning is encoded by the tone choice
itself. Extracting a `<c-status-icon tone="..." kind="..."/>`
primitive is doctrine-defensible only if the codebase consistently
uses the same icon-name for each tone — verify before recommending.

## Modal lookalikes that aren't modals

`fixed inset-0 z-40 bg-black opacity-30` is sometimes used as a
**page-loading overlay**, not a modal. Same class chain, different
intent. Read the markup: if there's a spinner inside and no
content-panel sibling, it's a loading overlay, not a modal. Skip.

## Repeated `tone` declarations across templates

Some templates intentionally hard-code their tone for branding (e.g.
the AGS site card always uses `border-red-200`). Tone-normalized
buckets group these with other tone-variant cards, producing
artificially high counts. Read 2-3 occurrences before recommending —
if every site has its own tone fixed by domain, the variation is
intentional. Skip or recommend a `tone` prop on the existing primitive.
