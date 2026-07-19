#!/usr/bin/env python3
"""Deterministic batched path mover with reference rewriting.

V1 supports standalone TypeScript/TSX path moves plus filesystem identity and
text references that can be resolved safely: Markdown links/images, HTML
href/src attributes, backtick path tokens, and exact path residues. TypeScript
source imports are intentionally not rewritten; affected local imports are
reported as an explicit risk for a resolver-aware follow-up.
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
        import[ \t]+(?:type[ \t]+)?(?:(?!\n).*?[ \t]+from[ \t]+)?
      | export[ \t]+(?:type[ \t]+)?(?:(?!\n).*?[ \t]+from[ \t]+)
    )
    (?P<quote>[\"'])(?P<specifier>[^\"'\\\n]+)(?P=quote)
    """
)
TYPESCRIPT_SUFFIXES = (".ts", ".tsx")
TYPESCRIPT_MODULE_SUFFIXES = (".ts", ".tsx", ".d.ts")


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
        if not path.is_file():
            continue
        rel = repo_rel(path, root)
        if matches_any(rel, excludes):
            continue
        if matches_any(rel, includes):
            out.append(rel)
    return out


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
    value = mode_for(plan, "code_imports", "ignore")
    if value != "ignore":
        raise SystemExit("rewrite.code_imports only supports ignore; TypeScript imports require a resolver-aware move")
    return value


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
    candidates = [resolved]
    if not resolved.endswith(TYPESCRIPT_MODULE_SUFFIXES):
        candidates.extend(resolved + suffix for suffix in TYPESCRIPT_MODULE_SUFFIXES)
        candidates.extend(resolved + "/index" + suffix for suffix in TYPESCRIPT_MODULE_SUFFIXES)
    for candidate in candidates:
        if (root / candidate).is_file() or (root / after_path_for(candidate, moves)).is_file():
            return candidate
    return None


def ignored_typescript_imports(root: Path, files: list[str], moves: list[MoveSpec]) -> list[dict]:
    """Report local TS/TSX imports invalidated by moving their target or referrer."""
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
            expected_specifier = format_reference(before, after, referrer_after, specifier)
            if expected_specifier == specifier:
                continue
            ignored.append(
                {
                    "file": rel,
                    "file_after": referrer_after,
                    "lineno": line_for_offset(text, match.start("specifier")),
                    "specifier": specifier,
                    "expected_specifier": expected_specifier,
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
        # Never mutate TypeScript source. The separate risk scan records only
        # local static imports that resolve to a moved identity.
        if path.suffix in TYPESCRIPT_SUFFIXES:
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
    out.extend(["", "## Ignored TypeScript Imports", ""])
    out.append(
        "- `rewrite.code_imports: ignore`: TypeScript and TSX source imports are not rewritten; "
        "review affected imports before applying this move."
    )
    if payload["code_imports"]["ignored"]:
        for item in payload["code_imports"]["ignored"][:200]:
            out.append(
                f"- `{item['file']}`:{item['lineno']} `{item['specifier']}`: "
                f"expected `{item['expected_specifier']}` for `{item['target_before']}` -> "
                f"`{item['target_after']}` ({item['reason']})"
            )
    else:
        out.append("- No local TypeScript/TSX import is invalidated by a moved target or referrer.")
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


def merge_ignored_code_imports(pre_apply: list[dict], post_apply: list[dict]) -> list[dict]:
    """Retain pre-move TS import risks when the final check has moved the referrer."""
    merged: list[dict] = []
    seen: set[tuple[str, int, str, str, str, str]] = set()
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
    code_import_mode(plan)
    moves: list[MoveSpec] = plan["_moves"]
    includes, excludes = plan_patterns(plan)
    files = iter_scope_files(root, includes, excludes)
    ignored_code_imports = ignored_typescript_imports(root, iter_typescript_source_files(root, excludes), moves)
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
        ignored_code_imports=ignored_code_imports,
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
