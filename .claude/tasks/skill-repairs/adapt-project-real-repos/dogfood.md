# Dogfood evidence — canonical `adapt-project`

Date: 2026-07-27

## Command boundary

Each pinned host was run through the documented copied-skill producer, not the
legacy repository helper:

```bash
.venv/bin/python -I -S .claude/skills/adapt-project/scripts/discover.py \
  --project-root <pinned-host> \
  --artifact-root <external-artifact-root> \
  --timestamp real-<name>-1950 \
  --no-host-write
.venv/bin/python -I -S \
  .claude/skills/adapt-project/scripts/check_evidence.py \
  --scan-dir <exact-timestamped-scan>
git -C <pinned-host> status --porcelain --untracked-files=all
```

Every discovery and evidence command exited zero. Every final Git status was
empty. The committed corpus manifest owns the exact revisions.

## Observed final facts

| Host | Final facts | Wall time | Artifact bytes |
|---|---|---:|---:|
| Requests | Python; `src=19`; `.venv/bin/python -m pytest`; venv plus `requirements-dev.txt` setup; one `auth.py` risk path | 0.06 s | 8,745 |
| Got | TypeScript; `source=25`; tests excluded from production roots; two declared npm tests; `npm install`; only authored `strip-url-auth.ts` retained as a risk path | 0.05 s | 6,570 |
| Chi | Go; root `5`; `middleware=30`; `_examples` and tests excluded; `go test ./...`; one `basic_auth.go` risk path | 0.06 s | 7,051 |
| Spring PetClinic | Java; `src=30`; Maven and Gradle wrapper tests; framework list remains empty | 0.08 s | 6,730 |

Exact scans are ignored disposable artifacts under:

```text
.engineering/local/real-repo-validation/<name>/shipped-adapt-final/
  reports/adapt-project/scan-real-<name>-1950/
```

## Review disposition

- The real omissions in the canonical producer were repaired and reduced to
  fixture regressions.
- The Go-only example-directory rule initially leaked into Java and excluded
  the common Java package name `example`; the full family suite caught it and
  the language policies are now separate.
- Got's canonical report exposed four documentation-only migration false
  positives. A narrow token/documentation rule removed those while preserving
  the authored auth-code match.
- Semantic evidence validation, specialized-language dispatch, and retirement
  of the duplicate repository helper are real follow-ons, but they are not
  smuggled into this bounded repair. They are ML-028 through ML-031 in the
  multi-language backlog with explicit triggers and acceptance criteria.
