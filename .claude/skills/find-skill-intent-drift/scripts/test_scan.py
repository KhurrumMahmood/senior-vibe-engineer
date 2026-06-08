#!/usr/bin/env python3
"""Regression tests for find-skill-intent-drift's intent-aware stale band.

Pins the fix that replaced the raw git-timestamp stale compare (which over-fired on every
mechanical body sweep — core/ -> app/ path references, prose edits below the frontmatter)
with a frontmatter-intent compare. The flagship cases the timestamp compare could not get
right:

  FM1  a body-only edit after the contract commit does NOT flag stale
  FM2  a frontmatter intent edit (e.g. a new not_for clause) DOES flag stale
  FM3  a path-only frontmatter edit (core/ -> app/ inside argument-hint or a path
       reference) does NOT flag stale — path tokens are normalized away
  FM4  an operational-key-only edit (allowed-tools) does NOT flag stale
  FM5  SKILL.md absent at the contract commit flags stale (intent unvouchable)
  FM6  an uncommitted contract stays "baseline", never stale

  plus direct unit coverage of the normalization primitives:
  N1   intent_fingerprint drops operational keys and collapses path tokens
  N2   frontmatter_block slices the leading ---...--- block; None without a closing fence

Run:  .venv/bin/python .claude/skills/find-skill-intent-drift/scripts/test_scan.py
"""
from __future__ import annotations

import importlib.util
import os
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
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


scan = _load("intent_scan", "scan.py")


# A minimal but realistic SKILL.md frontmatter + body. The body is what mechanical sweeps
# churn; the frontmatter is the intent surface the contract vouches for.
def skill_md(*, not_for_extra: str = "", arg_hint_dir: str = "core/", body: str = "original body",
             allowed_tools: str = "Bash, Read") -> str:
    return textwrap.dedent(f"""\
        ---
        name: demo-skill
        description: |
          Detect a thing and report it. Read-only.
        argument-hint: "[directory — defaults to {arg_hint_dir}]"
        allowed-tools: {allowed_tools}
        user-invocable: true
        tier: maintenance
        job: suspect
        best_for: |
          Reviewing a change that touches the thing.
        not_for: |
          Single-line changes.{not_for_extra}
        language: python
        framework: django
        ---

        # /demo-skill

        {body}
        """)


CONTRACT_YAML = textwrap.dedent("""\
    skill: demo-skill
    job: suspect
    problem_class: thing-detection
    intent: catch the thing
    solves: forgotten things
    born:
      commit: deadbeef
      date: '2026-01-01'
    dogfood_kind: fixture-pair
    provenance_confidence:
      textual: high
      structural: high
      temporal: high
      dogfood: high
    """)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True,
                   capture_output=True, text=True)


class IntentAwareStaleTests(unittest.TestCase):
    """Each test builds a real git repo: commit SKILL.md + contract together, then make a
    follow-up edit and re-commit *only the SKILL.md* (so the contract's last commit stays
    behind). classify_stale shells git against the relative paths, so we run from inside
    the repo (mirrors find-incomplete-sweep's PH5)."""

    def _scenario(self, second_skill_md: str) -> tuple[bool, str]:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            skilldir = root / ".claude/skills/demo-skill"
            contractdir = root / ".claude/contracts/skills"
            skilldir.mkdir(parents=True)
            contractdir.mkdir(parents=True)
            smd = skilldir / "SKILL.md"
            contract = contractdir / "demo-skill.yaml"

            smd.write_text(skill_md(), encoding="utf-8")
            contract.write_text(CONTRACT_YAML, encoding="utf-8")
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "t@t")
            _git(root, "config", "user.name", "t")
            _git(root, "add", "-A")
            _git(root, "commit", "-qm", "init: skill + contract")

            # Second commit: change SKILL.md only. Contract's last commit stays at init.
            smd.write_text(second_skill_md, encoding="utf-8")
            _git(root, "add", "--", str(smd))
            _git(root, "commit", "-qm", "edit skill")

            cwd0 = os.getcwd()
            os.chdir(root)
            try:
                return scan.classify_stale(
                    Path(".claude/contracts/skills/demo-skill.yaml"),
                    Path(".claude/skills/demo-skill/SKILL.md"),
                )
            finally:
                os.chdir(cwd0)

    def test_fm1_body_only_change_is_not_stale(self):
        is_stale, state = self._scenario(skill_md(body="REWRITTEN body — path sweep core/ -> app/ etc."))
        self.assertFalse(is_stale, f"body-only churn must not flag stale (got {state!r})")
        self.assertEqual(state, "ok")

    def test_fm2_frontmatter_intent_change_is_stale(self):
        # Extend the not_for block scalar on its existing logical line (a leading space,
        # no newline) so the fixture stays valid YAML — the change is a genuine,
        # path-free intent addition.
        is_stale, state = self._scenario(
            skill_md(not_for_extra=" Also not for the brand-new excluded case."))
        self.assertTrue(is_stale, "a real not_for intent addition must flag stale")
        self.assertIn("frontmatter intent changed", state)

    def test_fm3_path_only_frontmatter_change_is_not_stale(self):
        # The argument-hint default flips core/ -> app/ AND we add an in-prose path
        # reference swap; nothing about the intent changed.
        is_stale, state = self._scenario(skill_md(arg_hint_dir="app/", body="original body"))
        self.assertFalse(is_stale, f"a path-only frontmatter edit must not flag (got {state!r})")
        self.assertEqual(state, "ok")

    def test_fm4_operational_key_only_change_is_not_stale(self):
        is_stale, state = self._scenario(skill_md(allowed_tools="Bash, Read, Grep, Glob"))
        self.assertFalse(is_stale, f"allowed-tools churn is not intent (got {state!r})")
        self.assertEqual(state, "ok")

    def test_fm5_skillmd_absent_at_contract_commit_is_stale(self):
        # Commit the contract first (alone), THEN add the SKILL.md in a later commit, so
        # the SKILL.md does not exist as of the contract's last commit.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            skilldir = root / ".claude/skills/demo-skill"
            contractdir = root / ".claude/contracts/skills"
            skilldir.mkdir(parents=True)
            contractdir.mkdir(parents=True)
            contract = contractdir / "demo-skill.yaml"
            smd = skilldir / "SKILL.md"

            contract.write_text(CONTRACT_YAML, encoding="utf-8")
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "t@t")
            _git(root, "config", "user.name", "t")
            _git(root, "add", "--", str(contract))
            _git(root, "commit", "-qm", "contract only")

            smd.write_text(skill_md(), encoding="utf-8")
            _git(root, "add", "--", str(smd))
            _git(root, "commit", "-qm", "add skill md later")

            cwd0 = os.getcwd()
            os.chdir(root)
            try:
                is_stale, state = scan.classify_stale(
                    Path(".claude/contracts/skills/demo-skill.yaml"),
                    Path(".claude/skills/demo-skill/SKILL.md"),
                )
            finally:
                os.chdir(cwd0)
        self.assertTrue(is_stale, "SKILL.md absent at the contract commit must flag stale")
        self.assertIn("absent at contract commit", state)

    def test_fm6_uncommitted_contract_is_baseline(self):
        # Commit the SKILL.md but leave the contract untracked -> git_last_sha returns None.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            skilldir = root / ".claude/skills/demo-skill"
            contractdir = root / ".claude/contracts/skills"
            skilldir.mkdir(parents=True)
            contractdir.mkdir(parents=True)
            smd = skilldir / "SKILL.md"
            contract = contractdir / "demo-skill.yaml"

            smd.write_text(skill_md(), encoding="utf-8")
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "t@t")
            _git(root, "config", "user.name", "t")
            _git(root, "add", "--", str(smd))
            _git(root, "commit", "-qm", "skill only")
            contract.write_text(CONTRACT_YAML, encoding="utf-8")  # never committed

            cwd0 = os.getcwd()
            os.chdir(root)
            try:
                is_stale, state = scan.classify_stale(
                    Path(".claude/contracts/skills/demo-skill.yaml"),
                    Path(".claude/skills/demo-skill/SKILL.md"),
                )
            finally:
                os.chdir(cwd0)
        self.assertFalse(is_stale, "an uncommitted contract is baseline, not stale")
        self.assertEqual(state, "baseline (contract uncommitted)")


class NormalizationPrimitiveTests(unittest.TestCase):
    def test_n1_intent_fingerprint_drops_operational_and_collapses_paths(self):
        fm = textwrap.dedent("""\
            name: x
            argument-hint: "[directory — defaults to core/views]"
            allowed-tools: Bash, Read
            user-invocable: true
            job: suspect
            best_for: |
              Scan core/urls.py and app/views for the thing.
            """)
        fp = scan.intent_fingerprint(fm)
        # operational keys gone
        self.assertNotIn("name", fp)
        self.assertNotIn("argument-hint", fp)
        self.assertNotIn("allowed-tools", fp)
        self.assertNotIn("user-invocable", fp)
        # intent keys kept
        self.assertEqual(fp["job"], "suspect")
        # path tokens collapsed -> a core/ vs app/ swap inside best_for is invisible
        self.assertNotIn("core/urls.py", fp["best_for"])
        self.assertNotIn("app/views", fp["best_for"])
        self.assertIn("<PATH>", fp["best_for"])
        # the same text with core/ -> app/ fingerprints identically
        fp2 = scan.intent_fingerprint(fm.replace("core/urls.py", "app/urls.py")
                                        .replace("core/views", "app/views"))
        self.assertEqual(fp, fp2)

    def test_n2_frontmatter_block_slicing(self):
        text = "---\na: 1\nb: 2\n---\n# heading\nbody\n"
        self.assertEqual(scan.frontmatter_block(text), "a: 1\nb: 2")
        # no closing fence -> None (treated as malformed by the caller)
        self.assertIsNone(scan.frontmatter_block("---\na: 1\nno closing fence\n"))
        # no leading fence -> None
        self.assertIsNone(scan.frontmatter_block("# just a heading\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
