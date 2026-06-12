# skill-comply: wrong-name doc/code discrepancy — fixed

Scope: `scripts/skill_comply/` conformance harness (ported design doc +
code). Task: locate and fix the inherited doc/code discrepancy around the
`wrong-name` fixture/verdict.

## The discrepancy

**DESIGN.md** ("The scorer bug the depth pass found (and fixed)") documents
that the wrong-name fixture exposed substring-based hit-counting, and that
the fix made *both* the hit counters *and* C2 use a tag-field parse:

> **Fix.** Parse the **tag field** specifically. `_parse_violation` splits
> `path:line:col: tag: msg`, requires the locator (`path:line:col`) to carry
> exactly two colons so message text can never masquerade as the tag, and
> returns `(path, tag)`. Hit counting now compares `tag == rule_name`
> exactly; **C2's format check uses the same parse.** After the fix
> `wrong-name` fails C4 (now `pre-anchor hits=0`) **and C2 as designed** …

and (verdict-space section):

> They are distinguishable only by the cosmetic **C2** line
> (output-format/tag check), which `wrong-name` now fails and `defective`
> passes.

**The code** (`score_conformance.py`, `check_c2_rule_cli`) had received the
`_parse_violation` fix for C4/C8 hit-counting, but C2's format check still
used the old whole-line substring match:

```python
# Output-format spot check on the bad run.
fmt_ok = any(
    line.count(":") >= 3 and f": {rule_name}: " in line
    for line in bad_out.splitlines()
)
```

The wrong-name fixture's rule emits the drifted tag `no-bare-int-req` but
its message body ends with the allow-list hint
`(allow-list: # noqa: no-bare-int-request: <reason>)`, which contains the
substring `: no-bare-int-request: `. So C2's `fmt_ok` evaluated True on the
drifted-tag output — exactly the masking failure the doc says was fixed —
and wrong-name **passed** C2 instead of failing it.

## Which side I chose, and why

Made the **code** match the **documented intent**. Three reasons:

1. The doc is internally consistent: both the fix narrative and the
   verdict-space section say wrong-name fails C2; nothing elsewhere in
   DESIGN.md contradicts it (this is *not* one of the four ported KNOWN
   GAPS, which are about C8 skip, recall, ruff branch, and generality).
2. The documented intent is the correct design: a tag-drifted rule has a
   malformed output contract (the emitted tag is not the wired name), so
   the output-format check *should* flag it — that is the only line that
   distinguishes wrong-name from defective on the scorecard.
3. The code shape was an incomplete port of the documented fix — C4/C8 got
   the `_parse_violation` rewrite, C2 kept the pre-fix substring shape.

Not ambiguous; no fork to record.

## Diff summary

One file, `scripts/skill_comply/score_conformance.py` (+4 / −2): C2's
`fmt_ok` now uses the same `_parse_violation` tag-field comparison as C4/C8
(`pv[1] == rule_name`), plus a comment explaining why. No other files
touched; fixtures, validate expectations, and tests unchanged (validate.py
asserts verdict + consequential-fail IDs only, and wrong-name's verdict was
already `fail` via C4, so no expectation edits were needed).

## Verification

- `~/Projects/engineering-skills/.venv/bin/python scripts/skill_comply/validate.py`
  → `OVERALL: PASS` (all five fixtures VALIDATED). Spot check
  `--only wrong-name` now shows
  `C2 FAIL [cosmetic] … output_format_ok=False` alongside the expected
  `C4 FAIL [CONSEQUENTIAL]` — matching the documented scorecard.
- `.venv/bin/python -m pytest tests/test_skill_comply.py -q` → `1 passed`.
- `.venv/bin/ruff check scripts/skill_comply/` → `All checks passed!`

Nothing committed; change left in the working tree.
