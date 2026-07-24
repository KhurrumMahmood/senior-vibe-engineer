#!/usr/bin/env python3
"""Move one manifest-owned Kotlin/JVM source file without changing identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "kotlin-source-move-evidence-v1"
REPORT_SCHEMA = "kotlin-source-move-report-v1"
KOTLIN_VERSION = "2.4.10"
JVM_TARGET = "17"
SOURCE_ROOT = PurePosixPath("src/main/kotlin")
TEST_ROOT = PurePosixPath("tests")
EXCLUDED_PARTS = frozenset(
    {".git", ".gradle", "build", "dist", "generated", "out", "target", "vendor"}
)
GENERATED_RE = re.compile(
    rb"(?im)(code generated|generated (?:by|source)|do not edit)"
)
PACKAGE_RE = re.compile(r"(?m)^\s*package\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*$")
FILE_ANNOTATION_RE = re.compile(r"(?m)^\s*@file:")
GRADLE_VARIANT_RE = re.compile(
    r"(?m)^\s*(?:plugins|dependencies|sourceSets|repositories|kotlin|android)\s*\{"
)
DYNAMIC_RUNTIME_RE = re.compile(
    r"(?:Class\.forName|ClassLoader|ServiceLoader|URLClassLoader|loadClass\s*\(|"
    r"getResource(?:AsStream)?\s*\(|::class|kotlin\.reflect|java\.lang\.reflect|"
    r"java\.io\.File|java\.nio\.file|Paths\.|System\.getProperty\s*\(|"
    r"StackTraceElement|\.stackTrace\b|org\.springframework|jakarta\.persistence|"
    r"javax\.persistence|kotlinx\.serialization|com\.fasterxml\.jackson|"
    r"dagger\.|org\.koin)"
)


class UserError(RuntimeError):
    """Unsafe or invalid input that must not mutate the project."""


@dataclass(frozen=True)
class FileState:
    content: bytes
    mode: int


@dataclass(frozen=True)
class TreeState:
    files: dict[str, FileState]
    symlinks: dict[str, str]


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return _sha(rendered.encode("utf-8"))


def _relative(raw: Any, *, field: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise UserError(f"{field}_invalid")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise UserError(f"{field}_invalid")
    return path.as_posix()


def _inside(relative: str, parent: PurePosixPath) -> bool:
    try:
        PurePosixPath(relative).relative_to(parent)
    except ValueError:
        return False
    return True


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_bytes(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _excluded(path: Path, root: Path, report_dir: Path) -> bool:
    relative = path.relative_to(root)
    if relative.parts and relative.parts[0] == ".git":
        return True
    try:
        path.resolve().relative_to(report_dir.resolve())
    except ValueError:
        return False
    return True


def _snapshot(root: Path, report_dir: Path) -> TreeState:
    files: dict[str, FileState] = {}
    symlinks: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            symlinks[relative] = os.readlink(path)
        elif path.is_file():
            files[relative] = FileState(
                path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
            )
    return TreeState(files, symlinks)


def _tree_payload(state: TreeState) -> dict[str, Any]:
    return {
        "files": [
            {"path": path, "sha256": _sha(value.content), "mode": value.mode}
            for path, value in sorted(state.files.items())
        ],
        "symlinks": [
            {"path": path, "target": target}
            for path, target in sorted(state.symlinks.items())
        ],
    }


def _tree_hash(state: TreeState) -> str:
    return _canonical_hash(_tree_payload(state))


def _materialize(root: Path, state: TreeState) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for relative, value in sorted(state.files.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.content)
        path.chmod(value.mode)
    for relative, target in sorted(state.symlinks.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)


def _restore(root: Path, report_dir: Path, state: TreeState) -> None:
    current = _snapshot(root, report_dir)
    for relative in sorted(current.symlinks, reverse=True):
        (root / relative).unlink(missing_ok=True)
    for relative in sorted(current.files, reverse=True):
        (root / relative).unlink(missing_ok=True)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and not path.is_symlink() and not _excluded(path, root, report_dir):
            try:
                path.rmdir()
            except OSError:
                pass
    _materialize(root, state)


def _has_symlink_boundary(root: Path, relative: str) -> bool:
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            return True
        if not current.exists():
            break
    return False


def _tool(raw: Any, *, label: str) -> dict[str, str]:
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise UserError(f"kotlin_{label}_path_invalid")
    requested = Path(raw)
    try:
        resolved = requested.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise UserError(f"kotlin_{label}_unavailable") from exc
    if not resolved.is_file() or not os.access(requested, os.X_OK):
        raise UserError(f"kotlin_{label}_unavailable")
    return {"requested": str(requested), "path": str(resolved)}


def _run(argv: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "argv": argv,
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "argv": argv,
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UserError("kotlin_plan_invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "moves",
        "rewrite",
        "kotlin",
    }:
        raise UserError("kotlin_plan_invalid")
    if payload["version"] != 1:
        raise UserError("kotlin_plan_version_unsupported")
    moves = payload["moves"]
    if not isinstance(moves, list) or len(moves) != 1:
        raise UserError("kotlin_requires_exactly_one_move")
    move = moves[0]
    if not isinstance(move, dict) or set(move) != {"from", "to", "mode"}:
        raise UserError("kotlin_requires_one_file_move")
    if move["mode"] != "file":
        raise UserError("kotlin_requires_one_file_move")
    source = _relative(move["from"], field="kotlin_source_path")
    destination = _relative(move["to"], field="kotlin_destination_path")
    if PurePosixPath(source).suffix != ".kt" or PurePosixPath(destination).suffix != ".kt":
        raise UserError("kotlin_requires_kt_source")
    if not _inside(source, SOURCE_ROOT) or not _inside(destination, SOURCE_ROOT):
        raise UserError("kotlin_requires_manifested_authored_source")
    if PurePosixPath(source).name != PurePosixPath(destination).name:
        raise UserError("kotlin_jvm_identity_change_refused")
    if source == destination:
        raise UserError("kotlin_move_must_change_path")
    if any(part in EXCLUDED_PARTS for part in PurePosixPath(destination).parts):
        raise UserError("kotlin_generated_vendor_destination_refused")
    if payload["rewrite"] != {"code_imports": "update-kotlin-jvm"}:
        raise UserError("kotlin_rewrite_contract_invalid")
    config = payload["kotlin"]
    if not isinstance(config, dict) or set(config) != {
        "manifest",
        "kotlinc",
        "java",
        "kotlin_version",
        "jvm_target",
    }:
        raise UserError("kotlin_configuration_invalid")
    manifest = _relative(config["manifest"], field="kotlin_manifest_path")
    if manifest != "kotlin-project.json":
        raise UserError("kotlin_manifest_unsupported")
    if config["kotlin_version"] != KOTLIN_VERSION or config["jvm_target"] != JVM_TARGET:
        raise UserError("kotlin_toolchain_contract_unsupported")
    return {
        "raw": payload,
        "source": source,
        "destination": destination,
        "manifest": manifest,
        "kotlinc": _tool(config["kotlinc"], label="kotlinc"),
        "java": _tool(config["java"], label="java"),
    }


def _manifest(root: Path, relative: str) -> tuple[dict[str, Any], bytes, int]:
    path = root / relative
    if _has_symlink_boundary(root, relative) or not path.is_file():
        raise UserError("kotlin_manifest_unavailable")
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UserError("kotlin_manifest_invalid") from exc
    keys = {
        "schema_version",
        "jvm_target",
        "sources",
        "tests",
        "test_main",
        "smoke_output",
    }
    if not isinstance(payload, dict) or set(payload) != keys:
        raise UserError("kotlin_manifest_invalid")
    if payload["schema_version"] != 1 or payload["jvm_target"] != JVM_TARGET:
        raise UserError("kotlin_manifest_contract_unsupported")
    if not isinstance(payload["sources"], list) or not payload["sources"]:
        raise UserError("kotlin_manifest_incomplete")
    if not isinstance(payload["tests"], list) or not payload["tests"]:
        raise UserError("kotlin_manifest_incomplete")
    if not isinstance(payload["test_main"], str) or not payload["test_main"]:
        raise UserError("kotlin_manifest_invalid")
    if not isinstance(payload["smoke_output"], str):
        raise UserError("kotlin_manifest_invalid")
    for key, parent in (("sources", SOURCE_ROOT), ("tests", TEST_ROOT)):
        values = payload[key]
        if len(values) != len(set(values)):
            raise UserError("kotlin_manifest_duplicate_input")
        for index, value in enumerate(values):
            relative_path = _relative(value, field=f"kotlin_manifest_{key}_{index}")
            if PurePosixPath(relative_path).suffix != ".kt" or not _inside(relative_path, parent):
                raise UserError("kotlin_manifest_input_unsupported")
            source = root / relative_path
            if _has_symlink_boundary(root, relative_path):
                raise UserError("kotlin_symlink_boundary")
            if not source.is_file():
                raise UserError("kotlin_manifest_incomplete")
    discovered_sources = {
        path.relative_to(root).as_posix()
        for path in (root / SOURCE_ROOT.as_posix()).rglob("*.kt")
        if path.is_file()
    }
    discovered_tests = {
        path.relative_to(root).as_posix()
        for path in (root / TEST_ROOT.as_posix()).rglob("*.kt")
        if path.is_file()
    }
    if discovered_sources != set(payload["sources"]) or discovered_tests != set(payload["tests"]):
        raise UserError("kotlin_manifest_incomplete")
    return payload, raw, stat.S_IMODE(path.stat().st_mode)


def _package(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise UserError("kotlin_source_not_utf8") from exc
    matches = PACKAGE_RE.findall(text)
    if len(matches) != 1:
        raise UserError("kotlin_package_identity_uncertain")
    package = matches[0]
    if package.split(".", 1)[0] in {"java", "javax", "kotlin"}:
        raise UserError("kotlin_reserved_package_refused")
    return package


def _safety_blocks(
    root: Path,
    report_dir: Path,
    plan_path: Path,
    plan: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    source_path = root / plan["source"]
    if _has_symlink_boundary(root, plan["source"]) or _has_symlink_boundary(
        root, plan["destination"]
    ):
        blocked.append({"kind": "kotlin_symlink_boundary"})
        return blocked
    if not source_path.is_file() or source_path.is_symlink():
        blocked.append({"kind": "kotlin_source_unavailable"})
        return blocked
    if (root / plan["destination"]).exists() or (root / plan["destination"]).is_symlink():
        blocked.append({"kind": "kotlin_destination_exists"})
    if plan["source"] not in manifest["sources"] or plan["destination"] in manifest["sources"]:
        blocked.append({"kind": "kotlin_requires_manifested_authored_source"})
    if GENERATED_RE.search(source_path.read_bytes()) or any(
        part in EXCLUDED_PARTS for part in PurePosixPath(plan["source"]).parts
    ):
        blocked.append({"kind": "kotlin_generated_vendor_source_refused"})
    try:
        plan_relative = plan_path.relative_to(root).as_posix()
    except ValueError:
        plan_relative = None
    for relative in [*manifest["sources"], *manifest["tests"]]:
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            blocked.append({"kind": "kotlin_source_not_utf8", "path": relative})
            continue
        if FILE_ANNOTATION_RE.search(text):
            blocked.append({"kind": "kotlin_file_annotation_refused", "path": relative})
        if DYNAMIC_RUNTIME_RE.search(text):
            blocked.append({"kind": "kotlin_dynamic_runtime_uncertain", "path": relative})
        try:
            _package(path)
        except UserError as exc:
            blocked.append({"kind": str(exc), "path": relative})
    resources = root / "src/main/resources"
    if resources.exists() and any(path.is_file() or path.is_symlink() for path in resources.rglob("*")):
        blocked.append({"kind": "kotlin_resource_boundary_uncertain"})
    for name in ("build.gradle.kts", "settings.gradle.kts"):
        path = root / name
        if path.is_file():
            try:
                if GRADLE_VARIANT_RE.search(path.read_text(encoding="utf-8")):
                    blocked.append({"kind": "kotlin_gradle_variant_uncertain", "path": name})
            except UnicodeError:
                blocked.append({"kind": "kotlin_gradle_variant_uncertain", "path": name})
    for relative, value in _snapshot(root, report_dir).files.items():
        if relative in {plan["manifest"], plan_relative} or relative.startswith(".native-build/"):
            continue
        if plan["source"].encode("utf-8") in value.content:
            blocked.append({"kind": "kotlin_path_sensitive_reference", "path": relative})
    return blocked


def _manifest_after(
    raw: bytes, manifest: dict[str, Any], source: str, destination: str
) -> bytes:
    if manifest["sources"].count(source) != 1:
        raise UserError("kotlin_manifest_source_ambiguous")
    old = json.dumps(source).encode("utf-8")
    new = json.dumps(destination).encode("utf-8")
    if raw.count(old) != 1:
        raise UserError("kotlin_manifest_source_ambiguous")
    rendered = raw.replace(old, new, 1)
    try:
        after = json.loads(rendered.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise UserError("kotlin_manifest_edit_invalid") from exc
    expected = dict(manifest)
    expected["sources"] = [destination if value == source else value for value in manifest["sources"]]
    if after != expected:
        raise UserError("kotlin_manifest_edit_not_exact")
    return rendered


def _expected_tree(
    before: TreeState, plan: dict[str, Any], manifest_after: bytes
) -> TreeState:
    files = dict(before.files)
    source = files.pop(plan["source"])
    files[plan["destination"]] = source
    manifest = files[plan["manifest"]]
    files[plan["manifest"]] = FileState(manifest_after, manifest.mode)
    return TreeState(files, dict(before.symlinks))


def _classes(jar: Path, packages: set[str]) -> dict[str, str]:
    prefixes = tuple(package.replace(".", "/") + "/" for package in sorted(packages))
    try:
        with zipfile.ZipFile(jar) as archive:
            rows = {
                name: _sha(archive.read(name))
                for name in archive.namelist()
                if name.endswith(".class") and name.startswith(prefixes)
            }
    except (OSError, zipfile.BadZipFile) as exc:
        raise UserError("kotlin_compiler_output_invalid") from exc
    if not rows:
        raise UserError("kotlin_jvm_identity_unavailable")
    return dict(sorted(rows.items()))


def _native(root: Path, plan: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    kotlinc = plan["kotlinc"]["requested"]
    java = plan["java"]["requested"]
    source_paths = [str(root / relative) for relative in manifest["sources"]]
    test_paths = [str(root / relative) for relative in manifest["tests"]]
    packages = {
        _package(root / relative)
        for relative in [*manifest["sources"], *manifest["tests"]]
    }
    with tempfile.TemporaryDirectory(prefix="kotlin-source-move-native-") as raw:
        output = Path(raw)
        app = output / "app.jar"
        tests = output / "tests.jar"
        common = [kotlinc, "-jvm-target", JVM_TARGET, "-Werror", "-include-runtime"]
        compile_result = _run([*common, "-d", str(app), *source_paths], root)
        test_compile = _run(
            [*common, "-d", str(tests), *source_paths, *test_paths], root
        )
        test_result: dict[str, Any] = {
            "argv": [java, "-cp", str(tests), manifest["test_main"]],
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": "compile-tests did not pass",
        }
        smoke_result: dict[str, Any] = {
            "argv": [java, "-jar", str(app)],
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": "compile did not pass",
        }
        classes: dict[str, str] = {}
        if compile_result["passed"]:
            smoke_result = _run([java, "-jar", str(app)], root)
            try:
                classes = _classes(app, packages)
            except UserError as exc:
                smoke_result["passed"] = False
                smoke_result["stderr"] = str(exc)
        if test_compile["passed"]:
            test_result = _run([java, "-cp", str(tests), manifest["test_main"]], root)
        smoke_result["passed"] = (
            smoke_result["passed"]
            and smoke_result["stdout"] == manifest["smoke_output"]
        )
        return {
            "compile": compile_result,
            "compile_tests": test_compile,
            "test": test_result,
            "smoke": smoke_result,
            "classes": classes,
        }


def _native_passed(native: dict[str, Any]) -> bool:
    return all(native.get(key, {}).get("passed") is True for key in ("compile", "compile_tests", "test", "smoke"))


def _versions(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    kotlinc = _run([plan["kotlinc"]["requested"], "-version"], root)
    java = _run([plan["java"]["requested"], "-version"], root)
    combined_kotlinc = kotlinc["stdout"] + kotlinc["stderr"]
    combined_java = java["stdout"] + java["stderr"]
    return {
        "kotlinc": kotlinc,
        "java": java,
        "passed": (
            kotlinc["passed"]
            and java["passed"]
            and f"kotlinc-jvm {KOTLIN_VERSION}" in combined_kotlinc
            and re.search(r'(?m)(?:openjdk|java) version "17(?:[.\"]|$)', combined_java)
            is not None
        ),
    }


def _mutate(root: Path, plan: dict[str, Any], manifest_after: bytes, manifest_mode: int) -> None:
    source = root / plan["source"]
    destination = root / plan["destination"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    _atomic_bytes(root / plan["manifest"], manifest_after, manifest_mode)


def _analysis(root: Path, report_dir: Path, plan_path: Path, plan: dict[str, Any]) -> dict[str, Any]:
    full = _snapshot(root, report_dir)
    blocked: list[dict[str, Any]] = []
    try:
        manifest, manifest_raw, manifest_mode = _manifest(root, plan["manifest"])
    except UserError as exc:
        return {"full": full, "blocked": [{"kind": str(exc)}], "changes": []}
    blocked.extend(_safety_blocks(root, report_dir, plan_path, plan, manifest))
    versions = _versions(plan, root)
    if not versions["passed"]:
        blocked.append({"kind": "kotlin_toolchain_version_unsupported"})
    try:
        manifest_after = _manifest_after(
            manifest_raw, manifest, plan["source"], plan["destination"]
        )
        expected = _expected_tree(full, plan, manifest_after)
    except (KeyError, UserError) as exc:
        blocked.append({"kind": str(exc)})
        return {
            "full": full,
            "blocked": blocked,
            "changes": [],
            "manifest": manifest,
            "versions": versions,
        }
    changes = [
        {"kind": "kotlin_source_path", "old": plan["source"], "new": plan["destination"]},
        {
            "file": plan["manifest"],
            "kind": "kotlin_manifest_source",
            "old": plan["source"],
            "new": plan["destination"],
        },
    ]
    native_before: dict[str, Any] = {}
    native_after: dict[str, Any] = {}
    if not blocked:
        native_before = _native(root, plan, manifest)
        if not _native_passed(native_before):
            blocked.append({"kind": "kotlin_native_preflight_failed"})
    if not blocked:
        with tempfile.TemporaryDirectory(prefix="kotlin-source-move-preview-") as raw:
            virtual_root = Path(raw) / "host"
            _materialize(virtual_root, full)
            _mutate(virtual_root, plan, manifest_after, manifest_mode)
            virtual_manifest, _, _ = _manifest(virtual_root, plan["manifest"])
            native_after = _native(virtual_root, plan, virtual_manifest)
            actual = _snapshot(virtual_root, virtual_root / "reports/move-path")
            if not _native_passed(native_after):
                blocked.append({"kind": "kotlin_virtual_postflight_failed"})
            if _tree_hash(actual) != _tree_hash(expected):
                blocked.append({"kind": "kotlin_virtual_after_tree_mismatch"})
            if native_before.get("classes") != native_after.get("classes"):
                blocked.append({"kind": "kotlin_jvm_identity_changed"})
    return {
        "full": full,
        "expected": expected,
        "blocked": blocked,
        "changes": changes,
        "manifest": manifest,
        "manifest_after": manifest_after,
        "manifest_mode": manifest_mode,
        "versions": versions,
        "native_before": native_before,
        "native_after": native_after,
    }


def _evidence(plan_path: Path, plan: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "plan_sha256": _sha(plan_path.read_bytes()),
        "plan": plan["raw"],
        "adapter_sha256": _sha(Path(__file__).read_bytes()),
        "source": plan["source"],
        "destination": plan["destination"],
        "source_tree_sha256": _tree_hash(facts["full"]),
        "expected_after_tree_sha256": _tree_hash(facts["expected"]),
        "exact_changes": facts["changes"],
        "tooling": {
            "kotlinc": plan["kotlinc"],
            "java": plan["java"],
            "kotlin_version": KOTLIN_VERSION,
            "jvm_target": JVM_TARGET,
        },
        "classes": facts["native_before"]["classes"],
        "native_stdout": {
            "test": facts["native_before"]["test"]["stdout"],
            "smoke": facts["native_before"]["smoke"]["stdout"],
        },
    }
    payload["evidence_sha256"] = _canonical_hash(payload)
    return payload


def _load_evidence(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UserError("kotlin_evidence_invalid") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise UserError("kotlin_evidence_invalid")
    claimed = payload.get("evidence_sha256")
    raw = dict(payload)
    raw.pop("evidence_sha256", None)
    if claimed != _canonical_hash(raw):
        raise UserError("kotlin_evidence_hash_invalid")
    return payload


def _status(blocked: list[dict[str, Any]]) -> str:
    kinds = {row["kind"] for row in blocked}
    if any(
        token in kind
        for kind in kinds
        for token in ("refused", "uncertain", "unsupported", "symlink", "requires")
    ):
        return "unsupported"
    if any(token in kind for kind in kinds for token in ("invalid", "failed")):
        return "failed"
    return "partial"


def _report(
    *,
    mode: str,
    status: str,
    plan: dict[str, Any] | None,
    blocked: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    native: dict[str, Any] | None = None,
    classes_before: dict[str, str] | None = None,
    classes_after: dict[str, str] | None = None,
    evidence_sha: str | None = None,
    exact: dict[str, Any] | None = None,
    rolled_back: bool = False,
    rollback_exact: dict[str, Any] | None = None,
    old_identity: list[str] | None = None,
) -> dict[str, Any]:
    before = classes_before or {}
    after = classes_after if classes_after is not None else before
    return {
        "schema": REPORT_SCHEMA,
        "kotlin": {
            "mode": mode,
            "status": status,
            "source": plan["source"] if plan else None,
            "destination": plan["destination"] if plan else None,
            "blocked": blocked,
            "exact_changes": changes,
            "native_preflight" if mode == "dry-run" else "native": native or {},
            "identity_proof": {
                "classes_before": before,
                "classes_after": after,
                "passed": bool(before) and before == after,
            },
            "evidence_sha256": evidence_sha,
            "exact_after_tree": exact or {},
            "old_identity_remaining": old_identity or [],
            "rolled_back": rolled_back,
            "rollback_exact": rollback_exact or {},
        },
    }


def _write_report(report_dir: Path, payload: dict[str, Any]) -> None:
    _atomic_json(report_dir / "report.json", payload)


def run(
    *,
    root: Path,
    plan_path: Path,
    report_dir: Path,
    mode: str,
    evidence_path: Path | None,
    approval: str | None,
) -> tuple[int, dict[str, Any]]:
    report_dir.mkdir(parents=True, exist_ok=True)
    evidence_output = report_dir / "evidence.json"
    try:
        plan = _load_plan(plan_path)
    except UserError as exc:
        evidence_output.unlink(missing_ok=True)
        payload = _report(
            mode=mode,
            status=_status([{"kind": str(exc)}]),
            plan=None,
            blocked=[{"kind": str(exc)}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload

    if mode == "dry-run":
        facts = _analysis(root, report_dir, plan_path, plan)
        if facts["blocked"]:
            evidence_output.unlink(missing_ok=True)
            payload = _report(
                mode=mode,
                status=_status(facts["blocked"]),
                plan=plan,
                blocked=facts["blocked"],
                changes=facts["changes"],
                native=facts.get("native_before"),
                classes_before=facts.get("native_before", {}).get("classes"),
                classes_after=facts.get("native_after", {}).get("classes"),
            )
            _write_report(report_dir, payload)
            return 2, payload
        evidence = _evidence(plan_path, plan, facts)
        _atomic_json(evidence_output, evidence)
        payload = _report(
            mode=mode,
            status="complete",
            plan=plan,
            blocked=[],
            changes=facts["changes"],
            native=facts["native_before"],
            classes_before=facts["native_before"]["classes"],
            classes_after=facts["native_after"]["classes"],
            evidence_sha=evidence["evidence_sha256"],
        )
        _write_report(report_dir, payload)
        return 0, payload

    if evidence_path is None:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": "kotlin_evidence_required"}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload
    try:
        evidence = _load_evidence(evidence_path)
    except UserError as exc:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": str(exc)}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload
    plan_mismatch = (
        evidence.get("plan_sha256") != _sha(plan_path.read_bytes())
        or evidence.get("plan") != plan["raw"]
        or evidence.get("adapter_sha256") != _sha(Path(__file__).read_bytes())
    )

    if mode == "check":
        current = _snapshot(root, report_dir)
        blocked: list[dict[str, Any]] = []
        if plan_mismatch:
            blocked.append({"kind": "kotlin_evidence_plan_mismatch"})
        if _tree_hash(current) != evidence.get("expected_after_tree_sha256"):
            blocked.append({"kind": "kotlin_after_tree_mismatch"})
        old_identity = [
            relative
            for relative in (plan["source"],)
            if (root / relative).exists() or (root / relative).is_symlink()
        ]
        try:
            manifest, _, _ = _manifest(root, plan["manifest"])
            native = _native(root, plan, manifest)
        except UserError as exc:
            blocked.append({"kind": str(exc)})
            native = {}
        if old_identity:
            blocked.append({"kind": "kotlin_old_identity_remaining"})
        if native and (
            not _native_passed(native) or native["classes"] != evidence.get("classes")
        ):
            blocked.append({"kind": "kotlin_native_check_failed"})
        payload = _report(
            mode=mode,
            status="complete" if not blocked else "failed",
            plan=plan,
            blocked=blocked,
            changes=[],
            native=native,
            classes_before=evidence.get("classes"),
            classes_after=native.get("classes") if native else {},
            evidence_sha=evidence.get("evidence_sha256"),
            exact={"passed": not any(row["kind"] == "kotlin_after_tree_mismatch" for row in blocked)},
            old_identity=old_identity,
        )
        _write_report(report_dir, payload)
        return (0 if not blocked else 2), payload

    if approval != evidence.get("evidence_sha256"):
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": "kotlin_evidence_approval_mismatch"}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload
    facts = _analysis(root, report_dir, plan_path, plan)
    current_evidence = _evidence(plan_path, plan, facts) if not facts["blocked"] else None
    if facts["blocked"] or plan_mismatch or current_evidence != evidence:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[*facts["blocked"], {"kind": "kotlin_stale_evidence"}],
            changes=facts["changes"],
            native=facts.get("native_before"),
        )
        _write_report(report_dir, payload)
        return 2, payload

    try:
        _mutate(root, plan, facts["manifest_after"], facts["manifest_mode"])
        manifest, _, _ = _manifest(root, plan["manifest"])
        native = _native(root, plan, manifest)
        current = _snapshot(root, report_dir)
        exact_passed = _tree_hash(current) == evidence["expected_after_tree_sha256"]
        old_identity = [
            plan["source"]
            for _ in (0,)
            if (root / plan["source"]).exists() or (root / plan["source"]).is_symlink()
        ]
        if (
            not _native_passed(native)
            or native["classes"] != evidence["classes"]
            or not exact_passed
            or old_identity
        ):
            raise UserError("kotlin_postflight_failed")
    except (OSError, UserError) as exc:
        _restore(root, report_dir, facts["full"])
        rollback_passed = _tree_hash(_snapshot(root, report_dir)) == _tree_hash(facts["full"])
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": str(exc)}],
            changes=facts["changes"],
            native=locals().get("native", {}),
            classes_before=evidence.get("classes"),
            classes_after=locals().get("native", {}).get("classes", {}),
            rolled_back=True,
            rollback_exact={"passed": rollback_passed},
        )
        _write_report(report_dir, payload)
        return 2, payload
    payload = _report(
        mode=mode,
        status="complete",
        plan=plan,
        blocked=[],
        changes=facts["changes"],
        native=native,
        classes_before=evidence["classes"],
        classes_after=native["classes"],
        evidence_sha=evidence["evidence_sha256"],
        exact={"passed": True, "actual_fingerprint": _tree_hash(current)},
        old_identity=[],
    )
    _write_report(report_dir, payload)
    return 0, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--check", action="store_true")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--approve-evidence-sha256")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
    except (OSError, RuntimeError):
        print("project root is unavailable", file=sys.stderr)
        return 2
    if not root.is_dir() or root.is_symlink():
        print("project root must be a non-symlink directory", file=sys.stderr)
        return 2
    mode = "dry-run" if args.dry_run else "apply" if args.apply else "check"
    code, payload = run(
        root=root,
        plan_path=args.plan.resolve(),
        report_dir=args.report_dir.resolve(),
        mode=mode,
        evidence_path=args.evidence.resolve() if args.evidence else None,
        approval=args.approve_evidence_sha256,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
