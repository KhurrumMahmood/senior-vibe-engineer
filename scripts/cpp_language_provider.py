#!/usr/bin/env python3
"""Provide bounded C++ suffix and compile-database facts for the P7 spine."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CPP_SOURCE_SUFFIXES = frozenset({".cc", ".cpp", ".cxx", ".c++", ".C", ".ii"})
CPP_DECLARATION_SUFFIXES = frozenset(
    {".hpp", ".hh", ".hxx", ".h++", ".ipp", ".inl", ".tpp"}
)
AMBIGUOUS_HEADER_SUFFIXES = frozenset({".h", ".inc"})
CPP_DRIVERS = frozenset({"c++", "clang++", "g++"})
CPP_STANDARD = "-std=c++20"


@dataclass(frozen=True)
class CompileDatabaseResult:
    """A fail-closed validation state plus trusted entries when valid."""

    state: str
    entries: tuple[dict[str, Any], ...] = ()


def cpp_suffix_role(path: Path) -> str | None:
    """Classify an exact-case C++ suffix without borrowing C-family suffixes."""
    if path.suffix in CPP_SOURCE_SUFFIXES:
        return "source"
    if path.suffix in CPP_DECLARATION_SUFFIXES:
        return "declaration"
    if path.suffix in AMBIGUOUS_HEADER_SUFFIXES:
        return "ambiguous-header"
    return None


def _mode(arguments: list[str]) -> str | None:
    explicit_modes: list[str] = []
    for index, token in enumerate(arguments):
        if token == "-x" and index + 1 < len(arguments):
            explicit_modes.append(arguments[index + 1])
        elif token.startswith("-x") and token != "-x":
            explicit_modes.append(token[2:])
    if explicit_modes:
        return explicit_modes[-1]
    return None


def _is_cpp_command(arguments: list[str]) -> bool:
    if not arguments:
        return False
    mode = _mode(arguments)
    if mode is not None:
        return mode in {"c++", "c++-cpp-output"}
    return Path(arguments[0]).name in CPP_DRIVERS


def _effective_standard(arguments: list[str]) -> str | None:
    standards = [token for token in arguments if token.startswith("-std=")]
    return standards[-1] if standards else None


def validate_cpp_compile_database(
    project_root: Path,
    *,
    expected_sources: Iterable[Path],
    freshness_inputs: Iterable[Path],
) -> CompileDatabaseResult:
    """Validate a current, complete C++20 arguments database for one build."""
    root = project_root.resolve()
    database = root / "compile_commands.json"
    if not database.is_file():
        return CompileDatabaseResult("missing")
    try:
        payload = json.loads(database.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return CompileDatabaseResult("malformed")
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        return CompileDatabaseResult("malformed")

    expected = {path.resolve() for path in expected_sources}
    actual: set[Path] = set()
    trusted: list[dict[str, Any]] = []
    for row in payload:
        if set(row) != {"directory", "file", "arguments"}:
            return CompileDatabaseResult("malformed")
        if Path(str(row["directory"])) != root:
            return CompileDatabaseResult("mismatched-directory")
        file_path = Path(str(row["file"]))
        arguments = row["arguments"]
        if (
            not file_path.is_absolute()
            or not isinstance(arguments, list)
            or any(not isinstance(token, str) or not token for token in arguments)
        ):
            return CompileDatabaseResult("malformed")
        if cpp_suffix_role(file_path) != "source":
            return CompileDatabaseResult("wrong-language")
        if (
            _effective_standard(arguments) != CPP_STANDARD
            or "-c" not in arguments
            or not _is_cpp_command(arguments)
        ):
            return CompileDatabaseResult("wrong-mode")
        if str(file_path) not in arguments:
            return CompileDatabaseResult("malformed")
        actual.add(file_path.resolve())
        trusted.append(row)
    if actual != expected:
        return CompileDatabaseResult("incomplete")
    try:
        newest_input = max(path.stat().st_mtime_ns for path in freshness_inputs)
    except (OSError, ValueError):
        return CompileDatabaseResult("malformed")
    if database.stat().st_mtime_ns < newest_input:
        return CompileDatabaseResult("stale")
    return CompileDatabaseResult("valid", tuple(trusted))
