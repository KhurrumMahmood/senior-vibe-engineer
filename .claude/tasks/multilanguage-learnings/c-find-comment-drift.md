# C find-comment-drift learning

## Outcome

The copied `find-comment-drift` closure now contains a self-contained C lexical
producer, `scripts/analyze_comments_c.py`. With installed Apple Clang 21 it
writes `detections.jsonl`, `scan.json`, `findings.json`, and `report.md` from
raw comment tokens plus exact source bytes. The frozen C pilot reaches both
`complete/advisory-findings` and `complete/clean-within-complete`; a malformed
translation unit reaches `partial/incomplete`; missing or old Clang and a
selection containing only ambiguous headers reach `unsupported`; an analyzer
process failure reaches `failed`.

Every finding carries a half-open byte range, one-based start/end line and
column, and a SHA-256 fingerprint of the exact comment spelling. Zero findings
is clean only when all eligible source produced complete syntax and raw-token
evidence. Same-destination reruns replace all four artifacts, including a
proven advisory-findings-to-failed transition, so an old positive result cannot
survive a blocked scan.

## Source and compile-command boundary

`.c` and `.i` are the only independently eligible suffixes. `.h` and `.inc`
remain `ambiguous-header` unless a valid, current, complete C17
`compile_commands.json` dependency scan owns them. On the frozen two-TU host,
that closure owns `include/cpilot/invoice.h`, `src/invoice_internal.h`, and
`src/pilot_mode.inc`; the two orphan headers remain excluded. Missing,
malformed, incomplete, and stale databases are reported without fallback.
Generated, vendor, test, build, and symlink roles are inventoried but not
analyzed.

Independent SHA-256 maps before and after the positive, clean, and malformed
runs prove source preservation. The emitted inventory repeats each readable
source fingerprint and byte count, and the helper checks the fingerprint again
before publishing `source_preserved: true`. Reports are the only writes.

## Native verification and tool acquisition

No dependency was installed and no network was used. Verification used:

- `/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python` <!-- # host-ref-allow: required frozen P7 runtime -->
  (Python 3.11.10) for pytest, Ruff, and the stdlib-only copied helper;
- `/usr/bin/clang` (Apple Clang 21.0.0) for C17 warnings-as-errors syntax,
  dependency, and raw-token evidence; and
- `/usr/bin/make` (GNU Make 3.81) for the restrictive native fixture.

The copied host passed `make clean test CC=/usr/bin/clang`, including its
executable smoke, in 0.58 seconds. A complete five-file lexical run with a
valid copied-root compile database completed in 0.33 seconds and returned
`complete/clean-within-complete`. The focused suite completed 9 tests in 1.79
seconds.

## Closure and counted LOC

Closure is every regular non-`.pyc` file below
`.claude/skills/find-comment-drift`, excluding `__pycache__`.

- Base: 18 files, 93,488 bytes,
  `manifest_sha256=a0ea30a3d2b5721465e3b71b432cecb795e929bd1eb13ef55251423773b8264f`.
- C result: 19 files, 114,661 bytes,
  `manifest_sha256=f64de7ea0f138d3a617c0c8883c85c5c7e96b452c73707304878d716fc7f4182`.
- Delta: one file and 21,173 bytes (22.65% selected-skill closure growth).

Adapter-plus-test code is 760 physical lines and 677 nonblank lines: 481/441
in `analyze_comments_c.py` and 279/236 in `test_find_comment_drift_c.py`.
This learning packet is excluded from those LOC counts.

## Explicit limits

The producer is lexical. It does not interpret macro expansion, inactive
preprocessor branches, or comment-to-symbol association, and it makes no
documentation-completeness claim. Header ownership says only that an accepted
C compile command depends on the file; it does not assign public API meaning.
There is no C++, Objective-C, Objective-C++, CUDA, OpenCL, assembly, build-system
beyond the frozen Make/compile-database contract, or framework support.

## Root integration needs

Root may wire this C-named helper into the shared detector/reporter and publish
the earned C disposition. That integration must preserve the four evidence
states, `clean-within-complete`, exact spans, strict header gate, stale-artifact
replacement, and the lexical limits above. Shared dispatch, SKILL prose,
coverage/matrix/router truth, and catalog changes deliberately remain outside
this lane.
