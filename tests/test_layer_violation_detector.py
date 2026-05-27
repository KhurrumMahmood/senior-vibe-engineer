"""Regression guard: find-layer-violation must scan package ``__init__.py``.

Post-ADR-0011-style layouts carry real view/task code in package
``__init__.py`` files (e.g. pnci's ``app/pages/<area>/__init__.py``). The
detector's default skip set once listed ``"__init__.py"`` — a stale assumption
from the flat ``core/views/*.py`` era — which silently dropped those modules
from the layer-violation scan (measured: 16 → 19 findings once unskipped). This
pins the walker to include package ``__init__.py`` while still skipping
test/conftest files, which legitimately import across layers.

Plain ``unittest`` so the same file runs under Django's test runner (pnci) and
pytest (engineering-skills-2) unchanged.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_DETECT = REPO_ROOT / ".claude/skills/find-layer-violation/scripts/detect.py"
_COMMON = REPO_ROOT / ".claude/skills/_common"


def _load_detect():
    if str(_COMMON) not in sys.path:
        sys.path.insert(0, str(_COMMON))
    spec = importlib.util.spec_from_file_location("flv_detect_under_test", _DETECT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LayerViolationWalkerTests(unittest.TestCase):
    def test_walker_scans_package_init_but_skips_test_files(self) -> None:
        detect = _load_detect()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pkg = root / "app" / "pages" / "sites"
            pkg.mkdir(parents=True)
            (pkg / "__init__.py").write_text("class SitesView:\n    pass\n")
            (pkg / "helpers.py").write_text("VALUE = 1\n")
            (pkg / "test_sites.py").write_text("VALUE = 1\n")
            (pkg / "conftest.py").write_text("VALUE = 1\n")

            walked = {
                p.name
                for p in detect._walk_python_files(
                    root, detect._DEFAULT_SKIP_FILE_GLOBS, root
                )
            }

        self.assertIn(
            "__init__.py",
            walked,
            "package __init__.py must be scanned — ADR-0011 view code lives there",
        )
        self.assertIn("helpers.py", walked)
        self.assertNotIn("test_sites.py", walked)
        self.assertNotIn("conftest.py", walked)


if __name__ == "__main__":
    unittest.main()
