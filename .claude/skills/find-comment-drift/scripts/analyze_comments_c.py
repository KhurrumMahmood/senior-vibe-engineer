#!/usr/bin/env python3
"""Produce bounded C comment-drift artifacts from Clang raw tokens.

This analyzer makes lexical claims only. Raw tokens identify comment spelling;
source bytes provide exact half-open spans. It does not interpret macro expansion,
inactive branches, or comment-to-symbol meaning. C++, Objective-C, Objective-C++,
CUDA, OpenCL, assembly, and framework conventions are outside this contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_CLANG = (21, 0, 0)
MINIMUM_CLANG_TEXT = "21.0.0"
SOURCE_SUFFIXES = frozenset({".c", ".i"})
HEADER_SUFFIXES = frozenset({".h", ".inc"})
ALL_SUFFIXES = SOURCE_SUFFIXES | HEADER_SUFFIXES
TEST_DIRS = frozenset({"test", "tests", "__tests__", "testdata", "fixtures"})
GENERATED_DIRS = frozenset({"generated", "gen"})
BUILD_DIRS = frozenset({"build", "dist", "target", "out", ".native-build"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
STALE_TERM_RE = re.compile(r"\b(?:SiteConfig|Site Configuration|site configuration|site config)\b")
DOC_REF_RE = re.compile(
    r"\b(?:L\d{2,}|line\s+\d{2,}|[A-Za-z0-9_./-]+\.(?:c|i|h|inc):\d{1,5})\b",
    re.I,
)
NARRATION_RE = re.compile(
    r"^(?:get|create|update|delete|remove|save|return|format|parse|load|build|"
    r"render|initialize|validate|check|set|clear|find|filter|sort|count|"
    r"calculate|fetch|call|loop|append|add|show|store|reset|replace|compute)\b",
    re.I,
)
WHY_RE = re.compile(
    r"\b(?:why|because|compat|legacy|intentional|avoid|must|cannot|workaround|"
    r"race|safety|security|contract|temporary|until|fallback|preserve|exclude|"
    r"since|if|when|while|after|before|for|via|with|without|only|needed)\b",
    re.I,
)
RAW_COMMENT_RE = re.compile(
    r"^comment\s+'.*?'\s*(?:\[[^\]]+\]\s*)?Loc=<.*?:(\d+):(\d+)>$",
    re.M | re.S,
)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exclusion(path: Path, root: Path, text: str) -> str | None:
    relative = path.relative_to(root)
    parents = {part.casefold() for part in relative.parts[:-1]}
    if "vendor" in parents:
        return "vendor"
    if parents & TEST_DIRS:
        return "test-tree"
    if parents & GENERATED_DIRS:
        return "generated-tree"
    if parents & BUILD_DIRS:
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
        if not logical.exists():
            errors.append(f"target-missing:{raw}")
            continue
        if logical.is_symlink():
            if logical.suffix.casefold() in ALL_SUFFIXES:
                paths[_relative(logical, root)] = logical
            continue
        if logical.is_file():
            if logical.suffix.casefold() in ALL_SUFFIXES:
                paths[_relative(logical, root)] = logical
            continue
        for directory, dirnames, filenames in os.walk(logical, followlinks=False):
            current = Path(directory)
            dirnames[:] = sorted(dirnames)
            for name in sorted(filenames):
                path = current / name
                if path.suffix.casefold() in ALL_SUFFIXES:
                    paths[_relative(path, root)] = path
    inventory: list[dict[str, Any]] = []
    for relative, path in sorted(paths.items()):
        if path.is_symlink():
            inventory.append({"file": relative, "path": path, "role": "excluded", "reason": "symlink"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
            digest = _hash(path)
        except (OSError, UnicodeError) as exc:
            inventory.append(
                {"file": relative, "path": path, "role": "failed", "reason": "read-error", "detail": str(exc)}
            )
            continue
        reason = _exclusion(path, root, text)
        inventory.append(
            {
                "file": relative,
                "path": path,
                "role": "excluded" if reason else "candidate",
                **({"reason": reason} if reason else {}),
                "source_sha256": digest,
                "source_bytes": len(text.encode("utf-8")),
            }
        )
    return inventory, errors


def _all_first_party_sources(root: Path) -> set[Path]:
    sources: set[Path] = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink() or path.suffix.casefold() not in SOURCE_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if _exclusion(path, root, text) is None:
            sources.add(path.resolve())
    return sources


def _flags(arguments: list[str], source: Path) -> list[str]:
    result: list[str] = []
    skip = False
    for token in arguments[1:]:
        if skip:
            skip = False
            continue
        if token == "-o":
            skip = True
            continue
        if token in {"-c", str(source)}:
            continue
        result.append(token)
    return result


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=20
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _compile_database(root: Path, clang: Path) -> tuple[dict[str, Any], dict[Path, list[str]], set[Path]]:
    path = root / "compile_commands.json"
    empty: dict[Path, list[str]] = {}
    if not path.is_file():
        return {"status": "missing", "path": "compile_commands.json"}, empty, set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"status": "malformed", "detail": str(exc)}, empty, set()
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        return {"status": "malformed", "detail": "expected a non-empty JSON array of objects"}, empty, set()
    commands: dict[Path, list[str]] = {}
    directories: dict[Path, Path] = {}
    for row in payload:
        if set(row) != {"directory", "file", "arguments"} or not isinstance(row["arguments"], list):
            return {"status": "malformed", "detail": "entries require exact directory/file/arguments keys"}, empty, set()
        if any(not isinstance(token, str) for token in row["arguments"]):
            return {"status": "malformed", "detail": "arguments must contain only strings"}, empty, set()
        directory = Path(row["directory"])
        source = Path(row["file"])
        arguments = row["arguments"]
        if not directory.is_absolute() or directory.resolve() != root or not source.is_absolute():
            return {"status": "malformed", "detail": "entries must use the copied project root"}, empty, set()
        if source.suffix.casefold() != ".c" or "-std=c17" not in arguments or "-c" not in arguments:
            return {"status": "malformed", "detail": "entries must be C17 compile commands"}, empty, set()
        commands[source.resolve()] = list(arguments)
        directories[source.resolve()] = directory
    expected = _all_first_party_sources(root)
    if set(commands) != expected:
        return {
            "status": "incomplete",
            "expected_translation_units": sorted(_relative(item, root) for item in expected),
            "actual_translation_units": sorted(_relative(item, root) for item in commands),
        }, empty, set()
    dependencies: set[Path] = set(commands)
    for source, arguments in commands.items():
        result = _run([str(clang), *_flags(arguments, source), "-MM", str(source)], directories[source])
        if result.returncode != 0:
            return {"status": "incomplete", "detail": f"dependency scan failed for {_relative(source, root)}"}, empty, set()
        words = result.stdout.replace("\\\n", " ").partition(":")[2].split()
        for word in words:
            dependency = Path(word)
            dependency = dependency if dependency.is_absolute() else directories[source] / dependency
            try:
                dependency = dependency.resolve()
                dependency.relative_to(root)
            except (OSError, ValueError):
                continue
            dependencies.add(dependency)
    freshness_inputs = dependencies | {root / "Makefile"}
    existing = [item for item in freshness_inputs if item.is_file()]
    if existing and path.stat().st_mtime_ns < max(item.stat().st_mtime_ns for item in existing):
        return {"status": "stale", "detail": "compile database predates a compile-owned input"}, empty, set()
    return {
        "status": "valid",
        "path": "compile_commands.json",
        "translation_units": sorted(_relative(item, root) for item in commands),
        "owned_dependencies": sorted(_relative(item, root) for item in dependencies),
    }, commands, dependencies


def _probe(clang: Path) -> tuple[dict[str, Any], int]:
    if not clang.is_file() or not os.access(clang, os.X_OK):
        return {"status": "unsupported", "failure_kind": "clang-tool-missing", "minimum_clang_version": MINIMUM_CLANG_TEXT}, 2
    try:
        result = _run([str(clang), "--version"], Path.cwd())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "failure_kind": "clang-version-failed", "detail": str(exc)}, 1
    if result.returncode != 0:
        return {"status": "failed", "failure_kind": "clang-version-failed", "detail": (result.stderr or result.stdout).strip()}, 1
    match = re.search(r"clang version\s+(\d+)\.(\d+)\.(\d+)", result.stdout)
    if not match:
        return {"status": "failed", "failure_kind": "clang-version-unrecognized", "detail": result.stdout.strip()}, 1
    version = tuple(map(int, match.groups()))
    evidence = {"clang_path": str(clang), "clang_version": ".".join(match.groups()), "minimum_clang_version": MINIMUM_CLANG_TEXT}
    if version < MINIMUM_CLANG:
        return {**evidence, "status": "unsupported", "failure_kind": "clang-version-too-old"}, 2
    return {**evidence, "status": "complete"}, 0


def _command(clang: Path, path: Path, commands: dict[Path, list[str]], mode: str) -> list[str]:
    source = path.resolve()
    arguments = commands.get(source)
    if arguments is None and commands:
        source, arguments = next(iter(commands.items()))
    flags = _flags(arguments, source) if arguments else ["-std=c17", "-Wall", "-Wextra", "-Werror", "-pedantic"]
    language = "c-cpp-output" if path.suffix.casefold() == ".i" else "c-header" if path.suffix.casefold() in HEADER_SUFFIXES else "c"
    extra = ["-fsyntax-only"] if mode == "syntax" else ["-fsyntax-only", "-Xclang", "-dump-raw-tokens"]
    return [str(clang), *flags, "-x", language, *extra, str(path)]


def _span(source: bytes, line: int, column: int) -> tuple[int, int, dict[str, Any]] | None:
    lines = source.splitlines(keepends=True)
    if line < 1 or line > len(lines):
        return None
    start = sum(len(item) for item in lines[: line - 1]) + column - 1
    if source[start : start + 2] == b"//":
        newline = source.find(b"\n", start)
        end = len(source) if newline < 0 else newline
    elif source[start : start + 2] == b"/*":
        close = source.find(b"*/", start + 2)
        if close < 0:
            return None
        end = close + 2
    else:
        return None
    prefix = source[:end]
    end_line = prefix.count(b"\n") + 1
    last_newline = prefix.rfind(b"\n")
    end_column = end + 1 if last_newline < 0 else end - last_newline
    return start, end, {
        "start_byte": start,
        "end_byte": end,
        "start": {"line": line, "column": column},
        "end": {"line": end_line, "column": end_column},
    }


def _comment_text(spelling: str) -> str:
    if spelling.startswith("//"):
        return spelling[2:].strip()
    return re.sub(r"^\s*\* ?", "", spelling[2:-2], flags=re.M).strip()


def _findings(path: Path, root: Path, raw: str) -> list[dict[str, Any]]:
    source = path.read_bytes()
    results: list[dict[str, Any]] = []
    for match in RAW_COMMENT_RE.finditer(raw):
        location = _span(source, int(match.group(1)), int(match.group(2)))
        if location is None:
            continue
        start, end, span = location
        spelling = source[start:end].decode("utf-8")
        text = _comment_text(spelling)
        patterns: list[tuple[str, str]] = []
        if STALE_TERM_RE.search(text):
            patterns.append(("stale_comment_term", "Update the comment to current terminology."))
        if DOC_REF_RE.search(text):
            patterns.append(("malformed_doc_reference", "Replace line-number references with a durable symbol or path."))
        stripped = text.strip().strip("/#*-= ")
        if stripped and (stripped.isupper() or re.fullmatch(r"section\s+\d+.*", stripped, re.I)):
            patterns.append(("detached_section_banner", "Delete the banner or attach durable rationale to the code."))
        elif not WHY_RE.search(text) and NARRATION_RE.match(text):
            patterns.append(("obvious_narration_comment", "Delete narration; retain only rationale, contract, or caveat."))
        for pattern, recommendation in patterns:
            results.append(
                {
                    "pattern": pattern,
                    "file": _relative(path, root),
                    "lineno": span["start"]["line"],
                    "summary": text[:180],
                    "recommendation": recommendation,
                    "language": "c",
                    "source_span": span,
                    "spelling_sha256": hashlib.sha256(source[start:end]).hexdigest(),
                }
            )
    return results


def _publish(output: Path, analysis: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    payload = {
        "schema_version": 1,
        "status": analysis["status"],
        "outcome": analysis["outcome"],
        "total_findings": len(findings),
        "analysis": {"c": analysis},
        "findings": findings,
    }
    _atomic_text(output, "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings))
    _json(output.with_name("scan.json"), analysis)
    _json(output.with_name("findings.json"), payload)
    counts: dict[str, int] = {}
    for row in findings:
        counts[row["pattern"]] = counts.get(row["pattern"], 0) + 1
    markdown = (
        "# C comment-drift audit\n\n"
        f"**Status:** `{analysis['status']}`  \n"
        f"**Outcome:** `{analysis['outcome']}`  \n"
        f"**Findings:** {len(findings)}\n\n"
        "Lexical evidence only; see `findings.json` for inventory, exact spans, and limits.\n"
    )
    if counts:
        markdown += "\n" + "\n".join(
            f"- `{key}`: {value}" for key, value in sorted(counts.items())
        ) + "\n"
    _atomic_text(output.with_name("report.md"), markdown)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze C comments with Clang raw tokens.")
    parser.add_argument("targets", nargs="*", default=["."])
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--clang", type=Path, default=Path("/usr/bin/clang"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output.resolve()
    if output.suffix.casefold() != ".jsonl":
        parser.error("--output must be a .jsonl artifact path")
    for artifact in (output, output.with_name("scan.json"), output.with_name("findings.json"), output.with_name("report.md")):
        artifact.unlink(missing_ok=True)
    inventory, target_errors = _discover(args.targets or ["."], root)
    tool, rc = _probe(args.clang.resolve())
    base = {
        **tool,
        "language": "c",
        "analyzer": "clang-raw-tokens",
        "syntax_standard": "c17",
        "lexical_only": True,
        "limits": [
            "no macro expansion meaning",
            "no inactive branches meaning",
            "no comment-to-symbol semantics",
            "no C++, Objective-C, Objective-C++, CUDA, OpenCL, assembly, or framework support",
        ],
        "inventory": [{key: value for key, value in row.items() if key != "path"} for row in inventory],
        "errors": list(target_errors),
        "compile_database": {"status": "not-evaluated"},
        "source_preserved": True,
    }
    if rc:
        base["outcome"] = base["status"]
        base["summary"] = {"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": len(target_errors)}
        _publish(output, base, [])
        return rc
    database, commands, owned = _compile_database(root, args.clang.resolve())
    base["compile_database"] = database
    eligible: list[dict[str, Any]] = []
    for row in inventory:
        if row["role"] != "candidate":
            continue
        path = row["path"]
        if path.suffix.casefold() in HEADER_SUFFIXES and path.resolve() not in owned:
            row.update(role="excluded", reason="ambiguous-header")
        else:
            row["role"] = "eligible"
            eligible.append(row)
    findings: list[dict[str, Any]] = []
    analyzer_failures = 0
    for row in eligible:
        path = row["path"]
        syntax = _run(_command(args.clang.resolve(), path, commands, "syntax"), root)
        if syntax.returncode != 0:
            if "error:" not in syntax.stderr:
                analyzer_failures += 1
                row.update(role="failed", reason="clang-analysis-failed", detail=(syntax.stderr or syntax.stdout).strip())
            else:
                row.update(role="failed", reason="syntax-error", detail=syntax.stderr.strip())
            base["errors"].append(f"{row['file']}:{row['reason']}")
            continue
        raw = _run(_command(args.clang.resolve(), path, commands, "raw"), root)
        raw_text = raw.stdout + raw.stderr
        if raw.returncode != 0 or not raw_text.strip():
            analyzer_failures += 1
            row.update(role="failed", reason="clang-analysis-failed", detail=(raw.stderr or raw.stdout).strip())
            base["errors"].append(f"{row['file']}:clang-analysis-failed")
            continue
        findings.extend(_findings(path, root, raw_text))
    for row in inventory:
        if row.get("source_sha256") and row["path"].is_file() and _hash(row["path"]) != row["source_sha256"]:
            base["source_preserved"] = False
            base["errors"].append(f"{row['file']}:source-mutated")
    failed = sum(row["role"] == "failed" for row in inventory) + len(target_errors)
    excluded = sum(row["role"] == "excluded" for row in inventory)
    complete_eligible = sum(row["role"] == "eligible" for row in inventory)
    if analyzer_failures and complete_eligible == 0:
        status, outcome, rc = "failed", "failed", 1
        base["failure_kind"] = "clang-analysis-failed"
    elif failed:
        status, outcome, rc = "partial", "incomplete", 0
    elif not eligible:
        status, outcome, rc = "unsupported", "unsupported", 2
        base["failure_kind"] = "no-eligible-c-files"
    else:
        status, rc = "complete", 0
        outcome = "advisory-findings" if findings else "clean-within-complete"
    base.update(
        status=status,
        outcome=outcome,
        inventory=[{key: value for key, value in row.items() if key != "path"} for row in inventory],
        summary={"discovered": len(inventory), "eligible": complete_eligible, "excluded": excluded, "failed": failed},
    )
    findings.sort(key=lambda row: (row["file"], row["lineno"], row["pattern"]))
    _publish(output, base, findings)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
