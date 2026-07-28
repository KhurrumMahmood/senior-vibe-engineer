# Implementation record — `adapt-project` real-repository slice

## Changed behavior

- Canonical `scripts/discover.py` now recognizes `source/`, inventories
  domain-named authored Go packages, parses pytest configuration with stdlib
  `tomllib`, composes Python commands with its venv setup, prefers a declared
  `requirements-dev.txt`, and calibrates sensitive path matches to exclude
  documentation-only hits.
- Go example-directory exclusions no longer leak into Java, where `example`
  is a common package component.
- Reduced regressions cover positive, exclusion, malformed-config, and
  cross-language no-regression cases.
- Skill prose and the intent/provenance contract now describe the accepted
  source-root behavior.

## Judgment calls

- The implementation is confined to the skill-local producer named by
  `SKILL.md`. An initial expansion of legacy `scripts/project_adapt.py` was
  removed after independent scouting proved it was not the installed product
  path and its schema contradicted the canonical contract.
- The evidence gate and specialized-language dispatcher remain separate
  candidate work because neither was required to repair the three canonical
  omissions. Their demonstrated user impacts and acceptance criteria are
  ML-028 through ML-030.
- The Got documentation false positives were fixed in this slice because the
  canonical real-host report failed its finding-precision criterion; this was
  observed product behavior, not theoretical hardening.

## Verification run by the implementation lane

- Ruff on every changed Python implementation/test file: pass.
- TypeScript/Go/Java affected family suite: `31 passed in 33.32s` after the
  sensitive-path regression; the prior broader family/corpus run was
  `41 passed in 36.83s`.
- Release/router/corpus boundary: `106 passed in 23.54s`.
- Four canonical real-host scans: exit zero, evidence pass, exact accepted
  facts, 0.05–0.08 seconds each, and clean host Git state.
- No separate `--validate` mode exists in the canonical discovery script;
  `scripts/check_evidence.py` is the skill-local final-artifact gate and was
  run against every exact real-host scan.
