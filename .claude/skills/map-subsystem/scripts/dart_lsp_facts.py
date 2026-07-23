#!/usr/bin/env python3
"""Content-addressed, read-only Dart semantic facts over SDK LSP.

This is a Dart-family provider, not a language-neutral LSP abstraction.  It
owns the exact Dart 3.12 project/configuration and resolved outgoing-call
contract used by the D4 consumers and deliberately reports partial evidence
when that contract is not closed.
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
    "call_hierarchy": ("callHierarchyProvider",),
    "document_symbol": ("documentSymbolProvider",),
    "definition": ("definitionProvider",),
    "references": ("referencesProvider",),
    "workspace_symbol": ("workspaceSymbolProvider",),
    "rename": ("renameProvider",),
}
CALLABLE_SYMBOL_KINDS = {6: "method", 9: "constructor", 12: "function"}
LIMITS = [
    "selected-configuration static facts only; runtime dispatch is not inferred",
    "only server-resolved outgoing calls are edges; dynamic and out-of-scope "
    "targets remain explicit per-caller uncertainties",
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


def _lsp_range(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start")
    end = value.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return None
    try:
        return {
            "line": int(start["line"]) + 1,
            "column": int(start["character"]) + 1,
            "end_line": int(end["line"]) + 1,
            "end_column": int(end["character"]) + 1,
        }
    except (KeyError, TypeError, ValueError):
        return None


def _callable_symbols(
    items: Any,
    source: str,
    parent: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind in CALLABLE_SYMBOL_KINDS:
            rows.append({"source": source, "parent": parent, "item": item})
        rows.extend(_callable_symbols(item.get("children"), source, item.get("name")))
    return rows


def _call_item_identity(
    item: Any,
    root: Path,
    inventory: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(item, dict):
        return None, "call-hierarchy item is not an object"
    name = item.get("name")
    kind = item.get("kind")
    uri = item.get("uri")
    declaration = _lsp_range(item.get("range"))
    selection = _lsp_range(item.get("selectionRange"))
    if (
        not isinstance(name, str)
        or not name
        or not isinstance(kind, int)
        or not isinstance(uri, str)
        or declaration is None
        or selection is None
    ):
        return None, "call-hierarchy item omitted identity, URI, or exact ranges"
    path = _uri_path(uri)
    relative: str | None = None
    role = "external"
    origin = "external"
    if path is not None and _contained(root, path):
        relative = path.relative_to(root).as_posix()
        role = inventory.get(relative, {}).get("role", "untracked")
        origin = "first-party" if role == "production" else "first-party-excluded"
    identity: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "kind_name": CALLABLE_SYMBOL_KINDS.get(kind, "other"),
        "detail": item.get("detail") if isinstance(item.get("detail"), str) else None,
        "origin": origin,
        "role": role,
        "path": relative,
        "uri_sha256": None if relative is not None else hashlib.sha256(uri.encode()).hexdigest(),
        "declaration_range": declaration,
        "selection_range": selection,
    }
    identity["symbol_id"] = f"dart:{_canonical_hash(identity)}"
    return identity, None


def _document_symbol_identity(
    candidate: dict[str, Any],
    root: Path,
    inventory: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    item = candidate["item"]
    source = candidate["source"]
    synthetic = {
        "name": item.get("name"),
        "kind": item.get("kind"),
        "detail": candidate.get("parent") or Path(source).name,
        "uri": (root / source).as_uri(),
        "range": item.get("range"),
        "selectionRange": item.get("selectionRange"),
    }
    return _call_item_identity(synthetic, root, inventory)


def _call_sites(value: Any, caller: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(value, list):
        return [], "outgoing call omitted fromRanges"
    rows: list[dict[str, Any]] = []
    for raw in value:
        normalized = _lsp_range(raw)
        if normalized is None:
            return [], "outgoing call contains a malformed fromRange"
        rows.append({"path": caller["path"], **normalized})
    if not rows:
        return [], "outgoing call contains no source call-site range"
    rows.sort(
        key=lambda row: (
            row["line"],
            row["column"],
            row["end_line"],
            row["end_column"],
        )
    )
    return rows, None


def _dynamic_uncertainties(root: Path, caller: dict[str, Any]) -> list[dict[str, Any]]:
    path = caller.get("path")
    declaration = caller.get("declaration_range")
    if not isinstance(path, str) or not isinstance(declaration, dict):
        return []
    lines = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
    start_line = declaration["line"]
    end_line = declaration["end_line"]
    rows: list[dict[str, Any]] = []
    for line_number in range(start_line, min(end_line, len(lines)) + 1):
        line = lines[line_number - 1]
        for match in re.finditer(r"\bdynamic\b", line):
            rows.append(
                {
                    "kind": "dynamic-type-syntax",
                    "path": path,
                    "line": line_number,
                    "column": match.start() + 1,
                    "reason": "runtime dispatch target is not closed by static call hierarchy",
                }
            )
    return rows


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


def _collect_call_hierarchy(
    client: _LspClient,
    root: Path,
    inventory: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    available: bool,
    timeout: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    queries: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for candidate in candidates:
        source = candidate["source"]
        item = candidate["item"]
        fallback, fallback_error = _document_symbol_identity(candidate, root, inventory)
        if fallback is None:
            unresolved.append(
                {
                    "method": "textDocument/prepareCallHierarchy",
                    "source": source,
                    "name": item.get("name"),
                    "reason": fallback_error,
                }
            )
            continue
        source_sha256 = inventory.get(source, {}).get("sha256")

        def stopped(
            reason: str,
            prepare_status: str,
            *,
            caller_fallback: dict[str, Any] = fallback,
            caller_sha256: str | None = source_sha256,
            caller_source: str = source,
            caller_name: Any = item.get("name"),
        ) -> None:
            uncertainty = {
                "kind": "call-hierarchy-unresolved",
                "reason": reason,
            }
            queries.append(
                {
                    "caller": caller_fallback,
                    "source_sha256": caller_sha256,
                    "prepare": {
                        "method": "textDocument/prepareCallHierarchy",
                        "status": prepare_status,
                        "result_count": 0,
                    },
                    "method": "callHierarchy/outgoingCalls",
                    "outgoing_status": "not-run",
                    "status": "partial",
                    "outgoing_calls": [],
                    "uncertainties": [uncertainty],
                }
            )
            unresolved.append(
                {
                    "method": "textDocument/prepareCallHierarchy",
                    "source": caller_source,
                    "name": caller_name,
                    "reason": reason,
                }
            )

        if not available:
            stopped("server did not advertise callHierarchyProvider", "unsupported")
            continue
        selection = item.get("selectionRange", {}).get("start")
        if not isinstance(selection, dict):
            stopped("document symbol omitted an exact selection position", "malformed")
            continue
        request = {
            "textDocument": {"uri": (root / source).as_uri()},
            "position": selection,
        }
        try:
            prepared = client.request("textDocument/prepareCallHierarchy", request, timeout)
        except (DartFactError, TimeoutError) as exc:
            stopped(str(exc), "unresolved")
            continue
        if not isinstance(prepared, list) or not prepared:
            stopped("prepareCallHierarchy returned no origin item", "unresolved")
            continue
        for origin_item in prepared:
            caller, caller_error = _call_item_identity(origin_item, root, inventory)
            if caller is None:
                stopped(caller_error or "malformed origin item", "malformed")
                continue
            uncertainties: list[dict[str, Any]] = []
            if caller["origin"] != "first-party":
                uncertainties.append(
                    {
                        "kind": "prepare-origin-outside-production-scope",
                        "reason": "prepared origin is not a first-party production callable",
                    }
                )
            if any(
                caller[field] != fallback[field]
                for field in ("name", "kind", "path", "selection_range")
            ):
                uncertainties.append(
                    {
                        "kind": "prepare-origin-mismatch",
                        "candidate_symbol_id": fallback["symbol_id"],
                        "reason": "prepared origin does not match the document-symbol candidate",
                    }
                )
            if len(prepared) != 1:
                uncertainties.append(
                    {
                        "kind": "prepare-origin-ambiguous",
                        "reason": "prepareCallHierarchy returned multiple origin items",
                    }
                )
            uncertainties.extend(_dynamic_uncertainties(root, caller))
            outgoing_calls: list[dict[str, Any]] = []
            outgoing_status = "resolved"
            try:
                outgoing = client.request(
                    "callHierarchy/outgoingCalls", {"item": origin_item}, timeout
                )
            except (DartFactError, TimeoutError) as exc:
                outgoing = []
                outgoing_status = "unresolved"
                uncertainties.append(
                    {"kind": "call-hierarchy-unresolved", "reason": str(exc)}
                )
                unresolved.append(
                    {
                        "method": "callHierarchy/outgoingCalls",
                        "source": source,
                        "name": caller["name"],
                        "caller_symbol_id": caller["symbol_id"],
                        "reason": str(exc),
                    }
                )
            if outgoing is not None and not isinstance(outgoing, list):
                outgoing_status = "malformed"
                uncertainties.append(
                    {
                        "kind": "call-hierarchy-malformed",
                        "reason": "outgoingCalls result is not a list",
                    }
                )
                outgoing = []
            for raw in outgoing or []:
                if not isinstance(raw, dict):
                    uncertainties.append(
                        {
                            "kind": "call-hierarchy-malformed",
                            "reason": "outgoing call row is not an object",
                        }
                    )
                    continue
                callee, callee_error = _call_item_identity(raw.get("to"), root, inventory)
                if callee is None:
                    uncertainties.append(
                        {
                            "kind": "call-hierarchy-malformed",
                            "reason": callee_error,
                        }
                    )
                    continue
                call_sites, sites_error = _call_sites(raw.get("fromRanges"), caller)
                if sites_error:
                    uncertainties.append(
                        {
                            "kind": "call-hierarchy-malformed",
                            "callee_symbol_id": callee["symbol_id"],
                            "reason": sites_error,
                        }
                    )
                    continue
                resolution = {
                    "first-party": "resolved-first-party",
                    "first-party-excluded": "resolved-excluded-first-party",
                    "external": "resolved-external",
                }[callee["origin"]]
                outgoing_calls.append(
                    {
                        "callee": callee,
                        "call_sites": call_sites,
                        "resolution": resolution,
                    }
                )
                if callee["origin"] != "first-party":
                    uncertainties.append(
                        {
                            "kind": "callee-outside-production-scope",
                            "callee_symbol_id": callee["symbol_id"],
                            "resolution": resolution,
                            "reason": "callee internals are outside first-party production facts",
                        }
                    )
            outgoing_calls.sort(
                key=lambda row: (
                    row["callee"]["symbol_id"],
                    row["call_sites"][0]["line"],
                    row["call_sites"][0]["column"],
                )
            )
            uncertainties.sort(key=_canonical_hash)
            queries.append(
                {
                    "caller": caller,
                    "source_sha256": source_sha256,
                    "prepare": {
                        "method": "textDocument/prepareCallHierarchy",
                        "status": "resolved",
                        "result_count": len(prepared),
                    },
                    "method": "callHierarchy/outgoingCalls",
                    "outgoing_status": outgoing_status,
                    "status": "partial" if uncertainties else "complete",
                    "outgoing_calls": outgoing_calls,
                    "uncertainties": uncertainties,
                }
            )
    queries.sort(key=lambda row: row["caller"]["symbol_id"])
    return queries, unresolved


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
            "textDocument/prepareCallHierarchy",
            "callHierarchy/outgoingCalls",
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
        "call_hierarchy_queries": [],
        "call_hierarchy_summary": {
            "callers": 0,
            "complete": 0,
            "partial": 0,
            "resolved_edges": 0,
            "unresolved": 0,
        },
        "unresolved_requests": [],
        "server": {"protocol": "LSP", "argv": [], "info": None, "lifecycle": {}},
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
                        "callHierarchy": {"dynamicRegistration": False},
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
        payload["server"]["info"] = (
            initialized.get("serverInfo") if isinstance(initialized, dict) else None
        )
        payload["capabilities"] = capabilities
        for name, path_parts in CAPABILITY_PATHS.items():
            current: Any = capabilities
            for part in path_parts:
                current = current.get(part) if isinstance(current, dict) else None
            if not current:
                payload["missing_capabilities"].append(name)
        inventory_by_path = {row["path"]: row for row in inventory}
        production = [root / row["path"] for row in inventory if row["role"] == "production"]
        callable_candidates: list[dict[str, Any]] = []
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
                callable_candidates.extend(
                    row
                    for row in _callable_symbols(
                        result, source.relative_to(root).as_posix()
                    )
                    if row["item"].get("name") in query_names
                )
            except (DartFactError, TimeoutError) as exc:
                payload["unresolved_requests"].append(
                    {
                        "method": "textDocument/documentSymbol",
                        "source": source.relative_to(root).as_posix(),
                        "reason": str(exc),
                    }
                )
        call_queries, call_unresolved = _collect_call_hierarchy(
            client,
            root,
            inventory_by_path,
            callable_candidates,
            available="call_hierarchy" not in payload["missing_capabilities"],
            timeout=timeout,
        )
        payload["call_hierarchy_queries"] = call_queries
        payload["unresolved_requests"].extend(call_unresolved)
        payload["call_hierarchy_summary"] = {
            "callers": len(call_queries),
            "complete": sum(row["status"] == "complete" for row in call_queries),
            "partial": sum(row["status"] == "partial" for row in call_queries),
            "resolved_edges": sum(len(row["outgoing_calls"]) for row in call_queries),
            "unresolved": sum(len(row["uncertainties"]) for row in call_queries),
        }
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
        call_hierarchy_uncertain = any(
            row["status"] != "complete" for row in payload["call_hierarchy_queries"]
        )
        if call_hierarchy_uncertain:
            partial_reasons.append("one or more outgoing call hierarchies are uncertain")
        if error_diagnostics:
            payload.update(status="failed", failure_kind="lsp_error_diagnostics")
        elif partial_reasons:
            payload.update(
                status="partial",
                failure_kind=payload.get("failure_kind")
                or (
                    "call_hierarchy_uncertainty"
                    if call_hierarchy_uncertain
                    else "semantic_boundary"
                ),
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
