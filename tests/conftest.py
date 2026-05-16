"""Shared fixtures for the scripts/ runtime test suite.

Every substrate script (decisions / plans / specs / ledger / precedents)
exposes ``main(argv)`` and accepts directory-override args, so tests drive
them by calling ``main([...])`` against ``tmp_path``-seeded directories —
no tracked file is ever read or mutated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Put scripts/ on sys.path so tests can ``import decisions``, ``import specs``,
# etc. Each script also re-inserts this directory for its own ``_lib`` import.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _emit(path: Path, metadata: dict, body: str) -> Path:
    """Write a markdown file: a YAML frontmatter block followed by body."""
    path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(metadata, sort_keys=False, default_flow_style=False)
    path.write_text(f"---\n{front}---\n\n{body}", encoding="utf-8")
    return path


@pytest.fixture
def write_adr():
    """Return a helper that writes one ADR markdown file into a decisions dir."""
    def _write(decisions_dir, *, id="0001", slug="first-decision",
               status="accepted", date="2026-01-01", title=None,
               supersedes=None, superseded_by=None, applies_to=None,
               tags=None, body=None):
        title = title or slug.replace("-", " ").title()
        metadata = {
            "id": id,
            "title": title,
            "status": status,
            "date": date,
            "deciders": [],
            "supersedes": supersedes or [],
            "superseded_by": superseded_by,
            "applies_to": applies_to or [],
            "tags": tags or [],
        }
        body = body if body is not None else f"# {title}\n\n## Context\n\nSeeded.\n"
        return _emit(Path(decisions_dir) / f"{id}-{slug}.md", metadata, body)
    return _write


@pytest.fixture
def write_plan():
    """Return a helper that writes one plan markdown file into a plans dir."""
    def _write(plans_dir, *, slug="sample-plan", status="draft",
               date="2026-01-01", title=None, motivating_decision=None,
               successor_spec=None, subsystems=None, workflows=None, body=None):
        title = title or slug.replace("-", " ").title()
        metadata = {
            "name": slug,
            "title": title,
            "status": status,
            "date": date,
            "authors": [],
            "motivating_decision": motivating_decision,
            "successor_spec": successor_spec,
            "subsystems": subsystems or [],
            "workflows": workflows or [],
        }
        body = body if body is not None else f"# {title}\n\nPlan body.\n"
        return _emit(Path(plans_dir) / f"{slug}.md", metadata, body)
    return _write


@pytest.fixture
def write_spec():
    """Return a helper that writes one spec markdown file into a specs dir."""
    def _write(specs_dir, *, spec_id="sample-spec", status="draft", title=None,
               code_roots=None, last_audited="2026-01-01", body=None):
        title = title or spec_id.replace("-", " ").title()
        metadata = {
            "id": spec_id,
            "title": title,
            "status": status,
            "last_audited": last_audited,
            "code_roots": code_roots or [],
        }
        body = body if body is not None else f"# {title}\n\nSpec body.\n"
        return _emit(Path(specs_dir) / f"{spec_id}.md", metadata, body)
    return _write
