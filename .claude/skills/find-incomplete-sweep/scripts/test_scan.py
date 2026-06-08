#!/usr/bin/env python3
"""Regression tests for find-incomplete-sweep's follow-up work.

Pins the two detector enhancements added after the first dogfood pass — the
cases the dogfood itself could not prove deterministically:

  dataclass-default pre-filter (kwarg-omission band)
    DC1  a @dataclass field WITH a default is dropped as a straggler kwarg
    DC2  a @dataclass field WITHOUT a default still surfaces (not over-filtered)
    DC3  field(default_factory=...) counts as a default; bare field() does not
    DC4  a function param with a default is dropped; a required param is not
    DC5  frozen / dataclasses.dataclass spellings are recognized

  placeholder-residue band
    PH1  raise NotImplementedError in a CONCRETE class is a candidate
    PH2  @abstractmethod / ABC / Protocol bodies are NOT candidates
    PH3  a `pass`-only and a `...`-only body are candidates; real code is not
    PH4  `return None  # TODO` is a candidate; a plain `return None` is not
    PH5  recency + reference-asymmetry gate: a recent referenced stub gates IN;
         a recent UNreferenced/non-sibling stub gates OUT

Run:  .venv/bin/python .claude/skills/find-incomplete-sweep/scripts/test_scan.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _load(modname: str, filename: str):
    spec = importlib.util.spec_from_file_location(modname, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod  # register before exec so @dataclass resolves
    spec.loader.exec_module(mod)
    return mod


scan = _load("sweep_scan", "scan.py")
placeholder = _load("sweep_placeholder", "placeholder.py")


def write_pkg(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body), encoding="utf-8")


class DataclassDefaultFilterTests(unittest.TestCase):
    def _defaults(self, code: str) -> tuple[dict, set]:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_pkg(root, {"m.py": code})
            return scan.collect_default_kwargs([str(root)])

    def test_dc1_default_field_recognized(self):
        defaults, _ = self._defaults("""
            from dataclasses import dataclass
            @dataclass
            class Spec:
                name: str
                description: str = ""
        """)
        self.assertIn("description", defaults["Spec"])
        self.assertNotIn("name", defaults["Spec"])  # DC2: required, not a default

    def test_dc3_field_factory_vs_bare_field(self):
        defaults, _ = self._defaults("""
            from dataclasses import dataclass, field
            @dataclass
            class C:
                a: list = field(default_factory=list)
                b: list = field()
                c: int = field(default=3)
        """)
        self.assertIn("a", defaults["C"])
        self.assertIn("c", defaults["C"])
        self.assertNotIn("b", defaults["C"])  # field() with no default = required

    def test_dc4_function_param_defaults(self):
        defaults, _ = self._defaults("""
            def helper(value, *, max_len=500, list_mode='per'):
                return value
            def required_only(a, b):
                return a
        """)
        self.assertIn("max_len", defaults["helper"])
        self.assertEqual(defaults["helper"]["max_len"], "500")  # default VALUE captured
        self.assertIn("list_mode", defaults["helper"])
        self.assertEqual(defaults["required_only"], {})  # no defaults -> empty map

    def test_dc5_frozen_and_dotted_dataclass(self):
        defaults, _ = self._defaults("""
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class F:
                x: int
                y: int = 0
        """)
        self.assertIn("y", defaults["F"])

    def test_filter_downranks_default_kwarg_straggler(self):
        # Build a callee Spec(name=, description=) where the majority pass
        # description and one straggler omits it. Because description has a
        # default, the straggler must be DOWN-RANKED (present but flagged
        # optional_by_default, never gated in) — not silently dropped, so the
        # flagship "siblings override a default" forgotten sweep stays visible.
        code = """
            from dataclasses import dataclass
            @dataclass
            class Spec:
                name: str
                description: str = ""
            a = Spec(name="a", description="x")
            b = Spec(name="b", description="y")
            c = Spec(name="c", description="z")
            d = Spec(name="d", description="w")
            e = Spec(name="e")  # straggler: omits description (defaulted) -> down-ranked
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_pkg(root, {"m.py": code})
            sites, _, _ = scan.collect_callsites([str(root)])
            defaults, _ = scan.collect_default_kwargs([str(root)])
            with_filter = scan.find_candidates(
                sites, min_callsites=4, majority_frac=0.75, min_present=3,
                default_kwargs=defaults)
            without_filter = scan.find_candidates(
                sites, min_callsites=4, majority_frac=0.75, min_present=3)
        # With the default map: the straggler is present but down-ranked, not dropped.
        desc = [f for f in with_filter if f.kwarg == "description"]
        self.assertTrue(desc, "down-ranked finding must still be present (not dropped)")
        self.assertTrue(
            all(f.optional_by_default for f in desc),
            "defaulted-field straggler must be flagged optional_by_default")
        # Without the default map: same straggler surfaces as a normal finding.
        without_desc = [f for f in without_filter if f.kwarg == "description"]
        self.assertTrue(without_desc, "the straggler should surface without the default map")
        self.assertTrue(
            all(not f.optional_by_default for f in without_desc),
            "without the default map it is not flagged optional_by_default (proves the "
            "default map is what down-ranks it, not the thresholds)")

    def test_value_awareness_promotes_consistent_nondefault_override(self):
        # get_page(url, country_code='xx'): the majority pass the SAME non-default
        # value 'us'; the straggler omits it (taking the different default 'xx').
        # Value-awareness PROMOTES the straggler back to a normal gated-in candidate
        # — the flagship forgotten override.
        code = """
            def get_page(url, country_code='xx'):
                return url
            a = get_page('a', country_code='us')
            b = get_page('b', country_code='us')
            c = get_page('c', country_code='us')
            d = get_page('d', country_code='us')
            e = get_page('e')  # straggler: omits country_code -> takes default 'xx'
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_pkg(root, {"m.py": code})
            sites, _, _ = scan.collect_callsites([str(root)])
            defaults, _ = scan.collect_default_kwargs([str(root)])
            found = scan.find_candidates(
                sites, min_callsites=4, majority_frac=0.75, min_present=3,
                default_kwargs=defaults)
        cc = [f for f in found if f.kwarg == "country_code"]
        self.assertTrue(cc, "the override straggler should surface")
        self.assertTrue(
            all(not f.optional_by_default for f in cc),
            "consistent non-default override must be PROMOTED, not down-ranked")
        self.assertTrue(
            all(f.override_value == "'us'" and f.default_value == "'xx'" for f in cc),
            "promotion records the override value ('us') and the default ('xx')")

    def test_value_awareness_keeps_default_equal_value_downranked(self):
        # Siblings pass a value EQUAL to the default — the explicit pass is
        # redundant and omission is harmless — so it STAYS down-ranked.
        code = """
            def get_page(url, country_code='us'):
                return url
            a = get_page('a', country_code='us')
            b = get_page('b', country_code='us')
            c = get_page('c', country_code='us')
            d = get_page('d', country_code='us')
            e = get_page('e')  # omits country_code -> takes default 'us' (identical)
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_pkg(root, {"m.py": code})
            sites, _, _ = scan.collect_callsites([str(root)])
            defaults, _ = scan.collect_default_kwargs([str(root)])
            found = scan.find_candidates(
                sites, min_callsites=4, majority_frac=0.75, min_present=3,
                default_kwargs=defaults)
        cc = [f for f in found if f.kwarg == "country_code"]
        self.assertTrue(cc, "the straggler should surface")
        self.assertTrue(
            all(f.optional_by_default for f in cc),
            "siblings passing the default value -> no promotion (stays down-ranked)")

    def test_value_awareness_no_promote_when_default_is_non_literal(self):
        # The default is a NAME reference (DEFAULT_CC) that may resolve to the
        # exact value the siblings pass ('us'). The textual sigs differ
        # ('<expr>' vs "'us'") but the runtime values could be EQUAL, so the
        # straggler must NOT be promoted — it stays down-ranked. Guards the
        # non-literal-default false-promotion bug.
        code = """
            DEFAULT_CC = 'us'
            def get_page(url, country_code=DEFAULT_CC):
                return url
            a = get_page('a', country_code='us')
            b = get_page('b', country_code='us')
            c = get_page('c', country_code='us')
            d = get_page('d', country_code='us')
            e = get_page('e')  # omits country_code -> default DEFAULT_CC (may == 'us')
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_pkg(root, {"m.py": code})
            sites, _, _ = scan.collect_callsites([str(root)])
            defaults, _ = scan.collect_default_kwargs([str(root)])
            found = scan.find_candidates(
                sites, min_callsites=4, majority_frac=0.75, min_present=3,
                default_kwargs=defaults)
        cc = [f for f in found if f.kwarg == "country_code"]
        self.assertTrue(cc, "the straggler should still surface")
        self.assertTrue(
            all(f.optional_by_default for f in cc),
            "non-literal default is not value-comparable -> must stay down-ranked")


class PlaceholderBandTests(unittest.TestCase):
    def _collect(self, code: str):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_pkg(root, {"m.py": code})
            items, _ = placeholder.collect_placeholders([str(root)])
            return {(i.symbol, i.kind) for i in items}

    def test_ph1_notimplemented_concrete(self):
        got = self._collect("""
            class Builder:
                def build(self):
                    raise NotImplementedError
        """)
        self.assertIn(("Builder.build", "not_implemented"), got)

    def test_ph2_abstract_excluded(self):
        got = self._collect("""
            from abc import ABC, abstractmethod
            from typing import Protocol
            class Base(ABC):
                def hook(self):
                    raise NotImplementedError
            class Other:
                @abstractmethod
                def thing(self):
                    raise NotImplementedError
            class P(Protocol):
                def f(self): ...
        """)
        self.assertEqual(got, set(), f"abstract bodies must be excluded, got {got}")

    def test_ph3_pass_and_ellipsis(self):
        got = self._collect("""
            class C:
                def a(self):
                    pass
                def b(self):
                    ...
                def real(self):
                    return 1 + 1
        """)
        self.assertIn(("C.a", "empty_body"), got)
        self.assertIn(("C.b", "empty_body"), got)
        self.assertNotIn(("C.real", "empty_body"), got)

    def test_ph4_todo_return_vs_plain_return(self):
        got = self._collect("""
            class C:
                def stub(self):
                    return None  # TODO: implement
                def fine(self):
                    return None
        """)
        self.assertIn(("C.stub", "todo_stub"), got)
        self.assertNotIn(("C.fine", "todo_stub"), got)

    def test_ph5_recency_reference_gate(self):
        # Build a real git repo so blame/recency resolve. One recent referenced
        # stub (gates IN) and one recent unreferenced non-sibling stub (gates
        # OUT for lack of asymmetry).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_pkg(root, {
                "app/svc.py": """
                    class Filled:
                        def run(self):
                            return 42
                    class Forgotten:
                        def run(self):
                            raise NotImplementedError  # sibling of Filled.run
                    class Lonely:
                        def orphan_only(self):
                            raise NotImplementedError
                """,
                "app/caller.py": """
                    from app.svc import Forgotten
                    def go():
                        return Forgotten().run()
                """,
            })
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)

            # placeholder.line_commit_time shells `git blame` against the file
            # path; run from inside the repo so the relative paths resolve.
            import os
            cwd0 = os.getcwd()
            os.chdir(root)
            try:
                items, _ = placeholder.run(["app"], max_age_days=3650.0)
            finally:
                os.chdir(cwd0)

            by_symbol = {i.symbol: i for i in items}
            self.assertIn("Forgotten.run", by_symbol)
            self.assertTrue(by_symbol["Forgotten.run"].gated_in,
                            "recent + referenced + sibling-implemented should gate IN")
            self.assertIn("Lonely.orphan_only", by_symbol)
            self.assertFalse(by_symbol["Lonely.orphan_only"].gated_in,
                             "recent but unreferenced + no sibling should gate OUT "
                             "(route to /find-dormant)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
