"""Pin find-omnibus language-adapter behavior (ADR 0032).

The clustering/scoring core is language-neutral; per-language symbol
extraction adapters feed it. Pins:

1. Python adapter (exact ast) still flags a multi-domain module and
   stays silent on a cohesive one — pre-ADR behavior preserved.
2. JavaScript adapter (column-0 heuristic) flags a multi-domain JS file,
   stays silent on a cohesive one, and records ``analyzer`` /
   ``language`` so reviewers can calibrate trust in heuristic findings.
3. Minified/test JS files are skipped by default.

Plain ``unittest`` so the same file runs under Django's test runner
(host projects) and pytest (engineering-skills) unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_DETECT = REPO_ROOT / ".claude/skills/find-omnibus/scripts/detect.py"


def _load_detect():
    spec = importlib.util.spec_from_file_location("omnibus_detect_under_test", _DETECT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _py_omnibus_source() -> str:
    parts = []
    for domain in ("invoice", "shipment", "customer", "inventory"):
        for verb in ("load", "save"):
            parts.append(f"def {verb}_{domain}_record():\n    return 1\n")
    return "\n".join(parts)


def _js_omnibus_source() -> str:
    parts = []
    for domain in ("invoice", "shipment", "customer", "inventory"):
        parts.append(f"function load{domain.title()}Record() {{ return 1; }}")
        parts.append(f"const save{domain.title()}Record = () => 1;")
    parts.append("window.OmnibusModule = { loadInvoiceRecord };")
    return "\n".join(parts) + "\n"


def _js_cohesive_source() -> str:
    return (
        "function loadInvoiceRecord() { return 1; }\n"
        "function saveInvoiceRecord() { return 1; }\n"
        "const formatInvoiceTotal = (x) => x;\n"
    )


class OmnibusLanguageAdapterTests(unittest.TestCase):
    def _run(self, detect, target: Path, root: Path) -> list[dict]:
        out = root / "out.jsonl"
        rc = detect.main([
            "--target", str(target),
            "--project-root", str(root),
            "--output", str(out),
        ])
        self.assertEqual(rc, 0)
        return [json.loads(line) for line in out.read_text().splitlines()]

    def test_python_adapter_flags_multi_domain_and_skips_cohesive(self) -> None:
        detect = _load_detect()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "app"
            src.mkdir()
            (src / "omnibus.py").write_text(_py_omnibus_source())
            (src / "cohesive.py").write_text(
                "def load_invoice():\n    return 1\n\n"
                "def save_invoice():\n    return 1\n"
            )
            records = self._run(detect, src, root)
            files = {r["file"] for r in records}
            self.assertIn("app/omnibus.py", files)
            self.assertNotIn("app/cohesive.py", files)
            rec = next(r for r in records if r["file"] == "app/omnibus.py")
            self.assertEqual(rec["analyzer"], "python-ast")
            self.assertEqual(rec["language"], "python")
            self.assertEqual(rec["and_count"], 3)

    def test_javascript_adapter_flags_multi_domain_and_skips_cohesive(self) -> None:
        detect = _load_detect()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "static"
            src.mkdir()
            (src / "omnibus.js").write_text(_js_omnibus_source())
            (src / "cohesive.js").write_text(_js_cohesive_source())
            records = self._run(detect, src, root)
            files = {r["file"] for r in records}
            self.assertIn("static/omnibus.js", files)
            self.assertNotIn("static/cohesive.js", files)
            rec = next(r for r in records if r["file"] == "static/omnibus.js")
            self.assertEqual(rec["analyzer"], "javascript-syntax")
            self.assertEqual(rec["language"], "javascript")
            self.assertGreaterEqual(rec["and_count"], 3)
            cluster_names = {c["name"] for c in rec["clusters"]}
            self.assertTrue(
                {"invoice", "shipment", "customer", "inventory"} <= cluster_names,
                cluster_names,
            )

    def test_minified_and_test_js_skipped(self) -> None:
        detect = _load_detect()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "static"
            src.mkdir()
            (src / "app.min.js").write_text(_js_omnibus_source())
            (src / "app.spec.js").write_text(_js_omnibus_source())
            records = self._run(detect, src, root)
            self.assertEqual(records, [])

    def test_language_filter_restricts_scan(self) -> None:
        detect = _load_detect()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "mixed"
            src.mkdir()
            (src / "omnibus.py").write_text(_py_omnibus_source())
            (src / "omnibus.js").write_text(_js_omnibus_source())
            out = root / "out.jsonl"
            rc = detect.main([
                "--target", str(src),
                "--project-root", str(root),
                "--output", str(out),
                "--language", "javascript",
            ])
            self.assertEqual(rc, 0)
            records = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual({r["language"] for r in records}, {"javascript"})


if __name__ == "__main__":
    unittest.main()
