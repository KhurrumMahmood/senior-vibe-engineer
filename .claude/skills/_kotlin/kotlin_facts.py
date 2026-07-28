#!/usr/bin/env python3
"""Produce bounded Kotlin/JVM lexical, filesystem, and source-syntax facts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


JVM_TARGET = "17"
MINIMUM_KOTLIN = (2, 4, 0)
MINIMUM_JAVA = (17, 0, 0)
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen", "__generated__"})
VENDOR_DIRS = frozenset({"vendor", "vendors", "third_party", "third-party", "deps"})
BUILD_DIRS = frozenset({"build", "dist", "target", "out", ".native-build", "coverage"})
TOOLING_DIRS = frozenset({"script", "scripts", "tool", "tools"})
INTERNAL_DIRS = frozenset({".git", ".hg", ".svn", ".idea", ".gradle", ".kotlin"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
KOTLIN_VERSION_RE = re.compile(r"kotlinc-jvm\s+(\d+)\.(\d+)\.(\d+)", re.I)
JAVA_VERSION_RE = re.compile(r'(?:openjdk|java) version "(\d+)(?:\.(\d+))?(?:\.(\d+))?', re.I)
MULTI_OPERATORS = (
    "===", "!==", "..<", "...", "?.", "?:", "!!", "&&", "||", "::", "->",
    "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=", "++", "--", "..",
)
DECLARATION_KEYWORDS = frozenset({"class", "interface", "object", "typealias", "fun"})
CONTROL_KEYWORDS = frozenset({"if", "when", "for", "while", "catch", "switch"})


@dataclass(frozen=True)
class Token:
    """A direct source token; it carries no resolved identity."""

    kind: str
    text: str
    start: int
    end: int
    line: int


def add_fact_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--kotlinc")
    parser.add_argument("--java")


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def clear_artifacts(paths: Iterable[Path]) -> None:
    for path in paths:
        if path.is_file() or path.is_symlink():
            path.unlink()


def terminal_return_code(payload: dict[str, Any], producer_code: int = 0) -> int:
    if producer_code:
        return producer_code
    return 2 if payload.get("status") == "failed" else 0


def _run(
    argv: list[str], cwd: Path, *, timeout: int = 90,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False,
        shell=False, timeout=timeout,
    )


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_relative(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or raw in {".", ""}:
        return None
    return raw


def _source_role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    parts = set(path.relative_to(root).parts[:-1])
    if parts & GENERATED_DIRS or GENERATED_RE.search(text[:4096]):
        return "generated", "excluded-generated"
    if parts & VENDOR_DIRS:
        return "vendor", "excluded-vendor"
    if parts & BUILD_DIRS:
        return "build", "excluded-build"
    if parts & TOOLING_DIRS:
        return "tooling", "excluded-tooling"
    if parts & TEST_DIRS or path.name.endswith(("Test.kt", "Tests.kt")):
        return "test", "excluded-test"
    return "source", None


def _walk_candidates(root: Path) -> list[Path]:
    found: list[Path] = []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base = Path(current)
        dirs[:] = sorted(
            name for name in dirs
            if name not in INTERNAL_DIRS and not (base / name).is_symlink()
        )
        for name in sorted(files):
            path = base / name
            if path.suffix == ".kt" and not path.is_symlink():
                found.append(path)
    return found


def _inventory(root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    manifest: dict[str, str] = {}
    for path in _walk_candidates(root):
        relative = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError):
            rows.append({"file": relative, "role": "unreadable", "reason": "excluded-unreadable"})
            continue
        role, reason = _source_role(path, root, text)
        digest = hash_bytes(raw)
        rows.append({
            "file": relative, "role": role, "reason": reason,
            "source_sha256": digest, "bytes": len(raw),
        })
        manifest[relative] = digest
    return rows, manifest


def _manifest_hash(rows: dict[str, str]) -> str:
    serialized = "".join(f"{path}\0{digest}\n" for path, digest in sorted(rows.items()))
    return hash_bytes(serialized.encode())


def _resolve_tool(requested: str | None, fallback: str) -> Path | None:
    raw = requested or shutil.which(fallback)
    if not raw:
        return None
    try:
        path = Path(raw).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not path.is_file() or not os.access(path, os.X_OK):
        return None
    return path


def _probe_tool(
    root: Path, requested: str | None, *, name: str, argv: list[str],
    pattern: re.Pattern[str], minimum: tuple[int, int, int],
) -> tuple[dict[str, Any], Path | None]:
    path = _resolve_tool(requested, name)
    if path is None:
        return {"status": "missing", "path": None, "version": None}, None
    try:
        completed = _run([str(path), *argv], root, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "unusable", "path": str(path), "detail": str(exc)}, None
    rendered = f"{completed.stdout}\n{completed.stderr}"
    match = pattern.search(rendered)
    if not match:
        return {"status": "unusable", "path": str(path), "detail": rendered.strip()[:500]}, None
    groups = [int(value or 0) for value in match.groups()]
    version = tuple((groups + [0, 0, 0])[:3])
    status = "available" if version >= minimum else "too-old"
    return {
        "status": status, "path": str(path),
        "version": ".".join(str(value) for value in version),
        "minimum": ".".join(str(value) for value in minimum),
    }, path if status == "available" else None


def _load_project(root: Path, inventory: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        payload = json.loads((root / "kotlin-project.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("kotlin-project.json is unavailable or malformed") from exc
    keys = {"schema_version", "jvm_target", "sources", "tests", "test_main", "smoke_output"}
    if not isinstance(payload, dict) or set(payload) != keys:
        raise ValueError("kotlin-project.json has an unexpected shape")
    if payload["schema_version"] != 1 or payload["jvm_target"] != JVM_TARGET:
        raise ValueError("kotlin-project.json requests an unsupported contract")
    if not isinstance(payload["sources"], list) or not payload["sources"]:
        raise ValueError("kotlin-project.json must declare sources")
    if not isinstance(payload["tests"], list) or not payload["tests"]:
        raise ValueError("kotlin-project.json must declare tests")
    combined = [*payload["sources"], *payload["tests"]]
    if len(combined) != len(set(combined)):
        raise ValueError("kotlin-project.json contains duplicate inputs")
    roles = {row["file"]: row["role"] for row in inventory}
    for role, values in (("source", payload["sources"]), ("test", payload["tests"])):
        for raw in values:
            relative = _safe_relative(raw)
            if relative is None or PurePosixPath(relative).suffix != ".kt":
                raise ValueError(f"manifest {role} must be a safe lowercase .kt path")
            path = root / relative
            if not path.is_file() or path.is_symlink() or roles.get(relative) != role:
                raise ValueError(f"manifest {role} is unavailable or has an excluded role: {relative}")
    declared_sources = set(payload["sources"])
    eligible_sources = {path for path, role in roles.items() if role == "source"}
    if declared_sources != eligible_sources:
        raise ValueError("kotlin-project.json does not exactly enumerate first-party sources")
    declared_tests = set(payload["tests"])
    eligible_tests = {path for path, role in roles.items() if role == "test"}
    if declared_tests != eligible_tests:
        raise ValueError("kotlin-project.json does not exactly enumerate tests")
    if not isinstance(payload["test_main"], str) or not payload["test_main"]:
        raise ValueError("kotlin-project.json must declare test_main")
    if not isinstance(payload["smoke_output"], str):
        raise ValueError("kotlin-project.json must declare smoke_output")
    return payload


def _expected_commands(
    root: Path, project: dict[str, Any], kotlinc: Path, java: Path,
) -> dict[str, list[str]]:
    build = root / ".native-build"
    sources = [str(root / relative) for relative in project["sources"]]
    tests = [str(root / relative) for relative in project["tests"]]
    common = [str(kotlinc), "-jvm-target", JVM_TARGET, "-Werror", "-include-runtime"]
    return {
        "compile": [*common, "-d", str(build / "kotlin-app.jar"), *sources],
        "compile-tests": [*common, "-d", str(build / "kotlin-tests.jar"), *sources, *tests],
        "test": [str(java), "-cp", str(build / "kotlin-tests.jar"), project["test_main"]],
        "smoke": [str(java), "-jar", str(build / "kotlin-app.jar")],
    }


def _valid_digest(raw: object) -> bool:
    return (
        isinstance(raw, str) and len(raw) == 64
        and all(character in "0123456789abcdef" for character in raw)
    )


def _validate_evidence(
    root: Path, project: dict[str, Any], kotlinc: Path, java: Path,
) -> tuple[str, dict[str, Any] | None]:
    path = root / ".native-build/kotlin-build-evidence.json"
    if not path.is_file() or path.is_symlink():
        return "missing", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "malformed", None
    keys = {
        "schema_version", "status", "project_root", "jvm_target", "tools",
        "inputs", "commands", "outputs", "checks",
    }
    if not isinstance(payload, dict) or set(payload) != keys:
        return "malformed", None
    if (
        payload["schema_version"] != 1 or payload["status"] != "complete"
        or payload["project_root"] != str(root) or payload["jvm_target"] != JVM_TARGET
        or payload["tools"] != {"kotlinc": str(kotlinc), "java": str(java)}
    ):
        return "mismatched-contract", None
    expected_inputs = [
        {"path": relative, "role": role, "sha256": hash_bytes((root / relative).read_bytes())}
        for role, rows in (("source", project["sources"]), ("test", project["tests"]))
        for relative in rows
    ]
    if payload["inputs"] != expected_inputs:
        return "stale-or-incomplete-inputs", None
    if payload["commands"] != _expected_commands(root, project, kotlinc, java):
        return "wrong-command", None
    expected_outputs = [".native-build/kotlin-app.jar", ".native-build/kotlin-tests.jar"]
    outputs = payload["outputs"]
    if not isinstance(outputs, list) or [row.get("path") for row in outputs if isinstance(row, dict)] != expected_outputs:
        return "incomplete-outputs", None
    for row in outputs:
        if set(row) != {"path", "sha256"} or not _valid_digest(row["sha256"]):
            return "malformed", None
        output = root / row["path"]
        if not output.is_file() or output.is_symlink() or hash_bytes(output.read_bytes()) != row["sha256"]:
            return "stale-or-missing-output", None
    checks = payload["checks"]
    if not isinstance(checks, dict) or set(checks) != {"test", "smoke"}:
        return "malformed", None
    for name in ("test", "smoke"):
        check = checks[name]
        if (
            not isinstance(check, dict)
            or set(check) != {"returncode", "stdout", "stderr"}
            or check["returncode"] != 0
            or not isinstance(check["stdout"], str)
            or not isinstance(check["stderr"], str)
        ):
            return "native-check-failure", None
    if checks["smoke"]["stdout"] != project["smoke_output"]:
        return "native-check-failure", None
    return "valid-current", payload


def _diagnose(
    root: Path, project: dict[str, Any], kotlinc: Path,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="kotlin-facts-") as temporary:
        output = Path(temporary) / "diagnostic.jar"
        argv = [
            str(kotlinc), "-jvm-target", JVM_TARGET, "-Werror", "-d", str(output),
            *(str(root / relative) for relative in project["sources"]),
        ]
        return _run(argv, root, timeout=120)


def _lex(source: str) -> tuple[list[Token], list[dict[str, Any]]]:
    tokens: list[Token] = []
    comments: list[dict[str, Any]] = []
    index, line, length = 0, 1, len(source)
    while index < length:
        character = source[index]
        if character.isspace():
            line += character == "\n"
            index += 1
            continue
        start, start_line = index, line
        if source.startswith("//", index):
            end = source.find("\n", index + 2)
            end = length if end < 0 else end
            comments.append({
                "form": "line", "text": source[index + 2:end], "line": line,
                "span": {"start_byte": index, "end_byte": end},
            })
            index = end
            continue
        if source.startswith("/*", index):
            depth, cursor = 1, index + 2
            while cursor < length and depth:
                if source.startswith("/*", cursor):
                    depth += 1
                    cursor += 2
                elif source.startswith("*/", cursor):
                    depth -= 1
                    cursor += 2
                else:
                    cursor += 1
            end = cursor
            text = source[index + 2 : end - 2 if depth == 0 else end]
            comments.append({
                "form": "block", "text": text, "line": line,
                "span": {"start_byte": index, "end_byte": end},
            })
            line += source[index:end].count("\n")
            index = end
            continue
        if source.startswith('"""', index):
            end = source.find('"""', index + 3)
            end = length if end < 0 else end + 3
            tokens.append(Token("string", source[index:end], index, end, line))
            line += source[index:end].count("\n")
            index = end
            continue
        if character in {'"', "'"}:
            quote, cursor = character, index + 1
            while cursor < length:
                if source[cursor] == "\\":
                    cursor += 2
                    continue
                cursor += 1
                if source[cursor - 1] == quote:
                    break
            tokens.append(Token("string", source[index:cursor], index, cursor, line))
            line += source[index:cursor].count("\n")
            index = cursor
            continue
        if character == "`":
            end = source.find("`", index + 1)
            end = length if end < 0 else end + 1
            tokens.append(Token("identifier", source[index + 1 : end - 1], index, end, line))
            index = end
            continue
        if character == "_" or character.isalpha():
            cursor = index + 1
            while cursor < length and (source[cursor] == "_" or source[cursor].isalnum()):
                cursor += 1
            text = source[index:cursor]
            kind = "keyword" if text in DECLARATION_KEYWORDS | CONTROL_KEYWORDS else "identifier"
            tokens.append(Token(kind, text, index, cursor, line))
            index = cursor
            continue
        if character.isdigit():
            cursor = index + 1
            while cursor < length and (source[cursor].isalnum() or source[cursor] in "._"):
                cursor += 1
            tokens.append(Token("number", source[index:cursor], index, cursor, line))
            index = cursor
            continue
        operator = next((item for item in MULTI_OPERATORS if source.startswith(item, index)), None)
        if operator:
            tokens.append(Token("symbol", operator, index, index + len(operator), line))
            index += len(operator)
            continue
        tokens.append(Token("symbol", character, start, start + 1, start_line))
        index += 1
    return tokens, comments


def _pairs(tokens: list[Token], opening: str, closing: str) -> dict[int, int]:
    stack: list[int] = []
    pairs: dict[int, int] = {}
    for index, token in enumerate(tokens):
        if token.text == opening:
            stack.append(index)
        elif token.text == closing and stack:
            start = stack.pop()
            pairs[start] = index
    return pairs


def _package(tokens: list[Token]) -> str:
    for index, token in enumerate(tokens):
        if token.text != "package":
            continue
        parts: list[str] = []
        for item in tokens[index + 1 :]:
            if item.line != token.line or item.text == ";":
                break
            if item.kind == "identifier" or item.text == ".":
                parts.append(item.text)
        return "".join(parts)
    return ""


def _type_declarations(
    source: str, tokens: list[Token], brace_pairs: dict[int, int], package: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        if token.text not in {"class", "interface", "object", "typealias"}:
            continue
        name_index = next(
            (cursor for cursor in range(index + 1, min(index + 5, len(tokens)))
             if tokens[cursor].kind == "identifier"),
            None,
        )
        if name_index is None:
            continue
        name = tokens[name_index].text
        modifiers = {item.text for item in tokens[max(0, index - 4):index] if item.line == token.line}
        if token.text == "class" and "data" in modifiers:
            kind = "data-class"
        elif token.text == "class" and "enum" in modifiers:
            kind = "enum-class"
        elif token.text == "interface" and "sealed" in modifiers:
            kind = "sealed-interface"
        elif token.text == "class" and "sealed" in modifiers:
            kind = "sealed-class"
        else:
            kind = token.text
        body_start = next(
            (cursor for cursor in range(name_index + 1, len(tokens))
             if tokens[cursor].text in {"{", ";"} or tokens[cursor].line > token.line + 20),
            None,
        )
        body_end = brace_pairs.get(body_start) if body_start is not None else None
        end_token = tokens[body_end] if body_end is not None else tokens[name_index]
        qualified = ".".join(part for part in (package, name) if part)
        rows.append({
            "kind": kind, "name": name, "qualified_name": qualified,
            "line": token.line, "end_line": end_token.line,
            "signature": " ".join(item.text for item in tokens[index:name_index + 1]),
            "extension_receiver": None,
            "span": {"start_byte": token.start, "end_byte": end_token.end},
            "body_token_start": body_start, "body_token_end": body_end,
        })
    return rows


def _if_ranges(
    body_start: int, body_end: int, tokens: list[Token],
    paren_pairs: dict[int, int], brace_pairs: dict[int, int],
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for index in range(body_start, body_end + 1):
        if tokens[index].text != "if":
            continue
        opening = index + 1 if index + 1 < len(tokens) and tokens[index + 1].text == "(" else None
        if opening is None or opening not in paren_pairs:
            continue
        cursor = paren_pairs[opening] + 1
        if cursor < len(tokens) and tokens[cursor].text == "{" and cursor in brace_pairs:
            ranges.append((cursor, brace_pairs[cursor]))
        else:
            line = tokens[cursor].line if cursor < len(tokens) else tokens[index].line
            end = cursor
            while end + 1 <= body_end and tokens[end + 1].line == line:
                end += 1
            ranges.append((cursor, end))
    return ranges


def _function_declarations(
    source: str, tokens: list[Token], brace_pairs: dict[int, int],
    paren_pairs: dict[int, int], package: str, types: list[dict[str, Any]],
    source_sha256: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        if token.text != "fun":
            continue
        opening = next(
            (cursor for cursor in range(index + 1, len(tokens)) if tokens[cursor].text == "("),
            None,
        )
        if opening is None or opening not in paren_pairs:
            continue
        name_index = next(
            (cursor for cursor in range(opening - 1, index, -1) if tokens[cursor].kind == "identifier"),
            None,
        )
        if name_index is None:
            continue
        name = tokens[name_index].text
        receiver_tokens = tokens[index + 1:name_index]
        dot_positions = [position for position, item in enumerate(receiver_tokens) if item.text == "."]
        extension_receiver = None
        if dot_positions:
            extension_receiver = "".join(item.text for item in receiver_tokens[:dot_positions[-1]])
        close_paren = paren_pairs[opening]
        cursor = close_paren + 1
        body_start: int | None = None
        while cursor < len(tokens):
            if tokens[cursor].text in {"{", "="}:
                body_start = cursor
                break
            if tokens[cursor].text == ";" or tokens[cursor].text == "fun":
                break
            cursor += 1
        if body_start is None:
            signature_end = close_paren
            body_end = close_paren
            body_tokens: list[Token] = []
        elif tokens[body_start].text == "{" and body_start in brace_pairs:
            body_end = brace_pairs[body_start]
            signature_end = body_start - 1
            body_tokens = tokens[body_start + 1:body_end]
        else:
            signature_end = body_start - 1
            body_end = body_start
            while body_end + 1 < len(tokens) and tokens[body_end + 1].line == tokens[body_start].line:
                body_end += 1
            body_tokens = tokens[body_start + 1:body_end + 1]
        enclosing = [
            row for row in types
            if row["body_token_start"] is not None and row["body_token_end"] is not None
            and row["body_token_start"] < index < row["body_token_end"]
        ]
        owner = min(enclosing, key=lambda row: row["body_token_end"] - row["body_token_start"])["name"] if enclosing else None
        qualified = ".".join(part for part in (package, owner, name) if part)
        normalized = "\x1f".join(item.text for item in body_tokens)
        if_ranges = _if_ranges(body_start or index, body_end, tokens, paren_pairs, brace_pairs)
        calls: list[dict[str, Any]] = []
        excluded_calls = CONTROL_KEYWORDS | DECLARATION_KEYWORDS | {"return", "throw", "super", "this"}
        for cursor in range((body_start or index) + 1, body_end):
            current = tokens[cursor]
            if (
                current.kind == "identifier" and current.text not in excluded_calls
                and cursor + 1 < len(tokens) and tokens[cursor + 1].text == "("
            ):
                calls.append({
                    "spelling": current.text, "line": current.line,
                    "enclosures": ["if"] if any(start < cursor < end for start, end in if_ranges) else [],
                    "claim": "unresolved-direct-call-spelling",
                })
        rows.append({
            "kind": "function", "name": name, "qualified_name": qualified,
            "signature": " ".join(item.text for item in tokens[index:signature_end + 1]),
            "extension_receiver": extension_receiver,
            "line": token.line, "end_line": tokens[body_end].line,
            "loc": max(1, tokens[body_end].line - token.line + 1),
            "span": {"start_byte": token.start, "end_byte": tokens[body_end].end},
            "spelling_sha256": hash_bytes(source[token.start:tokens[body_end].end].encode()),
            "normalized_body_sha256": hash_bytes(normalized.encode()),
            "branch_score": sum(item.text in CONTROL_KEYWORDS for item in body_tokens),
            "calls": calls, "source_sha256": source_sha256,
        })
    return rows


def _syntax_file(path: Path, root: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    raw = source.encode()
    tokens, comments = _lex(source)
    brace_pairs = _pairs(tokens, "{", "}")
    paren_pairs = _pairs(tokens, "(", ")")
    package = _package(tokens)
    types = _type_declarations(source, tokens, brace_pairs, package)
    functions = _function_declarations(
        source, tokens, brace_pairs, paren_pairs, package, types, hash_bytes(raw)
    )
    public_types = [
        {key: value for key, value in row.items() if not key.startswith("body_token_")}
        for row in types
    ]
    return {
        "file": path.relative_to(root).as_posix(), "package": package,
        "source_sha256": hash_bytes(raw), "comments": comments,
        "identifier_tokens": [
            {"text": token.text, "line": token.line, "span": {"start_byte": token.start, "end_byte": token.end}}
            for token in tokens if token.kind == "identifier"
        ],
        "declarations": [*public_types, *functions], "functions": functions,
        "token_count": len(tokens),
    }


def _base_payload(
    root: Path, target: Path, inventory: list[dict[str, Any]], before: dict[str, str],
    tools: dict[str, Any], project: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1, "status": "failed", "failure_kind": "unknown",
        "language": "kotlin", "syntax_standard": "Kotlin/JVM 2.4 source syntax",
        "analyzer": "kotlinc-jvm17-diagnostic+kotlin-source-tokenizer",
        "project_root": str(root), "target": str(target), "tools": tools,
        "project_manifest": project,
        "inventory": inventory, "files": [], "native_evidence": {"state": "not-validated"},
        "source_manifest": {
            "before": before, "before_sha256": _manifest_hash(before),
            "after": None, "after_sha256": None, "preserved": False,
        },
        "boundaries": {
            "eligible_sources": "exact lowercase .kt paths declared by kotlin-project.json",
            "source_roles": "test, generated, vendor, build, tooling, unreadable, and symlink paths excluded",
            "resolved_symbols": "not available", "resolved_calls": "not available",
            "overrides": "not analyzed", "data_flow": "not analyzed",
            "compiler_ir": "not consumed", "runtime_behavior": "not proven",
        },
        "limits": [
            "Tokens, comments, declarations, branches, and direct call spellings are source syntax only.",
            "No resolved symbols, call targets, overrides, data flow, reflection, compiler IR, or runtime behavior are claimed.",
            "Only exact lowercase .kt Kotlin/JVM inputs in kotlin-project.json are eligible; .kts, Android, Multiplatform, Kotlin/JS, and Kotlin/Native are outside scope.",
        ],
    }


def produce(
    project_root: Path, target: Path, *, kotlinc: str | None, java: str | None,
    allow_source_only: bool = False,
) -> tuple[dict[str, Any], int]:
    try:
        root = project_root.resolve(strict=True)
    except (OSError, RuntimeError):
        root = project_root.resolve()
        return {
            "status": "failed", "failure_kind": "project_root_invalid",
            "language": "kotlin", "project_root": str(root), "files": [],
        }, 2
    requested_target = target if target.is_absolute() else root / target
    try:
        selected_target = requested_target.resolve(strict=True)
    except (OSError, RuntimeError):
        selected_target = requested_target.resolve()
    inventory, before = _inventory(root)
    kotlin_probe, kotlinc_path = _probe_tool(
        root, kotlinc, name="kotlinc", argv=["-version"],
        pattern=KOTLIN_VERSION_RE, minimum=MINIMUM_KOTLIN,
    )
    java_probe, java_path = _probe_tool(
        root, java, name="java", argv=["-version"],
        pattern=JAVA_VERSION_RE, minimum=MINIMUM_JAVA,
    )
    tools = {"kotlinc": kotlin_probe, "java": java_probe}
    payload = _base_payload(root, selected_target, inventory, before, tools, None)
    if not root.is_dir() or root.is_symlink() or not _inside(selected_target, root):
        payload.update(failure_kind="project_or_target_invalid")
        return payload, 2
    if kotlinc_path is None or java_path is None:
        missing = "kotlinc" if kotlinc_path is None else "java"
        state = tools[missing]["status"].replace("-", "_")
        payload.update(status="unsupported", failure_kind=f"{missing}_tool_{state}")
        after_inventory, after = _inventory(root)
        payload["inventory"] = after_inventory
        payload["source_manifest"].update(
            after=after, after_sha256=_manifest_hash(after), preserved=before == after,
        )
        return payload, 0
    try:
        project = _load_project(root, inventory)
    except ValueError as exc:
        if allow_source_only:
            selected_sources = [
                root / row["file"]
                for row in inventory
                if row["role"] == "source"
                and (
                    _inside(root / row["file"], selected_target)
                    or (selected_target.is_file() and root / row["file"] == selected_target)
                )
            ]
            if selected_sources:
                payload["files"] = [_syntax_file(path, root) for path in selected_sources]
                payload["analyzer"] = "kotlin-source-tokenizer"
                payload["boundaries"]["eligible_sources"] = (
                    "authored lowercase .kt files under the explicit target; "
                    "build membership and generated inputs are unvalidated"
                )
                payload["limits"].append(
                    "The project manifest was absent or invalid, so native compilation, "
                    "dependency resolution, and build-target membership were not validated."
                )
                payload.update(
                    status="partial",
                    failure_kind="kotlin_project_manifest_invalid",
                    detail=str(exc),
                )
                after_inventory, after = _inventory(root)
                payload["inventory"] = after_inventory
                payload["source_manifest"].update(
                    after=after,
                    after_sha256=_manifest_hash(after),
                    preserved=before == after,
                )
                if not payload["source_manifest"]["preserved"]:
                    payload.update(status="failed", failure_kind="unexpected_source_mutation")
                    return payload, 2
                return payload, 0
        payload.update(failure_kind="kotlin_project_manifest_invalid", detail=str(exc))
        after_inventory, after = _inventory(root)
        payload["inventory"] = after_inventory
        payload["source_manifest"].update(
            after=after, after_sha256=_manifest_hash(after), preserved=before == after,
        )
        return payload, 2
    payload["project_manifest"] = project
    diagnostic = _diagnose(root, project, kotlinc_path)
    payload["kotlinc_diagnostic"] = {
        "status": "passed" if diagnostic.returncode == 0 else "failed",
        "returncode": diagnostic.returncode,
        "stdout": diagnostic.stdout[:2000], "stderr": diagnostic.stderr[:4000],
        "contract": "direct JVM 17 compile diagnostic over exact manifest sources",
    }
    if diagnostic.returncode:
        payload.update(failure_kind="kotlinc_diagnostic_failed")
    else:
        evidence_state, evidence = _validate_evidence(root, project, kotlinc_path, java_path)
        payload["native_evidence"] = {"state": evidence_state}
        if evidence is None:
            payload.update(failure_kind=f"kotlin_build_evidence_{evidence_state.replace('-', '_')}")
        else:
            replay: dict[str, subprocess.CompletedProcess[str]] = {}
            for name in ("test", "smoke"):
                replay[name] = _run(evidence["commands"][name], root, timeout=60)
            if (
                any(result.returncode for result in replay.values())
                or replay["test"].stdout != evidence["checks"]["test"]["stdout"]
                or replay["smoke"].stdout != project["smoke_output"]
            ):
                payload.update(failure_kind="kotlin_native_replay_failed")
                payload["native_evidence"] = {"state": "native-replay-failed"}
            else:
                selected_sources = [
                    root / relative for relative in project["sources"]
                    if _inside(root / relative, selected_target)
                    or (selected_target.is_file() and root / relative == selected_target)
                ]
                payload["files"] = [_syntax_file(path, root) for path in selected_sources]
                payload["native_evidence"] = {
                    "state": "valid-current-and-replayed",
                    "evidence_sha256": hash_bytes(
                        (root / ".native-build/kotlin-build-evidence.json").read_bytes()
                    ),
                    "test_stdout": replay["test"].stdout,
                    "smoke_stdout": replay["smoke"].stdout,
                    "commands": evidence["commands"],
                }
                payload.update(status="complete", failure_kind="none")
    after_inventory, after = _inventory(root)
    payload["inventory"] = after_inventory
    payload["source_manifest"].update(
        after=after, after_sha256=_manifest_hash(after), preserved=before == after,
    )
    if not payload["source_manifest"]["preserved"]:
        payload.update(status="failed", failure_kind="unexpected_source_mutation")
        return payload, 2
    return payload, terminal_return_code(payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    add_fact_arguments(parser)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload, code = produce(
        args.project_root, args.target, kotlinc=args.kotlinc, java=args.java
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
