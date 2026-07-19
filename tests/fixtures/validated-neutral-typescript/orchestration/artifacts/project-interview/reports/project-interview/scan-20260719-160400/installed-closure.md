# Installed closure

The exact selected-skill copy includes skill-local stdlib helpers
`scripts/project_interview.py` and `scripts/evidence_gate.py`; neither imports
repository `scripts/`, sibling skills, a toolkit venv, or third-party Python
packages. The installed draft helper preserves `user_approved: false` until
visible human answers are captured and refuses premature durable apply.

The installed evidence gate ran against this scan's fixed manifest and final
artifacts:

```text
Evidence gate for /project-interview on reports/project-interview/scan-20260719-160400:
  [ok] profile -> profile.yml
  [ok] profile_summary -> profile.md
  [ok] open_questions -> open-questions.md

OK: 3/3 required evidence shapes present.
```
