"""Pin find-perimeter-gaps coverage semantics (ADR 0032).

Three load-bearing behaviors:

1. A high-LOC root in a language no suspect detector declares via
   ``scans:`` (or an exact ``language:`` match) is a PERIMETER GAP.
2. ``language: any`` does NOT confer coverage — it declares a portable
   implementation, not a universal scan surface. Overstated coverage is
   the failure mode the audit exists to catch.
3. Below-threshold cells and ``--accept``-ed cells are not gap-flagged.

Plain ``unittest`` so the same file runs under Django's test runner
(host projects) and pytest (engineering-skills) unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAN = REPO_ROOT / ".claude/skills/find-perimeter-gaps/scripts/scan.py"


def _load_scan():
    spec = importlib.util.spec_from_file_location("perimeter_scan_under_test", _SCAN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_skill(skills_root: Path, name: str, frontmatter: str) -> None:
    skill_dir = skills_root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# /{name}\n")


class PerimeterGapsTests(unittest.TestCase):
    def _build_host(self, root: Path) -> Path:
        skills = root / ".claude" / "skills"
        _write_skill(skills, "find-omnibus", "name: find-omnibus\njob: suspect\nlanguage: python")
        _write_skill(
            skills,
            "find-frontend-duplication",
            "name: find-frontend-duplication\njob: suspect\nlanguage: python\n"
            "scans: [javascript, templates]",
        )
        # language:any suspect skill — must NOT cover anything.
        _write_skill(
            skills,
            "find-orphaned-ideas",
            "name: find-orphaned-ideas\njob: suspect\nlanguage: any",
        )
        # Non-suspect skill — ignored entirely.
        _write_skill(skills, "refactor-subsystem", "name: refactor-subsystem\njob: refactor\nlanguage: python")

        (root / "app").mkdir()
        (root / "app" / "views.py").write_text("x = 1\n" * 4000)
        (root / "static").mkdir()
        (root / "static" / "big.js").write_text("var a = 1;\n" * 4000)
        (root / "frontend").mkdir()
        (root / "frontend" / "main.css").write_text("a { color: red; }\n" * 4000)
        (root / "scripts").mkdir()
        (root / "scripts" / "tiny.sh").write_text("echo hi\n" * 10)
        return skills

    def test_gap_semantics_and_any_language_exclusion(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._build_host(root)
            out = root / "report.json"
            rc = scan.main([
                "--project-root", str(root),
                "--min-loc", "1000",
                "--output", str(out),
            ])
            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text())

            cells = {(c["root"], c["language"]): c for c in payload["cells"]}
            gap_keys = {(g["root"], g["language"]) for g in payload["gaps"]}

            # Python is covered by find-omnibus (exact language match).
            self.assertIn("find-omnibus", cells[("app", "python")]["covered_by"])
            self.assertNotIn(("app", "python"), gap_keys)
            # JS is covered via the explicit scans: declaration.
            self.assertIn(
                "find-frontend-duplication",
                cells[("static", "javascript")]["covered_by"],
            )
            self.assertNotIn(("static", "javascript"), gap_keys)
            # CSS has no declared coverage anywhere → gap. In particular,
            # the language:any skill must not appear as covering it.
            self.assertEqual(cells[("frontend", "css")]["covered_by"], [])
            self.assertIn(("frontend", "css"), gap_keys)
            # Below-threshold shell cell exists but is not flagged.
            self.assertFalse(cells[("scripts", "shell")]["significant"])
            self.assertNotIn(("scripts", "shell"), gap_keys)

    def test_accept_and_fail_on_gap(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._build_host(root)
            rc = scan.main([
                "--project-root", str(root),
                "--min-loc", "1000",
                "--fail-on-gap",
            ])
            self.assertEqual(rc, 1)
            rc = scan.main([
                "--project-root", str(root),
                "--min-loc", "1000",
                "--accept", "frontend:css",
                "--fail-on-gap",
            ])
            self.assertEqual(rc, 0)

    def test_data_like_files_and_artifact_dirs_are_skipped(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._build_host(root)
            # A 20K-line "template" is a crawled snapshot, not source.
            (root / "app" / "dump.html").write_text("<p>x</p>\n" * 20000)
            (root / "fixtures").mkdir()
            (root / "fixtures" / "page.html").write_text("<p>x</p>\n" * 4000)
            out = root / "report.json"
            rc = scan.main([
                "--project-root", str(root),
                "--min-loc", "1000",
                "--output", str(out),
            ])
            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text())
            keys = {(c["root"], c["language"]) for c in payload["cells"]}
            self.assertNotIn(("app", "templates"), keys)
            self.assertNotIn(("fixtures", "templates"), keys)


if __name__ == "__main__":
    unittest.main()
