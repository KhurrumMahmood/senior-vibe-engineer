#!/usr/bin/env python3
"""Copied C17 project/lexical facts for five read-only consumers.

The provider owns only shared C facts: source roles and hashes, a complete and
current C17 compilation-database gate, Clang syntax checks, direct lexical
declaration/function spans, Make test and executable-smoke evidence, and
source preservation.  It does not infer framework conventions, project-layout
quality, symbol identity across preprocessing variants, behavior, or semantic
equivalence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_CLANG = (21, 0, 0)
MINIMUM_MAKE = (3, 81, 0)
SOURCE_SUFFIXES = frozenset({".c", ".i"})
HEADER_SUFFIXES = frozenset({".h", ".inc"})
ALL_SUFFIXES = SOURCE_SUFFIXES | HEADER_SUFFIXES
TEST_DIRS = frozenset({"test", "tests", "testdata", "fixtures", "__tests__"})
GENERATED_DIRS = frozenset({"generated", "gen"})
BUILD_DIRS = frozenset({"build", "dist", "out", ".native-build"})
REPORT_DIRS = frozenset({"report", "reports"})
INTERNAL_DIRS = frozenset({".agents", ".claude", ".engineering", ".git"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
CONTROL_WORDS = frozenset({"if", "for", "while", "switch", "return", "sizeof", "_Alignof"})


def add_snapshot_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--clang", type=Path, default=Path("clang"))
    parser.add_argument("--make", type=Path, default=Path("make"))
    parser.add_argument("--test-target", default="test")
    parser.add_argument("--smoke", help="Project-relative executable smoke path")


def atomic_text(path: Path, text: str) -> None:
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


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def clear_artifacts(paths: Iterable[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _which(configured: Path) -> Path | None:
    if configured.is_absolute():
        return configured if configured.is_file() and os.access(configured, os.X_OK) else None
    resolved = shutil.which(str(configured))
    return Path(resolved).resolve() if resolved else None


def _probe(
    configured: Path,
    name: str,
    minimum: tuple[int, int, int],
    root: Path,
) -> dict[str, Any]:
    path = _which(configured)
    if path is None:
        return {"state": "missing", "failure_kind": f"{name}-tool-missing"}
    result = _run([str(path), "--version"], root, timeout=10)
    if result.returncode:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-failed",
            "detail": (result.stderr or result.stdout).strip(),
        }
    if name == "clang":
        match = re.search(r"(?:Apple )?clang version\s+(\d+)\.(\d+)(?:\.(\d+))?", result.stdout)
    else:
        match = re.search(r"(?:GNU Make|make)\s+(\d+)\.(\d+)(?:\.(\d+))?", result.stdout, re.I)
    if match is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-unrecognized",
            "detail": result.stdout.strip(),
        }
    version = tuple(int(part or 0) for part in match.groups())
    ready = version >= minimum
    return {
        "state": "ready" if ready else "too-old",
        "path": str(path),
        "version": ".".join(str(part or 0) for part in match.groups()),
        "minimum_version": ".".join(map(str, minimum)),
        **({"failure_kind": f"{name}-version-too-old"} if not ready else {}),
    }


def _logical_targets(root: Path, targets: Iterable[str]) -> tuple[list[Path], list[str]]:
    selected: list[Path] = []
    errors: list[str] = []
    for raw in targets:
        path = Path(raw)
        path = path if path.is_absolute() else root / path
        path = Path(os.path.abspath(path))
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"target-outside-project:{raw}")
            continue
        if not path.exists() and not path.is_symlink():
            errors.append(f"target-missing:{raw}")
            continue
        selected.append(path)
    return selected, errors


def _selected(path: Path, targets: list[Path]) -> bool:
    return any(
        path == target
        or (
            target.is_dir()
            and not target.is_symlink()
            and _inside(path, target)
        )
        for target in targets
    )


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    parents = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if "vendor" in parents:
        return "excluded", "vendor"
    if parents & REPORT_DIRS:
        return "excluded", "report"
    if parents & BUILD_DIRS:
        return "excluded", "build"
    if parents & TEST_DIRS or name.endswith(("_test.c", ".test.c")):
        return "test", "test"
    if parents & GENERATED_DIRS:
        return "excluded", "generated"
    if GENERATED_RE.search(text[:4096]):
        return "excluded", "generated-marker"
    return "candidate", None


def _inventory(root: Path, targets: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    selected, errors = _logical_targets(root, targets)
    paths: dict[str, Path] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        linked = [name for name in dirnames if (current / name).is_symlink()]
        for name in linked:
            path = current / name
            paths[path.relative_to(root).as_posix()] = path
        dirnames[:] = sorted(
            name for name in dirnames if name not in linked and name.casefold() not in INTERNAL_DIRS
        )
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink() or path.suffix.casefold() in ALL_SUFFIXES or name == "Makefile":
                paths[path.relative_to(root).as_posix()] = path

    inventory: list[dict[str, Any]] = []
    for relative, path in sorted(paths.items()):
        if path.is_symlink():
            inventory.append(
                {
                    "file": relative,
                    "role": "excluded",
                    "reason": "symlink",
                    "selected": _selected(path, selected),
                    "_path": path,
                }
            )
            continue
        try:
            source = path.read_bytes()
            text = source.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            inventory.append(
                {
                    "file": relative,
                    "role": "failed",
                    "reason": "read-error",
                    "detail": str(exc),
                    "selected": _selected(path, selected),
                    "_path": path,
                }
            )
            continue
        if path.name == "Makefile":
            role, reason = "configuration", "configuration"
        else:
            role, reason = _role(path, root, text)
        inventory.append(
            {
                "file": relative,
                "role": role,
                **({"reason": reason} if reason else {}),
                "selected": _selected(path, selected),
                "source_sha256": hash_bytes(source),
                "source_bytes": len(source),
                "_path": path,
                "_source": source,
            }
        )
    return inventory, errors


def _manifest(inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    rows = [
        {
            "file": row["file"],
            "source_sha256": row["source_sha256"],
            "source_bytes": row["source_bytes"],
        }
        for row in inventory
        if "source_sha256" in row
    ]
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["file"].encode() + b"\0" + row["source_sha256"].encode() + b"\n")
    return rows, digest.hexdigest()


def _flags(arguments: list[str], source: Path) -> list[str]:
    result: list[str] = []
    skip = False
    for token in arguments[1:]:
        if skip:
            skip = False
            continue
        if token in {"-o", "-MF", "-MT", "-MQ", "--output"}:
            skip = True
            continue
        if token in {"-c", str(source)}:
            continue
        result.append(token)
    return result


def _all_authored_sources(inventory: list[dict[str, Any]]) -> set[Path]:
    return {
        row["_path"].resolve()
        for row in inventory
        if row["role"] == "candidate" and row["_path"].suffix.casefold() in SOURCE_SUFFIXES
    }


def _is_c17_command(arguments: list[str], source: Path, clang: Path) -> bool:
    if not arguments or "-std=c17" not in arguments or "-c" not in arguments:
        return False
    if _which(Path(arguments[0])) != clang or str(source) not in arguments:
        return False
    for index, token in enumerate(arguments):
        if token.startswith("-std=") and token != "-std=c17":
            return False
        language = token[3:] if token.startswith("-x=") else None
        if token == "-x" and index + 1 < len(arguments):
            language = arguments[index + 1]
        if language and language not in {"c", "cpp-output", "c-cpp-output"}:
            return False
    return True


def _compile_database(
    root: Path,
    clang: Path,
    inventory: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[Path, list[str]], set[Path]]:
    path = root / "compile_commands.json"
    empty: dict[Path, list[str]] = {}
    if not path.is_file():
        return {"status": "missing", "failure_kind": "compile-database-missing"}, empty, set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "status": "malformed",
            "failure_kind": "compile-database-malformed",
            "detail": str(exc),
        }, empty, set()
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        return {
            "status": "malformed",
            "failure_kind": "compile-database-malformed",
            "detail": "expected a non-empty JSON array of objects",
        }, empty, set()
    commands: dict[Path, list[str]] = {}
    for row in payload:
        if set(row) != {"directory", "file", "arguments"} or not isinstance(row["arguments"], list):
            return {"status": "malformed", "failure_kind": "compile-database-malformed"}, empty, set()
        arguments = row["arguments"]
        if any(not isinstance(token, str) for token in arguments):
            return {"status": "malformed", "failure_kind": "compile-database-malformed"}, empty, set()
        directory = Path(row["directory"])
        source = Path(row["file"])
        if (
            not directory.is_absolute()
            or directory.resolve() != root
            or not source.is_absolute()
            or not _inside(source.resolve(), root)
        ):
            return {
                "status": "mismatched",
                "failure_kind": "compile-database-mismatched-directory",
            }, empty, set()
        if source.suffix.casefold() not in SOURCE_SUFFIXES or not _is_c17_command(
            arguments, source, clang
        ):
            return {
                "status": "wrong-language",
                "failure_kind": "compile-database-non-c17-command",
            }, empty, set()
        resolved_source = source.resolve()
        if resolved_source in commands:
            return {
                "status": "malformed",
                "failure_kind": "compile-database-duplicate-translation-unit",
            }, empty, set()
        commands[resolved_source] = list(arguments)
    expected = _all_authored_sources(inventory)
    if set(commands) != expected:
        return {
            "status": "incomplete",
            "failure_kind": "compile-database-incomplete",
            "expected_translation_units": sorted(path.relative_to(root).as_posix() for path in expected),
            "actual_translation_units": sorted(path.relative_to(root).as_posix() for path in commands),
        }, empty, set()

    dependencies: set[Path] = set(commands)
    dependency_rows: dict[str, list[str]] = {}
    for source, arguments in sorted(commands.items()):
        result = _run([str(clang), *_flags(arguments, source), "-MM", "-MT", "c-lexical", str(source)], root)
        if result.returncode or ":" not in result.stdout:
            return {
                "status": "failed",
                "failure_kind": "clang-dependency-failed",
                "detail": (result.stderr or result.stdout).strip(),
            }, empty, set()
        owned: list[str] = []
        for word in result.stdout.replace("\\\n", " ").partition(":")[2].split():
            dependency = Path(word)
            dependency = dependency if dependency.is_absolute() else root / dependency
            try:
                dependency = dependency.resolve()
                relative = dependency.relative_to(root)
            except (OSError, ValueError):
                continue
            if dependency.suffix.casefold() in HEADER_SUFFIXES:
                dependencies.add(dependency)
                owned.append(relative.as_posix())
        dependency_rows[source.relative_to(root).as_posix()] = sorted(set(owned))
    freshness = dependencies | {root / "Makefile"}
    existing = [item for item in freshness if item.is_file()]
    if existing and path.stat().st_mtime_ns < max(item.stat().st_mtime_ns for item in existing):
        return {
            "status": "stale",
            "failure_kind": "compile-database-stale",
            "dependencies": dependency_rows,
        }, empty, set()
    return {
        "status": "valid",
        "path": "compile_commands.json",
        "translation_units": sorted(item.relative_to(root).as_posix() for item in commands),
        "dependencies": dependency_rows,
    }, commands, dependencies


def _mask(source: bytes, *, literals: bool) -> bytes:
    output = bytearray(source)
    index = 0
    state = "code"
    while index < len(source):
        current = source[index]
        following = source[index + 1] if index + 1 < len(source) else -1
        if state == "code":
            if current == 47 and following == 47:
                output[index : index + 2] = b"  "
                index += 2
                state = "line-comment"
                continue
            if current == 47 and following == 42:
                output[index : index + 2] = b"  "
                index += 2
                state = "block-comment"
                continue
            if current in {34, 39}:
                if not literals:
                    output[index] = 32
                state = "string" if current == 34 else "character"
        elif state == "line-comment":
            if current == 10:
                state = "code"
            else:
                output[index] = 32
        elif state == "block-comment":
            if current == 42 and following == 47:
                output[index : index + 2] = b"  "
                index += 2
                state = "code"
            elif current != 10:
                output[index] = 32
        else:
            quote = 34 if state == "string" else 39
            if not literals and current != 10:
                output[index] = 32
            if current == 92 and index + 1 < len(source):
                if not literals and source[index + 1] != 10:
                    output[index + 1] = 32
                index += 1
            elif current == quote:
                state = "code"
        index += 1
    for match in re.finditer(rb"(?m)^[ \t]*#.*$", bytes(output)):
        output[match.start() : match.end()] = b" " * (match.end() - match.start())
    return bytes(output)


def _line_column(source: bytes, offset: int) -> tuple[int, int]:
    before = source[:offset]
    line = before.count(b"\n") + 1
    column = offset - before.rfind(b"\n")
    return line, column


def _span(source: bytes, start: int, end: int) -> dict[str, Any]:
    start_line, start_column = _line_column(source, start)
    end_line, end_column = _line_column(source, end)
    return {
        "start_byte": start,
        "end_byte": end,
        "start": {"line": start_line, "column": start_column},
        "end": {"line": end_line, "column": end_column},
    }


def _matching_brace(masked: bytes, opening: int) -> int | None:
    depth = 0
    for index in range(opening, len(masked)):
        if masked[index] == 123:
            depth += 1
        elif masked[index] == 125:
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def lexical_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    masked = _mask(source, literals=False)
    literal_mask = _mask(source, literals=True)
    facts: list[dict[str, Any]] = []
    function_re = re.compile(
        rb"(?m)^[ \t]*(?P<prefix>[A-Za-z_][A-Za-z0-9_ \t*]*?)[ \t]+"
        rb"(?P<name>[A-Za-z_]\w*)[ \t]*\([^;{}]*\)[ \t\r\n]*(?P<end>[{;])"
    )
    for match in function_re.finditer(masked):
        name = match.group("name").decode()
        if name in CONTROL_WORDS:
            continue
        opening = match.start("end")
        end = opening + 1 if match.group("end") == b";" else _matching_brace(masked, opening)
        if end is None:
            continue
        start = match.start()
        while start < match.end() and source[start] in b" \t\r\n":
            start += 1
        line_count = source[start:end].count(b"\n") + 1
        body = literal_mask[opening:end]
        normalized = re.sub(rb"\s+", b" ", body.strip())
        prefix = match.group("prefix").decode().strip()
        facts.append(
            {
                "symbol": name,
                "kind": "function-definition" if match.group("end") == b"{" else "function-declaration",
                "linkage": "internal-lexical" if re.search(r"\bstatic\b", prefix) else "unresolved",
                "file": row["file"],
                "span": _span(source, start, end),
                "line_count": line_count,
                "source_sha256": row["source_sha256"],
                "spelling_sha256": hash_bytes(source[start:end]),
                "normalized_body": normalized.decode("utf-8", errors="replace"),
                "normalized_body_sha256": hash_bytes(normalized),
            }
        )
    type_re = re.compile(
        rb"(?ms)^[ \t]*typedef[ \t]+(?P<kind>struct|enum)[ \t]+(?:[A-Za-z_]\w*)?"
        rb"[ \t\r\n]*\{.*?\}[ \t]*(?P<name>[A-Za-z_]\w*)[ \t]*;"
    )
    for match in type_re.finditer(masked):
        start, end = match.span()
        while start < end and source[start] in b" \t\r\n":
            start += 1
        facts.append(
            {
                "symbol": match.group("name").decode(),
                "kind": f"typedef-{match.group('kind').decode()}",
                "linkage": "not-applicable",
                "file": row["file"],
                "span": _span(source, start, end),
                "line_count": source[start:end].count(b"\n") + 1,
                "source_sha256": row["source_sha256"],
                "spelling_sha256": hash_bytes(source[start:end]),
            }
        )
    return sorted(facts, key=lambda fact: (fact["span"]["start_byte"], fact["symbol"]))


def function_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [fact for fact in lexical_facts(row) if fact["kind"] == "function-definition"]


def public_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (
            [{k: v for k, v in row.items() if not k.startswith("_")} for row in value]
            if key == "inventory"
            else value
        )
        for key, value in snapshot.items()
        if not key.startswith("_")
    }


def sources_preserved(snapshot: dict[str, Any]) -> bool:
    for row in snapshot["inventory"]:
        path = row.get("_path")
        if row.get("source_sha256") and isinstance(path, Path):
            try:
                if hash_bytes(path.read_bytes()) != row["source_sha256"]:
                    return False
            except OSError:
                return False
    return True


def terminal_return_code(snapshot: dict[str, Any]) -> int:
    return 1 if snapshot["status"] == "failed" else 2 if snapshot["status"] == "partial" else 0


def _safe_project_file(root: Path, raw: str) -> Path | None:
    path = Path(raw)
    path = path if path.is_absolute() else root / path
    path = Path(os.path.abspath(path))
    if not _inside(path, root) or not path.is_file() or path.is_symlink():
        return None
    current = path.parent
    while current != root:
        if current.is_symlink():
            return None
        current = current.parent
    return path


def collect_snapshot(
    project_root: Path,
    targets: Iterable[str],
    *,
    clang: Path,
    make: Path,
    test_target: str,
    smoke: str | None,
) -> dict[str, Any]:
    """Collect one immutable, project-aware C17 lexical snapshot."""
    root = project_root.resolve()
    inventory, errors = _inventory(root, targets)
    manifest, manifest_hash = _manifest(inventory)
    tools = {
        "clang": _probe(clang, "clang", MINIMUM_CLANG, root),
        "make": _probe(make, "make", MINIMUM_MAKE, root),
    }
    snapshot: dict[str, Any] = {
        "language": "c",
        "analyzer": "c17-compile-db+clang-syntax+direct-lexical-v1",
        "status": "complete",
        "inventory": inventory,
        "errors": errors,
        "tools": tools,
        "source_manifest": manifest,
        "source_manifest_sha256": manifest_hash,
        "source_preserved": True,
        "limits": [
            "direct source spelling is not macro-expanded symbol identity or runtime behavior",
            "inactive preprocessor branches and arbitrary build variants are unresolved",
            "function pointers, callbacks, aliasing, linkage across variants, and dynamic loading are unresolved",
            "exact normalized body spelling is not semantic or behavioral equivalence",
            "filename clusters do not endorse a framework, project layout, ownership boundary, or safe move",
            "C++, Objective-C, CUDA, OpenCL, assembly, ABI, and object layout are excluded",
        ],
    }
    bad = [tool for tool in tools.values() if tool["state"] != "ready"]
    if bad:
        first = bad[0]
        snapshot.update(
            status="failed" if first["state"] == "failed" else "partial",
            failure_kind=first["failure_kind"],
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": len(bad)},
        )
        return snapshot
    if not (root / "Makefile").is_file():
        snapshot.update(status="partial", failure_kind="c-project-metadata-missing")
        snapshot["summary"] = {"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1}
        return snapshot

    compile_database, commands, dependencies = _compile_database(
        root, Path(tools["clang"]["path"]), inventory
    )
    snapshot["compile_database"] = compile_database
    if compile_database["status"] != "valid":
        failed = compile_database["status"] in {"malformed", "failed"}
        snapshot.update(
            status="failed" if failed else "partial",
            failure_kind=compile_database["failure_kind"],
        )
        snapshot["summary"] = {"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1}
        return snapshot

    for row in inventory:
        path = row.get("_path")
        if row["role"] != "candidate" or not isinstance(path, Path):
            continue
        resolved = path.resolve()
        if resolved in dependencies:
            row["role"] = "eligible"
            row["compiler_owned"] = True
        elif path.suffix.casefold() in HEADER_SUFFIXES:
            row.update(role="excluded", reason="ambiguous-header", compiler_owned=False)

    syntax_checks = []
    for source, arguments in sorted(commands.items()):
        result = _run(
            [str(tools["clang"]["path"]), *_flags(arguments, source), "-fsyntax-only", str(source)],
            root,
        )
        syntax_checks.append({"file": source.relative_to(root).as_posix(), "returncode": result.returncode})
        if result.returncode:
            row = next(item for item in inventory if item.get("_path") == source)
            row.update(role="failed", reason="syntax-error", detail=(result.stderr or result.stdout).strip())
            errors.append(f"{row['file']}:syntax-error")
    snapshot["syntax_checks"] = syntax_checks

    selected_rows = [row for row in inventory if row["role"] == "eligible" and row["selected"]]
    native: dict[str, Any] = {}
    make_result = _run(
        [str(tools["make"]["path"]), test_target, f"CC={tools['clang']['path']}"],
        root,
        env={
            **os.environ,
            "ALL_PROXY": "http://127.0.0.1:9",
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
        },
        timeout=120,
    )
    native["test"] = {
        "status": "passed" if make_result.returncode == 0 else "failed",
        "target": test_target,
        "returncode": make_result.returncode,
        "stdout": make_result.stdout[:4000],
        "stderr": make_result.stderr[:4000],
    }
    if make_result.returncode:
        snapshot.update(status="failed", failure_kind="native-test-failed")
    if not smoke:
        native["smoke"] = {"status": "not-run", "path": None}
        if snapshot["status"] != "failed":
            snapshot.update(status="partial", failure_kind="native-smoke-missing")
    else:
        smoke_path = _safe_project_file(root, smoke)
        if smoke_path is None:
            native["smoke"] = {"status": "failed", "path": smoke, "returncode": 2}
            snapshot.update(status="failed", failure_kind="native-smoke-unsafe")
        elif make_result.returncode:
            native["smoke"] = {"status": "not-run", "path": smoke}
        else:
            smoke_result = _run([str(smoke_path)], root, timeout=30)
            native["smoke"] = {
                "status": "passed" if smoke_result.returncode == 0 else "failed",
                "path": smoke_path.relative_to(root).as_posix(),
                "returncode": smoke_result.returncode,
                "stdout": smoke_result.stdout[:4000],
                "stderr": smoke_result.stderr[:4000],
            }
            if smoke_result.returncode:
                snapshot.update(status="failed", failure_kind="native-smoke-failed")
    snapshot["native"] = native

    failed_rows = sum(row["role"] == "failed" for row in inventory)
    target_errors = sum(error.startswith("target-") for error in errors)
    if snapshot["status"] != "failed":
        if failed_rows or target_errors:
            snapshot.update(status="partial", failure_kind="c-source-incomplete")
        elif not selected_rows:
            snapshot.update(status="partial", failure_kind="no-eligible-c-files")
    snapshot["errors"] = errors
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    snapshot["summary"] = {
        "discovered": len(inventory),
        "eligible": sum(row["role"] == "eligible" for row in inventory),
        "excluded": sum(row["role"] in {"excluded", "test", "configuration"} for row in inventory),
        "failed": failed_rows + target_errors,
    }
    return snapshot
