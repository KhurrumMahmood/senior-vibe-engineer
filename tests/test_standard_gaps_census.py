"""Pin census.py — convention discovery before standard declaration.

Behaviors under test:

1. Variant counts are exact and majority math is correct.
2. Stragglers are the non-majority variants with correct file:line lists.
3. Opaque (non-literal payload) calls are counted separately, not folded
   into variants, and do not affect majority share.
4. dict() call payloads are *not* classified as literal-dict variants (v1
   only counts ``{...}`` dict-literal syntax).
5. No-calls result: variants empty, opaque zero.
6. run_census is deterministic: ties broken by variant key alpha order.

Plain ``unittest`` so the same file runs under Django's test runner
(host projects) and pytest (engineering-skills) unchanged.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_CENSUS = REPO_ROOT / ".claude/skills/find-standard-gaps/scripts/census.py"


def _load_census():
    spec = importlib.util.spec_from_file_location("census_under_test", _CENSUS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_MAJORITY_SRC = """\
from django.http import JsonResponse

def view_a(request):
    return JsonResponse({'success': True, 'data': 'x'})

def view_b(request):
    return JsonResponse({'success': True, 'data': 'y'})

def view_c(request):
    return JsonResponse({'success': True, 'data': 'z'})
"""

_MINORITY_SRC = """\
from django.http import JsonResponse

def view_err(request):
    return JsonResponse({'error': 'not found'}, status=404)
"""

_OPAQUE_SRC = """\
from django.http import JsonResponse

def view_opaque(request):
    payload = build_payload()
    return JsonResponse(payload)

def view_opaque2(request):
    return JsonResponse(some_service.get_result())
"""

_MIXED_SRC = """\
from django.http import JsonResponse

def view_ok(request):
    # majority variant: ['data','success'], no_status
    return JsonResponse({'success': True, 'data': 1})

def view_err(request):
    # minority variant: ['error'], status=400
    return JsonResponse({'error': 'bad'}, status=400)

def view_err2(request):
    # same minority variant: ['error'], status=400
    return JsonResponse({'error': 'also bad'}, status=400)

def view_opq(request):
    # opaque
    result = compute()
    return JsonResponse(result)
"""

_DICT_CALL_SRC = """\
from django.http import JsonResponse

def view_dict_call(request):
    # dict() call — NOT a dict literal, must be opaque in v1
    return JsonResponse(dict(success=True, error=None))
"""

_EMPTY_SRC = """\
from django.http import HttpResponse

def view_no_json(request):
    return HttpResponse('ok')
"""

_STATUS_EXPR_SRC = """\
from django.http import JsonResponse

def view_dynamic_status(request, code):
    return JsonResponse({'error': 'oops'}, status=code)
"""


class CensusConcernTests(unittest.TestCase):

    def setUp(self):
        self.census = _load_census()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, name: str, src: str) -> Path:
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
        return p

    def _run(self, *filenames: str) -> dict:
        concern = self.census.CONCERN_REGISTRY["json_response_envelope"]
        # Pass absolute paths
        paths = [str(self.root / f) for f in filenames]
        return self.census.run_census(concern, paths, self.root)

    # ------------------------------------------------------------------
    def test_single_variant_majority_100_percent(self):
        self._write("api/majority.py", _MAJORITY_SRC)
        result = self._run("api/majority.py")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["classified"], 3)
        self.assertEqual(result["opaque_count"], 0)
        self.assertEqual(len(result["variants"]), 1)
        v = result["variants"][0]
        self.assertEqual(v["count"], 3)
        self.assertAlmostEqual(v["share"], 1.0)
        self.assertEqual(result["majority_share"], 1.0)
        self.assertEqual(result["stragglers"], [])

    def test_variant_key_encoding(self):
        """Majority variant key must encode sorted keys + status correctly."""
        self._write("api/majority.py", _MAJORITY_SRC)
        result = self._run("api/majority.py")
        majority_variant = result["majority_variant"]
        # Keys are 'success' and 'data' → sorted → ["data","success"]
        self.assertIn('"data"', majority_variant)
        self.assertIn('"success"', majority_variant)
        self.assertIn("no_status", majority_variant)

    def test_minority_straggler_identification(self):
        self._write("api/majority.py", _MAJORITY_SRC)
        self._write("api/minority.py", _MINORITY_SRC)
        result = self._run("api/majority.py", "api/minority.py")

        self.assertEqual(result["classified"], 4)
        self.assertEqual(result["opaque_count"], 0)
        # Two distinct variants
        self.assertEqual(len(result["variants"]), 2)

        variant_keys = [v["variant"] for v in result["variants"]]
        # Majority first (3 calls)
        self.assertIn("no_status", variant_keys[0])

        # One straggler
        self.assertEqual(len(result["stragglers"]), 1)
        straggler = result["stragglers"][0]
        self.assertEqual(straggler["count"], 1)
        # Straggler file is minority.py
        self.assertTrue(any("minority.py" in s["file"]
                            for s in straggler["sites"]))

    def test_status_kwarg_appears_in_variant_key(self):
        self._write("api/minority.py", _MINORITY_SRC)
        result = self._run("api/minority.py")
        self.assertEqual(result["classified"], 1)
        variant = result["majority_variant"]
        self.assertIn("status=404", variant)

    def test_opaque_not_in_classified(self):
        self._write("api/opaque.py", _OPAQUE_SRC)
        result = self._run("api/opaque.py")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["classified"], 0)
        self.assertEqual(result["opaque_count"], 2)
        self.assertEqual(result["variants"], [])
        self.assertIsNone(result["majority_variant"])
        self.assertIsNone(result["majority_share"])

    def test_opaque_does_not_affect_majority_share(self):
        """Majority share is over classified calls only, not total."""
        self._write("api/mixed.py", _MIXED_SRC)
        result = self._run("api/mixed.py")
        # 1 majority + 2 minority + 1 opaque
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["classified"], 3)
        self.assertEqual(result["opaque_count"], 1)
        # Minority has 2 calls, majority has 1 → majority is the minority variant
        # Actually: 1 no_status + 2 status=400 → status=400 is majority
        counts = {v["variant"]: v["count"] for v in result["variants"]}
        self.assertEqual(sum(counts.values()), 3)
        # Majority share denominator = classified (3), not total (4)
        self.assertAlmostEqual(result["majority_share"], 2 / 3, places=3)

    def test_dict_call_is_opaque(self):
        """dict(...) constructor payloads must be counted as opaque, not classified."""
        self._write("api/dict_call.py", _DICT_CALL_SRC)
        result = self._run("api/dict_call.py")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["classified"], 0)
        self.assertEqual(result["opaque_count"], 1)

    def test_no_json_response_calls(self):
        self._write("api/empty.py", _EMPTY_SRC)
        result = self._run("api/empty.py")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["classified"], 0)
        self.assertEqual(result["opaque_count"], 0)
        self.assertEqual(result["variants"], [])
        self.assertIsNone(result["majority_variant"])

    def test_status_expr_recorded_as_status_expr(self):
        """Non-literal status values are recorded as status=<expr>, not status=N."""
        self._write("api/status_expr.py", _STATUS_EXPR_SRC)
        result = self._run("api/status_expr.py")
        self.assertEqual(result["classified"], 1)
        variant = result["majority_variant"]
        self.assertIn("status=<expr>", variant)
        self.assertNotIn("status=code", variant)

    def test_deterministic_tie_breaking(self):
        """When two variants have equal counts, alpha order decides majority."""
        src_a = """\
from django.http import JsonResponse
def a(req): return JsonResponse({'aaa': 1})
"""
        src_b = """\
from django.http import JsonResponse
def b(req): return JsonResponse({'zzz': 1})
"""
        self._write("api/a.py", src_a)
        self._write("api/b.py", src_b)
        result = self._run("api/a.py", "api/b.py")
        self.assertEqual(result["classified"], 2)
        self.assertEqual(len(result["variants"]), 2)
        # Alphabetically first variant key should be majority on tie
        first_v = result["variants"][0]["variant"]
        second_v = result["variants"][1]["variant"]
        self.assertLess(first_v, second_v)
        self.assertEqual(result["majority_variant"], first_v)

    def test_straggler_file_line_accuracy(self):
        """Straggler sites must report the correct file and line number."""
        self._write("api/majority.py", _MAJORITY_SRC)
        self._write("api/minority.py", _MINORITY_SRC)
        result = self._run("api/majority.py", "api/minority.py")

        straggler = result["stragglers"][0]
        sites = straggler["sites"]
        self.assertEqual(len(sites), 1)
        site = sites[0]
        self.assertIn("minority.py", site["file"])
        # _MINORITY_SRC: JsonResponse is on line 4
        self.assertEqual(site["line"], 4)

    def test_multiple_files_aggregated(self):
        """Sites from multiple files are all counted."""
        self._write("api/a.py", _MINORITY_SRC)
        self._write("api/b.py", _MINORITY_SRC)
        result = self._run("api/a.py", "api/b.py")
        self.assertEqual(result["classified"], 2)
        self.assertEqual(result["majority_variant"],
                         result["variants"][0]["variant"])

    def test_directory_scan(self):
        """Passing a directory path recursively collects all .py files."""
        (self.root / "api").mkdir()
        self._write("api/v1.py", _MAJORITY_SRC)
        self._write("api/v2.py", _MINORITY_SRC)
        result = self._run("api")
        self.assertEqual(result["total"], 4)

    def test_skip_dirs_honoured(self):
        """Files under SKIP_DIRS (e.g. migrations) are not scanned."""
        (self.root / "app" / "migrations").mkdir(parents=True)
        self._write("app/migrations/0001_initial.py", _MAJORITY_SRC)
        self._write("app/views.py", _MINORITY_SRC)
        result = self._run("app")
        # Only minority.py is outside SKIP_DIRS
        self.assertEqual(result["total"], 1)

    def test_syntax_error_file_skipped_gracefully(self):
        """A file with a syntax error is silently skipped."""
        self._write("api/broken.py", "def foo(:\n    pass\n")
        self._write("api/ok.py", _MINORITY_SRC)
        result = self._run("api/broken.py", "api/ok.py")
        # broken.py yields nothing; ok.py yields 1 classified
        self.assertEqual(result["total"], 1)


class CensusMainCLITests(unittest.TestCase):
    """Smoke-test the main() CLI entry point."""

    def setUp(self):
        self.census = _load_census()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_main_returns_zero(self):
        (self.root / "api").mkdir()
        (self.root / "api" / "views.py").write_text(_MIXED_SRC)
        rc = self.census.main([
            "--concern", "json_response_envelope",
            "--project-root", str(self.root),
            str(self.root / "api"),
        ])
        self.assertEqual(rc, 0)

    def test_main_writes_json_artifact(self):
        (self.root / "api").mkdir()
        (self.root / "api" / "views.py").write_text(_MAJORITY_SRC)
        out = self.root / "findings.json"
        self.census.main([
            "--concern", "json_response_envelope",
            "--project-root", str(self.root),
            str(self.root / "api"),
            "--json", str(out),
        ])
        self.assertTrue(out.exists())
        import json as _json
        data = _json.loads(out.read_text())
        self.assertIn("variants", data)
        self.assertIn("majority_variant", data)
        self.assertIn("opaque_count", data)


if __name__ == "__main__":
    unittest.main()
