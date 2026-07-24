#!/usr/bin/env python3
"""Move one explicit Ruby module file from reviewed, content-addressed evidence."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "ruby-move-evidence-v1"
REPORT_VERSION = "ruby-move-report-v1"
MIN_RUBY = (3, 3, 0)
MIN_BUNDLER = (2, 6, 0)
EXCLUDED_PARTS = frozenset(
    {".git", ".bundle", "build", "dist", "generated", "gen", "out", "tmp", "vendor"}
)
CONSTANT_RE = re.compile(r"\A[A-Z]\w*(?:::[A-Z]\w*)*\Z")
LOAD_RE = re.compile(
    r"(?m)(?<![\w.])(?P<kind>require_relative|require|load)\s*(?:\(\s*)?"
    r"(?P<quote>['\"])(?P<value>[^'\"]+)(?P=quote)"
)
DECL_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)(?P<kind>module|class)\s+"
    r"(?P<name>[A-Z]\w*(?:::[A-Z]\w*)*)"
)


class UserError(RuntimeError):
    """Invalid or unsafe input that must not mutate the host tree."""


@dataclass(frozen=True)
class FileState:
    contents: bytes
    mode: int


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _hash_bytes(rendered.encode("utf-8"))


def _lexical(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _has_symlink(path: Path, root: Path) -> bool:
    path = _lexical(path)
    if not _inside(path, root):
        return True
    while path != root:
        if path.is_symlink():
            return True
        path = path.parent
    return root.is_symlink()


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _excluded(path: Path, root: Path, report_dir: Path) -> bool:
    logical = _lexical(path)
    relative = path.relative_to(root)
    return (
        (relative.parts and relative.parts[0] == ".git")
        or logical == report_dir
        or _inside(logical, report_dir)
    )


def _snapshot(root: Path, report_dir: Path) -> tuple[dict[str, FileState], dict[str, str]]:
    files: dict[str, FileState] = {}
    links: dict[str, str] = {}
    for current_text, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_text)
        retained: list[str] = []
        for name in sorted(directory_names):
            path = current / name
            if _excluded(path, root, report_dir):
                continue
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                links[relative] = os.readlink(path)
            else:
                retained.append(name)
        directory_names[:] = retained
        for name in sorted(file_names):
            path = current / name
            if _excluded(path, root, report_dir):
                continue
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                links[relative] = os.readlink(path)
            else:
                files[relative] = FileState(
                    path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
                )
    return files, links


def _fingerprint(files: dict[str, FileState], links: dict[str, str]) -> str:
    rows = {
        **{
            path: f"file:{state.mode:o}:{_hash_bytes(state.contents)}"
            for path, state in files.items()
        },
        **{path: f"symlink:{target}" for path, target in links.items()},
    }
    digest = hashlib.sha256()
    for path, value in sorted(rows.items()):
        digest.update(path.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest()


def _snapshot_diff(
    expected_files: dict[str, FileState],
    expected_links: dict[str, str],
    actual_files: dict[str, FileState],
    actual_links: dict[str, str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "expected_fingerprint": _fingerprint(expected_files, expected_links),
        "actual_fingerprint": _fingerprint(actual_files, actual_links),
        "changed": sorted(
            path
            for path in expected_files.keys() & actual_files.keys()
            if expected_files[path] != actual_files[path]
        ),
        "missing": sorted(expected_files.keys() - actual_files.keys()),
        "unexpected": sorted(actual_files.keys() - expected_files.keys()),
        "changed_symlinks": sorted(
            path
            for path in expected_links.keys() & actual_links.keys()
            if expected_links[path] != actual_links[path]
        ),
        "missing_symlinks": sorted(expected_links.keys() - actual_links.keys()),
        "unexpected_symlinks": sorted(actual_links.keys() - expected_links.keys()),
    }
    result["passed"] = not any(
        result[key]
        for key in (
            "changed",
            "missing",
            "unexpected",
            "changed_symlinks",
            "missing_symlinks",
            "unexpected_symlinks",
        )
    )
    return result


def _restore(
    root: Path,
    report_dir: Path,
    before_files: dict[str, FileState],
    before_links: dict[str, str],
) -> None:
    current_files, current_links = _snapshot(root, report_dir)
    current_paths = sorted(
        set(current_files) | set(current_links),
        key=lambda item: len(PurePosixPath(item).parts),
        reverse=True,
    )
    for relative in current_paths:
        (root / relative).unlink(missing_ok=True)
    for relative, state in sorted(before_files.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(state.contents)
        path.chmod(state.mode)
    for relative, target in sorted(before_links.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and path != report_dir and not _inside(path, report_dir):
            try:
                path.rmdir()
            except OSError:
                pass


def _safe_relative(root: Path, raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise UserError(f"{label} must be a non-empty POSIX relative path")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise UserError(f"{label} escapes the project root")
    result = pure.as_posix()
    path = _lexical(root / result)
    if not _inside(path, root) or _has_symlink(path.parent, root):
        raise UserError(f"{label} crosses a symlink or project boundary")
    return result


def _validate_cli(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    root = _lexical(Path(args.project_root))
    if not root.is_dir() or root.is_symlink():
        raise UserError("--project-root must be a non-symlink directory")
    plan = _lexical(Path(args.plan) if Path(args.plan).is_absolute() else root / args.plan)
    report_dir = _lexical(
        Path(args.report_dir)
        if Path(args.report_dir).is_absolute()
        else root / args.report_dir
    )
    if not _inside(plan, root) or _has_symlink(plan, root) or not plan.is_file():
        raise UserError("--plan must be a regular file inside the project root")
    if not _inside(report_dir, root) or _has_symlink(report_dir.parent, root):
        raise UserError("--report-dir must remain inside the project root")
    report_dir.mkdir(parents=True, exist_ok=True)
    return root, plan, report_dir


def _load_plan(root: Path, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UserError(f"invalid Ruby move plan: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise UserError("Ruby move plan version must be 1")
    moves = value.get("moves")
    if not isinstance(moves, list) or len(moves) != 1 or not isinstance(moves[0], dict):
        raise UserError("Ruby cohort supports exactly one file move")
    move = moves[0]
    if move.get("mode") != "file":
        raise UserError("Ruby cohort supports only mode=file")
    source = _safe_relative(root, move.get("from"), "moves[0].from")
    destination = _safe_relative(root, move.get("to"), "moves[0].to")
    if (
        source == destination
        or not source.startswith("lib/")
        or not destination.startswith("lib/")
        or not source.endswith(".rb")
        or not destination.endswith(".rb")
    ):
        raise UserError("Ruby cohort requires distinct .rb paths under lib/")
    if value.get("rewrite") != {"code_imports": "update-ruby"}:
        raise UserError("rewrite.code_imports must be update-ruby")
    ruby = value.get("ruby")
    required = {
        "binary",
        "bundler",
        "constant_before",
        "constant_after",
        "native_test",
        "native_test_expected_stdout",
        "smoke",
        "smoke_expected_stdout",
    }
    if not isinstance(ruby, dict) or set(ruby) != required:
        raise UserError("ruby plan block has unsupported or missing keys")
    before = ruby["constant_before"]
    after = ruby["constant_after"]
    if (
        not isinstance(before, str)
        or not isinstance(after, str)
        or not CONSTANT_RE.fullmatch(before)
        or not CONSTANT_RE.fullmatch(after)
        or before == after
        or before.split("::")[-1] != after.split("::")[-1]
    ):
        raise UserError("Ruby constants must be explicit qualified identities with one leaf")
    normalized_ruby = dict(ruby)
    normalized_ruby["native_test"] = _safe_relative(root, ruby["native_test"], "ruby.native_test")
    normalized_ruby["smoke"] = _safe_relative(root, ruby["smoke"], "ruby.smoke")
    for label in ("binary", "bundler", "native_test_expected_stdout", "smoke_expected_stdout"):
        if not isinstance(normalized_ruby[label], str) or not normalized_ruby[label]:
            raise UserError(f"ruby.{label} must be a non-empty string")
    value["_normalized"] = {
        "version": 1,
        "move": {"from": source, "to": destination},
        "rewrite": {"code_imports": "update-ruby"},
        "ruby": normalized_ruby,
    }
    return value


def _resolve_tool(raw: str) -> Path | None:
    candidate = Path(raw)
    if candidate.parent == Path("."):
        found = shutil.which(raw)
        candidate = Path(found) if found else candidate
    path = candidate.resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        return None
    return path


def _run(argv: list[str], *, root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"passed": False, "returncode": None, "stdout": "", "stderr": str(exc)}
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(map(int, match.groups())) if match else None  # type: ignore[return-value]


def _tool_evidence(root: Path, ruby_plan: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    ruby = _resolve_tool(ruby_plan["binary"])
    bundler = _resolve_tool(ruby_plan["bundler"])
    if ruby is None or bundler is None:
        return {"status": "partial"}, "ruby_tool_missing"
    ruby_version = _run([str(ruby), "--version"], root=root)
    parsed_ruby = _version(ruby_version["stdout"] + ruby_version["stderr"])
    if not ruby_version["passed"] or parsed_ruby is None or parsed_ruby < MIN_RUBY:
        return {
            "status": "partial",
            "ruby": ruby_version,
            "ruby_version": list(parsed_ruby) if parsed_ruby else None,
        }, "ruby_tool_too_old"
    bundle_version = _run([str(bundler), "--version"], root=root)
    parsed_bundle = _version(bundle_version["stdout"] + bundle_version["stderr"])
    if not bundle_version["passed"] or parsed_bundle is None or parsed_bundle < MIN_BUNDLER:
        return {"status": "partial", "bundler": bundle_version}, "ruby_tool_too_old"
    prism = _run(
        [str(ruby), "--disable-gems", "-rprism", "-e", "exit Prism.parse('x = 1').success? ? 0 : 1"],
        root=root,
    )
    if not prism["passed"]:
        return {"status": "partial", "prism": prism}, "ruby_tool_missing"
    return {
        "status": "complete",
        "ruby": {"path": str(ruby), "sha256": _hash_bytes(ruby.read_bytes()), "version": list(parsed_ruby)},
        "bundler": {"path": str(bundler), "sha256": _hash_bytes(bundler.read_bytes()), "version": list(parsed_bundle)},
        "prism": prism,
    }, None


def _eligible_ruby_files(root: Path, report_dir: Path) -> list[Path]:
    rows: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix == ".rb" and relative.parts[0] in {"lib", "test", "spec"}:
            rows.append(path)
        elif relative.parts[0] == "bin" and path.read_bytes().startswith(b"#!"):
            rows.append(path)
    return rows


def _native_checks(root: Path, report_dir: Path, ruby_plan: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    tools, failure = _tool_evidence(root, ruby_plan)
    if failure:
        return {"tools": tools}, failure
    ruby = tools["ruby"]["path"]
    bundler = tools["bundler"]["path"]
    syntax: list[dict[str, Any]] = []
    for path in _eligible_ruby_files(root, report_dir):
        row = _run([ruby, "--disable-gems", "-c", str(path)], root=root)
        row["path"] = path.relative_to(root).as_posix()
        syntax.append(row)
        if not row["passed"]:
            return {"tools": tools, "syntax_checks": syntax}, "ruby_syntax_failed"
    with tempfile.TemporaryDirectory(prefix="ruby-move-bundle-") as temporary:
        env = os.environ.copy()
        env.update(
            {
                "BUNDLE_APP_CONFIG": str(Path(temporary) / "app"),
                "BUNDLE_USER_HOME": str(Path(temporary) / "home"),
                "BUNDLE_FROZEN": "true",
                "BUNDLE_DISABLE_VERSION_CHECK": "true",
                "BUNDLE_GEMFILE": str(root / "Gemfile"),
                "http_proxy": "http://127.0.0.1:9",
                "https_proxy": "http://127.0.0.1:9",
                "HTTP_PROXY": "http://127.0.0.1:9",
                "HTTPS_PROXY": "http://127.0.0.1:9",
            }
        )
        bundle = _run([bundler, "check"], root=root, env=env)
    checks: dict[str, Any] = {
        "tools": tools,
        "syntax_checks": syntax,
        "bundle_check": bundle,
    }
    if not bundle["passed"]:
        return checks, "frozen_bundle_check_failed"
    for key, path_key, output_key in (
        ("native_test", "native_test", "native_test_expected_stdout"),
        ("smoke", "smoke", "smoke_expected_stdout"),
    ):
        row = _run(
            [ruby, "--disable-gems", "-I", str(root / "lib"), str(root / ruby_plan[path_key])],
            root=root,
        )
        row["expected_stdout"] = ruby_plan[output_key]
        row["passed"] = row["passed"] and row["stdout"] == ruby_plan[output_key]
        checks[key] = row
        if not row["passed"]:
            return checks, f"ruby_{key}_failed"
    return checks, None


def _excluded_identity_boundaries(root: Path, report_dir: Path, old_constant: str, source: str) -> list[dict[str, Any]]:
    old_path = source.removeprefix("lib/").removesuffix(".rb")
    blocked: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.rb")):
        if path.is_symlink() or not path.is_file() or _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root)
        if not any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if old_constant in text or old_path in text:
            blocked.append({"kind": "ruby_excluded_old_identity", "path": relative.as_posix()})
    return blocked


def _boundary_checks(root: Path, report_dir: Path, normalized: dict[str, Any]) -> list[dict[str, Any]]:
    move = normalized["move"]
    ruby = normalized["ruby"]
    source_path = root / move["from"]
    blocked: list[dict[str, Any]] = []
    if source_path.is_symlink() or not source_path.is_file():
        blocked.append({"kind": "ruby_symlink_boundary", "path": move["from"]})
        return blocked
    if (root / move["to"]).exists() or (root / move["to"]).is_symlink():
        blocked.append({"kind": "ruby_destination_exists", "path": move["to"]})
    if (root / "config/application.rb").exists():
        blocked.append({"kind": "ruby_framework_loader_unsupported", "path": "config/application.rb"})
    gem_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (root / "Gemfile", root / "Gemfile.lock")
        if path.is_file()
    )
    if re.search(r"\b(?:rails|zeitwerk)\b", gem_text, re.IGNORECASE):
        blocked.append({"kind": "ruby_framework_loader_unsupported", "path": "Gemfile"})
    blocked.extend(
        _excluded_identity_boundaries(
            root, report_dir, ruby["constant_before"], move["from"]
        )
    )
    old_path = move["from"].removeprefix("lib/").removesuffix(".rb")
    old_parts = ruby["constant_before"].split("::")
    namespace, leaf = "::".join(old_parts[:-1]), old_parts[-1]
    declaration_count = 0
    for path in _eligible_ruby_files(root, report_dir):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        declaration_count += len(
            re.findall(
                rf"(?m)^\s*class\s+(?:{re.escape(ruby['constant_before'])}|{re.escape(leaf)})\b",
                text,
            )
        ) if (namespace in text or ruby["constant_before"] in text) else 0
        if re.search(rf"\b(?:require|load)\s*(?:\(\s*)?['\"]{re.escape(old_path)}(?:\.rb)?['\"]", text):
            blocked.append({"kind": "ruby_non_relative_load_impact", "path": relative})
        if old_path in text and re.search(
            r"\brequire(?!_relative)\s*(?:\(\s*)?[^'\"\s]", text
        ):
            blocked.append({"kind": "ruby_dynamic_load_identity", "path": relative})
        if old_path in text and re.search(r"\bautoload\b", text):
            blocked.append({"kind": "ruby_autoload_identity", "path": relative})
        if re.search(
            rf"\b{re.escape(namespace)}\s*\.\s*(?:const_get|const_missing)\s*\(?\s*:{re.escape(leaf)}\b",
            text,
        ):
            blocked.append({"kind": "ruby_reflective_constant_identity", "path": relative})
    if declaration_count != 1:
        blocked.append({"kind": "ruby_constant_reopened", "path": move["from"]})
    return list({json.dumps(row, sort_keys=True): row for row in blocked}.values())


def _resolve_require_relative(caller: str, value: str) -> str:
    target = PurePosixPath(caller).parent / value
    normalized = os.path.normpath(target.as_posix()).replace("\\", "/")
    return normalized if normalized.endswith(".rb") else normalized + ".rb"


def _relative_spec(caller_after: str, target_after: str) -> str:
    caller_dir = PurePosixPath(caller_after).parent.as_posix()
    target_no_suffix = target_after.removesuffix(".rb")
    return os.path.relpath(target_no_suffix, caller_dir).replace("\\", "/")


def _map_after(path: str, source: str, destination: str) -> str:
    return destination if path == source else path


def _change(
    *,
    file_before: str,
    file_after: str,
    kind: str,
    old: str,
    new: str,
    start: int,
    end: int,
    source: bytes,
) -> dict[str, Any]:
    return {
        "file_before": file_before,
        "file_after": file_after,
        "kind": kind,
        "old": old,
        "new": new,
        "start": start,
        "end": end,
        "source_sha256": _hash_bytes(source),
        "line": source[:start].count(b"\n") + 1,
    }


def _plan_changes(root: Path, report_dir: Path, normalized: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    move = normalized["move"]
    ruby = normalized["ruby"]
    old_constant = ruby["constant_before"]
    new_constant = ruby["constant_after"]
    old_namespace = "::".join(old_constant.split("::")[:-1])
    new_namespace = "::".join(new_constant.split("::")[:-1])
    leaf = old_constant.split("::")[-1]
    changes: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for path in _eligible_ruby_files(root, report_dir):
        relative = path.relative_to(root).as_posix()
        after_relative = _map_after(relative, move["from"], move["to"])
        source = path.read_bytes()
        text = source.decode("utf-8")
        protected: list[tuple[int, int]] = []
        for match in LOAD_RE.finditer(text):
            if match.group("kind") != "require_relative":
                continue
            target = _resolve_require_relative(relative, match.group("value"))
            target_after = _map_after(target, move["from"], move["to"])
            if relative != after_relative or target != target_after:
                value = match.group("value")
                replacement = _relative_spec(after_relative, target_after)
                if replacement != value:
                    start, end = match.span("value")
                    changes.append(
                        _change(
                            file_before=relative,
                            file_after=after_relative,
                            kind="ruby_require_relative",
                            old=value,
                            new=replacement,
                            start=start,
                            end=end,
                            source=source,
                        )
                    )
                    protected.append((start, end))
        declaration_spans: list[tuple[int, int]] = []
        for declaration in DECL_RE.finditer(text):
            declaration_spans.append(declaration.span("name"))
        if relative == move["from"]:
            namespace_matches = [
                row
                for row in DECL_RE.finditer(text)
                if row.group("kind") == "module" and row.group("name") == old_namespace
            ]
            if len(namespace_matches) != 1:
                blocked.append({"kind": "ruby_source_namespace_unproved", "path": relative})
            else:
                match = namespace_matches[0]
                start, end = match.span("name")
                changes.append(
                    _change(
                        file_before=relative,
                        file_after=after_relative,
                        kind="ruby_module_namespace",
                        old=old_namespace,
                        new=new_namespace,
                        start=start,
                        end=end,
                        source=source,
                    )
                )
                declaration_spans.append((start, end))
        for match in re.finditer(rf"(?<![\w:]){re.escape(old_constant)}(?![\w:])", text):
            start, end = match.span()
            if any(begin <= start < finish for begin, finish in declaration_spans + protected):
                continue
            changes.append(
                _change(
                    file_before=relative,
                    file_after=after_relative,
                    kind="ruby_constant_reference",
                    old=old_constant,
                    new=new_constant,
                    start=start,
                    end=end,
                    source=source,
                )
            )
        if old_namespace in text:
            for match in re.finditer(rf"(?<![\w:]){re.escape(leaf)}(?![\w:])", text):
                start, end = match.span()
                if any(begin <= start < finish for begin, finish in declaration_spans + protected):
                    continue
                changes.append(
                    _change(
                        file_before=relative,
                        file_after=after_relative,
                        kind="ruby_constant_reference",
                        old=leaf,
                        new=new_constant,
                        start=start,
                        end=end,
                        source=source,
                    )
                )
    unique = {(
        row["file_before"], row["start"], row["end"]
    ): row for row in changes}
    ordered = sorted(unique.values(), key=lambda row: (row["file_before"], row["start"]))
    for first, second in zip(ordered, ordered[1:], strict=False):
        if first["file_before"] == second["file_before"] and first["end"] > second["start"]:
            blocked.append({"kind": "ruby_overlapping_edits", "path": first["file_before"]})
    return ordered, blocked


def _apply_replacements(content: bytes, changes: list[dict[str, Any]]) -> bytes:
    text = content.decode("utf-8")
    for row in sorted(changes, key=lambda item: item["start"], reverse=True):
        if text[row["start"] : row["end"]] != row["old"]:
            raise UserError(f"stale Ruby edit span in {row['file_before']}")
        text = text[: row["start"]] + row["new"] + text[row["end"] :]
    return text.encode("utf-8")


def _patched_files(before: dict[str, FileState], changes: list[dict[str, Any]]) -> dict[str, bytes]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in changes:
        grouped.setdefault(row["file_before"], []).append(row)
    return {
        path: _apply_replacements(before[path].contents, rows)
        for path, rows in grouped.items()
    }


def _expected_snapshot(
    before: dict[str, FileState], move: dict[str, str], patches: dict[str, bytes]
) -> dict[str, FileState]:
    expected: dict[str, FileState] = {}
    for relative, state in before.items():
        after = _map_after(relative, move["from"], move["to"])
        expected[after] = FileState(patches.get(relative, state.contents), state.mode)
    return expected


def _preview_diff(before: dict[str, FileState], expected: dict[str, FileState], move: dict[str, str]) -> str:
    chunks: list[str] = []
    for old, state in sorted(before.items()):
        new = _map_after(old, move["from"], move["to"])
        after = expected[new]
        if old != new or state.contents != after.contents:
            chunks.extend(
                difflib.unified_diff(
                    state.contents.decode("utf-8", errors="replace").splitlines(keepends=True),
                    after.contents.decode("utf-8", errors="replace").splitlines(keepends=True),
                    fromfile=old,
                    tofile=new,
                )
            )
    return "".join(chunks)


def _evidence_payload(
    normalized: dict[str, Any],
    before: dict[str, FileState],
    links: dict[str, str],
    expected: dict[str, FileState],
    changes: list[dict[str, Any]],
    tools: dict[str, Any],
) -> dict[str, Any]:
    script = Path(__file__).resolve()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "plan_sha256": _canonical_hash(normalized),
        "source_tree_sha256": _fingerprint(before, links),
        "expected_after_tree_sha256": _fingerprint(expected, links),
        "move": normalized["move"],
        "exact_changes": changes,
        "tools": tools,
        "adapter_sha256": _hash_bytes(script.read_bytes()),
    }
    payload["evidence_sha256"] = _canonical_hash(payload)
    return payload


def _load_evidence(root: Path, report_dir: Path, raw: str | None, normalized: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        raise UserError("--evidence is required for Ruby apply/check")
    path = _lexical(Path(raw) if Path(raw).is_absolute() else root / raw)
    if not _inside(path, report_dir) or _has_symlink(path, root) or not path.is_file():
        raise UserError("evidence must be a regular file in the report directory")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UserError(f"invalid Ruby move evidence: {exc}") from exc
    supplied = payload.get("evidence_sha256")
    unhashed = dict(payload)
    unhashed.pop("evidence_sha256", None)
    if payload.get("schema_version") != SCHEMA_VERSION or supplied != _canonical_hash(unhashed):
        raise UserError("Ruby move evidence hash does not verify")
    if payload.get("status") != "complete" or payload.get("plan_sha256") != _canonical_hash(normalized):
        raise UserError("Ruby move evidence does not authorize this plan")
    return payload


def _base_report(mode: str, status: str, failure: str, normalized: dict[str, Any], source_hash: str) -> dict[str, Any]:
    return {
        "schema_version": REPORT_VERSION,
        "ruby": {
            "mode": mode,
            "status": status,
            "failure_kind": failure,
            "move": normalized["move"],
            "source_tree_sha256": source_hash,
            "blocked": [],
            "exact_changes": [],
            "rolled_back": False,
            "old_identity_remaining": [],
            "further_edits": [],
        },
    }


def _markdown(report: dict[str, Any]) -> str:
    ruby = report["ruby"]
    return (
        "# Ruby move-path report\n\n"
        f"Status: `{ruby['status']}`\n"
        f"Mode: `{ruby['mode']}`\n"
        f"Failure: `{ruby['failure_kind']}`\n"
    )


def _write_report(report_dir: Path, report: dict[str, Any]) -> None:
    _atomic_json(report_dir / "report.json", report)
    _atomic_text(report_dir / "report.md", _markdown(report))


def _status_for_failure(failure: str) -> str:
    return "partial" if failure in {"ruby_tool_missing", "ruby_tool_too_old"} else "failed"


def _dry_run(root: Path, report_dir: Path, normalized: dict[str, Any]) -> tuple[dict[str, Any], int]:
    (report_dir / "evidence.json").unlink(missing_ok=True)
    before, links = _snapshot(root, report_dir)
    source_hash = _fingerprint(before, links)
    native, native_failure = _native_checks(root, report_dir, normalized["ruby"])
    after_native, after_links = _snapshot(root, report_dir)
    if _fingerprint(after_native, after_links) != source_hash:
        _restore(root, report_dir, before, links)
        native_failure = "source_changed_during_evidence"
    if native_failure:
        report = _base_report(
            "dry-run", _status_for_failure(native_failure), native_failure, normalized, source_hash
        )
        report["ruby"]["native_preflight"] = native
        _write_report(report_dir, report)
        return report, 2
    blocked = _boundary_checks(root, report_dir, normalized)
    changes, plan_blocked = _plan_changes(root, report_dir, normalized)
    blocked.extend(plan_blocked)
    if blocked:
        report = _base_report("dry-run", "partial", "unsafe_ruby_move_shape", normalized, source_hash)
        report["ruby"].update(blocked=blocked, native_preflight=native)
        _write_report(report_dir, report)
        return report, 2
    patches = _patched_files(before, changes)
    expected = _expected_snapshot(before, normalized["move"], patches)
    evidence = _evidence_payload(
        normalized, before, links, expected, changes, native["tools"]
    )
    _atomic_json(report_dir / "evidence.json", evidence)
    report = _base_report("dry-run", "complete", "none", normalized, source_hash)
    report["ruby"].update(
        evidence_sha256=evidence["evidence_sha256"],
        expected_after_tree_sha256=evidence["expected_after_tree_sha256"],
        exact_changes=changes,
        preview_diff=_preview_diff(before, expected, normalized["move"]),
        native_preflight=native,
    )
    _write_report(report_dir, report)
    return report, 0


def _apply_move(root: Path, move: dict[str, str], patches: dict[str, bytes]) -> None:
    source = root / move["from"]
    destination = root / move["to"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)
    for relative, content in patches.items():
        after = _map_after(relative, move["from"], move["to"])
        path = root / after
        mode = stat.S_IMODE(path.stat().st_mode)
        path.write_bytes(content)
        path.chmod(mode)


def _tool_evidence_matches(root: Path, ruby_plan: dict[str, Any], evidence: dict[str, Any]) -> bool:
    current, failure = _tool_evidence(root, ruby_plan)
    return failure is None and current == evidence.get("tools")


def _old_identity_remaining(root: Path, evidence: dict[str, Any]) -> list[dict[str, str]]:
    remaining: list[dict[str, str]] = []
    for row in evidence["exact_changes"]:
        path = root / row["file_after"]
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            if row["old"] in text and row["new"] not in text:
                remaining.append({"path": row["file_after"], "identity": row["old"]})
    return list({json.dumps(row, sort_keys=True): row for row in remaining}.values())


def _apply(args: argparse.Namespace, root: Path, report_dir: Path, normalized: dict[str, Any]) -> tuple[dict[str, Any], int]:
    evidence = _load_evidence(root, report_dir, args.evidence, normalized)
    if args.approve_evidence_sha256 != evidence["evidence_sha256"]:
        raise UserError("--approve-evidence-sha256 must equal reviewed evidence")
    before, links = _snapshot(root, report_dir)
    current_hash = _fingerprint(before, links)
    report = _base_report("apply", "failed", "stale_move_evidence", normalized, current_hash)
    report["ruby"].update(
        evidence_sha256=evidence["evidence_sha256"], exact_changes=evidence["exact_changes"]
    )
    if (
        current_hash != evidence["source_tree_sha256"]
        or _hash_bytes(Path(__file__).resolve().read_bytes()) != evidence.get("adapter_sha256")
        or not _tool_evidence_matches(root, normalized["ruby"], evidence)
    ):
        _write_report(report_dir, report)
        return report, 2
    for row in evidence["exact_changes"]:
        state = before.get(row["file_before"])
        if state is None or _hash_bytes(state.contents) != row["source_sha256"]:
            _write_report(report_dir, report)
            return report, 2
    patches = _patched_files(before, evidence["exact_changes"])
    expected = _expected_snapshot(before, normalized["move"], patches)
    try:
        _apply_move(root, normalized["move"], patches)
        native, failure = _native_checks(root, report_dir, normalized["ruby"])
        report["ruby"]["native_postflight"] = native
        if failure:
            report["ruby"]["failure_kind"] = failure
            raise UserError(failure)
        actual, actual_links = _snapshot(root, report_dir)
        exact = _snapshot_diff(expected, links, actual, actual_links)
        report["ruby"]["exact_after_tree"] = exact
        remaining = _old_identity_remaining(root, evidence)
        report["ruby"]["old_identity_remaining"] = remaining
        if not exact["passed"] or remaining:
            report["ruby"]["failure_kind"] = (
                "exact_after_tree_failed" if not exact["passed"] else "old_identity_residue"
            )
            raise UserError(report["ruby"]["failure_kind"])
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - rollback owns every post-mutation failure
        _restore(root, report_dir, before, links)
        report["ruby"].update(status="failed", rolled_back=True, failure_detail=str(exc))
        restored, restored_links = _snapshot(root, report_dir)
        report["ruby"]["rollback_exact"] = _snapshot_diff(before, links, restored, restored_links)
        _write_report(report_dir, report)
        return report, 2
    report["ruby"].update(status="complete", failure_kind="none", rolled_back=False)
    _write_report(report_dir, report)
    return report, 0


def _check(args: argparse.Namespace, root: Path, report_dir: Path, normalized: dict[str, Any]) -> tuple[dict[str, Any], int]:
    evidence = _load_evidence(root, report_dir, args.evidence, normalized)
    files, links = _snapshot(root, report_dir)
    current_hash = _fingerprint(files, links)
    report = _base_report("check", "failed", "after_tree_mismatch", normalized, current_hash)
    report["ruby"].update(
        evidence_sha256=evidence["evidence_sha256"], exact_changes=evidence["exact_changes"]
    )
    if current_hash != evidence["expected_after_tree_sha256"]:
        report["ruby"]["further_edits"] = ["current tree differs from approved after tree"]
        _write_report(report_dir, report)
        return report, 2
    native, failure = _native_checks(root, report_dir, normalized["ruby"])
    report["ruby"]["native_postflight"] = native
    remaining = _old_identity_remaining(root, evidence)
    report["ruby"]["old_identity_remaining"] = remaining
    if failure or remaining:
        report["ruby"]["failure_kind"] = failure or "old_identity_residue"
        _write_report(report_dir, report)
        return report, 2
    report["ruby"].update(status="complete", failure_kind="none", further_edits=[])
    _write_report(report_dir, report)
    return report, 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report-dir", default="reports/move-path")
    parser.add_argument("--evidence")
    parser.add_argument("--approve-evidence-sha256")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root, plan_path, report_dir = _validate_cli(args)
        normalized = _load_plan(root, plan_path)["_normalized"]
        if args.dry_run:
            report, code = _dry_run(root, report_dir, normalized)
        elif args.apply:
            report, code = _apply(args, root, report_dir, normalized)
        else:
            report, code = _check(args, root, report_dir, normalized)
    except UserError as exc:
        print(f"ruby move refused: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Ruby move {report['ruby']['mode']}: {report['ruby']['status']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
