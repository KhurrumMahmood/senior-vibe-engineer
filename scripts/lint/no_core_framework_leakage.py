#!/usr/bin/env python3
"""Reject framework vocabulary and dishonest metadata in migrated core skills.

The rule is source-aware: staged and revision diffs inspect the pre-move blob
as well as the post-move blob for renames/copies, so moving contaminated core
text under ``bindings/`` cannot launder it past the boundary.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib.skill_catalog import DEFAULT_INVENTORY_PATH, load_catalog
from _lib.yaml_frontmatter import FrontmatterError, parse


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / ".claude/skills/_common/capability-registry.yml"
DEFAULT_ALLOWLIST = (
    REPO_ROOT / ".claude/skills/_common/core-framework-leakage-allowlist.yml"
)
ALLOWLIST_FIELDS = frozenset({"path", "term", "owner", "reason", "expires_on"})
ALLOWLIST_TOP_LEVEL = frozenset({"schema_version", "allowlist"})
SAFE_FRONTMATTER_FIELDS = frozenset(
    {
        "binding",
        "bindings",
        "capabilities",
        "capability_evidence",
        "framework",
        "language",
        "layer",
        "portable_subjects",
        "scan_implementations",
        "scans",
        "support",
        "support_evidence",
    }
)
SKILL_PATH_RE = re.compile(
    r"^\.claude/skills/(?P<name>[^/]+)/(?P<tail>SKILL\.md|bindings/.+)$"
)


class AllowlistError(ValueError):
    """The external leakage allowlist violates its strict schema."""


@dataclass(frozen=True)
class Document:
    path: str
    text: str
    source: str


@dataclass(frozen=True)
class AllowlistEntry:
    path: str
    term: str
    owner: str
    reason: str
    expires_on: date


@dataclass(frozen=True)
class Violation:
    path: str
    code: str
    message: str
    source: str = "worktree"
    field: str = "body"
    line: int | None = None

    def render(self) -> str:
        location = self.path
        if self.line is not None:
            location += f":{self.line}"
        return f"{location}: [{self.code}] {self.message} ({self.source}; {self.field})"


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AllowlistError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise AllowlistError(f"invalid YAML in {path}: {exc}") from exc


def load_framework_vocabulary(path: Path = DEFAULT_REGISTRY) -> dict[str, str]:
    """Return canonical lower-case term -> owning framework from the registry."""
    payload = _load_yaml(path)
    frameworks = payload.get("frameworks") if isinstance(payload, dict) else None
    if not isinstance(frameworks, dict):
        raise AllowlistError("capability registry frameworks must be a mapping")
    vocabulary: dict[str, str] = {}
    errors: list[str] = []
    for framework, contract in frameworks.items():
        if framework in {"any", "none"}:
            continue
        if not isinstance(contract, dict):
            errors.append(f"framework {framework!r} contract must be a mapping")
            continue
        terms = contract.get("core_leakage_terms")
        if not isinstance(terms, list) or not terms:
            errors.append(
                f"framework {framework!r} must declare non-empty core_leakage_terms"
            )
            continue
        for raw_term in terms:
            if not isinstance(raw_term, str) or not raw_term.strip():
                errors.append(
                    f"framework {framework!r} has an invalid core leakage term"
                )
                continue
            term = raw_term.strip().casefold()
            previous = vocabulary.get(term)
            if previous is not None and previous != framework:
                errors.append(
                    f"core leakage term {term!r} belongs to both {previous!r} "
                    f"and {framework!r}"
                )
            vocabulary[term] = framework
    if errors:
        raise AllowlistError("\n".join(errors))
    return vocabulary


def _coerce_date(value: object, *, field: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise AllowlistError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AllowlistError(f"{field} must be an ISO date") from exc


def load_allowlist(
    path: Path = DEFAULT_ALLOWLIST,
    *,
    vocabulary: Mapping[str, str],
    today: date | None = None,
) -> tuple[AllowlistEntry, ...]:
    """Load exact, owner-bound, at-most-90-day temporary exceptions."""
    payload = _load_yaml(path)
    if not isinstance(payload, dict) or set(payload) != ALLOWLIST_TOP_LEVEL:
        raise AllowlistError(
            f"allowlist must contain exactly {sorted(ALLOWLIST_TOP_LEVEL)}"
        )
    if payload.get("schema_version") != 1:
        raise AllowlistError("allowlist schema_version must be 1")
    rows = payload.get("allowlist")
    if not isinstance(rows, list):
        raise AllowlistError("allowlist must be a list")
    current = today or date.today()
    entries: list[AllowlistEntry] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        prefix = f"allowlist[{index}]"
        if not isinstance(row, dict) or set(row) != ALLOWLIST_FIELDS:
            raise AllowlistError(
                f"{prefix} must contain exactly {sorted(ALLOWLIST_FIELDS)}"
            )
        path_value = row["path"]
        term_value = row["term"]
        owner = row["owner"]
        reason = row["reason"]
        path_match = (
            SKILL_PATH_RE.fullmatch(path_value)
            if isinstance(path_value, str)
            else None
        )
        if path_match is None or path_match.group("tail") != "SKILL.md":
            raise AllowlistError(f"{prefix}.path must be an exact core SKILL.md path")
        if not isinstance(term_value, str) or term_value.casefold() not in vocabulary:
            raise AllowlistError(f"{prefix}.term must be canonical registry vocabulary")
        term = term_value.casefold()
        if term_value != term:
            raise AllowlistError(f"{prefix}.term must use canonical lower-case spelling")
        if not isinstance(owner, str) or not owner.strip():
            raise AllowlistError(f"{prefix}.owner must be a non-empty string")
        if not isinstance(reason, str) or not reason.strip():
            raise AllowlistError(f"{prefix}.reason must be a non-empty string")
        expiry = _coerce_date(row["expires_on"], field=f"{prefix}.expires_on")
        remaining = (expiry - current).days
        if remaining < 0:
            raise AllowlistError(f"{prefix}.expires_on is expired")
        if remaining > 90:
            raise AllowlistError(f"{prefix}.expires_on exceeds the 90-day maximum")
        key = (path_value, term)
        if key in seen:
            raise AllowlistError(f"duplicate allowlist entry for {path_value} term {term}")
        seen.add(key)
        entries.append(
            AllowlistEntry(
                path=path_value,
                term=term,
                owner=owner.strip(),
                reason=reason.strip(),
                expires_on=expiry,
            )
        )
    return tuple(entries)


def _inventory_rows(path: Path = DEFAULT_INVENTORY_PATH) -> dict[str, dict[str, Any]]:
    catalog = load_catalog(path)
    return {
        entry.name: {
            "name": entry.name,
            "path": entry.path,
            "layer": entry.layer,
            "bindings": entry.bindings,
            "readiness": entry.readiness,
            "ar3_foundation_member": entry.ar3_foundation_member,
        }
        for entry in catalog.entries
    }


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def _string_fields(value: object, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield prefix, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _string_fields(item, f"{prefix}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _string_fields(item, child)


def _line_for(text: str, match_start: int) -> int:
    return text.count("\n", 0, match_start) + 1


def _normalized_paragraphs(text: str) -> set[str]:
    paragraphs: set[str] = set()
    for paragraph in re.split(r"\n\s*\n", text):
        normalized = re.sub(r"[^a-z0-9]+", " ", paragraph.casefold()).strip()
        if len(normalized) >= 60 and len(normalized.split()) >= 8:
            paragraphs.add(normalized)
    return paragraphs


# spec:portable-skill-layer-distribution::IM-5
def lint_documents(
    documents: Iterable[Document],
    *,
    inventory: Mapping[str, Mapping[str, Any]],
    vocabulary: Mapping[str, str],
    allowlist: Iterable[AllowlistEntry] = (),
) -> list[Violation]:
    docs = list(documents)
    allowed = {(entry.path, entry.term): entry for entry in allowlist}
    violations: list[Violation] = []
    core_paragraphs: dict[tuple[str, str], set[str]] = {}
    parsed_docs: list[tuple[Document, str, str, Any]] = []

    for document in docs:
        match = SKILL_PATH_RE.fullmatch(document.path)
        if not match:
            continue
        name, tail = match.group("name"), match.group("tail")
        row = inventory.get(name)
        if not row or row.get("layer") != "core" or row.get("readiness") != "foundation-ready":
            continue
        try:
            parsed = parse(document.text, path=document.path)
        except FrontmatterError as exc:
            violations.append(
                Violation(document.path, "invalid-frontmatter", str(exc), document.source)
            )
            continue
        parsed_docs.append((document, name, tail, parsed))
        if tail == "SKILL.md":
            core_paragraphs[(name, document.source)] = _normalized_paragraphs(parsed.body)

    for document, name, tail, parsed in parsed_docs:
        row = inventory[name]
        if tail != "SKILL.md":
            parts = PurePosixPath(tail).parts
            binding = PurePosixPath(tail).stem if len(parts) == 2 else None
            declared = tuple(row.get("bindings", ()))
            if (
                len(parts) != 2
                or parts[0] != "bindings"
                or PurePosixPath(tail).suffix != ".md"
                or binding not in declared
                or binding == "core"
            ):
                violations.append(
                    Violation(
                        document.path,
                        "undeclared-binding",
                        "binding files must be one-level Markdown overlays declared by the inventory",
                        document.source,
                    )
                )
                continue
            binding_paragraphs = _normalized_paragraphs(parsed.body)
            repeated = binding_paragraphs & core_paragraphs.get(
                (name, document.source),
                core_paragraphs.get((name, "worktree"), set()),
            )
            for paragraph in sorted(repeated):
                violations.append(
                    Violation(
                        document.path,
                        "duplicated-core-procedure",
                        f"binding repeats normalized core procedure paragraph: {paragraph[:80]!r}",
                        document.source,
                    )
                )
            continue

        if not parsed.has_frontmatter:
            violations.append(
                Violation(
                    document.path,
                    "invalid-frontmatter",
                    "migrated core SKILL.md requires YAML frontmatter",
                    document.source,
                )
            )
            continue
        metadata = parsed.metadata
        if metadata.get("framework") != "any":
            violations.append(
                Violation(
                    document.path,
                    "dishonest-frontmatter",
                    "migrated core skill must declare framework: any",
                    document.source,
                    "framework",
                )
            )
        verified = metadata.get("support") == "verified"
        path_allowlist = [entry for entry in allowlist if entry.path == document.path]
        if verified and path_allowlist:
            violations.append(
                Violation(
                    document.path,
                    "verified-claim-allowlist",
                    "verified capability claims cannot use framework leakage allowlists",
                    document.source,
                    "support",
                )
            )

        scan_fields = [("body", parsed.body)]
        scan_fields.extend(
            (field, value)
            for field, value in _string_fields(metadata)
            if field.split(".", 1)[0].split("[", 1)[0] not in SAFE_FRONTMATTER_FIELDS
        )
        for field, text in scan_fields:
            for term, framework in vocabulary.items():
                pattern = _term_pattern(term)
                for term_match in pattern.finditer(text):
                    if not verified and (document.path, term) in allowed:
                        continue
                    violations.append(
                        Violation(
                            document.path,
                            "framework-term",
                            f"core content names {term_match.group(0)!r} from the {framework!r} vocabulary",
                            document.source,
                            field,
                            _line_for(text, term_match.start()),
                        )
                    )
    return violations


def _git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=False, capture_output=True
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "git failed")
    return result


def _blob(repo: Path, spec: str) -> str:
    result = _git(repo, ["show", spec])
    return result.stdout.decode("utf-8")


def _name_status(repo: Path, args: list[str]) -> list[tuple[str, str, str | None]]:
    raw = _git(repo, ["diff", "--name-status", "-z", "-M", *args, "--", ".claude/skills"]).stdout
    fields = raw.decode("utf-8").split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    records: list[tuple[str, str, str | None]] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if status.startswith(("R", "C")):
            old, new = fields[index], fields[index + 1]
            index += 2
            records.append((status, old, new))
        else:
            path = fields[index]
            index += 1
            records.append((status, path, None))
    return records


def collect_changed_documents(
    repo: Path,
    *,
    staged: bool = False,
    changed_from: str | None = None,
) -> list[Document]:
    if staged == (changed_from is not None):
        raise ValueError("choose exactly one of staged or changed_from")
    if staged:
        records = _name_status(repo, ["--cached"])
        before_ref, after_ref = "HEAD", ":"
    else:
        merge_base = _git(repo, ["merge-base", changed_from or "", "HEAD"]).stdout.decode().strip()
        records = _name_status(repo, [f"{changed_from}...HEAD"])
        before_ref, after_ref = merge_base, "HEAD"
    documents: list[Document] = []
    for status, path, new_path in records:
        if status.startswith(("R", "C")):
            if SKILL_PATH_RE.fullmatch(path):
                documents.append(Document(path, _blob(repo, f"{before_ref}:{path}"), "before"))
            if new_path and SKILL_PATH_RE.fullmatch(new_path):
                documents.append(Document(new_path, _blob(repo, f"{after_ref}{new_path}" if after_ref == ":" else f"{after_ref}:{new_path}"), "after"))
        elif not status.startswith("D") and SKILL_PATH_RE.fullmatch(path):
            spec = f":{path}" if after_ref == ":" else f"{after_ref}:{path}"
            documents.append(Document(path, _blob(repo, spec), "after"))
    return documents


def _all_documents(repo: Path) -> list[Document]:
    result = _git(
        repo,
        ["ls-files", "-co", "--exclude-standard", "--", ".claude/skills"],
    )
    documents: list[Document] = []
    for raw_path in result.stdout.decode().splitlines():
        if not SKILL_PATH_RE.fullmatch(raw_path):
            continue
        path = repo / raw_path
        if path.is_file():
            documents.append(Document(raw_path, path.read_text(encoding="utf-8"), "worktree"))
    return documents


def _explicit_documents(repo: Path, paths: Iterable[str]) -> list[Document]:
    documents: list[Document] = []
    for raw_path in paths:
        path = Path(raw_path)
        absolute = path if path.is_absolute() else repo / path
        if not absolute.is_file():
            continue
        try:
            relative = absolute.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            continue
        documents.append(Document(relative, absolute.read_text(encoding="utf-8"), "worktree"))
    return documents


def _add_core_companions(
    repo: Path,
    documents: list[Document],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[Document]:
    present = {(doc.path, doc.source) for doc in documents}
    additions: list[Document] = []
    for document in documents:
        match = SKILL_PATH_RE.fullmatch(document.path)
        if not match:
            continue
        row = inventory.get(match.group("name"))
        if not row:
            continue
        if match.group("tail") == "SKILL.md":
            for binding in row.get("bindings", ()):
                if binding == "core":
                    continue
                binding_path = (
                    f".claude/skills/{match.group('name')}/bindings/{binding}.md"
                )
                key = (binding_path, document.source)
                disk_path = repo / binding_path
                if key not in present and disk_path.is_file():
                    additions.append(
                        Document(
                            binding_path,
                            disk_path.read_text(encoding="utf-8"),
                            document.source,
                        )
                    )
                    present.add(key)
            continue
        if not match.group("tail").startswith("bindings/"):
            continue
        core_path = str(row["path"])
        key = (core_path, document.source)
        if key in present:
            continue
        disk_path = repo / core_path
        if disk_path.is_file():
            additions.append(
                Document(core_path, disk_path.read_text(encoding="utf-8"), document.source)
            )
            present.add(key)
    return [*documents, *additions]


def _add_allowlist_targets(
    repo: Path,
    documents: list[Document],
    inventory: Mapping[str, Mapping[str, Any]],
    allowlist: Iterable[AllowlistEntry],
) -> list[Document]:
    present = {(document.path, document.source) for document in documents}
    additions: list[Document] = []
    for entry in allowlist:
        match = SKILL_PATH_RE.fullmatch(entry.path)
        name = match.group("name") if match else ""
        row = inventory.get(name)
        if (
            row is None
            or row.get("layer") != "core"
            or row.get("readiness") != "foundation-ready"
            or row.get("path") != entry.path
        ):
            raise AllowlistError(
                f"allowlist target {entry.path!r} is not an exact migrated core skill"
            )
        key = (entry.path, "worktree")
        if key in present:
            continue
        disk_path = repo / entry.path
        if not disk_path.is_file():
            raise AllowlistError(f"allowlist target does not exist: {entry.path}")
        additions.append(
            Document(entry.path, disk_path.read_text(encoding="utf-8"), "worktree")
        )
        present.add(key)
    return [*documents, *additions]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--staged", action="store_true")
    scope.add_argument("--changed-from", metavar="REF")
    scope.add_argument("--all", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY_PATH)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    if not (args.staged or args.changed_from or args.all or args.paths):
        parser.error("choose --staged, --changed-from, --all, or pass explicit paths")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo_root.resolve()
    try:
        vocabulary = load_framework_vocabulary(args.registry.resolve())
        allowlist = load_allowlist(args.allowlist.resolve(), vocabulary=vocabulary)
        inventory = _inventory_rows(args.inventory.resolve())
        if args.staged:
            documents = collect_changed_documents(repo, staged=True)
        elif args.changed_from:
            documents = collect_changed_documents(repo, changed_from=args.changed_from)
        elif args.all:
            documents = _all_documents(repo)
        else:
            documents = _explicit_documents(repo, args.paths)
        documents = _add_core_companions(repo, documents, inventory)
        documents = _add_allowlist_targets(repo, documents, inventory, allowlist)
        violations = lint_documents(
            documents,
            inventory=inventory,
            vocabulary=vocabulary,
            allowlist=allowlist,
        )
    except (AllowlistError, RuntimeError, ValueError) as exc:
        print(f"core-framework-leakage: configuration error: {exc}", file=sys.stderr)
        return 2
    if violations:
        print("core-framework-leakage FAILED:")
        for violation in violations:
            print(f"  {violation.render()}")
        return 1
    migrated = sum(
        row.get("layer") == "core" and row.get("readiness") == "foundation-ready"
        for row in inventory.values()
    )
    print(
        f"OK — {migrated} migrated core skill(s), canonical framework vocabulary, "
        "frontmatter, bindings, and duplication boundary are clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
