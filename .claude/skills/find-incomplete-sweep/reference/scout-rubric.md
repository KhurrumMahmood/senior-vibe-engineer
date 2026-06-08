# Scout rubric — judge one incomplete-sweep packet

You are judging **one** gated-in finding from `/find-incomplete-sweep`. The
deterministic detector already proved (a) a strong majority of a callee's call
sites pass kwarg `K` and one straggler does not, and (b) the kwarg-present
siblings were git-touched *after* the straggler (sweep-trajectory). Your job is
the one thing the script cannot decide: **is the straggler a forgotten site, or
a divergence that is correct by nature?**

You are given a packet: the straggler's code window (`>>` marks the call line),
1–2 present-site windows, and the divergence metadata. **Judge from the packet.**
Read the callee's definition only if you must confirm whether `K` has a default.

## Verdict vocabulary (pick exactly one)

- **`forgotten`** — the sweep should have reached this site and didn't. Passing
  `K` would change behavior/correctness in the direction the majority already
  adopted, and nothing about this site makes `K` inapplicable. Supply a
  suggested completion (the exact kwarg to add).
- **`deliberate`** — an intentional exception: the straggler is a *different
  code path* from the present sites (success-vs-error branch of a result
  object, a minimal/default construction, an ABC/override, an equivalent
  idiom). Omission is the point.
- **`optional`** — `K` is optional-by-nature (has a default on the callee). The
  present sites pass a **non-default** value because they need it; the straggler
  is correct with the default. The divergence is "some callers customize, one
  doesn't," not "one forgot."
- **`not-applicable`** — `K` is illegal/impossible here: wrong arity (e.g.
  `flat=True` with multiple columns), a type clash, or a selector that can't
  take it. The straggler *cannot* pass `K`.

`deliberate` vs `optional` overlap; prefer `optional` when the deciding fact is
"the field has a default and this site wants it," and `deliberate` when the
deciding fact is "this is a structurally different branch/idiom." When torn,
either is fine — both mean "not a forgotten sweep, do not action."

## The dominant trap (most gated-in findings hit this)

The detector clusters by **callee + kwarg presence**, so two very common,
perfectly-correct patterns look identical to a forgotten sweep:

1. **Result-shape success/error branch.** A `@dataclass` result with
   `success: bool`, `error: Optional[str] = None`, `status_code=None`, etc. The
   present sites are the *failure* returns (they pass `error=`); the straggler
   is the *success* return (`success=True`, no `error`). Passing `error=` on a
   success path would be *wrong*. → `deliberate`.

2. **Optional dataclass / constructor field.** A builder where most call sites
   set field `K` but a minimal one doesn't, and `K` has a default. The straggler
   builds the terse/default variant. → `optional`. (Example: a budget object
   whose deadline/token caps default to `None`; a spec whose `description`
   defaults to `""`.)

Both mimic "updated N-1 of N." The trajectory gate cannot separate them because
the optional/error-branch sites are also recently edited. **You** separate them
by asking: *would passing `K` here be correct, or would it be wrong / redundant
with the default?* If redundant or wrong → not `forgotten`.

## Forgotten looks like this instead

- `K` is **not** a result-shape or optional-customization field — it changes how
  the call *behaves*, and the majority adopted it as the new convention.
- The straggler is the *same kind* of call as the present sites (same branch,
  same intent), just missing `K`.
- A concrete behavioral/correctness gap follows from the omission.

Canonical example: `zip(strict=False)` threaded through siblings while one
`dict(zip(headers, row))` site still relies on the silent-truncation default —
same intent (pair two sequences), behavioral divergence (silent length
mismatch), majority already swept. → `forgotten`, completion `strict=False`.

## Equivalent-idiom caution

A straggler may achieve `K`'s effect a different way: `el.get_text().strip()`
instead of `get_text(strip=True)`; a `re.sub(...).strip()` wrapper instead of
`separator=`/`strip=`. That is not a forgotten kwarg — the behavior is already
there. → `deliberate` (note the equivalent idiom).

## Precondition-bearing kwarg caution

A kwarg can presuppose a condition that not every sibling site is in.
`exc_info=True` only makes sense when an exception is in scope — a logger
method that records a *business condition* (a validation outcome, a quota
event) has no traceback to attach, so passing it would log a spurious empty
stack. Likewise `update_fields=` presupposes a partial save, `flat=` a single
selected column. Before calling such a straggler `forgotten`, confirm its call
site is actually in the condition the kwarg requires; if it is not, it is
`optional` / `deliberate` (or `not-applicable`) — never forgotten, even when
the majority of siblings pass it.

## Output

Return one record:

```json
{
  "id": "<packet id>",
  "verdict": "forgotten|deliberate|optional|not-applicable",
  "rationale": "one line — the deciding fact",
  "completion": "<kwarg to add, only when forgotten>"
}
```
