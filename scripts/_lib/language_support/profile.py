#!/usr/bin/env python3
"""Load strict, versioned, stdlib-only language support profiles."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
ALLOWED_ROLES = frozenset(
    {
        "source",
        "test",
        "generated",
        "vendor",
        "build",
        "declaration",
        "configuration",
        "tooling",
        "symlink",
    }
)
ALLOWED_FACT_TIERS = frozenset(
    {"lexical-filesystem", "syntax", "semantic-project"}
)
ALLOWED_OUTCOMES = frozenset(
    {
        "complete",
        "partial",
        "unsupported",
        "tool-missing",
        "syntax-error",
        "native-check-failure",
        "unexpected-source-mutation",
    }
)
TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "language",
        "suffixes",
        "project_markers",
        "source_roles",
        "native_tools",
        "fact_tiers",
        "verification_commands",
        "terminal_outcomes",
        "explicit_limits",
    }
)
ROLE_KEYS = frozenset(
    {"supported", "test_file_globs", "declaration_file_globs", "configuration_files"}
)
TOOL_KEYS = frozenset(
    {
        "id",
        "project_paths",
        "system_commands",
        "version_argv",
        "minimum_version",
        "required",
    }
)
COMMAND_KEYS = frozenset({"id", "argv", "requires"})
SHELL_COMMANDS = frozenset({"sh", "bash", "zsh", "cmd", "powershell", "pwsh"})
UNSAFE_TOKEN = re.compile(r"[\x00\r\n;|&><]")
PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]*$")


class ProfileError(ValueError):
    """A language profile is malformed, unsafe, or conflicts with a sibling."""


@dataclass(frozen=True)
class SourceRoles:
    supported: tuple[str, ...]
    test_file_globs: tuple[str, ...]
    declaration_file_globs: tuple[str, ...]
    configuration_files: tuple[str, ...]


@dataclass(frozen=True)
class NativeTool:
    id: str
    project_paths: tuple[str, ...]
    system_commands: tuple[str, ...]
    version_argv: tuple[str, ...]
    minimum_version: str | None
    required: bool


@dataclass(frozen=True)
class VerificationCommand:
    id: str
    argv: tuple[str, ...]
    requires: tuple[str, ...]


@dataclass(frozen=True)
class LanguageProfile:
    schema_version: int
    language: str
    suffixes: tuple[str, ...]
    project_markers: tuple[str, ...]
    source_roles: SourceRoles
    native_tools: tuple[NativeTool, ...]
    fact_tiers: tuple[str, ...]
    verification_commands: tuple[VerificationCommand, ...]
    terminal_outcomes: tuple[str, ...]
    explicit_limits: tuple[str, ...]

    def as_json(self) -> dict[str, object]:
        return asdict(self)


def _object(value: Any, *, label: str, keys: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileError(f"{label} must be an object")
    unknown = set(value) - keys
    missing = keys - set(value)
    if unknown:
        raise ProfileError(f"{label} has unknown keys: {sorted(unknown)}")
    if missing:
        raise ProfileError(f"{label} is missing keys: {sorted(missing)}")
    return value


def _strings(value: Any, *, label: str, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ProfileError(f"{label} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise ProfileError(f"{label} may not be empty")
    if len(value) != len(set(value)):
        raise ProfileError(f"{label} contains a duplicate value")
    return tuple(value)


def _identifier(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ProfileError(f"{label} must be a lowercase identifier")
    return value


def _relative(value: str, *, label: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value in {"", "."} or "\\" in value:
        raise ProfileError(f"{label} must be a safe relative POSIX path")
    return value


def _argv(
    value: Any,
    *,
    label: str,
    allowed_placeholders: frozenset[str],
) -> tuple[str, ...]:
    argv = _strings(value, label=label)
    if Path(argv[0]).name.lower() in SHELL_COMMANDS:
        raise ProfileError(f"{label} may not invoke a command shell")
    for token in argv:
        if UNSAFE_TOKEN.search(token):
            raise ProfileError(f"{label} contains an unsafe token")
        placeholders = PLACEHOLDER.findall(token)
        if token.count("{") != len(placeholders) or token.count("}") != len(placeholders):
            raise ProfileError(f"{label} contains malformed placeholders")
        if any(placeholder not in allowed_placeholders for placeholder in placeholders):
            raise ProfileError(f"{label} contains an unknown placeholder")
    return argv


def _load_document(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"cannot load profile {path}: {exc}") from exc
    return _object(payload, label=f"profile {path.name}", keys=TOP_LEVEL_KEYS)


def load_profile(path: Path) -> LanguageProfile:
    """Load one profile; cross-profile suffix conflicts are checked by load_profiles."""
    payload = _load_document(path)
    if payload["schema_version"] != SCHEMA_VERSION or isinstance(payload["schema_version"], bool):
        raise ProfileError(
            f"profile {path.name} schema_version must be {SCHEMA_VERSION}"
        )
    language = _identifier(payload["language"], label="language")
    raw_suffixes = payload["suffixes"]
    if (
        isinstance(raw_suffixes, list)
        and all(isinstance(item, str) for item in raw_suffixes)
        and len(raw_suffixes) != len(set(raw_suffixes))
    ):
        raise ProfileError(f"duplicate suffix in profile {language}")
    suffixes = _strings(raw_suffixes, label="suffixes")
    for suffix in suffixes:
        if not suffix.startswith(".") or suffix != suffix.lower() or "/" in suffix:
            raise ProfileError(f"invalid suffix for {language}: {suffix}")
    markers = _strings(payload["project_markers"], label="project_markers")
    project_markers = tuple(_relative(item, label="project marker") for item in markers)

    role_payload = _object(payload["source_roles"], label="source_roles", keys=ROLE_KEYS)
    supported = _strings(role_payload["supported"], label="source_roles.supported")
    unknown_roles = set(supported) - ALLOWED_ROLES
    if unknown_roles:
        raise ProfileError(f"unknown source role: {sorted(unknown_roles)}")
    if set(supported) != ALLOWED_ROLES:
        missing = sorted(ALLOWED_ROLES - set(supported))
        raise ProfileError(f"source role vocabulary is incomplete: {missing}")
    source_roles = SourceRoles(
        supported=supported,
        test_file_globs=_strings(
            role_payload["test_file_globs"], label="source_roles.test_file_globs",
            allow_empty=True,
        ),
        declaration_file_globs=_strings(
            role_payload["declaration_file_globs"],
            label="source_roles.declaration_file_globs",
            allow_empty=True,
        ),
        configuration_files=_strings(
            role_payload["configuration_files"],
            label="source_roles.configuration_files",
            allow_empty=True,
        ),
    )

    raw_tools = payload["native_tools"]
    if not isinstance(raw_tools, list) or not raw_tools:
        raise ProfileError("native_tools must be a non-empty list")
    native_tools: list[NativeTool] = []
    for index, raw in enumerate(raw_tools):
        row = _object(raw, label=f"native tool {index}", keys=TOOL_KEYS)
        tool_id = _identifier(row["id"], label=f"native tool {index} id")
        project_paths = _strings(
            row["project_paths"], label=f"native tool {tool_id} project_paths",
            allow_empty=True,
        )
        project_paths = tuple(
            _relative(item, label=f"native tool {tool_id} project path")
            for item in project_paths
        )
        system_commands = _strings(
            row["system_commands"], label=f"native tool {tool_id} system_commands"
        )
        if any("/" in command or "\\" in command for command in system_commands):
            raise ProfileError(f"native tool {tool_id} system command must be a name")
        version_argv = _argv(
            row["version_argv"],
            label=f"native tool {tool_id} version_argv",
            allowed_placeholders=frozenset({"tool"}),
        )
        if version_argv[0] != "{tool}":
            raise ProfileError(f"native tool {tool_id} version_argv must start with {{tool}}")
        minimum = row["minimum_version"]
        if minimum is not None and (not isinstance(minimum, str) or not VERSION.fullmatch(minimum)):
            raise ProfileError(f"native tool {tool_id} minimum_version is invalid")
        if not isinstance(row["required"], bool):
            raise ProfileError(f"native tool {tool_id} required must be boolean")
        native_tools.append(
            NativeTool(
                tool_id, project_paths, system_commands, version_argv, minimum, row["required"]
            )
        )
    tool_ids = [tool.id for tool in native_tools]
    if len(tool_ids) != len(set(tool_ids)):
        raise ProfileError(f"native_tools contains a duplicate id in {language}")

    fact_tiers = _strings(payload["fact_tiers"], label="fact_tiers")
    unknown_tiers = set(fact_tiers) - ALLOWED_FACT_TIERS
    if unknown_tiers:
        raise ProfileError(f"unknown fact tier: {sorted(unknown_tiers)}")

    raw_commands = payload["verification_commands"]
    if not isinstance(raw_commands, list) or not raw_commands:
        raise ProfileError("verification_commands must be a non-empty list")
    commands: list[VerificationCommand] = []
    allowed_command_placeholders = frozenset(
        {"project_root", "source_files", *(f"tool:{tool_id}" for tool_id in tool_ids)}
    )
    for index, raw in enumerate(raw_commands):
        row = _object(raw, label=f"verification command {index}", keys=COMMAND_KEYS)
        command_id = _identifier(row["id"], label=f"verification command {index} id")
        argv = _argv(
            row["argv"],
            label=f"verification command {command_id} argv",
            allowed_placeholders=allowed_command_placeholders,
        )
        requires = _strings(
            row["requires"], label=f"verification command {command_id} requires"
        )
        if not set(requires) <= set(tool_ids):
            raise ProfileError(f"verification command {command_id} requires an unknown tool")
        commands.append(VerificationCommand(command_id, argv, requires))
    command_ids = [command.id for command in commands]
    if len(command_ids) != len(set(command_ids)):
        raise ProfileError(f"verification_commands contains a duplicate id in {language}")

    outcomes = _strings(payload["terminal_outcomes"], label="terminal_outcomes")
    unknown_outcomes = set(outcomes) - ALLOWED_OUTCOMES
    if unknown_outcomes:
        raise ProfileError(f"unknown terminal outcome: {sorted(unknown_outcomes)}")
    limits = _strings(payload["explicit_limits"], label="explicit_limits")
    return LanguageProfile(
        SCHEMA_VERSION,
        language,
        suffixes,
        project_markers,
        source_roles,
        tuple(native_tools),
        fact_tiers,
        tuple(commands),
        outcomes,
        limits,
    )


def load_profiles(root: Path) -> dict[str, LanguageProfile]:
    """Load every JSON profile under one directory and reject shared suffixes."""
    if root.is_symlink():
        raise ProfileError(f"profiles root must be a regular directory: {root}")
    profile_root = root.resolve()
    if not profile_root.is_dir():
        raise ProfileError(f"profiles root must be a regular directory: {root}")
    paths = sorted(profile_root.glob("*.json"))
    if not paths:
        raise ProfileError(f"profiles root has no JSON profiles: {root}")
    profiles: dict[str, LanguageProfile] = {}
    suffix_owners: dict[str, str] = {}
    for path in paths:
        if path.is_symlink():
            raise ProfileError(f"profile may not be a symbolic link: {path}")
        profile = load_profile(path)
        if path.stem != profile.language:
            raise ProfileError(
                f"profile filename {path.name} does not match language {profile.language}"
            )
        if profile.language in profiles:
            raise ProfileError(f"duplicate language profile: {profile.language}")
        for suffix in profile.suffixes:
            owner = suffix_owners.get(suffix)
            if owner is not None:
                raise ProfileError(f"suffix {suffix} is claimed by both {owner} and {profile.language}")
            suffix_owners[suffix] = profile.language
        profiles[profile.language] = profile
    return profiles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-root", type=Path, required=True)
    parser.add_argument("--language", required=True)
    args = parser.parse_args(argv)
    try:
        profiles = load_profiles(args.profiles_root)
        profile = profiles.get(args.language)
        if profile is None:
            raise ProfileError(f"unknown language profile: {args.language}")
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(profile.as_json(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
