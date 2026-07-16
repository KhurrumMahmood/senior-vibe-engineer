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
import hashlib
import json
import platform
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from _lib.host_profile import profile_host
from _lib.support_evidence import canonical_evidence_hash, sha256_bytes, sha256_file

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


def _write_evidenced_typescript_skill(skills_root: Path, name: str = "find-typescript-shape") -> Path:
    skill_dir = skills_root / name
    scripts = skill_dir / "scripts"
    scripts.mkdir(parents=True)
    scanner = scripts / "scan.py"
    claim = {"kind": "skill", "id": name}
    observation = {"claim": claim, "result": "pass", "subject": "typescript"}
    scanner.write_text(
        "import json\n"
        f"observation = {observation!r}\n"
        "print(json.dumps(observation, sort_keys=True, separators=(',', ':')))\n",
        encoding="utf-8",
    )
    digest = sha256_file(scanner)
    test_attestation = {"kind": "test", "path": "scripts/scan.py", "sha256": digest}
    script_attestation = {"kind": "script", "path": "scripts/scan.py", "sha256": digest}
    expected = json.dumps(observation, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    evidence = {
        "claim": claim,
        "fixtures": [
            {
                "subject": "typescript",
                "command": [sys.executable, "scripts/scan.py"],
                "cwd": ".",
                "expected_observation": observation,
                "expected_stdout_sha256": sha256_bytes(expected),
                "timeout_seconds": 10,
            }
        ],
        "artifacts": [test_attestation, script_attestation],
        "tools": [{"name": "python-runtime", "command": [sys.executable, "--version"]}],
        "platforms": [{"system": platform.system(), "machine": platform.machine()}],
    }
    evidence["evidence_hash"] = canonical_evidence_hash(evidence)
    metadata = {
        "name": name,
        "description": "Fixture detector",
        "job": "suspect",
        "language": "typescript",
        "framework": "react",
        "scans": ["typescript"],
        "capability_contract": 1,
        "layer": "framework",
        "binding": "react",
        "bindings": [],
        "support": "experimental",
        "capabilities": ["analysis.symbols"],
        "capability_evidence": {"typescript": [test_attestation]},
        "support_evidence": evidence,
        "scan_implementations": {
            "typescript": {
                "mechanism": "typescript-syntax",
                "path": "scripts/scan.py",
                "sha256": digest,
            }
        },
    }
    (skill_dir / "SKILL.md").write_text(
        f"---\n{yaml.safe_dump(metadata, sort_keys=False)}---\n\n# /{name}\n",
        encoding="utf-8",
    )
    return skill_dir


def _read_skill_metadata(skill_dir: Path) -> dict:
    text = skill_dir.joinpath("SKILL.md").read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def _write_skill_metadata(skill_dir: Path, metadata: dict) -> None:
    skill_dir.joinpath("SKILL.md").write_text(
        f"---\n{yaml.safe_dump(metadata, sort_keys=False)}---\n\n# /{metadata['name']}\n",
        encoding="utf-8",
    )


def _rehash_profile(profile: dict) -> None:
    unhashed = dict(profile)
    unhashed.pop("profile_sha256", None)
    encoded = json.dumps(unhashed, sort_keys=True, separators=(",", ":")).encode()
    profile["profile_sha256"] = hashlib.sha256(encoded).hexdigest()


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
                "--accept", "frontend:css=generated stylesheet snapshot",
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

    def test_profile_mode_requires_current_executable_scan_evidence(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "host"
            root.mkdir()
            (root / "package.json").write_text('{"devDependencies":{"typescript":"5.9.3"}}')
            (root / "tsconfig.json").write_text("{}\n")
            (root / "src").mkdir()
            (root / "src" / "large.ts").write_text("export const value = 1;\n" * 1200)
            profile = profile_host(root)
            profile_path = Path(d) / "host-profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            skills = Path(d) / "skills"
            evidenced = _write_evidenced_typescript_skill(skills)
            output = Path(d) / "perimeter.json"

            rc = scan.main(
                [
                    "--project-root", str(root),
                    "--skills-root", str(skills),
                    "--host-profile", str(profile_path),
                    "--min-loc", "1000",
                    "--output", str(output),
                    "--fail-on-gap",
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(output.read_text())
            self.assertEqual(payload["coverage_mode"], "executable-evidence")
            self.assertEqual(payload["gaps"], [])
            cell = next(item for item in payload["cells"] if item["language"] == "typescript")
            self.assertEqual(cell["covered_by"], ["find-typescript-shape"])

            # A post-attestation edit makes the installed implementation stale;
            # the same declaration can no longer count as coverage.
            (evidenced / "scripts" / "scan.py").write_text("print('stale')\n")
            rc = scan.main(
                [
                    "--project-root", str(root),
                    "--skills-root", str(skills),
                    "--host-profile", str(profile_path),
                    "--min-loc", "1000",
                    "--output", str(output),
                    "--fail-on-gap",
                ]
            )
            self.assertEqual(rc, 1)
            payload = json.loads(output.read_text())
            cell = next(item for item in payload["cells"] if item["language"] == "typescript")
            self.assertEqual(cell["covered_by"], [])
            self.assertTrue(cell["rejected_coverage_candidates"])
            self.assertTrue(
                any("sha256 mismatch" in reason for reason in cell["rejected_coverage_candidates"][0]["reasons"])
            )

            rc = scan.main(
                [
                    "--project-root", str(root),
                    "--skills-root", str(skills),
                    "--host-profile", str(profile_path),
                    "--min-loc", "1000",
                    "--accept", ".:typescript=temporary migration gap",
                    "--output", str(output),
                    "--fail-on-gap",
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(output.read_text())
            self.assertEqual(
                payload["accepted_exclusions"],
                [{"root": ".", "language": "typescript", "reason": "temporary migration gap"}],
            )

    def test_profile_mode_rejects_rehashed_malformed_profile_before_false_clean(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "host"
            root.mkdir()
            (root / "package.json").write_text('{"devDependencies":{"typescript":"5.9.3"}}')
            (root / "tsconfig.json").write_text("{}\n")
            (root / "src").mkdir()
            (root / "src" / "large.ts").write_text("export const value = 1;\n" * 1200)
            profile = profile_host(root)
            profile["roots"][0]["code_roots"] = "src"
            _rehash_profile(profile)
            profile_path = Path(d) / "host-profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            output = Path(d) / "perimeter.json"

            rc = scan.main([
                "--project-root", str(root),
                "--host-profile", str(profile_path),
                "--output", str(output),
                "--fail-on-gap",
            ])

            self.assertEqual(rc, 2)
            self.assertFalse(output.exists())

    def test_accepted_exclusion_without_reason_is_rejected(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._build_host(root)
            self.assertEqual(
                scan.main(["--project-root", str(root), "--accept", "frontend:css"]),
                2,
            )

    def test_profile_mode_treats_uninstalled_detector_as_gap(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "host"
            root.mkdir()
            (root / "package.json").write_text('{"devDependencies":{"typescript":"5.9.3"}}')
            (root / "tsconfig.json").write_text("{}\n")
            (root / "src").mkdir()
            (root / "src" / "large.ts").write_text("export const value = 1;\n" * 1200)
            profile_path = Path(d) / "host-profile.json"
            profile_path.write_text(json.dumps(profile_host(root)), encoding="utf-8")
            skills = Path(d) / "empty-skills"
            skills.mkdir()
            output = Path(d) / "perimeter.json"

            rc = scan.main([
                "--project-root", str(root),
                "--skills-root", str(skills),
                "--host-profile", str(profile_path),
                "--min-loc", "1000",
                "--output", str(output),
                "--fail-on-gap",
            ])

            self.assertEqual(rc, 1)
            payload = json.loads(output.read_text())
            self.assertEqual(payload["detectors"], [])
            self.assertEqual(payload["gaps"][0]["language"], "typescript")

    def test_profile_mode_rejects_detector_with_missing_evidence_contract(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "host"
            root.mkdir()
            (root / "package.json").write_text('{"devDependencies":{"typescript":"5.9.3"}}')
            (root / "tsconfig.json").write_text("{}\n")
            (root / "src").mkdir()
            (root / "src" / "large.ts").write_text("export const value = 1;\n" * 1200)
            profile_path = Path(d) / "host-profile.json"
            profile_path.write_text(json.dumps(profile_host(root)), encoding="utf-8")
            skills = Path(d) / "skills"
            _write_skill(
                skills,
                "find-typescript-shape",
                "name: find-typescript-shape\njob: suspect\nlanguage: typescript\nscans: [typescript]",
            )
            output = Path(d) / "perimeter.json"

            rc = scan.main([
                "--project-root", str(root),
                "--skills-root", str(skills),
                "--host-profile", str(profile_path),
                "--min-loc", "1000",
                "--output", str(output),
                "--fail-on-gap",
            ])

            self.assertEqual(rc, 1)
            candidate = json.loads(output.read_text())["gaps"][0]["rejected_coverage_candidates"][0]
            self.assertIn("missing capability_contract", candidate["reasons"])

    def test_profile_mode_rejects_version_incompatible_detector(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "host"
            root.mkdir()
            (root / "package.json").write_text('{"devDependencies":{"typescript":"5.9.3"}}')
            (root / "tsconfig.json").write_text("{}\n")
            (root / "src").mkdir()
            (root / "src" / "large.ts").write_text("export const value = 1;\n" * 1200)
            profile_path = Path(d) / "host-profile.json"
            profile_path.write_text(json.dumps(profile_host(root)), encoding="utf-8")
            skills = Path(d) / "skills"
            skill = _write_evidenced_typescript_skill(skills)
            metadata = _read_skill_metadata(skill)
            metadata["capability_contract"] = 999
            _write_skill_metadata(skill, metadata)
            output = Path(d) / "perimeter.json"

            rc = scan.main([
                "--project-root", str(root),
                "--skills-root", str(skills),
                "--host-profile", str(profile_path),
                "--min-loc", "1000",
                "--output", str(output),
                "--fail-on-gap",
            ])

            self.assertEqual(rc, 1)
            reasons = json.loads(output.read_text())["gaps"][0]["rejected_coverage_candidates"][0]["reasons"]
            self.assertTrue(any("capability_contract must be 1" in reason for reason in reasons))

    def test_profile_mode_executes_evidence_and_rejects_wrong_output(self) -> None:
        scan = _load_scan()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "host"
            root.mkdir()
            (root / "package.json").write_text('{"devDependencies":{"typescript":"5.9.3"}}')
            (root / "tsconfig.json").write_text("{}\n")
            (root / "src").mkdir()
            (root / "src" / "large.ts").write_text("export const value = 1;\n" * 1200)
            profile_path = Path(d) / "host-profile.json"
            profile_path.write_text(json.dumps(profile_host(root)), encoding="utf-8")
            skills = Path(d) / "skills"
            skill = _write_evidenced_typescript_skill(skills)
            scanner = skill / "scripts" / "scan.py"
            scanner.write_text("print('wrong output')\n", encoding="utf-8")
            digest = sha256_file(scanner)
            metadata = _read_skill_metadata(skill)
            metadata["capability_evidence"]["typescript"][0]["sha256"] = digest
            metadata["scan_implementations"]["typescript"]["sha256"] = digest
            for artifact in metadata["support_evidence"]["artifacts"]:
                if artifact["path"] == "scripts/scan.py":
                    artifact["sha256"] = digest
            metadata["support_evidence"].pop("evidence_hash")
            metadata["support_evidence"]["evidence_hash"] = canonical_evidence_hash(
                metadata["support_evidence"]
            )
            _write_skill_metadata(skill, metadata)
            output = Path(d) / "perimeter.json"

            rc = scan.main([
                "--project-root", str(root),
                "--skills-root", str(skills),
                "--host-profile", str(profile_path),
                "--min-loc", "1000",
                "--output", str(output),
                "--fail-on-gap",
            ])

            self.assertEqual(rc, 1)
            reasons = json.loads(output.read_text())["gaps"][0]["rejected_coverage_candidates"][0]["reasons"]
            self.assertTrue(any("stdout" in reason or "observation" in reason for reason in reasons))


if __name__ == "__main__":
    unittest.main()
