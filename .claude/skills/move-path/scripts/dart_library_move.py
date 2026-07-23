#!/usr/bin/env python3
"""Move one private Dart library path from reviewed, content-addressed evidence."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "dart-move-evidence-v1"
REPORT_VERSION = "dart-move-report-v1"
GENERATED_PARTS = frozenset({"generated", "gen", "build", "dist", "out", "vendor"})
GENERATED_SUFFIXES = (".g.dart", ".freezed.dart", ".mocks.dart")
GENERATED_MARKER = re.compile(
    r"(?:GENERATED CODE|Generated code|DO NOT EDIT|@generated)", re.IGNORECASE
)
DIRECTIVE_RE = re.compile(
    r"(?m)^\s*(?P<kind>import|export|part(?:\s+of)?)\s+"
    r"(?P<quote>['\"])(?P<uri>[^'\"]+)(?P=quote)(?P<tail>[^;]*);"
)
DYNAMIC_TOKENS = (
    "dart:mirrors",
    "MirrorSystem",
    "Isolate.spawnUri",
    "Uri.parse",
    "loadLibrary",
    "DynamicLibrary.open",
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


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _lexical(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _has_symlink(path: Path, root: Path) -> bool:
    if not _inside(_lexical(path), root):
        return True
    current = _lexical(path)
    while current != root:
        if current.is_symlink():
            return True
        current = current.parent
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


def _load_module(path: Path, name: str):
    if not path.is_file():
        raise UserError(f"copied Dart closure is missing {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise UserError(f"cannot load copied Dart closure file {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _library_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    required = (
        root / "_dart/scripts/dart_syntax_facts.py",
        root / "_dart/dart_project_snapshot.py",
        root / "map-subsystem/scripts/dart_lsp_facts.py",
    )
    if not all(path.is_file() for path in required):
        missing = ", ".join(path.relative_to(root).as_posix() for path in required if not path.is_file())
        raise UserError(f"copied Dart external-library closure is incomplete: {missing}")
    return root


def _runtime_closure_evidence(library_root: Path) -> dict[str, Any]:
    paths = (
        library_root / "move-path/scripts/dart_library_move.py",
        library_root / "_dart/dart_project_snapshot.py",
        library_root / "_dart/scripts/dart_syntax_facts.py",
        library_root / "_dart/tool/bin/dart_syntax_facts.dart",
        library_root / "_dart/tool/pubspec.yaml",
        library_root / "_dart/tool/pubspec.lock",
        library_root / "map-subsystem/scripts/dart_lsp_facts.py",
    )
    rows: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(library_root).as_posix()):
        relative = path.relative_to(library_root).as_posix()
        file_hash = _hash_bytes(path.read_bytes())
        rows.append({"path": relative, "sha256": file_hash, "bytes": path.stat().st_size})
        digest.update(relative.encode() + b"\0" + file_hash.encode() + b"\n")
    return {"sha256": digest.hexdigest(), "files": rows}


def _dart_binary_evidence(raw: str) -> dict[str, Any]:
    candidate = Path(raw)
    if candidate.parent == Path("."):
        discovered = shutil.which(raw)
        if discovered is None:
            raise UserError("configured Dart binary is unavailable")
        candidate = Path(discovered)
    path = candidate.resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise UserError("configured Dart binary is not an executable regular file")
    return {"path": str(path), "sha256": _hash_bytes(path.read_bytes()), "bytes": path.stat().st_size}


def _excluded(path: Path, root: Path, report_dir: Path) -> bool:
    relative = path.relative_to(root)
    if relative.parts and relative.parts[0] == ".git":
        return True
    logical = _lexical(path)
    return logical == report_dir or _inside(logical, report_dir)


def _snapshot(
    root: Path, report_dir: Path
) -> tuple[dict[str, FileState], dict[str, str]]:
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
    digest = hashlib.sha256()
    rows = {
        **{path: _hash_bytes(state.contents) for path, state in files.items()},
        **{path: f"symlink:{target}" for path, target in links.items()},
    }
    for path, value in sorted(rows.items()):
        digest.update(path.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest()


def _snapshot_diff(
    expected_files: dict[str, FileState],
    expected_links: dict[str, str],
    actual_files: dict[str, FileState],
    actual_links: dict[str, str],
) -> dict[str, Any]:
    changed = sorted(
        path
        for path in expected_files.keys() & actual_files.keys()
        if expected_files[path] != actual_files[path]
    )
    result = {
        "expected_fingerprint": _fingerprint(expected_files, expected_links),
        "actual_fingerprint": _fingerprint(actual_files, actual_links),
        "changed": changed,
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
    result["passed"] = (
        not result["changed"]
        and not result["missing"]
        and not result["unexpected"]
        and not result["changed_symlinks"]
        and not result["missing_symlinks"]
        and not result["unexpected_symlinks"]
    )
    return result


def _restore(
    root: Path,
    report_dir: Path,
    before_files: dict[str, FileState],
    before_links: dict[str, str],
) -> None:
    current_files, current_links = _snapshot(root, report_dir)
    for relative in sorted(current_links, key=lambda item: len(PurePosixPath(item).parts), reverse=True):
        (root / relative).unlink(missing_ok=True)
    for relative in sorted(current_files, key=lambda item: len(PurePosixPath(item).parts), reverse=True):
        (root / relative).unlink(missing_ok=True)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if _excluded(path, root, report_dir) or path.is_symlink():
            continue
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    for relative, state in before_files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(state.contents)
        path.chmod(state.mode)
    for relative, target in before_links.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, path)


def _safe_relative(root: Path, raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise UserError(f"{label} must be a non-empty POSIX project-relative path")
    path = PurePosixPath(raw.rstrip("/"))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise UserError(f"{label} must stay inside project root")
    absolute = _lexical(root / Path(*path.parts))
    if not _inside(absolute, root):
        raise UserError(f"{label} must stay inside project root")
    return path.as_posix()


def _validate_cli(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    root_input = Path(args.project_root)
    if not root_input.is_dir() or root_input.is_symlink():
        raise UserError("project root must be a regular directory")
    root = root_input.resolve()
    plan = Path(args.plan)
    plan = plan if plan.is_absolute() else root / plan
    plan = _lexical(plan)
    if not _inside(plan, root) or _has_symlink(plan, root) or not plan.is_file():
        raise UserError("plan must be a regular file inside project root")
    report = Path(args.report_dir)
    report = report if report.is_absolute() else root / report
    report = _lexical(report)
    if report == root or not _inside(report, root) or _has_symlink(report, root):
        raise UserError("report directory must be a non-symlinked directory inside project root")
    return root, plan, report


def _load_plan(root: Path, plan_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UserError(f"plan is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise UserError("Dart move plan must be a version 1 JSON object")
    moves = payload.get("moves")
    if not isinstance(moves, list) or len(moves) != 1 or not isinstance(moves[0], dict):
        raise UserError("Dart v1 requires exactly one move")
    move = moves[0]
    source = _safe_relative(root, move.get("from"), "moves[0].from")
    destination = _safe_relative(root, move.get("to"), "moves[0].to")
    mode = move.get("mode")
    if mode not in {"file", "directory"}:
        raise UserError("moves[0].mode must be file or directory")
    if payload.get("rewrite", {}).get("code_imports") != "update-dart":
        raise UserError('rewrite.code_imports must be "update-dart"')
    section = payload.get("dart")
    if not isinstance(section, dict):
        raise UserError("dart configuration is required")
    if section.get("host_scope") not in {"disposable", "user-approved"}:
        raise UserError("dart.host_scope must explicitly be disposable or user-approved")
    barrels = section.get("public_barrels")
    if not isinstance(barrels, list) or not barrels:
        raise UserError("dart.public_barrels must declare at least one stable public barrel")
    normalized_barrels = [_safe_relative(root, value, "dart.public_barrels[]") for value in barrels]
    if len(set(normalized_barrels)) != len(normalized_barrels):
        raise UserError("dart.public_barrels contains duplicates")
    required_strings = ("binary", "package_config", "native_test", "smoke", "smoke_expected_stdout")
    if any(not isinstance(section.get(key), str) or not section[key] for key in required_strings):
        raise UserError("dart binary, package_config, native_test, smoke, and smoke_expected_stdout are required")
    normalized = {
        "version": 1,
        "move": {"from": source, "to": destination, "mode": mode},
        "rewrite": "update-dart",
        "dart": {
            "binary": section["binary"],
            "host_scope": section["host_scope"],
            "package_config": _safe_relative(root, section["package_config"], "dart.package_config"),
            "native_test": _safe_relative(root, section["native_test"], "dart.native_test"),
            "smoke": _safe_relative(root, section["smoke"], "dart.smoke"),
            "smoke_expected_stdout": section["smoke_expected_stdout"],
            "public_barrels": sorted(normalized_barrels),
            "pub_cache": section.get("pub_cache"),
        },
    }
    payload["_normalized"] = normalized
    return payload


def _is_private_library_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return len(parts) >= 3 and parts[:2] == ("lib", "src")


def _generated_path(path: str) -> bool:
    pure = PurePosixPath(path)
    lower = tuple(part.casefold() for part in pure.parts)
    return bool(set(lower[:-1]) & GENERATED_PARTS) or pure.name.casefold().endswith(GENERATED_SUFFIXES)


def _preflight_paths(root: Path, normalized: dict[str, Any]) -> list[dict[str, Any]]:
    move = normalized["move"]
    source = root / move["from"]
    destination = root / move["to"]
    blocked: list[dict[str, Any]] = []
    if not _is_private_library_path(move["from"]) or not _is_private_library_path(move["to"]):
        blocked.append({"kind": "dart_public_or_cross_package_move", "path": move["from"]})
    if _generated_path(move["from"]) or _generated_path(move["to"]):
        blocked.append({"kind": "dart_generated_move_path"})
    if destination.exists() or destination.is_symlink():
        blocked.append({"kind": "dart_destination_exists", "path": move["to"]})
    if move["mode"] == "file":
        if not source.is_file() or source.is_symlink() or source.suffix != ".dart":
            blocked.append({"kind": "dart_source_not_regular_library_file", "path": move["from"]})
    else:
        if not source.is_dir() or source.is_symlink():
            blocked.append({"kind": "dart_source_not_regular_leaf_directory", "path": move["from"]})
        else:
            children = list(source.iterdir())
            if not children or any(path.is_dir() or path.is_symlink() or path.suffix != ".dart" for path in children):
                blocked.append({"kind": "dart_source_not_regular_leaf_directory", "path": move["from"]})
    config = normalized["dart"]
    for label in (config["package_config"], config["native_test"], config["smoke"], *config["public_barrels"]):
        path = root / label
        if not path.is_file() or _has_symlink(path, root):
            blocked.append({"kind": "dart_required_file_missing_or_symlinked", "path": label})
    for barrel in config["public_barrels"]:
        if not barrel.startswith("lib/") or barrel.startswith("lib/src/"):
            blocked.append({"kind": "dart_public_barrel_not_public", "path": barrel})
    return blocked


def _map_after(path: str, source: str, destination: str) -> str:
    if path == source:
        return destination
    prefix = source + "/"
    if path.startswith(prefix):
        return destination + path[len(source) :]
    return path


def _path_moved(path: str, source: str) -> bool:
    return path == source or path.startswith(source + "/")


def _package_name(root: Path) -> str | None:
    match = re.search(
        r"(?m)^name:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:#.*)?$",
        (root / "pubspec.yaml").read_text(encoding="utf-8", errors="replace"),
    )
    return match.group(1) if match else None


def _resolve_lexical_uri(source: str, uri: str, package_name: str) -> str | None:
    if uri.startswith("dart:"):
        return None
    if uri.startswith("package:"):
        prefix = f"package:{package_name}/"
        if not uri.startswith(prefix):
            return None
        return "lib/" + uri[len(prefix) :]
    if ":" in uri or uri.startswith("/"):
        return None
    combined = PurePosixPath(source).parent / PurePosixPath(uri)
    parts: list[str] = []
    for part in combined.parts:
        if part == ".":
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return PurePosixPath(*parts).as_posix()


def _new_uri(
    source: str,
    target: str,
    uri: str,
    *,
    move_source: str,
    move_destination: str,
    package_name: str,
) -> str:
    source_after = _map_after(source, move_source, move_destination)
    target_after = _map_after(target, move_source, move_destination)
    if uri.startswith("package:"):
        if not target_after.startswith("lib/src/"):
            raise UserError("Dart v1 will not rewrite a public package URI")
        return f"package:{package_name}/{target_after[len('lib/') :]}"
    relative = os.path.relpath(target_after, PurePosixPath(source_after).parent.as_posix())
    return PurePosixPath(relative).as_posix()


def _exact_uri_span(source: bytes, directive: dict[str, Any]) -> tuple[int, int] | None:
    try:
        text = source.decode("utf-8")
        start = _utf16_offset_to_index(text, int(directive["offset"]))
        end = _utf16_offset_to_index(text, int(directive["end"]))
        uri = directive["uri"]
    except (UnicodeError, KeyError, TypeError, ValueError):
        return None
    fragment = text[start:end]
    for quote in ("'", '"'):
        token = quote + uri + quote
        relative = fragment.find(token)
        if relative >= 0 and fragment.find(token, relative + 1) < 0:
            uri_start = start + relative + 1
            return uri_start, uri_start + len(uri)
    return None


def _utf16_offset_to_index(text: str, offset: int) -> int:
    if offset < 0:
        raise ValueError("negative Dart source offset")
    units = 0
    for index, character in enumerate(text):
        if units == offset:
            return index
        units += 2 if ord(character) > 0xFFFF else 1
        if units > offset:
            raise ValueError("Dart source offset splits a UTF-16 surrogate pair")
    if units == offset:
        return len(text)
    raise ValueError("Dart source offset exceeds source length")


def _apply_replacements(content: bytes, changes: list[dict[str, Any]]) -> bytes:
    text = content.decode("utf-8")
    for row in sorted(changes, key=lambda item: item["start"], reverse=True):
        if text[row["start"] : row["end"]] != row["old"]:
            raise UserError(f"approved edit is stale in {row['file_before']}")
        text = text[: row["start"]] + row["new"] + text[row["end"] :]
    return text.encode("utf-8")


def _dart_sources(root: Path, report_dir: Path) -> list[Path]:
    sources: list[Path] = []
    for current_text, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_text)
        retained: list[str] = []
        for name in sorted(directory_names):
            path = current / name
            if _excluded(path, root, report_dir) or name in {".dart_tool", ".git"}:
                continue
            if path.is_symlink():
                continue
            retained.append(name)
        directory_names[:] = retained
        for name in sorted(file_names):
            path = current / name
            if path.suffix == ".dart" and not path.is_symlink():
                sources.append(path)
    return sorted(sources)


def _move_path_related(path: str, move: dict[str, str]) -> bool:
    return _path_moved(path, move["from"]) or _path_moved(path, move["to"])


def _moved_source_boundaries(
    root: Path, report_dir: Path, move: dict[str, str]
) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for source in _dart_sources(root, report_dir):
        relative = source.relative_to(root).as_posix()
        if not _path_moved(relative, move["from"]):
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        if _generated_path(relative) or GENERATED_MARKER.search(text[:4096]):
            blocked.append({"kind": "dart_generated_source", "path": relative})
        if re.search(r"(?m)^\s*(?:part\s+of|augment(?:ation)?)\b", text):
            blocked.append({"kind": "dart_part_or_augmentation", "path": relative})
        for token in DYNAMIC_TOKENS:
            if token in text:
                blocked.append({"kind": "dart_dynamic_loading_boundary", "path": relative, "token": token})
    return blocked


def _impacted_files(
    normalized: dict[str, Any], semantic: dict[str, Any]
) -> set[str]:
    move = normalized["move"]
    impacted = {
        row["path"]
        for row in semantic.get("source_inventory", [])
        if isinstance(row.get("path"), str) and _move_path_related(row["path"], move)
    }
    for edge in semantic.get("module_edges", []):
        source = edge.get("source")
        targets = [
            target.get("path")
            for target in edge.get("targets", [])
            if isinstance(target.get("path"), str)
        ]
        if not isinstance(source, str):
            continue
        if _move_path_related(source, move) or any(
            _move_path_related(target, move) for target in targets
        ):
            impacted.add(source)
            impacted.update(targets)
    return impacted


def _boundary_targets_move(
    path: str, boundary: dict[str, Any], move: dict[str, str], package_name: str
) -> bool:
    directive = boundary.get("directive")
    if not isinstance(directive, str):
        return False
    match = DIRECTIVE_RE.search(directive)
    if match is None:
        return False
    target = _resolve_lexical_uri(path, match.group("uri"), package_name)
    return target is not None and _move_path_related(target, move)


def _relevant_semantic_boundaries(
    normalized: dict[str, Any],
    semantic: dict[str, Any],
    impacted_files: set[str],
    package_name: str,
) -> list[dict[str, Any]]:
    move = normalized["move"]
    relevant: list[dict[str, Any]] = []
    for boundary in semantic.get("boundaries", []):
        path = boundary.get("path")
        if not isinstance(path, str):
            continue
        if (
            path in impacted_files
            or _move_path_related(path, move)
            or _boundary_targets_move(path, boundary, move, package_name)
        ):
            relevant.append(boundary)
    return relevant


def _impacted_closure_boundaries(
    root: Path,
    report_dir: Path,
    normalized: dict[str, Any],
    semantic: dict[str, Any],
    impacted_files: set[str],
) -> list[dict[str, Any]]:
    move = normalized["move"]
    package_name = _package_name(root)
    blocked: list[dict[str, Any]] = []
    for source in _dart_sources(root, report_dir):
        relative = source.relative_to(root).as_posix()
        if relative not in impacted_files and not _move_path_related(relative, move):
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        if _generated_path(relative) or GENERATED_MARKER.search(text[:4096]):
            blocked.append({"kind": "dart_generated_source", "path": relative})
        if re.search(r"(?m)^\s*(?:part\s+of|augment(?:ation)?)\b", text):
            blocked.append({"kind": "dart_part_or_augmentation", "path": relative})
        for token in DYNAMIC_TOKENS:
            if token in text:
                blocked.append(
                    {
                        "kind": "dart_dynamic_loading_boundary",
                        "path": relative,
                        "token": token,
                    }
                )
    if package_name is not None:
        for boundary in _relevant_semantic_boundaries(
            normalized, semantic, impacted_files, package_name
        ):
            path = boundary["path"]
            if boundary.get("kind") in {"part", "augmentation"}:
                blocked.append({"kind": "dart_part_or_augmentation", "path": path})
            else:
                blocked.append(
                    {
                        "kind": "dart_dynamic_loading_boundary",
                        "path": path,
                        "token": boundary.get("kind"),
                    }
                )
    return blocked


def _collect_facts(
    root: Path,
    normalized: dict[str, Any],
    library_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    syntax_module = _load_module(
        library_root / "_dart/scripts/dart_syntax_facts.py", "dart_d8_syntax_facts"
    )
    semantic_module = _load_module(
        library_root / "map-subsystem/scripts/dart_lsp_facts.py", "dart_d8_lsp_facts"
    )
    config = normalized["dart"]
    pub_cache_raw = config.get("pub_cache")
    pub_cache = Path(pub_cache_raw) if isinstance(pub_cache_raw, str) and pub_cache_raw else None
    syntax, _ = syntax_module.produce(
        root,
        root / "lib",
        dart=config["binary"],
        pub_cache=pub_cache,
        native_test=root / config["native_test"],
        smoke=root / config["smoke"],
        smoke_stdout=config["smoke_expected_stdout"],
        tool_root=library_root / "_dart/tool",
    )
    query_names = sorted(
        {
            row["name"]
            for file in syntax.get("files", [])
            for row in file.get("declarations", [])
            if row.get("top_level") and isinstance(row.get("name"), str) and row["name"]
        }
    )
    semantic = semantic_module.collect(
        root,
        ".",
        query_names,
        dart=config["binary"],
        packages=root / config["package_config"],
        cache_dir=None,
        timeout=30,
    )
    return syntax, semantic


def _fact_failure(
    syntax: dict[str, Any],
    semantic: dict[str, Any],
    *,
    normalized: dict[str, Any],
    impacted_files: set[str],
    package_name: str | None,
) -> tuple[str, str] | None:
    if syntax.get("status") == "failed":
        return "failed", str(syntax.get("failure_kind") or "dart_syntax_failed")
    if semantic.get("status") == "failed":
        return "failed", str(semantic.get("failure_kind") or "dart_semantic_failed")
    if syntax.get("status") != "complete":
        return "partial", str(syntax.get("failure_kind") or "dart_syntax_partial")
    if semantic.get("status") != "complete":
        boundary_reason = "conditional/part/augmentation/runtime boundaries are present"
        remaining_reasons = [
            reason
            for reason in semantic.get("partial_reasons", [])
            if reason != boundary_reason
        ]
        relevant_boundaries = (
            _relevant_semantic_boundaries(
                normalized, semantic, impacted_files, package_name
            )
            if package_name is not None
            else semantic.get("boundaries", [])
        )
        if remaining_reasons or relevant_boundaries:
            return "partial", str(
                semantic.get("failure_kind") or "dart_semantic_partial"
            )
    return None


def _plan_changes(
    root: Path,
    report_dir: Path,
    normalized: dict[str, Any],
    syntax: dict[str, Any],
    semantic: dict[str, Any],
    impacted_files: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    move = normalized["move"]
    package_name = _package_name(root)
    if package_name is None:
        return [], [{"kind": "dart_package_name_unresolved"}], []
    edges: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
    for edge in semantic.get("module_edges", []):
        key = (edge.get("source"), edge.get("kind"), edge.get("specifier"), edge.get("line"))
        edges.setdefault(key, []).append(edge)
    changes: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for file in syntax.get("files", []):
        source_name = file["file"]
        source = root / source_name
        contents = source.read_bytes()
        if _hash_bytes(contents) != file.get("source_sha256"):
            blocked.append({"kind": "dart_syntax_evidence_stale", "path": source_name})
            continue
        for directive in file.get("directives", []):
            kind = directive.get("kind")
            uri = directive.get("uri")
            if kind in {"part", "part_of"}:
                target = (
                    _resolve_lexical_uri(source_name, uri, package_name)
                    if isinstance(uri, str)
                    else None
                )
                if (
                    source_name in impacted_files
                    or _move_path_related(source_name, move)
                    or (target is not None and _move_path_related(target, move))
                ):
                    blocked.append(
                        {"kind": "dart_part_directive", "path": source_name}
                    )
                continue
            if directive.get("supported") is False:
                blocked.append(
                    {
                        "kind": directive.get("unsupported_reason") or "dart_unsupported_directive",
                        "path": source_name,
                        "line": directive.get("line"),
                    }
                )
                continue
            if kind not in {"import", "export"} or not isinstance(uri, str) or uri.startswith("dart:"):
                continue
            matches = edges.get((source_name, kind, uri, directive.get("line")), [])
            if len(matches) != 1 or len(matches[0].get("targets", [])) != 1:
                blocked.append(
                    {
                        "kind": "dart_unresolved_module_edge",
                        "path": source_name,
                        "line": directive.get("line"),
                        "uri": uri,
                    }
                )
                continue
            target = matches[0]["targets"][0]["path"]
            lexical = _resolve_lexical_uri(source_name, uri, package_name)
            if lexical != target:
                blocked.append(
                    {
                        "kind": "dart_lexical_semantic_identity_mismatch",
                        "path": source_name,
                        "uri": uri,
                        "semantic_target": target,
                        "lexical_target": lexical,
                    }
                )
                continue
            impacted = _path_moved(source_name, move["from"]) or _path_moved(target, move["from"])
            if not impacted:
                continue
            if uri.startswith("package:") and not uri.startswith(f"package:{package_name}/src/"):
                blocked.append({"kind": "dart_public_or_external_package_uri", "path": source_name, "uri": uri})
                continue
            span = _exact_uri_span(contents, directive)
            if span is None:
                blocked.append({"kind": "dart_directive_span_unproved", "path": source_name, "line": directive.get("line")})
                continue
            replacement = _new_uri(
                source_name,
                target,
                uri,
                move_source=move["from"],
                move_destination=move["to"],
                package_name=package_name,
            )
            if replacement == uri:
                continue
            source_after = _map_after(source_name, move["from"], move["to"])
            changes.append(
                {
                    "file_before": source_name,
                    "file_after": source_after,
                    "source_sha256": file["source_sha256"],
                    "start": span[0],
                    "end": span[1],
                    "old": uri,
                    "new": replacement,
                    "kind": kind,
                    "target_before": target,
                    "target_after": _map_after(target, move["from"], move["to"]),
                    "line": directive.get("line"),
                }
            )

    syntax_files = {file["file"] for file in syntax.get("files", [])}
    old_identities = {
        row["old"] for row in changes
    } | {
        move["from"],
        f"package:{package_name}/{move['from'][len('lib/') :]}",
    }
    for source in _dart_sources(root, report_dir):
        relative = source.relative_to(root).as_posix()
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in DIRECTIVE_RE.finditer(text):
            kind = match.group("kind")
            uri = match.group("uri")
            if kind.startswith("part"):
                target = _resolve_lexical_uri(relative, uri, package_name)
                if (
                    relative in impacted_files
                    or _move_path_related(relative, move)
                    or (target is not None and _move_path_related(target, move))
                ):
                    blocked.append(
                        {
                            "kind": "dart_part_directive",
                            "path": relative,
                            "line": text[: match.start()].count("\n") + 1,
                        }
                    )
            if " if (" in match.group("tail"):
                blocked.append({"kind": "conditional_configuration", "path": relative, "line": text[: match.start()].count("\n") + 1})
            if relative not in syntax_files:
                target = _resolve_lexical_uri(relative, uri, package_name)
                if target and (_path_moved(target, move["from"]) or _path_moved(relative, move["from"])):
                    blocked.append(
                        {
                            "kind": "dart_unresolved_excluded_role_impact",
                            "path": relative,
                            "uri": uri,
                        }
                    )
        for identity in sorted(old_identities):
            for match in re.finditer(rf"(['\"]){re.escape(identity)}\1", text):
                offset = match.start() + 1
                if not any(
                    row["file_before"] == relative and row["start"] <= offset < row["end"]
                    for row in changes
                ):
                    blocked.append(
                        {
                            "kind": "dart_unproved_dynamic_identity",
                            "path": relative,
                            "identity": identity,
                        }
                    )

    blocked.extend(
        _impacted_closure_boundaries(
            root, report_dir, normalized, semantic, impacted_files
        )
    )
    barrels_preserved: list[str] = []
    for barrel in normalized["dart"]["public_barrels"]:
        barrel_changes = [row for row in changes if row["file_before"] == barrel and row["kind"] == "export"]
        if not barrel_changes:
            blocked.append({"kind": "dart_declared_barrel_does_not_export_move", "path": barrel})
        else:
            barrels_preserved.append(barrel)
    unique_blocked = list({json.dumps(row, sort_keys=True): row for row in blocked}.values())
    return sorted(changes, key=lambda row: (row["file_before"], row["start"])), unique_blocked, sorted(barrels_preserved)


def _patched_files(
    before: dict[str, FileState], changes: list[dict[str, Any]]
) -> dict[str, bytes]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in changes:
        grouped.setdefault(row["file_before"], []).append(row)
    return {
        path: _apply_replacements(before[path].contents, rows)
        for path, rows in grouped.items()
    }


def _expected_snapshot(
    before: dict[str, FileState],
    move: dict[str, str],
    patches: dict[str, bytes],
) -> dict[str, FileState]:
    expected: dict[str, FileState] = {}
    for relative, state in before.items():
        after = _map_after(relative, move["from"], move["to"])
        expected[after] = FileState(patches.get(relative, state.contents), state.mode)
    return expected


def _preview_diff(
    before: dict[str, FileState], expected: dict[str, FileState], move: dict[str, str]
) -> str:
    chunks: list[str] = []
    for old in sorted(before):
        state = before[old]
        new = _map_after(old, move["from"], move["to"])
        after_state = expected.get(new)
        if after_state is None or old != new or state.contents != after_state.contents:
            old_text = state.contents.decode("utf-8", errors="replace").splitlines(keepends=True)
            new_text = (after_state.contents if after_state else b"").decode("utf-8", errors="replace").splitlines(keepends=True)
            chunks.extend(difflib.unified_diff(old_text, new_text, fromfile=old, tofile=new))
    return "".join(chunks)


def _evidence_payload(
    *,
    normalized: dict[str, Any],
    before_files: dict[str, FileState],
    before_links: dict[str, str],
    expected: dict[str, FileState],
    changes: list[dict[str, Any]],
    barrels: list[str],
    syntax: dict[str, Any],
    semantic: dict[str, Any],
    runtime_closure: dict[str, Any],
    dart_binary: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "plan_sha256": _canonical_hash(normalized),
        "source_tree_sha256": _fingerprint(before_files, before_links),
        "expected_after_tree_sha256": _fingerprint(expected, before_links),
        "move": normalized["move"],
        "host_scope": normalized["dart"]["host_scope"],
        "public_barrels": barrels,
        "exact_changes": changes,
        "syntax_evidence": {
            "analyzer": syntax.get("analyzer"),
            "analyzer_package": syntax.get("analyzer_package"),
            "source_manifest_sha256": syntax.get("source_manifest", {}).get("before_sha256"),
            "tool_package_sha256": syntax.get("tool_package", {}).get("sha256"),
            "dart": syntax.get("tools", {}).get("dart"),
        },
        "semantic_evidence": {
            "fact_pack_sha256": semantic.get("fact_pack_sha256"),
            "query_plan_sha256": semantic.get("query_plan_sha256"),
            "package_config": semantic.get("package_config"),
            "source_hashes": semantic.get("source_hashes"),
        },
        "runtime_closure": runtime_closure,
        "dart_binary": dart_binary,
    }
    payload["evidence_sha256"] = _canonical_hash(payload)
    return payload


def _load_evidence(
    root: Path,
    report_dir: Path,
    raw: str | None,
    normalized: dict[str, Any],
) -> tuple[dict[str, Any], Path]:
    if not raw:
        raise UserError("--evidence is required for Dart apply/check")
    path = Path(raw)
    path = path if path.is_absolute() else root / path
    path = _lexical(path)
    if not _inside(path, report_dir) or _has_symlink(path, root) or not path.is_file():
        raise UserError("evidence must be a regular file inside the selected report directory")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UserError(f"Dart move evidence is invalid: {exc}") from exc
    supplied = payload.get("evidence_sha256")
    unhashed = dict(payload)
    unhashed.pop("evidence_sha256", None)
    if payload.get("schema_version") != SCHEMA_VERSION or supplied != _canonical_hash(unhashed):
        raise UserError("Dart move evidence hash does not verify")
    if payload.get("status") != "complete" or payload.get("plan_sha256") != _canonical_hash(normalized):
        raise UserError("Dart move evidence does not authorize this exact plan")
    return payload, path


def _apply_move(
    root: Path,
    move: dict[str, str],
    patches: dict[str, bytes],
) -> None:
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


def _old_identity_remaining(root: Path, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    remaining: list[dict[str, Any]] = []
    for row in evidence["exact_changes"]:
        path = root / row["file_after"]
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        old = row["old"]
        directive_uris = {match.group("uri") for match in DIRECTIVE_RE.finditer(text)}
        quoted_old = re.search(rf"(['\"]){re.escape(old)}\1", text) is not None
        if old in directive_uris or quoted_old:
            remaining.append({"path": row["file_after"], "identity": row["old"]})
    return remaining


def _base_report(
    *,
    mode: str,
    status: str,
    failure_kind: str,
    normalized: dict[str, Any],
    source_tree_sha256: str,
    blocked: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_VERSION,
        "dart": {
            "mode": mode,
            "status": status,
            "failure_kind": failure_kind,
            "move": normalized["move"],
            "host_scope": normalized["dart"]["host_scope"],
            "source_tree_sha256": source_tree_sha256,
            "blocked": blocked or [],
            "exact_changes": [],
            "public_barrels_preserved": [],
            "rolled_back": False,
            "old_identity_remaining": [],
            "further_edits": [],
        },
    }


def _markdown(report: dict[str, Any]) -> str:
    dart = report["dart"]
    lines = [
        "# Dart move-path report",
        "",
        f"Status: `{dart['status']}`",
        f"Mode: `{dart['mode']}`",
        f"Failure: `{dart['failure_kind']}`",
        f"Source tree: `{dart['source_tree_sha256']}`",
        "",
        "## Move",
        "",
        f"- `{dart['move']['from']}` → `{dart['move']['to']}`",
        f"- exact directive edits: {len(dart.get('exact_changes', []))}",
        f"- rolled back: {str(dart.get('rolled_back', False)).lower()}",
    ]
    if dart.get("evidence_sha256"):
        lines.append(f"- reviewed evidence: `{dart['evidence_sha256']}`")
    if dart.get("blocked"):
        lines.extend(["", "## Blocked", ""])
        lines.extend(f"- `{row['kind']}`: `{row.get('path', '')}`" for row in dart["blocked"])
    return "\n".join(lines) + "\n"


def _write_report(report_dir: Path, report: dict[str, Any]) -> None:
    _atomic_json(report_dir / "report.json", report)
    _atomic_text(report_dir / "report.md", _markdown(report))


def _dry_run(
    root: Path,
    report_dir: Path,
    normalized: dict[str, Any],
    library_root: Path,
) -> tuple[dict[str, Any], int]:
    # A partial/failed rerun must not leave prior mutation authority available.
    (report_dir / "evidence.json").unlink(missing_ok=True)
    before_files, before_links = _snapshot(root, report_dir)
    source_hash = _fingerprint(before_files, before_links)
    blocked = _preflight_paths(root, normalized) + _moved_source_boundaries(
        root, report_dir, normalized["move"]
    )
    if blocked:
        report = _base_report(
            mode="dry-run",
            status="partial",
            failure_kind="unsafe_dart_move_shape",
            normalized=normalized,
            source_tree_sha256=source_hash,
            blocked=blocked,
        )
        _write_report(report_dir, report)
        return report, 0
    syntax, semantic = _collect_facts(root, normalized, library_root)
    after_fact_files, after_fact_links = _snapshot(root, report_dir)
    if _fingerprint(after_fact_files, after_fact_links) != source_hash:
        report = _base_report(
            mode="dry-run",
            status="failed",
            failure_kind="source_changed_during_evidence",
            normalized=normalized,
            source_tree_sha256=source_hash,
        )
        _write_report(report_dir, report)
        return report, 2
    impacted_files = _impacted_files(normalized, semantic)
    package_name = _package_name(root)
    fact_failure = _fact_failure(
        syntax,
        semantic,
        normalized=normalized,
        impacted_files=impacted_files,
        package_name=package_name,
    )
    changes, plan_blocked, barrels = _plan_changes(
        root, report_dir, normalized, syntax, semantic, impacted_files
    )
    if fact_failure or plan_blocked:
        status, failure = fact_failure or ("partial", "unresolved_dart_move_evidence")
        report = _base_report(
            mode="dry-run",
            status=status,
            failure_kind=failure,
            normalized=normalized,
            source_tree_sha256=source_hash,
            blocked=plan_blocked,
        )
        report["dart"]["syntax_preflight"] = syntax
        report["dart"]["semantic_preflight"] = semantic
        _write_report(report_dir, report)
        return report, 2 if status == "failed" else 0
    patches = _patched_files(before_files, changes)
    expected = _expected_snapshot(before_files, normalized["move"], patches)
    evidence = _evidence_payload(
        normalized=normalized,
        before_files=before_files,
        before_links=before_links,
        expected=expected,
        changes=changes,
        barrels=barrels,
        syntax=syntax,
        semantic=semantic,
        runtime_closure=_runtime_closure_evidence(library_root),
        dart_binary=_dart_binary_evidence(normalized["dart"]["binary"]),
    )
    _atomic_json(report_dir / "evidence.json", evidence)
    report = _base_report(
        mode="dry-run",
        status="complete",
        failure_kind="none",
        normalized=normalized,
        source_tree_sha256=source_hash,
    )
    report["dart"].update(
        evidence_sha256=evidence["evidence_sha256"],
        expected_after_tree_sha256=evidence["expected_after_tree_sha256"],
        exact_changes=changes,
        public_barrels_preserved=barrels,
        preview_diff=_preview_diff(before_files, expected, normalized["move"]),
        native_preflight={"status": syntax["status"], "checks": syntax.get("native", {})},
        syntax_evidence=evidence["syntax_evidence"],
        semantic_evidence=evidence["semantic_evidence"],
    )
    _write_report(report_dir, report)
    return report, 0


def _apply(
    args: argparse.Namespace,
    root: Path,
    report_dir: Path,
    normalized: dict[str, Any],
    library_root: Path,
) -> tuple[dict[str, Any], int]:
    evidence, _ = _load_evidence(root, report_dir, args.evidence, normalized)
    if args.approve_evidence_sha256 != evidence["evidence_sha256"]:
        raise UserError("--approve-evidence-sha256 must equal the reviewed evidence hash")
    before_files, before_links = _snapshot(root, report_dir)
    current_hash = _fingerprint(before_files, before_links)
    report = _base_report(
        mode="apply",
        status="failed",
        failure_kind="stale_move_evidence",
        normalized=normalized,
        source_tree_sha256=current_hash,
    )
    report["dart"].update(
        evidence_sha256=evidence["evidence_sha256"],
        exact_changes=evidence["exact_changes"],
        public_barrels_preserved=evidence["public_barrels"],
    )
    current_closure = _runtime_closure_evidence(library_root)
    current_dart = _dart_binary_evidence(normalized["dart"]["binary"])
    if (
        current_closure != evidence.get("runtime_closure")
        or current_dart != evidence.get("dart_binary")
    ):
        _write_report(report_dir, report)
        return report, 2
    if current_hash != evidence["source_tree_sha256"]:
        _write_report(report_dir, report)
        return report, 2
    for row in evidence["exact_changes"]:
        state = before_files.get(row["file_before"])
        if state is None or _hash_bytes(state.contents) != row["source_sha256"]:
            _write_report(report_dir, report)
            return report, 2
    patches = _patched_files(before_files, evidence["exact_changes"])
    expected = _expected_snapshot(before_files, normalized["move"], patches)
    try:
        _apply_move(root, normalized["move"], patches)
        syntax, semantic = _collect_facts(root, normalized, library_root)
        failure = _fact_failure(
            syntax,
            semantic,
            normalized=normalized,
            impacted_files=_impacted_files(normalized, semantic),
            package_name=_package_name(root),
        )
        report["dart"]["native_postflight"] = {
            "status": syntax.get("status"),
            "checks": syntax.get("native", {}),
        }
        report["dart"]["semantic_postflight"] = {
            "status": semantic.get("status"),
            "fact_pack_sha256": semantic.get("fact_pack_sha256"),
        }
        if failure:
            report["dart"]["failure_kind"] = failure[1]
            raise UserError(failure[1])
        actual_files, actual_links = _snapshot(root, report_dir)
        exact = _snapshot_diff(expected, before_links, actual_files, actual_links)
        report["dart"]["exact_after_tree"] = exact
        remaining = _old_identity_remaining(root, evidence)
        report["dart"]["old_identity_remaining"] = remaining
        if not exact["passed"] or remaining:
            report["dart"]["failure_kind"] = (
                "exact_after_tree_failed" if not exact["passed"] else "old_identity_residue"
            )
            raise UserError(report["dart"]["failure_kind"])
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - rollback owns every post-mutation failure
        _restore(root, report_dir, before_files, before_links)
        report["dart"]["status"] = "failed"
        report["dart"]["rolled_back"] = True
        if report["dart"]["failure_kind"] == "stale_move_evidence":
            report["dart"]["failure_kind"] = "dart_apply_failed"
        report["dart"]["failure_detail"] = str(exc)
        restored_files, restored_links = _snapshot(root, report_dir)
        report["dart"]["rollback_exact"] = _snapshot_diff(
            before_files, before_links, restored_files, restored_links
        )
        _write_report(report_dir, report)
        return report, 2
    report["dart"].update(status="complete", failure_kind="none", rolled_back=False)
    _write_report(report_dir, report)
    return report, 0


def _check(
    args: argparse.Namespace,
    root: Path,
    report_dir: Path,
    normalized: dict[str, Any],
    library_root: Path,
) -> tuple[dict[str, Any], int]:
    evidence, _ = _load_evidence(root, report_dir, args.evidence, normalized)
    files, links = _snapshot(root, report_dir)
    current_hash = _fingerprint(files, links)
    report = _base_report(
        mode="check",
        status="failed",
        failure_kind="after_tree_mismatch",
        normalized=normalized,
        source_tree_sha256=current_hash,
    )
    report["dart"].update(
        evidence_sha256=evidence["evidence_sha256"],
        exact_changes=evidence["exact_changes"],
        public_barrels_preserved=evidence["public_barrels"],
    )
    if (
        _runtime_closure_evidence(library_root) != evidence.get("runtime_closure")
        or _dart_binary_evidence(normalized["dart"]["binary"])
        != evidence.get("dart_binary")
    ):
        report["dart"]["failure_kind"] = "stale_move_evidence"
        _write_report(report_dir, report)
        return report, 2
    if current_hash != evidence["expected_after_tree_sha256"]:
        report["dart"]["further_edits"] = ["current tree differs from approved after tree"]
        _write_report(report_dir, report)
        return report, 2
    syntax, semantic = _collect_facts(root, normalized, library_root)
    failure = _fact_failure(
        syntax,
        semantic,
        normalized=normalized,
        impacted_files=_impacted_files(normalized, semantic),
        package_name=_package_name(root),
    )
    report["dart"]["native_postflight"] = {
        "status": syntax.get("status"),
        "checks": syntax.get("native", {}),
    }
    remaining = _old_identity_remaining(root, evidence)
    report["dart"]["old_identity_remaining"] = remaining
    if failure or remaining:
        report["dart"]["failure_kind"] = failure[1] if failure else "old_identity_residue"
        _write_report(report_dir, report)
        return report, 2
    report["dart"].update(status="complete", failure_kind="none", further_edits=[])
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
        plan = _load_plan(root, plan_path)
        normalized = plan["_normalized"]
        library_root = _library_root()
        if args.dry_run:
            report, code = _dry_run(root, report_dir, normalized, library_root)
        elif args.apply:
            report, code = _apply(args, root, report_dir, normalized, library_root)
        else:
            report, code = _check(args, root, report_dir, normalized, library_root)
    except UserError as exc:
        print(f"dart move refused: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Dart move {report['dart']['mode']}: {report['dart']['status']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
