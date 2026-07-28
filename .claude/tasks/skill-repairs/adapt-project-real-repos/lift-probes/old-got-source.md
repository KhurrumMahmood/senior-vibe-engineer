# Old `/adapt-project` lift probe — got source discovery

## Scope and command

- Historical skill read: `/tmp/skill-repairs-old/adapt-project/SKILL.md`.
- Pinned host (read-only): `<repo>/.engineering/local/real-repo-corpus/got`.
- Artifact root (outside host): `/private/tmp/adapt-project-lift-old/got-20260728T001344-16497`.
- Scan directory: `/private/tmp/adapt-project-lift-old/got-20260728T001344-16497/reports/adapt-project/scan-20260728-071344`.

Executed exactly through the skill's dogfood discovery path:

```bash
cd /tmp/skill-repairs-old/adapt-project
python3 -I -S scripts/discover.py \
  --project-root <repo>/.engineering/local/real-repo-corpus/got \
  --artifact-root /tmp/adapt-project-lift-old/got-20260728T001344-16497 \
  --no-host-write
python3 -I -S scripts/check_evidence.py \
  --scan-dir /private/tmp/adapt-project-lift-old/got-20260728T001344-16497/reports/adapt-project/scan-20260728-071344
```

## Exact observed adapter facts

- Report language: `javascript`.
- Adapter language: `javascript`.
- Stack markers: `package.json`, `tsconfig.json`.
- Package manager: `npm`.
- Frameworks: `(none detected)`.
- Production source root/count: report says `(none inferred)`; adapter has `"source_roots": []`. No production source-root or count was emitted.
- Test commands: `cd . && npm run test`; `cd . && npm run test:coverage`.
- Setup commands: `(none inferred)`; adapter has `"setup": []`.
- Lint commands: `(none inferred)`.
- Dev commands: `(none inferred)`.
- Adapter status: `complete`.

## Evidence gate

Exit status: `0`.

Exact gate output:

```text
adapt-project evidence OK
```

`evidence.json` maps the required tokens as follows:

```json
{
  "evidence": {
    "adapter": "adapter.yml",
    "report": "report.md"
  },
  "notes": "no host writes",
  "produced_at": "2026-07-28T07:13:44Z",
  "scan_id": "scan-20260728-071344",
  "skill": "adapt-project"
}
```

## Final pinned-host git status

`git -C <repo>/.engineering/local/real-repo-corpus/got status --short` produced no output: clean. The host was not modified; all generated artifacts are outside it.
