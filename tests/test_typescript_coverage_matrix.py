"""Mechanical completeness and routing-honesty checks for TypeScript coverage."""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX = REPO_ROOT / ".claude" / "tasks" / "typescript-skill-coverage.json"
CATALOG = REPO_ROOT / ".claude" / "skills" / "which-skill" / "catalog.json"
ALLOWED = {
    "typescript-supported",
    "validated-neutral",
    "stack-bound",
    "ecosystem-runtime",
}
EXPECTED_COUNTS = {
    "typescript-supported": 22,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}


def test_typescript_coverage_matrix_is_complete_and_honest() -> None:
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    rows = payload["skills"]
    names = [row["skill"] for row in rows]
    actual = {
        path.parent.name
        for path in (REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md")
    }

    assert len(rows) == 76
    assert len(names) == len(set(names))
    assert set(names) == actual
    assert Counter(row["disposition"] for row in rows) == EXPECTED_COUNTS
    assert {row["disposition"] for row in rows} == ALLOWED

    template = payload["stock_install_command_template"]
    assert "skills@1.5.19" in template
    assert "{skill}" in template
    assert "--copy" in template
    reviewed_revisions: set[str] = set()
    for row in rows:
        assert (REPO_ROOT / row["evidence_path"]).is_file(), row
        expected_command = template.format(skill=row["skill"])
        assert row["install_command"] == expected_command, row
        assert f"--skill {row['skill']}" in row["install_command"]
        assert row["reviewed_revision"], row
        reviewed_revisions.add(row["reviewed_revision"])
        assert row["install_status"] in {
            "passed",
            "deferred-named-stack",
            "not-host-language-variant",
        }

    assert payload["reviewed_revision"] in reviewed_revisions
    for revision in reviewed_revisions:
        revision_check = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert revision_check.returncode == 0, revision_check.stderr

    catalog = {
        item["name"]: item
        for item in json.loads(CATALOG.read_text(encoding="utf-8"))["skills"]
    }
    for row in rows:
        metadata = catalog[row["skill"]]
        disposition = row["disposition"]
        language = metadata.get("language", "any")
        framework = metadata.get("framework", "any")
        scans = set(metadata.get("scans", []))
        if disposition == "validated-neutral":
            assert (language, framework) == ("any", "any"), row
        elif disposition == "typescript-supported":
            assert language in {"any", "typescript"}, row
            if metadata.get("job") == "suspect" and "scans" in metadata:
                assert "typescript" in scans, row
        elif disposition == "stack-bound":
            assert language != "any" or framework != "any", row
