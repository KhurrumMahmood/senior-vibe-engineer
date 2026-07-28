#!/usr/bin/env python3
"""Produce bounded, source-preserving Rust syntax facts for read-only skills.

This is deliberately not a universal AST. It inventories first-party Rust,
attempts a locked/offline Cargo validation with stable native tools, masks Rust
comments and literals, and emits only comment, function, branch, and direct-call
facts needed by the four Rust syntax-family consumers. Offline validation may
reuse an existing local Cargo cache but never fetches dependencies.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MINIMUMS = {
    "cargo": (1, 85, 0),
    "rustc": (1, 85, 0),
    "rustfmt": (1, 8, 0),
    "clippy": (0, 1, 85),
}
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen", "__generated__"})
VENDOR_DIRS = frozenset({"vendor", "vendors", "third_party", "third-party", "deps"})
BUILD_DIRS = frozenset({"target", "build", "dist", "out", "coverage", "reports"})
AUXILIARY_DIRS = frozenset({"examples", "benches"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CFG_RE = re.compile(r"#\s*!?\s*\[\s*cfg(?:_attr)?\b")
MACRO_RE = re.compile(r"\b(?:macro_rules|include)\s*!|\b[A-Za-z_][A-Za-z0-9_]*\s*!")
BUILD_OUTPUT_RE = re.compile(r"\b(?:OUT_DIR|include!)\b|fs::write|File::create|cargo:rustc-(?:cfg|env)")
OFFLINE_DEPENDENCY_RE = re.compile(
    r"no matching package named|failed to download|attempting to make an HTTP request|"
    r"can't find crate|could not find .* in registry",
    re.IGNORECASE,
)
CONTROL_WORDS = frozenset({
    "if", "else", "for", "while", "loop", "match", "return", "break",
    "continue", "fn", "struct", "enum", "impl", "trait", "mod", "use",
    "let", "const", "static", "type", "where", "unsafe", "async", "move",
})


@dataclass(frozen=True)
class Token:
    value: str
    start: int
    end: int


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(
    argv: list[str], cwd: Path, *, env: dict[str, str] | None = None, timeout: int = 180
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": argv,
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "argv": argv,
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[:8000],
        "stderr": result.stderr[:8000],
    }


def _resolve_tool(raw: str | None, name: str) -> Path | None:
    value = raw or name
    if os.sep in value or (os.altsep and os.altsep in value):
        path = Path(value)
        return path.resolve() if path.is_file() and os.access(path, os.X_OK) else None
    discovered = shutil.which(value)
    return Path(discovered).resolve() if discovered else None


def _version(text: str, name: str) -> tuple[int, int, int] | None:
    patterns = {
        "cargo": r"\bcargo\s+(\d+)\.(\d+)\.(\d+)",
        "rustc": r"\brustc\s+(\d+)\.(\d+)\.(\d+)",
        "rustfmt": r"\brustfmt\s+(\d+)\.(\d+)\.(\d+)",
        "clippy": r"\bclippy\s+(\d+)\.(\d+)\.(\d+)",
    }
    match = re.search(patterns[name], text)
    return tuple(map(int, match.groups())) if match else None


def _probe_tools(root: Path, requested: dict[str, str | None]) -> tuple[dict[str, Any], str | None, str]:
    probes: dict[str, Any] = {}
    for name in ("cargo", "rustc", "rustfmt", "clippy"):
        path = _resolve_tool(requested.get(name), "cargo-clippy" if name == "clippy" else name)
        if path is None:
            probes[name] = {"state": "missing", "path": requested.get(name)}
            return probes, f"{name}_tool_missing", "partial"
        result = _run([str(path), "--version"], root, timeout=20)
        if not result["passed"]:
            probes[name] = {"state": "failed", "path": str(path), "probe": result}
            return probes, f"{name}_tool_probe_failed", "failed"
        parsed = _version(result["stdout"], name)
        if parsed is None:
            probes[name] = {"state": "failed", "path": str(path), "probe": result}
            return probes, f"{name}_tool_probe_failed", "failed"
        if parsed < MINIMUMS[name]:
            probes[name] = {
                "state": "too-old",
                "path": str(path),
                "version": ".".join(map(str, parsed)),
                "minimum": ".".join(map(str, MINIMUMS[name])),
            }
            return probes, f"{name}_tool_too_old", "partial"
        probes[name] = {
            "state": "ready",
            "path": str(path),
            "version": ".".join(map(str, parsed)),
        }
    return probes, None, "complete"


def _walk_rust(root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in list(dirnames):
            candidate = current / name
            if candidate.is_symlink():
                paths.append(candidate)
                dirnames.remove(name)
        for name in filenames:
            candidate = current / name
            if candidate.suffix.lower() == ".rs" or candidate.is_symlink():
                paths.append(candidate)
    return sorted(set(paths))


def _role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if path.is_symlink():
        return "symlink", "rust_symlink_boundary"
    if parts & BUILD_DIRS:
        return "build", "build-output"
    if parts & VENDOR_DIRS:
        return "vendor", "vendor"
    if parts & GENERATED_DIRS or GENERATED_RE.search(text[:4096]):
        return "generated", "generated"
    if parts & TEST_DIRS or name.endswith("_test.rs"):
        return "test", "test"
    if parts & AUXILIARY_DIRS:
        return "auxiliary", "auxiliary-target"
    if name == "build.rs":
        return "configuration", "build-script"
    return "source", None


def _inventory(root: Path, target: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []
    for path in _walk_rust(root):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            row = {"file": relative, "role": "symlink", "reason": "external-or-indirect-source"}
            inventory.append(row)
            if path == target or target in path.parents or path in target.parents:
                ambiguities.append({"kind": "rust_symlink_boundary", "file": relative})
            continue
        try:
            content = path.read_bytes()
            text = content.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            row = {"file": relative, "role": "failed", "reason": "read-error", "detail": str(exc)}
            inventory.append(row)
            ambiguities.append({"kind": "rust_source_read_failed", "file": relative})
            continue
        role, reason = _role(path, root, text)
        row = {
            "file": relative,
            "role": role,
            "source_sha256": _hash(content),
            "source_bytes": len(content),
            **({"reason": reason} if reason else {}),
        }
        inventory.append(row)
        try:
            in_target = path == target or target in path.parents
        except RuntimeError:
            in_target = False
        if in_target and role == "source":
            selected.append({**row, "path": path, "text": text})
    return inventory, selected, ambiguities


def _project_manifest(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        dirnames[:] = [
            name
            for name in dirnames
            if name not in {".git", "target", "reports", "__pycache__"}
            and not (current / name).is_symlink()
        ]
        for name in sorted(filenames):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                rows[relative] = "symlink:" + os.readlink(path)
            else:
                rows[relative] = _hash(path.read_bytes())
        for name in sorted(set(os.listdir(current)) - set(dirnames) - set(filenames)):
            path = current / name
            if path.is_symlink():
                rows[path.relative_to(root).as_posix()] = "symlink:" + os.readlink(path)
    return rows


def _manifest_hash(rows: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(rows.items()):
        digest.update(path.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest()


def _line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    return starts


def _line(starts: list[int], offset: int) -> int:
    return bisect.bisect_right(starts, offset)


def _raw_string_end(text: str, start: int) -> int | None:
    cursor = start
    if text.startswith("br", cursor) or text.startswith("cr", cursor):
        cursor += 2
    elif text.startswith("r", cursor):
        cursor += 1
    else:
        return None
    hashes = 0
    while cursor < len(text) and text[cursor] == "#":
        hashes += 1
        cursor += 1
    if cursor >= len(text) or text[cursor] != '"':
        return None
    terminator = '"' + "#" * hashes
    found = text.find(terminator, cursor + 1)
    return len(text) if found < 0 else found + len(terminator)


def _quoted_end(text: str, start: int, quote: str) -> int:
    cursor = start + 1
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text[cursor] == quote:
            return cursor + 1
        cursor += 1
    return len(text)


def _char_literal_end(text: str, start: int) -> int | None:
    if text[start] != "'":
        return None
    cursor = start + 1
    if cursor >= len(text):
        return None
    if text[cursor] == "\\":
        cursor += 2
    else:
        cursor += 1
    return cursor + 1 if cursor < len(text) and text[cursor] == "'" else None


def _lex(text: str) -> tuple[list[Token], list[dict[str, Any]], str]:
    tokens: list[Token] = []
    comments: list[dict[str, Any]] = []
    masked = list(text)
    starts = _line_starts(text)
    cursor = 0
    length = len(text)

    def blank(start: int, end: int) -> None:
        for index in range(start, end):
            if masked[index] not in {"\n", "\r"}:
                masked[index] = " "

    while cursor < length:
        if text.startswith("//", cursor):
            end = text.find("\n", cursor)
            end = length if end < 0 else end
            marker = "line-doc" if text.startswith("///", cursor) or text.startswith("//!", cursor) else "line"
            comments.append({
                "text": text[cursor:end], "form": marker,
                "line": _line(starts, cursor), "end_line": _line(starts, max(cursor, end - 1)),
                "start": cursor, "end": end,
            })
            blank(cursor, end)
            cursor = end
            continue
        if text.startswith("/*", cursor):
            depth = 1
            end = cursor + 2
            while end < length and depth:
                if text.startswith("/*", end):
                    depth += 1
                    end += 2
                elif text.startswith("*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
            marker = "block-doc" if text.startswith("/**", cursor) or text.startswith("/*!", cursor) else "block"
            comments.append({
                "text": text[cursor:end], "form": marker,
                "line": _line(starts, cursor), "end_line": _line(starts, max(cursor, end - 1)),
                "start": cursor, "end": end,
            })
            blank(cursor, end)
            cursor = end
            continue
        raw_end = _raw_string_end(text, cursor)
        if raw_end is not None:
            blank(cursor, raw_end)
            cursor = raw_end
            continue
        if text.startswith('b"', cursor) or text.startswith('c"', cursor):
            end = _quoted_end(text, cursor + 1, '"')
            blank(cursor, end)
            cursor = end
            continue
        if text[cursor] == '"':
            end = _quoted_end(text, cursor, '"')
            blank(cursor, end)
            cursor = end
            continue
        char_start = cursor + 1 if text.startswith("b'", cursor) else cursor
        if char_start < length and text[char_start] == "'":
            char_end = _char_literal_end(text, char_start)
            if char_end is not None:
                end = char_end
                blank(cursor, end)
                cursor = end
                continue
        match = IDENTIFIER_RE.match(text, cursor)
        if match:
            tokens.append(Token(match.group(), cursor, match.end()))
            cursor = match.end()
            continue
        if text[cursor].isspace():
            cursor += 1
            continue
        composite = next(
            (value for value in ("::", "&&", "||", "=>", "->", "..=", "..", "<=", ">=", "==", "!=") if text.startswith(value, cursor)),
            None,
        )
        if composite:
            tokens.append(Token(composite, cursor, cursor + len(composite)))
            cursor += len(composite)
        else:
            tokens.append(Token(text[cursor], cursor, cursor + 1))
            cursor += 1
    return tokens, comments, "".join(masked)


def _brace_pairs(tokens: list[Token]) -> dict[int, int]:
    stack: list[int] = []
    pairs: dict[int, int] = {}
    for index, token in enumerate(tokens):
        if token.value == "{":
            stack.append(index)
        elif token.value == "}" and stack:
            start = stack.pop()
            pairs[start] = index
    return pairs


def _function_rows(tokens: list[Token], pairs: dict[int, int], text: str) -> list[dict[str, Any]]:
    starts = _line_starts(text)
    raw: list[tuple[int, int, int, str]] = []
    for index, token in enumerate(tokens):
        if token.value != "fn" or index + 1 >= len(tokens):
            continue
        name = tokens[index + 1].value
        if not IDENTIFIER_RE.fullmatch(name):
            continue
        body = next(
            (cursor for cursor in range(index + 2, len(tokens)) if tokens[cursor].value in {"{", ";"}),
            None,
        )
        if body is None or tokens[body].value != "{" or body not in pairs:
            continue
        raw.append((index, body, pairs[body], name))

    closure_ranges: list[tuple[int, int]] = []
    for body, end in pairs.items():
        previous = tokens[body - 1].value if body else ""
        if previous in {"|", "||"}:
            closure_ranges.append((body, end))

    rows: list[dict[str, Any]] = []
    branch_words = {"if", "for", "while", "loop", "match"}
    for fn_index, body, end, name in raw:
        child_ranges = [
            (child_body, child_end)
            for _, child_body, child_end, _ in raw
            if body < child_body < end
        ]
        child_ranges.extend((start, stop) for start, stop in closure_ranges if body < start < end)

        def nested(index: int, ranges: tuple[tuple[int, int], ...] = tuple(child_ranges)) -> bool:
            return any(start <= index <= stop for start, stop in ranges)

        score = sum(
            token.value in branch_words or token.value in {"&&", "||"}
            for index, token in enumerate(tokens[body + 1 : end], start=body + 1)
            if not nested(index)
        )
        start_line = _line(starts, tokens[fn_index].start)
        end_line = _line(starts, tokens[end].end - 1)
        rows.append({
            "name": name,
            "kind": "function",
            "line": start_line,
            "end_line": end_line,
            "loc": end_line - start_line + 1,
            "branch_score": score,
            "token_start": fn_index,
            "body_token": body,
            "token_end": end,
        })
    return rows


def _call_rows(
    tokens: list[Token], pairs: dict[int, int], functions: list[dict[str, Any]], text: str
) -> list[dict[str, Any]]:
    starts = _line_starts(text)
    match_ranges: list[tuple[int, int]] = []
    for index, token in enumerate(tokens):
        if token.value != "match":
            continue
        brace = next((cursor for cursor in range(index + 1, len(tokens)) if tokens[cursor].value == "{"), None)
        if brace is not None and brace in pairs:
            match_ranges.append((index, pairs[brace]))
    calls: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        if token.value != "(" or index == 0:
            continue
        cursor = index - 1
        if not IDENTIFIER_RE.fullmatch(tokens[cursor].value):
            continue
        parts = [tokens[cursor].value]
        start = cursor
        while start >= 2 and tokens[start - 1].value in {"::", "."} and IDENTIFIER_RE.fullmatch(tokens[start - 2].value):
            parts[:0] = [tokens[start - 2].value, tokens[start - 1].value]
            start -= 2
        spelling = "".join(parts)
        if parts[-1] in CONTROL_WORDS or (start and tokens[start - 1].value == "fn"):
            continue
        owners = [row for row in functions if row["body_token"] < index < row["token_end"]]
        owner = min(owners, key=lambda row: row["token_end"] - row["body_token"]) if owners else None
        calls.append({
            "spelling": spelling,
            "line": _line(starts, tokens[start].start),
            "function": owner["name"] if owner else None,
            "enclosures": ["match"] if any(begin <= index <= end for begin, end in match_ranges) else [],
        })
    return calls


def _facts(row: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    text = row["text"]
    tokens, comments, masked = _lex(text)
    pairs = _brace_pairs(tokens)
    functions = _function_rows(tokens, pairs, text)
    calls = _call_rows(tokens, pairs, functions, text)
    ambiguities: list[dict[str, Any]] = []
    if CFG_RE.search(masked):
        ambiguities.append({"kind": "rust_cfg_ambiguity", "file": row["file"]})
    if MACRO_RE.search(masked):
        ambiguities.append({"kind": "rust_macro_ambiguity", "file": row["file"]})
    public_functions = [
        {
            key: value
            for key, value in function.items()
            if key not in {"token_start", "body_token", "token_end"}
        }
        for function in functions
    ]
    return {
        "file": row["file"],
        "source_sha256": row["source_sha256"],
        "comments": comments,
        "functions": public_functions,
        "calls": calls,
    }, ambiguities


def _cargo_environment(state: Path, probes: dict[str, Any]) -> dict[str, str]:
    target = state / "target"
    return {
        **os.environ,
        "CARGO_TARGET_DIR": str(target),
        "CARGO_NET_OFFLINE": "true",
        "RUSTC": probes["rustc"]["path"],
        "ALL_PROXY": "http://127.0.0.1:9",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
    }


def _native(
    root: Path,
    probes: dict[str, Any],
    selected: list[dict[str, Any]],
) -> tuple[dict[str, Any], str | None, str]:
    with tempfile.TemporaryDirectory(prefix="rust-syntax-") as raw_state:
        state = Path(raw_state)
        env = _cargo_environment(state, probes)
        cargo = probes["cargo"]["path"]
        commands = {
            "cargo_metadata": [cargo, "metadata", "--format-version", "1", "--locked", "--offline", "--no-deps"],
            "cargo_check": [cargo, "check", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"],
            "cargo_test": [cargo, "test", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"],
            "cargo_clippy": [cargo, "clippy", "--locked", "--offline", "--workspace", "--all-targets", "--all-features", "--", "-D", "warnings"],
            "cargo_fmt": [cargo, "fmt", "--all", "--", "--check"],
        }
        results: dict[str, Any] = {}
        for name, argv in commands.items():
            results[name] = _run(argv, root, env=env)
            if not results[name]["passed"]:
                transcript = results[name]["stdout"] + "\n" + results[name]["stderr"]
                if name.startswith("cargo_") and OFFLINE_DEPENDENCY_RE.search(transcript):
                    return results, "cargo_dependency_cache_unavailable", "partial"
                return results, f"{name}_failed", "failed"
        for row in selected:
            command = [
                probes["rustfmt"]["path"],
                "--edition", "2024", "--check", "--config", "skip_children=true",
                str(row["path"]),
            ]
            result = _run(command, root, env=env)
            results.setdefault("rustfmt_files", []).append({"file": row["file"], **result})
            if not result["passed"]:
                return results, "rustfmt_parse_failed", "failed"
        return results, None, "complete"


def _terminal(
    *,
    status: str,
    failure_kind: str,
    root: Path,
    target: Path,
    before: dict[str, str],
    after: dict[str, str],
    inventory: list[dict[str, Any]],
    files: list[dict[str, Any]],
    ambiguities: list[dict[str, Any]],
    tools: dict[str, Any],
    native: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "analyzer": "rust-syntax-facts-v1",
        "status": status,
        "failure_kind": failure_kind,
        "project_root": str(root),
        "target": target.relative_to(root).as_posix() if target != root else ".",
        "claim_boundary": "lexical comments, declared functions, direct syntactic branches and calls; no expansion, identity, cfg-target completeness, or runtime behavior",
        "tools": tools,
        "native": native,
        "inventory": inventory,
        "files": files,
        "ambiguities": ambiguities,
        "source_manifest": {
            "before_sha256": _manifest_hash(before),
            "after_sha256": _manifest_hash(after),
            "preserved": before == after,
            "changed": sorted(path for path in before.keys() & after.keys() if before[path] != after[path]),
            "missing": sorted(before.keys() - after.keys()),
            "unexpected": sorted(after.keys() - before.keys()),
        },
    }


def produce(
    project_root: Path,
    target: Path,
    *,
    cargo: str | None = None,
    rustc: str | None = None,
    rustfmt: str | None = None,
    clippy: str | None = None,
) -> tuple[dict[str, Any], int]:
    root = project_root.resolve()
    target = target if target.is_absolute() else root / target
    target = Path(os.path.abspath(target))
    if not root.is_dir() or not target.exists():
        payload = {
            "schema_version": 1, "analyzer": "rust-syntax-facts-v1",
            "status": "failed", "failure_kind": "invalid_project_or_target",
            "inventory": [], "files": [], "ambiguities": [], "native": {}, "tools": {},
            "source_manifest": {"preserved": True},
        }
        return payload, 2
    try:
        target.relative_to(root)
    except ValueError:
        payload = {
            "schema_version": 1, "analyzer": "rust-syntax-facts-v1",
            "status": "failed", "failure_kind": "unsafe_target",
            "inventory": [], "files": [], "ambiguities": [], "native": {}, "tools": {},
            "source_manifest": {"preserved": True},
        }
        return payload, 2

    before = _project_manifest(root)
    inventory, selected, ambiguities = _inventory(root, target)
    facts: list[dict[str, Any]] = []
    for row in selected:
        fact, local = _facts(row)
        facts.append(fact)
        ambiguities.extend(local)
    for row in inventory:
        if row["role"] == "configuration":
            text = (root / row["file"]).read_text(encoding="utf-8")
            if BUILD_OUTPUT_RE.search(text):
                ambiguities.append({"kind": "rust_build_output_ambiguity", "file": row["file"]})

    probes, probe_failure, probe_status = _probe_tools(
        root, {"cargo": cargo, "rustc": rustc, "rustfmt": rustfmt, "clippy": clippy}
    )
    after = _project_manifest(root)
    if probe_failure:
        return _terminal(
            status=probe_status, failure_kind=probe_failure, root=root, target=target,
            before=before, after=after, inventory=inventory, files=facts,
            ambiguities=ambiguities, tools=probes, native={},
        ), 2 if probe_status == "failed" else 0
    if not (root / "Cargo.toml").is_file():
        return _terminal(
            status="partial", failure_kind="cargo_manifest_missing", root=root, target=target,
            before=before, after=after, inventory=inventory, files=facts,
            ambiguities=ambiguities, tools=probes, native={},
        ), 0
    if not (root / "Cargo.lock").is_file():
        return _terminal(
            status="partial", failure_kind="cargo_lock_missing", root=root, target=target,
            before=before, after=after, inventory=inventory, files=facts,
            ambiguities=ambiguities, tools=probes, native={},
        ), 0
    native, native_failure, native_status = _native(root, probes, selected)
    after = _project_manifest(root)
    if before != after:
        return _terminal(
            status="failed", failure_kind="source_mutated_by_native_check", root=root, target=target,
            before=before, after=after, inventory=inventory, files=facts,
            ambiguities=ambiguities, tools=probes, native=native,
        ), 2
    if native_failure:
        return _terminal(
            status=native_status, failure_kind=native_failure, root=root, target=target,
            before=before, after=after, inventory=inventory, files=facts,
            ambiguities=ambiguities, tools=probes, native=native,
        ), 0 if native_status == "partial" else 2
    if any(row["kind"] == "rust_source_read_failed" for row in ambiguities):
        return _terminal(
            status="failed", failure_kind="rust_source_read_failed", root=root, target=target,
            before=before, after=after, inventory=inventory, files=facts,
            ambiguities=ambiguities, tools=probes, native=native,
        ), 2
    if ambiguities:
        return _terminal(
            status="partial", failure_kind=ambiguities[0]["kind"], root=root, target=target,
            before=before, after=after, inventory=inventory, files=facts,
            ambiguities=ambiguities, tools=probes, native=native,
        ), 0
    return _terminal(
        status="complete", failure_kind="none", root=root, target=target,
        before=before, after=after, inventory=inventory, files=facts,
        ambiguities=[], tools=probes, native=native,
    ), 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--cargo")
    parser.add_argument("--rustc")
    parser.add_argument("--rustfmt")
    parser.add_argument("--clippy")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload, code = produce(
        args.project_root, args.target,
        cargo=args.cargo, rustc=args.rustc, rustfmt=args.rustfmt, clippy=args.clippy,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
