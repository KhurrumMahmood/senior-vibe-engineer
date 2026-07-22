"""Bounded transaction for one dependency-free SwiftPM target-directory move."""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


SWIFT_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
IMPORT_RE = re.compile(r"(?m)^\s*(?:@testable\s+)?import\s+([A-Za-z_][A-Za-z0-9_]*)\s*$")
GENERATED_RE = re.compile(r"(?im)^\s*//\s*code generated .*do not edit")
FORBIDDEN_MANIFEST_TOKENS = (
    ".binaryTarget(", ".macro(", ".plugin(", ".systemLibrary(",
    "resources:", "plugins:", "publicHeadersPath:",
)
EXCLUDED_PARTS = frozenset({".build", "Tests", "build", "generated", "vendor"})


def _run(argv: list[str], cwd: Path, *, timeout: int = 120) -> dict:
    try:
        result = subprocess.run(
            argv, cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout
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
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _fingerprint(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, contents in sorted(files.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(contents).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _excluded(path: Path, root: Path, report_dir: Path) -> bool:
    relative = path.relative_to(root)
    if ".git" in relative.parts:
        return True
    try:
        path.resolve().relative_to(report_dir.resolve())
        return True
    except ValueError:
        return False


def _snapshot(root: Path, report_dir: Path) -> tuple[dict[str, bytes], list[str]]:
    files: dict[str, bytes] = {}
    symlinks: list[str] = []
    for path in sorted(root.rglob("*")):
        if _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            symlinks.append(relative)
        elif path.is_file():
            files[relative] = path.read_bytes()
    return files, symlinks


def _expected_snapshot(
    before: dict[str, bytes], source: str, destination: str, manifest: bytes
) -> dict[str, bytes]:
    expected: dict[str, bytes] = {}
    for relative, contents in before.items():
        if relative == source or relative.startswith(source + "/"):
            relative = destination + relative[len(source):]
        expected[relative] = contents
    expected["Package.swift"] = manifest
    return expected


def _diff(expected: dict[str, bytes], actual: dict[str, bytes]) -> dict:
    changed = sorted(
        path for path in expected.keys() & actual.keys() if expected[path] != actual[path]
    )
    missing = sorted(expected.keys() - actual.keys())
    unexpected = sorted(actual.keys() - expected.keys())
    return {
        "passed": not changed and not missing and not unexpected,
        "expected_fingerprint": _fingerprint(expected),
        "actual_fingerprint": _fingerprint(actual),
        "changed": changed,
        "missing": missing,
        "unexpected": unexpected,
    }


def _restore(root: Path, report_dir: Path, before: dict[str, bytes]) -> None:
    current, links = _snapshot(root, report_dir)
    for relative in sorted(links, reverse=True):
        (root / relative).unlink()
    for relative in sorted(current, reverse=True):
        path = root / relative
        if path.exists() or path.is_symlink():
            path.unlink()
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and not path.is_symlink() and not _excluded(path, root, report_dir):
            try:
                path.rmdir()
            except OSError:
                pass
    for relative, contents in before.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)


def _swift_argv(swift: str, root: Path, state: Path, subcommand: str) -> list[str]:
    return [
        swift,
        "package" if subcommand == "dump-package" else "build",
        "--package-path",
        str(root),
        "--cache-path",
        str(state / "cache"),
        "--config-path",
        str(state / "config"),
        "--security-path",
        str(state / "security"),
        "--scratch-path",
        str(state / "build"),
        "--disable-dependency-cache",
        "--manifest-cache",
        "local",
        "--disable-netrc",
        "--disable-keychain",
        "--disable-prefetching",
        "--disable-automatic-resolution",
        *(["--enable-index-store"] if subcommand == "build" else []),
        *([subcommand] if subcommand == "dump-package" else []),
    ]


def _dump_package(swift: str, root: Path, state: Path) -> tuple[dict | None, dict]:
    result = _run(_swift_argv(swift, root, state, "dump-package"), root)
    if not result["passed"]:
        return None, result
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        result["passed"] = False
        result["stderr"] = "swift package dump-package emitted invalid JSON"
        return None, result
    return payload, result


def _manifest_rewrite(text: str, target: str, destination: str) -> tuple[str | None, dict | None]:
    simple = re.compile(
        rf"\.target\(\s*name\s*:\s*\"{re.escape(target)}\"\s*\)"
    )
    explicit = re.compile(
        rf"\.target\(\s*name\s*:\s*\"{re.escape(target)}\"\s*,\s*path\s*:\s*\"Sources/{re.escape(target)}\"\s*\)"
    )
    matches = list(simple.finditer(text)) + list(explicit.finditer(text))
    if len(matches) != 1:
        return None, {"kind": "swift_manifest_dynamic_or_unsupported_target", "target": target}
    match = matches[0]
    old = match.group(0)
    new = f'.target(name: "{target}", path: "{destination}")'
    return text[:match.start()] + new + text[match.end():], {
        "file_before": "Package.swift",
        "file_after": "Package.swift",
        "kind": "swiftpm_target_path",
        "old": old,
        "new": new,
        "target_before": f"Sources/{target}",
        "target_after": destination,
    }


def _manifest_after_is_exact(text: str, target: str, destination: str) -> bool:
    pattern = re.compile(
        rf"\.target\(\s*name\s*:\s*\"{re.escape(target)}\"\s*,\s*path\s*:\s*\"{re.escape(destination)}\"\s*\)"
    )
    return len(pattern.findall(text)) == 1


def _review_diff(before: str, after: str, source: str, destination: str, files: list[str]) -> str:
    manifest = list(difflib.unified_diff(
        before.splitlines(), after.splitlines(), fromfile="a/Package.swift",
        tofile="b/Package.swift", lineterm="",
    ))
    renames = [f"rename {path} -> {destination + path[len(source):]}" for path in files]
    return "\n".join([*manifest, *renames]) + "\n"


def _write_report(report_dir: Path, payload: dict) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    swift = payload["swift"]
    lines = [
        "# move-path report", "", f"**Mode:** {payload['mode']}", "",
        "## Checked SwiftPM target-directory move", "",
        f"- Status: `{swift['status']}`",
        f"- Target identity retained: `{swift.get('target')}`",
        f"- Source path: `{swift.get('source')}` -> `{swift.get('destination')}`",
        f"- Rolled back: `{str(swift.get('rolled_back', False)).lower()}`", "",
        "## Review diff", "", "```diff", swift.get("review_diff", "").rstrip(), "```", "",
        "## Blocked", "",
    ]
    lines.extend(
        [f"- `{item.get('kind')}`: `{item}`" for item in swift.get("blocked", [])]
        or ["- None"]
    )
    lines.append("")
    (report_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def _base_payload(root: Path, plan_path: Path, mode: str, move, swift: dict) -> dict:
    blocked = swift.get("blocked", [])
    return {
        "project_root": root.as_posix(),
        "plan_path": plan_path.as_posix(),
        "mode": mode,
        "summary": {"moves": 1, "blocked": len(blocked), "swift_status": swift["status"]},
        "moves": [{"move_id": move.move_id, "src": move.src, "dst": move.dst, "mode": move.mode}],
        "blocked": blocked,
        "code_imports": {
            "mode": "update-swift",
            "risk": "The bounded move retains module identity and edits only one proven SwiftPM target path.",
            "ignored": [],
        },
        "swift": swift,
    }


def run_swift_plan(*, root: Path, plan_path: Path, plan: dict, moves: list, mode: str, report_dir: Path, stage: bool = False) -> dict:
    """Plan or transact the frozen one-target SwiftPM directory move."""
    blocked: list[dict] = []
    swift_section = plan.get("swift")
    move = moves[0] if len(moves) == 1 else None
    if not isinstance(swift_section, dict):
        blocked.append({"kind": "swift_config_required"})
    if move is None:
        blocked.append({"kind": "swift_move_count_unsupported"})
    elif move.mode != "directory":
        blocked.append({"kind": "swift_target_move_must_be_directory"})
    if blocked:
        swift = {"status": "unsupported", "blocked": blocked, "rolled_back": False}
        payload = _base_payload(root, plan_path, mode, move or moves[0], swift)
        _write_report(report_dir, payload)
        return payload

    assert isinstance(swift_section, dict)
    source, destination = move.src, move.dst
    source_parts, destination_parts = Path(source).parts, Path(destination).parts
    target = source_parts[1] if len(source_parts) == 2 else ""
    if (
        len(source_parts) != 2 or len(destination_parts) != 2
        or source_parts[0] != "Sources" or destination_parts[0] != "Sources"
        or not SWIFT_IDENTIFIER.fullmatch(target)
        or not SWIFT_IDENTIFIER.fullmatch(destination_parts[1])
    ):
        blocked.append({"kind": "swift_sources_root_target_directory_required"})
    current_source = destination if mode == "check" else source
    if not (root / current_source).is_dir():
        blocked.append({"kind": "swift_target_directory_missing", "path": current_source})
    if (root / (source if mode == "check" else destination)).exists():
        blocked.append({"kind": "swift_move_state_ambiguous"})
    if any(part in EXCLUDED_PARTS for part in (*source_parts, *destination_parts)):
        blocked.append({"kind": "swift_excluded_path_unsupported"})
    if list(root.glob("*.xcodeproj")) or list(root.glob("*.xcworkspace")):
        blocked.append({"kind": "swift_xcode_project_unsupported"})
    if (root / "Package.resolved").exists():
        blocked.append({"kind": "swift_dependency_resolution_unsupported"})
    before, symlinks = _snapshot(root, report_dir)
    if symlinks:
        blocked.append({"kind": "swift_symlink_boundary", "paths": symlinks})
    manifest_path = root / "Package.swift"
    if not manifest_path.is_file():
        blocked.append({"kind": "swiftpm_manifest_required"})
        manifest_text = ""
    else:
        try:
            manifest_text = manifest_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            manifest_text = ""
            blocked.append({"kind": "swiftpm_manifest_not_utf8"})
    for token in FORBIDDEN_MANIFEST_TOKENS:
        if token in manifest_text:
            blocked.append({"kind": "swift_manifest_feature_unsupported", "feature": token})

    swift_binary = str(swift_section.get("binary") or shutil.which("swift") or "")
    swiftc_binary = str(swift_section.get("swiftc_binary") or shutil.which("swiftc") or "")
    product = swift_section.get("smoke_product")
    expected_stdout = swift_section.get("smoke_expected_stdout")
    if not swift_binary or not swiftc_binary:
        blocked.append({"kind": "swift_tool_missing"})
    if not isinstance(product, str) or not product or not isinstance(expected_stdout, str):
        blocked.append({"kind": "swift_executable_smoke_required"})

    source_files = sorted(
        path.relative_to(root).as_posix()
        for path in (root / current_source).rglob("*")
        if path.is_file() and not path.is_symlink()
    ) if (root / current_source).is_dir() else []
    if not source_files or any(Path(path).suffix != ".swift" for path in source_files):
        blocked.append({"kind": "swift_target_requires_only_swift_sources", "paths": source_files})
    generated = [path for path in source_files if GENERATED_RE.search((root / path).read_text(encoding="utf-8", errors="replace"))]
    if generated:
        blocked.append({"kind": "swift_generated_source", "paths": generated})
    mixed = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "Sources").rglob("*")
        if path.is_file() and not path.is_symlink() and path.suffix != ".swift"
    ) if (root / "Sources").is_dir() else []
    if mixed:
        blocked.append({"kind": "swift_mixed_language_unsupported", "paths": mixed})

    manifest_after = manifest_text
    exact_change = None
    if mode == "check":
        if not _manifest_after_is_exact(manifest_text, target, destination):
            blocked.append({"kind": "swiftpm_target_path_not_applied"})
    else:
        manifest_after, exact_change = _manifest_rewrite(manifest_text, target, destination)
        if manifest_after is None:
            blocked.append(exact_change or {"kind": "swift_manifest_unsupported"})
            manifest_after = manifest_text

    partial: list[dict] = []
    for path in sorted((root / "Sources").rglob("*.swift")) if (root / "Sources").is_dir() else []:
        text = path.read_text(encoding="utf-8", errors="replace")
        if source in text:
            partial.append({"kind": "swift_unproved_reflective_path_identity", "path": path.relative_to(root).as_posix()})

    native: dict = {}
    package: dict | None = None
    with tempfile.TemporaryDirectory(prefix="move-path-swift-") as temp:
        state = Path(temp)
        for directory in ("cache", "config", "security"):
            (state / directory).mkdir(parents=True, exist_ok=True)
        if swift_binary:
            package, native["dump_package"] = _dump_package(swift_binary, root, state)
        if package is not None:
            if package.get("dependencies"):
                blocked.append({"kind": "swift_dependency_resolution_unsupported"})
            targets = [row for row in package.get("targets", []) if row.get("name") == target]
            if len(targets) != 1 or targets[0].get("type") != "regular":
                blocked.append({"kind": "swiftpm_regular_target_required", "target": target})
            elif targets[0].get("resources") or targets[0].get("settings"):
                blocked.append({"kind": "swift_target_resource_or_build_setting_unsupported"})
            product_rows = [row for row in package.get("products", []) if row.get("name") == product]
            if len(product_rows) != 1 or product_rows[0].get("type", {}).get("executable", "missing") is not None:
                blocked.append({"kind": "swift_executable_product_required", "product": product})
            target_names = {row.get("name") for row in package.get("targets", [])}
            for path in sorted((root / "Sources").rglob("*.swift")) if (root / "Sources").is_dir() else []:
                for imported in IMPORT_RE.findall(path.read_text(encoding="utf-8", errors="replace")):
                    if imported not in target_names:
                        blocked.append({"kind": "swift_framework_or_external_import_unsupported", "path": path.relative_to(root).as_posix(), "import": imported})
        elif swift_binary and native.get("dump_package"):
            blocked.append({"kind": "swiftpm_manifest_failed"})
        if swiftc_binary and source_files and not blocked:
            native["typecheck_preflight"] = _run(
                [swiftc_binary, "-typecheck", *[str(root / path) for path in source_files]], root
            )
            if not native["typecheck_preflight"]["passed"]:
                blocked.append({"kind": "swift_typecheck_failed"})

        status = "failed" if any(item["kind"] in {"swiftpm_manifest_failed", "swift_typecheck_failed"} for item in blocked) else "unsupported" if blocked else "partial" if partial else "complete"
        blocked.extend(partial)
        expected = _expected_snapshot(before, source, destination, manifest_after.encode("utf-8")) if mode != "check" else before
        review = _review_diff(manifest_text, manifest_after, source, destination, source_files) if mode != "check" else ""
        swift_report = {
            "mode": "update-swift", "status": status, "target": target,
            "source": source, "destination": destination,
            "blocked": blocked, "exact_changes": [exact_change] if exact_change else [],
            "review_diff": review,
            "source_manifest": {
                "before_fingerprint": _fingerprint(before),
                "expected_fingerprint": _fingerprint(expected),
                "actual_fingerprint": _fingerprint(before) if mode == "check" else None,
                "files_before": sorted(before), "files_expected": sorted(expected),
            },
            "excluded_files": sorted(path for path in before if any(part in EXCLUDED_PARTS for part in Path(path).parts)),
            "native": native, "rolled_back": False,
        }
        payload = _base_payload(root, plan_path, mode, move, swift_report)
        _write_report(report_dir, payload)
        if mode == "dry-run" or (mode == "check" and status != "complete"):
            return payload
        if status != "complete":
            raise SystemExit(f"blocked findings prevent apply; see {report_dir / 'report.md'}")
        if mode == "apply":
            shutil.move(str(root / source), str(root / destination))
            manifest_path.write_text(manifest_after, encoding="utf-8")
        package_after, native["dump_package_after"] = _dump_package(swift_binary, root, state)
        build_argv = _swift_argv(swift_binary, root, state, "build") + ["--product", product]
        native["build"] = _run(build_argv, root)
        executable = state / "build" / "debug" / product
        native["smoke"] = _run([str(executable)], root) if native["build"]["passed"] else {
            "argv": [str(executable)], "passed": False, "returncode": None,
            "stdout": "", "stderr": "build failed",
        }
        native["smoke"]["passed"] = native["smoke"]["passed"] and native["smoke"]["stdout"] == expected_stdout
        actual, unexpected_links = _snapshot(root, report_dir)
        exact = _diff(expected, actual)
        exact["before_fingerprint"] = _fingerprint(before)
        if unexpected_links:
            exact["passed"] = False
            exact["unexpected_symlinks"] = unexpected_links
        native["exact_diff"] = exact
        passed = package_after is not None and all(row.get("passed", False) for row in native.values())
        if not passed:
            _restore(root, report_dir, before)
            swift_report["status"] = "failed"
            swift_report["rolled_back"] = True
            swift_report["blocked"].append({"kind": "swift_native_or_exact_check_failed"})
            payload["blocked"] = swift_report["blocked"]
            payload["summary"]["blocked"] = len(swift_report["blocked"])
            payload["summary"]["swift_status"] = "failed"
            _write_report(report_dir, payload)
            raise SystemExit(f"Swift native verification failed; source rolled back; see {report_dir / 'report.md'}")
        swift_report["source_manifest"]["actual_fingerprint"] = _fingerprint(actual)
        _write_report(report_dir, payload)
        if stage and (root / ".git").exists():
            subprocess.run(["git", "add", "--", source, destination, "Package.swift"], cwd=root, check=True)
        return payload
