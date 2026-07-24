#!/usr/bin/env python3
"""Move one C# implementation file with reviewed, content-addressed authority.

This copied closure intentionally supports only one strict dependency-free
``net10.0`` executable project.  It changes a source location and the matching
explicit ``Compile Include`` while preserving source bytes, filename,
namespace, type identity, and assembly identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


sys.dont_write_bytecode = True
SCHEMA_VERSION = 1
GLOB_MAGIC = frozenset("*?[]")
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
NAMESPACE = re.compile(
    r"(?m)^\s*namespace\s+(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*;\s*$"
)
TYPE_DECLARATION = re.compile(
    r"(?m)^\s*(?P<modifiers>(?:(?:public|internal|protected|private|abstract|"
    r"sealed|static|partial|readonly|ref|file|unsafe|new)\s+)*)"
    r"(?P<kind>record(?:\s+(?:class|struct))?|class|struct|interface|enum)\s+"
    r"(?P<name>[A-Za-z_]\w*)\b"
)
EXPECTED_PROPERTIES = {
    "OutputType": "Exe",
    "TargetFramework": "net10.0",
    "ImplicitUsings": "disable",
    "Nullable": "enable",
    "TreatWarningsAsErrors": "true",
    "EnableDefaultCompileItems": "false",
    "Deterministic": "true",
    "NuGetAudit": "false",
}
CSHARP_KEYS = {
    "dotnet",
    "project",
    "sdk_version",
    "assembly_name",
    "namespace",
    "type_identity",
    "artifact_scope",
    "external_consumers",
    "native_test_expected_stdout",
    "smoke_expected_stdout",
}
EXCLUDED_CSHARP_PARTS = {
    "generated",
    "vendor",
    "build",
    "tools",
    "tooling",
    "obj",
    "bin",
}
REFLECTION_TOKENS = (
    b"Type.GetType",
    b"Assembly.GetType",
    b"Activator.CreateInstance",
    b"System.Reflection",
    b"GetCustomAttribute",
)
PATH_TOKENS = (
    b"System.IO.Path",
    b"Path.",
    b"System.IO.File",
    b"File.",
    b"Directory.",
)
RESOURCE_TOKENS = (
    b"GetManifestResourceStream",
    b"ResourceManager",
    b"EmbeddedResource",
    b".resx",
)
ABI_TOKENS = (
    b"DllImport",
    b"LibraryImport",
    b"UnmanagedCallersOnly",
    b"ComVisible",
    b"extern ",
    b"unsafe ",
)


class MoveFailure(Exception):
    """A bounded refusal or failed proof with a stable machine kind."""

    def __init__(
        self,
        kind: str,
        detail: str,
        *,
        status: str = "partial",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.status = status
        self.extra = extra or {}


class NativeFailure(MoveFailure):
    """A native boundary failed with its complete command evidence."""


@dataclass(frozen=True)
class TreeEntry:
    kind: str
    data: bytes | str
    mode: int


@dataclass(frozen=True)
class Context:
    root: Path
    plan_path: Path
    plan_relative: str
    report_dir: Path
    report_relative: str
    evidence_path: Path
    report_path: Path


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(raw: object, *, label: str, suffix: str | None = None) -> str:
    if (
        not isinstance(raw, str)
        or not raw
        or "\\" in raw
        or any(character in raw for character in GLOB_MAGIC)
    ):
        raise MoveFailure("csharp_plan_invalid", f"{label} must be an exact POSIX path")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or raw in {"", "."}:
        raise MoveFailure("csharp_plan_invalid", f"{label} must stay inside the project")
    if suffix is not None and path.suffix != suffix:
        raise MoveFailure("csharp_plan_invalid", f"{label} must use {suffix}")
    return raw


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _has_symlink_ancestor(path: Path, root: Path) -> bool:
    current = path
    while current != root:
        if current.exists() and current.is_symlink():
            return True
        current = current.parent
    return root.is_symlink()


def _context(args: argparse.Namespace) -> Context:
    try:
        root = args.project_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MoveFailure("csharp_project_root_invalid", str(exc), status="failed") from exc
    if not root.is_dir() or root.is_symlink():
        raise MoveFailure(
            "csharp_project_root_invalid",
            "project root must be a regular directory",
            status="failed",
        )
    try:
        plan_path = args.plan.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MoveFailure("csharp_plan_invalid", str(exc), status="failed") from exc
    if (
        not plan_path.is_file()
        or plan_path.is_symlink()
        or not _inside(plan_path, root)
        or _has_symlink_ancestor(plan_path, root)
    ):
        raise MoveFailure(
            "csharp_plan_invalid",
            "plan must be a regular file inside the project root",
            status="failed",
        )
    report_dir = args.report_dir.resolve(strict=False)
    if not _inside(report_dir, root) or report_dir == root:
        raise MoveFailure(
            "csharp_report_path_invalid",
            "report directory must stay below the project root",
            status="failed",
        )
    if report_dir.exists() and (report_dir.is_symlink() or not report_dir.is_dir()):
        raise MoveFailure(
            "csharp_report_path_invalid",
            "report path must be a non-symlink directory",
            status="failed",
        )
    if _has_symlink_ancestor(report_dir, root):
        raise MoveFailure(
            "csharp_report_path_invalid",
            "report path may not cross a symlink",
            status="failed",
        )
    relative = report_dir.relative_to(root).as_posix()
    return Context(
        root=root,
        plan_path=plan_path,
        plan_relative=plan_path.relative_to(root).as_posix(),
        report_dir=report_dir,
        report_relative=relative,
        evidence_path=report_dir / "evidence.json",
        report_path=report_dir / "report.json",
    )


def _write_bytes_atomic(path: Path, data: bytes, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_bytes_atomic(
        path,
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n",
        mode=0o644,
    )


def _is_report_path(relative: str, report_relative: str) -> bool:
    return relative == report_relative or relative.startswith(report_relative + "/")


def _capture_tree(root: Path, report_relative: str) -> dict[str, TreeEntry]:
    rows: dict[str, TreeEntry] = {}

    def visit(directory: Path, prefix: PurePosixPath) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda row: row.name)
        except OSError as exc:
            raise MoveFailure("csharp_tree_unreadable", str(exc), status="failed") from exc
        for child in children:
            relative_path = prefix / child.name
            relative = relative_path.as_posix()
            if relative_path.parts[0] == ".git" or _is_report_path(
                relative, report_relative
            ):
                continue
            try:
                metadata = child.stat(follow_symlinks=False)
                mode = stat.S_IMODE(metadata.st_mode)
                if child.is_symlink():
                    rows[relative] = TreeEntry("link", os.readlink(child.path), mode)
                elif child.is_file(follow_symlinks=False):
                    rows[relative] = TreeEntry(
                        "file", Path(child.path).read_bytes(), mode
                    )
                elif child.is_dir(follow_symlinks=False):
                    visit(Path(child.path), relative_path)
                else:
                    raise MoveFailure(
                        "csharp_special_file_unsupported",
                        f"special filesystem entry is unsupported: {relative}",
                    )
            except OSError as exc:
                raise MoveFailure("csharp_tree_unreadable", str(exc), status="failed") from exc

    visit(root, PurePosixPath())
    return rows


def _tree_manifest(rows: dict[str, TreeEntry]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for relative, entry in sorted(rows.items()):
        row: dict[str, Any] = {
            "path": relative,
            "kind": entry.kind,
            "mode": entry.mode,
        }
        if entry.kind == "file":
            assert isinstance(entry.data, bytes)
            row.update(size=len(entry.data), sha256=_sha256_bytes(entry.data))
        else:
            assert isinstance(entry.data, str)
            row["target"] = entry.data
        manifest.append(row)
    return manifest


def _tree_fingerprint(rows: dict[str, TreeEntry]) -> str:
    digest = hashlib.sha256()
    for relative, entry in sorted(rows.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry.kind.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(entry.mode).encode("ascii"))
        digest.update(b"\0")
        if isinstance(entry.data, bytes):
            digest.update(entry.data)
        else:
            digest.update(entry.data.encode("utf-8", "surrogateescape"))
        digest.update(b"\n")
    return digest.hexdigest()


def _materialize(rows: dict[str, TreeEntry], root: Path) -> None:
    for relative, entry in sorted(rows.items()):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if entry.kind == "file":
            assert isinstance(entry.data, bytes)
            destination.write_bytes(entry.data)
            destination.chmod(entry.mode)
        else:
            assert isinstance(entry.data, str)
            destination.symlink_to(entry.data)


def _clear_tree(root: Path, report_relative: str) -> None:
    report_parts = PurePosixPath(report_relative).parts
    for path in sorted(root.rglob("*"), key=lambda row: len(row.parts), reverse=True):
        relative = path.relative_to(root)
        rendered = relative.as_posix()
        if relative.parts and relative.parts[0] == ".git":
            continue
        if _is_report_path(rendered, report_relative):
            continue
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
            continue
        if path.is_dir() and tuple(relative.parts) != report_parts[: len(relative.parts)]:
            try:
                path.rmdir()
            except OSError:
                pass


def _restore_tree(root: Path, report_relative: str, rows: dict[str, TreeEntry]) -> None:
    _clear_tree(root, report_relative)
    _materialize(rows, root)


def _load_plan(context: Context) -> dict[str, Any]:
    try:
        raw = context.plan_path.read_bytes()
        plan = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MoveFailure("csharp_plan_invalid", f"plan is invalid JSON: {exc}") from exc
    if not isinstance(plan, dict) or set(plan) != {
        "version",
        "moves",
        "rewrite",
        "csharp",
    }:
        raise MoveFailure("csharp_plan_invalid", "plan must contain only the C# v1 keys")
    if plan["version"] != 1:
        raise MoveFailure("csharp_plan_invalid", "plan version must be 1")
    moves = plan["moves"]
    if not isinstance(moves, list) or len(moves) != 1:
        raise MoveFailure(
            "csharp_move_scope_unsupported", "exactly one file move is required"
        )
    move = moves[0]
    if not isinstance(move, dict) or set(move) != {"from", "to", "mode"}:
        raise MoveFailure(
            "csharp_move_scope_unsupported", "move must contain from, to, and mode"
        )
    if move["mode"] != "file":
        raise MoveFailure(
            "csharp_move_scope_unsupported", "directory moves are unsupported"
        )
    source = _safe_relative(move["from"], label="moves.from", suffix=".cs")
    destination = _safe_relative(move["to"], label="moves.to", suffix=".cs")
    if source == destination:
        raise MoveFailure("csharp_move_scope_unsupported", "move paths must differ")
    if PurePosixPath(source).name != PurePosixPath(destination).name:
        raise MoveFailure(
            "csharp_filename_identity_change", "source and destination filenames must match"
        )
    if plan["rewrite"] != {"code_imports": "update-csharp-project"}:
        raise MoveFailure(
            "csharp_plan_invalid", "rewrite must select update-csharp-project"
        )
    config = plan["csharp"]
    if not isinstance(config, dict) or set(config) != CSHARP_KEYS:
        raise MoveFailure(
            "csharp_plan_invalid", "csharp must contain the exact bounded contract"
        )
    for key in (
        "project",
        "sdk_version",
        "assembly_name",
        "namespace",
        "type_identity",
        "artifact_scope",
        "external_consumers",
        "native_test_expected_stdout",
        "smoke_expected_stdout",
    ):
        if not isinstance(config[key], str) or not config[key]:
            raise MoveFailure("csharp_plan_invalid", f"csharp.{key} must be a string")
    _safe_relative(config["project"], label="csharp.project", suffix=".csproj")
    if PurePosixPath(config["project"]).parent != PurePosixPath("."):
        raise MoveFailure("csharp_plan_invalid", "project must be a root .csproj")
    if VERSION.fullmatch(config["sdk_version"]) is None or not config[
        "sdk_version"
    ].startswith("10."):
        raise MoveFailure("csharp_plan_invalid", "sdk_version must pin .NET 10")
    if config["artifact_scope"] != "closed-executable" or config[
        "external_consumers"
    ] != "none":
        raise MoveFailure(
            "csharp_public_api_unsupported",
            "only a closed executable with no external consumers is supported",
        )
    if not Path(config["dotnet"]).is_absolute():
        raise MoveFailure("csharp_plan_invalid", "csharp.dotnet must be absolute")
    return plan


def _parse_xml(path: Path, *, label: str) -> ElementTree.Element:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise MoveFailure("csharp_project_invalid", f"{label} is unreadable") from exc
    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
        raise MoveFailure("csharp_project_invalid", f"{label} may not contain entities")
    try:
        return ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise MoveFailure("csharp_project_invalid", f"{label} is malformed XML") from exc


def _validate_global_json(root: Path, config: dict[str, str]) -> dict[str, Any]:
    path = root / "global.json"
    if not path.is_file() or path.is_symlink():
        raise MoveFailure("csharp_project_invalid", "global.json must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MoveFailure("csharp_project_invalid", "global.json is malformed") from exc
    expected = {
        "sdk": {
            "version": config["sdk_version"],
            "rollForward": "disable",
            "allowPrerelease": False,
        }
    }
    if payload != expected:
        raise MoveFailure(
            "csharp_project_invalid", "global.json must exactly pin the reviewed SDK"
        )
    return {"path": "global.json", "sha256": _sha256_path(path), **payload["sdk"]}


def _validate_nuget(root: Path) -> dict[str, Any]:
    path = root / "NuGet.Config"
    if not path.is_file() or path.is_symlink():
        raise MoveFailure("csharp_project_invalid", "NuGet.Config must be a regular file")
    document = _parse_xml(path, label="NuGet.Config")
    children = list(document)
    if (
        document.tag != "configuration"
        or document.attrib
        or len(children) != 1
        or children[0].tag != "packageSources"
        or children[0].attrib
    ):
        raise MoveFailure(
            "csharp_project_dependency_unsupported",
            "NuGet.Config must contain only packageSources",
        )
    sources = list(children[0])
    if (
        len(sources) != 1
        or sources[0].tag != "clear"
        or sources[0].attrib
        or list(sources[0])
    ):
        raise MoveFailure(
            "csharp_project_dependency_unsupported",
            "NuGet.Config must clear every package source",
        )
    return {"path": "NuGet.Config", "sha256": _sha256_path(path), "sources": []}


def _role(relative: str) -> str:
    parts = PurePosixPath(relative).parts
    if any(part.lower() in EXCLUDED_CSHARP_PARTS for part in parts[:-1]):
        return "excluded"
    if parts and parts[0] == "src":
        return "source"
    if parts and parts[0] == "tests":
        return "test"
    return "unknown"


def _csharp_inventory(
    root: Path,
    rows: dict[str, TreeEntry],
) -> tuple[dict[str, str], list[str]]:
    roles: dict[str, str] = {}
    for relative, entry in rows.items():
        suffix = PurePosixPath(relative).suffix
        if suffix in {".csx", ".fs", ".fsx", ".vb"}:
            raise MoveFailure(
                "csharp_project_source_closure_mismatch",
                f"mixed or script source is unsupported: {relative}",
            )
        if suffix != ".cs":
            continue
        if entry.kind != "file":
            raise MoveFailure(
                "csharp_symlink_source_unsupported",
                f"C# source may not be a symlink: {relative}",
            )
        role = _role(relative)
        roles[relative] = role
        if role == "unknown":
            raise MoveFailure(
                "csharp_project_source_closure_mismatch",
                f"C# source has no supported role: {relative}",
            )
        if role in {"source", "test"}:
            assert isinstance(entry.data, bytes)
            lower = entry.data.lower()
            if b"<auto-generated" in lower or b"generated code" in lower:
                raise MoveFailure(
                    "csharp_generated_source_unsupported",
                    f"compiled generated source is unsupported: {relative}",
                )
    authored = sorted(
        relative for relative, role in roles.items() if role in {"source", "test"}
    )
    return roles, authored


def _validate_project_graph(root: Path, rows: dict[str, TreeEntry], project: str) -> None:
    projects = sorted(
        relative for relative in rows if PurePosixPath(relative).suffix == ".csproj"
    )
    if projects != [project]:
        raise MoveFailure(
            "csharp_project_graph_ambiguous",
            "exactly the reviewed root project may exist",
        )
    ambiguous_suffixes = {".sln", ".slnx", ".props", ".targets"}
    ambiguous_names = {
        "Directory.Build.props",
        "Directory.Build.targets",
        "Directory.Packages.props",
        "packages.lock.json",
    }
    ambiguous = [
        relative
        for relative in rows
        if PurePosixPath(relative).suffix in ambiguous_suffixes
        or PurePosixPath(relative).name in ambiguous_names
        or relative == ".config/dotnet-tools.json"
    ]
    if ambiguous:
        raise MoveFailure(
            "csharp_project_graph_ambiguous",
            f"solution, graph, or imported build metadata is unsupported: {ambiguous[0]}",
        )


def _validate_project(
    root: Path,
    rows: dict[str, TreeEntry],
    config: dict[str, str],
    authored: list[str],
) -> dict[str, Any]:
    project_relative = config["project"]
    _validate_project_graph(root, rows, project_relative)
    project = root / project_relative
    if not project.is_file() or project.is_symlink():
        raise MoveFailure("csharp_project_invalid", "project must be a regular file")
    document = _parse_xml(project, label=project_relative)
    if document.tag != "Project" or document.attrib != {"Sdk": "Microsoft.NET.Sdk"}:
        raise MoveFailure(
            "csharp_project_dependency_unsupported",
            "only Microsoft.NET.Sdk is supported",
        )
    properties: dict[str, str] = {}
    compile_items: list[str] = []
    for group in document:
        if group.tag == "PropertyGroup" and not group.attrib:
            for element in group:
                if element.attrib or list(element) or element.tag in properties:
                    raise MoveFailure(
                        "csharp_project_invalid", "properties must be unique scalar values"
                    )
                properties[element.tag] = (element.text or "").strip()
        elif group.tag == "ItemGroup" and not group.attrib:
            for element in group:
                if element.tag != "Compile":
                    raise MoveFailure(
                        "csharp_project_dependency_unsupported",
                        f"project item is unsupported: {element.tag}",
                    )
                if set(element.attrib) != {"Include"} or list(element):
                    raise MoveFailure(
                        "csharp_project_source_closure_mismatch",
                        "Compile items must be exact unconditional Include values",
                    )
                compile_items.append(
                    _safe_relative(
                        element.attrib["Include"],
                        label="Compile Include",
                        suffix=".cs",
                    )
                )
        else:
            raise MoveFailure(
                "csharp_project_dependency_unsupported",
                "only unconditional PropertyGroup and Compile ItemGroup are supported",
            )
    expected = {
        **EXPECTED_PROPERTIES,
        "AssemblyName": config["assembly_name"],
        "RootNamespace": config["namespace"],
    }
    if properties.get("AssemblyName") != config["assembly_name"]:
        raise MoveFailure(
            "csharp_assembly_identity_change",
            "project AssemblyName does not match reviewed identity",
        )
    if properties.get("RootNamespace") != config["namespace"]:
        raise MoveFailure(
            "csharp_namespace_identity_change",
            "project RootNamespace does not match reviewed identity",
        )
    if properties != expected:
        raise MoveFailure(
            "csharp_project_dependency_unsupported",
            "project must declare the exact dependency-free property set",
        )
    if len(compile_items) != len(set(compile_items)) or sorted(compile_items) != sorted(
        authored
    ):
        raise MoveFailure(
            "csharp_project_source_closure_mismatch",
            "Compile Include items must exactly cover authored source and tests",
        )
    for relative in compile_items:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise MoveFailure(
                "csharp_project_source_closure_mismatch",
                f"compile item is unavailable: {relative}",
            )
    return {
        "path": project_relative,
        "sha256": _sha256_path(project),
        "sdk": "Microsoft.NET.Sdk",
        "properties": properties,
        "compile_items": compile_items,
        "global_json": _validate_global_json(root, config),
        "nuget_config": _validate_nuget(root),
    }


def _source_facts(data: bytes, config: dict[str, str]) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise MoveFailure(
            "csharp_source_encoding_unsupported", "moved source must be UTF-8"
        ) from exc
    namespaces = list(NAMESPACE.finditer(text))
    if len(namespaces) != 1 or len(re.findall(r"\bnamespace\s+", text)) != 1:
        raise MoveFailure(
            "csharp_namespace_identity_change",
            "moved source must have one file-scoped namespace",
        )
    namespace = namespaces[0].group("name")
    if namespace != config["namespace"]:
        raise MoveFailure(
            "csharp_namespace_identity_change",
            "moved source namespace does not match reviewed identity",
        )
    declarations = list(TYPE_DECLARATION.finditer(text))
    if len(declarations) != 1:
        raise MoveFailure(
            "csharp_type_identity_change",
            "moved source must declare exactly one top-level type",
        )
    declaration = declarations[0]
    modifiers = declaration.group("modifiers").split()
    if "public" in modifiers or "protected" in modifiers:
        raise MoveFailure(
            "csharp_public_identity_unsupported",
            "moved type must not be public or protected",
        )
    if "partial" in modifiers or "file" in modifiers:
        raise MoveFailure(
            "csharp_type_identity_unsupported",
            "partial and file-local moved types are unsupported",
        )
    name = declaration.group("name")
    identity = f"{namespace}.{name}"
    if identity != config["type_identity"]:
        raise MoveFailure(
            "csharp_type_identity_change",
            "moved source type does not match reviewed identity",
        )
    if b"#line" in data or b"#if" in data or b"#define" in data:
        raise MoveFailure(
            "csharp_source_variant_unsupported",
            "preprocessor-dependent moved source is unsupported",
        )
    return {
        "namespace": namespace,
        "type_name": name,
        "type_identity": identity,
        "source_sha256": _sha256_bytes(data),
    }


def _validate_uncertainty(
    rows: dict[str, TreeEntry],
    project: dict[str, Any],
    plan_relative: str,
    move: dict[str, str],
    config: dict[str, str],
    *,
    phase: str,
) -> list[str]:
    source = move["from"]
    old_path = source.encode("utf-8")
    type_identity = config["type_identity"].encode("utf-8")
    type_name = config["type_identity"].rsplit(".", 1)[-1].encode("utf-8")
    basename = PurePosixPath(source).name.encode("utf-8")
    markers = (type_identity, type_name, basename, old_path)
    residue: list[str] = []
    for relative, entry in rows.items():
        if entry.kind != "file":
            continue
        assert isinstance(entry.data, bytes)
        data = entry.data
        if old_path in data and relative != plan_relative:
            if not (phase == "before" and relative == project["path"]):
                residue.append(relative)
        if PurePosixPath(relative).suffix == ".cs" and _role(relative) == "excluded":
            if type_identity in data or old_path in data:
                raise MoveFailure(
                    "csharp_excluded_identity_uncertain",
                    f"excluded C# source mentions the moved identity: {relative}",
                )
    if residue:
        raise MoveFailure(
            "csharp_old_path_residue",
            f"old source path occurs outside its owned project item: {residue[0]}",
        )
    for relative in project["compile_items"]:
        entry = rows[relative]
        assert isinstance(entry.data, bytes)
        data = entry.data
        if not any(marker in data for marker in markers):
            continue
        if any(token in data for token in RESOURCE_TOKENS):
            raise MoveFailure(
                "csharp_resource_identity_uncertain",
                f"resource lookup involving moved identity is unsupported: {relative}",
            )
        if any(token in data for token in REFLECTION_TOKENS):
            raise MoveFailure(
                "csharp_reflection_identity_uncertain",
                f"reflection involving moved identity is unsupported: {relative}",
            )
        if any(token in data for token in PATH_TOKENS):
            raise MoveFailure(
                "csharp_path_identity_uncertain",
                f"runtime path use involving moved identity is unsupported: {relative}",
            )
        if any(token in data for token in ABI_TOKENS):
            raise MoveFailure(
                "csharp_abi_identity_uncertain",
                f"interop or unsafe identity boundary is unsupported: {relative}",
            )
    return residue


def _validate_location(root: Path, relative: str, *, destination: bool) -> None:
    parts = PurePosixPath(relative).parts
    if not parts or parts[0] != "src" or any(
        part.lower() in EXCLUDED_CSHARP_PARTS for part in parts[:-1]
    ):
        raise MoveFailure(
            "csharp_source_role_unsupported",
            "source and destination must stay in the authored src tree",
        )
    path = root / relative
    if _has_symlink_ancestor(path, root):
        raise MoveFailure(
            "csharp_symlink_source_unsupported",
            f"source location crosses a symlink: {relative}",
        )
    if destination:
        if path.exists() or path.is_symlink():
            raise MoveFailure(
                "csharp_destination_exists", f"destination already exists: {relative}"
            )
    elif path.is_symlink():
        raise MoveFailure(
            "csharp_symlink_source_unsupported", f"source is a symlink: {relative}"
        )
    elif not path.is_file():
        raise MoveFailure("csharp_source_missing", f"source is missing: {relative}")


def _inspect(
    root: Path,
    rows: dict[str, TreeEntry],
    context: Context,
    plan: dict[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    move = plan["moves"][0]
    config = plan["csharp"]
    source = move["from"]
    destination = move["to"]
    if phase == "before":
        _validate_location(root, source, destination=False)
        _validate_location(root, destination, destination=True)
        selected = source
    else:
        if (root / source).exists() or (root / source).is_symlink():
            raise MoveFailure(
                "csharp_old_path_residue", "old source path remains after the move"
            )
        _validate_location(root, destination, destination=False)
        selected = destination
    roles, authored = _csharp_inventory(root, rows)
    if phase == "before" and roles.get(source) != "source":
        raise MoveFailure(
            "csharp_source_role_unsupported", "moved input must be authored source"
        )
    if phase == "after" and roles.get(destination) != "source":
        raise MoveFailure(
            "csharp_source_role_unsupported", "moved output must be authored source"
        )
    project = _validate_project(root, rows, config, authored)
    entry = rows.get(selected)
    if entry is None or entry.kind != "file":
        raise MoveFailure("csharp_source_missing", f"source is unavailable: {selected}")
    assert isinstance(entry.data, bytes)
    facts = _source_facts(entry.data, config)
    _validate_uncertainty(
        rows,
        project,
        context.plan_relative,
        move,
        config,
        phase=phase,
    )
    return {
        "project": project,
        "roles": roles,
        "authored_sources": authored,
        "source_facts": facts,
        "source_path": selected,
        "source_bytes": entry.data,
    }


def _probe_dotnet(root: Path, config: dict[str, str]) -> tuple[dict[str, str], Path]:
    requested = Path(config["dotnet"])
    try:
        resolved = requested.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MoveFailure(
            "dotnet_tool_missing", f"dotnet is unavailable: {exc}", status="unsupported"
        ) from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise MoveFailure(
            "dotnet_tool_missing", "dotnet must be an executable file", status="unsupported"
        )
    completed = _run([str(resolved), "--version"], root, timeout=20)
    version = completed.stdout.strip()
    if completed.returncode != 0 or VERSION.fullmatch(version) is None:
        raise MoveFailure(
            "dotnet_tool_unusable",
            (completed.stderr or completed.stdout or "dotnet --version failed").strip(),
            status="unsupported",
        )
    if version != config["sdk_version"]:
        raise MoveFailure(
            "dotnet_sdk_mismatch",
            f"dotnet reported {version}, expected {config['sdk_version']}",
            status="unsupported",
        )
    return {"path": str(resolved), "version": version}, resolved


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
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _record(
    argv: list[str],
    completed: subprocess.CompletedProcess[str],
    *,
    temporary: Path,
) -> dict[str, Any]:
    marker = "$EPHEMERAL_ROOT"

    def clean(value: str) -> str:
        rendered = value.replace(str(temporary), marker)
        rendered = re.sub(r"\(in \d+(?:\.\d+)? ms\)", "(in <elapsed>)", rendered)
        rendered = re.sub(
            r"(?m)^Time Elapsed .+$", "Time Elapsed <elapsed>", rendered
        )
        return rendered

    return {
        "passed": completed.returncode == 0,
        "argv": [clean(token) for token in argv],
        "cwd": "$EPHEMERAL_ROOT/project",
        "returncode": completed.returncode,
        "stdout": clean(completed.stdout)[:12000],
        "stderr": clean(completed.stderr)[:12000],
    }


def _input_hashes(root: Path, project: dict[str, Any]) -> dict[str, str]:
    paths = [
        project["path"],
        project["global_json"]["path"],
        project["nuget_config"]["path"],
        *project["compile_items"],
    ]
    return {relative: _sha256_path(root / relative) for relative in sorted(paths)}


def _native_checks(
    root: Path,
    dotnet: Path,
    project: dict[str, Any],
    config: dict[str, str],
) -> dict[str, Any]:
    native: dict[str, Any] = {
        name: {"passed": False, "status": "not-run"}
        for name in ("restore", "build", "test", "smoke")
    }
    with tempfile.TemporaryDirectory(prefix="csharp-source-move-") as temporary_raw:
        temporary = Path(temporary_raw).resolve()
        working = temporary / "project"
        working.mkdir()
        paths = [
            project["path"],
            project["global_json"]["path"],
            project["nuget_config"]["path"],
            *project["compile_items"],
        ]
        for relative in paths:
            destination = working / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, destination)
        before = _input_hashes(working, project)
        env = {
            **os.environ,
            "ALL_PROXY": "http://127.0.0.1:9",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
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
            raise NativeFailure(
                "dotnet_restore_failed",
                "offline dotnet restore failed",
                status="failed",
                extra={"native": native},
            )
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
            f"--property:PathMap={working}=/_/src",
        ]
        built = _run(build, working, env=env)
        native["build"] = _record(build, built, temporary=temporary)
        if built.returncode:
            raise NativeFailure(
                "dotnet_build_failed",
                "dotnet build failed",
                status="failed",
                extra={"native": native},
            )
        output = (
            working
            / "bin"
            / "Release"
            / "net10.0"
            / f"{config['assembly_name']}.dll"
        )
        if not output.is_file():
            raise NativeFailure(
                "dotnet_build_output_missing",
                "reviewed assembly output was not produced",
                status="failed",
                extra={"native": native},
            )
        native["build"]["output"] = {
            "path": f"bin/Release/net10.0/{config['assembly_name']}.dll",
            "assembly_name": config["assembly_name"],
            "present": True,
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
        if (
            tested.returncode
            or tested.stdout != config["native_test_expected_stdout"]
        ):
            raise NativeFailure(
                "dotnet_native_test_failed",
                "native test did not produce the reviewed outcome",
                status="failed",
                extra={"native": native},
            )
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
        if smoked.returncode or smoked.stdout != config["smoke_expected_stdout"]:
            raise NativeFailure(
                "dotnet_smoke_failed",
                "smoke did not produce the reviewed executable output",
                status="failed",
                extra={"native": native},
            )
        after = _input_hashes(working, project)
        if before != after:
            raise NativeFailure(
                "dotnet_source_mutation",
                "native checks changed a project input",
                status="failed",
                extra={"native": native},
            )
        native["source_preservation"] = {
            "passed": True,
            "before": before,
            "after": after,
        }
    return native


def _project_rewrite(data: bytes, source: str, destination: str) -> bytes:
    old = f'<Compile Include="{source}" />'.encode("utf-8")
    new = f'<Compile Include="{destination}" />'.encode("utf-8")
    if data.count(old) != 1 or new in data:
        raise MoveFailure(
            "csharp_project_source_closure_mismatch",
            "project must contain one exact source Compile Include token",
        )
    return data.replace(old, new, 1)


def _apply_mutation(root: Path, plan: dict[str, Any]) -> None:
    move = plan["moves"][0]
    source = root / move["from"]
    destination = root / move["to"]
    project = root / plan["csharp"]["project"]
    project_mode = stat.S_IMODE(project.stat().st_mode)
    rewritten = _project_rewrite(project.read_bytes(), move["from"], move["to"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)
    _write_bytes_atomic(project, rewritten, mode=project_mode)


def _analysis(context: Context) -> dict[str, Any]:
    plan = _load_plan(context)
    before_tree = _capture_tree(context.root, context.report_relative)
    before = _inspect(context.root, before_tree, context, plan, phase="before")
    tool, dotnet = _probe_dotnet(context.root, plan["csharp"])
    native_before = _native_checks(
        context.root, dotnet, before["project"], plan["csharp"]
    )
    with tempfile.TemporaryDirectory(prefix="csharp-move-preview-") as temporary_raw:
        virtual_root = Path(temporary_raw) / "host"
        virtual_root.mkdir()
        _materialize(before_tree, virtual_root)
        virtual_context = Context(
            root=virtual_root,
            plan_path=virtual_root / context.plan_relative,
            plan_relative=context.plan_relative,
            report_dir=virtual_root / context.report_relative,
            report_relative=context.report_relative,
            evidence_path=virtual_root / context.report_relative / "evidence.json",
            report_path=virtual_root / context.report_relative / "report.json",
        )
        _apply_mutation(virtual_root, plan)
        after_tree = _capture_tree(virtual_root, context.report_relative)
        after = _inspect(virtual_root, after_tree, virtual_context, plan, phase="after")
        if after["source_bytes"] != before["source_bytes"]:
            raise MoveFailure(
                "csharp_source_bytes_changed", "virtual move changed source bytes", status="failed"
            )
        if after["source_facts"] != before["source_facts"]:
            raise MoveFailure(
                "csharp_identity_changed", "virtual move changed source identity", status="failed"
            )
        native_after = _native_checks(
            virtual_root, dotnet, after["project"], plan["csharp"]
        )
    move = plan["moves"][0]
    exact_changes = [
        {
            "path": plan["csharp"]["project"],
            "kind": "csharp_compile_include",
            "old": move["from"],
            "new": move["to"],
        },
        {
            "path": move["from"],
            "kind": "csharp_source_location",
            "old": move["from"],
            "new": move["to"],
        },
    ]
    identity = {
        "assembly_name": plan["csharp"]["assembly_name"],
        "namespace": before["source_facts"]["namespace"],
        "type_identity": before["source_facts"]["type_identity"],
        "source_sha256": before["source_facts"]["source_sha256"],
    }
    evidence: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "language": "csharp",
        "plan": plan,
        "plan_sha256": _sha256_path(context.plan_path),
        "adapter_sha256": _sha256_path(Path(__file__).resolve()),
        "source_tree_sha256": _tree_fingerprint(before_tree),
        "source_tree_manifest": _tree_manifest(before_tree),
        "expected_after_tree_sha256": _tree_fingerprint(after_tree),
        "expected_after_tree_manifest": _tree_manifest(after_tree),
        "exact_changes": exact_changes,
        "identity": identity,
        "tool": tool,
        "project_before": before["project"],
        "project_after": after["project"],
        "source_closure_before": before["authored_sources"],
        "source_closure_after": after["authored_sources"],
        "native_preflight": native_before,
        "native_after_preview": native_after,
    }
    evidence["evidence_sha256"] = _sha256_bytes(_canonical(evidence))
    return evidence


def _verify_evidence(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise MoveFailure("move_evidence_invalid", "evidence schema is invalid", status="failed")
    rendered = payload.get("evidence_sha256")
    if not isinstance(rendered, str) or len(rendered) != 64:
        raise MoveFailure("move_evidence_invalid", "evidence hash is missing", status="failed")
    core = dict(payload)
    del core["evidence_sha256"]
    if _sha256_bytes(_canonical(core)) != rendered:
        raise MoveFailure(
            "move_evidence_invalid", "evidence content hash does not match", status="failed"
        )


def _load_evidence(context: Context, requested: Path | None) -> dict[str, Any]:
    if requested is None:
        raise MoveFailure(
            "missing_move_evidence",
            "apply/check requires the reviewed evidence file",
            status="failed",
        )
    resolved = requested.resolve(strict=False)
    if resolved != context.evidence_path or not resolved.is_file() or resolved.is_symlink():
        raise MoveFailure(
            "move_evidence_invalid",
            "evidence must be the regular report-dir/evidence.json",
            status="failed",
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MoveFailure("move_evidence_invalid", str(exc), status="failed") from exc
    _verify_evidence(payload)
    return payload


def _base_report(mode: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "csharp": {
            "status": "failed",
            "mode": mode,
            "failure_kind": "unknown",
            "rolled_back": False,
            "limits": [
                "One same-filename authored .cs implementation-file location move is supported.",
                "One strict dependency-free net10.0 executable project is the complete source/project closure.",
                "Namespace, type, assembly, source bytes, public API/ABI claims, dynamic identity, resources, packages, generators, analyzers, workloads, solutions, and external consumers are not inferred.",
            ],
        },
    }


def _failure_report(mode: str, failure: MoveFailure) -> dict[str, Any]:
    report = _base_report(mode)
    report["csharp"].update(
        status=failure.status,
        failure_kind=failure.kind,
        detail=failure.detail,
        **failure.extra,
    )
    return report


def _preview_report(evidence: dict[str, Any]) -> dict[str, Any]:
    report = _base_report("dry-run")
    report["csharp"].update(
        status="complete",
        failure_kind="none",
        evidence_sha256=evidence["evidence_sha256"],
        source_tree_sha256=evidence["source_tree_sha256"],
        expected_after_tree_sha256=evidence["expected_after_tree_sha256"],
        exact_changes=evidence["exact_changes"],
        identity=evidence["identity"],
        tool=evidence["tool"],
        project_before=evidence["project_before"],
        project_after=evidence["project_after"],
        source_closure_before=evidence["source_closure_before"],
        source_closure_after=evidence["source_closure_after"],
        native_preflight=evidence["native_preflight"],
        native_after_preview=evidence["native_after_preview"],
        exact_after_tree={
            "passed": True,
            "expected_fingerprint": evidence["expected_after_tree_sha256"],
            "actual_fingerprint": evidence["expected_after_tree_sha256"],
        },
        old_path_residue=[],
    )
    return report


def _dry_run(context: Context) -> tuple[dict[str, Any], int]:
    context.report_dir.mkdir(parents=True, exist_ok=True)
    context.evidence_path.unlink(missing_ok=True)
    try:
        evidence = _analysis(context)
    except MoveFailure as failure:
        return _failure_report("dry-run", failure), 2
    _write_json_atomic(context.evidence_path, evidence)
    return _preview_report(evidence), 0


def _fresh_authority(
    context: Context,
    requested: Path | None,
    approval: str | None,
    *,
    require_approval: bool,
) -> dict[str, Any]:
    evidence = _load_evidence(context, requested)
    if require_approval and approval != evidence["evidence_sha256"]:
        raise MoveFailure(
            "move_evidence_not_approved",
            "apply requires the exact reviewed evidence SHA-256",
            status="failed",
        )
    if evidence.get("adapter_sha256") != _sha256_path(Path(__file__).resolve()):
        raise MoveFailure(
            "stale_move_evidence", "adapter changed after preview", status="failed"
        )
    if evidence.get("plan_sha256") != _sha256_path(context.plan_path):
        raise MoveFailure("stale_move_evidence", "plan changed after preview", status="failed")
    return evidence


def _apply(
    context: Context,
    requested: Path | None,
    approval: str | None,
) -> tuple[dict[str, Any], int]:
    try:
        evidence = _fresh_authority(
            context, requested, approval, require_approval=True
        )
    except MoveFailure as failure:
        return _failure_report("apply", failure), 2
    try:
        current = _analysis(context)
    except MoveFailure as failure:
        stale = MoveFailure(
            "stale_move_evidence",
            f"current preview no longer matches: {failure.kind}: {failure.detail}",
            status="failed",
        )
        report = _failure_report("apply", stale)
        report["csharp"]["rolled_back"] = False
        return report, 2
    if current != evidence:
        report = _failure_report(
            "apply",
            MoveFailure(
                "stale_move_evidence",
                "current project/source/tool proof differs from reviewed evidence",
                status="failed",
            ),
        )
        report["csharp"]["rolled_back"] = False
        return report, 2
    before_tree = _capture_tree(context.root, context.report_relative)
    plan = evidence["plan"]
    try:
        _apply_mutation(context.root, plan)
        after_tree = _capture_tree(context.root, context.report_relative)
        after = _inspect(context.root, after_tree, context, plan, phase="after")
        if after["source_facts"]["source_sha256"] != evidence["identity"][
            "source_sha256"
        ]:
            raise MoveFailure(
                "csharp_source_bytes_changed",
                "applied destination bytes differ from preview",
                status="failed",
            )
        _, dotnet = _probe_dotnet(context.root, plan["csharp"])
        native = _native_checks(
            context.root, dotnet, after["project"], plan["csharp"]
        )
        actual_fingerprint = _tree_fingerprint(after_tree)
        if (
            actual_fingerprint != evidence["expected_after_tree_sha256"]
            or _tree_manifest(after_tree) != evidence["expected_after_tree_manifest"]
        ):
            raise MoveFailure(
                "csharp_exact_after_tree_mismatch",
                "applied tree differs from reviewed virtual after-tree",
                status="failed",
            )
    except (MoveFailure, OSError, RuntimeError, KeyboardInterrupt) as exc:
        failure = (
            exc
            if isinstance(exc, MoveFailure)
            else MoveFailure("csharp_apply_failed", str(exc), status="failed")
        )
        try:
            _restore_tree(context.root, context.report_relative, before_tree)
            restored = _capture_tree(context.root, context.report_relative)
            rollback_exact = {
                "passed": restored == before_tree,
                "expected_fingerprint": _tree_fingerprint(before_tree),
                "actual_fingerprint": _tree_fingerprint(restored),
            }
        except (MoveFailure, OSError, RuntimeError) as rollback_error:
            rollback_exact = {"passed": False, "detail": str(rollback_error)}
        report = _failure_report("apply", failure)
        report["csharp"].update(
            rolled_back=True,
            rollback_exact=rollback_exact,
        )
        return report, 2
    report = _base_report("apply")
    report["csharp"].update(
        status="complete",
        failure_kind="none",
        rolled_back=False,
        evidence_sha256=evidence["evidence_sha256"],
        exact_changes=evidence["exact_changes"],
        identity=evidence["identity"],
        native_postflight=native,
        old_path_residue=[],
        exact_after_tree={
            "passed": True,
            "expected_fingerprint": evidence["expected_after_tree_sha256"],
            "actual_fingerprint": actual_fingerprint,
        },
    )
    return report, 0


def _check(context: Context, requested: Path | None) -> tuple[dict[str, Any], int]:
    try:
        evidence = _fresh_authority(
            context, requested, approval=None, require_approval=False
        )
        plan = evidence["plan"]
        actual_tree = _capture_tree(context.root, context.report_relative)
        actual_fingerprint = _tree_fingerprint(actual_tree)
        if (
            actual_fingerprint != evidence["expected_after_tree_sha256"]
            or _tree_manifest(actual_tree) != evidence["expected_after_tree_manifest"]
        ):
            raise MoveFailure(
                "csharp_exact_after_tree_mismatch",
                "current tree differs from reviewed after-tree",
                status="failed",
            )
        after = _inspect(context.root, actual_tree, context, plan, phase="after")
        if after["source_facts"]["source_sha256"] != evidence["identity"][
            "source_sha256"
        ]:
            raise MoveFailure(
                "csharp_source_bytes_changed",
                "checked destination bytes differ from preview",
                status="failed",
            )
        _, dotnet = _probe_dotnet(context.root, plan["csharp"])
        native = _native_checks(
            context.root, dotnet, after["project"], plan["csharp"]
        )
    except MoveFailure as failure:
        return _failure_report("check", failure), 2
    report = _base_report("check")
    report["csharp"].update(
        status="complete",
        failure_kind="none",
        evidence_sha256=evidence["evidence_sha256"],
        identity=evidence["identity"],
        native_postflight=native,
        old_path_residue=[],
        exact_after_tree={
            "passed": True,
            "expected_fingerprint": evidence["expected_after_tree_sha256"],
            "actual_fingerprint": actual_fingerprint,
        },
    )
    return report, 0


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int, Context | None]:
    mode = "dry-run" if args.dry_run else "apply" if args.apply else "check"
    try:
        context = _context(args)
    except MoveFailure as failure:
        return _failure_report(mode, failure), 2, None
    context.report_dir.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        report, code = _dry_run(context)
    elif args.apply:
        report, code = _apply(
            context, args.evidence, args.approve_evidence_sha256
        )
    else:
        report, code = _check(context, args.evidence)
    _write_json_atomic(context.report_path, report)
    return report, code, context


def _parser() -> argparse.ArgumentParser:
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
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report, code, _ = run(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif code:
        print(
            f"C# move-path {report['csharp']['status']}: "
            f"{report['csharp']['failure_kind']}",
            file=sys.stderr,
        )
    else:
        print(f"C# move-path {report['csharp']['mode']}: complete")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
