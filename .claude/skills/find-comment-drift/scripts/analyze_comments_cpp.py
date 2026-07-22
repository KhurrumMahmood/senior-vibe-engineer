#!/usr/bin/env python3
"""Produce bounded C++20 comment-drift artifacts from Clang raw tokens.

This analyzer makes lexical claims only. Raw tokens identify comment spelling;
source bytes provide exact half-open spans. It does not interpret macro expansion,
inactive branches, or comment-to-symbol meaning. C, Objective-C, Objective-C++,
CUDA, modules, assembly, and framework conventions remain outside this contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_CLANG = (21, 0, 0)
MINIMUM_CLANG_TEXT = "21.0.0"
LANGUAGE_CONFIGS = {
    "cpp": {
        "display": "C++",
        "standard": "c++20",
        "standard_flags": frozenset(
            {"-std=c++20", "-std=gnu++20", "-std=c++2a", "-std=gnu++2a"}
        ),
        "source_suffixes": frozenset({".cpp", ".cc", ".cxx", ".c++", ".C", ".ii"}),
        "header_suffixes": frozenset(
            {".h", ".hpp", ".hh", ".hxx", ".h++", ".inc", ".ipp", ".inl", ".tpp"}
        ),
        "preprocessed_suffixes": frozenset({".ii"}),
        "source_language": "c++",
        "header_language": "c++-header",
        "preprocessed_language": "c++-cpp-output",
        "unsupported": "no C, Objective-C, Objective-C++, CUDA, module-interface, assembly, or framework support",
    },
}
ACTIVE_LANGUAGE = "cpp"
ACTIVE_CONFIG = LANGUAGE_CONFIGS[ACTIVE_LANGUAGE]
SOURCE_SUFFIXES = ACTIVE_CONFIG["source_suffixes"]
HEADER_SUFFIXES = ACTIVE_CONFIG["header_suffixes"]
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
RAW_TOKEN_MARKER_RE = re.compile(
    r"(?m)^(?:raw_identifier|identifier|comment|string_literal|char_constant|"
    r"numeric_constant|hash|unknown|l_paren|r_paren|l_brace|r_brace|semi)\s+'"
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


def _suffix(path: Path) -> str:
    """Keep C++ suffixes case-sensitive, including the conventional `.C`."""
    return path.suffix


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
            if _suffix(logical) in ALL_SUFFIXES:
                paths[_relative(logical, root)] = logical
            continue
        if logical.is_file():
            if _suffix(logical) in ALL_SUFFIXES:
                paths[_relative(logical, root)] = logical
            continue
        for directory, dirnames, filenames in os.walk(logical, followlinks=False):
            current = Path(directory)
            dirnames[:] = sorted(dirnames)
            for name in sorted(filenames):
                path = current / name
                if _suffix(path) in ALL_SUFFIXES:
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
        if not path.is_file() or path.is_symlink() or _suffix(path) not in SOURCE_SUFFIXES:
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


def _effective_standard(arguments: list[str]) -> str | None:
    standards = [token for token in arguments if token.startswith("-std=")]
    return standards[-1] if standards else None


def _effective_language_mode(arguments: list[str]) -> str | None:
    modes: list[str] = []
    for index, token in enumerate(arguments):
        if token == "-x" and index + 1 < len(arguments):
            modes.append(arguments[index + 1])
        elif token.startswith("-x") and token != "-x":
            modes.append(token[2:])
    return modes[-1] if modes else None


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
        language_mode = _effective_language_mode(arguments)
        if (
            _suffix(source) not in SOURCE_SUFFIXES
            or _effective_standard(arguments) not in ACTIVE_CONFIG["standard_flags"]
            or language_mode not in {None, "c++", "c++-cpp-output"}
            or "-c" not in arguments
        ):
            return {
                "status": "malformed",
                "detail": f"entries must be {ACTIVE_CONFIG['standard']} compile commands",
            }, empty, set()
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
    default_standard = sorted(ACTIVE_CONFIG["standard_flags"])[0]
    flags = _flags(arguments, source) if arguments else [default_standard, "-Wall", "-Wextra", "-Werror", "-pedantic"]
    suffix = _suffix(path)
    language = (
        ACTIVE_CONFIG["preprocessed_language"]
        if suffix in ACTIVE_CONFIG["preprocessed_suffixes"]
        else ACTIVE_CONFIG["header_language"]
        if suffix in HEADER_SUFFIXES
        else ACTIVE_CONFIG["source_language"]
    )
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


def _source_comment_locations(source: bytes) -> set[tuple[int, int]]:
    """Conservatively enumerate source comments to reject truncated Clang output.

    Findings still require Clang comment tokens. This byte scanner is only an
    output-completeness guard and handles escaped literals plus C++ raw strings.
    """
    found: set[tuple[int, int]] = set()
    index = 0
    line = 1
    column = 1

    def advance(chunk: bytes) -> None:
        nonlocal line, column
        newlines = chunk.count(b"\n")
        if newlines:
            line += newlines
            column = len(chunk.rsplit(b"\n", 1)[1]) + 1
        else:
            column += len(chunk)

    while index < len(source):
        if source.startswith(b"//", index):
            found.add((line, column))
            end = source.find(b"\n", index)
            end = len(source) if end < 0 else end
            advance(source[index:end])
            index = end
            continue
        if source.startswith(b"/*", index):
            found.add((line, column))
            end = source.find(b"*/", index + 2)
            end = len(source) if end < 0 else end + 2
            advance(source[index:end])
            index = end
            continue
        raw_prefix = next(
            (
                prefix
                for prefix in (b'u8R"', b'uR"', b'UR"', b'LR"', b'R"')
                if source.startswith(prefix, index)
            ),
            None,
        )
        if raw_prefix is not None:
            delimiter_start = index + len(raw_prefix)
            delimiter_end = source.find(b"(", delimiter_start, delimiter_start + 17)
            if delimiter_end >= 0:
                delimiter = source[delimiter_start:delimiter_end]
                terminator = b")" + delimiter + b'"'
                raw_end = source.find(terminator, delimiter_end + 1)
                if raw_end >= 0:
                    raw_end += len(terminator)
                    advance(source[index:raw_end])
                    index = raw_end
                    continue
        if source[index : index + 1] in {b'"', b"'"}:
            quote = source[index : index + 1]
            end = index + 1
            while end < len(source):
                if source[end : end + 1] == b"\\":
                    end += 2
                    continue
                end += 1
                if source[end - 1 : end] == quote:
                    break
            advance(source[index:end])
            index = end
            continue
        advance(source[index : index + 1])
        index += 1
    return found


def _raw_output_status(path: Path, raw: str) -> tuple[str, str | None]:
    if not RAW_TOKEN_MARKER_RE.search(raw):
        return "malformed", "Clang output contained no recognizable raw-token records"
    expected = _source_comment_locations(path.read_bytes())
    actual = {
        (int(match.group(1)), int(match.group(2)))
        for match in RAW_COMMENT_RE.finditer(raw)
    }
    if actual != expected:
        return (
            "incomplete",
            f"Clang returned comment locations {sorted(actual)}; expected {sorted(expected)}",
        )
    return "complete", None


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
            finding = {
                "pattern": pattern,
                "file": _relative(path, root),
                "lineno": span["start"]["line"],
                "summary": text[:180],
                "recommendation": recommendation,
                "language": ACTIVE_LANGUAGE,
                "source_span": span,
                "spelling_sha256": hashlib.sha256(source[start:end]).hexdigest(),
            }
            if ACTIVE_LANGUAGE == "cpp":
                finding.update(
                    evidence_kind="clang-raw-comment-token",
                    source_sha256=hashlib.sha256(source).hexdigest(),
                )
            results.append(finding)
    return results


def _publish(output: Path, analysis: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    payload = {
        "schema_version": 1,
        "status": analysis["status"],
        "outcome": analysis["outcome"],
        "total_findings": len(findings),
        "analysis": {ACTIVE_LANGUAGE: analysis},
        "findings": findings,
    }
    _atomic_text(output, "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings))
    _json(output.with_name("scan.json"), analysis)
    _json(output.with_name("findings.json"), payload)
    counts: dict[str, int] = {}
    for row in findings:
        counts[row["pattern"]] = counts.get(row["pattern"], 0) + 1
    markdown = (
        f"# {ACTIVE_CONFIG['display']} comment-drift audit\n\n"
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


def _manifest_hash(inventory: list[dict[str, Any]]) -> str:
    rows = [
        [row["file"], row["source_sha256"]]
        for row in inventory
        if isinstance(row.get("source_sha256"), str)
    ]
    encoded = json.dumps(sorted(rows), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _verify_artifact(root: Path, artifact: Path, language: str) -> int:
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        analysis = payload["analysis"][language]
        inventory = analysis["inventory"]
        findings = payload["findings"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"invalid artifact: {exc}", file=sys.stderr)
        return 2
    errors: list[str] = []
    if analysis.get("source_manifest_sha256") != _manifest_hash(inventory):
        errors.append("artifact source manifest hash mismatch")
    inventory_hashes: dict[str, str] = {}
    for row in inventory:
        relative = row.get("file")
        expected = row.get("source_sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            continue
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
            actual = _hash(path)
        except (OSError, ValueError):
            errors.append(f"source unavailable: {relative}")
            continue
        inventory_hashes[relative] = expected
        if actual != expected:
            errors.append(f"source hash mismatch: {relative}")
    for finding in findings:
        relative = finding.get("file")
        expected = finding.get("source_sha256")
        if inventory_hashes.get(relative) != expected:
            errors.append(f"finding source hash mismatch: {relative}")
            continue
        try:
            path = (root / relative).resolve()
            source = path.read_bytes()
            span = finding["source_span"]
            spelling = source[span["start_byte"] : span["end_byte"]]
        except (OSError, KeyError, TypeError):
            errors.append(f"finding span unavailable: {relative}")
            continue
        if hashlib.sha256(spelling).hexdigest() != finding.get("spelling_sha256"):
            errors.append(f"finding spelling hash mismatch: {relative}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    print(
        f"verified {language} artifact: {len(inventory_hashes)} source hashes, "
        f"{len(findings)} findings"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    global ACTIVE_CONFIG, ACTIVE_LANGUAGE, ALL_SUFFIXES, HEADER_SUFFIXES, SOURCE_SUFFIXES
    language = "cpp"
    ACTIVE_LANGUAGE = language
    ACTIVE_CONFIG = LANGUAGE_CONFIGS[language]
    SOURCE_SUFFIXES = ACTIVE_CONFIG["source_suffixes"]
    HEADER_SUFFIXES = ACTIVE_CONFIG["header_suffixes"]
    ALL_SUFFIXES = SOURCE_SUFFIXES | HEADER_SUFFIXES
    parser = argparse.ArgumentParser(
        description=f"Analyze {ACTIVE_CONFIG['display']} comments with Clang raw tokens."
    )
    parser.add_argument("targets", nargs="*", default=["."])
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--clang", type=Path, default=Path("/usr/bin/clang"))
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path)
    destination.add_argument("--verify-artifact", type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    if args.verify_artifact is not None:
        return _verify_artifact(root, args.verify_artifact.resolve(), language)
    output = args.output.resolve()
    if output.suffix.casefold() != ".jsonl":
        parser.error("--output must be a .jsonl artifact path")
    for artifact in (output, output.with_name("scan.json"), output.with_name("findings.json"), output.with_name("report.md")):
        artifact.unlink(missing_ok=True)
    inventory, target_errors = _discover(args.targets or ["."], root)
    tool, rc = _probe(args.clang.resolve())
    base = {
        **tool,
        "language": language,
        "analyzer": "clang-raw-tokens",
        "syntax_standard": ACTIVE_CONFIG["standard"],
        "lexical_only": True,
        "limits": [
            "no macro expansion meaning",
            "no inactive branches meaning",
            "no comment-to-symbol semantics",
            ACTIVE_CONFIG["unsupported"],
        ],
        "inventory": [{key: value for key, value in row.items() if key != "path"} for row in inventory],
        "errors": list(target_errors),
        "compile_database": {"status": "not-evaluated"},
        "source_preserved": True,
    }
    if language == "cpp":
        base["source_manifest_sha256"] = _manifest_hash(base["inventory"])
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
        if _suffix(path) in HEADER_SUFFIXES and path.resolve() not in owned:
            row.update(role="excluded", reason="ambiguous-header")
        else:
            row["role"] = "eligible"
            eligible.append(row)
    findings: list[dict[str, Any]] = []
    analyzer_failures = 0
    analyzer_failure_kinds: list[str] = []
    for row in eligible:
        path = row["path"]
        syntax = _run(_command(args.clang.resolve(), path, commands, "syntax"), root)
        if syntax.returncode != 0:
            if "error:" not in syntax.stderr:
                analyzer_failures += 1
                row.update(role="failed", reason="clang-analysis-failed", detail=(syntax.stderr or syntax.stdout).strip())
                analyzer_failure_kinds.append("clang-analysis-failed")
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
            analyzer_failure_kinds.append("clang-analysis-failed")
            continue
        if language == "cpp":
            raw_status, raw_detail = _raw_output_status(path, raw_text)
            if raw_status != "complete":
                failure_kind = f"clang-output-{raw_status}"
                analyzer_failures += 1
                analyzer_failure_kinds.append(failure_kind)
                row.update(role="failed", reason=failure_kind, detail=raw_detail)
                base["errors"].append(f"{row['file']}:{failure_kind}")
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
        base["failure_kind"] = analyzer_failure_kinds[0]
    elif failed:
        status, outcome, rc = "partial", "incomplete", 0
    elif not eligible:
        status, outcome, rc = "unsupported", "unsupported", 2
        base["failure_kind"] = f"no-eligible-{language}-files"
    else:
        status, rc = "complete", 0
        outcome = "advisory-findings" if findings else "clean-within-complete"
    base.update(
        status=status,
        outcome=outcome,
        inventory=[{key: value for key, value in row.items() if key != "path"} for row in inventory],
        summary={"discovered": len(inventory), "eligible": complete_eligible, "excluded": excluded, "failed": failed},
    )
    if language == "cpp":
        base["source_manifest_sha256"] = _manifest_hash(base["inventory"])
    findings.sort(key=lambda row: (row["file"], row["lineno"], row["pattern"]))
    _publish(output, base, findings)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
