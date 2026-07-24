#!/usr/bin/env python3
"""Build exact offline C# semantic facts with SDK-bundled csc and Roslyn."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "csharp-roslyn-semantic-facts-v1"
SDK_VERSION = "10.0.302"
RUNTIME_VERSION = "10.0.10"
TARGET_FRAMEWORK = "net10.0"
DOTNET_SHA256 = "ed8eb05ce0598b40df34f464d16063b30896c7e28dc1ac9e94554a8aff9676ed"
CSC_SHA256 = "c5a2ff87882ad0c1b2e8d554ddf8d9eae1aa5d4d9b659f43a7c28d336ca2ba81"
CODE_ANALYSIS_SHA256 = "eabc44a97ca36c415af0d7a4db353c170fad26da897b11862927bdb3402f3786"
CSHARP_ANALYSIS_SHA256 = "daff05fe558690b194b93e99d1299f2a85afba55c41fba5718dba6bdfd36bfe9"
REFERENCE_PACK_SHA256 = "9719ee9a053103d3de4b3bfb91f230d9a58325f47e7ac90a2147649d288f2fdd"
REFERENCE_COUNT = 167
HELPER_SHA256 = "0475a903da8973491775d627da2ca48c274e0c0684063ec229a26e439f5ed980"
LIMITS = [
    "Complete only for the exact manifest-selected C# sources/tests under .NET SDK 10.0.302, runtime/reference pack 10.0.10, and the pinned SDK-bundled Roslyn assemblies.",
    "Direct csc compilation and Roslyn symbol binding establish selected static declarations, references, overload targets, constructor arguments, and direct assignments; they do not establish runtime reachability or behavior.",
    "Overrides, interface dispatch, delegates, reflection and runtime names, dynamic dispatch, partial declarations, source generators, generated/vendor inputs, analyzers, and external consumers remain review boundaries.",
    "NuGet restore, SDK workloads, solution/project-reference graphs, conditional build variants, framework registration, trimming/AOT, interop, serialization, binary compatibility, and mutation authority are outside this bounded fixture contract.",
]


class ProviderError(RuntimeError):
    """A classified terminal provider state."""

    def __init__(self, status: str, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.kind = kind
        self.detail = detail


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
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


def _safe_output(root: Path, supplied: Path) -> Path:
    output = Path(os.path.abspath(supplied if supplied.is_absolute() else root / supplied))
    allowed = root / "reports" / "csharp-semantic"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must stay beneath reports/csharp-semantic") from exc
    if not relative.parts:
        raise ValueError("output must name a fact-pack file")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output cannot traverse a symbolic link")
    return output


def _safe_relative(raw: object) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ProviderError(
            "failed", "manifest_malformed", "manifest paths must be POSIX strings"
        )
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".cs":
        raise ProviderError(
            "failed", "manifest_malformed", f"unsafe or non-C# path: {raw}"
        )
    return raw


def _manifest(
    root: Path, supplied: Path
) -> tuple[dict[str, Any], Path, list[dict[str, str]]]:
    candidate = supplied if supplied.is_absolute() else root / supplied
    if not candidate.is_file() or candidate.is_symlink():
        raise ProviderError(
            "partial", "manifest_unavailable", "manifest must be a regular project file"
        )
    try:
        path = candidate.resolve(strict=True)
        path.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ProviderError(
            "partial", "manifest_unavailable", "manifest must stay inside project root"
        ) from exc
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProviderError("failed", "manifest_malformed", str(exc)) from exc
    expected = {
        "schema_version",
        "assembly_name",
        "target_framework",
        "sources",
        "tests",
        "excluded",
        "test_main",
        "test_output",
        "smoke_main",
        "smoke_output",
    }
    if not isinstance(raw, dict) or set(raw) != expected or raw["schema_version"] != 1:
        raise ProviderError(
            "failed", "manifest_malformed", "manifest shape or schema is invalid"
        )
    if raw["target_framework"] != TARGET_FRAMEWORK:
        raise ProviderError(
            "partial",
            "target_framework_unsupported",
            f"expected {TARGET_FRAMEWORK}",
        )
    scalar_keys = {"assembly_name", "test_main", "test_output", "smoke_main", "smoke_output"}
    if any(not isinstance(raw[key], str) or not raw[key] for key in scalar_keys):
        raise ProviderError(
            "failed", "manifest_malformed", "manifest scalar fields must be strings"
        )
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", raw["assembly_name"]):
        raise ProviderError("failed", "manifest_malformed", "invalid assembly name")
    try:
        sources = [_safe_relative(value) for value in raw["sources"]]
        tests = [_safe_relative(value) for value in raw["tests"]]
    except TypeError as exc:
        raise ProviderError("failed", "manifest_malformed", str(exc)) from exc
    if not sources or not tests:
        raise ProviderError(
            "failed", "manifest_malformed", "non-empty source and test sets are required"
        )
    excluded: list[dict[str, str]] = []
    if not isinstance(raw["excluded"], list):
        raise ProviderError("failed", "manifest_malformed", "excluded must be a list")
    for row in raw["excluded"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "role"}
            or row["role"] not in {"generated", "vendor"}
        ):
            raise ProviderError("failed", "manifest_malformed", "invalid excluded row")
        excluded.append({"path": _safe_relative(row["path"]), "role": row["role"]})
    all_paths = [*sources, *tests, *(row["path"] for row in excluded)]
    if len(all_paths) != len(set(all_paths)):
        raise ProviderError("failed", "manifest_malformed", "manifest paths must be unique")
    inventory: list[dict[str, str]] = []
    roles = [
        *((relative, "source") for relative in sources),
        *((relative, "test") for relative in tests),
        *((row["path"], row["role"]) for row in excluded),
    ]
    for relative, role in roles:
        candidate = root / relative
        if not candidate.is_file() or candidate.is_symlink():
            raise ProviderError("partial", "manifest_input_unavailable", relative)
        try:
            candidate.resolve().relative_to(root)
        except ValueError as exc:
            raise ProviderError(
                "partial", "manifest_input_unavailable", relative
            ) from exc
        inventory.append(
            {"path": relative, "role": role, "sha256": _sha256(candidate)}
        )
    normalized = {
        **raw,
        "sources": sources,
        "tests": tests,
        "excluded": excluded,
    }
    return normalized, path, inventory


def _run(argv: list[str], root: Path, *, timeout: int = 180) -> dict[str, Any]:
    environment = {
        **os.environ,
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_NOLOGO": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "NUGET_XMLDOC_MODE": "skip",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
    }
    try:
        result = subprocess.run(
            argv,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProviderError("partial", "tool_execution_failed", str(exc)) from exc
    return {
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _resolve_dotnet(supplied: str) -> Path:
    raw = Path(supplied)
    candidate = raw if "/" in supplied else Path(shutil.which(supplied) or "")
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise ProviderError("partial", "dotnet_unavailable", supplied)
    try:
        return candidate.resolve(strict=True)
    except OSError as exc:
        raise ProviderError("partial", "dotnet_unavailable", str(exc)) from exc


def _reference_manifest(path: Path) -> tuple[list[Path], str]:
    references = sorted(path.glob("*.dll"))
    rows = [{"name": item.name, "sha256": _sha256(item)} for item in references]
    return references, _object_hash(rows)


def _toolchain(dotnet_arg: str, root: Path) -> dict[str, Any]:
    dotnet = _resolve_dotnet(dotnet_arg)
    info = _run([str(dotnet), "--info"], root)
    if info["returncode"]:
        raise ProviderError("partial", "dotnet_info_failed", info["stderr"])
    version = _run([str(dotnet), "--version"], root)
    if version["returncode"] or version["stdout"].strip() != SDK_VERSION:
        raise ProviderError(
            "partial",
            "dotnet_sdk_version_mismatch",
            version["stdout"] + version["stderr"],
        )
    base_match = re.search(r"^\s*Base Path:\s*(.+?)\s*$", info["stdout"], re.MULTILINE)
    host_match = re.search(
        r"^Host:\s*\n\s*Version:\s*([^\s]+)", info["stdout"], re.MULTILINE
    )
    if base_match is None or host_match is None:
        raise ProviderError("failed", "dotnet_info_malformed", info["stdout"])
    sdk_base = Path(base_match.group(1)).resolve(strict=True)
    if sdk_base.name != SDK_VERSION or host_match.group(1) != RUNTIME_VERSION:
        raise ProviderError("partial", "dotnet_runtime_mismatch", info["stdout"])
    dotnet_root = sdk_base.parent.parent
    runtime = dotnet_root / "shared" / "Microsoft.NETCore.App" / RUNTIME_VERSION
    reference_dir = (
        dotnet_root
        / "packs"
        / "Microsoft.NETCore.App.Ref"
        / RUNTIME_VERSION
        / "ref"
        / TARGET_FRAMEWORK
    )
    roslyn = sdk_base / "Roslyn" / "bincore"
    selected = {
        "dotnet": dotnet,
        "csc": roslyn / "csc.dll",
        "code_analysis": roslyn / "Microsoft.CodeAnalysis.dll",
        "csharp_analysis": roslyn / "Microsoft.CodeAnalysis.CSharp.dll",
    }
    if not runtime.is_dir() or not reference_dir.is_dir():
        raise ProviderError("partial", "dotnet_reference_pack_unavailable", str(dotnet_root))
    expected_hashes = {
        "dotnet": DOTNET_SHA256,
        "csc": CSC_SHA256,
        "code_analysis": CODE_ANALYSIS_SHA256,
        "csharp_analysis": CSHARP_ANALYSIS_SHA256,
    }
    for name, path in selected.items():
        if not path.is_file() or _sha256(path) != expected_hashes[name]:
            raise ProviderError(
                "partial", f"{name}_hash_mismatch", str(path)
            )
    references, manifest_sha256 = _reference_manifest(reference_dir)
    if len(references) != REFERENCE_COUNT or manifest_sha256 != REFERENCE_PACK_SHA256:
        raise ProviderError(
            "partial", "reference_pack_hash_mismatch", str(reference_dir)
        )
    return {
        "dotnet": str(dotnet),
        "sdk_base": str(sdk_base),
        "runtime_path": str(runtime),
        "reference_dir": str(reference_dir),
        "references": references,
        "paths": selected,
        "evidence": {
            "sdk_version": SDK_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "dotnet": {"path": str(dotnet), "sha256": DOTNET_SHA256},
            "csc": {"path": str(selected["csc"]), "sha256": CSC_SHA256},
            "assemblies": [
                {
                    "path": str(selected["code_analysis"]),
                    "sha256": CODE_ANALYSIS_SHA256,
                },
                {
                    "path": str(selected["csharp_analysis"]),
                    "sha256": CSHARP_ANALYSIS_SHA256,
                },
            ],
            "reference_pack": {
                "path": str(reference_dir),
                "assembly_count": REFERENCE_COUNT,
                "manifest_sha256": REFERENCE_PACK_SHA256,
            },
            "dotnet_info": info,
        },
    }


def _runtime_config() -> dict[str, Any]:
    return {
        "runtimeOptions": {
            "tfm": TARGET_FRAMEWORK,
            "framework": {
                "name": "Microsoft.NETCore.App",
                "version": RUNTIME_VERSION,
            },
            "rollForward": "Disable",
        }
    }


def _write_runtime_config(assembly: Path) -> Path:
    path = assembly.with_suffix(".runtimeconfig.json")
    path.write_text(json.dumps(_runtime_config(), sort_keys=True) + "\n", encoding="utf-8")
    return path


def _compile(
    toolchain: dict[str, Any],
    root: Path,
    sources: list[Path],
    output: Path,
    main: str,
) -> dict[str, Any]:
    references = [f"-r:{path}" for path in toolchain["references"]]
    argv = [
        toolchain["dotnet"],
        str(toolchain["paths"]["csc"]),
        "-nologo",
        "-noconfig",
        "-nostdlib+",
        "-deterministic+",
        "-debug-",
        "-nullable:enable",
        "-warnaserror+",
        "-langversion:14",
        "-target:exe",
        f"-main:{main}",
        f"-out:{output}",
        *references,
        *(str(path) for path in sources),
    ]
    return _run(argv, root)


def _partial(
    root: Path,
    manifest: Path,
    *,
    status: str,
    kind: str,
    detail: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA,
        "language": "csharp",
        "status": status,
        "read_only": True,
        "failure_kind": kind,
        "failure_detail": detail,
        "project_root": str(root),
        "manifest_path": str(manifest),
        "source_inventory": [],
        "declarations": [],
        "calls": [],
        "references": [],
        "writes": [],
        "boundaries": [],
        "limits": LIMITS,
    }
    payload["fact_pack_sha256"] = _object_hash(payload)
    return payload


def _relative_fact_paths(
    root: Path, facts: dict[str, Any], allowed: set[str]
) -> None:
    for group in ("declarations", "calls", "references", "writes", "boundaries", "diagnostics"):
        for row in facts.get(group, []):
            raw = row.get("path")
            if not raw:
                continue
            try:
                relative = Path(raw).resolve().relative_to(root).as_posix()
            except (OSError, ValueError) as exc:
                raise ProviderError(
                    "failed", "helper_output_outside_manifest", str(raw)
                ) from exc
            if relative not in allowed:
                raise ProviderError(
                    "failed", "helper_output_outside_manifest", relative
                )
            row["path"] = relative


def collect(
    *,
    project_root: Path,
    manifest_path: Path,
    output: Path,
    dotnet: str,
) -> tuple[dict[str, Any], int]:
    root = project_root.resolve(strict=True)
    destination = _safe_output(root, output)
    manifest_display = manifest_path if manifest_path.is_absolute() else root / manifest_path
    helper = Path(__file__).with_name("CSharpSemanticFacts.cs")
    try:
        if _sha256(helper) != HELPER_SHA256:
            raise ProviderError("failed", "helper_source_hash_mismatch", str(helper))
        manifest, manifest_file, inventory = _manifest(root, manifest_path)
        tools = _toolchain(dotnet, root)
        sources = [root / relative for relative in manifest["sources"]]
        tests = [root / relative for relative in manifest["tests"]]
        before = {row["path"]: row["sha256"] for row in inventory}
        with tempfile.TemporaryDirectory(prefix="csharp-semantic-") as temporary:
            build = Path(temporary)
            app = build / "app.dll"
            test = build / "tests.dll"
            helper_dll = build / "CSharpSemanticFacts.dll"
            commands = {
                "compile": _compile(
                    tools, root, sources, app, manifest["smoke_main"]
                ),
                "compile_tests": _compile(
                    tools, root, [*sources, *tests], test, manifest["test_main"]
                ),
            }
            if commands["compile"]["returncode"] or commands["compile_tests"]["returncode"]:
                raise ProviderError(
                    "failed",
                    "native_diagnostics_failed",
                    json.dumps(commands, sort_keys=True),
                )
            _write_runtime_config(app)
            _write_runtime_config(test)
            commands["test"] = _run([tools["dotnet"], str(test)], root)
            commands["smoke"] = _run([tools["dotnet"], str(app)], root)
            if (
                commands["test"]["returncode"]
                or commands["test"]["stdout"] != manifest["test_output"]
                or commands["smoke"]["returncode"]
                or commands["smoke"]["stdout"] != manifest["smoke_output"]
            ):
                raise ProviderError(
                    "failed",
                    "native_test_smoke_failed",
                    json.dumps(commands, sort_keys=True),
                )
            helper_references = [
                *(f"-r:{path}" for path in tools["references"]),
                f"-r:{tools['paths']['code_analysis']}",
                f"-r:{tools['paths']['csharp_analysis']}",
            ]
            helper_argv = [
                tools["dotnet"],
                str(tools["paths"]["csc"]),
                "-nologo",
                "-noconfig",
                "-nostdlib+",
                "-deterministic+",
                "-debug-",
                "-nullable:enable",
                "-warnaserror+",
                "-langversion:14",
                "-target:exe",
                "-main:EngineeringSkills.CSharpSemantic.CSharpSemanticFacts",
                f"-out:{helper_dll}",
                *helper_references,
                str(helper),
            ]
            commands["compile_helper"] = _run(helper_argv, root)
            if commands["compile_helper"]["returncode"]:
                raise ProviderError(
                    "failed",
                    "helper_compile_failed",
                    json.dumps(commands["compile_helper"], sort_keys=True),
                )
            _write_runtime_config(helper_dll)
            shutil.copy2(tools["paths"]["code_analysis"], build)
            shutil.copy2(tools["paths"]["csharp_analysis"], build)
            descriptors = [
                f"{row['role']}={root / row['path']}" for row in inventory
            ]
            commands["semantic_read"] = _run(
                [
                    tools["dotnet"],
                    str(helper_dll),
                    tools["reference_dir"],
                    *descriptors,
                ],
                root,
            )
            if commands["semantic_read"]["returncode"]:
                raise ProviderError(
                    "failed",
                    "helper_run_failed",
                    json.dumps(commands["semantic_read"], sort_keys=True),
                )
            try:
                facts = json.loads(commands["semantic_read"]["stdout"])
            except json.JSONDecodeError as exc:
                raise ProviderError("failed", "helper_output_malformed", str(exc)) from exc
        if facts.get("schema_version") != 1:
            raise ProviderError("failed", "helper_output_malformed", "schema mismatch")
        errors = [
            row
            for row in facts.get("diagnostics", [])
            if row.get("severity") == "Error"
        ]
        if errors:
            raise ProviderError(
                "failed", "roslyn_diagnostics_failed", json.dumps(errors, sort_keys=True)
            )
        allowed = {row["path"] for row in inventory}
        _relative_fact_paths(root, facts, allowed)
        current = {row["path"]: _sha256(root / row["path"]) for row in inventory}
        if current != before:
            raise ProviderError(
                "failed",
                "unexpected_source_mutation",
                "a manifest input changed during analysis",
            )
        commands["semantic_read"]["stdout"] = "<fact-json-captured>"
        payload: dict[str, Any] = {
            "schema_version": SCHEMA,
            "language": "csharp",
            "status": "complete",
            "read_only": True,
            "semantic_authority": {
                "kind": "sdk-bundled-roslyn-after-direct-csc-native-gates",
                "sdk_version": SDK_VERSION,
                "runtime_version": RUNTIME_VERSION,
                "helper_sha256": HELPER_SHA256,
                "provider_sha256": _sha256(Path(__file__)),
                "roslyn_assembly": facts.get("roslyn_assembly"),
                "code_analysis_assembly": facts.get("code_analysis_assembly"),
            },
            "project_root": str(root),
            "manifest_path": str(manifest_file),
            "manifest_sha256": _sha256(manifest_file),
            "project_contract_sha256": _object_hash(manifest),
            "manifest": manifest,
            "source_inventory": inventory,
            "source_manifest_sha256": _object_hash(inventory),
            "tools": tools["evidence"],
            "commands": commands,
            "source_preservation": {"unchanged": True},
            "declarations": facts["declarations"],
            "calls": facts["calls"],
            "references": facts["references"],
            "writes": facts["writes"],
            "boundaries": facts["boundaries"],
            "diagnostics": facts["diagnostics"],
            "limits": LIMITS,
        }
        payload["fact_pack_sha256"] = _object_hash(payload)
        _atomic_json(destination, payload)
        return payload, 0
    except ProviderError as exc:
        payload = _partial(
            root,
            manifest_display,
            status=exc.status,
            kind=exc.kind,
            detail=exc.detail,
        )
        _atomic_json(destination, payload)
        return payload, 1 if exc.status == "failed" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=Path("csharp-semantic-project.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/csharp-semantic/facts.json")
    )
    parser.add_argument("--dotnet", default="dotnet")
    args = parser.parse_args()
    try:
        _, returncode = collect(
            project_root=args.project_root,
            manifest_path=args.manifest,
            output=args.output,
            dotnet=args.dotnet,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
