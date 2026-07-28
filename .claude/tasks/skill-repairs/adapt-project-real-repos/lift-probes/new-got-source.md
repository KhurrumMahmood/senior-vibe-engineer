# Adapt-project blind new-condition lift probe: got

## Scope and command

Read exactly one skill: `.claude/skills/adapt-project/SKILL.md`.

Read-only dogfood discovery was run against the pinned host:

`<repo>/.engineering/local/real-repo-corpus/got`

with this external, unique artifact root:

`/private/tmp/adapt-project-lift-new/got-20260728T000000Z-16812`

The executed discovery command, from `.claude/skills/adapt-project`, was:

```bash
python3 -I -S scripts/discover.py \
  --project-root <repo>/.engineering/local/real-repo-corpus/got \
  --artifact-root /private/tmp/adapt-project-lift-new/got-20260728T000000Z-16812 \
  --no-host-write
```

It produced:

`/private/tmp/adapt-project-lift-new/got-20260728T000000Z-16812/reports/adapt-project/scan-20260728-071351`

## Exact observed facts

- Project name: `got`.
- Observed language: `typescript`.
- Stack markers: `package.json`, `tsconfig.json`; package manager: `npm`.
- Production source root: `source`.
- Production source count: 25 TypeScript files: 25 `.ts`, 0 `.tsx`; 0 Python and 0 Markdown files.
- Sensitive surface: `source/core/utils/strip-url-auth.ts` (`sensitive-looking name`).

## Exact discovered commands

- Setup: `npm install`
- Test: `cd . && npm run test`
- Test: `cd . && npm run test:coverage`
- Lint: none inferred.
- Dev: none inferred.

## Evidence gate

The mandatory evidence command was run against the resulting scan directory:

```bash
python3 -I -S scripts/check_evidence.py \
  --scan-dir /private/tmp/adapt-project-lift-new/got-20260728T000000Z-16812/reports/adapt-project/scan-20260728-071351
```

Result: exit 0, exact output `adapt-project evidence OK`.

`evidence.json` maps required evidence tokens `adapter` to `adapter.yml` and `report` to `report.md`; its note is `no host writes`. The generated adapter status is `complete`.

## Final git status

At the status check, the project worktree already contained the following changes; the discovery itself wrote only outside the host. This probe report is the requested local artifact.

```text
 M .claude/contracts/skills/adapt-project.yaml
 M .claude/skills/adapt-project/SKILL.md
 M .claude/skills/adapt-project/scripts/discover.py
 M .claude/tasks/multilanguage-support-backlog.md
 M tests/test_adapt_project_go_g1.py
 M tests/test_adapt_project_typescript.py
?? .claude/tasks/real-repository-corpus.json
?? .claude/tasks/real-repository-validation-plan.md
?? .claude/tasks/skill-repairs/adapt-project-real-repos/
?? scripts/real_repo_corpus.py
?? tests/test_real_repo_corpus.py
```

## Correction: pinned-host git status

The preceding worktree status was for the engineering-skills product worktree,
not the pinned `got` host, and therefore does not establish host safety.

The requested command was run exactly:

```bash
git -C <repo>/.engineering/local/real-repo-corpus/got status --porcelain --untracked-files=all
```

Exact result: no output (the pinned `got` host worktree is clean). This confirms
the `--no-host-write` dogfood discovery did not modify the host.
