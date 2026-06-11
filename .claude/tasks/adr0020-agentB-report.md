# ADR 0020 — Agent B completion report: `/orient` skill

## What was built

A new user-invocable skill `/orient` — the human-in-the-loop "pull"
mechanism of ADR 0020 (lifecycle- and stakes-gated standard activation).
It establishes/re-confirms a project's lifecycle state on two
independent axes (maturity × stakes) via orientation questions, shows
the resulting classification + which standard rungs it activates (and
which it deliberately caps), then writes the declared state to
`<project-root>/.project-state.json`.

## Files created (all under `.claude/skills/orient/` — the owned surface)

- `.claude/skills/orient/SKILL.md` — orchestrator. Frontmatter
  (`tier: cross-cutting`, `job: meta`, `language: any`, `framework:
  any`, plus `best_for`/`not_for`/`escalate_to` and optional task-packet
  fields `lanes`/`stage`/`entrypoint`/`produces`). Body covers: the two
  ordinal ladders, the 8 orientation questions, the answer→(maturity,
  stakes) "highest applicable rung" mapping, the "show classification +
  implications + capped rungs, then write" step, the EXACT
  `.project-state.json` schema, idempotent re-confirm/overwrite behavior,
  and the full push-inference section. Notes the intentional convention
  divergence (writes a durable single-instance state file at project
  root, not a timestamped `reports/<skill>/scan-<TS>/` artifact).
- `.claude/skills/orient/scripts/infer_state_signals.py` — thin,
  stdlib-only, READ-ONLY "push" inference pass. Greps for 5 transition
  signals (unauth side-effectful handler, public deploy/ingress, payment/
  PII/credential handling, auth/login surface, real-user-data model/DB),
  marks each `[FLAG]` (above declared state) or `[info]` (at/below),
  text + `--json` output, `wrote_anything: false`. os.walk with dir
  pruning + a 512 KB per-file size cap (skipped count reported, never a
  silent "compliant") so it stays fast on data-heavy repos.
- `.claude/skills/orient/knowledge/inference-heuristics.md` — signal
  taxonomy, the recall-over-precision rationale, how to read FLAG/info
  output, what the pass does NOT do (no writes, no auto-advance), tuning.

I built the inference helper as a script (not just a checklist) because
the "push" half of ADR 0020 calls for an actual pass that flags
candidate transitions, and the verification step required running it
against pnci — a documentation-only checklist would make the push side
vaporware. The script is bounded (~5 cheap regexes, read-only) so it
earns its place without over-engineering.

## The contract (honored exactly)

`.project-state.json` schema written by the skill:
`{maturity ∈ {prototype,first-users,production}, stakes ∈ {internal,
external,public-adversarial}, declared_by:"orient", declared_at:<ISO8601>,
notes?:<freeform>}`. Ordinal ladders documented; a rung activates only
when BOTH axes meet its thresholds; re-running overwrites (idempotent).

## Verification (all green)

- `python3 scripts/skill_meta.py lint` → `OK — 66 skills, 66 declaring
  new contract`, exit 0. `skill_meta.py show orient` parses all fields.
  (One YAML fix needed mid-build: an unquoted `: ` in the single-line
  `description` broke the parser; rephrased to an em-dash.)
- `ruff check` on the script → All checks passed.
- Inference script run against a controlled temp fixture: with NO
  declared state → all 3 planted signals `[FLAG]`; with a
  `public-adversarial` declared state → same signals downgrade to
  `[info]` ("No re-orientation prompted"); `--json` confirms
  `wrote_anything: false`; fixture dir confirmed to contain NO
  `.project-state.json` after the run (read-only proven).
- Contract round-trip: wrote the exact Stage-3 schema to a temp path,
  loaded it back, asserted every enum value, `declared_by=="orient"`,
  and ISO8601 `declared_at` → CONTRACT ROUND-TRIP OK.
- Ran against `/Users/khurrummahmood/Projects/pnci-pricing` read-only.
  pnci already has a `manual`-declared `.project-state.json`
  (production / internal — ADR 0020's worked classification), confirming
  my schema/enums match real externally-authored state. Verified I did
  NOT create either repo's state file (both are `declared_by:"manual"`,
  authored by the user/sibling; my script never writes).

## Ownership respected

Did not touch `find-standard-gaps/`, did not create either repo's
`.project-state.json`, did not edit the idea ledger. No git mutations.

## Note for the sibling scanner author

The scanner consuming `.project-state.json` should treat a missing or
malformed file as "undeclared," not "compliant" — `/orient`'s inference
pass already follows this convention (undeclared → everything FLAGs).
