#!/usr/bin/env python3
"""Install a hand-built proposal into a seeded mini-host repo, by side-effect.

This is the deterministic stand-in for the human reviewer who executes a
``/prevent-regression`` proposal: it copies the proposal's rule script and
fixture pair into the repo's ``scripts/lint/`` and ``tests/lint/``, then applies
the wiring edits a guard requires — a ``RuleSpec`` in ``scripts/lint/run.py``, a
``local`` hook in ``.pre-commit-config.yaml``, a diff-scoped CI step in
``.github/workflows/ci.yml``, and a Canonical-Patterns bullet in ``CLAUDE.md``.

The scorer then grades the repo's resulting on-disk state. Separating "install"
from "score" keeps the scorer honest: it never trusts the proposal's say-so,
only what landed on disk.

A proposal directory must contain ``proposal_manifest.json``::

    {
      "rule_name": "no-bare-int-request",
      "module": "no_bare_int_request",          # scripts/lint/<module>.py
      "rule_script": "scripts/lint/no_bare_int_request.py",
      "bad_fixture": "tests/lint/no_bare_int_request_bad.py",
      "good_fixture": "tests/lint/no_bare_int_request_good.py",
      "include_regex": "^app/(services|views|pages|api)/.*\\\\.py$",
      "exclude_regex": "^tests/test_.*\\\\.py$",
      "claude_bullet": "- **`no-bare-int-request` / ...** ...",
      "wire_claude_md": true                     # optional, default true
    }

Paths in the manifest are relative to the proposal directory.

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

# Markers the seed leaves so installs are deterministic insertions, not blind
# appends.
RUN_PY_MARKER = "# --- prevent-regression guard registers its RuleSpec below this line ---"
PRECOMMIT_MARKER = "# --- prevent-regression guard adds its hook entry below this line ---"
CLAUDE_MARKER = "<!-- prevent-regression guard appends its canonical-pattern bullet below -->"


def _load_manifest(proposal_dir: Path) -> dict:
    manifest_path = proposal_dir / "proposal_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"error: {manifest_path} not found")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _copy_artifacts(proposal_dir: Path, repo: Path, manifest: dict) -> None:
    """Copy rule script + fixtures into the repo, preserving relative layout."""
    for key in ("rule_script", "bad_fixture", "good_fixture"):
        rel = manifest[key]
        src = proposal_dir / rel
        if not src.exists():
            raise SystemExit(f"error: proposal artifact missing: {src}")
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)


def _wire_run_py(repo: Path, manifest: dict) -> None:
    run_py = repo / "scripts/lint/run.py"
    text = run_py.read_text(encoding="utf-8")
    if manifest["rule_name"] in text:
        return  # idempotent
    exclude = manifest.get("exclude_regex")
    exclude_line = (
        f'        exclude=re.compile(r"{exclude}"),\n' if exclude else ""
    )
    # The marker sits at a 4-space indent; a bare-substring replace keeps those
    # 4 spaces in front of the first injected line, so `RuleSpec(` leads with
    # none of its own (it inherits the file's 4). Inside a parenthesised tuple
    # Python ignores indentation, but we keep it clean anyway.
    spec = (
        f'RuleSpec(\n'
        f'        name="{manifest["rule_name"]}",\n'
        f'        script="{manifest["rule_script"]}",\n'
        f'        include=re.compile(r"{manifest["include_regex"]}"),\n'
        f'{exclude_line}'
        f'    ),\n'
    )
    if RUN_PY_MARKER not in text:
        raise SystemExit("error: run.py marker missing — seed corrupted")
    text = text.replace(RUN_PY_MARKER, spec + "    " + RUN_PY_MARKER)
    run_py.write_text(text, encoding="utf-8")


def _wire_precommit(repo: Path, manifest: dict) -> None:
    cfg = repo / ".pre-commit-config.yaml"
    text = cfg.read_text(encoding="utf-8")
    if f"id: {manifest['rule_name']}" in text:
        return
    # The marker in the seed sits at a 6-space indent (`      <marker>`). A
    # bare-substring replace keeps those 6 spaces in front of whatever we
    # inject, so the hook's FIRST line carries no indent of its own (it
    # inherits the file's 6); continuation lines carry the full 8-space YAML
    # indent. The re-inserted marker gets its 6 spaces back explicitly.
    hook = (
        f"- id: {manifest['rule_name']}\n"
        f'        name: "{manifest["rule_name"]} (no bare int(request...) — use safe_int)"\n'
        f"        entry: python scripts/lint/run.py --rule {manifest['rule_name']}\n"
        f"        language: python\n"
        f"        types: [python]\n"
        f"        files: '^app/.*\\.py$'\n"
    )
    if PRECOMMIT_MARKER not in text:
        raise SystemExit("error: pre-commit marker missing — seed corrupted")
    text = text.replace(PRECOMMIT_MARKER, hook + "      " + PRECOMMIT_MARKER)
    cfg.write_text(text, encoding="utf-8")


def _wire_ci(repo: Path, manifest: dict) -> None:
    """The seed's CI already runs `--rule all`, which covers every registered
    RuleSpec. We add an explicit, rule-named diff-scoped step too so the wiring
    check has a concrete per-rule reference to grep — matching how a real
    proposal documents the CI surface for the new rule."""
    ci = repo / ".github/workflows/ci.yml"
    text = ci.read_text(encoding="utf-8")
    if manifest["rule_name"] in text:
        return
    step = (
        f"      - name: {manifest['rule_name']} guard (diff-scoped)\n"
        f"        run: |\n"
        f'          BASE="origin/${{{{ github.base_ref || \'main\' }}}}"\n'
        f"          python scripts/lint/run.py --changed-from \"$BASE\" --rule {manifest['rule_name']}\n"
    )
    text = text.rstrip("\n") + "\n" + step
    ci.write_text(text, encoding="utf-8")


def _wire_claude_md(repo: Path, manifest: dict) -> None:
    if not manifest.get("wire_claude_md", True):
        return
    claude = repo / "CLAUDE.md"
    text = claude.read_text(encoding="utf-8")
    bullet = manifest["claude_bullet"].rstrip("\n")
    if manifest["rule_name"] in text and bullet in text:
        return
    if CLAUDE_MARKER not in text:
        raise SystemExit("error: CLAUDE.md marker missing — seed corrupted")
    text = text.replace(CLAUDE_MARKER, bullet + "\n" + CLAUDE_MARKER)
    claude.write_text(text, encoding="utf-8")


def install(proposal_dir: Path, repo: Path) -> dict:
    manifest = _load_manifest(proposal_dir)
    _copy_artifacts(proposal_dir, repo, manifest)
    _wire_run_py(repo, manifest)
    _wire_precommit(repo, manifest)
    _wire_ci(repo, manifest)
    _wire_claude_md(repo, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", required=True, type=Path, help="Proposal directory")
    parser.add_argument("--repo", required=True, type=Path, help="Seeded mini-host repo")
    args = parser.parse_args()
    if not args.proposal.is_dir():
        raise SystemExit(f"error: proposal dir not found: {args.proposal}")
    if not args.repo.is_dir():
        raise SystemExit(f"error: repo dir not found: {args.repo}")
    manifest = install(args.proposal, args.repo)
    print(f"installed {manifest['rule_name']} into {args.repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
