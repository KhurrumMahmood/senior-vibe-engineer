"""Tests for the host-authored workflow loader (.claude/skills/_common/workflows.py).

Covers parsing a `.engineering/docs/product-workflows.md` descriptor in a tmp
state home: step rows (`id | label | route_name | path`), malformed-row
skipping, labels/tab-ids = steps-plus-extras (deduped, ordered), the three glob
sections, and the empty fallback when no descriptor exists (the toolkit ships
with no workflow). Deterministic and disk-isolated — every read runs against
``tmp_path``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# workflows.py lives in _common, not scripts/ (which conftest puts on the path).
_COMMON = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

import workflows  # noqa: E402


def _write_descriptor(root: Path, body: str) -> Path:
    p = root / ".engineering" / "docs" / "product-workflows.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


_FULL = (
    "# Product workflows\n\n"
    "## Steps\n"
    "- `setup | Setup | site_setup | /sites/{site_id}/setup/`\n"
    "- `export | Export | site_export_data | /sites/{site_id}/export/data/`\n\n"
    "## Extra labels\n"
    "- Downloads\n"
    "- Setup\n"  # duplicate of a step label — must dedupe
    "## Extra tab ids\n"
    "- export_data\n\n"
    "## Targets\n"
    "- app/pages/sites\n"
    "- static/js/site-config-*.js\n\n"
    "## Template roots\n"
    "- templates/sites\n\n"
    "## Text-file globs\n"
    "- app/urls.py\n"
    "- templates/sites/*.html\n"
)


# ---- steps ---------------------------------------------------------------

def test_workflow_steps_parses_pipe_rows(tmp_path):
    _write_descriptor(tmp_path, _FULL)
    steps = workflows.workflow_steps(tmp_path)
    assert steps == [
        {"id": "setup", "label": "Setup", "route_name": "site_setup", "path": "/sites/{site_id}/setup/"},
        {"id": "export", "label": "Export", "route_name": "site_export_data", "path": "/sites/{site_id}/export/data/"},
    ]


def test_workflow_steps_skips_malformed_rows(tmp_path):
    _write_descriptor(
        tmp_path,
        "## Steps\n"
        "- `setup | Setup | site_setup | /sites/{site_id}/setup/`\n"
        "- `bad | only | three`\n"  # 3 fields, not 4 — skipped, not fatal
        "- `extra | E | r | p | toomany`\n",  # 5 fields — skipped
    )
    steps = workflows.workflow_steps(tmp_path)
    assert [s["id"] for s in steps] == ["setup"]


# ---- labels / tab ids: steps plus extras, deduped ------------------------

def test_workflow_labels_steps_plus_extras_deduped(tmp_path):
    _write_descriptor(tmp_path, _FULL)
    # step labels first (order), then extras, with the duplicate "Setup" dropped.
    assert workflows.workflow_labels(tmp_path) == ["Setup", "Export", "Downloads"]


def test_workflow_tab_ids_steps_plus_extras(tmp_path):
    _write_descriptor(tmp_path, _FULL)
    # step ids first, then extra tab ids.
    assert workflows.workflow_tab_ids(tmp_path) == ["setup", "export", "export_data"]


# ---- glob sections -------------------------------------------------------

def test_workflow_targets_template_roots_text_globs(tmp_path):
    _write_descriptor(tmp_path, _FULL)
    assert workflows.workflow_targets(tmp_path) == ["app/pages/sites", "static/js/site-config-*.js"]
    assert workflows.workflow_template_roots(tmp_path) == ["templates/sites"]
    assert workflows.workflow_text_globs(tmp_path) == ["app/urls.py", "templates/sites/*.html"]


# ---- empty fallback (toolkit ships no workflow) --------------------------

def test_absent_descriptor_is_empty(tmp_path):
    assert workflows.workflow_steps(tmp_path) == []
    assert workflows.workflow_labels(tmp_path) == []
    assert workflows.workflow_tab_ids(tmp_path) == []
    assert workflows.workflow_targets(tmp_path) == []
    assert workflows.workflow_template_roots(tmp_path) == []
    assert workflows.workflow_text_globs(tmp_path) == []


def test_descriptor_without_relevant_sections_is_empty(tmp_path):
    _write_descriptor(tmp_path, "# Notes\n\n## Other\n- something\n")
    assert workflows.workflow_steps(tmp_path) == []
    assert workflows.workflow_targets(tmp_path) == []
