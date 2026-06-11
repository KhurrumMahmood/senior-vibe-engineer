# Fan-out brief — generate ES2 skill intent + provenance contracts (schema v2)

You are one of several parallel agents authoring per-skill contracts for the
**engineering-skills-2** repo. Each contract is one YAML file at
`.claude/contracts/skills/<skill>.yaml`. Your prompt names the exact subset
of skills you own. Do ONLY those. Other agents handle the rest.

- **Project root:** `~/Projects/engineering-skills-2` (cd here)
- **venv (if you run anything):** `.venv/bin/python`  · **Platform:** darwin/macOS
- You write files only; no git mutations, no commits.

## Read these first (authoritative)

1. **Schema + worked example:** `.claude/contracts/skills/_schema.yaml`. Copy
   the `example:` field set EXACTLY (same keys, same nesting). Drop the
   `example:` wrapper — your file's top level is `schema_version: 2` then the
   fields.
2. **Deterministic git/disk facts:** `.claude/tasks/es2_skill_facts.yaml`. This
   is the ONLY source for `born` (commit/date/sibling_births), `reports_dir`,
   `run_evidence`, and the `has_fixtures` / `has_scripts` booleans. **Never
   re-run git archaeology** — these facts already resolved true birth by
   parent-absence (the `--diff-filter=A` merge artifact is avoided).
3. **The skill itself:** `.claude/skills/<skill>/SKILL.md` — read it for every
   skill you own. `job:` is pulled VERBATIM from this frontmatter.
4. **The full ES2 skill set:** `.claude/tasks/_fanout_partition.yaml`
   (`shared` + `es2_only`). Use it to check whether a skill you'd reference in
   `related_skills` / `duplication_risk` actually EXISTS in ES2.

## Two authoring modes

**SHARED skills** (have a host-a contract — see your list): the host-a contract at
`<host-a-checkout>/.claude/contracts/skills/<skill>.yaml`
is your **intent base**. Transfer `problem_class`, `intent`, `solves`,
`related_skills`, and `duplication_risk` *relationships* — but:
- **VERIFY against the ES2 `SKILL.md`.** If ES2's skill differs (narrower,
  renamed surface, different `not_for`), write ES2's reality, not host-a's.
- **RE-DERIVE all provenance from ES2 facts.** Never copy host-a's `born`,
  `dogfooded_on`, `reports_dir`, `run_evidence`, or `provenance_confidence`.
  Those are host-a's history; ES2's are different (big-bang extraction).

**ES2-ONLY skills** (no host-a contract): author fresh from the ES2 `SKILL.md`
+ facts. These tend to be ecosystem-bootstrap skills (adapt-project,
engineer-init, orient, project-interview, which-shape, check-ecosystem-consistency,
find-standard-gaps, harvest-learnings, find-skill-artifact-drift).

## Hard rules (apply to every contract)

- **`embodies_decisions.adr: []` ALWAYS.** ES2 has no `docs/decisions/` tree.
  For `precedent`: grep `.claude/docs/precedents.yml` for the skill name; list
  the entry id if present, else `[]`. `doc`/`contract`: only if the SKILL.md
  clearly embodies one; else `[]`.
- **`born`:** copy `commit` / `date` / `sibling_births` verbatim from the facts
  file. (sibling_births is large for the big-bang commit `90f8567`.)
- **`dogfood_kind`** — pick from ES2 evidence ONLY (enum:
  `subsystem-refactor` | `self-installed-guard` | `fixture-pair` | `none-found`):
  - `has_fixtures: true` → **fixture-pair** (the good/bad pair is the oracle).
  - else a meta-guard that ran against the ecosystem itself (name like
    `find-skill-*`, `check-ecosystem-*`, `find-rule-surface-*`, `find-folder-*`,
    `find-stale-artifacts`, `find-comment-drift`) AND has a self-scan run in
    facts → **self-installed-guard**.
  - else → **none-found** (extracted big-bang, not yet dogfooded in THIS repo).
    This is the honest answer for most no-fixtures/no-reports skills — say so.
  - ES2 has **no** host-subsystem refactors, so `subsystem-refactor` is almost
    never right here; don't use it unless the SKILL.md + a real run prove it.
- **`dogfooded_on`:** the fixtures pair, and/or the on-disk self-scan run(s)
  named in `run_evidence`, and/or "none-found (extracted, no ES2 dogfood run)".
  Be honest — do not invent a dogfood target.
- **`run_evidence`:** copy from facts (`count` already excludes `latest`
  symlinks). If `reports_dir` is null, `count: 0`, `first`/`latest`: null.
- **`provenance_confidence`** (re-assess for ES2, do not copy host-a):
  - `textual`: **low** for big-bang (`90f8567`) skills unless born in a named
    later commit; `med`/`high` only if you can see the commit names the skill
    (optional: one `git log --oneline -- .claude/skills/<skill>` is fine, but
    default low for the big-bang set rather than running 60 git commands).
  - `structural`: `has_scripts` + `has_fixtures` → high; one of them → med;
    neither (prose-only skill) → low.
  - `temporal`: big-bang `90f8567` cohort → **low** (birth proximity carries no
    signal when 55 skills share a commit); small named cohort → med/high.
  - `dogfood`: real fixtures oracle OR ≥2 self-runs → high; exactly one
    self-run → med; none → low.
- **`duplication_risk`:** preserve cross-skill relationships, but **drop or
  repoint any entry whose `with:` skill does NOT exist in ES2** (check
  `_fanout_partition.yaml`). The COMPLETE set of host-a-only skills absent from
  ES2 (drop/repoint duplication edges pointing at these) is exactly these 6:
  find-augment-mirror-drift, find-broken-file-refs, find-doc-link-rot,
  find-folder-readme-drift, find-spine-drift, propose-spine. Everything else a
  host-a contract references (e.g. find-contract-drift, find-frontend-contract-drift)
  DOES exist in ES2 — keep those edges.
  Relation enum: `sequential` | `sibling-different-layer` |
  `shared-doc-coupling` | `genuine-overlap`. Each entry needs a one-line
  `disambiguator` (usually a `not_for` quote).
- **The skill-meta trio** (call it out where relevant): `find-skill-intent-drift`
  (intent+provenance layer), `find-skill-artifact-drift` (SKILL.md prose ↔
  on-disk artifacts), and `scripts/skill_meta.py lint` (frontmatter contract).
  These are `sibling-different-layer`, NOT genuine overlap. If you own
  `find-skill-artifact-drift`, record its `sibling-different-layer` relation to
  `find-skill-intent-drift`.
- **Use `gaps:`** for anything you genuinely cannot determine. **Do NOT guess.**
- Output must be valid YAML and load with `yaml.safe_load`. Match the example's
  key set exactly: `schema_version, skill, job, problem_class, intent, solves,
  born{commit,date,sibling_births}, dogfood_kind, dogfooded_on[], reports_dir,
  run_evidence{count,first,latest}, embodies_decisions{adr,precedent,doc,contract},
  related_skills[], duplication_risk[]{with,relation,disambiguator},
  provenance_confidence{textual,structural,temporal,dogfood}, evidence[], gaps[]`.

## When done

Write each `<skill>.yaml`, then reply with: the count you wrote, any skill where
ES2's reality diverged from the host-a intent base (and how), and any
`duplication_risk` entries you dropped because the target skill is host-a-only.
Keep the reply short — your durable output is the files.
