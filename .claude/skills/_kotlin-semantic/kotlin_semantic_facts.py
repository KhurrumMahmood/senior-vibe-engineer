#!/usr/bin/env python3
"""Build a pinned Kotlin/JVM fact pack after native compile/test/smoke gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


KOTLIN_VERSION = "2.4.10"
JVM_TARGET = "17"
COMPILER_SHA256 = "db12b1af0db0e10eeedfc15d5dac0316604e5c556321f60e3bcd73075a66f0a3"
STDLIB_SHA256 = "4ec0293bc3751423b203f1d8493251c57c42e73eb6377a6b8560d0974ff0a6df"
HELPER_SHA256 = "9d00c5690cf0ead2b2b7d2c6a9f2247ac325effd4c2fe00c4f29752d61c56877"
HELPER_MAIN = "engineering.skills.kotlinsemantic.KotlinSemanticFactsKt"
LIMITS = [
    "Pinned to the Homebrew Kotlin/JVM 2.4.10 compiler and stdlib jar hashes; other distributions are partial, not silently accepted.",
    "A successful native K2 compile, test main, and smoke main gates a deprecated K1 compiler-API read. The helper facts are intentionally limited to project declarations, direct selected calls/references, direct property assignments, constructor arguments, explicit overrides, and extensions.",
    "Reflection, callable references, delegated properties, generated/KAPT/KSP sources, compiler plugins, Gradle variants, Java sources, expect/actual, Kotlin scripts, framework registration, and runtime reachability remain pending human evidence.",
    "A resolved overload identifies the selected descriptor signature. Unresolved calls and override/extension boundaries are preserved as uncertainty and never promoted to safe-delete or behavioral-equivalence claims.",
]


class ProviderError(RuntimeError):
    """A classified fail-closed provider boundary."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _safe_relative(raw: object) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ProviderError("manifest-malformed", "manifest paths must be non-empty POSIX strings")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".kt":
        raise ProviderError("manifest-malformed", f"unsafe or non-.kt manifest path: {raw}")
    return raw


def _safe_output(root: Path, supplied: Path) -> Path:
    output = Path(os.path.abspath(supplied if supplied.is_absolute() else root / supplied))
    allowed = root / "reports" / "kotlin-semantic"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ProviderError(
            "unsafe-output", "output must stay beneath reports/kotlin-semantic"
        ) from exc
    current = allowed
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ProviderError("unsafe-output", "output cannot traverse a symbolic link")
    return output


def _run(argv: list[str], cwd: Path, *, timeout: int = 120) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=timeout,
            env={
                **os.environ,
                "http_proxy": "http://127.0.0.1:9",
                "https_proxy": "http://127.0.0.1:9",
                "ALL_PROXY": "http://127.0.0.1:9",
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderError("tool-execution-failed", str(exc)) from exc
    return {
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _manifest(root: Path, path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest_path = path if path.is_absolute() else root / path
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProviderError("manifest-malformed", str(exc)) from exc
    keys = {
        "schema_version",
        "sources",
        "tests",
        "test_main",
        "test_output",
        "smoke_main",
        "smoke_output",
    }
    if not isinstance(raw, dict) or set(raw) != keys or raw["schema_version"] != 1:
        raise ProviderError("manifest-malformed", "manifest shape or schema version is invalid")
    sources = [_safe_relative(item) for item in raw["sources"]]
    tests = [_safe_relative(item) for item in raw["tests"]]
    if not sources or not tests or len(set([*sources, *tests])) != len([*sources, *tests]):
        raise ProviderError(
            "manifest-malformed", "manifest needs unique non-empty source and test sets"
        )
    if not all(isinstance(raw[key], str) for key in keys - {"schema_version", "sources", "tests"}):
        raise ProviderError("manifest-malformed", "manifest main/output fields must be strings")
    rows: list[dict[str, str]] = []
    for role, paths in (("source", sources), ("test", tests)):
        for relative in paths:
            candidate = root / relative
            if not candidate.is_file() or candidate.is_symlink():
                raise ProviderError("manifest-input-unavailable", relative)
            try:
                candidate.resolve().relative_to(root)
            except ValueError as exc:
                raise ProviderError("manifest-input-unavailable", relative) from exc
            rows.append({"path": relative, "role": role, "sha256": _sha256(candidate)})
    normalized = {**raw, "sources": sources, "tests": tests}
    return normalized, rows


def _toolchain(kotlinc: Path, java: Path) -> tuple[Path, Path, dict[str, Any]]:
    try:
        compiler = kotlinc.resolve(strict=True)
        runtime = java.resolve(strict=True)
    except OSError as exc:
        raise ProviderError("toolchain-unavailable", str(exc)) from exc
    version = _run([str(compiler), "-version"], Path.cwd())
    version_text = version["stdout"] + version["stderr"]
    if version["returncode"] != 0 or not re.search(r"kotlinc-jvm 2\.4\.10(?:\s|$)", version_text):
        raise ProviderError("compiler-version-mismatch", version_text.strip())
    java_version = _run([str(runtime), "-version"], Path.cwd())
    java_text = java_version["stdout"] + java_version["stderr"]
    if java_version["returncode"] != 0 or not re.search(r'version "17\.', java_text):
        raise ProviderError("java-version-mismatch", java_text.strip())
    installation = compiler.parent.parent
    lib = installation / "libexec" / "lib"
    compiler_jar = lib / "kotlin-compiler.jar"
    stdlib_jar = lib / "kotlin-stdlib.jar"
    if not compiler_jar.is_file() or _sha256(compiler_jar) != COMPILER_SHA256:
        raise ProviderError("compiler-jar-hash-mismatch", str(compiler_jar))
    if not stdlib_jar.is_file() or _sha256(stdlib_jar) != STDLIB_SHA256:
        raise ProviderError("stdlib-jar-hash-mismatch", str(stdlib_jar))
    return (
        compiler_jar,
        stdlib_jar,
        {
            "kotlinc": str(compiler),
            "java": str(runtime),
            "kotlinc_version": version,
            "java_version": java_version,
            "compiler_jar": {"path": str(compiler_jar), "sha256": COMPILER_SHA256},
            "stdlib_jar": {"path": str(stdlib_jar), "sha256": STDLIB_SHA256},
        },
    )


def _partial(root: Path, manifest_path: Path, kind: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": "kotlin-jvm-semantic-facts-v1",
        "language": "kotlin",
        "status": "partial",
        "read_only": True,
        "failure_kind": kind,
        "failure_detail": detail,
        "project_root": str(root),
        "manifest": str(manifest_path),
        "declarations": [],
        "calls": [],
        "references": [],
        "writes": [],
        "limits": LIMITS,
    }


def collect(
    *,
    project_root: Path,
    manifest_path: Path,
    output: Path,
    kotlinc: Path,
    java: Path,
) -> tuple[dict[str, Any], int]:
    root = project_root.resolve(strict=True)
    destination = _safe_output(root, output)
    helper = Path(__file__).with_name("KotlinSemanticFacts.kt")
    try:
        if _sha256(helper) != HELPER_SHA256:
            raise ProviderError("helper-source-hash-mismatch", str(helper))
        manifest, inputs = _manifest(root, manifest_path)
        compiler_jar, stdlib_jar, tools = _toolchain(kotlinc, java)
        source_paths = [str(root / row["path"]) for row in inputs if row["role"] == "source"]
        test_paths = [str(root / row["path"]) for row in inputs if row["role"] == "test"]
        with tempfile.TemporaryDirectory(prefix="kotlin-semantic-") as temporary:
            build = Path(temporary)
            app_jar = build / "app.jar"
            tests_jar = build / "tests.jar"
            helper_jar = build / "semantic-helper.jar"
            commands = {
                "compile": _run(
                    [
                        str(kotlinc),
                        "-jvm-target",
                        JVM_TARGET,
                        "-Werror",
                        "-d",
                        str(app_jar),
                        *source_paths,
                    ],
                    root,
                ),
                "compile_tests": _run(
                    [
                        str(kotlinc),
                        "-jvm-target",
                        JVM_TARGET,
                        "-Werror",
                        "-d",
                        str(tests_jar),
                        *source_paths,
                        *test_paths,
                    ],
                    root,
                ),
            }
            if commands["compile"]["returncode"] or commands["compile_tests"]["returncode"]:
                raise ProviderError(
                    "native-diagnostics-failed", json.dumps(commands, sort_keys=True)
                )
            classpath = os.pathsep.join((str(tests_jar), str(stdlib_jar)))
            commands["test"] = _run([str(java), "-cp", classpath, manifest["test_main"]], root)
            smoke_cp = os.pathsep.join((str(app_jar), str(stdlib_jar)))
            commands["smoke"] = _run([str(java), "-cp", smoke_cp, manifest["smoke_main"]], root)
            if (
                commands["test"]["returncode"]
                or commands["test"]["stdout"] != manifest["test_output"]
                or commands["smoke"]["returncode"]
                or commands["smoke"]["stdout"] != manifest["smoke_output"]
            ):
                raise ProviderError(
                    "native-test-smoke-failed", json.dumps(commands, sort_keys=True)
                )
            commands["compile_helper"] = _run(
                [
                    str(kotlinc),
                    "-jvm-target",
                    JVM_TARGET,
                    "-Werror",
                    "-cp",
                    str(compiler_jar),
                    "-d",
                    str(helper_jar),
                    str(helper),
                ],
                root,
            )
            if commands["compile_helper"]["returncode"]:
                raise ProviderError(
                    "helper-compile-failed", json.dumps(commands["compile_helper"], sort_keys=True)
                )
            helper_cp = os.pathsep.join((str(helper_jar), str(compiler_jar)))
            commands["semantic_read"] = _run(
                [
                    str(java),
                    "-cp",
                    helper_cp,
                    HELPER_MAIN,
                    str(stdlib_jar),
                    *source_paths,
                    *test_paths,
                ],
                root,
            )
            if commands["semantic_read"]["returncode"]:
                raise ProviderError(
                    "helper-run-failed", json.dumps(commands["semantic_read"], sort_keys=True)
                )
            try:
                facts = json.loads(commands["semantic_read"]["stdout"])
            except json.JSONDecodeError as exc:
                raise ProviderError("helper-output-malformed", str(exc)) from exc
        errors = [row for row in facts.get("diagnostics", []) if row.get("severity") == "ERROR"]
        if errors:
            raise ProviderError("helper-diagnostics-failed", json.dumps(errors, sort_keys=True))
        current = {row["path"]: _sha256(root / row["path"]) for row in inputs}
        if any(current[row["path"]] != row["sha256"] for row in inputs):
            raise ProviderError(
                "unexpected-source-mutation", "a selected Kotlin input changed during analysis"
            )
        by_absolute = {str((root / row["path"]).resolve()): row for row in inputs}
        for group in ("declarations", "calls", "references", "writes"):
            for row in facts.get(group, []):
                inventory = by_absolute.get(row.get("path"))
                if inventory is None:
                    raise ProviderError("helper-output-outside-manifest", str(row.get("path")))
                row["path"] = inventory["path"]
                row["role"] = inventory["role"]
        commands["semantic_read"]["stdout"] = "<fact-json-captured>"
        payload: dict[str, Any] = {
            "schema_version": "kotlin-jvm-semantic-facts-v1",
            "language": "kotlin",
            "status": "complete",
            "read_only": True,
            "semantic_authority": {
                "kind": "pinned-kotlin-compiler-k1-api-after-k2-native-gate",
                "kotlin_version": KOTLIN_VERSION,
                "helper_sha256": HELPER_SHA256,
            },
            "project_root": str(root),
            "manifest": manifest,
            "source_inventory": inputs,
            "source_manifest_sha256": _object_hash(inputs),
            "tools": tools,
            "commands": commands,
            "declarations": facts["declarations"],
            "calls": facts["calls"],
            "references": facts["references"],
            "writes": facts["writes"],
            "diagnostics": facts["diagnostics"],
            "limits": LIMITS,
        }
        payload["fact_pack_sha256"] = _object_hash(payload)
        _atomic(destination, payload)
        return payload, 0
    except ProviderError as exc:
        payload = _partial(root, manifest_path, exc.kind, exc.detail)
        _atomic(destination, payload)
        return payload, 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("kotlin-semantic-project.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/kotlin-semantic/facts.json"))
    parser.add_argument("--kotlinc", type=Path, default=Path("/opt/homebrew/bin/kotlinc"))
    parser.add_argument("--java", type=Path, default=Path("/usr/bin/java"))
    args = parser.parse_args()
    try:
        _, returncode = collect(
            project_root=args.project_root,
            manifest_path=args.manifest,
            output=args.output,
            kotlinc=args.kotlinc,
            java=args.java,
        )
    except (OSError, RuntimeError) as exc:
        parser.error(str(exc))
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
