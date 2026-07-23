#!/usr/bin/env python3
"""Content-addressed, read-only Dart semantic facts over SDK LSP.

This is a Dart-family provider, not a language-neutral LSP abstraction.  It
owns the exact Dart 3.12 project/configuration contract used by the D4
consumers and deliberately reports partial evidence when that contract is not
closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


SCHEMA_VERSION = "dart-lsp-facts-v1"
MINIMUM_DART = (3, 12)
CAPABILITY_PATHS = {
    "document_symbol": ("documentSymbolProvider",),
    "definition": ("definitionProvider",),
    "references": ("referencesProvider",),
    "workspace_symbol": ("workspaceSymbolProvider",),
    "rename": ("renameProvider",),
}
LIMITS = [
    "selected-configuration static facts only; runtime dispatch is not inferred",
    "conditional imports/exports, parts, augmentations, and generated code remain partial",
    "reflection, registries, isolates, native/JS interop, and external consumers remain unresolved",
    "SDK and dependency symbols are excluded from first-party facts",
    "no Flutter routes, widgets, assets, build modes, or runtime behavior are claimed",
]
EXCLUDED_DIRS = {
    ".git",
    ".dart_tool",
    ".venv",
    "build",
    "coverage",
    "example",
    "examples",
    "generated",
    "reports",
    "test",
    "tests",
    "vendor",
}
HARD_SKIP_DIRS = {".git", ".dart_tool", ".venv", "coverage", "reports"}


class DartFactError(RuntimeError):
    """A bounded provider failure that must survive in the terminal artifact."""


def _canonical(path: Path, *, strict: bool = False) -> Path:
    """Canonicalize real paths (including macOS case aliases)."""
    return Path(os.path.realpath(path.resolve(strict=strict)))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _contained(root: Path, candidate: Path) -> bool:
    try:
        _canonical(candidate).relative_to(_canonical(root))
        return True
    except ValueError:
        return False


def _safe_artifact(root: Path, supplied: Path, allowed: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    if not _contained(allowed, output) or output == allowed:
        raise DartFactError(f"output must stay beneath {allowed.relative_to(root).as_posix()}/")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise DartFactError("output must not traverse a symbolic link")
    return output


def _tool_path(value: str) -> str | None:
    candidate = Path(value)
    if candidate.parent != Path("."):
        return (
            str(_canonical(candidate))
            if candidate.is_file() and os.access(candidate, os.X_OK)
            else None
        )
    found = shutil.which(value)
    return str(_canonical(Path(found))) if found else None


def _tool_version(tool: str | None) -> tuple[str | None, tuple[int, int] | None, str | None]:
    if tool is None:
        return None, None, "dart executable is unavailable"
    try:
        result = subprocess.run(
            [tool, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, None, str(exc)
    rendered = (result.stdout + result.stderr).strip()
    match = re.search(r"Dart SDK version:\s*(\d+)\.(\d+)(?:\.\d+)?", rendered)
    if result.returncode != 0 or match is None:
        return rendered or None, None, "Dart version probe failed or was unrecognized"
    return rendered, (int(match.group(1)), int(match.group(2))), None


def _role(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    lower_parts = [part.lower() for part in relative.parts]
    name = path.name.lower()
    if any(part in {"test", "tests"} for part in lower_parts[:-1]) or name.endswith("_test.dart"):
        return "test-excluded"
    if any(part in {"example", "examples"} for part in lower_parts[:-1]):
        return "example-excluded"
    if any(part == "vendor" for part in lower_parts[:-1]):
        return "vendor-excluded"
    if any(part in {"build", ".dart_tool"} for part in lower_parts[:-1]):
        return "build-excluded"
    if any(part in {"generated", "gen"} for part in lower_parts[:-1]) or name.endswith(
        (".g.dart", ".freezed.dart")
    ):
        return "generated-excluded"
    if lower_parts and lower_parts[0] in {"bin", "tool"}:
        return "tooling-excluded"
    return "production"


def _inventory(root: Path, target: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    discovered: list[Path] = []
    for current_text, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_text)
        retained_directories: list[str] = []
        for name in sorted(directory_names):
            path = current / name
            relative = path.relative_to(root)
            if path.is_symlink():
                rows.append(
                    {
                        "path": relative.as_posix(),
                        "role": "symlink-excluded",
                        "selected": False,
                        "entry_kind": "directory",
                    }
                )
                continue
            if name.lower() in HARD_SKIP_DIRS:
                continue
            retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in sorted(file_names):
            if not name.lower().endswith(".dart"):
                continue
            discovered.append(current / name)
    for path in sorted(discovered):
        relative = path.relative_to(root)
        role = _role(root, path)
        if path.is_symlink():
            rows.append(
                {
                    "path": relative.as_posix(),
                    "role": "symlink-excluded",
                    "selected": False,
                    "entry_kind": "file",
                }
            )
            continue
        real = _canonical(path)
        if not _contained(root, real):
            rows.append(
                {"path": relative.as_posix(), "role": "symlink-excluded", "selected": False}
            )
            continue
        selected = path == target or (target.is_dir() and _contained(target, path))
        rows.append(
            {
                "path": relative.as_posix(),
                "real_path": real.as_posix(),
                "role": role,
                "selected": selected,
                "sha256": _sha256(path),
            }
        )
    return rows


def _pubspec_name(root: Path) -> str | None:
    pubspec = root / "pubspec.yaml"
    if not pubspec.is_file() or pubspec.is_symlink():
        return None
    match = re.search(
        r"(?m)^name:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:#.*)?$",
        pubspec.read_text(encoding="utf-8", errors="replace"),
    )
    return match.group(1) if match else None


def _package_config(
    root: Path, supplied: Path | None, package_imports: list[str]
) -> dict[str, Any]:
    default = root / ".dart_tool" / "package_config.json"
    original = supplied if supplied is not None else (default if default.is_file() else None)
    result: dict[str, Any] = {
        "required": bool(package_imports),
        "path": None,
        "sha256": None,
        "state": "not-required" if not package_imports else "missing",
        "package_imports": sorted(set(package_imports)),
        "selected_package": _pubspec_name(root),
        "problems": [],
        "selection": "explicit-external-allowed" if supplied is not None else "host-default",
    }
    if original is None:
        return result
    original = original if original.is_absolute() else root / original
    current = Path(original.anchor)
    for part in original.parts[1:] if original.is_absolute() else original.parts:
        current /= part
        if current.exists() and current.is_symlink():
            result["path"] = Path(os.path.abspath(original)).as_posix()
            result["state"] = "invalid"
            result["problems"].append("package configuration must not traverse a symbolic link")
            return result
    path = _canonical(original, strict=False)
    result["path"] = path.as_posix()
    if not path.is_file():
        result["state"] = "missing"
        result["problems"].append("selected package configuration is absent")
        return result
    result["sha256"] = _sha256(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result["state"] = "invalid"
        result["problems"].append(f"invalid package configuration: {exc}")
        return result
    packages = payload.get("packages")
    if not isinstance(packages, list):
        result["state"] = "invalid"
        result["problems"].append("package configuration has no packages list")
        return result
    names: set[str] = set()
    stale: list[str] = []
    for row in packages:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            continue
        names.add(row["name"])
        uri = row.get("rootUri")
        if isinstance(uri, str):
            parsed = urlparse(uri)
            package_root = (
                Path(unquote(parsed.path))
                if parsed.scheme == "file"
                else path.parent / unquote(uri)
            )
            if not _canonical(package_root, strict=False).exists():
                stale.append(row["name"])
    selected = result["selected_package"]
    imported_names = {item.split(":", 1)[1].split("/", 1)[0] for item in package_imports}
    missing = sorted(imported_names - names)
    if selected and selected not in names:
        missing.append(selected)
    if missing:
        result["problems"].append(
            f"packages absent from configuration: {', '.join(sorted(set(missing)))}"
        )
    if stale:
        result["problems"].append(f"stale package roots: {', '.join(sorted(stale))}")
    result["state"] = "current" if not result["problems"] else "stale"
    return result


def _uri_path(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return _canonical(Path(unquote(parsed.path)), strict=False)


def _location(row: dict[str, Any], root: Path) -> dict[str, Any] | None:
    uri = row.get("targetUri") or row.get("uri")
    if not isinstance(uri, str):
        return None
    path = _uri_path(uri)
    if path is None or not _contained(root, path):
        return None
    selected_range = row.get("targetSelectionRange") or row.get("range") or {}
    start = selected_range.get("start", {})
    return {
        "path": path.relative_to(root).as_posix(),
        "line": int(start.get("line", 0)) + 1,
        "column": int(start.get("character", 0)) + 1,
    }


class _LspClient:
    def __init__(self, argv: list[str], cwd: Path):
        self.argv = argv
        self.process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.pending: dict[int, dict[str, Any]] = {}
        self.notifications: list[dict[str, Any]] = []
        self.stderr: list[bytes] = []
        self.request_id = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.err_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self.reader.start()
        self.err_reader.start()

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        while chunk := self.process.stderr.readline():
            self.stderr.append(chunk)

    def _read(self) -> None:
        assert self.process.stdout is not None
        stream = self.process.stdout
        try:
            while True:
                headers: dict[str, str] = {}
                while True:
                    line = stream.readline()
                    if not line:
                        return
                    if line in {b"\r\n", b"\n"}:
                        break
                    if b":" not in line:
                        raise DartFactError("malformed LSP header")
                    name, value = line.decode("ascii", errors="strict").split(":", 1)
                    headers[name.lower().strip()] = value.strip()
                length = int(headers.get("content-length", "-1"))
                if length < 0:
                    raise DartFactError("LSP message omitted Content-Length")
                body = stream.read(length)
                if len(body) != length:
                    raise DartFactError("truncated LSP message")
                self.messages.put(json.loads(body.decode("utf-8")))
        except (OSError, UnicodeDecodeError, ValueError, DartFactError) as exc:
            # Reader failures are delivered through the queue to the request loop.
            self.messages.put({"_reader_error": str(exc)})

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        self.process.stdin.flush()

    def notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _dispatch(self, message: dict[str, Any]) -> None:
        if "_reader_error" in message:
            raise DartFactError(f"LSP protocol error: {message['_reader_error']}")
        if "id" in message and ("result" in message or "error" in message):
            self.pending[int(message["id"])] = message
        elif "method" in message:
            self.notifications.append(message)
            if "id" in message:
                self._send({"jsonrpc": "2.0", "id": message["id"], "result": None})

    def pump(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self._dispatch(
                    self.messages.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
                )
            except queue.Empty:
                continue

    def request(self, method: str, params: Any, timeout: float) -> Any:
        self.request_id += 1
        request_id = self.request_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if request_id in self.pending:
                response = self.pending.pop(request_id)
                if "error" in response:
                    raise DartFactError(f"{method} failed: {response['error']}")
                return response.get("result")
            if self.process.poll() is not None:
                stderr = b"".join(self.stderr).decode(errors="replace")[-2000:]
                raise DartFactError(
                    f"Dart language server exited {self.process.returncode}: {stderr}"
                )
            try:
                self._dispatch(
                    self.messages.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
                )
            except queue.Empty:
                continue
        raise TimeoutError(f"LSP request timed out: {method}")

    def close(self) -> dict[str, Any]:
        shutdown = False
        exited = False
        try:
            if self.process.poll() is None:
                self.request("shutdown", None, 5)
                shutdown = True
                self.notify("exit", None)
                self.process.wait(timeout=5)
                exited = True
        except (DartFactError, TimeoutError, subprocess.TimeoutExpired):
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        return {
            "shutdown_acknowledged": shutdown,
            "exited_cleanly": exited and self.process.returncode == 0,
            "returncode": self.process.returncode,
            "stderr": b"".join(self.stderr).decode(errors="replace")[-2000:],
        }


def _flatten_symbols(items: Any, source: str, parent: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items or []:
        selection = (
            item.get("selectionRange")
            or item.get("location", {}).get("range")
            or item.get("range", {})
        )
        start = selection.get("start", {})
        row = {
            "name": item.get("name"),
            "kind": item.get("kind"),
            "source": source,
            "line": int(start.get("line", 0)) + 1,
            "column": int(start.get("character", 0)) + 1,
            "parent": parent,
            "top_level": parent is None,
        }
        rows.append(row)
        rows.extend(_flatten_symbols(item.get("children"), source, item.get("name")))
    return rows


def _lexical_boundaries(
    root: Path, inventory: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    boundaries: list[dict[str, Any]] = []
    package_imports: list[str] = []
    directive = re.compile(
        r"(?m)^\s*(import|export|part(?:\s+of)?)\s+['\"]([^'\"]+)['\"](?P<tail>[^;]*);"
    )
    for row in inventory:
        if row["role"] != "production":
            continue
        source = root / row["path"]
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in directive.finditer(text):
            uri = match.group(2)
            if uri.startswith("package:"):
                package_imports.append(uri)
            kind = match.group(1)
            tail = match.group("tail")
            if kind.startswith("part"):
                boundaries.append(
                    {"path": row["path"], "kind": "part", "directive": match.group(0).strip()}
                )
            if " if (" in tail:
                boundaries.append(
                    {
                        "path": row["path"],
                        "kind": "conditional-directive",
                        "directive": match.group(0).strip(),
                    }
                )
        if re.search(r"(?m)^\s*augment(?:ation)?\b", text):
            boundaries.append({"path": row["path"], "kind": "augmentation"})
        if re.search(r"\b(?:MirrorsUsed|dart:mirrors)\b", text):
            boundaries.append({"path": row["path"], "kind": "reflection"})
        if re.search(r"\b(?:Isolate|dart:isolate)\b", text):
            boundaries.append({"path": row["path"], "kind": "isolate"})
        if re.search(r"\b(?:dart:ffi|dart:js_interop)\b", text):
            boundaries.append({"path": row["path"], "kind": "native-or-js-interop"})
    return boundaries, package_imports


def _diagnostics(client: _LspClient, root: Path) -> list[dict[str, Any]]:
    client.pump(1.0)
    rows: list[dict[str, Any]] = []
    for message in client.notifications:
        if message.get("method") != "textDocument/publishDiagnostics":
            continue
        params = message.get("params", {})
        path = _uri_path(params.get("uri", ""))
        if path is None or not _contained(root, path):
            continue
        for diagnostic in params.get("diagnostics", []):
            start = diagnostic.get("range", {}).get("start", {})
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "line": int(start.get("line", 0)) + 1,
                    "column": int(start.get("character", 0)) + 1,
                    "severity": diagnostic.get("severity"),
                    "code": diagnostic.get("code"),
                    "message": diagnostic.get("message"),
                }
            )
    return sorted(rows, key=lambda row: (row["path"], row["line"], row["column"]))


def collect(
    project_root: Path,
    target: str,
    queries: list[str],
    *,
    dart: str = "dart",
    packages: Path | None = None,
    cache_dir: Path | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    root = _canonical(project_root, strict=True)
    selected = _canonical(root / target, strict=True)
    if not _contained(root, selected):
        raise DartFactError("target must stay inside project root")
    inventory = _inventory(root, selected)
    boundaries, package_imports = _lexical_boundaries(root, inventory)
    config = _package_config(root, packages, package_imports)
    tool = _tool_path(dart)
    version, release, version_error = _tool_version(tool)
    query_names = sorted(set(name for name in queries if re.fullmatch(r"[A-Za-z_]\w*", name)))
    query_plan = {
        "target": selected.relative_to(root).as_posix(),
        "queries": query_names,
        "requests": [
            "workspace/symbol",
            "textDocument/documentSymbol",
            "textDocument/definition",
            "textDocument/references",
            "textDocument/prepareRename",
            "textDocument/rename",
        ],
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "language": "dart",
        "read_only": True,
        "status": "partial",
        "failure_kind": None,
        "target": query_plan["target"],
        "tool": {"path": tool, "version": version, "minimum": "3.12.0"},
        "package_config": config,
        "source_inventory": inventory,
        "source_hashes": [
            {"path": row["path"], "sha256": row["sha256"], "role": row["role"]}
            for row in inventory
            if "sha256" in row
        ],
        "boundaries": boundaries,
        "query_plan": query_plan,
        "query_plan_sha256": _canonical_hash(query_plan),
        "capabilities": {},
        "missing_capabilities": [],
        "diagnostics": [],
        "document_symbols": [],
        "workspace_symbols": [],
        "definition_queries": [],
        "module_edges": [],
        "reference_queries": [],
        "rename_queries": [],
        "unresolved_requests": [],
        "server": {"protocol": "LSP", "argv": [], "lifecycle": {}},
        "cache": {"external": True, "owned": cache_dir is None, "cleanup_verified": False},
        "limits": LIMITS,
    }
    if version_error or release is None:
        payload.update(status="failed", failure_kind="dart_missing_or_broken")
        payload["failure_detail"] = version_error
        return _finalize(payload)
    if release < MINIMUM_DART:
        payload.update(status="failed", failure_kind="dart_too_old")
        payload["failure_detail"] = "Dart 3.12 or newer is required"
        return _finalize(payload)
    if config["state"] in {"missing", "invalid", "stale"}:
        payload["failure_kind"] = f"package_config_{config['state']}"

    owned_cache = cache_dir is None
    cache = (
        _canonical(cache_dir, strict=False)
        if cache_dir
        else Path(tempfile.mkdtemp(prefix="dart-lsp-cache-"))
    )
    cache.mkdir(parents=True, exist_ok=True)
    payload["cache"]["path_kind"] = "caller-owned" if not owned_cache else "temporary"
    argv = [tool, "language-server", "--protocol=lsp", f"--cache={cache}"]
    if config.get("path"):
        argv.append(f"--packages={config['path']}")
    payload["server"]["argv"] = [
        "<dart>",
        "language-server",
        "--protocol=lsp",
        "--cache=<external>",
    ] + (["--packages=<hashed-config>"] if config.get("path") else [])
    client: _LspClient | None = None
    snapshot = {row["path"]: row.get("sha256") for row in inventory if "sha256" in row}
    try:
        client = _LspClient(argv, root)
        initialized = client.request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": root.as_uri(),
                "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
                "capabilities": {
                    "workspace": {"symbol": {"resolveSupport": {"properties": []}}},
                    "textDocument": {
                        "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                        "definition": {"linkSupport": True},
                        "references": {},
                        "rename": {"prepareSupport": True},
                        "publishDiagnostics": {},
                    },
                },
            },
            timeout,
        )
        client.notify("initialized", {})
        capabilities = initialized.get("capabilities", {}) if isinstance(initialized, dict) else {}
        payload["capabilities"] = capabilities
        for name, path_parts in CAPABILITY_PATHS.items():
            current: Any = capabilities
            for part in path_parts:
                current = current.get(part) if isinstance(current, dict) else None
            if not current:
                payload["missing_capabilities"].append(name)
        production = [root / row["path"] for row in inventory if row["role"] == "production"]
        # Workspace-symbol polling is the known Dart readiness barrier.
        readiness = query_names[0] if query_names else (_pubspec_name(root) or "")
        deadline = time.monotonic() + timeout
        ready_symbols: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            result = client.request("workspace/symbol", {"query": readiness}, min(10, timeout))
            ready_symbols = result or []
            if not readiness or ready_symbols:
                break
            time.sleep(0.1)
        payload["workspace_symbols"] = [
            {
                "name": row.get("name"),
                "kind": row.get("kind"),
                "location": _location(row.get("location", row), root),
            }
            for row in ready_symbols
            if _location(row.get("location", row), root) is not None
        ]
        if readiness and not ready_symbols:
            payload["unresolved_requests"].append(
                {
                    "method": "workspace/symbol",
                    "query": readiness,
                    "reason": "readiness symbol not observed",
                }
            )
        for source in production:
            try:
                result = client.request(
                    "textDocument/documentSymbol",
                    {"textDocument": {"uri": source.as_uri()}},
                    timeout,
                )
                payload["document_symbols"].extend(
                    _flatten_symbols(result, source.relative_to(root).as_posix())
                )
            except (DartFactError, TimeoutError) as exc:
                payload["unresolved_requests"].append(
                    {
                        "method": "textDocument/documentSymbol",
                        "source": source.relative_to(root).as_posix(),
                        "reason": str(exc),
                    }
                )
        directive_pattern = re.compile(
            r"(?m)^\s*(?P<kind>import|export)\s+['\"](?P<uri>[^'\"]+)['\"]"
        )
        for source in production:
            text = source.read_text(encoding="utf-8", errors="replace")
            for match in directive_pattern.finditer(text):
                prefix = text[: match.start("uri")]
                line_index = prefix.count("\n")
                line_start = prefix.rfind("\n") + 1
                character = match.start("uri") - line_start
                request = {
                    "textDocument": {"uri": source.as_uri()},
                    "position": {"line": line_index, "character": character},
                }
                edge = {
                    "source": source.relative_to(root).as_posix(),
                    "line": line_index + 1,
                    "kind": match.group("kind"),
                    "specifier": match.group("uri"),
                    "targets": [],
                    "method": "textDocument/definition",
                }
                try:
                    definitions = client.request("textDocument/definition", request, timeout)
                    if isinstance(definitions, dict):
                        definitions = [definitions]
                    edge["targets"] = [
                        item for row in definitions or [] if (item := _location(row, root))
                    ]
                    if not edge["targets"] and not match.group("uri").startswith("dart:"):
                        payload["unresolved_requests"].append(
                            {
                                "method": "textDocument/definition",
                                "source": edge["source"],
                                "line": edge["line"],
                                "specifier": edge["specifier"],
                                "reason": "module directive did not resolve to first-party source",
                            }
                        )
                except (DartFactError, TimeoutError) as exc:
                    payload["unresolved_requests"].append(
                        {
                            "method": "textDocument/definition",
                            "source": edge["source"],
                            "line": edge["line"],
                            "specifier": edge["specifier"],
                            "reason": str(exc),
                        }
                    )
                payload["module_edges"].append(edge)
        declarations = {
            (row["name"], row["source"], row["line"], row["column"]): row
            for row in payload["document_symbols"]
            if row["name"] in query_names and row.get("top_level")
        }
        for source in production:
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
            for line_index, line in enumerate(lines):
                for name in query_names:
                    for match in re.finditer(rf"\b{re.escape(name)}\b", line):
                        position = {"line": line_index, "character": match.start()}
                        request = {"textDocument": {"uri": source.as_uri()}, "position": position}
                        try:
                            definitions = client.request(
                                "textDocument/definition", request, timeout
                            )
                            if isinstance(definitions, dict):
                                definitions = [definitions]
                            targets = [
                                item for row in definitions or [] if (item := _location(row, root))
                            ]
                            payload["definition_queries"].append(
                                {
                                    "name": name,
                                    "source": source.relative_to(root).as_posix(),
                                    "line": line_index + 1,
                                    "column": match.start() + 1,
                                    "targets": targets,
                                    "method": "textDocument/definition",
                                }
                            )
                        except (DartFactError, TimeoutError) as exc:
                            payload["unresolved_requests"].append(
                                {
                                    "method": "textDocument/definition",
                                    "name": name,
                                    "source": source.relative_to(root).as_posix(),
                                    "line": line_index + 1,
                                    "reason": str(exc),
                                }
                            )
        for (_, source_name, line, column), declaration in declarations.items():
            source = root / source_name
            position = {"line": line - 1, "character": column - 1}
            request = {"textDocument": {"uri": source.as_uri()}, "position": position}
            try:
                references = client.request(
                    "textDocument/references",
                    {**request, "context": {"includeDeclaration": False}},
                    timeout,
                )
                targets = [item for row in references or [] if (item := _location(row, root))]
                payload["reference_queries"].append(
                    {
                        "name": declaration["name"],
                        "declaration": {"path": source_name, "line": line, "column": column},
                        "references": targets,
                        "method": "textDocument/references",
                    }
                )
            except (DartFactError, TimeoutError) as exc:
                payload["unresolved_requests"].append(
                    {
                        "method": "textDocument/references",
                        "name": declaration["name"],
                        "source": source_name,
                        "line": line,
                        "reason": str(exc),
                    }
                )
                continue
            rename_row: dict[str, Any] = {
                "name": declaration["name"],
                "declaration": {"path": source_name, "line": line, "column": column},
                "prepare": None,
                "read_only_edit_count": None,
            }
            try:
                rename_row["prepare"] = client.request(
                    "textDocument/prepareRename", request, timeout
                )
                edits = client.request(
                    "textDocument/rename",
                    {**request, "newName": f"{declaration['name']}D4Probe"},
                    timeout,
                )
                changes = (edits or {}).get("changes", {}) if isinstance(edits, dict) else {}
                document_changes = (
                    (edits or {}).get("documentChanges", []) if isinstance(edits, dict) else []
                )
                rename_row["read_only_edit_count"] = sum(
                    len(value) for value in changes.values()
                ) + len(document_changes)
            except (DartFactError, TimeoutError) as exc:
                rename_row["reason"] = str(exc)
                payload["unresolved_requests"].append(
                    {
                        "method": "textDocument/prepareRename+rename",
                        "name": declaration["name"],
                        "source": source_name,
                        "line": line,
                        "reason": str(exc),
                    }
                )
            payload["rename_queries"].append(rename_row)
        payload["diagnostics"] = _diagnostics(client, root)
        error_diagnostics = [row for row in payload["diagnostics"] if row.get("severity") == 1]
        partial_reasons = []
        if config["state"] in {"missing", "invalid", "stale"}:
            partial_reasons.append(f"package configuration is {config['state']}")
        if boundaries:
            partial_reasons.append("conditional/part/augmentation/runtime boundaries are present")
        if payload["missing_capabilities"]:
            partial_reasons.append("required LSP capabilities are missing")
        if payload["unresolved_requests"]:
            partial_reasons.append("one or more LSP requests are unresolved")
        if error_diagnostics:
            payload.update(status="failed", failure_kind="lsp_error_diagnostics")
        elif partial_reasons:
            payload.update(
                status="partial", failure_kind=payload.get("failure_kind") or "semantic_boundary"
            )
        else:
            payload.update(status="complete", failure_kind=None)
        payload["partial_reasons"] = partial_reasons
        current = _inventory(root, selected)
        current_snapshot = {row["path"]: row.get("sha256") for row in current if "sha256" in row}
        if current_snapshot != snapshot:
            payload.update(status="failed", failure_kind="source_mutation_detected")
    except (OSError, DartFactError, TimeoutError, subprocess.SubprocessError) as exc:
        payload.update(status="failed", failure_kind="lsp_protocol_or_process_failure")
        payload["failure_detail"] = str(exc)
    finally:
        if client is not None:
            payload["server"]["lifecycle"] = client.close()
        if owned_cache:
            shutil.rmtree(cache, ignore_errors=True)
            payload["cache"]["cleanup_verified"] = not cache.exists()
        else:
            payload["cache"]["cleanup_verified"] = None
    return _finalize(payload)


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    payload.pop("fact_pack_sha256", None)
    payload["fact_pack_sha256"] = _canonical_hash(payload)
    return payload


def load_or_collect(
    *,
    facts: Path | None,
    project_root: Path,
    target: str,
    queries: list[str],
    dart: str,
    packages: Path | None,
    cache_dir: Path | None,
    timeout: float,
) -> dict[str, Any]:
    root = _canonical(project_root, strict=True)
    if facts is None:
        return collect(
            root,
            target,
            queries,
            dart=dart,
            packages=packages,
            cache_dir=cache_dir,
            timeout=timeout,
        )
    payload = json.loads(facts.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise DartFactError("incompatible Dart semantic fact pack")
    supplied = payload.get("fact_pack_sha256")
    without = dict(payload)
    without.pop("fact_pack_sha256", None)
    if supplied != _canonical_hash(without):
        raise DartFactError("Dart semantic fact pack hash does not verify")
    requested_target = _canonical(root / target, strict=True).relative_to(root)
    packed_target = Path(payload.get("target", "."))
    try:
        requested_target.relative_to(packed_target)
    except ValueError as exc:
        raise DartFactError("Dart semantic fact pack does not cover the consumer target") from exc
    requested = sorted(set(queries))
    if any(name not in payload.get("query_plan", {}).get("queries", []) for name in requested):
        raise DartFactError("Dart semantic fact pack does not contain the consumer query")
    for row in payload.get("source_hashes", []):
        source = root / row["path"]
        if not source.is_file() or source.is_symlink() or _sha256(source) != row["sha256"]:
            raise DartFactError(f"Dart semantic fact pack is stale for {row['path']}")
    config = payload.get("package_config", {})
    if config.get("path") and config.get("sha256"):
        path = Path(config["path"])
        if not path.is_file() or _sha256(path) != config["sha256"]:
            raise DartFactError("Dart semantic fact pack package configuration is stale")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dart", default="dart")
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    root = _canonical(args.project_root, strict=True)
    try:
        output = _safe_artifact(root, args.output, root / "reports" / "dart-lsp-facts")
        payload = collect(
            root,
            args.target,
            args.query,
            dart=args.dart,
            packages=args.packages,
            cache_dir=args.cache_dir,
            timeout=args.timeout,
        )
        _atomic(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except (DartFactError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"wrote Dart semantic fact pack: {output}")
    return 2 if payload["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
