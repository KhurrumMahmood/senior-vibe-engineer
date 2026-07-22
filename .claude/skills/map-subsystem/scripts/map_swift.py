#!/usr/bin/env python3
"""Build a bounded SwiftPM subsystem map from public native-tool surfaces."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


MINIMUM_SWIFT = (6, 0, 0)
EXCLUDED_PARTS = {".build", "build", "generated", "vendor"}
UNSUPPORTED_LIMITS = [
    "conditional compilation",
    "macros and plugins",
    "reflection and dynamic dispatch",
    "Xcode projects, workspaces, schemes, and Apple frameworks",
    "arbitrary package dependencies",
    "mixed-language targets",
]


class UserError(Exception):
    """Unsafe invocation that must not write artifacts."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(argv: list[str], *, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: dict) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _reject_symlink_chain(path: Path, stop: Path) -> None:
    current = path
    while current != stop:
        if current.is_symlink():
            raise UserError(f"symbolic link is not allowed: {current}")
        current = current.parent
    if stop.is_symlink():
        raise UserError(f"symbolic link is not allowed: {stop}")


def _validate_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        raise UserError("project root must be an existing directory")
    target_input = Path(args.target)
    target = target_input if target_input.is_absolute() else root / target_input
    target = target.resolve(strict=False)
    if not _is_within(target, root):
        raise UserError("target must stay inside project root")
    _reject_symlink_chain(target, root)

    output = Path(args.output).resolve(strict=False)
    evidence = Path(args.evidence).resolve(strict=False)
    allowed_output = root / ".claude" / "docs" / "subsystems"
    allowed_evidence = root / "reports" / "map"
    if not _is_within(output, allowed_output):
        raise UserError("output must stay under .claude/docs/subsystems")
    if not _is_within(evidence, allowed_evidence):
        raise UserError("evidence must stay under reports/map")
    for artifact, base in ((output, root), (evidence, root)):
        current = artifact.parent
        while current != base:
            if current.exists() and current.is_symlink():
                raise UserError(f"artifact parent is a symbolic link: {current}")
            current = current.parent
    return root, target, output, evidence


def _version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(?:Swift version|Apple Swift version)\s+(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _source_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {".build", "reports", ".claude", ".agents"} for part in relative.parts):
            continue
        if path.is_symlink():
            result[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _role(path: str) -> str:
    parts = Path(path).parts
    if path == "Package.swift":
        return "configuration"
    if any(part in {".build", "build"} for part in parts):
        return "build"
    if "generated" in parts:
        return "generated"
    if "vendor" in parts:
        return "vendor"
    if "Tests" in parts or Path(path).name.endswith(("Test.swift", "Tests.swift")):
        return "test"
    return "source"


def _inventory(root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(root.rglob("*.swift")):
        relative = path.relative_to(root).as_posix()
        rows.append({
            "path": relative,
            "role": "symlink" if path.is_symlink() else _role(relative),
            "included": _role(relative) == "source" and not path.is_symlink(),
        })
    if not any(row["path"] == "Package.swift" for row in rows):
        rows.append({"path": "Package.swift", "role": "configuration", "included": False})
    return sorted(rows, key=lambda row: row["path"])


def _terminal(
    *,
    name: str,
    target: str,
    status: str,
    failure_kind: str,
    message: str,
    toolchain: dict | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "language": "swift",
        "analyzer": "swiftpm+swift-build+sourcekit-lsp+symbolgraph",
        "name": name,
        "target": target,
        "generated_at": _now(),
        "status": status,
        "failure_kind": failure_kind,
        "message": message,
        "toolchain": toolchain or {},
        "limitations": UNSUPPORTED_LIMITS,
    }


def _render(payload: dict) -> str:
    lines = [
        "---",
        f"subsystem: {payload['name']}",
        "language: swift",
        f"status: {payload['status']}",
        f"regenerated: {payload['generated_at']}",
        "---",
        "",
        f"# {payload['name']}",
        "",
        f"Status: **{payload['status']}**",
        "",
    ]
    if payload.get("message"):
        lines.extend([payload["message"], ""])
    if payload["status"] in {"complete", "partial"} and "selected_target" in payload:
        selected = payload["selected_target"]
        lines.extend([
            "## SwiftPM target",
            "",
            f"- Package: `{payload['package']['name']}`",
            f"- Selected target: `{selected['name']}` (`{selected['type']}`)",
            f"- Sources: {', '.join(f'`{item}`' for item in selected['sources'])}",
            "",
            "## Public surface",
            "",
        ])
        if payload["public_surface"]:
            for symbol in payload["public_surface"]:
                lines.append(
                    f"- `{symbol['path']}` — {symbol['kind']} at "
                    f"`{symbol['file']}:{symbol['line']}`"
                )
        else:
            lines.append("- No public declarations.")
        lines.extend(["", "## Target and import edges", ""])
        for edge in payload["target_edges"]:
            lines.append(
                f"- `{edge['dependency']}` → `{edge['consumer']}` "
                f"(SwiftPM target dependency; import `{edge['import']}`)"
            )
        if not payload["target_edges"]:
            lines.append("- None in the bounded selected scope.")
        lines.extend([
            "",
            "## Native evidence",
            "",
            f"- Restrictive SwiftPM build: `{payload['native_evidence']['build']['status']}`",
            f"- SourceKit target inspection: `{payload['native_evidence']['index']['status']}`",
            f"- Compiler symbol graph: `{payload['native_evidence']['symbol_graph']['status']}`",
            "",
        ])
    lines.extend(["## Explicit limitations", ""])
    lines.extend(f"- {item}." for item in payload["limitations"])
    lines.append("")
    return "\n".join(lines)


def _write_terminal(output: Path, evidence: Path, payload: dict) -> int:
    _atomic_json(evidence, payload)
    _atomic_text(output, _render(payload))
    return 2 if payload["status"] == "failed" else 0


def _swiftpm_base(swift: str, root: Path, state: Path) -> list[str]:
    return [
        swift,
        "package",
        "--package-path", str(root),
        "--cache-path", str(state / "cache"),
        "--config-path", str(state / "config"),
        "--security-path", str(state / "security"),
        "--scratch-path", str(state / "build"),
        "--disable-dependency-cache",
        "--manifest-cache", "local",
        "--disable-netrc",
        "--disable-keychain",
        "--disable-prefetching",
        "--disable-automatic-resolution",
    ]


def _target_for_path(target: Path, root: Path, targets: list[dict]) -> dict | None:
    relative = target.relative_to(root).as_posix().rstrip("/")
    matches = []
    for item in targets:
        base = item.get("path", "").rstrip("/")
        files = {f"{base}/{source}" for source in item.get("sources", [])}
        if relative == base or relative in files:
            matches.append(item)
    return matches[0] if len(matches) == 1 else None


def _unsupported_shape(manifest: dict, description: dict) -> str | None:
    if manifest.get("dependencies"):
        return "arbitrary package dependencies are outside Swift v1"
    for target in manifest.get("targets", []):
        if target.get("resources") or target.get("settings"):
            return "resources, build settings, and conditional compilation are outside Swift v1"
        if target.get("type") not in {"regular", "executable", "test"}:
            return f"SwiftPM target type {target.get('type')!r} is outside Swift v1"
    for target in description.get("targets", []):
        if target.get("module_type") != "SwiftTarget":
            return "mixed-language targets are outside Swift v1"
        if any(Path(source).suffix != ".swift" for source in target.get("sources", [])):
            return "mixed-language targets are outside Swift v1"
    return None


def _source_imports(root: Path, target: dict) -> list[dict]:
    imports: list[dict] = []
    base = root / target["path"]
    for source in target.get("sources", []):
        path = base / source
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            match = re.match(r"^\s*(?:@testable\s+)?import\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?://.*)?$", line)
            if match:
                imports.append({"module": match.group(1), "file": path.relative_to(root).as_posix(), "line": number})
    return imports


def _target_edges(root: Path, targets: list[dict]) -> list[dict]:
    names = {target["name"] for target in targets}
    edges: list[dict] = []
    for consumer in targets:
        dependencies = set(consumer.get("target_dependencies", []))
        for item in _source_imports(root, consumer):
            if item["module"] in dependencies and item["module"] in names:
                edges.append({
                    "dependency": item["module"],
                    "consumer": consumer["name"],
                    "import": item["module"],
                    "file": item["file"],
                    "line": item["line"],
                    "resolution": "swiftpm_target_dependency+successful_build_index",
                })
    return edges


def _index_targets(output: str, targets: list[dict], root: Path) -> tuple[dict[str, dict], bool]:
    results: dict[str, dict] = {}
    names = [target["name"] for target in targets]
    for name in names:
        marker = f"Preparing {name}"
        start = output.find(marker)
        if start < 0:
            results[name] = {"status": "missing", "prepare_exit_codes": []}
            continue
        stops = [output.find(f"Preparing {other}", start + len(marker)) for other in names]
        stops = [stop for stop in stops if stop >= 0]
        chunk = output[start:min(stops) if stops else len(output)]
        codes = [int(value) for value in re.findall(r"Finished with exit code (\d+)", chunk)]
        expected_sources = [
            str((root / target["path"] / source).resolve())
            for target in targets
            if target["name"] == name
            for source in target.get("sources", [])
        ]
        sources = [source for source in expected_sources if f"Indexing {source}" in output]
        build_ok = f"Build of target: '{name}' complete!" in chunk
        results[name] = {
            "status": "complete" if build_ok and codes and all(code == 0 for code in codes) and sources == expected_sources else "failed",
            "prepare_exit_codes": codes,
            "indexed_sources": sources,
        }
    return results, bool(results) and all(item["status"] == "complete" for item in results.values())


def _public_surface(root: Path, symbol_dir: Path, selected: dict) -> list[dict]:
    graph = symbol_dir / f"{selected['name']}.symbols.json"
    if not graph.is_file():
        return []
    payload = json.loads(graph.read_text(encoding="utf-8"))
    rows = []
    selected_root = (root / selected["path"]).resolve()
    for symbol in payload.get("symbols", []):
        location = symbol.get("location", {})
        uri = location.get("uri")
        if not uri:
            continue
        parsed = urlparse(uri)
        path = Path(unquote(parsed.path)).resolve()
        if not _is_within(path, selected_root):
            continue
        rows.append({
            "identifier": symbol.get("identifier", {}).get("precise"),
            "path": ".".join(symbol.get("pathComponents", [])),
            "kind": symbol.get("kind", {}).get("identifier", "swift.unknown"),
            "access": symbol.get("accessLevel"),
            "file": path.relative_to(root).as_posix(),
            "line": location.get("position", {}).get("line", 0) + 1,
            "declaration": "".join(fragment.get("spelling", "") for fragment in symbol.get("declarationFragments", [])),
            "fact_source": "swift compiler symbol graph",
        })
    return sorted(rows, key=lambda row: (row["file"], row["line"], row["path"]))


def map_swift(args: argparse.Namespace) -> int:
    root, target_path, output, evidence = _validate_paths(args)
    relative_target = target_path.relative_to(root).as_posix()
    output.unlink(missing_ok=True)
    evidence.unlink(missing_ok=True)
    swift = shutil.which(args.swift) if not Path(args.swift).is_absolute() else args.swift
    sourcekit = shutil.which(args.sourcekit_lsp) if not Path(args.sourcekit_lsp).is_absolute() else args.sourcekit_lsp
    toolchain: dict = {"swift": swift, "sourcekit_lsp": sourcekit}
    if not swift or not Path(swift).is_file():
        payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="swift_tool_missing", message="Swift 6.0+ is required.", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    version_run = _run([str(swift), "--version"], cwd=root, timeout=10)
    version = _version(version_run.stdout + version_run.stderr)
    toolchain["swift_version"] = ".".join(map(str, version)) if version else None
    if version is None or version < tuple(args.minimum_swift):
        payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="swift_version_too_old", message="The selected Swift tool is unavailable or older than the required version.", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    if not sourcekit or not Path(sourcekit).is_file():
        payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="sourcekit_lsp_missing", message="SourceKit-LSP is required for the bounded semantic map.", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    if not target_path.exists() or any(part in EXCLUDED_PARTS or part == "Tests" for part in Path(relative_target).parts):
        payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="excluded_or_missing_target", message="The target is missing or has a non-production source role.", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    if not (root / "Package.swift").is_file():
        payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="swiftpm_manifest_missing", message="A SwiftPM Package.swift is required.", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)

    before = _source_manifest(root)
    state = evidence.parent / ".swift-state"
    shutil.rmtree(state, ignore_errors=True)
    for child in ("cache", "config", "security", "build"):
        (state / child).mkdir(parents=True, exist_ok=True)
    base = _swiftpm_base(str(swift), root, state)
    dump = _run(base + ["dump-package"], cwd=root)
    if dump.returncode != 0:
        payload = _terminal(name=args.name, target=relative_target, status="failed", failure_kind="swiftpm_manifest_invalid", message=(dump.stderr or "SwiftPM manifest inspection failed.").strip()[:2000], toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    try:
        manifest = json.loads(dump.stdout)
    except json.JSONDecodeError as exc:
        payload = _terminal(name=args.name, target=relative_target, status="failed", failure_kind="swiftpm_output_invalid", message=str(exc), toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    if manifest.get("dependencies"):
        payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="unsupported_package_shape", message="arbitrary package dependencies are outside Swift v1", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    describe = _run(base + ["describe", "--type", "json"], cwd=root)
    if describe.returncode != 0:
        payload = _terminal(name=args.name, target=relative_target, status="failed", failure_kind="swiftpm_manifest_invalid", message=(describe.stderr or "SwiftPM target graph inspection failed.").strip()[:2000], toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    try:
        description = json.loads(describe.stdout)
    except json.JSONDecodeError as exc:
        payload = _terminal(name=args.name, target=relative_target, status="failed", failure_kind="swiftpm_output_invalid", message=str(exc), toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    shape_error = _unsupported_shape(manifest, description)
    if shape_error:
        payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="unsupported_package_shape", message=shape_error, toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    targets = description.get("targets", [])
    selected = _target_for_path(target_path, root, targets)
    if selected is None:
        payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="target_not_in_swiftpm_graph", message="Target must resolve to exactly one declared SwiftPM source target.", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    for declared_target in targets:
        source_root = root / declared_target["path"]
        for source in declared_target.get("sources", []):
            source_path = source_root / source
            if source_path.is_symlink() or not _is_within(source_path.resolve(), root):
                payload = _terminal(name=args.name, target=relative_target, status="unsupported", failure_kind="unsafe_source", message=f"SwiftPM source is a symbolic link or escapes the project: {source_path.relative_to(root)}", toolchain=toolchain)
                return _write_terminal(output, evidence, payload)

    build = _run([
        str(swift), "build", "--package-path", str(root),
        "--cache-path", str(state / "cache"), "--config-path", str(state / "config"),
        "--security-path", str(state / "security"), "--scratch-path", str(state / "build"),
        "--disable-dependency-cache", "--manifest-cache", "local", "--disable-netrc",
        "--disable-keychain", "--disable-prefetching", "--disable-automatic-resolution",
        "--enable-index-store",
    ], cwd=root)
    if build.returncode != 0:
        payload = _terminal(name=args.name, target=relative_target, status="failed", failure_kind="native_build_failed", message=(build.stdout + build.stderr).strip()[-3000:], toolchain=toolchain)
        return _write_terminal(output, evidence, payload)

    index_root = root / ".build" / "index-build"
    if index_root.is_symlink():
        raise UserError("SwiftPM index artifact path is a symbolic link")
    shutil.rmtree(index_root, ignore_errors=True)
    index = _run([str(sourcekit), "debug", "index", "--project", str(root)], cwd=root, timeout=180)
    index_text = index.stdout + index.stderr
    per_target, targets_complete = _index_targets(index_text, targets, root)
    shutil.rmtree(index_root, ignore_errors=True)
    if index.returncode != 0 or not targets_complete:
        payload = _terminal(name=args.name, target=relative_target, status="failed" if any(item["status"] == "failed" for item in per_target.values()) else "partial", failure_kind="sourcekit_target_failure" if any(item["status"] == "failed" for item in per_target.values()) else "sourcekit_index_incomplete", message="SourceKit-LSP did not prove every declared target prepared and indexed successfully.", toolchain=toolchain)
        payload["native_evidence"] = {"index": {"process_exit": index.returncode, "targets": per_target}}
        return _write_terminal(output, evidence, payload)

    symbol_dir = state / "build" / "arm64-apple-macosx" / "symbolgraph"
    shutil.rmtree(symbol_dir, ignore_errors=True)
    symbols = _run(base + ["dump-symbol-graph", "--minimum-access-level", "public"], cwd=root)
    if symbols.returncode != 0:
        payload = _terminal(name=args.name, target=relative_target, status="partial", failure_kind="compiler_symbol_graph_incomplete", message="The successful build/index did not yield compiler public-surface facts.", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)
    after = _source_manifest(root)
    if before != after:
        payload = _terminal(name=args.name, target=relative_target, status="failed", failure_kind="unexpected_source_mutation", message="Native analysis changed a non-artifact project file.", toolchain=toolchain)
        return _write_terminal(output, evidence, payload)

    surface = _public_surface(root, symbol_dir, selected)
    edges = _target_edges(root, targets)
    payload = {
        "schema_version": 1,
        "language": "swift",
        "analyzer": "swiftpm+swift-build+sourcekit-lsp+symbolgraph",
        "name": args.name,
        "target": relative_target,
        "generated_at": _now(),
        "status": "complete",
        "failure_kind": None,
        "message": "Complete only for the declared dependency-free SwiftPM target graph and this successful build/index snapshot.",
        "package": {"name": description["name"], "tools_version": description.get("tools_version"), "dependencies": []},
        "selected_target": {
            "name": selected["name"],
            "type": selected["type"],
            "path": selected["path"],
            "sources": [f"{selected['path']}/{source}" for source in selected.get("sources", [])],
        },
        "targets": targets,
        "source_inventory": _inventory(root),
        "public_surface": surface,
        "target_edges": edges,
        "native_evidence": {
            "build": {"status": "complete", "process_exit": build.returncode, "scratch_path": str(state / "build"), "restrictive_resolution": True},
            "index": {"status": "complete", "process_exit": index.returncode, "targets": per_target, "forced_clean_index": True},
            "symbol_graph": {"status": "complete", "process_exit": symbols.returncode, "symbol_count": len(surface)},
        },
        "source_manifest_sha256": hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
        "toolchain": toolchain,
        "limitations": UNSUPPORTED_LIMITS,
    }
    return _write_terminal(output, evidence, payload)


def _minimum(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if not 2 <= len(parts) <= 3 or not all(part.isdigit() for part in parts):
        raise argparse.ArgumentTypeError("expected MAJOR.MINOR[.PATCH]")
    return tuple(int(part) for part in (parts + ["0"])[:3])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--swift", default="swift")
    parser.add_argument("--sourcekit-lsp", default="sourcekit-lsp")
    parser.add_argument("--minimum-swift", type=_minimum, default=MINIMUM_SWIFT)
    args = parser.parse_args(argv)
    try:
        return map_swift(args)
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
