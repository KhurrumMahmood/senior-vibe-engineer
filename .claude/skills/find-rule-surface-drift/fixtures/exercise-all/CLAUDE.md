# Fixture CLAUDE.md

This file is deliberately oversized for the `oversized_root` band. The
soft budget for the fixture run is 200 characters, and this preamble alone
already passes that threshold so the band fires reliably.

## Project Overview

Stand-in project text. Real CLAUDE.md content lives elsewhere; this
fixture exists only to exercise the rule-surface-drift detector.

## Supplementary Documentation

| File | Read when… |
|---|---|
| `present.md` | A normal, registered, referenced doc — should produce no finding. |
| `huge.md` | A registered + referenced doc that is itself oversized. |
| `phantom.md` | A registered doc that does not exist on disk — should fire `missing_doc`. |
| `orphan.md` | A registered doc that exists but is mentioned nowhere else — should fire `unreferenced_doc`. |

Note: `dormant.md` is intentionally absent from this table even though
the file exists under `docs/` — that's the `dormant_doc` trigger.
