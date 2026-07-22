#!/usr/bin/env python3
"""Preview, apply, and verify one bounded conventional Rust module move."""
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
from pathlib import Path


MINIMUMS = {
    "cargo": (1, 85, 0),
    "rustc": (1, 85, 0),
    "cargo_clippy": (0, 1, 85),
    "rustfmt": (1, 8, 0),
}
EXCLUDED_PARTS = frozenset({"generated", "vendor", "target", "build", "dist", "out"})
BUILD_OUTPUT_TOKENS = (
    "OUT_DIR",
    "cargo:rustc-cfg",
    "cargo:rustc-env",
    "include!",
    "fs::write",
    "File::create",
)
RUST_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UserError(Exception):
    """Unsafe invocation that must not touch final artifacts."""


@dataclass(frozen=True)
class FileState:
    contents: bytes
    mode: int


@dataclass(frozen=True)
class Token:
    value: str
    start: int
    end: int
    kind: str = "punct"


@dataclass(frozen=True)
class Replacement:
    file_before: str
    file_after: str
    start: int
    end: int
    old: str
    new: str
    kind: str
    line: int


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _has_symlink(path: Path, root: Path) -> bool:
    if not _inside(path, root):
        return True
    current = path
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


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 180,
) -> dict:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": argv,
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "argv": argv,
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[:8000],
        "stderr": result.stderr[:8000],
    }


def _excluded_from_snapshot(path: Path, root: Path, report_dir: Path) -> bool:
    relative = path.relative_to(root)
    if ".git" in relative.parts:
        return True
    lexical = Path(os.path.abspath(path))
    return lexical == report_dir or _inside(lexical, report_dir)


def _snapshot(
    root: Path, report_dir: Path
) -> tuple[dict[str, FileState], dict[str, str]]:
    files: dict[str, FileState] = {}
    links: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if _excluded_from_snapshot(path, root, report_dir):
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            links[relative] = os.readlink(path)
        elif path.is_file():
            files[relative] = FileState(
                path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
            )
    return files, links


def _fingerprint(files: dict[str, FileState], links: dict[str, str]) -> str:
    digest = hashlib.sha256()
    rows = {
        **{
            path: hashlib.sha256(state.contents).hexdigest()
            for path, state in files.items()
        },
        **{path: f"symlink:{target}" for path, target in links.items()},
    }
    for path, value in sorted(rows.items()):
        digest.update(path.encode("utf-8") + b"\0" + value.encode("utf-8") + b"\n")
    return digest.hexdigest()


def _map_after_path(path: str, source: str, destination: str) -> str:
    if path == source:
        return destination
    prefix = source + "/"
    if path.startswith(prefix):
        return destination + path[len(source):]
    return path


def _expected_snapshot(
    before: dict[str, FileState],
    source: str,
    destination: str,
    patched: dict[str, bytes],
) -> dict[str, FileState]:
    expected: dict[str, FileState] = {}
    for relative, state in before.items():
        after = _map_after_path(relative, source, destination)
        expected[after] = FileState(patched.get(relative, state.contents), state.mode)
    return expected


def _snapshot_diff(
    expected: dict[str, FileState],
    expected_links: dict[str, str],
    actual: dict[str, FileState],
    actual_links: dict[str, str],
) -> dict:
    changed = sorted(
        path
        for path in expected.keys() & actual.keys()
        if expected[path] != actual[path]
    )
    missing = sorted(expected.keys() - actual.keys())
    unexpected = sorted(actual.keys() - expected.keys())
    link_changed = sorted(
        path
        for path in expected_links.keys() & actual_links.keys()
        if expected_links[path] != actual_links[path]
    )
    return {
        "passed": not changed and not missing and not unexpected
        and expected_links == actual_links,
        "expected_fingerprint": _fingerprint(expected, expected_links),
        "actual_fingerprint": _fingerprint(actual, actual_links),
        "changed": changed,
        "missing": missing,
        "unexpected": unexpected,
        "changed_symlinks": link_changed,
        "missing_symlinks": sorted(expected_links.keys() - actual_links.keys()),
        "unexpected_symlinks": sorted(actual_links.keys() - expected_links.keys()),
    }


def _restore(
    root: Path,
    report_dir: Path,
    before: dict[str, FileState],
    links: dict[str, str],
) -> None:
    current_files, current_links = _snapshot(root, report_dir)
    for relative in sorted(current_links, key=lambda item: len(Path(item).parts), reverse=True):
        (root / relative).unlink(missing_ok=True)
    for relative in sorted(current_files, key=lambda item: len(Path(item).parts), reverse=True):
        (root / relative).unlink(missing_ok=True)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if _excluded_from_snapshot(path, root, report_dir):
            continue
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                pass
    for relative, state in before.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(state.contents)
        path.chmod(state.mode)
    for relative, target in links.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, path)


def _validate_cli(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    root_input = Path(args.project_root)
    if not root_input.is_dir() or root_input.is_symlink():
        raise UserError("project root must be a regular directory")
    root = root_input.resolve()
    plan = Path(args.plan)
    plan = plan if plan.is_absolute() else root / plan
    plan = Path(os.path.abspath(plan))
    if not _inside(plan, root) or _has_symlink(plan, root) or not plan.is_file():
        raise UserError("plan must be a regular file inside project root")
    report = Path(args.report_dir)
    report = report if report.is_absolute() else root / report
    report = Path(os.path.abspath(report))
    if report == root or not _inside(report, root):
        raise UserError("report directory must stay inside project root")
    if _has_symlink(report, root):
        raise UserError("report directory must not traverse a symbolic link")
    return root, plan, report


def _safe_move_path(root: Path, value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise UserError(f"{label} must be a non-empty POSIX project-relative path")
    path = Path(value.rstrip("/"))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise UserError(f"{label} must stay inside project root")
    absolute = Path(os.path.abspath(root / path))
    if not _inside(absolute, root):
        raise UserError(f"{label} must stay inside project root")
    return path.as_posix()


def _load_plan(root: Path, plan_path: Path) -> dict:
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        return {"_error": "plan_invalid", "_message": str(exc)}
    if not isinstance(plan, dict):
        return {"_error": "plan_invalid", "_message": "plan must be a JSON object"}
    moves = plan.get("moves")
    if not isinstance(moves, list) or not moves:
        return {"_error": "plan_invalid", "_message": "moves must be a non-empty list"}
    normalized = []
    for index, move in enumerate(moves):
        if not isinstance(move, dict):
            return {"_error": "plan_invalid", "_message": f"move {index} must be an object"}
        source = _safe_move_path(root, move.get("from"), f"moves[{index}].from")
        destination = _safe_move_path(root, move.get("to"), f"moves[{index}].to")
        mode = move.get("mode")
        if mode not in {"file", "directory"}:
            return {"_error": "plan_invalid", "_message": f"move {index} mode must be file or directory"}
        normalized.append({"from": source, "to": destination, "mode": mode})
    plan["_moves"] = normalized
    return plan


def _resolve_tool(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if "/" in value:
        path = Path(value)
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(value)


def _parse_version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _toolchain(root: Path, section: object) -> tuple[dict, list[dict]]:
    if not isinstance(section, dict):
        return {}, [{"kind": "rust_config_required"}]
    specs = {
        "cargo": section.get("cargo", "cargo"),
        "rustc": section.get("rustc", "rustc"),
        "cargo_clippy": section.get("cargo_clippy", "cargo-clippy"),
        "rustfmt": section.get("rustfmt", "rustfmt"),
    }
    tools: dict[str, dict] = {}
    blocked: list[dict] = []
    for name, raw in specs.items():
        path = _resolve_tool(raw)
        if path is None:
            kind = "rust_tool_missing" if name in {"cargo", "rustc"} else "rust_optional_native_tool_missing"
            blocked.append({"kind": kind, "tool": name, "state": "pending-tooling"})
            tools[name] = {"path": None, "status": "missing"}
            continue
        result = _run([path, "--version"], cwd=root, timeout=15)
        version = _parse_version(result["stdout"] + result["stderr"])
        if not result["passed"] or version is None:
            blocked.append({"kind": "rust_tool_probe_failed", "tool": name, "state": "pending-tooling"})
            tools[name] = {"path": path, "status": "unavailable", "probe": result}
            continue
        if version < MINIMUMS[name]:
            blocked.append({
                "kind": "rust_tool_too_old",
                "tool": name,
                "version": ".".join(map(str, version)),
                "minimum": ".".join(map(str, MINIMUMS[name])),
                "state": "pending-tooling",
            })
            tools[name] = {"path": path, "status": "too-old", "version": ".".join(map(str, version))}
            continue
        tools[name] = {
            "path": path,
            "status": "available",
            "version": ".".join(map(str, version)),
            "probe": (result["stdout"] + result["stderr"]).strip().splitlines()[0],
        }
    return tools, blocked


def _cargo_environment(tools: dict, state: Path) -> dict[str, str]:
    path_dirs = {
        str(Path(row["path"]).parent)
        for row in tools.values()
        if row.get("path")
    }
    cargo_home = state / "cargo-home"
    target = state / "target"
    cargo_home.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "CARGO_HOME": str(cargo_home),
        "CARGO_NET_OFFLINE": "true",
        "CARGO_TARGET_DIR": str(target),
        "RUSTC": tools["rustc"]["path"],
        "PATH": os.pathsep.join([*sorted(path_dirs), os.environ.get("PATH", "")]),
        "ALL_PROXY": "http://127.0.0.1:9",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
    }


def _metadata(tools: dict, root: Path, env: dict[str, str]) -> tuple[dict | None, dict]:
    result = _run([
        tools["cargo"]["path"], "metadata", "--format-version", "1",
        "--locked", "--offline", "--no-deps",
    ], cwd=root, env=env)
    if not result["passed"]:
        return None, result
    try:
        return json.loads(result["stdout"]), result
    except json.JSONDecodeError as exc:
        result["passed"] = False
        result["stderr"] = f"cargo metadata emitted invalid JSON: {exc}"
        return None, result


def _native_suite(
    tools: dict,
    root: Path,
    state: Path,
    smoke_package: object,
    expected_stdout: object,
) -> tuple[dict, str | None]:
    env = _cargo_environment(tools, state)
    metadata, metadata_run = _metadata(tools, root, env)
    native: dict[str, dict] = {"cargo_metadata": metadata_run}
    if metadata is None:
        return native, "cargo_metadata_failed"
    commands = (
        (
            "cargo_check",
            [tools["cargo"]["path"], "check", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"],
            "cargo_check_failed",
        ),
        (
            "cargo_test",
            [tools["cargo"]["path"], "test", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"],
            "cargo_test_failed",
        ),
        (
            "clippy",
            [tools["cargo"]["path"], "clippy", "--locked", "--offline", "--workspace", "--all-targets", "--all-features", "--", "-D", "warnings"],
            "cargo_clippy_failed",
        ),
        (
            "rustfmt",
            [tools["cargo"]["path"], "fmt", "--all", "--", "--check"],
            "cargo_rustfmt_failed",
        ),
    )
    for key, argv, failure in commands:
        native[key] = _run(argv, cwd=root, env=env)
        if not native[key]["passed"]:
            return native, failure
    if not isinstance(smoke_package, str) or not smoke_package or not isinstance(expected_stdout, str):
        native["smoke"] = {
            "argv": [], "passed": False, "returncode": None,
            "stdout": "", "stderr": "rust.smoke_package and smoke_expected_stdout are required",
        }
        return native, "cargo_smoke_configuration_missing"
    native["smoke"] = _run([
        tools["cargo"]["path"], "run", "--quiet", "--locked", "--offline",
        "-p", smoke_package,
    ], cwd=root, env=env)
    native["smoke"]["passed"] = (
        native["smoke"]["passed"]
        and native["smoke"]["stdout"] == expected_stdout
    )
    if not native["smoke"]["passed"]:
        return native, "cargo_smoke_failed"
    return native, None


def _scan_tokens(text: str) -> tuple[list[Token], list[tuple[int, int, str]]]:
    tokens: list[Token] = []
    excluded: list[tuple[int, int, str]] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index)
            end = length if end < 0 else end
            excluded.append((index, end, text[index:end]))
            index = end
            continue
        if text.startswith("/*", index):
            depth = 1
            cursor = index + 2
            while cursor < length and depth:
                if text.startswith("/*", cursor):
                    depth += 1
                    cursor += 2
                elif text.startswith("*/", cursor):
                    depth -= 1
                    cursor += 2
                else:
                    cursor += 1
            end = cursor
            excluded.append((index, end, text[index:end]))
            index = end
            continue
        raw = re.match(r"(?:br|r)(#+)?\"", text[index:])
        if raw:
            hashes = raw.group(1) or ""
            start = index
            cursor = index + raw.end()
            closing = '"' + hashes
            found = text.find(closing, cursor)
            end = length if found < 0 else found + len(closing)
            excluded.append((start, end, text[start:end]))
            index = end
            continue
        quote_start = None
        if text.startswith('b"', index):
            quote_start = index + 1
        elif char == '"':
            quote_start = index
        if quote_start is not None:
            start = index
            cursor = quote_start + 1
            escaped = False
            while cursor < length:
                current = text[cursor]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    cursor += 1
                    break
                cursor += 1
            excluded.append((start, cursor, text[start:cursor]))
            index = cursor
            continue
        if char == "'":
            closing = text.find("'", index + 1)
            if closing >= 0 and closing - index <= 8:
                excluded.append((index, closing + 1, text[index:closing + 1]))
                index = closing + 1
                continue
        raw_identifier = re.match(r"r#[A-Za-z_][A-Za-z0-9_]*", text[index:])
        if raw_identifier:
            end = index + raw_identifier.end()
            tokens.append(Token(text[index:end], index, end, "raw-ident"))
            index = end
            continue
        identifier = re.match(r"[A-Za-z_][A-Za-z0-9_]*", text[index:])
        if identifier:
            end = index + identifier.end()
            tokens.append(Token(text[index:end], index, end, "ident"))
            index = end
            continue
        if text.startswith("::", index):
            tokens.append(Token("::", index, index + 2))
            index += 2
            continue
        tokens.append(Token(char, index, index + 1))
        index += 1
    return tokens, excluded


def _balanced_macro_ranges(tokens: list[Token], old_name: str) -> list[dict]:
    blocked: list[dict] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    for index, token in enumerate(tokens):
        if token.value != "!" or index + 1 >= len(tokens):
            continue
        opener = tokens[index + 1].value
        if opener not in pairs:
            continue
        depth = 0
        end = index + 1
        for cursor in range(index + 1, len(tokens)):
            if tokens[cursor].value == opener:
                depth += 1
            elif tokens[cursor].value == pairs[opener]:
                depth -= 1
                if depth == 0:
                    end = cursor
                    break
        if any(row.value == old_name for row in tokens[index + 2:end]):
            blocked.append({"kind": "rust_macro_module_ambiguity", "line_token": old_name})
    return blocked


def _module_path_for_file(path: Path, source_root: Path) -> list[str] | None:
    if not _inside(path, source_root) or path.suffix != ".rs":
        return None
    relative = path.relative_to(source_root)
    if relative.as_posix() in {"lib.rs", "main.rs"}:
        return []
    parts = list(relative.parts)
    if parts[-1] == "mod.rs":
        return parts[:-1]
    parts[-1] = Path(parts[-1]).stem
    return parts


def _path_runs(tokens: list[Token]) -> list[list[int]]:
    runs: list[list[int]] = []
    index = 0
    while index < len(tokens):
        if tokens[index].kind not in {"ident", "raw-ident"}:
            index += 1
            continue
        run = [index]
        cursor = index
        while (
            cursor + 2 < len(tokens)
            and tokens[cursor + 1].value == "::"
            and tokens[cursor + 2].kind in {"ident", "raw-ident"}
        ):
            run.append(cursor + 2)
            cursor += 2
        if len(run) > 1:
            runs.append(run)
            index = cursor + 1
        else:
            index += 1
    return runs


def _matching_segment(
    identifiers: list[str],
    *,
    current_module: list[str] | None,
    same_library: bool,
    old_module: list[str],
    crate_aliases: set[str],
) -> int | None:
    candidates: list[tuple[list[str], int]] = []
    if identifiers[0] == "crate" and same_library:
        candidates.append((identifiers[1:], 1))
    if identifiers[0] in crate_aliases:
        candidates.append((identifiers[1:], 1))
    if current_module is not None:
        if identifiers[0] == "self":
            candidates.append((current_module + identifiers[1:], 1 + len(current_module)))
        elif identifiers[0] == "super":
            count = 0
            while count < len(identifiers) and identifiers[count] == "super":
                count += 1
            if count <= len(current_module):
                base = current_module[:len(current_module) - count]
                candidates.append((base + identifiers[count:], count + len(base)))
        else:
            candidates.append((current_module + identifiers, len(current_module)))
    for canonical, offset in candidates:
        if canonical[:len(old_module)] != old_module:
            continue
        old_index = len(old_module) - 1
        source_index = old_index - offset
        if source_index >= 0:
            if identifiers[0] in {"crate", "self", "super"} or identifiers[0] in crate_aliases:
                source_index += 1 if identifiers[0] not in {"super"} else 0
        # Directly locate the old terminal spelling; the canonical math above
        # licenses which occurrence may be changed.
        matches = [index for index, value in enumerate(identifiers) if value == old_module[-1]]
        if matches:
            return matches[-1]
    return None


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _eligible_rust_files(root: Path, report_dir: Path) -> list[Path]:
    rows = []
    for path in sorted(root.rglob("*.rs")):
        if _excluded_from_snapshot(path, root, report_dir):
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_file() and not path.is_symlink():
            rows.append(path)
    return rows


def _package_context(metadata: dict, root: Path, current: Path) -> tuple[dict | None, Path | None]:
    matches = []
    for package in metadata.get("packages", []):
        manifest = Path(package.get("manifest_path", "")).resolve(strict=False)
        package_root = manifest.parent
        if _inside(current, package_root):
            matches.append((package, package_root))
    if len(matches) != 1:
        return None, None
    return matches[0]


def _lib_target(package: dict) -> dict | None:
    rows = [
        target for target in package.get("targets", [])
        if any(kind in {"lib", "rlib"} for kind in target.get("kind", []))
    ]
    return rows[0] if len(rows) == 1 else None


def _dependency_aliases(metadata: dict, moved_package: dict) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    moved_name = moved_package["name"]
    moved_crate = moved_name.replace("-", "_")
    for package in metadata.get("packages", []):
        aliases = {moved_crate}
        for dependency in package.get("dependencies", []):
            if dependency.get("name") == moved_name:
                aliases.add((dependency.get("rename") or moved_name).replace("-", "_"))
        result[package["id"]] = aliases
    return result


def _build_module_shape(
    root: Path,
    source: str,
    destination: str,
    mode: str,
    metadata: dict,
    run_mode: str,
) -> tuple[dict | None, list[dict]]:
    blocked: list[dict] = []
    source_path = root / source
    destination_path = root / destination
    current = destination_path if run_mode == "check" else source_path
    absent = source_path if run_mode == "check" else destination_path
    if current.is_symlink() or _has_symlink(current, root):
        blocked.append({"kind": "rust_symlink_boundary", "path": current.relative_to(root).as_posix()})
    if not current.exists():
        blocked.append({"kind": "rust_module_source_missing", "path": current.relative_to(root).as_posix()})
    if absent.exists() or absent.is_symlink():
        blocked.append({"kind": "rust_move_state_ambiguous", "path": absent.relative_to(root).as_posix()})
    if any(part in EXCLUDED_PARTS for part in (*Path(source).parts, *Path(destination).parts)):
        blocked.append({"kind": "rust_excluded_move_path"})
    if Path(source).parent != Path(destination).parent:
        blocked.append({"kind": "rust_sibling_module_move_required"})
    old_name = Path(source).name if mode == "directory" else Path(source).stem
    new_name = Path(destination).name if mode == "directory" else Path(destination).stem
    if not RUST_IDENTIFIER.fullmatch(old_name) or not RUST_IDENTIFIER.fullmatch(new_name):
        blocked.append({"kind": "rust_identifier_required"})
    if mode == "file":
        if Path(source).suffix != ".rs" or Path(destination).suffix != ".rs" or old_name == "mod":
            blocked.append({"kind": "rust_conventional_module_file_required"})
        move_shape = "module-file"
    else:
        move_shape = "leaf-directory-module"
        if current.is_dir():
            members = sorted(path.relative_to(current).as_posix() for path in current.rglob("*"))
            if members != ["mod.rs"] or not (current / "mod.rs").is_file():
                blocked.append({"kind": "rust_leaf_mod_rs_directory_required", "members": members})
        elif current.exists():
            blocked.append({"kind": "rust_leaf_mod_rs_directory_required", "members": []})
    package, _package_root = _package_context(metadata, root, current)
    if package is None:
        blocked.append({"kind": "rust_workspace_package_ambiguity"})
        return None, blocked
    lib = _lib_target(package)
    if lib is None:
        blocked.append({"kind": "rust_library_target_ambiguity"})
        return None, blocked
    crate_root = Path(lib["src_path"]).resolve(strict=False)
    source_root = crate_root.parent
    if not _inside(current, source_root) or not _inside(destination_path, source_root):
        blocked.append({"kind": "rust_library_source_root_required"})
        return None, blocked
    relative = current.relative_to(source_root)
    if mode == "file":
        current_module = _module_path_for_file(current, source_root)
    else:
        current_module = list(relative.parts)
    if current_module is None or not current_module:
        blocked.append({"kind": "rust_nested_module_required"})
        return None, blocked
    parent_module = current_module[:-1]
    parent_candidates = [crate_root] if not parent_module else [
        source_root.joinpath(*parent_module).with_suffix(".rs"),
        source_root.joinpath(*parent_module, "mod.rs"),
    ]
    parents = [path for path in parent_candidates if path.is_file() and not path.is_symlink()]
    if len(parents) != 1:
        blocked.append({"kind": "rust_parent_module_ambiguity", "candidates": [str(path) for path in parent_candidates]})
        return None, blocked
    old_module = parent_module + [old_name]
    new_module = parent_module + [new_name]
    return {
        "package": package,
        "lib_target": lib,
        "crate_root": crate_root,
        "source_root": source_root,
        "parent_file": parents[0],
        "parent_module": parent_module,
        "old_module": old_module,
        "new_module": new_module,
        "old_name": old_name,
        "new_name": new_name,
        "move_shape": move_shape,
    }, blocked


def _scan_and_plan_replacements(
    root: Path,
    report_dir: Path,
    metadata: dict,
    shape: dict,
    source: str,
    destination: str,
    run_mode: str,
) -> tuple[list[Replacement], list[dict], bool, list[dict]]:
    replacements: list[Replacement] = []
    blocked: list[dict] = []
    old_remaining: list[dict] = []
    old_name = shape["old_name"]
    new_name = shape["new_name"]
    old_module = shape["old_module"]
    moved_package = shape["package"]
    aliases = _dependency_aliases(metadata, moved_package)
    crate_ident = moved_package["name"].replace("-", "_")
    parent_file = shape["parent_file"]
    public_reexport = False
    for path in _eligible_rust_files(root, report_dir):
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            blocked.append({"kind": "rust_source_not_utf8", "path": relative})
            continue
        tokens, excluded = _scan_tokens(text)
        for _start, _end, content in excluded:
            markers = (
                "::".join([crate_ident, *old_module]),
                "::".join(["crate", *old_module]),
                f"{old_name}::",
                source,
            )
            if any(marker in content for marker in markers):
                blocked.append({"kind": "rust_unproved_textual_reference", "path": relative})
                break
        if any(token.value == "include" and index + 1 < len(tokens) and tokens[index + 1].value == "!" for index, token in enumerate(tokens)):
            blocked.append({"kind": "rust_include_macro_ambiguity", "path": relative})
        if re.search(r"#\s*\[\s*path\b", text):
            blocked.append({"kind": "rust_path_attribute_ambiguity", "path": relative})
        blocked.extend({**row, "path": relative} for row in _balanced_macro_ranges(tokens, old_name))

        package, _ = _package_context(metadata, root, path)
        package_id = package["id"] if package else ""
        same_library = _inside(path, shape["source_root"])
        current_module = _module_path_for_file(path, shape["source_root"]) if same_library else None
        token_edits: set[int] = set()
        declaration_matches = []
        for index in range(len(tokens) - 2):
            if (
                tokens[index].value == "mod"
                and tokens[index + 1].value == (new_name if run_mode == "check" else old_name)
                and tokens[index + 2].value == ";"
            ):
                declaration_matches.append(index + 1)
        if path == parent_file:
            expected_name = new_name if run_mode == "check" else old_name
            cfg_pattern = re.compile(
                rf"#\s*\[\s*(?:cfg|cfg_attr)\b[^\]]*\]\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+{re.escape(expected_name)}\b",
                re.S,
            )
            if cfg_pattern.search(text):
                blocked.append({"kind": "rust_cfg_module_ambiguity", "path": relative})
            if len(declaration_matches) != 1:
                blocked.append({"kind": "rust_module_declaration_ambiguity", "path": relative, "count": len(declaration_matches)})
            elif run_mode != "check":
                token = tokens[declaration_matches[0]]
                replacements.append(Replacement(
                    relative,
                    _map_after_path(relative, source, destination),
                    token.start,
                    token.end,
                    old_name,
                    new_name,
                    "module-declaration",
                    _line(text, token.start),
                ))
                token_edits.add(declaration_matches[0])

        for run in _path_runs(tokens):
            identifiers = [tokens[index].value for index in run]
            segment = _matching_segment(
                identifiers,
                current_module=current_module,
                same_library=same_library,
                old_module=old_module,
                crate_aliases=aliases.get(package_id, {crate_ident}),
            )
            old_positions = [position for position, value in enumerate(identifiers) if value == old_name]
            if run_mode == "check":
                if old_positions and segment is not None:
                    old_remaining.append({"kind": "rust_old_module_path", "path": relative, "line": _line(text, tokens[run[segment]].start)})
                continue
            if segment is not None and identifiers[segment] == old_name:
                token_index = run[segment]
                token = tokens[token_index]
                replacements.append(Replacement(
                    relative,
                    _map_after_path(relative, source, destination),
                    token.start,
                    token.end,
                    old_name,
                    new_name,
                    "resolved-module-path",
                    _line(text, token.start),
                ))
                token_edits.add(token_index)
                line_text = text.splitlines()[_line(text, token.start) - 1]
                if path == parent_file and re.match(r"\s*pub\s+use\b", line_text):
                    public_reexport = True
            elif old_positions:
                for position in old_positions:
                    token_index = run[position]
                    if token_index not in token_edits:
                        blocked.append({
                            "kind": "rust_unresolved_module_path",
                            "path": relative,
                            "line": _line(text, tokens[token_index].start),
                        })

        # Bounded support for `use service;` in the parent module.
        for index in range(len(tokens) - 2):
            if tokens[index].value == "use" and tokens[index + 1].value == old_name and tokens[index + 2].value == ";":
                if run_mode == "check":
                    old_remaining.append({"kind": "rust_old_module_use", "path": relative, "line": _line(text, tokens[index + 1].start)})
                elif path == parent_file:
                    token = tokens[index + 1]
                    replacements.append(Replacement(
                        relative, _map_after_path(relative, source, destination),
                        token.start, token.end, old_name, new_name,
                        "resolved-module-use", _line(text, token.start),
                    ))
                    token_edits.add(index + 1)
                else:
                    blocked.append({"kind": "rust_unresolved_use_shape", "path": relative, "line": _line(text, tokens[index + 1].start)})
    build_script = Path(moved_package["manifest_path"]).parent / "build.rs"
    if build_script.is_file():
        build_text = build_script.read_text(encoding="utf-8", errors="replace")
        if any(token in build_text for token in BUILD_OUTPUT_TOKENS) or old_name in build_text:
            blocked.append({"kind": "rust_build_output_ambiguity", "path": build_script.relative_to(root).as_posix()})
    unique = {
        (row.file_before, row.start, row.end, row.kind): row
        for row in replacements
    }
    replacements = sorted(unique.values(), key=lambda row: (row.file_before, row.start, row.kind))
    if run_mode != "check" and not public_reexport:
        blocked.append({"kind": "rust_public_reexport_not_proved", "path": parent_file.relative_to(root).as_posix()})
    return replacements, blocked, public_reexport, old_remaining


def _patched_contents(
    root: Path, replacements: list[Replacement]
) -> dict[str, bytes]:
    grouped: dict[str, list[Replacement]] = {}
    for replacement in replacements:
        grouped.setdefault(replacement.file_before, []).append(replacement)
    result: dict[str, bytes] = {}
    for relative, rows in grouped.items():
        text = (root / relative).read_text(encoding="utf-8")
        for row in sorted(rows, key=lambda item: item.start, reverse=True):
            if text[row.start:row.end] != row.old:
                raise UserError(f"replacement span drifted for {relative}:{row.line}")
            text = text[:row.start] + row.new + text[row.end:]
        result[relative] = text.encode("utf-8")
    return result


def _review_diff(
    root: Path,
    replacements: list[Replacement],
    patched: dict[str, bytes],
    source: str,
    destination: str,
) -> str:
    lines = [f"rename {source} -> {destination}"]
    for relative in sorted(patched):
        before = (root / relative).read_text(encoding="utf-8")
        after = patched[relative].decode("utf-8")
        after_path = next(
            (row.file_after for row in replacements if row.file_before == relative),
            relative,
        )
        lines.extend(difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile=f"a/{relative}", tofile=f"b/{after_path}", lineterm="",
        ))
    return "\n".join(lines) + "\n"


def _metadata_boundaries(metadata: dict) -> list[dict]:
    blocked: list[dict] = []
    workspace = set(metadata.get("workspace_members", []))
    packages = metadata.get("packages", [])
    if not packages or {row.get("id") for row in packages} != workspace:
        blocked.append({"kind": "rust_workspace_target_ambiguity"})
    for package in packages:
        for target in package.get("targets", []):
            if "proc-macro" in target.get("kind", []):
                blocked.append({"kind": "rust_procedural_macro_ambiguity", "package": package.get("name")})
        for dependency in package.get("dependencies", []):
            path = dependency.get("path")
            if dependency.get("source") is not None or path is None:
                blocked.append({"kind": "rust_non_path_dependency_ambiguity", "package": package.get("name"), "dependency": dependency.get("name")})
    return blocked


def _base_payload(
    root: Path,
    plan_path: Path,
    mode: str,
    rust: dict,
) -> dict:
    return {
        "schema_version": 1,
        "project_root": root.as_posix(),
        "plan_path": plan_path.as_posix(),
        "mode": mode,
        "summary": {
            "moves": 1,
            "blocked": len(rust.get("blocked", [])),
            "rust_status": rust["status"],
        },
        "code_imports": {
            "mode": "update-rust",
            "risk": "Only conventional module declarations and statically resolved Rust path tokens are rewritten.",
        },
        "rust": rust,
    }


def _render(payload: dict) -> str:
    rust = payload["rust"]
    lines = [
        "# move-path report",
        "",
        f"**Mode:** `{payload['mode']}`",
        "",
        "## Checked Rust module move",
        "",
        f"- Status: `{rust['status']}`",
        f"- Failure kind: `{rust.get('failure_kind', 'none')}`",
        f"- Source: `{rust.get('source')}`",
        f"- Destination: `{rust.get('destination')}`",
        f"- Module: `{rust.get('module_before')}` -> `{rust.get('module_after')}`",
        f"- Rolled back: `{str(rust.get('rolled_back', False)).lower()}`",
        "",
        "## Exact changes",
        "",
    ]
    changes = rust.get("exact_changes", [])
    lines.extend(
        f"- `{row['file_before']}:{row['line']}` {row['kind']}: `{row['old']}` -> `{row['new']}`"
        for row in changes
    )
    if not changes:
        lines.append("- None")
    lines.extend(["", "## Review diff", "", "```diff", rust.get("review_diff", "").rstrip(), "```", "", "## Blocked", ""])
    lines.extend(
        f"- `{row.get('kind')}`: `{row}`" for row in rust.get("blocked", [])
    )
    if not rust.get("blocked"):
        lines.append("- None")
    lines.extend([
        "",
        "## Explicit limits",
        "",
        "- Macro-generated modules and references are not rewritten.",
        "- `include!`, procedural macros, build output, `#[path]`, and relevant cfg-dependent modules are refused.",
        "- Trait dispatch, generated code, target variants, and runtime identities are not inferred.",
        "",
    ])
    return "\n".join(lines)


def _write_report(report_dir: Path, payload: dict) -> None:
    _atomic_text(report_dir / "report.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic_text(report_dir / "report.md", _render(payload))


def _terminal_rust(
    *,
    status: str,
    failure_kind: str,
    message: str,
    source: str | None = None,
    destination: str | None = None,
    blocked: list[dict] | None = None,
    **facts: object,
) -> dict:
    return {
        "status": status,
        "failure_kind": failure_kind,
        "message": message,
        "source": source,
        "destination": destination,
        "blocked": blocked or [],
        "exact_changes": [],
        "review_diff": "",
        "rolled_back": False,
        **facts,
    }


def _apply_transaction(
    root: Path,
    source: str,
    destination: str,
    patched: dict[str, bytes],
) -> None:
    destination_path = root / destination
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(root / source), str(destination_path))
    for before, contents in patched.items():
        after = _map_after_path(before, source, destination)
        path = root / after
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)


def _execute(
    *,
    root: Path,
    plan_path: Path,
    report_dir: Path,
    plan: dict,
    mode: str,
    expected_source_sha256: str | None,
) -> tuple[dict, int]:
    if plan.get("_error"):
        rust = _terminal_rust(
            status="failed",
            failure_kind=plan["_error"],
            message=plan["_message"],
        )
        return _base_payload(root, plan_path, mode, rust), 2
    moves = plan["_moves"]
    if len(moves) != 1:
        rust = _terminal_rust(
            status="partial",
            failure_kind="rust_move_count_ambiguous",
            message="Rust mutation remains pending for multiple moves.",
            blocked=[{"kind": "rust_move_count_ambiguous", "count": len(moves)}],
        )
        return _base_payload(root, plan_path, mode, rust), 0 if mode == "dry-run" else 2
    move = moves[0]
    source = move["from"]
    destination = move["to"]
    if plan.get("rewrite", {}).get("code_imports") != "update-rust":
        rust = _terminal_rust(
            status="partial",
            failure_kind="rust_mode_not_selected",
            message="rewrite.code_imports must be update-rust.",
            source=source,
            destination=destination,
            blocked=[{"kind": "rust_mode_not_selected"}],
        )
        return _base_payload(root, plan_path, mode, rust), 0 if mode == "dry-run" else 2

    before, links = _snapshot(root, report_dir)
    before_fingerprint = _fingerprint(before, links)
    source_manifest = {
        "before_fingerprint": before_fingerprint,
        "actual_fingerprint": before_fingerprint,
        "expected_fingerprint": None,
        "files_before": sorted(before),
    }
    if expected_source_sha256 and expected_source_sha256 != before_fingerprint:
        rust = _terminal_rust(
            status="failed",
            failure_kind="stale_source_snapshot",
            message="Current project fingerprint does not match --expected-source-sha256.",
            source=source,
            destination=destination,
            source_manifest=source_manifest,
        )
        return _base_payload(root, plan_path, mode, rust), 2
    if links:
        rust = _terminal_rust(
            status="partial",
            failure_kind="rust_symlink_boundary",
            message="Rust mutation remains pending for projects containing symlinks.",
            source=source,
            destination=destination,
            blocked=[{"kind": "rust_symlink_boundary", "paths": sorted(links)}],
            source_manifest=source_manifest,
        )
        return _base_payload(root, plan_path, mode, rust), 0 if mode == "dry-run" else 2

    tools, tool_blocks = _toolchain(root, plan.get("rust"))
    if tool_blocks:
        rust = _terminal_rust(
            status="partial",
            failure_kind=tool_blocks[0]["kind"],
            message="Required native tooling is missing, old, or unusable; implementation remains pending.",
            source=source,
            destination=destination,
            blocked=tool_blocks,
            tools=tools,
            source_manifest=source_manifest,
        )
        return _base_payload(root, plan_path, mode, rust), 0 if mode == "dry-run" else 2

    state = report_dir / ".rust-state"
    shutil.rmtree(state, ignore_errors=True)
    pre_state = state / "preflight"
    env = _cargo_environment(tools, pre_state)
    metadata, metadata_run = _metadata(tools, root, env)
    if metadata is None:
        rust = _terminal_rust(
            status="failed",
            failure_kind="cargo_metadata_failed",
            message="Locked offline Cargo metadata failed.",
            source=source,
            destination=destination,
            tools=tools,
            native_preflight={"cargo_metadata": metadata_run},
            source_manifest=source_manifest,
        )
        return _base_payload(root, plan_path, mode, rust), 2

    boundary_blocks = _metadata_boundaries(metadata)
    shape, shape_blocks = _build_module_shape(
        root, source, destination, move["mode"], metadata, mode
    )
    blocked = [*boundary_blocks, *shape_blocks]
    if shape is None:
        status = "partial"
        rust = _terminal_rust(
            status=status,
            failure_kind=blocked[0]["kind"] if blocked else "rust_module_shape_pending",
            message="The selected Rust move is outside the bounded conventional module shape.",
            source=source,
            destination=destination,
            blocked=blocked,
            tools=tools,
            native_preflight={"cargo_metadata": metadata_run},
            source_manifest=source_manifest,
        )
        return _base_payload(root, plan_path, mode, rust), 0 if mode == "dry-run" else 2

    replacements, scan_blocks, public_reexport, old_remaining = _scan_and_plan_replacements(
        root, report_dir, metadata, shape, source, destination, mode
    )
    blocked.extend(scan_blocks)
    if mode == "check" and old_remaining:
        blocked.extend(old_remaining)
    if blocked:
        rust = _terminal_rust(
            status="partial",
            failure_kind=blocked[0]["kind"],
            message="Unproved Rust module/reference shapes block mutation.",
            source=source,
            destination=destination,
            blocked=blocked,
            tools=tools,
            move_shape=shape["move_shape"],
            module_before="::".join([shape["package"]["name"].replace("-", "_"), *shape["old_module"]]),
            module_after="::".join([shape["package"]["name"].replace("-", "_"), *shape["new_module"]]),
            public_reexport_preserved=public_reexport,
            old_identity_remaining=old_remaining,
            native_preflight={"cargo_metadata": metadata_run},
            source_manifest=source_manifest,
        )
        return _base_payload(root, plan_path, mode, rust), 0 if mode == "dry-run" else 2

    rust_section = plan["rust"]
    native_preflight, native_failure = _native_suite(
        tools,
        root,
        pre_state,
        rust_section.get("smoke_package"),
        rust_section.get("smoke_expected_stdout"),
    )
    if native_failure:
        after_native, after_links = _snapshot(root, report_dir)
        if (after_native, after_links) != (before, links):
            _restore(root, report_dir, before, links)
        rust = _terminal_rust(
            status="failed",
            failure_kind=native_failure,
            message="Rust native preflight failed; no move was applied.",
            source=source,
            destination=destination,
            tools=tools,
            move_shape=shape["move_shape"],
            native_preflight=native_preflight,
            source_manifest=source_manifest,
            rolled_back=(after_native, after_links) != (before, links),
        )
        return _base_payload(root, plan_path, mode, rust), 2
    after_preflight, after_preflight_links = _snapshot(root, report_dir)
    if (after_preflight, after_preflight_links) != (before, links):
        _restore(root, report_dir, before, links)
        rust = _terminal_rust(
            status="failed",
            failure_kind="source_mutated_preflight",
            message="Native preflight changed the audited project and was rolled back.",
            source=source,
            destination=destination,
            tools=tools,
            native_preflight=native_preflight,
            source_manifest={
                **source_manifest,
                "actual_fingerprint": _fingerprint(after_preflight, after_preflight_links),
            },
            rolled_back=True,
        )
        return _base_payload(root, plan_path, mode, rust), 2

    module_before = "::".join([shape["package"]["name"].replace("-", "_"), *shape["old_module"]])
    module_after = "::".join([shape["package"]["name"].replace("-", "_"), *shape["new_module"]])
    if mode == "check":
        post_state = state / "check"
        native_postflight, post_failure = _native_suite(
            tools, root, post_state,
            rust_section.get("smoke_package"),
            rust_section.get("smoke_expected_stdout"),
        )
        current, current_links = _snapshot(root, report_dir)
        exact = _snapshot_diff(before, links, current, current_links)
        native_postflight["exact_diff"] = exact
        failure = post_failure or (None if exact["passed"] else "exact_diff_failed")
        rust = {
            "status": "failed" if failure else "complete",
            "failure_kind": failure or "none",
            "message": "Checked moved Rust module and native snapshot." if not failure else "Post-move Rust verification failed.",
            "source": source,
            "destination": destination,
            "move_shape": shape["move_shape"],
            "module_before": module_before,
            "module_after": module_after,
            "blocked": [],
            "exact_changes": [],
            "review_diff": "",
            "public_reexport_preserved": True,
            "old_identity_remaining": old_remaining,
            "tools": tools,
            "native_preflight": native_preflight,
            "native_postflight": native_postflight,
            "source_manifest": {
                **source_manifest,
                "expected_fingerprint": before_fingerprint,
                "actual_fingerprint": _fingerprint(current, current_links),
            },
            "rolled_back": False,
        }
        return _base_payload(root, plan_path, mode, rust), 2 if failure else 0

    patched = _patched_contents(root, replacements)
    expected = _expected_snapshot(before, source, destination, patched)
    expected_fingerprint = _fingerprint(expected, links)
    review = _review_diff(root, replacements, patched, source, destination)
    changes = [
        {
            "file_before": row.file_before,
            "file_after": row.file_after,
            "start": row.start,
            "end": row.end,
            "line": row.line,
            "old": row.old,
            "new": row.new,
            "kind": row.kind,
        }
        for row in replacements
    ]
    rust = {
        "status": "complete",
        "failure_kind": "none",
        "message": "Complete for one conventional module move and exact static path edits.",
        "source": source,
        "destination": destination,
        "move_shape": shape["move_shape"],
        "module_before": module_before,
        "module_after": module_after,
        "blocked": [],
        "exact_changes": changes,
        "review_diff": review,
        "public_reexport_preserved": public_reexport,
        "old_identity_remaining": [],
        "tools": tools,
        "native_preflight": native_preflight,
        "native_postflight": {},
        "source_manifest": {
            **source_manifest,
            "expected_fingerprint": expected_fingerprint,
        },
        "rolled_back": False,
    }
    if mode == "dry-run":
        return _base_payload(root, plan_path, mode, rust), 0

    _apply_transaction(root, source, destination, patched)
    post_state = state / "postflight"
    native_postflight, post_failure = _native_suite(
        tools, root, post_state,
        rust_section.get("smoke_package"),
        rust_section.get("smoke_expected_stdout"),
    )
    actual, actual_links = _snapshot(root, report_dir)
    exact = _snapshot_diff(expected, links, actual, actual_links)
    native_postflight["exact_diff"] = exact
    failure = post_failure or (None if exact["passed"] else "exact_diff_failed")
    rust["native_postflight"] = native_postflight
    rust["source_manifest"]["actual_fingerprint"] = _fingerprint(actual, actual_links)
    if failure:
        _restore(root, report_dir, before, links)
        rust["status"] = "failed"
        rust["failure_kind"] = failure
        rust["message"] = "Rust postflight failed; the complete project snapshot was rolled back."
        rust["blocked"] = [{"kind": failure}]
        rust["rolled_back"] = True
        return _base_payload(root, plan_path, mode, rust), 2
    return _base_payload(root, plan_path, mode, rust), 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report-dir", required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--check", action="store_true")
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.expected_source_sha256 and not re.fullmatch(r"[0-9a-f]{64}", args.expected_source_sha256):
            raise UserError("--expected-source-sha256 must be a lowercase SHA-256 digest")
        root, plan_path, report_dir = _validate_cli(args)
        plan = _load_plan(root, plan_path)
        report_json = report_dir / "report.json"
        report_markdown = report_dir / "report.md"
        report_json.unlink(missing_ok=True)
        report_markdown.unlink(missing_ok=True)
        mode = "dry-run" if args.dry_run else "apply" if args.apply else "check"
        payload, exit_code = _execute(
            root=root,
            plan_path=plan_path,
            report_dir=report_dir,
            plan=plan,
            mode=mode,
            expected_source_sha256=args.expected_source_sha256,
        )
        _write_report(report_dir, payload)
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        return exit_code
    except UserError as exc:
        print(f"rust_module_move.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
