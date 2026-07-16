"""Exemplar adoption of the scope.json sidecar (spec IM-5, ADR 0037).

The two exemplar proposal collectors — unify-shadows and extract-enum —
must emit a scope.json sidecar next to their artifact declaring the repo
paths the artifact's conclusions depend on.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COLLECT_SHADOWS = REPO_ROOT / ".claude" / "skills" / "unify-shadows" / "scripts" / "collect_shadows.py"
COLLECT_ENUM = REPO_ROOT / ".claude" / "skills" / "extract-enum" / "scripts" / "collect.py"

TRIAGE = """\
### SC-1: Duplicated helpers [HIGH]

- `app/a.py:10` — `helper_a` (12 lines, 3 callers)
- `app/b.py:20` — `helper_b` (12 lines, 2 callers)

**Consolidation shape:** `share_utilities`
"""


def test_collect_shadows_emits_scope_sidecar(tmp_path):
    triage = tmp_path / "triage.md"
    triage.write_text(TRIAGE)
    out = tmp_path / "reports" / "unify-shadows" / "SC-1" / "targets.json"
    proc = subprocess.run(
        [sys.executable, str(COLLECT_SHADOWS), "--triage", str(triage),
         "--finding-id", "SC-1", "--output", str(out)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    sidecar = json.loads((out.parent / "scope.json").read_text())
    assert sidecar["paths"] == ["app/a.py", "app/b.py"]
    assert sidecar["written_at"]


def test_extract_enum_sidecar_helper_writes(tmp_path):
    spec = importlib.util.spec_from_file_location("collect_enum_mod", COLLECT_ENUM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._write_scope_sidecar(tmp_path / "artifact", ["app/models/x.py", "app/views/y.py"])
    sidecar = json.loads((tmp_path / "artifact" / "scope.json").read_text())
    assert sidecar["paths"] == ["app/models/x.py", "app/views/y.py"]


def test_extract_enum_sidecar_accepts_a_deterministic_clock(tmp_path):
    spec = importlib.util.spec_from_file_location("collect_enum_clock_mod", COLLECT_ENUM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    clock = "2000-01-01T00:00:00+00:00"

    first = tmp_path / "first"
    second = tmp_path / "second"
    mod._write_scope_sidecar(first, ["app/models/x.py"], written_at=clock)
    mod._write_scope_sidecar(second, ["app/models/x.py"], written_at=clock)

    assert (first / "scope.json").read_bytes() == (second / "scope.json").read_bytes()
    assert json.loads((first / "scope.json").read_text())["written_at"] == clock
