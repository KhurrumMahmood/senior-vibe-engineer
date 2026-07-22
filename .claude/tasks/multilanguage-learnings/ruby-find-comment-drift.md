# Ruby find-comment-drift learning

## Outcome

The copied `find-comment-drift` closure now contains one self-contained Ruby
lexical/syntax producer, `scripts/analyze_comments_ruby.py`. Ruby 3.4.1 and its
bundled Prism 1.2.0 identify exact comment byte ranges; a separate `ruby -c`
process gates every eligible input. On the frozen fixture, the analyzer finds
the comment claiming that `fee_cents(amount_cents)` calculates a percentage
from the invoice amount while the complete adjacent method returns the fixed
literal `125`. The finding records the comment and method spans, their spelling
hashes, the parameter name, returned literal, full-source hash, and source
manifest hash as machine-checkable evidence.

The outcome vocabulary keeps evidence coverage separate from scan results:
`complete/advisory-findings` and `complete/clean-within-complete` are successful;
a malformed selected Ruby file is `partial/incomplete`; missing Ruby, Ruby below
3.3, or an all-excluded selection is `unsupported`; a version probe, native
syntax-check process, Prism process, or payload failure with no completed input
is `failed`. Same-destination reruns replace `detections.jsonl`, `scan.json`,
`findings.json`, and `report.md` atomically, including valid-to-failed,
failed-to-valid, and changed-source transitions. Old finding and source hashes
do not survive a rerun.

## Source and lexical boundary

Ordinary `.rb` files and executable extensionless files with a Ruby shebang are
eligible. Test/spec, generated, vendor, build, generated-marker, and symlink
inputs are inventoried but not analyzed. Ruby magic comments and shebangs are
recognized separately from ordinary comments. Prism prevents `#` text inside
quoted strings and heredocs from becoming comment evidence; the focused
fixture contains both decoys.

The behavior rule is intentionally narrow: an ordinary comment immediately
adjacent to a syntactically valid method must claim a percentage/rate derived
from an amount/total, and the entire simple method body must be one fixed
numeric-literal return. This is useful evidence, not general natural-language
or behavioral proof. The producer also preserves the existing lexical
stale-term, brittle Ruby line-reference, and detached-banner bands.

## What generalized

- The family-local inventory, four terminal evidence states, JSONL finding
  shape, exact source fingerprints, atomic artifacts, stale-output clearing,
  copied-layout replay, and source-preservation proof transferred directly.
- Clean remains a result only inside complete evidence. A zero-finding partial,
  unsupported, or failed run never becomes clean.
- Native syntax must run per selected file. One successful `ruby -c` invocation
  is never projected onto another file.
- A content-derived source manifest plus per-finding source/comment/code hashes
  makes changed-source reruns auditable without a repository runtime.

## What stayed Ruby/family-local

Prism comment locations, Ruby magic-comment policy, Ruby shebang discovery,
`.rb` test naming, and the adjacent Ruby `def`/`end` fixed-return rule remain in
the skill-local producer. No universal AST, comment-to-code schema, or shared
natural-language behavior engine was introduced.

The analyzer does not resolve calls, constants, types, dynamic `require`/`load`
or `autoload`, `send`/`public_send`, `const_get`, `method_missing`, eval,
`define_method`, reflection, callbacks, refinements, monkey patches,
class/module reopening, DSLs, Rails, or Zeitwerk. A method with nested control
flow or any body beyond the accepted one-literal form is deliberately outside
the behavior rule. Framework documentation conventions and YARD completeness
are also non-claims.

## Native verification and acquisition

No dependency was installed or updated, and no network was used. Verification
selected:

- `/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python` <!-- # host-ref-allow: required frozen P7 runtime -->
  3.11.10 for the isolated stdlib-only producer, Ruff, and pytest; and
- `/Users/khurrummahmood/.local/bin/ruby` <!-- # host-ref-allow: required frozen P7 runtime -->
  3.4.1 with bundled Prism 1.2.0 for per-file syntax and comment evidence.

The copied fixture passes `ruby --disable-gems -c` once for every selected
first-party/test source, a dependency-free Ruby test, and the executable
Ruby-shebang smoke. The malformed fixture fails native syntax as expected, and
all source bytes remain unchanged across positive, clean, malformed, and
lifecycle scans.

## Closure and counted LOC

Closure is every regular non-`.pyc` file below
`.claude/skills/find-comment-drift`, excluding `__pycache__`, with manifest
SHA-256 over sorted `path + NUL + file_sha256 + LF` rows.

- Branch base: 19 files, 115,973 bytes,
  `manifest_sha256=ef38900ad25906bc0222f267b9273903dabf4c19561acc69e4c69a9eedaf9bc3`.
- Ruby result: 20 files, 138,678 bytes,
  `manifest_sha256=4eb4bcd92a1f09227f701743c072834c7f4e7aac80ba3958d78f134b53c0ca10`.
- Delta: one copied-runtime file and 22,705 bytes (19.58% selected-skill
  closure growth).

Adapter-plus-test code is 945 physical lines and 855 nonblank lines: 593/546
in `analyze_comments_ruby.py` and 352/309 in
`tests/test_find_comment_drift_ruby.py`. Fixtures and this learning packet are
excluded from LOC.

## Root integration needs

Root should make only these shared changes before publishing Ruby support:

1. In `find-comment-drift/SKILL.md`, add Ruby to the description/frontmatter,
   document the direct copied-helper command, four artifacts, Ruby >= 3.3 and
   Prism boundary, `.rb` plus Ruby-shebang inventory, role exclusions, native
   `ruby -c`/test/executable obligations, and dynamic/metaprogramming non-claims.
2. Change only the `find-comment-drift` row in
   `.claude/tasks/ruby-language-coverage.json` from
   `ruby-pending-implementation` to `ruby-supported`, citing this learning
   packet, the integrated revision, exact native checks, and the bounded local
   syntax limitation. Regenerate the multilingual matrix through its existing
   builder rather than hand-editing generated projections.
3. Add Ruby to any shared router/catalog description only after those artifacts
   and the focused/full family regressions pass on the integration branch. The
   standalone helper needs no `detect.py`, `report.py`, shared inventory,
   profile, or provider change.

These shared surfaces deliberately remain root-owned; this lane edits none of
them.
