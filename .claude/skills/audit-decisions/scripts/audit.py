#!/usr/bin/env python3
"""Portable decision-registry drift audit.

The selected skill cannot depend on the toolkit's ``scripts/decisions.py``:
stock Codex installs copy only this directory.  This deliberately small,
stdlib-only executor preserves the audit's read-only registry/link checks and
adds comment-aware TypeScript/TSX decision references without claiming any
TypeScript semantic or framework knowledge.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ADR_NAME = re.compile(r"^(?P<id>\d{4})-(?P<slug>[a-z][a-z0-9_-]*)\.md$")
REFERENCE = re.compile(r"\bdecision:(\d{4})\b")
MARKDOWN_REFERENCE = re.compile(r"#\s*decision:(\d{4})\b")
VALID_STATUSES = {"proposed", "accepted", "superseded", "deprecated"}
EMBODIMENT_KINDS = {"skill", "lint", "script", "hook", "doctrine", "contract", "pending"}
EXCLUDED_DIRS = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "bower_components", "vendor", "third_party", "third-party", "deps",
    "dependencies", "dist", "build", "out", "coverage", "reports",
    "generated", "__generated__", "test", "tests", "__tests__", "spec",
    "specs", "fixture", "fixtures", ".next", ".cache", "site-packages",
})
SCANNED_SUFFIXES = {".py", ".md", ".html", ".htm", ".ts", ".tsx"}


@dataclass(frozen=True)
class Decision:
    id: str
    slug: str
    title: str
    status: str
    date: str
    supersedes: list[str]
    superseded_by: str | None
    applies_to: list[str]
    embodied_by: list[str]
    tags: list[str]
    frontmatter: dict[str, Any]
    path: Path


def _remove_yaml_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.rstrip()


def _split_inline_list(value: str) -> list[str]:
    items: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    depth = 0
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char in "[{(":
            depth += 1
        elif char in "]})":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(value[start:index])
            start = index + 1
    items.append(value[start:])
    return [item.strip() for item in items if item.strip()]


def _parse_scalar(raw: str) -> Any:
    value = _remove_yaml_comment(raw.strip())
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        return [_parse_scalar(item) for item in _split_inline_list(value[1:-1])]
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    return value


def _frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.replace("\r\n", "\n").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing YAML frontmatter")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError(f"{path}: unclosed YAML frontmatter") from exc

    metadata: dict[str, Any] = {}
    active_list: str | None = None
    key_pattern = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]*(?P<value>.*))?$")
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        if stripped.startswith("- "):
            if active_list is None:
                raise ValueError(f"{path}: list item without a key")
            current = metadata.setdefault(active_list, [])
            if not isinstance(current, list):
                raise ValueError(f"{path}: mixed scalar/list value for {active_list}")
            current.append(_parse_scalar(stripped[2:]))
            continue
        match = key_pattern.match(line)
        if not match:
            raise ValueError(f"{path}: unsupported frontmatter line {line!r}")
        key = match.group("key")
        raw_value = match.group("value") or ""
        if not raw_value.strip():
            metadata[key] = []
            active_list = key
        else:
            metadata[key] = _parse_scalar(raw_value)
            active_list = None
    return metadata


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def load_decisions(decisions_dir: Path) -> list[Decision]:
    if not decisions_dir.is_dir():
        raise ValueError(f"decision directory does not exist: {decisions_dir}")
    decisions: list[Decision] = []
    for path in sorted(decisions_dir.glob("*.md")):
        match = ADR_NAME.match(path.name)
        if not match:
            continue
        fm = _frontmatter(path)
        decisions.append(Decision(
            id=match.group("id"),
            slug=match.group("slug"),
            title=str(fm.get("title") or ""),
            status=str(fm.get("status") or "proposed"),
            date=str(fm.get("date") or ""),
            supersedes=[str(value).zfill(4) for value in _as_list(fm.get("supersedes"))],
            superseded_by=(str(fm["superseded_by"]).zfill(4) if fm.get("superseded_by") else None),
            applies_to=_as_list(fm.get("applies_to")),
            embodied_by=_as_list(fm.get("embodied_by")),
            tags=_as_list(fm.get("tags")),
            frontmatter=fm,
            path=path,
        ))
    return decisions


def _relative(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root).as_posix()


def _is_excluded(path: Path, project_root: Path) -> bool:
    """Apply source policy to a project-relative path, never to a target root."""
    try:
        rel = path.resolve().relative_to(project_root)
    except ValueError:
        return True
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return True
    name = path.name.lower()
    return (
        name.startswith("test_")
        or name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".d.ts"))
        or ".min." in name
    )


def _resolve_target(raw: str, project_root: Path) -> Path:
    candidate = Path(raw)
    target = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"target is outside project root: {raw}") from exc
    if not target.exists():
        raise ValueError(f"target does not exist: {raw}")
    return target


def iter_scannable_files(project_root: Path, targets: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for target in targets:
        if _is_excluded(target, project_root):
            continue
        if target.is_file():
            if target.suffix.lower() in SCANNED_SUFFIXES:
                found.add(target)
            continue
        for path in sorted(target.rglob("*")):
            if path.is_file() and path.suffix.lower() in SCANNED_SUFFIXES and not _is_excluded(path, project_root):
                found.add(path)
    return sorted(found, key=lambda path: _relative(path, project_root))


class TypeScriptCommentScanner:
    """Small lexical scanner for TS comments, strings, templates, regexes, and JSX text."""

    def __init__(self, text: str, *, tsx: bool) -> None:
        self.text = text
        self.tsx = tsx
        self.references: list[tuple[int, str, str]] = []

    def scan(self) -> list[tuple[int, str, str]]:
        self._scan_code(0, stop_on_brace=False)
        return self.references

    def _record_comment(self, start: int, end: int, form: str) -> None:
        for match in REFERENCE.finditer(self.text[start:end]):
            self.references.append((start + match.start(), match.group(1), form))

    def _skip_quoted(self, index: int, quote: str) -> int:
        index += 1
        while index < len(self.text):
            if self.text[index] == "\\":
                index += 2
            elif self.text[index] == quote:
                return index + 1
            else:
                index += 1
        return index

    def _scan_template(self, index: int) -> int:
        index += 1
        while index < len(self.text):
            char = self.text[index]
            if char == "\\":
                index += 2
            elif char == "`":
                return index + 1
            elif char == "$" and index + 1 < len(self.text) and self.text[index + 1] == "{":
                index = self._scan_code(index + 2, stop_on_brace=True)
            else:
                index += 1
        return index

    def _can_start_regex(self, index: int) -> bool:
        previous = index - 1
        while previous >= 0 and self.text[previous].isspace():
            previous -= 1
        if previous < 0 or self.text[previous] in "=([{,:;!?&|^~<>+-*%":
            return True
        word_end = previous + 1
        while previous >= 0 and (self.text[previous].isalnum() or self.text[previous] in "_$"):
            previous -= 1
        word = self.text[previous + 1:word_end]
        if previous >= 0 and self.text[previous] == ".":
            return False
        return word in {
            "await", "case", "delete", "do", "else", "in", "instanceof",
            "new", "return", "throw", "typeof", "void", "yield",
        }

    def _skip_regex(self, index: int) -> int:
        index += 1
        in_class = False
        while index < len(self.text):
            char = self.text[index]
            if char == "\\":
                index += 2
            elif char == "[":
                in_class = True
                index += 1
            elif char == "]":
                in_class = False
                index += 1
            elif char == "/" and not in_class:
                index += 1
                while index < len(self.text) and self.text[index].isalpha():
                    index += 1
                return index
            elif char in "\r\n":
                return index
            else:
                index += 1
        return index

    def _jsx_can_start(self, index: int) -> bool:
        if not self.tsx or index + 1 >= len(self.text):
            return False
        is_fragment = self.text[index + 1] == ">"
        if not is_fragment and not self.text[index + 1].isalpha():
            return False
        previous = index - 1
        while previous >= 0 and self.text[previous].isspace():
            previous -= 1
        if previous >= 0 and self.text[previous] not in "=([{,:;!?":
            word_end = previous + 1
            while previous >= 0 and (self.text[previous].isalnum() or self.text[previous] in "_$"):
                previous -= 1
            if self.text[previous + 1:word_end] != "return":
                return False
        if is_fragment:
            return True

        name_end = index + 1
        while name_end < len(self.text) and (self.text[name_end].isalnum() or self.text[name_end] in "_$-."):
            name_end += 1
        cursor = name_end
        tag_tokens: list[str] = []
        while cursor < len(self.text):
            char = self.text[cursor]
            if char in {"'", '"'}:
                cursor = self._skip_quoted(cursor, char)
            elif char == "{":
                cursor = self._skip_balanced_braces(cursor + 1)
            elif char == ">":
                break
            else:
                tag_tokens.append(char)
                cursor += 1
        if cursor >= len(self.text):
            return False

        probe = "".join(tag_tokens)
        if "," in probe or re.search(r"\bextends\b", probe):
            return False
        after = cursor + 1
        while after < len(self.text) and self.text[after].isspace():
            after += 1
        return not (not probe.strip() and after < len(self.text) and self.text[after] == "(")

    def _skip_balanced_braces(self, index: int) -> int:
        depth = 1
        while index < len(self.text) and depth:
            char = self.text[index]
            if char in {"'", '"'}:
                index = self._skip_quoted(index, char)
            elif char == "`":
                index = self._skip_template_literal(index)
            elif char == "{":
                depth += 1
                index += 1
            elif char == "}":
                depth -= 1
                index += 1
            else:
                index += 1
        return index

    def _skip_template_literal(self, index: int) -> int:
        index += 1
        while index < len(self.text):
            if self.text[index] == "\\":
                index += 2
            elif self.text[index] == "`":
                return index + 1
            else:
                index += 1
        return index

    def _skip_jsx_tag(self, index: int) -> tuple[int, bool, bool]:
        """Return (after tag, is_closing, is_self_closing)."""
        closing = self.text.startswith("</", index)
        index += 2 if closing else 1
        while index < len(self.text):
            char = self.text[index]
            if char in {"'", '"'}:
                index = self._skip_quoted(index, char)
            elif char == "{":
                index = self._scan_code(index + 1, stop_on_brace=True)
            elif char == ">":
                back = index - 1
                while back >= 0 and self.text[back].isspace():
                    back -= 1
                return index + 1, closing, self.text[back] == "/"
            else:
                index += 1
        return index, closing, False

    def _scan_jsx_element(self, index: int) -> int:
        index, closing, self_closing = self._skip_jsx_tag(index)
        if closing or self_closing:
            return index
        while index < len(self.text):
            if self.text[index] == "{":
                index = self._scan_code(index + 1, stop_on_brace=True)
            elif self.text[index] == "<" and index + 1 < len(self.text):
                if self.text.startswith("</", index):
                    return self._skip_jsx_tag(index)[0]
                if self.text[index + 1].isalpha() or self.text[index + 1] == ">":
                    index = self._scan_jsx_element(index)
                else:
                    index += 1
            else:
                index += 1
        return index

    def _scan_code(self, index: int, *, stop_on_brace: bool) -> int:
        while index < len(self.text):
            char = self.text[index]
            if stop_on_brace and char == "}":
                return index + 1
            if char in {"'", '"'}:
                index = self._skip_quoted(index, char)
            elif char == "`":
                index = self._scan_template(index)
            elif char == "{":
                index = self._scan_code(index + 1, stop_on_brace=True)
            elif char == "/" and index + 1 < len(self.text) and self.text[index + 1] == "/":
                end = self.text.find("\n", index)
                end = len(self.text) if end < 0 else end
                self._record_comment(index, end, "line")
                index = end
            elif char == "/" and index + 1 < len(self.text) and self.text[index + 1] == "*":
                end = self.text.find("*/", index + 2)
                end = len(self.text) if end < 0 else end + 2
                self._record_comment(index, end, "jsdoc" if self.text.startswith("/**", index) else "block")
                index = end
            elif char == "/" and self._can_start_regex(index):
                index = self._skip_regex(index)
            elif char == "<" and self._jsx_can_start(index):
                index = self._scan_jsx_element(index)
            else:
                index += 1
        return index


def _reference_dict(path: Path, project_root: Path, line: int, identifier: str, language: str, comment_form: str) -> dict[str, Any]:
    return {
        "path": _relative(path, project_root),
        "line": line,
        "id": identifier,
        "language": language,
        "comment_form": comment_form,
    }


def scan_references(path: Path, project_root: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    suffix = path.suffix.lower()
    references: list[dict[str, Any]] = []
    if suffix == ".py":
        try:
            for token in tokenize.generate_tokens(io.StringIO(text).readline):
                if token.type != tokenize.COMMENT:
                    continue
                for match in REFERENCE.finditer(token.string):
                    references.append(_reference_dict(path, project_root, token.start[0], match.group(1), "python", "line"))
        except (tokenize.TokenError, IndentationError):
            return []
    elif suffix in {".ts", ".tsx"}:
        for offset, identifier, form in TypeScriptCommentScanner(text, tsx=suffix == ".tsx").scan():
            references.append(_reference_dict(path, project_root, text.count("\n", 0, offset) + 1, identifier, "typescript", form))
    elif suffix == ".md":
        for match in MARKDOWN_REFERENCE.finditer(text):
            references.append(_reference_dict(path, project_root, text.count("\n", 0, match.start()) + 1, match.group(1), "markdown", "hash"))
    else:
        for match in MARKDOWN_REFERENCE.finditer(text):
            before = text.rfind("<!--", 0, match.start())
            after = text.find("-->", match.start())
            form = "html-comment" if before >= 0 and after >= 0 else "hash"
            references.append(_reference_dict(path, project_root, text.count("\n", 0, match.start()) + 1, match.group(1), "html", form))
    return references


def registry_audit(decisions: list[Decision]) -> list[str]:
    diagnostics: list[str] = []
    today = dt.date.today()
    by_id = {decision.id: decision for decision in decisions}
    identifiers = [decision.id for decision in decisions]
    duplicates = sorted({identifier for identifier in identifiers if identifiers.count(identifier) > 1})
    diagnostics.extend(f"duplicate id {identifier}" for identifier in duplicates)
    for decision in decisions:
        if decision.status not in VALID_STATUSES:
            diagnostics.append(f"{decision.id}: invalid status {decision.status!r} (allowed: {sorted(VALID_STATUSES)})")
        if decision.status == "proposed" and decision.date and not (decision.frontmatter.get("revisit_when") or decision.frontmatter.get("provenance")):
            try:
                age = (today - dt.date.fromisoformat(decision.date)).days
            except ValueError:
                diagnostics.append(f"{decision.id}: malformed date {decision.date!r}")
            else:
                if age > 30:
                    diagnostics.append(
                        f"{decision.id}: proposed for {age} days (>30) — accept, reject, "
                        "or add a revisit_when trigger"
                    )
        if decision.status == "accepted" and not decision.embodied_by:
            diagnostics.append(
                f"{decision.id}: accepted but embodied_by is empty — name the skill/lint/"
                "script that realizes it, doctrine:<path> if prose-only is deliberate, "
                "or pending:<ref> if the build is tracked elsewhere (ADR 0033)"
            )
        for target in decision.supersedes:
            if target not in by_id:
                diagnostics.append(f"{decision.id}: supersedes {target} which does not exist")
        if decision.superseded_by and decision.superseded_by not in by_id:
            diagnostics.append(f"{decision.id}: superseded_by {decision.superseded_by} which does not exist")
    return diagnostics


def link_check(decisions: list[Decision], project_root: Path) -> tuple[list[str], list[str]]:
    diagnostics: list[str] = []
    advisory: list[str] = []
    by_id = {decision.id: decision for decision in decisions}
    for decision in decisions:
        for target in decision.supersedes:
            if target not in by_id:
                diagnostics.append(f"{decision.id}: supersedes {target} -> not found")
        if decision.superseded_by and decision.superseded_by not in by_id:
            diagnostics.append(f"{decision.id}: superseded_by {decision.superseded_by} -> not found")
        for applies_to in decision.applies_to:
            host_path = applies_to.startswith("host:")
            candidate = applies_to.removeprefix("host:")
            matches = list(project_root.glob(candidate)) if any(char in candidate for char in "*?[") else [project_root / candidate]
            if any(path.exists() for path in matches):
                continue
            if host_path:
                advisory.append(
                    f"{decision.id}: applies_to {applies_to} → host path, resolves "
                    "in the importing project (advisory)"
                )
            else:
                diagnostics.append(f"{decision.id}: applies_to {applies_to} → path does not exist")
        for entry in decision.embodied_by:
            kind, separator, ref = entry.partition(":")
            if not separator or kind not in EMBODIMENT_KINDS or not ref:
                diagnostics.append(
                    f"{decision.id}: embodied_by {entry!r} → must be <kind>:<ref> with kind "
                    f"in {sorted(EMBODIMENT_KINDS)}"
                )
                continue
            if kind == "pending":
                advisory.append(f"{decision.id}: embodied_by pending:{ref} → decided-but-unbuilt (advisory backlog)")
            elif kind == "hook":
                advisory.append(f"{decision.id}: embodied_by hook:{ref} → hook, resolves in harness settings (advisory)")
            else:
                target = {
                    "skill": Path(".claude/skills") / ref / "SKILL.md",
                    "lint": Path("scripts/lint") / f"{ref}.py",
                }.get(kind, Path(ref.partition("#")[0]))
                if not (project_root / target).exists():
                    diagnostics.append(f"{decision.id}: embodied_by {entry} → {target} does not exist")
    return diagnostics, advisory


def _row(symptom: str, severity: str, adr_id: str | None, evidence: dict[str, Any], resolution: str) -> dict[str, Any]:
    return {
        "symptom": symptom,
        "severity": severity,
        "adr_id": adr_id,
        "evidence": evidence,
        "resolution_command": resolution,
    }


def _applies_missing(decision: Decision, project_root: Path) -> list[str]:
    missing: list[str] = []
    for raw in decision.applies_to:
        if raw.startswith("host:"):
            continue
        matches = list(project_root.glob(raw)) if any(char in raw for char in "*?[") else [project_root / raw]
        if not any(path.exists() for path in matches):
            missing.append(raw)
    return missing


def make_drift(decisions: list[Decision], project_root: Path, references: list[dict[str, Any]], *, full_reference_scope: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_id = {decision.id: decision for decision in decisions}
    for diagnostic in registry_audit(decisions):
        if "supersedes" in diagnostic or "superseded_by" in diagnostic or "proposed for" in diagnostic:
            continue
        identifier = diagnostic[:4] if diagnostic[:4].isdigit() else None
        rows.append(_row("registry-audit", "P0", identifier, {"diagnostic": diagnostic}, "/decide --amend " + identifier if identifier else "/decide"))
    for reference in references:
        if reference["id"] in by_id:
            continue
        severity = "P1" if reference["language"] in {"markdown", "html"} else "P0"
        rows.append(_row(
            "code-ref-orphan", severity, reference["id"],
            {key: reference[key] for key in ("path", "line", "language", "comment_form")},
            f"/decide {reference['id']} or remove the reference",
        ))
    for decision in decisions:
        for target in decision.supersedes:
            other = by_id.get(target)
            if other is None or other.superseded_by != decision.id:
                rows.append(_row(
                    "broken-supersession", "P0", decision.id,
                    {"relation": "supersedes", "target": target}, f"/decide --amend {decision.id}",
                ))
        if decision.superseded_by:
            other = by_id.get(decision.superseded_by)
            if other is None or decision.id not in other.supersedes:
                rows.append(_row(
                    "broken-supersession", "P0", decision.id,
                    {"relation": "superseded_by", "target": decision.superseded_by}, f"/decide --amend {decision.superseded_by}",
                ))
        if decision.status == "proposed":
            try:
                days_old = (dt.date.today() - dt.date.fromisoformat(decision.date)).days
            except ValueError:
                days_old = 0
            if days_old > 30 and not (decision.frontmatter.get("revisit_when") or decision.frontmatter.get("provenance")):
                rows.append(_row(
                    "proposed-too-long", "P0" if days_old > 90 else "P1", decision.id,
                    {"date": decision.date, "days_old": days_old}, f"/decide --amend {decision.id}",
                ))
        missing = _applies_missing(decision, project_root)
        if missing:
            severity = "P0" if len(missing) == len([path for path in decision.applies_to if not path.startswith("host:")]) else "P1"
            rows.append(_row(
                "applies-to-missing", severity, decision.id,
                {"paths": missing}, f"/decide --amend {decision.id}",
            ))
    if full_reference_scope:
        referenced = {reference["id"] for reference in references if reference["id"] in by_id}
        for decision in decisions:
            try:
                days_old = (dt.date.today() - dt.date.fromisoformat(decision.date)).days
            except ValueError:
                continue
            if decision.status == "accepted" and days_old > 60 and decision.id not in referenced:
                severity = "P1" if {"lint", "enforced"} & set(decision.tags) else "P2"
                rows.append(_row(
                    "unreferenced-decision", severity, decision.id,
                    {"title": decision.title, "days_old": days_old}, "review whether the decision remains load-bearing",
                ))
    return sorted(rows, key=lambda row: (row["severity"], row["symptom"], row.get("adr_id") or "", json.dumps(row["evidence"], sort_keys=True)))


def render_drift(scan_id: str, decisions: list[Decision], references: list[dict[str, Any]], rows: list[dict[str, Any]]) -> str:
    counts = {severity: sum(row["severity"] == severity for row in rows) for severity in ("P0", "P1", "P2")}
    summary = {symptom: sum(row["symptom"] == symptom for row in rows) for symptom in (
        "broken-supersession", "code-ref-orphan", "applies-to-missing", "proposed-too-long", "unreferenced-decision",
    )}
    ts_count = sum(reference["language"] == "typescript" for reference in references)
    lines = [
        f"# Decision-registry drift — {scan_id}",
        "",
        f"_{len(decisions)} ADRs scanned. {len(rows)} drift rows surfaced._",
        "",
        "## Summary",
        "| Symptom | Count | Severity |",
        "|---|---:|---|",
    ]
    defaults = {
        "broken-supersession": "P0", "code-ref-orphan": "P0", "applies-to-missing": "P1",
        "proposed-too-long": "P1", "unreferenced-decision": "P2",
    }
    lines.extend(f"| {symptom} | {summary[symptom]} | {defaults[symptom]} |" for symptom in defaults)
    lines.extend([
        "",
        "## Reference inventory",
        "",
        f"TS/TSX comment references: {ts_count} total. Resolved references are retained here even when they create no drift row.",
    ])
    if references:
        for reference in references:
            resolution = "resolved" if reference["resolved"] else "orphan"
            lines.append(f"- `{resolution}` — `{reference['path']}:{reference['line']}` `decision:{reference['id']}` ({reference['language']}, {reference['comment_form']})")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Drift rows", ""])
    for severity, title in (("P0", "fix before next release"), ("P1", "fix this sprint"), ("P2", "review when convenient")):
        lines.extend([f"### {severity} — {title}", ""])
        selected = [row for row in rows if row["severity"] == severity]
        if not selected:
            lines.extend(["(empty)", ""])
            continue
        for row in selected:
            identifier = f" ADR `{row['adr_id']}`" if row.get("adr_id") else ""
            lines.append(f"- `{row['symptom']}` —{identifier} `{json.dumps(row['evidence'], sort_keys=True)}`")
            lines.append(f"  - Resolution: `{row['resolution_command']}`")
        lines.append("")
    lines.extend([
        "## Notes for the user",
        "",
        f"- Severity totals: P0: {counts['P0']}, P1: {counts['P1']}, P2: {counts['P2']}.",
        "- Re-run after applying resolutions to confirm clean.",
    ])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        raise ValueError(f"project root does not exist: {project_root}")
    output_dir = args.output_dir.resolve()
    targets = [_resolve_target(raw, project_root) for raw in args.target] if args.target else [project_root]
    decisions = load_decisions(project_root / "ai-docs" / "decisions")
    references = [reference for path in iter_scannable_files(project_root, targets) for reference in scan_references(path, project_root)]
    known_ids = {decision.id for decision in decisions}
    for reference in references:
        reference["resolved"] = reference["id"] in known_ids
    references.sort(key=lambda item: (item["path"], item["line"], item["id"]))
    rows = make_drift(decisions, project_root, references, full_reference_scope=not args.target)
    audit_diagnostics = registry_audit(decisions)
    link_diagnostics, link_advisories = link_check(decisions, project_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    scan_id = output_dir.name
    (output_dir / "registry-audit.json").write_text(json.dumps({
        "count": len(decisions), "drift_count": len(audit_diagnostics), "drift": audit_diagnostics,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    link_lines = [*link_advisories, *link_diagnostics]
    if not link_diagnostics:
        tail = f", {len(link_advisories)} host-scoped" if link_advisories else ""
        link_lines.append(f"OK — {len(decisions)} decisions, all links resolve{tail}")
    (output_dir / "link-check.txt").write_text("\n".join(link_lines) + "\n", encoding="utf-8")
    raw = {
        "scan_id": scan_id,
        "project_root": str(project_root),
        "targets": [_relative(target, project_root) for target in targets],
        "references": references,
        "registry_audit": {"drift": audit_diagnostics},
        "link_check": {"drift": link_diagnostics, "advisory": link_advisories},
        "drift": rows,
    }
    (output_dir / "raw-drift.json").write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "drift.md").write_text(render_drift(scan_id, decisions, references, rows), encoding="utf-8")
    print(f"{output_dir / 'drift.md'}")
    return 1 if rows else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only portable decision-registry drift audit.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", action="append", default=[], help="Optional project-relative scan target; repeatable.")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
