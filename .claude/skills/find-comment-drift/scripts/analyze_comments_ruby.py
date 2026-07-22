#!/usr/bin/env python3
"""Produce bounded Ruby comment-drift artifacts with Prism comment locations.

The analyzer makes lexical and narrowly local syntax claims only.  Prism proves
which byte ranges are comments, while ``ruby -c`` gates completeness for every
eligible input.  The behavior-drift rule recognizes one intentionally small
case: a comment says an adjacent method calculates a percentage from an amount,
but the complete method body returns only a fixed numeric literal.  It does not
resolve calls, constants, dynamic loading, reopening, reflection, or runtime
metaprogramming.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_RUBY = (3, 3, 0)
MINIMUM_RUBY_TEXT = "3.3.0"
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen"})
BUILD_DIRS = frozenset({"build", "dist", "tmp", "target", "out", ".bundle"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
RUBY_SHEBANG_RE = re.compile(rb"^#![^\n]*\bruby(?:\s|$)")
MAGIC_COMMENT_RE = re.compile(
    r"^#\s*(?:-\*-.*(?:coding|encoding).*?-\*-|(?:coding|encoding)\s*[:=]|"
    r"frozen_string_literal\s*:|warn_indent\s*:|shareable_constant_value\s*:|typed\s*:)",
    re.I,
)
STALE_TERM_RE = re.compile(r"\b(?:SiteConfig|Site Configuration|site configuration|site config)\b")
DOC_REF_RE = re.compile(
    r"\b(?:L\d{2,}|line\s+\d{2,}|[A-Za-z0-9_./-]+\.rb:\d{1,5})\b", re.I
)
SECTION_BANNER_RE = re.compile(r"^section\s+\d+.*$", re.I)
UPPER_BANNER_RE = re.compile(r"^[A-Z][A-Z0-9 _/:-]{5,}$")
PERCENT_CLAIM_RE = re.compile(
    r"\b(?:calculates?|computes?|derives?)\b.*\b(?:percentage|percent(?:age)?\s+fee|rate)\b"
    r".*\b(?:from|of|based\s+on)\b.*\b(?:amount|subtotal|total)\b",
    re.I,
)
DEF_RE = re.compile(
    r"^(?P<indent>[ \t]*)def\s+(?P<name>(?:self\.)?[A-Za-z_]\w*[!?=]?)"
    r"(?:\s*\((?P<paren>[^\n)]*)\)|\s+(?P<bare>[^\n]+))?\s*$"
)
FIXED_RETURN_RE = re.compile(r"^(?:return\s+)?(?P<literal>-?\d+(?:\.\d+)?)\s*$")
RUBY_PROVIDER = r'''path = ARGV.fetch(0)
source = File.binread(path)
result = Prism.parse(source)
payload = {
  success: result.success?,
  prism_version: Prism::VERSION,
  errors: result.errors.map { |error| error.message },
  comments: result.comments.map do |comment|
    location = comment.location
    {
      start_offset: location.start_offset,
      end_offset: location.end_offset,
      start_line: location.start_line,
      start_column: location.start_column,
      end_line: location.end_line,
      end_column: location.end_column,
      kind: comment.class.name,
    }
  end,
}
STDOUT.write(JSON.generate(payload))
'''


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=20
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _is_ruby_input(path: Path) -> bool:
    if path.suffix.casefold() == ".rb":
        return True
    try:
        mode = path.stat(follow_symlinks=False).st_mode
        if not mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            return False
        with path.open("rb") as handle:
            return RUBY_SHEBANG_RE.search(handle.readline(512)) is not None
    except OSError:
        return False


def _exclusion(path: Path, root: Path, text: str) -> str | None:
    relative = path.relative_to(root)
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if "vendor" in parts:
        return "vendor"
    if parts & TEST_DIRS or name.endswith("_test.rb") or name.startswith("test_"):
        return "test"
    if parts & GENERATED_DIRS:
        return "generated-tree"
    if parts & BUILD_DIRS:
        return "build-tree"
    if GENERATED_RE.search(text[:4096]):
        return "generated-marker"
    return None


def _discover(targets: Iterable[str], root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    paths: dict[str, Path] = {}
    errors: list[str] = []
    for raw in targets:
        logical = Path(raw)
        logical = logical if logical.is_absolute() else root / logical
        logical = Path(os.path.abspath(logical))
        try:
            logical.relative_to(root)
        except ValueError:
            errors.append(f"target-outside-project:{raw}")
            continue
        if not logical.exists() and not logical.is_symlink():
            errors.append(f"target-missing:{raw}")
            continue
        if logical.is_symlink() or logical.is_file():
            if logical.suffix.casefold() == ".rb" or _is_ruby_input(logical):
                paths[_relative(logical, root)] = logical
            continue
        for directory, dirnames, filenames in os.walk(logical, followlinks=False):
            current = Path(directory)
            symlink_dirs = [name for name in dirnames if (current / name).is_symlink()]
            dirnames[:] = sorted(name for name in dirnames if name not in symlink_dirs)
            for name in sorted(filenames):
                path = current / name
                if path.suffix.casefold() == ".rb" or _is_ruby_input(path):
                    paths[_relative(path, root)] = path
    inventory: list[dict[str, Any]] = []
    for relative, path in sorted(paths.items()):
        if path.is_symlink():
            inventory.append(
                {"file": relative, "path": path, "role": "excluded", "reason": "symlink"}
            )
            continue
        try:
            content = path.read_bytes()
            text = content.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            inventory.append(
                {
                    "file": relative,
                    "path": path,
                    "role": "failed",
                    "reason": "read-error",
                    "detail": str(exc),
                }
            )
            continue
        reason = _exclusion(path, root, text)
        inventory.append(
            {
                "file": relative,
                "path": path,
                "role": "excluded" if reason else "candidate",
                **({"reason": reason} if reason else {}),
                "input_kind": "ruby-source" if path.suffix.casefold() == ".rb" else "ruby-executable",
                "source_sha256": _hash_bytes(content),
                "source_bytes": len(content),
            }
        )
    return inventory, errors


def _probe(ruby: Path, root: Path) -> tuple[dict[str, Any], int]:
    if not ruby.is_file() or not os.access(ruby, os.X_OK):
        return {
            "status": "unsupported",
            "failure_kind": "ruby-tool-missing",
            "minimum_ruby_version": MINIMUM_RUBY_TEXT,
        }, 2
    result = _run([str(ruby), "--version"], root)
    if result.returncode != 0:
        return {
            "status": "failed",
            "failure_kind": "ruby-version-failed",
            "minimum_ruby_version": MINIMUM_RUBY_TEXT,
            "detail": (result.stderr or result.stdout).strip(),
        }, 1
    match = re.search(r"\bruby\s+(\d+)\.(\d+)\.(\d+)", result.stdout)
    if not match:
        return {
            "status": "failed",
            "failure_kind": "ruby-version-unrecognized",
            "minimum_ruby_version": MINIMUM_RUBY_TEXT,
            "detail": result.stdout.strip(),
        }, 1
    version = tuple(map(int, match.groups()))
    evidence = {
        "ruby_path": str(ruby),
        "ruby_version": ".".join(match.groups()),
        "minimum_ruby_version": MINIMUM_RUBY_TEXT,
    }
    if version < MINIMUM_RUBY:
        return {
            **evidence,
            "status": "unsupported",
            "failure_kind": "ruby-version-too-old",
        }, 2
    return {**evidence, "status": "complete"}, 0


def _span(location: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_byte": location["start_offset"],
        "end_byte": location["end_offset"],
        "start": {
            "line": location["start_line"],
            "column": location["start_column"] + 1,
        },
        "end": {
            "line": location["end_line"],
            "column": location["end_column"] + 1,
        },
    }


def _comment_text(spelling: str) -> str:
    if spelling.startswith("#"):
        return spelling[1:].strip()
    return spelling.strip()


def _line_offsets(source: bytes) -> list[int]:
    offsets = [0]
    for match in re.finditer(b"\n", source):
        offsets.append(match.end())
    return offsets


def _adjacent_fixed_method(
    text: str, source: bytes, comment_end_line: int
) -> dict[str, Any] | None:
    lines = text.splitlines()
    index = comment_end_line
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return None
    definition = DEF_RE.match(lines[index])
    if definition is None:
        return None
    indent = definition.group("indent")
    end_index = index + 1
    while end_index < len(lines) and lines[end_index] != f"{indent}end":
        end_index += 1
    if end_index >= len(lines):
        return None
    body_lines = [line.strip() for line in lines[index + 1 : end_index] if line.strip()]
    if len(body_lines) != 1:
        return None
    fixed = FIXED_RETURN_RE.match(body_lines[0])
    if fixed is None:
        return None
    raw_parameters = definition.group("paren") or definition.group("bare") or ""
    parameters = [
        token.strip().split("=", 1)[0].strip().lstrip("*&#")
        for token in raw_parameters.split(",")
        if token.strip()
    ]
    offsets = _line_offsets(source)
    start = offsets[index]
    end = offsets[end_index] + len(lines[end_index].encode("utf-8"))
    return {
        "method_name": definition.group("name"),
        "parameters": parameters,
        "returned_literal": fixed.group("literal"),
        "span": {
            "start_byte": start,
            "end_byte": end,
            "start": {"line": index + 1, "column": len(indent) + 1},
            "end": {"line": end_index + 1, "column": len(lines[end_index]) + 1},
        },
        "spelling_sha256": _hash_bytes(source[start:end]),
    }


def _findings(
    path: Path, root: Path, provider: dict[str, Any]
) -> list[dict[str, Any]]:
    source = path.read_bytes()
    text = source.decode("utf-8")
    results: list[dict[str, Any]] = []
    for location in provider["comments"]:
        start = location["start_offset"]
        end = location["end_offset"]
        spelling = source[start:end].decode("utf-8")
        if MAGIC_COMMENT_RE.match(spelling) or spelling.startswith("#!"):
            continue
        comment = _comment_text(spelling)
        comment_span = _span(location)
        pattern: str | None = None
        recommendation: str | None = None
        evidence: dict[str, Any] = {
            "comment_span": comment_span,
            "comment_spelling_sha256": _hash_bytes(source[start:end]),
        }
        if PERCENT_CLAIM_RE.search(comment):
            method = _adjacent_fixed_method(text, source, location["end_line"])
            if method is not None:
                pattern = "behavior_drift_comment"
                recommendation = (
                    "Reconcile the percentage-from-amount claim with the adjacent fixed-literal method."
                )
                evidence.update(
                    claim_kind="parameter-derived-percentage",
                    code_fact="fixed-numeric-literal-return",
                    method=method,
                )
        if pattern is None and STALE_TERM_RE.search(comment):
            pattern = "stale_comment_term"
            recommendation = "Update the comment to current terminology."
        if pattern is None and DOC_REF_RE.search(comment):
            pattern = "malformed_doc_reference"
            recommendation = "Replace line-number references with a durable symbol or path."
        stripped = comment.strip().strip("#*-= ")
        if pattern is None and stripped and (
            SECTION_BANNER_RE.fullmatch(stripped) or UPPER_BANNER_RE.fullmatch(stripped)
        ):
            pattern = "detached_section_banner"
            recommendation = "Delete the banner or attach durable rationale to adjacent code."
        if pattern is None:
            continue
        results.append(
            {
                "pattern": pattern,
                "file": _relative(path, root),
                "lineno": location["start_line"],
                "summary": comment[:180],
                "recommendation": recommendation,
                "language": "ruby",
                "source_sha256": _hash_bytes(source),
                "source_span": comment_span,
                "evidence": evidence,
            }
        )
    return results


def _manifest(inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    rows = [
        {"file": row["file"], "source_sha256": row["source_sha256"], "source_bytes": row["source_bytes"]}
        for row in inventory
        if "source_sha256" in row
    ]
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["file"].encode("utf-8") + b"\0")
        digest.update(row["source_sha256"].encode("ascii") + b"\n")
    return rows, digest.hexdigest()


def _publish(output: Path, analysis: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    jsonl = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    detections_sha256 = _hash_bytes(jsonl.encode("utf-8"))
    analysis["detections_sha256"] = detections_sha256
    payload = {
        "schema_version": 1,
        "status": analysis["status"],
        "outcome": analysis["outcome"],
        "total_findings": len(findings),
        "source_manifest_sha256": analysis["source_manifest_sha256"],
        "detections_sha256": detections_sha256,
        "analysis": {"ruby": analysis},
        "findings": findings,
    }
    counts: dict[str, int] = {}
    for row in findings:
        counts[row["pattern"]] = counts.get(row["pattern"], 0) + 1
    markdown = (
        "# Ruby comment-drift audit\n\n"
        f"**Status:** `{analysis['status']}`  \n"
        f"**Outcome:** `{analysis['outcome']}`  \n"
        f"**Findings:** {len(findings)}  \n"
        f"**Source manifest:** `{analysis['source_manifest_sha256']}`\n\n"
        "Prism-backed comments and bounded adjacent syntax only; see `findings.json` "
        "for exact spans, hashes, inventory, and dynamic-Ruby limits.\n"
    )
    if counts:
        markdown += "\n" + "\n".join(
            f"- `{key}`: {value}" for key, value in sorted(counts.items())
        ) + "\n"
    _atomic_text(output, jsonl)
    _json(output.with_name("scan.json"), analysis)
    _json(output.with_name("findings.json"), payload)
    _atomic_text(output.with_name("report.md"), markdown)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Ruby comments with Prism.")
    parser.add_argument("targets", nargs="*", default=["."])
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--ruby", type=Path, default=Path("ruby"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output.resolve()
    if output.suffix.casefold() != ".jsonl":
        parser.error("--output must be a .jsonl artifact path")
    try:
        output.relative_to(root)
    except ValueError:
        parser.error("--output must be inside --project-root")
    artifacts = (
        output,
        output.with_name("scan.json"),
        output.with_name("findings.json"),
        output.with_name("report.md"),
    )
    for artifact in artifacts:
        artifact.unlink(missing_ok=True)

    inventory, target_errors = _discover(args.targets or ["."], root)
    manifest, manifest_digest = _manifest(inventory)
    ruby = args.ruby
    if not ruby.is_absolute():
        resolved = shutil_which(str(ruby))
        ruby = Path(resolved) if resolved else root / str(ruby)
    tool, tool_rc = _probe(ruby, root)
    base: dict[str, Any] = {
        **tool,
        "language": "ruby",
        "analyzer": "ruby-prism-comments",
        "lexical_only": True,
        "limits": [
            "bounded adjacent fixed-literal behavior rule only",
            "no call, constant, type, or runtime identity resolution",
            "no dynamic require/load/autoload resolution",
            "no send/public_send, const_get, method_missing, eval, define_method, or reflection resolution",
            "no class/module reopening, monkey-patch, refinement, callback, DSL, Rails, or Zeitwerk semantics",
        ],
        "inventory": [{key: value for key, value in row.items() if key != "path"} for row in inventory],
        "errors": list(target_errors),
        "source_manifest": manifest,
        "source_manifest_sha256": manifest_digest,
        "source_preserved": True,
    }
    if tool_rc:
        base["outcome"] = base["status"]
        base["summary"] = {
            "discovered": len(inventory),
            "eligible": 0,
            "excluded": sum(row["role"] == "excluded" for row in inventory),
            "failed": len(target_errors),
        }
        _publish(output, base, [])
        return tool_rc

    eligible = [row for row in inventory if row["role"] == "candidate"]
    findings: list[dict[str, Any]] = []
    provider_failures = 0
    prism_versions: set[str] = set()
    for row in eligible:
        path = row["path"]
        syntax = _run([str(ruby), "--disable-gems", "-c", str(path)], root)
        if syntax.returncode != 0:
            detail = (syntax.stderr or syntax.stdout).strip()
            if "syntax error" in detail.casefold():
                row.update(role="failed", reason="syntax-error", detail=detail)
            else:
                provider_failures += 1
                row.update(role="failed", reason="ruby-syntax-check-failed", detail=detail)
            base["errors"].append(f"{row['file']}:{row['reason']}")
            continue
        provided = _run(
            [str(ruby), "--disable-gems", "-rjson", "-rprism", "-e", RUBY_PROVIDER, str(path)],
            root,
        )
        if provided.returncode != 0:
            provider_failures += 1
            row.update(
                role="failed",
                reason="ruby-provider-failed",
                detail=(provided.stderr or provided.stdout).strip(),
            )
            base["errors"].append(f"{row['file']}:ruby-provider-failed")
            continue
        try:
            payload = json.loads(provided.stdout)
            if (
                not isinstance(payload, dict)
                or payload.get("success") is not True
                or not isinstance(payload.get("comments"), list)
                or not isinstance(payload.get("prism_version"), str)
            ):
                raise ValueError("provider payload lacks successful Prism evidence")
        except (json.JSONDecodeError, ValueError) as exc:
            provider_failures += 1
            row.update(role="failed", reason="ruby-provider-invalid", detail=str(exc))
            base["errors"].append(f"{row['file']}:ruby-provider-invalid")
            continue
        prism_versions.add(payload["prism_version"])
        row["role"] = "eligible"
        row["comment_count"] = len(payload["comments"])
        findings.extend(_findings(path, root, payload))

    for row in inventory:
        path = row["path"]
        if row.get("source_sha256") and path.is_file() and _hash_file(path) != row["source_sha256"]:
            base["source_preserved"] = False
            base["errors"].append(f"{row['file']}:source-mutated")
    failed = sum(row["role"] == "failed" for row in inventory) + len(target_errors)
    excluded = sum(row["role"] == "excluded" for row in inventory)
    completed = sum(row["role"] == "eligible" for row in inventory)
    if not base["source_preserved"]:
        status, outcome, rc = "failed", "failed", 1
        base["failure_kind"] = "unexpected-source-mutation"
    elif provider_failures and completed == 0:
        status, outcome, rc = "failed", "failed", 1
        base["failure_kind"] = "ruby-provider-failed"
    elif failed:
        status, outcome, rc = "partial", "incomplete", 0
    elif not eligible:
        status, outcome, rc = "unsupported", "unsupported", 2
        base["failure_kind"] = "no-eligible-ruby-files"
    else:
        status, rc = "complete", 0
        outcome = "advisory-findings" if findings else "clean-within-complete"
    base.update(
        status=status,
        outcome=outcome,
        prism_versions=sorted(prism_versions),
        inventory=[{key: value for key, value in row.items() if key != "path"} for row in inventory],
        summary={
            "discovered": len(inventory),
            "eligible": completed,
            "excluded": excluded,
            "failed": failed,
        },
    )
    findings.sort(key=lambda row: (row["file"], row["lineno"], row["pattern"]))
    _publish(output, base, findings)
    return rc


def shutil_which(command: str) -> str | None:
    """Resolve a bare tool name without importing repository helpers."""
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory or ".") / command
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
    return None


if __name__ == "__main__":
    raise SystemExit(main())
