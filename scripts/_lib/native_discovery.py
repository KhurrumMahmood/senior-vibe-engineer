"""Strict parsers for pinned, non-model native discovery commands."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_PUBLIC_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RIPGREP_WARNING = "Ripgrep is not available. Falling back to GrepTool."
_LIST_HEADER = "Discovered Agent Skills:"
_EMPTY_LIST = "No skills discovered."


class NativeDiscoveryParseError(ValueError):
    """A pinned runtime emitted output outside its strict parser contract."""


@dataclass(frozen=True)
class NativeSkillRow:
    """One enabled native skill name bound to its resolved project-local file."""

    name: str
    location: Path


def validate_gemini_skills_list_stderr(stderr: bytes | str) -> None:
    """Accept only the pinned runtime's optional ripgrep fallback notice."""
    text = _strict_utf8(stderr)
    if text not in {"", f"{_RIPGREP_WARNING}\n"}:
        raise NativeDiscoveryParseError("Gemini discovery stderr is malformed")


def _strict_utf8(output: bytes | str) -> str:
    if isinstance(output, str):
        return output
    try:
        return output.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise NativeDiscoveryParseError("Gemini discovery output is not strict UTF-8") from exc


def parse_gemini_skills_list(
    output: bytes | str, *, project_root: Path
) -> tuple[NativeSkillRow, ...]:
    """Parse exact Gemini 0.45.0 ``skills list`` enabled name/location blocks."""
    root = project_root.resolve()
    lines = _strict_utf8(output).splitlines()
    if lines and lines[0] == _RIPGREP_WARNING:
        lines.pop(0)
    if lines == [_EMPTY_LIST]:
        return ()
    if not lines or lines.pop(0) != _LIST_HEADER:
        raise NativeDiscoveryParseError("malformed Gemini skills-list preamble")
    if not lines or lines.pop(0) != "":
        raise NativeDiscoveryParseError("malformed Gemini skills-list header separator")
    if not any(lines):
        raise NativeDiscoveryParseError("Gemini skills list is missing skill rows")

    rows: list[NativeSkillRow] = []
    names: set[str] = set()
    locations: set[Path] = set()
    position = 0
    while position < len(lines):
        if lines[position] == "":
            position += 1
            continue
        header = lines[position]
        position += 1
        match = re.fullmatch(r"([^ ]+) \[([^]]+)\]", header)
        if match is None:
            raise NativeDiscoveryParseError("malformed Gemini skill row header")
        name, status = match.groups()
        if status != "Enabled":
            raise NativeDiscoveryParseError(f"Gemini discovery contains disabled skill: {name}")
        if _PUBLIC_NAME.fullmatch(name) is None:
            raise NativeDiscoveryParseError(f"malformed Gemini skill name: {name!r}")
        if name in names:
            raise NativeDiscoveryParseError(f"duplicate skill name in Gemini discovery: {name}")

        if position < len(lines) and lines[position].startswith("  Description: "):
            if lines[position] == "  Description: ":
                raise NativeDiscoveryParseError(f"malformed Gemini description for {name}")
            position += 1
        if position >= len(lines) or not lines[position].startswith("  Location:    "):
            raise NativeDiscoveryParseError(f"Gemini skill {name} is missing Location")
        location_text = lines[position].removeprefix("  Location:    ")
        position += 1
        if not location_text or not Path(location_text).is_absolute():
            raise NativeDiscoveryParseError(f"malformed Gemini Location for {name}")
        location = Path(location_text).resolve()
        try:
            location.relative_to(root)
        except ValueError as exc:
            raise NativeDiscoveryParseError(
                f"Gemini skill {name} Location is outside project root"
            ) from exc
        if location in locations:
            raise NativeDiscoveryParseError(
                f"duplicate skill location in Gemini discovery: {location}"
            )
        if position < len(lines) and lines[position] != "":
            raise NativeDiscoveryParseError(f"malformed Gemini skill block for {name}")
        names.add(name)
        locations.add(location)
        rows.append(NativeSkillRow(name=name, location=location))

    return tuple(rows)
