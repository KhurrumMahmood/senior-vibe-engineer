#!/usr/bin/env python3
"""Produce narrow C# inventory and exact native project-compilation evidence."""
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
import xml.etree.ElementTree as ElementTree
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


sys.dont_write_bytecode = True
LIBRARY_ROOT = Path(__file__).resolve().parent.parent
if str(LIBRARY_ROOT) not in sys.path:
    sys.path.insert(0, str(LIBRARY_ROOT))

from scripts._lib.language_support.lifecycle import (  # noqa: E402
    LifecycleError,
    write_text_atomic,
)
from scripts.source_inventory import build_inventory  # noqa: E402


SCHEMA_VERSION = 1
MINIMUM_DOTNET = (10, 0, 0)
DEFAULT_PROFILES_ROOT = Path(__file__).resolve().parent / "language_profiles"
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
GLOB_MAGIC = frozenset("*?[]")
EXPECTED_PROPERTIES = {
    "OutputType": "Exe",
    "ImplicitUsings": "disable",
    "Nullable": "enable",
    "TreatWarningsAsErrors": "true",
    "EnableDefaultCompileItems": "false",
    "Deterministic": "true",
    "NuGetAudit": "false",
}
CAPABILITIES = {
    "inventory": "available",
    "project_compilation": "unavailable",
    "syntax_facts": "unavailable",
    "semantic_facts": "unavailable",
    "rewrite": "unavailable",
}


class CSharpProjectMissing(ValueError):
    """No root project was available for the bounded foundation."""


class CSharpProjectError(ValueError):
    """Project metadata exceeded or violated the bounded foundation."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version_parts(rendered: str) -> tuple[int, int, int] | None:
    match = VERSION.fullmatch(rendered.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _resolve_dotnet(requested: Path | None) -> Path | None:
    if requested is None:
        raw = shutil.which("dotnet")
        if raw is None:
            return None
        requested = Path(raw)
    try:
        resolved = requested.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        return None
    return resolved


def _probe_dotnet(root: Path, requested: Path | None) -> tuple[dict[str, Any], Path | None]:
    path = _resolve_dotnet(requested)
    if path is None:
        return {
            "status": "missing",
            "path": None,
            "version": None,
            "minimum_version": "10.0.0",
        }, None
    completed = _run([str(path), "--version"], root, timeout=15)
    version = _version_parts(completed.stdout)
    if completed.returncode != 0 or version is None:
        return {
            "status": "unusable",
            "path": str(path),
            "version": None,
            "minimum_version": "10.0.0",
            "detail": (completed.stderr or completed.stdout).strip()[:1000],
        }, None
    rendered = ".".join(str(part) for part in version)
    if version < MINIMUM_DOTNET:
        return {
            "status": "too-old",
            "path": str(path),
            "version": rendered,
            "minimum_version": "10.0.0",
        }, None
    return {
        "status": "available",
        "path": str(path),
        "version": rendered,
        "minimum_version": "10.0.0",
    }, path


def _safe_compile_item(raw: object) -> str:
    if (
        not isinstance(raw, str)
        or not raw
        or "\\" in raw
        or any(character in raw for character in GLOB_MAGIC)
    ):
        raise CSharpProjectError("Compile Include values must be exact relative paths")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or raw in {"", "."}:
        raise CSharpProjectError("Compile Include values must stay inside the project")
    if path.suffix != ".cs":
        raise CSharpProjectError("Compile Include values must use exact lowercase .cs")
    return raw


def _load_global_json(root: Path) -> dict[str, Any]:
    path = root / "global.json"
    if not path.is_file() or path.is_symlink():
        raise CSharpProjectError("global.json is required and must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CSharpProjectError("global.json is malformed") from exc
    expected = {"version", "rollForward", "allowPrerelease"}
    if not isinstance(payload, dict) or set(payload) != {"sdk"}:
        raise CSharpProjectError("global.json must contain only the sdk contract")
    sdk = payload["sdk"]
    if not isinstance(sdk, dict) or set(sdk) != expected:
        raise CSharpProjectError("global.json sdk has an unexpected shape")
    version = _version_parts(sdk["version"]) if isinstance(sdk["version"], str) else None
    if (
        version is None
        or version[0] != 10
        or sdk["rollForward"] != "disable"
        or sdk["allowPrerelease"] is not False
    ):
        raise CSharpProjectError("global.json must pin a stable .NET 10 SDK exactly")
    return {
        "path": "global.json",
        "sha256": _sha256(path),
        "sdk_version": sdk["version"],
        "roll_forward": sdk["rollForward"],
        "allow_prerelease": sdk["allowPrerelease"],
    }


def _parse_xml(path: Path, *, label: str) -> ElementTree.Element:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CSharpProjectError(f"{label} is unreadable") from exc
    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
        raise CSharpProjectError(f"{label} may not contain a DTD or entity")
    try:
        return ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise CSharpProjectError(f"{label} is malformed XML") from exc


def _load_nuget_config(root: Path) -> dict[str, Any]:
    path = root / "NuGet.Config"
    if not path.is_file() or path.is_symlink():
        raise CSharpProjectError("NuGet.Config is required and must be a regular file")
    document = _parse_xml(path, label="NuGet.Config")
    children = list(document)
    if (
        document.tag != "configuration"
        or document.attrib
        or len(children) != 1
        or children[0].tag != "packageSources"
        or children[0].attrib
    ):
        raise CSharpProjectError("NuGet.Config must contain only packageSources")
    sources = list(children[0])
    if len(sources) != 1 or sources[0].tag != "clear" or sources[0].attrib:
        raise CSharpProjectError("NuGet.Config packageSources must contain only clear")
    return {
        "path": "NuGet.Config",
        "sha256": _sha256(path),
        "package_sources": "cleared",
    }


def _load_project(
    root: Path,
    inventory: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    candidates = [
        path for path in sorted(root.glob("*.csproj"))
        if path.is_file() and not path.is_symlink()
    ]
    if not candidates:
        raise CSharpProjectMissing("no root .csproj is available")
    if len(candidates) != 1:
        raise CSharpProjectError("exactly one root .csproj is required")
    project = candidates[0]
    global_json = _load_global_json(root)
    sdk_version = _version_parts(global_json["sdk_version"])
    assert sdk_version is not None
    expected_properties = {
        **EXPECTED_PROPERTIES,
        "TargetFramework": f"net{sdk_version[0]}.0",
    }
    document = _parse_xml(project, label=project.name)
    if document.tag != "Project" or document.attrib != {"Sdk": "Microsoft.NET.Sdk"}:
        raise CSharpProjectError("the project must use only Microsoft.NET.Sdk")
    properties: dict[str, str] = {}
    compile_items: list[str] = []
    for group in document:
        if group.tag == "PropertyGroup" and not group.attrib:
            for element in group:
                if element.attrib or list(element) or element.tag in properties:
                    raise CSharpProjectError("project properties must be unique scalar values")
                properties[element.tag] = (element.text or "").strip()
        elif group.tag == "ItemGroup" and not group.attrib:
            for element in group:
                if (
                    element.tag != "Compile"
                    or set(element.attrib) != {"Include"}
                    or list(element)
                ):
                    raise CSharpProjectError("only exact Compile Include items are supported")
                compile_items.append(_safe_compile_item(element.attrib["Include"]))
        else:
            raise CSharpProjectError("only unconditional PropertyGroup and ItemGroup are supported")
    if properties != expected_properties:
        raise CSharpProjectError("the project must declare the exact property set")
    if not compile_items or len(compile_items) != len(set(compile_items)):
        raise CSharpProjectError("the project must declare unique compile items")
    roles = {
        row["path"]: row["role"]
        for row in inventory["files"]
        if row["language"] == "csharp" and row["classification"] == "classified"
    }
    expected = {path for path, role in roles.items() if role in {"source", "test"}}
    if set(compile_items) != expected:
        raise CSharpProjectError(
            "Compile Include items must exactly cover first-party source and test files"
        )
    for relative in compile_items:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise CSharpProjectError(f"compile item is unavailable: {relative}")
    nuget = _load_nuget_config(root)
    evidence = {
        "status": "valid",
        "path": project.name,
        "sha256": _sha256(project),
        "sdk": document.attrib["Sdk"],
        "target_framework": properties["TargetFramework"],
        "output_type": properties["OutputType"],
        "properties": properties,
        "compile_items": compile_items,
        "global_json": global_json,
        "nuget_config": nuget,
    }
    return evidence, compile_items


def _relevant_hashes(root: Path, inventory: dict[str, Any]) -> dict[str, str]:
    paths = {
        row["path"]
        for row in inventory["files"]
        if row["language"] == "csharp"
    }
    paths.update(
        path.relative_to(root).as_posix()
        for path in root.glob("*.csproj")
        if path.is_file() and not path.is_symlink()
    )
    paths.update(name for name in ("global.json", "NuGet.Config") if (root / name).is_file())
    return {
        relative: _sha256(root / relative)
        for relative in sorted(paths)
        if (root / relative).is_file() and not (root / relative).is_symlink()
    }


def _manifest_sha256(rows: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for relative, file_digest in sorted(rows.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _base_payload(
    root: Path,
    inventory: dict[str, Any],
    before: dict[str, str],
    tool: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "language": "csharp",
        "status": "failed",
        "outcome": "native-check-failure",
        "failure_kind": "unknown",
        "project_root": str(root),
        "tool": tool,
        "capabilities": dict(CAPABILITIES),
        "inventory": inventory,
        "project_evidence": {"status": "not-inspected"},
        "native": {
            name: {"status": "not-run"}
            for name in ("restore", "build", "test", "smoke")
        },
        "source_manifest": {
            "before": before,
            "before_sha256": _manifest_sha256(before),
            "after": None,
            "after_sha256": None,
            "preserved": False,
        },
        "limits": [
            "One root SDK-style project with exact explicit Compile items is supported.",
            "Roslyn compilation is observed through MSBuild; syntax and semantic APIs are not consumed.",
            "Solutions, packages, project references, generators, analyzers, workloads, and rewrites are unsupported.",
        ],
    }


def _record(
    argv: list[str],
    completed: subprocess.CompletedProcess[str],
    *,
    temporary: Path,
) -> dict[str, Any]:
    marker = "$EPHEMERAL_ROOT"
    rendered_argv = [token.replace(str(temporary), marker) for token in argv]
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "argv": rendered_argv,
        "cwd": "$EPHEMERAL_ROOT/project",
        "returncode": completed.returncode,
        "stdout": completed.stdout[:8000],
        "stderr": completed.stderr[:8000],
    }


def _native_checks(
    root: Path,
    dotnet: Path,
    project: dict[str, Any],
    compile_items: list[str],
) -> tuple[dict[str, Any], str | None]:
    native = {name: {"status": "not-run"} for name in ("restore", "build", "test", "smoke")}
    with tempfile.TemporaryDirectory(prefix="csharp-foundation-") as temporary_raw:
        temporary = Path(temporary_raw)
        working = temporary / "project"
        working.mkdir()
        copied = [
            project["path"],
            project["global_json"]["path"],
            project["nuget_config"]["path"],
            *compile_items,
        ]
        for relative in copied:
            destination = working / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, destination)
        env = {
            **os.environ,
            "ALL_PROXY": "http://127.0.0.1:9",
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
            "DOTNET_CLI_HOME": str(temporary / "dotnet-home"),
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "DOTNET_MULTILEVEL_LOOKUP": "0",
            "DOTNET_NOLOGO": "1",
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
            "NUGET_PACKAGES": str(temporary / "packages"),
        }
        restore = [
            str(dotnet),
            "restore",
            project["path"],
            "--configfile",
            project["nuget_config"]["path"],
            "--packages",
            str(temporary / "packages"),
            "--ignore-failed-sources",
            "--nologo",
        ]
        restored = _run(restore, working, env=env)
        native["restore"] = _record(restore, restored, temporary=temporary)
        if restored.returncode:
            return native, "dotnet-restore-failed"
        build = [
            str(dotnet),
            "build",
            project["path"],
            "--no-restore",
            "--configuration",
            "Release",
            "--nologo",
            "--verbosity",
            "minimal",
        ]
        built = _run(build, working, env=env)
        native["build"] = _record(build, built, temporary=temporary)
        if built.returncode:
            return native, "dotnet-build-failed"
        output = (
            working
            / "bin"
            / "Release"
            / project["target_framework"]
            / f"{Path(project['path']).stem}.dll"
        )
        if not output.is_file():
            return native, "dotnet-build-output-missing"
        native["build"]["output"] = {
            "path": output.relative_to(working).as_posix(),
            "sha256": _sha256(output),
        }
        test = [
            str(dotnet),
            "run",
            "--project",
            project["path"],
            "--configuration",
            "Release",
            "--no-build",
            "--no-restore",
            "--",
            "--self-test",
        ]
        tested = _run(test, working, env=env)
        native["test"] = _record(test, tested, temporary=temporary)
        if tested.returncode or tested.stdout != "csharp-foundation-tests:ok\n":
            return native, "dotnet-native-test-failed"
        smoke = [
            str(dotnet),
            "run",
            "--project",
            project["path"],
            "--configuration",
            "Release",
            "--no-build",
            "--no-restore",
        ]
        smoked = _run(smoke, working, env=env)
        native["smoke"] = _record(smoke, smoked, temporary=temporary)
        if smoked.returncode or smoked.stdout != "invoice:INV-42:125:csharp\n":
            return native, "dotnet-smoke-failed"
    return native, None


def _finish(
    payload: dict[str, Any],
    root: Path,
    profiles_root: Path,
    before: dict[str, str],
) -> tuple[dict[str, Any], int]:
    after_inventory = build_inventory(root, [], profiles_root)
    after = _relevant_hashes(root, after_inventory)
    payload["inventory"] = after_inventory
    payload["source_manifest"].update(
        after=after,
        after_sha256=_manifest_sha256(after),
        preserved=before == after,
    )
    if before != after:
        payload.update(
            status="failed",
            outcome="unexpected-source-mutation",
            failure_kind="unexpected-source-mutation",
        )
    return payload, 2 if payload["status"] == "failed" else 0


def produce(
    project_root: Path,
    *,
    dotnet: Path | None,
    profiles_root: Path = DEFAULT_PROFILES_ROOT,
) -> tuple[dict[str, Any], int]:
    try:
        root = project_root.resolve(strict=True)
    except (OSError, RuntimeError):
        root = project_root.resolve(strict=False)
        return {
            "schema_version": SCHEMA_VERSION,
            "language": "csharp",
            "status": "failed",
            "outcome": "native-check-failure",
            "failure_kind": "project-root-invalid",
            "project_root": str(root),
        }, 2
    if not root.is_dir() or root.is_symlink():
        return {
            "schema_version": SCHEMA_VERSION,
            "language": "csharp",
            "status": "failed",
            "outcome": "native-check-failure",
            "failure_kind": "project-root-invalid",
            "project_root": str(root),
        }, 2
    inventory = build_inventory(root, [], profiles_root)
    before = _relevant_hashes(root, inventory)
    tool, dotnet_path = _probe_dotnet(root, dotnet)
    payload = _base_payload(root, inventory, before, tool)
    if dotnet_path is None:
        state = tool["status"]
        failure = "dotnet-tool-missing" if state == "missing" else f"dotnet-tool-{state}"
        outcome = "tool-missing" if state == "missing" else "unsupported"
        payload.update(status="unsupported", outcome=outcome, failure_kind=failure)
        return _finish(payload, root, profiles_root, before)
    try:
        project, compile_items = _load_project(root, inventory)
    except CSharpProjectMissing as exc:
        payload.update(
            status="partial",
            outcome="partial",
            failure_kind="csharp-project-missing",
            detail=str(exc),
        )
        payload["project_evidence"] = {"status": "missing"}
        return _finish(payload, root, profiles_root, before)
    except CSharpProjectError as exc:
        payload.update(
            status="failed",
            outcome="native-check-failure",
            failure_kind="csharp-project-invalid",
            detail=str(exc),
        )
        payload["project_evidence"] = {"status": "invalid", "detail": str(exc)}
        return _finish(payload, root, profiles_root, before)
    payload["project_evidence"] = project
    if tool["version"] != project["global_json"]["sdk_version"]:
        payload.update(
            status="unsupported",
            outcome="unsupported",
            failure_kind="dotnet-sdk-mismatch",
            detail="resolved dotnet SDK does not match global.json",
        )
        return _finish(payload, root, profiles_root, before)
    payload["capabilities"]["project_compilation"] = "available"
    native, failure = _native_checks(root, dotnet_path, project, compile_items)
    payload["native"] = native
    if failure is None:
        payload.update(status="complete", outcome="complete", failure_kind="none")
    else:
        payload.update(
            status="failed",
            outcome="syntax-error" if failure == "dotnet-build-failed" else "native-check-failure",
            failure_kind=failure,
        )
    return _finish(payload, root, profiles_root, before)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--profiles-root", type=Path, default=DEFAULT_PROFILES_ROOT)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        output = args.output.resolve(strict=False)
        if not root.is_dir() or root.is_symlink() or not _inside(output, root):
            raise LifecycleError("output must stay inside a regular project root")
        if output.is_symlink() or output.is_dir():
            raise LifecycleError("output must be a non-symlink file path")
        protected = {"global.json", "NuGet.Config"}
        if output.suffix in {".cs", ".csproj"} or output.name in protected:
            raise LifecycleError("output may not replace C# project inputs")
        output.unlink(missing_ok=True)
        payload, code = produce(
            root,
            dotnet=args.dotnet,
            profiles_root=args.profiles_root,
        )
        write_text_atomic(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except (LifecycleError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
