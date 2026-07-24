#!/usr/bin/env python3
"""Report read-only language toolchain capabilities for one project."""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


sys.dont_write_bytecode = True
LIBRARY_ROOT = Path(__file__).resolve().parent.parent
if str(LIBRARY_ROOT) not in sys.path:
    # Isolated execution intentionally imports only from this exact library root.
    sys.path.insert(0, str(LIBRARY_ROOT))

from scripts._lib.language_support.profile import (  # noqa: E402
    LanguageProfile,
    NativeTool,
    ProfileError,
    load_profiles,
)


SCHEMA_VERSION = 1
DEFAULT_PROFILES_ROOT = Path(__file__).resolve().parent / "language_profiles"
VERSION_TIMEOUT_SECONDS = 5.0
VERSION_TOKEN = r"\d+(?:\.\d+){1,3}"
PREFERRED_VERSION_PATTERNS = (
    re.compile(rf"\bgo\s+version\s+go({VERSION_TOKEN})", re.IGNORECASE),
    re.compile(
        rf"\b(?:version|python|javac)\s+[\"']?v?({VERSION_TOKEN})",
        re.IGNORECASE,
    ),
    re.compile(rf"^\s*v?({VERSION_TOKEN})\s*$", re.MULTILINE),
)
FALLBACK_VERSION_PATTERN = re.compile(rf"(?<![0-9])({VERSION_TOKEN})(?![0-9])")


class DoctorError(ValueError):
    """A doctor request is invalid or cannot be inspected safely."""


def _project_markers(
    profile: LanguageProfile,
    root: Path,
) -> tuple[dict[str, object], bool]:
    present: list[str] = []
    matches: dict[str, list[str]] = {}
    for marker in profile.project_markers:
        if glob.has_magic(marker):
            matches[marker] = [
                candidate.relative_to(root).as_posix()
                for candidate in sorted(root.glob(marker))
                if candidate.is_file() and not candidate.is_symlink()
            ]
        elif (root / marker).is_file() and not (root / marker).is_symlink():
            present.append(marker)
    payload: dict[str, object] = {
        "declared": list(profile.project_markers),
        "present": present,
    }
    if matches:
        payload["matches"] = matches
    return payload, bool(present or any(matches.values()))


def _project_root(path: Path) -> Path:
    try:
        root = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DoctorError(f"project root is unavailable: {path}") from exc
    if not root.is_dir():
        raise DoctorError(f"project root must be a directory: {path}")
    return root


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _resolve_executable(tool: NativeTool, project_root: Path) -> tuple[Path, str] | None:
    for relative in tool.project_paths:
        candidate = project_root / relative
        if _executable(candidate):
            return candidate.absolute(), "project-local"
    for command in tool.system_commands:
        resolved = shutil.which(command)
        if resolved is not None:
            return Path(os.path.abspath(resolved)), "system"
    return None


def _version_parts(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _version_key(version: str) -> tuple[int, int, int, int]:
    parts = (*_version_parts(version), 0, 0, 0, 0)
    return parts[:4]


def _parse_version(rendered: str, tool_id: str) -> str | None:
    match = None
    for pattern in PREFERRED_VERSION_PATTERNS:
        match = pattern.search(rendered)
        if match is not None:
            break
    if match is None:
        match = FALLBACK_VERSION_PATTERN.search(rendered)
    if match is None:
        return None
    parts = list(_version_parts(match.group(1)))
    if tool_id in {"java", "javac"} and len(parts) > 1 and parts[0] == 1:
        parts = parts[1:]
    return ".".join(str(part) for part in parts)


def _version_command(tool: NativeTool, executable: Path) -> list[str]:
    return [str(executable) if token == "{tool}" else token for token in tool.version_argv]


def _unavailable_tool(
    tool: NativeTool,
    *,
    reason: str,
    executable: Path | None = None,
    provenance: str | None = None,
    command: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": tool.id,
        "minimum_version": tool.minimum_version,
        "path": str(executable) if executable is not None else None,
        "provenance": provenance,
        "reason": reason,
        "required": tool.required,
        "status": "unavailable",
        "version": None,
        "version_command": command or [],
    }


def _inspect_tool(
    tool: NativeTool,
    project_root: Path,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    resolved = _resolve_executable(tool, project_root)
    if resolved is None:
        return _unavailable_tool(tool, reason="not-found")
    executable, provenance = resolved
    command = _version_command(tool, executable)
    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            shell=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return _unavailable_tool(
            tool,
            reason="version-command-timeout",
            executable=executable,
            provenance=provenance,
            command=command,
        )
    except OSError:
        return _unavailable_tool(
            tool,
            reason="version-command-failed",
            executable=executable,
            provenance=provenance,
            command=command,
        )
    if completed.returncode != 0:
        return _unavailable_tool(
            tool,
            reason="version-command-failed",
            executable=executable,
            provenance=provenance,
            command=command,
        )
    rendered = "\n".join(
        part for part in (completed.stdout, completed.stderr) if part
    )
    version = _parse_version(rendered, tool.id)
    if version is None:
        return _unavailable_tool(
            tool,
            reason="version-unrecognized",
            executable=executable,
            provenance=provenance,
            command=command,
        )
    too_old = (
        tool.minimum_version is not None
        and _version_key(version) < _version_key(tool.minimum_version)
    )
    return {
        "id": tool.id,
        "minimum_version": tool.minimum_version,
        "path": str(executable),
        "provenance": provenance,
        "reason": "below-minimum-version" if too_old else None,
        "required": tool.required,
        "status": "too-old" if too_old else "available",
        "version": version,
        "version_command": command,
    }


def _capability_status(
    tools: list[dict[str, object]],
    *,
    project_metadata_present: bool,
) -> tuple[str, list[str]]:
    statuses = {tool["status"] for tool in tools}
    if statuses == {"available"}:
        status, reasons = "available", []
    elif statuses == {"too-old"}:
        status, reasons = "too-old", ["toolchain-too-old"]
    elif statuses == {"unavailable"}:
        status, reasons = "unavailable", ["toolchain-unavailable"]
    else:
        status, reasons = "limited", ["partial-toolchain"]
    if not project_metadata_present:
        reasons.append("project-metadata-unavailable")
        if status == "available":
            status = "limited"
    return status, reasons


def inspect_language(
    profile: LanguageProfile,
    project_root: Path,
    *,
    timeout_seconds: float = VERSION_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Inspect one strict profile without changing the audited project."""
    root = _project_root(project_root)
    project_markers, project_metadata_present = _project_markers(profile, root)
    tools = [
        _inspect_tool(tool, root, timeout_seconds=timeout_seconds)
        for tool in profile.native_tools
    ]
    status, reasons = _capability_status(
        tools, project_metadata_present=project_metadata_present
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_schema_version": profile.schema_version,
        "language": profile.language,
        "project_root": str(root),
        "status": status,
        "status_reasons": reasons,
        "project_markers": project_markers,
        "fact_tiers": list(profile.fact_tiers),
        "tools": tools,
        "explicit_limits": list(profile.explicit_limits),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-root", type=Path, default=DEFAULT_PROFILES_ROOT)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--language", required=True)
    args = parser.parse_args(argv)
    try:
        profiles = load_profiles(args.profiles_root)
        profile = profiles.get(args.language)
        if profile is None:
            raise DoctorError(f"unknown language profile: {args.language}")
        payload = inspect_language(profile, args.project_root)
    except (DoctorError, ProfileError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
