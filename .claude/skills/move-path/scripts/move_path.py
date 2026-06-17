#!/usr/bin/env python3
"""Deterministic batched path mover with reference rewriting.

V0 focuses on filesystem identity and text references that can be resolved
safely: Markdown links/images, HTML href/src attributes, backtick path tokens,
and exact path residues. Language imports are intentionally adapter-deferred.
"""
from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in minimal hosts.
    yaml = None


DEFAULT_INCLUDES = ["**/*.md", "**/*.mdx", "**/*.yml", "**/*.yaml", "**/*.json", "**/*.html"]
DEFAULT_EXCLUDES = [".git/**", ".move-path/**", "node_modules/**", ".venv/**", "__pycache__/**"]
LOCAL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
MD_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\n]+)\)")
HTML_REF_RE = re.compile(r"(?P<attr>\b(?:href|src)=)(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")


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
    if yaml is None:
        raise SystemExit("PyYAML is required to read move-path plans")
    try:
        data = yaml.safe_load(_read_text(plan_path))
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError) as exc:
        raise SystemExit(f"cannot read plan {plan_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("move-path plan must be a YAML mapping")
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
        if not path.is_file():
            continue
        rel = repo_rel(path, root)
        if matches_any(rel, excludes):
            continue
        if matches_any(rel, includes):
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
    if after == resolved:
        return None, resolved, after
    return format_reference(resolved, after, referrer_after, original_target), resolved, after


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
            for move in moves:
                for token in {move.src, "/" + move.src}:
                    for match in re.finditer(r"(?<![\w./-])" + re.escape(token) + r"(?![\w./-])", text):
                        if any(match.start() < end and start < match.end() for start, end in covered_ranges):
                            continue
                        after = after_path_for(token.lstrip("/"), moves)
                        new_token = ("/" if token.startswith("/") else "") + after
                        if exact_text == "update":
                            add_replacement(
                                replacements,
                                file_before=rel,
                                file_after=file_after,
                                start=match.start(),
                                end=match.end(),
                                old=match.group(0),
                                new=new_token,
                                kind="exact_text_path",
                                target_before=token.lstrip("/"),
                                target_after=after,
                            )
                        else:
                            suggestions.append(
                                Suggestion(
                                    rel,
                                    file_after,
                                    line_for_offset(text, match.start()),
                                    "exact_text_path",
                                    match.group(0),
                                    new_token,
                                    "exact text paths default to suggest",
                                )
                            )
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
        if path.is_file():
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
        if path.is_file():
            rel = repo_rel(path, root)
            if not rel.startswith(".git/"):
                paths.add(rel)
    return paths


def old_path_residue(root: Path, moves: list[MoveSpec], files: list[str]) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    tokens = []
    for move in moves:
        tokens.append((move.src, move.dst))
        tokens.append(("/" + move.src, "/" + move.dst))
    for rel in files:
        try:
            text = _read_text(root / rel)
        except OSError:
            continue
        for old, new in tokens:
            for match in re.finditer(r"(?<![\w./-])" + re.escape(old) + r"(?![\w./-])", text):
                suggestions.append(
                    Suggestion(
                        file_before=rel,
                        file_after=rel,
                        lineno=line_for_offset(text, match.start()),
                        kind="old_path_residue",
                        token=match.group(0),
                        target_after=new,
                        reason="old path remains after move",
                    )
                )
    return suggestions


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
        tmp_rel = f".move-path/tmp/{next(tempfile._get_candidate_names())}-{Path(src).name}"
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
    *,
    stage: bool,
) -> None:
    for move in sorted(moves, key=lambda m: len(m.src), reverse=True):
        move_one(root, move.src, move.dst)
    for before in touched_text_files_before:
        after = after_path_for(before, moves)
        if after in after_texts:
            _write_text(root / after, after_texts[after])
    if stage and is_git_repo(root):
        stage_paths: set[str] = set()
        for move in moves:
            stage_paths.add(move.src)
            stage_paths.add(move.dst)
        for before in touched_text_files_before:
            stage_paths.add(before)
            stage_paths.add(after_path_for(before, moves))
        subprocess.run(["git", "add", "--", *sorted(stage_paths)], cwd=root, check=True)


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
        },
        "moves": [dataclasses.asdict(m) for m in moves],
        "auto_rewrites": [dataclasses.asdict(r) for r in replacements],
        "suggestions": [dataclasses.asdict(s) for s in suggestions],
        "blocked": blocked,
        "post_broken_links": post_broken_links,
        "dirty_touched": dirty,
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
    moves: list[MoveSpec] = plan["_moves"]
    includes, excludes = plan_patterns(plan)
    files = iter_scope_files(root, includes, excludes)
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
        )
        write_report(report_dir, payload)
        return payload

    blocked = validate_moves(root, moves)
    replacements, suggestions, reference_blocked = detect_references(root, plan, moves, files)
    blocked.extend(reference_blocked)
    after_texts = build_after_texts(root, files, moves, replacements)
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
    )
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
    apply_moves_and_rewrites(root, moves, after_texts, touched_before, stage=stage)
    # Re-run check after mutation so report reflects final state.
    return run_plan(
        plan_path=plan_path,
        project_root=root,
        mode="check",
        report_dir=report_dir,
        allow_dirty_touched=True,
        stage=False,
    )


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
        report_dir = root / ".move-path"
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
