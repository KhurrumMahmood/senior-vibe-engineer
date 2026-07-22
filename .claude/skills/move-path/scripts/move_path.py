#!/usr/bin/env python3
"""Deterministic batched path mover with reference rewriting.

The base path/text contract supports standalone TypeScript/TSX moves without
rewriting source imports. Opt-in family-local modes add checked JavaScript and
bounded Go, Java, PHP, and SwiftPM moves with native rollback.
"""
from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, unquote

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in minimal hosts.
    yaml = None


DEFAULT_INCLUDES = ["**/*.md", "**/*.mdx", "**/*.yml", "**/*.yaml", "**/*.json", "**/*.html"]
DEFAULT_EXCLUDES = [
    ".git/**",
    ".engineering/local/**",
    ".move-path/**",
    "node_modules/**",
    ".venv/**",
    "__pycache__/**",
]
DEFAULT_REPORT_DIR = ".engineering/local/move-path"
LOCAL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
MD_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\n]+)\)")
HTML_REF_RE = re.compile(r"(?P<attr>\b(?:href|src)=)(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
TS_IMPORT_RE = re.compile(
    r"""(?mx)
    ^[ \t]*
    (?:
        (?:import|export)[ \t]+(?:type[ \t]+)?[^;\"']*?[ \t]+from[ \t]+
      | import[ \t]*
    )
    (?P<quote>[\"'])(?P<specifier>[^\"'\\\n]+)(?P=quote)
    """
)
TYPESCRIPT_SUFFIXES = (".ts", ".tsx", ".mts", ".cts")
TYPESCRIPT_MODULE_SUFFIXES = (".ts", ".tsx", ".d.ts")
JAVASCRIPT_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs")
GO_PACKAGE_MOVE_MINIMUM = (1, 22, 0)
GO_PACKAGE_MOVE_MINIMUM_TEXT = "1.22"
GO_NON_SOURCE_TEXT_SUFFIXES = frozenset({".json", ".md", ".toml", ".txt", ".yaml", ".yml"})
GO_NON_SOURCE_SKIP_PARTS = frozenset({".git", ".move-path", ".venv", "__pycache__", "generated", "node_modules", "vendor"})
JAVA_PACKAGE_MOVE_MINIMUM = 17
JAVA_SKIP_PARTS = frozenset({".git", ".move-path", ".venv", "build", "dist", "generated", "gen", "node_modules", "reports", "target", "vendor"})
JAVA_RUNTIME_SUFFIXES = frozenset({".json", ".properties", ".toml", ".xml", ".yaml", ".yml"})
PHP_NAMESPACE_MOVE_MINIMUM = (8, 1, 0)
PHP_NAMESPACE_MOVE_MINIMUM_TEXT = "8.1"
PHP_SKIP_PARTS = frozenset({
    ".git", ".move-path", ".venv", "build", "dist", "generated", "gen",
    "node_modules", "reports", "target", "vendor",
})
GENERATED_TEXT_MARKER_RE = re.compile(r"(?im)^\s*(?:(?://|#|<!--)\s*)?code generated .*do not edit")
JAVA_GENERATED_ANNOTATION_RE = re.compile(
    r"(?m)^\s*@(?:javax\.annotation\.processing\.)?Generated(?:\s*\(|\s*$)"
)
EMITTED_SPECIFIER_SOURCE_SUFFIXES = {
    ".js": (".ts", ".tsx", ".d.ts"),
    ".mjs": (".mts", ".d.mts"),
    ".cjs": (".cts", ".d.cts"),
}


@dataclasses.dataclass(frozen=True)
class MoveSpec:
    move_id: str
    src: str
    dst: str
    mode: str


@dataclasses.dataclass(frozen=True)
class Replacement:
    file_before: str
    file_after: str
    start: int
    end: int
    old: str
    new: str
    kind: str
    confidence: str
    target_before: str
    target_after: str


@dataclasses.dataclass(frozen=True)
class Suggestion:
    file_before: str
    file_after: str
    lineno: int
    kind: str
    token: str
    target_after: str | None
    reason: str


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _has_magic(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def repo_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def normalize_plan_path(raw: str, root: Path) -> str:
    value = str(raw).strip()
    if not value:
        raise ValueError("empty path in move plan")
    value = value.replace("\\", "/")
    trailing_slash = value.endswith("/")
    if re.match(r"^[A-Za-z]:/", value):
        value = Path(value).resolve().relative_to(root.resolve()).as_posix()
    elif value.startswith("/"):
        value = value.lstrip("/")
    value = value.removeprefix("./")
    while "//" in value:
        value = value.replace("//", "/")
    value = value.rstrip("/")
    if not value or value == "." or value.startswith("../") or "/../" in value:
        raise ValueError(f"path escapes project root: {raw!r}")
    return value + ("/" if trailing_slash else "")


def strip_dir(path: str) -> str:
    return path.rstrip("/")


def is_under(path: str, parent: str) -> bool:
    parent = parent.rstrip("/")
    return path == parent or path.startswith(parent + "/")


def after_path_for(path: str, moves: list[MoveSpec]) -> str:
    best: tuple[int, MoveSpec] | None = None
    for move in moves:
        src = strip_dir(move.src)
        if is_under(path, src):
            score = len(src)
            if best is None or score > best[0]:
                best = (score, move)
    if best is None:
        return path
    move = best[1]
    src = strip_dir(move.src)
    dst = strip_dir(move.dst)
    if path == src:
        return dst
    return dst + path[len(src):]


def load_plan(plan_path: Path, root: Path) -> dict:
    suffix = plan_path.suffix.lower()
    try:
        text = _read_text(plan_path)
        if suffix == ".json":
            data = json.loads(text)
        elif suffix in {".yml", ".yaml"}:
            if yaml is None:
                raise SystemExit("YAML plans require optional PyYAML; use a .json plan for the stdlib-only path")
            data = yaml.safe_load(text)
        else:
            raise SystemExit("move-path plans must use .json, .yml, or .yaml")
    except SystemExit:
        raise
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read plan {plan_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise SystemExit(f"cannot read plan {plan_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("move-path plan must be a mapping")
    raw_moves = data.get("moves")
    if not isinstance(raw_moves, list) or not raw_moves:
        raise SystemExit("move-path plan must declare at least one move")
    moves: list[MoveSpec] = []
    seen_ids: set[str] = set()
    for i, row in enumerate(raw_moves, 1):
        if not isinstance(row, dict):
            raise SystemExit(f"moves[{i}] must be a mapping")
        src = normalize_plan_path(str(row.get("from", "")), root)
        dst = normalize_plan_path(str(row.get("to", "")), root)
        mode = str(row.get("mode") or row.get("kind") or ("directory" if src.endswith("/") else "file"))
        if mode not in {"file", "directory"}:
            raise SystemExit(f"{src}: mode must be file or directory")
        move_id = str(row.get("id") or strip_dir(src).replace("/", "-"))
        if move_id in seen_ids:
            raise SystemExit(f"duplicate move id: {move_id}")
        seen_ids.add(move_id)
        moves.append(MoveSpec(move_id, strip_dir(src), strip_dir(dst), mode))
    data["_moves"] = moves
    return data


def validate_moves(root: Path, moves: list[MoveSpec]) -> list[dict]:
    blocked: list[dict] = []
    destinations: dict[str, str] = {}
    sources = {m.src for m in moves}
    for move in moves:
        src_path = root / move.src
        dst_path = root / move.dst
        if not src_path.exists():
            blocked.append({"kind": "missing_source", "move": move.move_id, "path": move.src})
        if move.mode == "file" and src_path.exists() and not src_path.is_file():
            blocked.append({"kind": "source_not_file", "move": move.move_id, "path": move.src})
        if move.mode == "directory" and src_path.exists() and not src_path.is_dir():
            blocked.append({"kind": "source_not_directory", "move": move.move_id, "path": move.src})
        if move.src == move.dst:
            blocked.append({"kind": "same_source_destination", "move": move.move_id, "path": move.src})
        if move.dst in destinations:
            blocked.append({
                "kind": "duplicate_destination",
                "move": move.move_id,
                "path": move.dst,
                "first_move": destinations[move.dst],
            })
        destinations[move.dst] = move.move_id
        if dst_path.exists() and move.dst not in sources and move.src.lower() != move.dst.lower():
            blocked.append({"kind": "destination_exists", "move": move.move_id, "path": move.dst})
    for a in moves:
        for b in moves:
            if a is b:
                continue
            if is_under(a.src, b.src) or is_under(a.dst, b.dst):
                if a.src != b.src and a.dst != b.dst:
                    blocked.append({
                        "kind": "nested_move_overlap",
                        "move": a.move_id,
                        "other_move": b.move_id,
                        "path": a.src,
                    })
    return blocked


def validate_applied_moves(root: Path, moves: list[MoveSpec]) -> list[dict]:
    blocked: list[dict] = []
    for move in moves:
        src_path = root / move.src
        dst_path = root / move.dst
        if not dst_path.exists():
            blocked.append({"kind": "missing_destination_after_move", "move": move.move_id, "path": move.dst})
        if src_path.exists() and move.src.lower() != move.dst.lower():
            blocked.append({"kind": "source_still_exists_after_move", "move": move.move_id, "path": move.src})
    return blocked


def plan_patterns(plan: dict) -> tuple[list[str], list[str]]:
    scope = plan.get("reference_scope") or {}
    includes = scope.get("include") or DEFAULT_INCLUDES
    excludes = DEFAULT_EXCLUDES + list(scope.get("exclude") or [])
    return list(includes), list(excludes)


def matches_any(rel: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(rel, pattern[3:]):
            return True
    return False


def iter_scope_files(root: Path, includes: list[str], excludes: list[str]) -> list[str]:
    out: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            rel = repo_rel(path, root)
        except ValueError:
            continue
        if matches_any(rel, excludes):
            continue
        if matches_any(rel, includes):
            out.append(rel)
    return out


def exclude_authority_file(files: list[str], authority_path: Path, root: Path) -> list[str]:
    """Exclude an exact resolved authority input from text scans and rewrites."""
    try:
        authority_rel = repo_rel(authority_path, root)
    except ValueError:
        return files
    return [rel for rel in files if rel != authority_rel]


def iter_typescript_source_files(root: Path, excludes: list[str]) -> list[str]:
    """Collect TS/TSX import-risk sources even when text rewriting excludes them."""
    out: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in TYPESCRIPT_SUFFIXES:
            continue
        rel = repo_rel(path, root)
        if not matches_any(rel, excludes):
            out.append(rel)
    return out


def iter_javascript_source_files(root: Path, excludes: list[str]) -> list[str]:
    out: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in JAVASCRIPT_SUFFIXES:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if not matches_any(rel, excludes) and not (
            "tests" in Path(rel).parts or re.search(r"\.(?:test|spec)\.(?:js|jsx|mjs|cjs)$", rel)
        ):
            out.append(rel)
    return out


def split_target(raw: str) -> tuple[str, str, str]:
    target = raw.strip()
    fragment = ""
    query = ""
    if "#" in target:
        target, frag = target.split("#", 1)
        fragment = "#" + frag
    if "?" in target:
        target, q = target.split("?", 1)
        query = "?" + q
    return target, query, fragment


def is_external_target(raw: str) -> bool:
    target = raw.strip()
    if not target or target.startswith("#"):
        return True
    if target.startswith("//"):
        return True
    m = LOCAL_SCHEME_RE.match(target)
    return bool(m and not re.match(r"^[A-Za-z]:[\\/]", target))


def safe_norm_parts(parts: list[str]) -> str | None:
    out: list[str] = []
    for part in parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not out:
                return None
            out.pop()
        else:
            out.append(part)
    return "/".join(out)


def resolve_reference(target: str, referrer_before: str, root: Path) -> str | None:
    if is_external_target(target):
        return None
    body, _query, _fragment = split_target(target)
    if not body:
        return None
    decoded = unquote(body)
    slashy = decoded.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", slashy):
        try:
            return Path(slashy).resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            return None
    if slashy.startswith("/"):
        candidate = slashy.lstrip("/")
    else:
        base = Path(referrer_before).parent.as_posix()
        parts = [] if base == "." else base.split("/")
        parts.extend(slashy.split("/"))
        candidate = safe_norm_parts(parts)
        if candidate is None:
            return None
    return candidate.rstrip("/")


def format_reference(
    target_before: str,
    target_after: str,
    referrer_after: str,
    original: str,
) -> str:
    _body, query, fragment = split_target(original)
    original_body = split_target(original)[0]
    root_relative = original_body.startswith("/")
    windows_style = "\\" in original_body and "/" not in original_body
    encoded_style = "%" in original_body
    if root_relative:
        value = "/" + target_after
    else:
        start_dir = Path(referrer_after).parent
        rel = os.path.relpath(target_after, start=start_dir.as_posix())
        value = "." if rel == "." else rel.replace(os.sep, "/")
    if windows_style:
        value = value.replace("/", "\\")
    if encoded_style:
        value = quote(value, safe="/\\._-~")
    return value + query + fragment


def rewrite_target(
    original_target: str,
    referrer_before: str,
    referrer_after: str,
    root: Path,
    moves: list[MoveSpec],
) -> tuple[str | None, str | None, str | None]:
    resolved = resolve_reference(original_target, referrer_before, root)
    if resolved is None:
        return None, None, None
    after = after_path_for(resolved, moves)
    new_target = format_reference(resolved, after, referrer_after, original_target)
    if after == resolved and new_target == original_target:
        return None, resolved, after
    return new_target, resolved, after


def normalize_inline_path_token(token: str, root: Path) -> str | None:
    raw = token.strip()
    if not raw or is_external_target(raw):
        return None
    body, _query, _fragment = split_target(raw)
    if not body or body.startswith(("./", "../")):
        return None
    slashy = unquote(body).replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", slashy):
        try:
            return Path(slashy).resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            return None
    if slashy.startswith("/"):
        slashy = slashy.lstrip("/")
    if not slashy or slashy.startswith("../") or "/../" in slashy:
        return None
    return slashy.rstrip("/")


def format_inline_path_token(token: str, target_after: str) -> str:
    body, query, fragment = split_target(token)
    leading_slash = body.startswith("/")
    windows_style = "\\" in body and "/" not in body
    encoded_style = "%" in body
    value = ("/" if leading_slash else "") + target_after
    if windows_style:
        value = value.replace("/", "\\")
    if encoded_style:
        value = quote(value, safe="/\\._-~")
    return value + query + fragment


def mode_for(plan: dict, key: str, default: str = "ignore") -> str:
    rewrite = plan.get("rewrite") or {}
    value = str(rewrite.get(key, default))
    if value not in {"update", "suggest", "ignore"}:
        raise SystemExit(f"rewrite.{key} must be update, suggest, or ignore")
    return value


def code_import_mode(plan: dict) -> str:
    """Return the only supported source-import policy without implying safety."""
    value = str((plan.get("rewrite") or {}).get("code_imports", "ignore"))
    if value not in {"ignore", "update-javascript", "update-go", "update-java", "update-php", "update-swift"}:
        raise SystemExit("rewrite.code_imports only supports ignore, update-javascript, update-go, update-java, update-php, or update-swift; TypeScript imports require a resolver-aware move")
    return value


def _go_version(value: str) -> tuple[int, int, int] | None:
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.(\d+))?\b", value)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def _go_minimum(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", value.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def go_package_symlink_blocks(root: Path, package_path: Path) -> list[dict]:
    """Reject symlinked shapes before a package-directory move can escape its tree."""
    blocked: list[dict] = []
    for path in sorted(package_path.rglob("*")):
        if path.is_symlink():
            blocked.append({"kind": "go_symlink_in_package", "path": path.relative_to(root).as_posix()})
    return blocked


def non_go_old_import_path_blocks(
    root: Path,
    old_import: str,
    authority_path: Path,
    report_dir: Path,
) -> list[dict]:
    """Find stale Go package identities only in bounded, first-party text files.

    The Go helper already rejects dynamic uses in Go source. This separate scan
    deliberately does not rewrite non-Go strings: config, documentation, and
    runtime data can attach semantics to an import-shaped value that a generic
    textual replacement cannot prove safe. Generated, vendored, symlinked, and
    binary inputs are outside the first-party source boundary.
    """
    try:
        authority_rel = authority_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        authority_rel = None
    excluded_paths = {(report_dir / name).resolve() for name in ("report.json", "report.md")}
    blocked: list[dict] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in GO_NON_SOURCE_TEXT_SUFFIXES:
            continue
        if path.resolve() in excluded_paths:
            continue
        rel = path.relative_to(root).as_posix()
        parts = Path(rel).parts
        if rel == authority_rel or any(part in GO_NON_SOURCE_SKIP_PARTS for part in parts):
            continue
        try:
            contents = path.read_bytes()
        except OSError as exc:
            blocked.append({"kind": "go_non_go_text_unreadable", "path": rel, "detail": str(exc)})
            continue
        if b"\0" in contents:
            continue
        try:
            text = contents.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if GENERATED_TEXT_MARKER_RE.search(text[:2048]):
            continue
        offset = text.find(old_import)
        if offset >= 0:
            blocked.append({
                "kind": "go_dynamic_old_import_path_non_go",
                "path": rel,
                "line": line_for_offset(text, offset),
            })
    return blocked


def go_tooling(root: Path, moves: list[MoveSpec], *, post_apply: bool = False) -> dict:
    """Discover the one-root-module contract without installing anything."""
    outcome: dict = {"status": "unsupported", "blocked": []}
    if len(moves) != 1:
        outcome["blocked"].append({"kind": "go_move_count_unsupported"})
        return outcome
    move = moves[0]
    if move.mode != "directory":
        outcome["blocked"].append({"kind": "go_package_move_must_be_directory", "path": move.src})
        return outcome
    package_path = root / (move.dst if post_apply else move.src)
    if not package_path.is_dir():
        outcome["blocked"].append({
            "kind": "go_destination_package_missing_after_move" if post_apply else "go_package_move_must_be_directory",
            "path": move.dst if post_apply else move.src,
        })
        return outcome
    if any("vendor" == part for part in (*Path(move.src).parts, *Path(move.dst).parts)):
        outcome["blocked"].append({"kind": "go_vendor_path_unsupported", "path": move.src})
        return outcome
    if (root / move.src).is_symlink() or (root / move.dst).is_symlink():
        outcome["blocked"].append({"kind": "go_symlink_boundary", "path": move.src})
        return outcome
    if symlink_blocks := go_package_symlink_blocks(root, package_path):
        outcome["blocked"].extend(symlink_blocks)
        return outcome
    go = shutil.which("go")
    gofmt = shutil.which("gofmt")
    if go is None:
        outcome["blocked"].append({"kind": "go_tool_missing", "tool": "go"})
        return outcome
    if gofmt is None:
        outcome["blocked"].append({"kind": "go_tool_missing", "tool": "gofmt"})
        return outcome
    try:
        version_result = subprocess.run([go, "version"], cwd=root, text=True, capture_output=True, check=False)
        workspace = subprocess.run([go, "env", "GOWORK"], cwd=root, text=True, capture_output=True, check=False)
        module_file = subprocess.run([go, "env", "GOMOD"], cwd=root, text=True, capture_output=True, check=False)
        module = subprocess.run(
            [go, "mod", "edit", "-json"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "GOWORK": "off"},
        )
    except OSError as exc:
        outcome["blocked"].append({"kind": "go_tool_invocation_failed", "detail": str(exc)})
        return outcome
    actual = _go_version(version_result.stdout + version_result.stderr)
    if version_result.returncode != 0 or actual is None:
        outcome["blocked"].append({"kind": "go_version_unreadable", "detail": version_result.stderr.strip()})
        return outcome
    if workspace.returncode != 0 or workspace.stdout.strip():
        outcome["blocked"].append({"kind": "go_workspace_unsupported", "detail": workspace.stdout.strip() or workspace.stderr.strip()})
        return outcome
    expected_mod = (root / "go.mod").resolve()
    reported_mod = Path(module_file.stdout.strip()).resolve() if module_file.stdout.strip() else None
    if module_file.returncode != 0 or reported_mod != expected_mod:
        outcome["blocked"].append({"kind": "go_root_module_required", "detail": module_file.stdout.strip() or module_file.stderr.strip()})
        return outcome
    try:
        module_payload = json.loads(module.stdout)
    except json.JSONDecodeError:
        module_payload = None
    if module.returncode != 0 or not isinstance(module_payload, dict):
        outcome["blocked"].append({"kind": "go_module_metadata_unavailable", "detail": module.stderr.strip()})
        return outcome
    path = ((module_payload.get("Module") or {}).get("Path"))
    minimum_text = module_payload.get("Go")
    minimum = _go_minimum(str(minimum_text or ""))
    if not isinstance(path, str) or not path or minimum is None:
        outcome["blocked"].append({"kind": "go_module_version_required"})
        return outcome
    required_minimum = max(minimum, GO_PACKAGE_MOVE_MINIMUM)
    required_minimum_text = minimum_text if minimum >= GO_PACKAGE_MOVE_MINIMUM else GO_PACKAGE_MOVE_MINIMUM_TEXT
    if actual < required_minimum:
        outcome["blocked"].append({
            "kind": "go_version_too_old",
            "actual": version_result.stdout.strip(),
            "minimum": required_minimum_text,
        })
        return outcome
    outcome.update({
        "status": "complete",
        "go": {
            "path": go,
            "version": version_result.stdout.strip(),
            "minimum": required_minimum_text,
            "module_minimum": minimum_text,
        },
        "gofmt": {"path": gofmt},
        "module": {"path": path, "go_mod": expected_mod.as_posix()},
    })
    return outcome


def checked_go(root: Path, moves: list[MoveSpec], tooling: dict) -> dict:
    """Ask the copied, stdlib-only Go helper for exact import-literal spans."""
    if tooling.get("status") != "complete":
        return tooling
    move = moves[0]
    command = [
        tooling["go"]["path"],
        "run",
        str(Path(__file__).with_name("go_package_import_spans.go")),
        "--project-root",
        str(root),
        "--from",
        move.src,
        "--to",
        move.dst,
        "--module",
        tooling["module"]["path"],
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "GOWORK": "off"},
    )
    try:
        outcome = json.loads(result.stdout)
    except json.JSONDecodeError:
        outcome = {"status": "failed", "error": "Go helper emitted invalid JSON", "blocked": []}
    outcome["returncode"] = result.returncode
    outcome["tooling"] = tooling
    if result.returncode != 0 and outcome.get("status") == "complete":
        outcome["status"] = "failed"
        outcome["error"] = result.stderr.strip() or "Go helper failed"
    return outcome


def utf8_offset(text: str, offset: int) -> int:
    """Convert Go token byte offsets to Python string offsets."""
    total = 0
    for index, char in enumerate(text):
        if total >= offset:
            return index
        total += len(char.encode("utf-8"))
    return len(text)


def go_rewrites(root: Path, moves: list[MoveSpec], outcome: dict) -> tuple[list[Replacement], list[dict]]:
    replacements: list[Replacement] = []
    blocked = list(outcome.get("blocked") or [])
    if outcome.get("status") != "complete":
        return replacements, blocked
    for item in outcome.get("spans", []):
        source = item["file"]
        text = _read_text(root / source)
        start = utf8_offset(text, int(item["start"]))
        end = utf8_offset(text, int(item["end"]))
        old_literal = item["old_literal"]
        if text[start:end] != old_literal:
            blocked.append({"kind": "go_import_span_mismatch", "path": source, "line": item["line"]})
            continue
        replacements.append(Replacement(
            file_before=source,
            file_after=after_path_for(source, moves),
            start=start,
            end=end,
            old=old_literal,
            new=item["new_literal"],
            kind="go_import",
            confidence="auto",
            target_before=item["old"],
            target_after=item["new"],
        ))
    return replacements, blocked


def java_package_symlink_blocks(root: Path, package_path: Path) -> list[dict]:
    """Reject a package tree containing links before any Java move is planned."""
    return [
        {"kind": "java_symlink_in_package", "path": path.relative_to(root).as_posix()}
        for path in sorted(package_path.rglob("*"))
        if path.is_symlink()
    ]


def traversed_symlink(root: Path, path: Path) -> str | None:
    """Return the first existing symlink component beneath root."""
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            return current.relative_to(root).as_posix()
        if not current.exists():
            break
    return None


def java_generated_source(path: Path) -> bool:
    text = _read_text(path)
    return bool(
        GENERATED_TEXT_MARKER_RE.search(text[:2048])
        or JAVA_GENERATED_ANNOTATION_RE.search(text)
    )


def java_runtime_old_package_blocks(root: Path, old_package: str) -> list[dict]:
    """Find first-party resource identities that a source AST cannot rewrite."""
    blocked: list[dict] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        lower_parts = tuple(part.lower() for part in relative.parts)
        if any(part in JAVA_SKIP_PARTS for part in lower_parts):
            continue
        is_service = "meta-inf" in lower_parts and "services" in lower_parts
        is_resource = "resources" in lower_parts and path.suffix.lower() in JAVA_RUNTIME_SUFFIXES
        if not is_service and not is_resource:
            continue
        contents = path.read_bytes()
        if b"\0" in contents:
            continue
        try:
            text = contents.decode("utf-8")
        except UnicodeDecodeError:
            continue
        offset = text.find(old_package)
        if offset >= 0:
            blocked.append({
                "kind": "java_runtime_old_package",
                "path": relative.as_posix(),
                "line": line_for_offset(text, offset),
            })
    return blocked


def java_tooling(root: Path, moves: list[MoveSpec], *, post_apply: bool = False) -> dict:
    """Validate the bounded standalone-JDK leaf-package contract."""
    outcome: dict = {"status": "unsupported", "blocked": []}
    if len(moves) != 1:
        outcome["blocked"].append({"kind": "java_move_count_unsupported"})
        return outcome
    move = moves[0]
    if move.mode != "directory":
        outcome["blocked"].append({"kind": "java_package_move_must_be_directory", "path": move.src})
        return outcome
    package_rel = move.dst if post_apply else move.src
    package_path = root / package_rel
    source_link = traversed_symlink(root, root / move.src)
    destination_link = traversed_symlink(root, root / move.dst)
    if source_link or destination_link:
        outcome["blocked"].append({"kind": "java_symlink_boundary", "path": source_link or destination_link})
        return outcome
    if not package_path.is_dir():
        outcome["blocked"].append({
            "kind": "java_destination_package_missing_after_move" if post_apply else "java_package_move_must_be_directory",
            "path": package_rel,
        })
        return outcome
    if any(part.lower() in JAVA_SKIP_PARTS for part in (*Path(move.src).parts, *Path(move.dst).parts)):
        outcome["blocked"].append({"kind": "java_excluded_path_unsupported", "path": package_rel})
        return outcome
    if (root / move.src).is_symlink() or (root / move.dst).is_symlink():
        outcome["blocked"].append({"kind": "java_symlink_boundary", "path": package_rel})
        return outcome
    if symlinks := java_package_symlink_blocks(root, package_path):
        outcome["blocked"].extend(symlinks)
        return outcome
    nested = [path for path in package_path.iterdir() if path.is_dir()]
    if nested:
        outcome["blocked"].append({
            "kind": "java_package_not_leaf",
            "paths": [path.relative_to(root).as_posix() for path in sorted(nested)],
        })
        return outcome
    generated = []
    for path in sorted(package_path.glob("*.java")):
        if java_generated_source(path):
            generated.append(path.relative_to(root).as_posix())
    if generated:
        outcome["blocked"].append({"kind": "java_generated_source", "paths": generated})
        return outcome
    java = shutil.which("java")
    javac = shutil.which("javac")
    if java is None or javac is None:
        outcome["blocked"].append({"kind": "java_tool_missing", "tools": [name for name, value in (("java", java), ("javac", javac)) if value is None]})
        return outcome
    version = subprocess.run([java, "-version"], cwd=root, text=True, capture_output=True, check=False)
    javac_version = subprocess.run([javac, "-version"], cwd=root, text=True, capture_output=True, check=False)
    match = re.search(r'(?i)(?:version\s+"?|javac\s+)(\d+)', version.stdout + version.stderr + "\n" + javac_version.stdout + javac_version.stderr)
    if version.returncode != 0 or javac_version.returncode != 0 or match is None:
        outcome["blocked"].append({"kind": "java_version_unreadable"})
        return outcome
    feature = int(match.group(1))
    if feature < JAVA_PACKAGE_MOVE_MINIMUM:
        outcome["blocked"].append({"kind": "java_version_too_old", "actual": feature, "minimum": JAVA_PACKAGE_MOVE_MINIMUM})
        return outcome
    outcome.update({
        "status": "complete",
        "java": {"path": java, "version": (version.stderr or version.stdout).splitlines()[0], "minimum": JAVA_PACKAGE_MOVE_MINIMUM},
        "javac": {"path": javac, "version": (javac_version.stdout or javac_version.stderr).strip()},
    })
    return outcome


def checked_java(
    root: Path,
    moves: list[MoveSpec],
    tooling: dict,
    *,
    include_runtime_blocks: bool = True,
) -> dict:
    """Ask the copied JDK-only helper for attributed package/reference spans."""
    if tooling.get("status") != "complete":
        return tooling
    move = moves[0]
    command = [
        tooling["java"]["path"],
        str(Path(__file__).with_name("java_package_reference_spans.java")),
        "--project-root",
        str(root),
        "--from",
        move.src,
        "--to",
        move.dst,
    ]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    try:
        outcome = json.loads(result.stdout)
    except json.JSONDecodeError:
        outcome = {"status": "failed", "error": "Java helper emitted invalid JSON", "blocked": []}
    outcome["returncode"] = result.returncode
    outcome["tooling"] = tooling
    if outcome.get("old_package"):
        generated_consumers = sorted({
            item["file"]
            for item in outcome.get("spans", [])
            if java_generated_source(root / item["file"])
        })
        runtime_blocks = (
            java_runtime_old_package_blocks(root, outcome["old_package"])
            if include_runtime_blocks
            else []
        )
        if generated_consumers:
            outcome.setdefault("blocked", []).append({
                "kind": "java_generated_consumer",
                "paths": generated_consumers,
            })
            outcome["status"] = "unsupported"
        elif runtime_blocks:
            outcome.setdefault("blocked", []).extend(runtime_blocks)
            outcome["status"] = "partial"
    if result.returncode != 0 and outcome.get("status") == "complete":
        outcome["status"] = "failed"
        outcome["error"] = result.stderr.strip() or "Java helper failed"
    return outcome


def java_rewrites(root: Path, moves: list[MoveSpec], outcome: dict) -> tuple[list[Replacement], list[dict]]:
    replacements: list[Replacement] = []
    blocked = list(outcome.get("blocked") or [])
    if outcome.get("status") != "complete":
        return replacements, blocked
    for item in outcome.get("spans", []):
        source = item["file"]
        text = _read_text(root / source)
        start = utf16_offset(text, int(item["start"]))
        end = utf16_offset(text, int(item["end"]))
        if text[start:end] != item["old_text"]:
            blocked.append({"kind": "java_reference_span_mismatch", "path": source, "line": item["line"]})
            continue
        replacements.append(Replacement(
            file_before=source,
            file_after=after_path_for(source, moves),
            start=start,
            end=end,
            old=item["old_text"],
            new=item["new_text"],
            kind=item["kind"],
            confidence="auto",
            target_before=outcome["old_package"],
            target_after=outcome["new_package"],
        ))
    return replacements, blocked


def iter_java_source_files(root: Path) -> list[str]:
    return [
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*.java"))
        if path.is_file()
        and not path.is_symlink()
        and not any(part.lower() in JAVA_SKIP_PARTS for part in path.relative_to(root).parts)
    ]


def run_java_compile(root: Path, javac: str, files: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="move-path-java-") as classes:
        return _native_result(
            [javac, "--release", "17", "-proc:none", "-d", classes, *[str(root / path) for path in files]],
            root,
        )


def _php_version(value: str) -> tuple[int, int, int] | None:
    match = re.search(r"\bPHP\s+(\d+)\.(\d+)(?:\.(\d+))?", value)
    if match is None:
        return None
    return tuple(int(part or 0) for part in match.groups())


def php_generated_source(path: Path) -> bool:
    return bool(GENERATED_TEXT_MARKER_RE.search(_read_text(path)[:2048]))


def _psr4_string_mappings(composer: dict) -> list[tuple[str, str]]:
    autoload = composer.get("autoload")
    psr4 = autoload.get("psr-4") if isinstance(autoload, dict) else None
    if not isinstance(psr4, dict):
        return []
    mappings: list[tuple[str, str]] = []
    for prefix, raw_path in psr4.items():
        if not isinstance(prefix, str) or not isinstance(raw_path, str):
            continue
        candidate = raw_path.replace("\\", "/")
        if candidate.startswith("/") or re.match(r"^[A-Za-z]:/", candidate):
            continue
        normalized = candidate.removeprefix("./").strip("/")
        if ".." in Path(normalized).parts:
            continue
        if normalized:
            mappings.append((prefix.rstrip("\\"), normalized))
    return mappings


def _namespace_for_psr4_path(prefix: str, source_root: str, path: str) -> str | None:
    if not is_under(path, source_root):
        return None
    relative = path[len(source_root):].strip("/")
    suffix = relative.replace("/", "\\")
    namespace = prefix + ("\\" + suffix if suffix else "")
    if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in namespace.split("\\")):
        return None
    return namespace


def _php_config(plan: dict, root: Path) -> tuple[str | None, list[str], list[dict]]:
    section = plan.get("php")
    blocked: list[dict] = []
    if not isinstance(section, dict):
        return None, [], [{"kind": "php_config_required"}]
    raw_binary = section.get("binary")
    if raw_binary is None:
        php = shutil.which("php")
    else:
        candidate = Path(str(raw_binary))
        php = (
            str(candidate)
            if candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK)
            else None
        )
        if php is None:
            blocked.append({"kind": "php_binary_unavailable", "path": str(raw_binary)})
    raw_scripts = section.get("verification_scripts")
    if not isinstance(raw_scripts, list) or not raw_scripts:
        blocked.append({"kind": "php_verification_scripts_required"})
        scripts: list[str] = []
    else:
        scripts = []
        for raw in raw_scripts:
            try:
                relative = strip_dir(normalize_plan_path(str(raw), root))
            except ValueError as exc:
                blocked.append({"kind": "php_verification_script_invalid", "detail": str(exc)})
                continue
            path = root / relative
            if path.suffix.lower() != ".php" or not path.is_file() or path.is_symlink():
                blocked.append({"kind": "php_verification_script_unavailable", "path": relative})
            else:
                scripts.append(relative)
        labels = [Path(script).stem for script in scripts]
        if len(labels) != len(set(labels)):
            blocked.append({"kind": "php_verification_script_names_ambiguous"})
    return php, scripts, blocked


def _iter_php_files(root: Path) -> list[str]:
    return [
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*.php"))
        if path.is_file() and not path.is_symlink() and ".git" not in path.relative_to(root).parts
    ]


def _php_excluded_identity_blocks(
    root: Path,
    excluded: list[str],
    old_namespace: str,
    old_path: str,
) -> list[dict]:
    needles = (old_namespace, f"/{old_path.strip('/')}/", f"{old_path.strip('/')}/")
    blocked: list[dict] = []
    for relative in excluded:
        text = _read_text(root / relative)
        matches = [needle for needle in needles if needle in text]
        if matches:
            blocked.append({
                "kind": "php_excluded_old_identity",
                "path": relative,
                "identities": sorted(set(matches)),
            })
    return blocked


def php_tooling(
    root: Path,
    plan: dict,
    moves: list[MoveSpec],
    *,
    post_apply: bool = False,
) -> dict:
    """Validate one Composer PSR-4 leaf namespace-directory move."""
    outcome: dict = {"status": "unsupported", "blocked": []}
    if len(moves) != 1:
        outcome["blocked"].append({"kind": "php_move_count_unsupported"})
        return outcome
    move = moves[0]
    if move.mode != "directory":
        outcome["blocked"].append({"kind": "php_namespace_move_must_be_directory", "path": move.src})
        return outcome
    source_link = traversed_symlink(root, root / move.src)
    destination_link = traversed_symlink(root, root / move.dst)
    if source_link or destination_link:
        outcome["blocked"].append({"kind": "php_symlink_boundary", "path": source_link or destination_link})
        return outcome
    current_relative = move.dst if post_apply else move.src
    current = root / current_relative
    if not current.is_dir():
        outcome["blocked"].append({
            "kind": "php_destination_namespace_missing_after_move" if post_apply else "php_namespace_move_must_be_directory",
            "path": current_relative,
        })
        return outcome
    if any(part.lower() in PHP_SKIP_PARTS for part in (*Path(move.src).parts, *Path(move.dst).parts)):
        outcome["blocked"].append({"kind": "php_excluded_path_unsupported", "path": current_relative})
        return outcome
    symlinks = [
        path.relative_to(root).as_posix()
        for path in sorted(current.rglob("*"))
        if path.is_symlink()
    ]
    if symlinks:
        outcome["blocked"].append({"kind": "php_symlink_in_namespace", "paths": symlinks})
        return outcome
    nested = [path.relative_to(root).as_posix() for path in sorted(current.iterdir()) if path.is_dir()]
    if nested:
        outcome["blocked"].append({"kind": "php_namespace_not_leaf", "paths": nested})
        return outcome
    moved_files = [
        path.relative_to(root).as_posix()
        for path in sorted(current.iterdir())
        if path.is_file()
    ]
    if not moved_files or any(Path(path).suffix.lower() != ".php" for path in moved_files):
        outcome["blocked"].append({"kind": "php_namespace_requires_only_php_sources", "paths": moved_files})
        return outcome
    generated = [path for path in moved_files if php_generated_source(root / path)]
    if generated:
        outcome["blocked"].append({"kind": "php_generated_source", "paths": generated})
        return outcome

    composer_path = root / "composer.json"
    try:
        composer = json.loads(composer_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "status": "failed",
            "error": f"composer.json is unavailable or malformed: {exc}",
            "blocked": [{"kind": "php_composer_metadata_failed", "detail": str(exc)}],
        }
    mappings = _psr4_string_mappings(composer)
    candidates = []
    for prefix, source_root in mappings:
        old_namespace = _namespace_for_psr4_path(prefix, source_root, move.src)
        new_namespace = _namespace_for_psr4_path(prefix, source_root, move.dst)
        if old_namespace and new_namespace:
            candidates.append((len(source_root), prefix, source_root, old_namespace, new_namespace))
    if not candidates:
        outcome["blocked"].append({"kind": "php_psr4_mapping_required"})
        return outcome
    candidates.sort(reverse=True)
    longest = candidates[0][0]
    selected = [candidate for candidate in candidates if candidate[0] == longest]
    if len(selected) != 1:
        outcome["blocked"].append({"kind": "php_psr4_mapping_ambiguous"})
        return outcome
    _, prefix, source_root, old_namespace, new_namespace = selected[0]

    php, verification_files, config_blocks = _php_config(plan, root)
    outcome["blocked"].extend(config_blocks)
    if php is None:
        if not any(item["kind"] == "php_binary_unavailable" for item in outcome["blocked"]):
            outcome["blocked"].append({"kind": "php_tool_missing", "tool": "php"})
        return outcome
    version_result = subprocess.run([php, "-v"], cwd=root, text=True, capture_output=True, check=False)
    version = _php_version(version_result.stdout + version_result.stderr)
    if version_result.returncode != 0 or version is None:
        outcome["blocked"].append({"kind": "php_version_unreadable"})
        return outcome
    if version < PHP_NAMESPACE_MOVE_MINIMUM:
        outcome["blocked"].append({
            "kind": "php_version_too_old",
            "actual": ".".join(str(part) for part in version),
            "minimum": PHP_NAMESPACE_MOVE_MINIMUM_TEXT,
        })
        return outcome
    if config_blocks:
        return outcome

    source_files: set[str] = set()
    for _mapping_prefix, mapping_root in mappings:
        mapping_path = root / mapping_root
        if not mapping_path.is_dir() or mapping_path.is_symlink():
            continue
        for path in sorted(mapping_path.rglob("*.php")):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part.lower() in PHP_SKIP_PARTS for part in relative.parts):
                continue
            if php_generated_source(path):
                continue
            source_files.add(relative.as_posix())
    analyzed_files = sorted(source_files | set(verification_files))
    excluded_files = sorted(set(_iter_php_files(root)) - set(analyzed_files))
    excluded_blocks = _php_excluded_identity_blocks(root, excluded_files, old_namespace, move.src)
    if excluded_blocks:
        return {
            **outcome,
            "status": "unsupported",
            "blocked": [*outcome["blocked"], *excluded_blocks],
            "php": {
                "path": php,
                "version": (version_result.stdout or version_result.stderr).splitlines()[0],
                "minimum": PHP_NAMESPACE_MOVE_MINIMUM_TEXT,
            },
            "psr4": {"prefix": prefix, "source_root": source_root},
            "old_namespace": old_namespace,
            "new_namespace": new_namespace,
            "php_files": analyzed_files,
            "moved_files": moved_files,
            "verification_files": verification_files,
            "excluded_files": excluded_files,
        }
    outcome.update({
        "status": "complete",
        "php": {
            "path": php,
            "version": (version_result.stdout or version_result.stderr).splitlines()[0],
            "minimum": PHP_NAMESPACE_MOVE_MINIMUM_TEXT,
        },
        "psr4": {"prefix": prefix, "source_root": source_root},
        "old_namespace": old_namespace,
        "new_namespace": new_namespace,
        "php_files": analyzed_files,
        "moved_files": moved_files,
        "verification_files": verification_files,
        "excluded_files": excluded_files,
    })
    return outcome


def checked_php(root: Path, moves: list[MoveSpec], tooling: dict, *, post_apply: bool = False) -> dict:
    """Ask PHP's tokenizer for exact syntax spans; never infer dynamic identities."""
    if tooling.get("status") != "complete":
        return tooling
    move = moves[0]
    request = {
        "project_root": str(root),
        "old_namespace": tooling["old_namespace"],
        "new_namespace": tooling["new_namespace"],
        "old_path": move.src,
        "new_path": move.dst,
        "moved_path": move.dst if post_apply else move.src,
        "expected_moved_namespace": tooling["new_namespace"] if post_apply else tooling["old_namespace"],
        "files": tooling["php_files"],
    }
    result = subprocess.run(
        [tooling["php"]["path"], str(Path(__file__).with_name("php_namespace_reference_spans.php"))],
        cwd=root,
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        outcome = json.loads(result.stdout)
    except json.JSONDecodeError:
        outcome = {"status": "failed", "error": "PHP helper emitted invalid JSON", "blocked": []}
    outcome["returncode"] = result.returncode
    outcome["tooling"] = tooling
    for key in (
        "old_namespace", "new_namespace", "php_files", "moved_files",
        "verification_files", "excluded_files",
    ):
        outcome[key] = tooling.get(key)
    if post_apply and outcome.get("spans"):
        outcome.setdefault("blocked", []).append({
            "kind": "php_old_identity_remains_after_move",
            "paths": sorted({item["file"] for item in outcome["spans"]}),
        })
        outcome["status"] = "partial"
    if result.returncode != 0 and outcome.get("status") == "complete":
        outcome["status"] = "failed"
        outcome["error"] = result.stderr.strip() or "PHP helper failed"
    return outcome


def php_rewrites(root: Path, moves: list[MoveSpec], outcome: dict) -> tuple[list[Replacement], list[dict]]:
    replacements: list[Replacement] = []
    blocked = list(outcome.get("blocked") or [])
    if outcome.get("status") != "complete":
        return replacements, blocked
    for item in outcome.get("spans", []):
        source = item["file"]
        text = _read_text(root / source)
        start = utf8_offset(text, int(item["start"]))
        end = utf8_offset(text, int(item["end"]))
        if text[start:end] != item["old_text"]:
            blocked.append({"kind": "php_reference_span_mismatch", "path": source, "line": item["line"]})
            continue
        replacements.append(Replacement(
            file_before=source,
            file_after=after_path_for(source, moves),
            start=start,
            end=end,
            old=item["old_text"],
            new=item["new_text"],
            kind=item["kind"],
            confidence="auto",
            target_before=outcome["old_namespace"],
            target_after=outcome["new_namespace"],
        ))
    return replacements, blocked


def run_php_script(root: Path, php: str, script: str) -> dict:
    return _native_result([php, script], root)


def _native_result(
    command: list[str], root: Path, *, write: bool = False, require_empty_stdout: bool = False
) -> dict:
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "GOWORK": "off"},
    )
    return {
        "argv": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "write": write,
        "passed": result.returncode == 0 and (not require_empty_stdout or not result.stdout),
    }


def run_gofmt(root: Path, gofmt: str, files: list[str], *, write: bool = False) -> dict:
    command = [gofmt, "-w" if write else "-d", *[str(root / path) for path in files]]
    return _native_result(command, root, write=write, require_empty_stdout=not write)


def run_go_test(root: Path, go: str) -> dict:
    return _native_result([go, "test", "./..."], root)


def javascript_config(plan: dict, root: Path) -> Path | None:
    section = plan.get("javascript") or {}
    if not isinstance(section, dict) or not section.get("config"):
        return None
    try:
        return (root / normalize_plan_path(str(section["config"]), root)).resolve()
    except ValueError as exc:
        raise SystemExit(f"invalid javascript.config: {exc}") from exc


def checked_javascript(root: Path, config: Path | None, files: list[str]) -> dict:
    if config is None:
        return {"status": "unsupported", "error": "javascript.config is required for update-javascript"}
    node = shutil.which("node")
    if node is None:
        return {"status": "unsupported", "error": "node is not available on PATH"}
    command = [
        node,
        str(Path(__file__).with_name("javascript_module_spans.mjs")),
        "--project-root",
        str(root),
        "--config",
        str(config),
        *[str(root / file) for file in files],
    ]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    try:
        outcome = json.loads(result.stdout)
    except json.JSONDecodeError:
        outcome = {"status": "failed", "error": "JavaScript helper emitted invalid JSON"}
    outcome["returncode"] = result.returncode
    return outcome


def utf16_offset(text: str, offset: int) -> int:
    units = 0
    for index, char in enumerate(text):
        if units >= offset:
            return index
        units += 2 if ord(char) > 0xFFFF else 1
    return len(text)


def javascript_rewrites(root: Path, moves: list[MoveSpec], outcome: dict) -> tuple[list[Replacement], list[dict]]:
    replacements: list[Replacement] = []
    blocked: list[dict] = []
    for item in outcome.get("unsupported", []):
        if after_path_for(item["file"], moves) != item["file"]:
            blocked.append({"kind": "javascript_dynamic_import", "path": item["file"], "detail": item["kind"]})
    for item in outcome.get("module_specifiers", []):
        source = item["file"]
        specifier = item["specifier"]
        body, query, fragment = split_target(specifier)
        resolved = resolve_reference(body, source, root) if not query and not fragment else None
        source_after = after_path_for(source, moves)
        target_after = after_path_for(resolved, moves) if resolved else None
        affected = source_after != source or (resolved is not None and target_after != resolved)
        if not affected or not body.startswith(("./", "../")):
            continue
        if (
            resolved is None
            or Path(resolved).suffix.lower() not in JAVASCRIPT_SUFFIXES
            or not (root / resolved).is_file()
            or (root / resolved).is_symlink()
        ):
            blocked.append({"kind": "javascript_import_unresolved", "path": source, "line": item["line"], "specifier": specifier})
            continue
        text = _read_text(root / source)
        start = utf16_offset(text, item["start"])
        end = utf16_offset(text, item["end"])
        replacement = Replacement(
            file_before=source,
            file_after=source_after,
            start=start,
            end=end,
            old=specifier,
            new=format_reference(resolved, target_after or resolved, source_after, specifier),
            kind="javascript_import",
            confidence="auto",
            target_before=resolved,
            target_after=target_after or resolved,
        )
        if replacement.old != replacement.new:
            replacements.append(replacement)
    return replacements, blocked


def resolve_typescript_import(
    specifier: str,
    referrer_before: str,
    root: Path,
    moves: list[MoveSpec],
) -> str | None:
    """Resolve only local TS/TSX spellings enough to report ignored move risk.

    This is deliberately not a TypeScript module resolver: aliases, package
    exports, project references, and compiler options remain unsupported. The
    filesystem check is enough to identify a relative module whose file is in
    the move map, while leaving import rewriting entirely disabled.
    """
    body, _query, _fragment = split_target(specifier)
    if not body.startswith(("./", "../", "/")):
        return None
    resolved = resolve_reference(specifier, referrer_before, root)
    if resolved is None:
        return None
    emitted_suffix = Path(resolved).suffix.lower()
    source_suffixes = EMITTED_SPECIFIER_SOURCE_SUFFIXES.get(emitted_suffix)
    if source_suffixes is not None:
        stem = resolved.removesuffix(emitted_suffix)
        candidates = [stem + suffix for suffix in source_suffixes]
        candidates.append(resolved)
    elif not resolved.endswith(TYPESCRIPT_MODULE_SUFFIXES):
        candidates = [resolved]
        candidates.extend(resolved + suffix for suffix in TYPESCRIPT_MODULE_SUFFIXES)
        candidates.extend(resolved + "/index" + suffix for suffix in TYPESCRIPT_MODULE_SUFFIXES)
    else:
        candidates = [resolved]
    for candidate in candidates:
        if (root / candidate).is_file() or (root / after_path_for(candidate, moves)).is_file():
            return candidate
    return None


def ignored_typescript_imports(root: Path, files: list[str], moves: list[MoveSpec]) -> list[dict]:
    """Report local TS/TSX imports at risk when their target or referrer moves."""
    ignored: list[dict] = []
    for rel in files:
        if Path(rel).suffix not in TYPESCRIPT_SUFFIXES:
            continue
        try:
            text = _read_text(root / rel)
        except OSError:
            continue
        for match in TS_IMPORT_RE.finditer(text):
            specifier = match.group("specifier")
            before = resolve_typescript_import(specifier, rel, root, moves)
            if before is None:
                continue
            after = after_path_for(before, moves)
            referrer_after = after_path_for(rel, moves)
            if after == before and referrer_after == rel:
                continue
            changed_identity = []
            if after != before:
                changed_identity.append("target")
            if referrer_after != rel:
                changed_identity.append("referrer")
            ignored.append(
                {
                    "file": rel,
                    "file_after": referrer_after,
                    "lineno": line_for_offset(text, match.start("specifier")),
                    "specifier": specifier,
                    "expected_specifier": None,
                    "remediation": "unknown_without_typescript_module_resolution",
                    "changed_identity": changed_identity,
                    "target_before": before,
                    "target_after": after,
                    "reason": "rewrite.code_imports is ignore; TypeScript source imports are not rewritten",
                }
            )
    return ignored


TEXT_PATH_SUFFIX_RE = r"(?:/[A-Za-z0-9._~@%+=:@#-]+)*(?:#[A-Za-z0-9._~@%+=:@#/-]+)?"


def exact_text_path_matches(text: str, move: MoveSpec) -> Iterable[tuple[int, int, str, str, str]]:
    """Yield exact prose path tokens under this move's source.

    The exact-text pass is intentionally conservative, but directory moves
    commonly leave plain prose like "inputs-1/kb" or "kb/evals/foo.md".
    Match the longest path-like token rooted at move.src, then rewrite the
    path portion while preserving an optional Markdown-style fragment.
    """
    for root_prefix in ("", "/"):
        pattern = re.compile(
            r"(?<![\w./-])"
            + re.escape(root_prefix + move.src)
            + r"(?P<suffix>"
            + TEXT_PATH_SUFFIX_RE
            + r")"
            + r"(?![\w/-])"
        )
        for match in pattern.finditer(text):
            old_token = match.group(0).rstrip(".,;:")
            trim_count = len(match.group(0)) - len(old_token)
            suffix = match.group("suffix")
            if trim_count:
                suffix = suffix[:-trim_count]
            path_suffix, sep, fragment = suffix.partition("#")
            target_before = move.src + path_suffix
            target_after = after_path_for(target_before, [move])
            if target_after == target_before:
                continue
            new_token = root_prefix + target_after + (sep + fragment if sep else "")
            yield match.start(), match.end() - trim_count, old_token, target_before, new_token


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def add_replacement(
    replacements: list[Replacement],
    *,
    file_before: str,
    file_after: str,
    start: int,
    end: int,
    old: str,
    new: str,
    kind: str,
    target_before: str,
    target_after: str,
) -> None:
    if old == new:
        return
    replacements.append(
        Replacement(
            file_before=file_before,
            file_after=file_after,
            start=start,
            end=end,
            old=old,
            new=new,
            kind=kind,
            confidence="auto",
            target_before=target_before,
            target_after=target_after,
        )
    )


def detect_references(
    root: Path,
    plan: dict,
    moves: list[MoveSpec],
    files: list[str],
) -> tuple[list[Replacement], list[Suggestion], list[dict]]:
    replacements: list[Replacement] = []
    suggestions: list[Suggestion] = []
    blocked: list[dict] = []
    md_links = mode_for(plan, "markdown_links", "update")
    md_images = mode_for(plan, "markdown_images", "update")
    html_refs = mode_for(plan, "html_href_src", "update")
    backticks = mode_for(plan, "backtick_paths", "update")
    exact_text = mode_for(plan, "exact_text_paths", "suggest")

    for rel in files:
        path = root / rel
        # Source code is handled only by its language-specific path.
        if path.suffix.lower() in {*TYPESCRIPT_SUFFIXES, *JAVASCRIPT_SUFFIXES}:
            continue
        try:
            text = _read_text(path)
        except OSError as exc:
            blocked.append({"kind": "cannot_read", "path": rel, "detail": str(exc)})
            continue
        file_after = after_path_for(rel, moves)
        for match in MD_LINK_RE.finditer(text):
            is_image = bool(match.group(1))
            mode = md_images if is_image else md_links
            if mode == "ignore":
                continue
            target = match.group(3).strip()
            new_target, before, after = rewrite_target(target, rel, file_after, root, moves)
            if new_target is None:
                continue
            kind = "markdown_image" if is_image else "markdown_link"
            if mode == "suggest":
                suggestions.append(Suggestion(rel, file_after, line_for_offset(text, match.start(3)), kind, target, after, "rewrite mode is suggest"))
            else:
                add_replacement(
                    replacements,
                    file_before=rel,
                    file_after=file_after,
                    start=match.start(3),
                    end=match.end(3),
                    old=match.group(3),
                    new=new_target,
                    kind=kind,
                    target_before=before or "",
                    target_after=after or "",
                )
        for match in HTML_REF_RE.finditer(text):
            if html_refs == "ignore":
                continue
            target = match.group("target")
            new_target, before, after = rewrite_target(target, rel, file_after, root, moves)
            if new_target is None:
                continue
            if html_refs == "suggest":
                suggestions.append(Suggestion(rel, file_after, line_for_offset(text, match.start("target")), "html_href_src", target, after, "rewrite mode is suggest"))
            else:
                add_replacement(
                    replacements,
                    file_before=rel,
                    file_after=file_after,
                    start=match.start("target"),
                    end=match.end("target"),
                    old=target,
                    new=new_target,
                    kind="html_href_src",
                    target_before=before or "",
                    target_after=after or "",
                )
        for match in BACKTICK_RE.finditer(text):
            token = match.group(1).strip()
            if backticks == "ignore" or any(ch.isspace() for ch in token):
                continue
            resolved = resolve_reference(token, rel, root)
            if resolved is None:
                resolved = normalize_inline_path_token(token, root)
            after = after_path_for(resolved, moves) if resolved is not None else None
            if after == resolved:
                inline_resolved = normalize_inline_path_token(token, root)
                inline_after = after_path_for(inline_resolved, moves) if inline_resolved else None
                if inline_after != inline_resolved:
                    resolved = inline_resolved
                    after = inline_after
                    new_token = format_inline_path_token(token, after or "")
                else:
                    continue
            elif resolved is not None and token.lstrip("/").replace("\\", "/") == resolved:
                new_token = format_inline_path_token(token, after or "")
            elif resolved is not None and after is not None:
                new_token = format_reference(resolved, after, file_after, token)
            else:
                continue
            if backticks == "suggest":
                suggestions.append(Suggestion(rel, file_after, line_for_offset(text, match.start(1)), "backtick_path", token, after, "rewrite mode is suggest"))
            else:
                add_replacement(
                    replacements,
                    file_before=rel,
                    file_after=file_after,
                    start=match.start(1),
                    end=match.end(1),
                    old=match.group(1),
                    new=new_token,
                    kind="backtick_path",
                    target_before=resolved,
                    target_after=after,
                )
        if exact_text != "ignore":
            covered_ranges = [(r.start, r.end) for r in replacements if r.file_before == rel]
            for move in sorted(moves, key=lambda item: len(item.src), reverse=True):
                for start, end, old_token, target_before, new_token in exact_text_path_matches(text, move):
                    if any(start < covered_end and covered_start < end for covered_start, covered_end in covered_ranges):
                        continue
                    target_after = new_token.lstrip("/").split("#", 1)[0]
                    if exact_text == "update":
                        add_replacement(
                            replacements,
                            file_before=rel,
                            file_after=file_after,
                            start=start,
                            end=end,
                            old=old_token,
                            new=new_token,
                            kind="exact_text_path",
                            target_before=target_before,
                            target_after=target_after,
                        )
                        covered_ranges.append((start, end))
                    else:
                        suggestions.append(
                            Suggestion(
                                rel,
                                file_after,
                                line_for_offset(text, start),
                                "exact_text_path",
                                old_token,
                                new_token,
                                "exact text paths default to suggest",
                            )
                        )
                        covered_ranges.append((start, end))
    return replacements, suggestions, blocked


def apply_replacements(text: str, replacements: list[Replacement]) -> str:
    ordered = sorted(replacements, key=lambda r: r.start)
    out: list[str] = []
    cursor = 0
    last_end = -1
    for rep in ordered:
        if rep.start < last_end:
            raise ValueError(f"overlapping replacements in {rep.file_before}")
        out.append(text[cursor:rep.start])
        out.append(rep.new)
        cursor = rep.end
        last_end = rep.end
    out.append(text[cursor:])
    return "".join(out)


def build_after_texts(root: Path, files: list[str], moves: list[MoveSpec], replacements: list[Replacement]) -> dict[str, str]:
    by_file: dict[str, list[Replacement]] = {}
    for rep in replacements:
        by_file.setdefault(rep.file_before, []).append(rep)
    after: dict[str, str] = {}
    for rel in files:
        try:
            text = _read_text(root / rel)
        except OSError:
            continue
        after_rel = after_path_for(rel, moves)
        after[after_rel] = apply_replacements(text, by_file.get(rel, []))
    return after


def all_repo_paths_after(root: Path, moves: list[MoveSpec]) -> set[str]:
    paths: set[str] = set()
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            rel = repo_rel(path, root)
            if rel.startswith(".git/"):
                continue
            paths.add(after_path_for(rel, moves))
    return paths


def verify_markdown_links(root: Path, after_texts: dict[str, str], after_paths: set[str]) -> list[dict]:
    broken: list[dict] = []
    for rel_after, text in after_texts.items():
        for match in MD_LINK_RE.finditer(text):
            target = match.group(3).strip()
            resolved = resolve_reference(target, rel_after, root)
            if resolved is None:
                continue
            if resolved not in after_paths:
                broken.append({
                    "file": rel_after,
                    "lineno": line_for_offset(text, match.start(3)),
                    "target": target,
                    "resolved": resolved,
                })
    return broken


def current_texts(root: Path, files: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in files:
        try:
            out[rel] = _read_text(root / rel)
        except OSError:
            continue
    return out


def current_paths(root: Path) -> set[str]:
    paths: set[str] = set()
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            rel = repo_rel(path, root)
            if not rel.startswith(".git/"):
                paths.add(rel)
    return paths


def old_path_residue(root: Path, moves: list[MoveSpec], files: list[str]) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    tokens = path_residue_tokens(root, moves)
    for rel in files:
        try:
            text = _read_text(root / rel)
        except OSError:
            continue
        for old, new, token_kind in tokens:
            pattern = residue_pattern(old)
            for match in re.finditer(pattern, text):
                token = match.group(0)
                target_after = residue_match_target(old, new, token)
                if is_current_relative_reference(root, rel, token, target_after):
                    continue
                suggestions.append(
                    Suggestion(
                        file_before=rel,
                        file_after=rel,
                        lineno=line_for_offset(text, match.start()),
                        kind="old_path_residue",
                        token=token,
                        target_after=target_after,
                        reason=f"old {token_kind} path remains after move",
                    )
                )
    return suggestions


def path_residue_tokens(root: Path, moves: list[MoveSpec]) -> list[tuple[str, str, str]]:
    tokens: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(old: str, new: str, kind: str) -> None:
        key = (old, new, kind)
        if old and key not in seen:
            tokens.append(key)
            seen.add(key)

    for move in moves:
        src = move.src.rstrip("/")
        dst = move.dst.rstrip("/")
        src_abs = (root / src).as_posix()
        dst_abs = (root / dst).as_posix()
        src_win = src.replace("/", "\\")
        dst_win = dst.replace("/", "\\")
        src_abs_win = src_abs.replace("/", "\\")
        dst_abs_win = dst_abs.replace("/", "\\")

        # Bare top-level directory names like "outputs" or "datasets" are
        # often ordinary prose or preserved source labels. Treat them as
        # residue only when they still appear as path prefixes. File moves and
        # nested paths are path-shaped enough to scan exactly.
        path_shaped = "/" in move.src or "." in Path(move.src).name
        if path_shaped:
            add(move.src, move.dst, "relative")
            add("/" + move.src, "/" + move.dst, "root-relative")
            add(src_abs, dst_abs, "absolute-posix")
            add(src_win, dst_win, "relative-windows")
            add(src_abs_win, dst_abs_win, "absolute-windows")

        if move.mode == "directory":
            add(src + "/", dst + "/", "relative-prefix")
            add("/" + src + "/", "/" + dst + "/", "root-relative-prefix")
            add(src_abs + "/", dst_abs + "/", "absolute-posix-prefix")
            add(src_win + "\\", dst_win + "\\", "relative-windows-prefix")
            add(src_abs_win + "\\", dst_abs_win + "\\", "absolute-windows-prefix")

    return tokens


def residue_pattern(old: str) -> str:
    path_char = r"[\w./\\:-]"
    pattern = r"(?<!" + path_char + r")" + re.escape(old)
    if not old.endswith(("/", "\\")):
        pattern += r"(?!" + path_char + r")"
    else:
        pattern += path_char + "*"
    return pattern


def residue_match_target(old: str, new: str, token: str) -> str:
    if old.endswith(("/", "\\")):
        return new + token[len(old):]
    return new


def is_current_relative_reference(root: Path, rel: str, token: str, target_after: str) -> bool:
    if token.startswith(("/", "\\")):
        return False
    if re.match(r"^[A-Za-z]:[\\/]", token):
        return False
    if target_after.startswith(("/", "\\")):
        return False
    if re.match(r"^[A-Za-z]:[\\/]", target_after):
        return False
    try:
        candidate = repo_rel((root / Path(rel).parent / token.replace("\\", "/")).resolve(), root)
    except ValueError:
        return False
    return candidate.rstrip("/") == target_after.replace("\\", "/").rstrip("/")


def git_root(cwd: Path) -> Path | None:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(res.stdout.strip())


def is_git_repo(root: Path) -> bool:
    return (root / ".git").exists()


def git_tracked(root: Path, rel: str) -> bool:
    res = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel], cwd=root, capture_output=True)
    return res.returncode == 0


def dirty_touched(root: Path, paths: list[str]) -> list[str]:
    if not is_git_repo(root) or not paths:
        return []
    res = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        cwd=root,
        text=True,
        capture_output=True,
    )
    dirty: list[str] = []
    for line in res.stdout.splitlines():
        if line:
            dirty.append(line)
    return dirty


def move_one(root: Path, src: str, dst: str) -> None:
    src_path = root / src
    dst_path = root / dst
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    use_git = is_git_repo(root) and git_tracked(root, src)
    case_only = src.lower() == dst.lower() and src != dst
    if case_only:
        tmp_rel = f"{DEFAULT_REPORT_DIR}/tmp/{next(tempfile._get_candidate_names())}-{Path(src).name}"
        tmp_path = root / tmp_rel
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        if use_git:
            subprocess.run(["git", "mv", "--", src, tmp_rel], cwd=root, check=True)
            subprocess.run(["git", "mv", "--", tmp_rel, dst], cwd=root, check=True)
        else:
            shutil.move(str(src_path), str(tmp_path))
            shutil.move(str(tmp_path), str(dst_path))
        return
    if use_git:
        subprocess.run(["git", "mv", "--", src, dst], cwd=root, check=True)
    else:
        shutil.move(str(src_path), str(dst_path))


def apply_moves_and_rewrites(
    root: Path,
    moves: list[MoveSpec],
    after_texts: dict[str, str],
    touched_text_files_before: list[str],
) -> None:
    for move in sorted(moves, key=lambda m: len(m.src), reverse=True):
        move_one(root, move.src, move.dst)
    for before in touched_text_files_before:
        after = after_path_for(before, moves)
        if after in after_texts:
            _write_text(root / after, after_texts[after])


def stage_applied_paths(
    root: Path,
    moves: list[MoveSpec],
    touched_text_files_before: list[str],
) -> None:
    """Stage only paths that exist after a successful move and native checks."""
    if not is_git_repo(root):
        return
    candidates = {
        *(move.dst for move in moves),
        *(after_path_for(before, moves) for before in touched_text_files_before),
    }
    existing = sorted(
        rel for rel in candidates if (root / rel).exists() or (root / rel).is_symlink()
    )
    if existing:
        subprocess.run(["git", "add", "--", *existing], cwd=root, check=True)


def report_payload(
    *,
    root: Path,
    plan_path: Path,
    mode: str,
    moves: list[MoveSpec],
    files: list[str],
    replacements: list[Replacement],
    suggestions: list[Suggestion],
    blocked: list[dict],
    post_broken_links: list[dict],
    dirty: list[str],
    ignored_code_imports: list[dict],
) -> dict:
    return {
        "project_root": root.as_posix(),
        "plan_path": plan_path.as_posix(),
        "mode": mode,
        "summary": {
            "moves": len(moves),
            "scoped_files": len(files),
            "auto_rewrites": len(replacements),
            "suggestions": len(suggestions),
            "blocked": len(blocked),
            "post_broken_links": len(post_broken_links),
            "dirty_touched": len(dirty),
            "ignored_code_import_risks": len(ignored_code_imports),
        },
        "moves": [dataclasses.asdict(m) for m in moves],
        "auto_rewrites": [dataclasses.asdict(r) for r in replacements],
        "suggestions": [dataclasses.asdict(s) for s in suggestions],
        "blocked": blocked,
        "post_broken_links": post_broken_links,
        "dirty_touched": dirty,
        "code_imports": {
            "mode": "ignore",
            "risk": (
                "TypeScript and TSX source import specifiers are not rewritten. "
                "Review every affected import before applying a move; import-safe moves require a named resolver."
            ),
            "ignored": ignored_code_imports,
        },
    }


def render_markdown(payload: dict) -> str:
    out = [
        "# move-path report",
        "",
        f"**Mode:** {payload['mode']}",
        f"**Project root:** `{payload['project_root']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        out.append(f"- `{key}`: {value}")
    out.extend(["", "## Moves", ""])
    for move in payload["moves"]:
        out.append(f"- `{move['src']}` -> `{move['dst']}` ({move['mode']})")
    out.extend(["", "## Auto Rewrites", ""])
    if payload["auto_rewrites"]:
        for rep in payload["auto_rewrites"][:200]:
            out.append(
                f"- `{rep['file_before']}` -> `{rep['file_after']}` "
                f"{rep['kind']}: `{rep['old']}` -> `{rep['new']}`"
            )
    else:
        out.append("- None")
    out.extend(["", "## Suggestions", ""])
    if payload["suggestions"]:
        for item in payload["suggestions"][:200]:
            out.append(
                f"- `{item['file_before']}`:{item['lineno']} {item['kind']}: "
                f"`{item['token']}` -> `{item['target_after']}` ({item['reason']})"
            )
    else:
        out.append("- None")
    out.extend(["", "## Blocked", ""])
    if payload["blocked"]:
        for item in payload["blocked"]:
            out.append(f"- `{item.get('kind')}`: `{item}`")
    else:
        out.append("- None")
    if payload["code_imports"]["mode"] == "ignore":
        out.extend(["", "## Ignored TypeScript Imports", ""])
        out.append(
            "- `rewrite.code_imports: ignore`: TypeScript and TSX source imports are not rewritten; "
            "review affected imports before applying this move."
        )
        if payload["code_imports"]["ignored"]:
            for item in payload["code_imports"]["ignored"][:200]:
                out.append(
                    f"- `{item['file']}`:{item['lineno']} `{item['specifier']}`: "
                    f"`{item['target_before']}` -> `{item['target_after']}`; remediation unknown without "
                    f"TypeScript module resolution ({item['reason']})"
                )
        else:
            out.append("- No local TypeScript/TSX import is invalidated by a moved target or referrer.")
    if javascript := payload.get("javascript"):
        out.extend(["", "## Checked JavaScript", ""])
        out.append(f"- Status: `{javascript['status']}`")
        out.append(f"- Updated import spans: {len(javascript.get('updates', []))}")
        if javascript.get("error"):
            out.append(f"- Detail: {javascript['error']}")
        if javascript.get("rolled_back"):
            out.append("- Source changes were rolled back after the host-native check failed.")
    if go := payload.get("go"):
        out.extend(["", "## Checked Go Package Move", ""])
        out.append(f"- Status: `{go['status']}`")
        out.append(f"- Updated import spans: {len(go.get('updates', []))}")
        if go.get("old_import"):
            out.append(f"- Import identity: `{go['old_import']}` -> `{go['new_import']}`")
        if go.get("error"):
            out.append(f"- Detail: {go['error']}")
        if go.get("rolled_back"):
            out.append("- Source changes were rolled back after the Go native check failed.")
    if java := payload.get("java"):
        out.extend(["", "## Checked Java Package Move", ""])
        out.append(f"- Status: `{java['status']}`")
        out.append(f"- Updated reference spans: {len(java.get('updates', []))}")
        if java.get("old_package"):
            out.append(f"- Package identity: `{java['old_package']}` -> `{java['new_package']}`")
        if java.get("error"):
            out.append(f"- Detail: {java['error']}")
        if java.get("rolled_back"):
            out.append("- Source changes were rolled back after Java native compilation failed.")
    if php := payload.get("php"):
        out.extend(["", "## Checked PHP Namespace Move", ""])
        out.append(f"- Status: `{php['status']}`")
        out.append(f"- Updated token spans: {len(php.get('updates', []))}")
        if php.get("old_namespace"):
            out.append(f"- Namespace identity: `{php['old_namespace']}` -> `{php['new_namespace']}`")
        if php.get("error"):
            out.append(f"- Detail: {php['error']}")
        if php.get("rolled_back"):
            out.append("- Source changes were rolled back after PHP native or exact-diff verification failed.")
    out.extend(["", "## Post-Apply Broken Links", ""])
    if payload["post_broken_links"]:
        for item in payload["post_broken_links"]:
            out.append(f"- `{item['file']}`:{item['lineno']} -> `{item['target']}`")
    else:
        out.append("- None")
    out.append("")
    return "\n".join(out)


def write_report(report_dir: Path, payload: dict) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_text(report_dir / "report.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _write_text(report_dir / "report.md", render_markdown(payload))


def add_javascript_report(payload: dict, outcome: dict, replacements: list[Replacement], *, rolled_back: bool = False) -> None:
    payload["javascript"] = {
        "mode": "update-javascript",
        "status": outcome["status"],
        "error": outcome.get("error"),
        "updates": [dataclasses.asdict(item) for item in replacements],
        "exact_changes": [dataclasses.asdict(item) for item in replacements],
        "rolled_back": rolled_back,
    }
    payload["summary"]["javascript_status"] = outcome["status"]


def add_go_report(
    payload: dict,
    outcome: dict,
    replacements: list[Replacement],
    *,
    native: dict | None = None,
    rolled_back: bool = False,
) -> None:
    payload["code_imports"] = {
        "mode": "update-go",
        "risk": "Only exact Go AST import string literals are updated; runtime and non-import paths are not rewritten.",
        "ignored": [],
    }
    payload["go"] = {
        "mode": "update-go",
        "status": outcome.get("status", "failed"),
        "error": outcome.get("error"),
        "tooling": outcome.get("tooling"),
        "old_import": outcome.get("old_import"),
        "new_import": outcome.get("new_import"),
        "updates": [dataclasses.asdict(item) for item in replacements],
        "exact_changes": [dataclasses.asdict(item) for item in replacements],
        "blocked": outcome.get("blocked", []),
        "native": native or {},
        "rolled_back": rolled_back,
    }
    payload["summary"]["go_status"] = outcome.get("status", "failed")


def add_java_report(
    payload: dict,
    outcome: dict,
    replacements: list[Replacement],
    *,
    native: dict | None = None,
    rolled_back: bool = False,
) -> None:
    payload["code_imports"] = {
        "mode": "update-java",
        "risk": "Only JDK-compiler-attributed package, import, and fully-qualified type spans are updated; strings and framework/runtime identities block apply.",
        "ignored": [],
    }
    payload["java"] = {
        "mode": "update-java",
        "status": outcome.get("status", "failed"),
        "error": outcome.get("error"),
        "tooling": outcome.get("tooling"),
        "old_package": outcome.get("old_package"),
        "new_package": outcome.get("new_package"),
        "updates": [dataclasses.asdict(item) for item in replacements],
        "exact_changes": [dataclasses.asdict(item) for item in replacements],
        "blocked": outcome.get("blocked", []),
        "native": native or {},
        "rolled_back": rolled_back,
    }
    payload["summary"]["java_status"] = outcome.get("status", "failed")


def add_php_report(
    payload: dict,
    outcome: dict,
    replacements: list[Replacement],
    *,
    native: dict | None = None,
    rolled_back: bool = False,
) -> None:
    payload["code_imports"] = {
        "mode": "update-php",
        "risk": "Only PHP-token namespace/name spans and exact require/include literals are updated; excluded or dynamic identities block apply.",
        "ignored": [],
    }
    tooling = outcome.get("tooling") or outcome
    payload["php"] = {
        "mode": "update-php",
        "status": outcome.get("status", "failed"),
        "error": outcome.get("error"),
        "tooling": tooling,
        "old_namespace": outcome.get("old_namespace") or tooling.get("old_namespace"),
        "new_namespace": outcome.get("new_namespace") or tooling.get("new_namespace"),
        "updates": [dataclasses.asdict(item) for item in replacements],
        "exact_changes": [dataclasses.asdict(item) for item in replacements],
        "blocked": outcome.get("blocked", []),
        "verification_files": outcome.get("verification_files") or tooling.get("verification_files", []),
        "excluded_files": outcome.get("excluded_files") or tooling.get("excluded_files", []),
        "native": native or {},
        "rolled_back": rolled_back,
    }
    payload["summary"]["php_status"] = outcome.get("status", "failed")


def snapshot_move_inputs(root: Path, moves: list[MoveSpec], touched_before: list[str]) -> dict[str, bytes]:
    """Capture the bounded moved tree and rewritten files for native rollback."""
    paths = set(touched_before)
    for move in moves:
        source = root / move.src
        if source.is_dir():
            for path in source.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    paths.add(repo_rel(path, root))
    return {path: (root / path).read_bytes() for path in sorted(paths) if (root / path).is_file()}


def rollback_move_inputs(root: Path, moves: list[MoveSpec], snapshots: dict[str, bytes]) -> None:
    for move in sorted(moves, key=lambda item: len(item.src)):
        if (root / move.dst).exists() and not (root / move.src).exists():
            move_one(root, move.dst, move.src)
    for path, contents in snapshots.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)


def exact_snapshot_match(
    root: Path,
    moves: list[MoveSpec],
    snapshots: dict[str, bytes],
    after_texts: dict[str, str],
) -> bool:
    """Prove gofmt changed no source beyond the declared after-tree."""
    for before, contents in snapshots.items():
        after = after_path_for(before, moves)
        expected = after_texts.get(after)
        expected_bytes = expected.encode("utf-8") if expected is not None else contents
        path = root / after
        if not path.is_file() or path.read_bytes() != expected_bytes:
            return False
    return True


def _snapshot_excluded(path: Path, root: Path, report_dir: Path) -> bool:
    relative = path.relative_to(root)
    if ".git" in relative.parts:
        return True
    try:
        path.resolve().relative_to(report_dir.resolve())
        return True
    except ValueError:
        return False


def snapshot_php_project(root: Path, report_dir: Path) -> dict[str, bytes]:
    """Capture every regular host file so native side effects are detectable."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not _snapshot_excluded(path, root, report_dir)
    }


def _manifest_fingerprint(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, contents in sorted(files.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(contents).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def exact_php_project_diff(
    root: Path,
    report_dir: Path,
    moves: list[MoveSpec],
    before: dict[str, bytes],
    after_texts: dict[str, str],
) -> dict:
    """Compare the whole host to the exact virtual after-tree, not only touched files."""
    expected: dict[str, bytes] = {}
    for relative, contents in before.items():
        after = after_path_for(relative, moves)
        expected_text = after_texts.get(after)
        expected[after] = expected_text.encode("utf-8") if expected_text is not None else contents
    actual = snapshot_php_project(root, report_dir)
    changed = sorted(
        path for path in expected.keys() & actual.keys() if expected[path] != actual[path]
    )
    missing = sorted(expected.keys() - actual.keys())
    unexpected = sorted(actual.keys() - expected.keys())
    return {
        "passed": not changed and not missing and not unexpected,
        "before_fingerprint": _manifest_fingerprint(before),
        "expected_fingerprint": _manifest_fingerprint(expected),
        "actual_fingerprint": _manifest_fingerprint(actual),
        "changed": changed,
        "missing": missing,
        "unexpected": unexpected,
    }


def rollback_php_project(
    root: Path,
    report_dir: Path,
    moves: list[MoveSpec],
    before: dict[str, bytes],
) -> None:
    """Restore the pre-apply manifest, including unexpected native output files."""
    for move in sorted(moves, key=lambda item: len(item.src)):
        if (root / move.dst).exists() and not (root / move.src).exists():
            move_one(root, move.dst, move.src)
    current = snapshot_php_project(root, report_dir)
    for relative in sorted(current.keys() - before.keys(), reverse=True):
        (root / relative).unlink()
    for relative, contents in before.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)


def merge_ignored_code_imports(pre_apply: list[dict], post_apply: list[dict]) -> list[dict]:
    """Retain pre-move TS import risks when the final check has moved the referrer."""
    merged: list[dict] = []
    seen: set[tuple[str, int, str, str | None, str, str]] = set()
    for item in [*pre_apply, *post_apply]:
        key = (
            item["file"],
            item["lineno"],
            item["specifier"],
            item["expected_specifier"],
            item["target_before"],
            item["target_after"],
        )
        if key not in seen:
            seen.add(key)
            merged.append(item)
    return merged


def run_plan(
    *,
    plan_path: Path,
    project_root: Path | None,
    mode: str,
    report_dir: Path,
    allow_dirty_touched: bool = False,
    stage: bool = False,
) -> dict:
    root = project_root or git_root(Path.cwd()) or Path.cwd()
    root = root.resolve()
    plan = load_plan(plan_path, root)
    import_mode = code_import_mode(plan)
    moves: list[MoveSpec] = plan["_moves"]
    if import_mode == "update-swift":
        import importlib.util

        helper_path = Path(__file__).with_name("swiftpm_move.py")
        spec = importlib.util.spec_from_file_location("move_path_swiftpm", helper_path)
        if spec is None or spec.loader is None:
            raise SystemExit(f"cannot load SwiftPM move helper: {helper_path}")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        return helper.run_swift_plan(
            root=root,
            plan_path=plan_path,
            plan=plan,
            moves=moves,
            mode=mode,
            report_dir=report_dir,
            stage=stage,
        )
    includes, excludes = plan_patterns(plan)
    files = exclude_authority_file(iter_scope_files(root, includes, excludes), plan_path, root)
    ignored_code_imports = ignored_typescript_imports(root, iter_typescript_source_files(root, excludes), moves)
    javascript_files = iter_javascript_source_files(root, excludes)
    config = javascript_config(plan, root) if import_mode == "update-javascript" else None
    if mode == "check":
        blocked = validate_applied_moves(root, moves)
        texts = current_texts(root, files)
        post_broken = verify_markdown_links(root, texts, current_paths(root))
        suggestions = old_path_residue(root, moves, files)
        payload = report_payload(
            root=root,
            plan_path=plan_path,
            mode=mode,
            moves=moves,
            files=files,
            replacements=[],
            suggestions=suggestions,
            blocked=blocked,
            post_broken_links=post_broken,
            dirty=[],
            ignored_code_imports=ignored_code_imports,
        )
        if import_mode == "update-javascript":
            add_javascript_report(payload, checked_javascript(root, config, javascript_files), [])
        if import_mode == "update-go":
            tooling = go_tooling(root, moves, post_apply=True)
            native: dict = {}
            if tooling.get("status") == "complete":
                go_files = [
                    repo_rel(path, root)
                    for path in sorted(root.rglob("*.go"))
                    if path.is_file() and not path.is_symlink() and "vendor" not in path.relative_to(root).parts
                ]
                native["gofmt"] = run_gofmt(root, tooling["gofmt"]["path"], go_files)
                native["go_test"] = run_go_test(root, tooling["go"]["path"])
                old_import = tooling["module"]["path"].rstrip("/") + "/" + moves[0].src
                remaining = [path for path in go_files if old_import in _read_text(root / path)]
                non_go_blocks = non_go_old_import_path_blocks(root, old_import, plan_path, report_dir)
                if remaining:
                    tooling["blocked"].append({"kind": "go_old_import_remains_after_move", "paths": remaining})
                tooling["blocked"].extend(non_go_blocks)
                tooling.update({
                    "old_import": old_import,
                    "new_import": tooling["module"]["path"].rstrip("/") + "/" + moves[0].dst,
                    "status": (
                        "failed"
                        if not all(item["passed"] for item in native.values()) or remaining
                        else "partial" if non_go_blocks else "complete"
                    ),
                })
            add_go_report(payload, tooling, [], native=native)
        if import_mode == "update-java":
            tooling = java_tooling(root, moves, post_apply=True)
            native: dict = {}
            outcome = tooling
            if tooling.get("status") == "complete":
                move = moves[0]
                reverse = [MoveSpec(move.move_id, move.dst, move.src, move.mode)]
                reverse_outcome = checked_java(
                    root, reverse, tooling, include_runtime_blocks=False
                )
                if reverse_outcome.get("status") == "complete":
                    old_package = reverse_outcome["new_package"]
                    new_package = reverse_outcome["old_package"]
                    residues = []
                    for source in iter_java_source_files(root):
                        text = _read_text(root / source)
                        if old_package in text:
                            residues.append({"kind": "java_old_package_remains_after_move", "path": source})
                    residues.extend(java_runtime_old_package_blocks(root, old_package))
                    native["javac"] = run_java_compile(root, tooling["javac"]["path"], iter_java_source_files(root))
                    outcome = {
                        **reverse_outcome,
                        "old_package": old_package,
                        "new_package": new_package,
                        "blocked": residues,
                        "status": "failed" if not native["javac"]["passed"] else "partial" if residues else "complete",
                    }
                else:
                    outcome = reverse_outcome
            add_java_report(payload, outcome, [], native=native)
        if import_mode == "update-php":
            tooling = php_tooling(root, plan, moves, post_apply=True)
            outcome = checked_php(root, moves, tooling, post_apply=True)
            native: dict = {}
            if outcome.get("status") == "complete":
                scripts = outcome.get("verification_files", [])
                labels = [Path(script).stem for script in scripts]
                for label, script in zip(labels, scripts, strict=True):
                    native[label] = run_php_script(root, outcome["tooling"]["php"]["path"], script)
                if not all(item["passed"] for item in native.values()):
                    outcome["status"] = "failed"
                    outcome.setdefault("blocked", []).append({"kind": "php_native_check_failed"})
            add_php_report(payload, outcome, [], native=native)
        write_report(report_dir, payload)
        return payload

    blocked = validate_moves(root, moves)
    replacements, suggestions, reference_blocked = detect_references(root, plan, moves, files)
    blocked.extend(reference_blocked)
    javascript = checked_javascript(root, config, javascript_files) if import_mode == "update-javascript" else None
    go = checked_go(root, moves, go_tooling(root, moves)) if import_mode == "update-go" else None
    java = checked_java(root, moves, java_tooling(root, moves)) if import_mode == "update-java" else None
    php = checked_php(root, moves, php_tooling(root, plan, moves)) if import_mode == "update-php" else None
    if go is not None and go.get("status") == "complete":
        non_go_blocks = non_go_old_import_path_blocks(root, go["old_import"], plan_path, report_dir)
        if non_go_blocks:
            go["blocked"].extend(non_go_blocks)
            go["status"] = "partial"
    javascript_replacements: list[Replacement] = []
    go_replacements: list[Replacement] = []
    java_replacements: list[Replacement] = []
    php_replacements: list[Replacement] = []
    if javascript is not None:
        if javascript["status"] == "complete":
            javascript_replacements, javascript_blocked = javascript_rewrites(root, moves, javascript)
            blocked.extend(javascript_blocked)
            if javascript_blocked:
                javascript["status"] = "partial"
        else:
            blocked.append({"kind": f"javascript_{javascript['status']}", "detail": javascript.get("error")})
    elif any(Path(move.src).suffix.lower() in JAVASCRIPT_SUFFIXES for move in moves):
        blocked.append({"kind": "javascript_updates_not_enabled", "detail": "JavaScript moves require update-javascript"})
    if go is not None:
        if go.get("status") == "complete":
            go_replacements, go_blocked = go_rewrites(root, moves, go)
            blocked.extend(go_blocked)
            if go_blocked:
                go["status"] = "unsupported"
        else:
            blocked.append({"kind": f"go_{go.get('status', 'failed')}", "detail": go.get("error"), "findings": go.get("blocked", [])})
    if java is not None:
        if java.get("status") == "complete":
            java_replacements, java_blocked = java_rewrites(root, moves, java)
            blocked.extend(java_blocked)
            if java_blocked:
                java["status"] = "unsupported"
        else:
            blocked.append({"kind": f"java_{java.get('status', 'failed')}", "detail": java.get("error"), "findings": java.get("blocked", [])})
    if php is not None:
        if php.get("status") == "complete":
            php_replacements, php_blocked = php_rewrites(root, moves, php)
            blocked.extend(php_blocked)
            if php_blocked:
                php["status"] = "unsupported"
        else:
            blocked.append({"kind": f"php_{php.get('status', 'failed')}", "detail": php.get("error"), "findings": php.get("blocked", [])})
    replacements.extend(javascript_replacements)
    replacements.extend(go_replacements)
    replacements.extend(java_replacements)
    replacements.extend(php_replacements)
    go_files = go.get("go_files", []) if go is not None else []
    java_files = java.get("java_files", []) if java is not None else []
    php_files = php.get("php_files", []) if php is not None else []
    after_texts = build_after_texts(root, sorted({*files, *javascript_files, *go_files, *java_files, *php_files}), moves, replacements)
    after_paths = all_repo_paths_after(root, moves)
    post_broken = verify_markdown_links(root, after_texts, after_paths)

    touched_before = sorted({r.file_before for r in replacements})
    touched_git_paths = sorted({m.src for m in moves} | {m.dst for m in moves} | set(touched_before))
    dirty = dirty_touched(root, touched_git_paths)
    if dirty and not allow_dirty_touched and mode == "apply":
        blocked.append({"kind": "dirty_touched_files", "files": dirty})

    payload = report_payload(
        root=root,
        plan_path=plan_path,
        mode=mode,
        moves=moves,
        files=files,
        replacements=replacements,
        suggestions=suggestions,
        blocked=blocked,
        post_broken_links=post_broken,
        dirty=dirty,
        ignored_code_imports=ignored_code_imports,
    )
    if javascript is not None:
        add_javascript_report(payload, javascript, javascript_replacements)
    if go is not None:
        add_go_report(payload, go, go_replacements)
    if java is not None:
        add_java_report(payload, java, java_replacements)
    if php is not None:
        add_php_report(payload, php, php_replacements)
    write_report(report_dir, payload)

    safety = plan.get("safety") or {}
    fail_on_blocked = bool(safety.get("fail_on_blocked", True))
    fail_on_broken = bool(safety.get("fail_on_broken_links", True))
    if mode in {"dry-run", "check"}:
        return payload
    if fail_on_blocked and blocked:
        raise SystemExit(f"blocked findings prevent apply; see {report_dir / 'report.md'}")
    if fail_on_broken and post_broken:
        raise SystemExit(f"post-apply broken links prevent apply; see {report_dir / 'report.md'}")
    native: dict = {}
    go_touched_before: list[str] = []
    if go is not None:
        go_touched_before = sorted({*go.get("moved_files", []), *(item["file"] for item in go.get("spans", []))})
        native["gofmt_preflight"] = run_gofmt(root, go["tooling"]["gofmt"]["path"], go_touched_before)
        if not native["gofmt_preflight"]["passed"]:
            go["status"] = "partial"
            go.setdefault("blocked", []).append({"kind": "go_unformatted_touched_source"})
            add_go_report(payload, go, go_replacements, native=native)
            payload["blocked"].append({"kind": "go_unformatted_touched_source"})
            payload["summary"]["blocked"] = len(payload["blocked"])
            write_report(report_dir, payload)
            raise SystemExit(f"gofmt preflight prevents apply; see {report_dir / 'report.md'}")
    if java is not None:
        native["javac_preflight"] = run_java_compile(root, java["tooling"]["javac"]["path"], java.get("java_files", []))
        if not native["javac_preflight"]["passed"]:
            java["status"] = "failed"
            java.setdefault("blocked", []).append({"kind": "java_compile_preflight_failed"})
            add_java_report(payload, java, java_replacements, native=native)
            payload["blocked"].append({"kind": "java_compile_preflight_failed"})
            payload["summary"]["blocked"] = len(payload["blocked"])
            write_report(report_dir, payload)
            raise SystemExit(f"javac preflight prevents apply; see {report_dir / 'report.md'}")
    php_snapshot: dict[str, bytes] | None = None
    if php is not None:
        php_snapshot = snapshot_php_project(root, report_dir)
        scripts = php.get("verification_files", [])
        labels = [Path(script).stem for script in scripts]
        for label, script in zip(labels, scripts, strict=True):
            native[f"{label}_preflight"] = run_php_script(root, php["tooling"]["php"]["path"], script)
        native["preflight_fingerprint"] = exact_php_project_diff(
            root, report_dir, [], php_snapshot, {}
        )
        if not all(item["passed"] for item in native.values()):
            rollback_php_project(root, report_dir, [], php_snapshot)
            php["status"] = "failed"
            php.setdefault("blocked", []).append({"kind": "php_native_preflight_failed"})
            add_php_report(payload, php, php_replacements, native=native, rolled_back=True)
            payload["blocked"].append({"kind": "php_native_preflight_failed"})
            payload["summary"]["blocked"] = len(payload["blocked"])
            write_report(report_dir, payload)
            raise SystemExit(f"PHP native preflight failed; source rolled back; see {report_dir / 'report.md'}")
    snapshots = snapshot_move_inputs(root, moves, touched_before) if go is not None or java is not None else {path: (root / path).read_bytes() for path in touched_before}
    apply_moves_and_rewrites(root, moves, after_texts, touched_before)
    if javascript is not None:
        checked_after = checked_javascript(root, config, [after_path_for(path, moves) for path in javascript_files])
        if checked_after["status"] != "complete":
            for move in sorted(moves, key=lambda item: len(item.src)):
                if (root / move.dst).exists() and not (root / move.src).exists():
                    move_one(root, move.dst, move.src)
            for path, contents in snapshots.items():
                (root / path).write_bytes(contents)
            add_javascript_report(payload, checked_after, javascript_replacements, rolled_back=True)
            payload["blocked"].append({"kind": f"javascript_{checked_after['status']}", "detail": checked_after.get("error")})
            payload["summary"]["blocked"] = len(payload["blocked"])
            write_report(report_dir, payload)
            raise SystemExit(f"checked JavaScript failed; source rolled back; see {report_dir / 'report.md'}")
    if go is not None:
        go_touched_after = [after_path_for(path, moves) for path in go_touched_before]
        native["gofmt"] = run_gofmt(root, go["tooling"]["gofmt"]["path"], go_touched_after, write=True)
        native["gofmt_check"] = run_gofmt(root, go["tooling"]["gofmt"]["path"], go_touched_after)
        native["go_test"] = run_go_test(root, go["tooling"]["go"]["path"])
        exact = exact_snapshot_match(root, moves, snapshots, after_texts)
        if not exact:
            native["exact_diff"] = {"passed": False}
        else:
            native["exact_diff"] = {"passed": True}
        if not all(item["passed"] for item in native.values()):
            rollback_move_inputs(root, moves, snapshots)
            go["status"] = "failed"
            go.setdefault("blocked", []).append({"kind": "go_native_or_exact_check_failed"})
            add_go_report(payload, go, go_replacements, native=native, rolled_back=True)
            payload["blocked"].append({"kind": "go_native_or_exact_check_failed"})
            payload["summary"]["blocked"] = len(payload["blocked"])
            write_report(report_dir, payload)
            raise SystemExit(f"Go native verification failed; source rolled back; see {report_dir / 'report.md'}")
        add_go_report(payload, go, go_replacements, native=native)
        write_report(report_dir, payload)
        if stage:
            stage_applied_paths(root, moves, touched_before)
        return payload
    if java is not None:
        java_files_after = [after_path_for(path, moves) for path in java.get("java_files", [])]
        native["javac"] = run_java_compile(root, java["tooling"]["javac"]["path"], java_files_after)
        native["exact_diff"] = {"passed": exact_snapshot_match(root, moves, snapshots, after_texts)}
        if not all(item["passed"] for item in native.values()):
            rollback_move_inputs(root, moves, snapshots)
            java["status"] = "failed"
            java.setdefault("blocked", []).append({"kind": "java_native_or_exact_check_failed"})
            add_java_report(payload, java, java_replacements, native=native, rolled_back=True)
            payload["blocked"].append({"kind": "java_native_or_exact_check_failed"})
            payload["summary"]["blocked"] = len(payload["blocked"])
            write_report(report_dir, payload)
            raise SystemExit(f"Java native verification failed; source rolled back; see {report_dir / 'report.md'}")
        add_java_report(payload, java, java_replacements, native=native)
        write_report(report_dir, payload)
        if stage:
            stage_applied_paths(root, moves, touched_before)
        return payload
    if php is not None:
        assert php_snapshot is not None
        checked_after = checked_php(
            root,
            moves,
            php_tooling(root, plan, moves, post_apply=True),
            post_apply=True,
        )
        native["token_check"] = {
            "passed": checked_after.get("status") == "complete",
            "status": checked_after.get("status", "failed"),
            "blocked": checked_after.get("blocked", []),
        }
        scripts = php.get("verification_files", [])
        labels = [Path(script).stem for script in scripts]
        for label, script in zip(labels, scripts, strict=True):
            native[label] = run_php_script(root, php["tooling"]["php"]["path"], script)
        native["exact_diff"] = exact_php_project_diff(
            root, report_dir, moves, php_snapshot, after_texts
        )
        if not all(item["passed"] for item in native.values()):
            rollback_php_project(root, report_dir, moves, php_snapshot)
            checked_after["status"] = "failed"
            checked_after.setdefault("blocked", []).append({"kind": "php_native_or_exact_check_failed"})
            add_php_report(payload, checked_after, php_replacements, native=native, rolled_back=True)
            payload["blocked"].append({"kind": "php_native_or_exact_check_failed"})
            payload["summary"]["blocked"] = len(payload["blocked"])
            write_report(report_dir, payload)
            raise SystemExit(f"PHP native verification failed; source rolled back; see {report_dir / 'report.md'}")
        add_php_report(payload, checked_after, php_replacements, native=native)
        write_report(report_dir, payload)
        if stage:
            stage_applied_paths(root, moves, touched_before)
        return payload
    # Re-run check after mutation so report reflects final state.
    post_apply = run_plan(
        plan_path=plan_path,
        project_root=root,
        mode="check",
        report_dir=report_dir,
        allow_dirty_touched=True,
        stage=False,
    )
    merged_imports = merge_ignored_code_imports(ignored_code_imports, post_apply["code_imports"]["ignored"])
    if merged_imports != post_apply["code_imports"]["ignored"]:
        post_apply["code_imports"]["ignored"] = merged_imports
        post_apply["summary"]["ignored_code_import_risks"] = len(merged_imports)
        write_report(report_dir, post_apply)
    if javascript is not None:
        post_apply["javascript"] = payload["javascript"]
        post_apply["summary"]["javascript_status"] = payload["javascript"]["status"]
        write_report(report_dir, post_apply)
    if stage:
        stage_applied_paths(root, moves, touched_before)
    return post_apply


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely move paths and rewrite references.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--report-dir", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--allow-dirty-touched", action="store_true")
    parser.add_argument("--stage", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    selected = "dry-run" if args.dry_run else "apply" if args.apply else "check"
    report_dir = args.report_dir
    root = args.project_root or git_root(Path.cwd()) or Path.cwd()
    if report_dir is None:
        report_dir = root / DEFAULT_REPORT_DIR
    payload = run_plan(
        plan_path=args.plan,
        project_root=root,
        mode=selected,
        report_dir=report_dir,
        allow_dirty_touched=args.allow_dirty_touched,
        stage=args.stage,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(report_dir / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
