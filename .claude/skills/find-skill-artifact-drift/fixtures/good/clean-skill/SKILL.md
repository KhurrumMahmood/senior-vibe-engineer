---
name: clean-skill
description: A fixture skill whose SKILL.md matches its artifacts.
allowed-tools: Bash, Read
not_for: Generating external product documentation.
produces: [report]
---

# /clean-skill

A coherent fixture: every documented reference resolves to a real artifact.

## Pipeline

```bash
.venv/bin/python scripts/detect.py --output report.jsonl
```

Writes a `report` for review.
