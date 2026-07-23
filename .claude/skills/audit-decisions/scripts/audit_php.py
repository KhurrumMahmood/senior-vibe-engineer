#!/usr/bin/env python3
"""Write audit-decisions artifacts from bounded PHP comment syntax facts."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any


REFERENCE = re.compile(r"\bdecision:(\d{4})\b")
ARTIFACTS = ("drift.md", "raw-drift.json", "registry-audit.json", "link-check.txt")


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _provider_path() -> Path:
    return Path(__file__).resolve().parents[2] / "_php-syntax/php_syntax_facts.php"


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    provider = _provider_path()
    if not provider.is_file():
        return {
            "status": "partial", "failure_kind": "php_syntax_provider_missing",
            "analyzer": "php-token-syntax-facts-v1", "files": [], "inventory": [],
            "source_manifest": {"preserved": True},
        }, 2
    runner = args.php_runner or shutil.which("php") or "php"
    command = [
        runner, str(provider), "--project-root", str(args.project_root), "--target", str(args.target),
        "--php", args.php, "--composer", args.composer,
        "--minimum-php", args.minimum_php, "--minimum-composer", args.minimum_composer,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        facts = json.loads(result.stdout)
    except (OSError, json.JSONDecodeError) as error:
        return {
            "status": "failed", "failure_kind": "php_syntax_provider_execution_failed",
            "analyzer": "php-token-syntax-facts-v1", "files": [], "inventory": [],
            "provider_error": str(error), "source_manifest": {"preserved": True},
        }, 1
    return facts, result.returncode


def _terminal(output: Path, facts: dict[str, Any]) -> None:
    raw = {
        "status": facts["status"], "failure_kind": facts["failure_kind"],
        "analysis": {"php": facts}, "references": [], "drift": [],
    }
    _atomic(output / "raw-drift.json", json.dumps(raw, indent=2, sort_keys=True) + "\n")
    _atomic(output / "registry-audit.json", json.dumps({"status": "not-run", "drift": []}, indent=2) + "\n")
    _atomic(output / "link-check.txt", f"NOT RUN — {facts['failure_kind']}\n")
    _atomic(
        output / "drift.md",
        "# Decision-registry drift\n\n"
        f"Status: `{facts['status']}`\n\nFailure: `{facts['failure_kind']}`\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--php", default="php")
    parser.add_argument("--composer", default="composer")
    parser.add_argument("--php-runner")
    parser.add_argument("--minimum-php", default="8.1.0")
    parser.add_argument("--minimum-composer", default="2.2.0")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    facts, code = _facts(args)
    if facts["status"] != "complete":
        _terminal(output, facts)
        return code or 2

    root = args.project_root.resolve()
    audit = _module(Path(__file__).with_name("audit.py"), "audit_decisions_base")
    decisions = audit.load_decisions(root / "ai-docs/decisions")
    known = {decision.id for decision in decisions}
    references: list[dict[str, Any]] = []
    for file in facts["files"]:
        for comment in file["comments"]:
            for match in REFERENCE.finditer(comment["text"]):
                references.append({
                    "path": file["file"], "line": comment["line"], "language": "php",
                    "comment_form": comment["form"], "id": match.group(1),
                    "resolved": match.group(1) in known,
                })
    references.sort(key=lambda row: (row["path"], row["line"], row["id"]))
    full_scope = Path(args.target).as_posix() in {".", ""}
    rows = audit.make_drift(decisions, root, references, full_reference_scope=full_scope)
    registry = audit.registry_audit(decisions)
    link_drift, link_advisory = audit.link_check(decisions, root)
    output.mkdir(parents=True, exist_ok=True)
    raw = {
        "status": "complete", "failure_kind": "none", "scan_id": output.name,
        "analysis": {"php": facts}, "references": references,
        "registry_audit": {"drift": registry},
        "link_check": {"drift": link_drift, "advisory": link_advisory}, "drift": rows,
    }
    _atomic(output / "raw-drift.json", json.dumps(raw, indent=2, sort_keys=True) + "\n")
    _atomic(
        output / "registry-audit.json",
        json.dumps({"count": len(decisions), "drift": registry}, indent=2, sort_keys=True) + "\n",
    )
    links = [*link_advisory, *link_drift] or [f"OK — {len(decisions)} decisions, all links resolve"]
    _atomic(output / "link-check.txt", "\n".join(links) + "\n")
    rendered = audit.render_drift(output.name, decisions, references, rows)
    _atomic(
        output / "drift.md",
        rendered + "\nPHP syntax status: `complete` via `php-token-syntax-facts-v1`; "
        "comments are lexical evidence, not behavior or framework truth.\n",
    )
    print(output / "drift.md")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
