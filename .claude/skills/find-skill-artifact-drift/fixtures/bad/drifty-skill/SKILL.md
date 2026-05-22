---
name: drifty-skill
description: A fixture skill whose SKILL.md drifted from its artifacts.
allowed-tools: Read, Write
not_for: This skill never edits code.
produces: [ghost_report]
---

# /drifty-skill

This skill still points at scripts/missing.py, which was deleted.

## Pipeline

```bash
.venv/bin/python scripts/real.py --nonexistent
```

It writes a short summary.
