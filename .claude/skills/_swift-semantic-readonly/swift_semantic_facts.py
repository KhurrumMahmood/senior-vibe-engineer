#!/usr/bin/env python3
"""Fresh SwiftPM/index/SourceKit-LSP facts for bounded read-only consumers.

This is a Swift-local union fact pack, not a universal semantic model. It owns
the selected SwiftPM package/target/configuration identity, restrictive native
gates, a fresh isolated index, and stable LSP document-symbol, reference,
definition, hover, prepare-rename, and call-hierarchy requests. Consumers own
their candidates, reviews, reports, and terminal status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlparse


SCHEMA_VERSION = "swift-semantic-facts-v1"
MINIMUM_SWIFT = (6, 0, 0)
ARTIFACT_DIRS = frozenset({".agents", ".build", ".git", ".swiftpm", "reports"})
BUILD_DIRS = frozenset({".build", "build", "dist", "out"})
GENERATED_DIRS = frozenset({"generated", "derivedsources", "gen"})
VENDOR_DIRS = frozenset({"vendor", "vendors", "third_party", "third-party"})
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
CALLABLE_KINDS = frozenset({6, 9, 12})
LIMITS = [
    "dependency-free SwiftPM regular library/executable targets in one selected debug or release configuration only",
    "a fresh successful restrictive build and fresh index-store units are required before SourceKit-LSP facts",
    "stable LSP symbols, references, definitions, hovers, prepare-rename, and call-hierarchy requests only; definition-location identities are used when SourceKit exposes no compiler USR",
    "conditional compilation, attached/freestanding macros, plugins, generated code, reflection, @objc/dynamic dispatch, and selectors are not expanded",
    "protocol/existential runtime dispatch, overload behavior, runtime reachability, side effects, and deletion/refactor safety remain unresolved",
    "Xcode projects/workspaces/schemes, Apple-framework behavior, resources, package dependencies, and mixed-language targets are outside this contract",
    "native XCTest and Testing modules remain unavailable under the active Command Line Tools; fixture-owned check and smoke executables are required",
    "ASCII identifier queries only; Unicode identifier spellings are not a selected consumer contract",
]


class SwiftFactError(ValueError):
    """An invalid or stale fact-pack handoff."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def safe_output(root: Path, supplied: Path, relative_root: str) -> Path:
    candidate = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(candidate))
    allowed = root / relative_root
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise SwiftFactError("unsafe_output", f"output must stay beneath {relative_root}/") from exc
    if not relative.parts:
        raise SwiftFactError("unsafe_output", "output must name a file")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise SwiftFactError("unsafe_output", "output must not traverse a symbolic link")
    return output


def _run(argv: list[str], cwd: Path, *, timeout: float = 240) -> subprocess.CompletedProcess[str]:
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


def _check(identifier: str, argv: list[str], result: subprocess.CompletedProcess[str]) -> dict:
    return {
        "id": identifier,
        "command": argv,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def _which(configured: str | Path) -> Path | None:
    path = Path(configured)
    if path.is_absolute():
        return path if path.is_file() and os.access(path, os.X_OK) else None
    resolved = shutil.which(str(path))
    return Path(resolved).resolve() if resolved else None


def _version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(?:Apple )?Swift version\s+(\d+)\.(\d+)(?:\.(\d+))?", text, re.I)
    if match is None:
        match = re.search(r"(?m)^\s*(\d+)\.(\d+)(?:\.(\d+))?\s*$", text)
    return tuple(int(value or 0) for value in match.groups()) if match else None


def _probe_version(path: Path | None, root: Path, name: str) -> dict[str, Any]:
    if path is None:
        return {"state": "missing", "failure_kind": f"{name}_missing"}
    result = _run([str(path), "--version"], root, timeout=20)
    rendered = result.stdout + result.stderr
    parsed = _version(rendered)
    if result.returncode:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}_version_failed",
            "detail": rendered.strip()[-2000:],
        }
    if parsed is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}_version_malformed",
            "detail": rendered.strip()[-2000:],
        }
    return {
        "state": "ready" if parsed >= MINIMUM_SWIFT else "too-old",
        "path": str(path),
        "version": ".".join(map(str, parsed)),
        "version_tuple": list(parsed),
        "failure_kind": None if parsed >= MINIMUM_SWIFT else f"{name}_too_old",
    }


def _snapshot(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for directory, directories, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        relative_parent = parent.relative_to(root)
        directories[:] = [
            name
            for name in directories
            if name not in ARTIFACT_DIRS and not (parent / name).is_symlink()
        ]
        for name in sorted(files):
            path = parent / name
            relative = (relative_parent / name).as_posix()
            if any(part in ARTIFACT_DIRS for part in Path(relative).parts):
                continue
            if path.is_symlink():
                rows[relative] = f"symlink:{os.readlink(path)}"
            elif path.is_file():
                rows[relative] = _sha256(path)
    return rows


def _manifest_hash(rows: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(rows.items()):
        digest.update(path.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest()


def _swiftpm_base(swift: Path, root: Path, state: Path) -> list[str]:
    return [
        str(swift),
        "package",
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
    ]


def _role_for_path(relative: Path) -> str:
    lowered = {part.lower() for part in relative.parts}
    if lowered & BUILD_DIRS:
        return "build"
    if lowered & GENERATED_DIRS:
        return "generated"
    if lowered & VENDOR_DIRS:
        return "vendor"
    if lowered & TEST_DIRS:
        return "test"
    return "unowned"


def _inventory(
    root: Path, description: dict[str, Any], target_name: str
) -> tuple[list[dict], list[Path], dict]:
    targets = description.get("targets", [])
    selected = next((row for row in targets if row.get("name") == target_name), None)
    if selected is None:
        raise SwiftFactError("target_not_found", f"SwiftPM target {target_name!r} was not found")
    if selected.get("type") not in {"library", "executable"}:
        raise SwiftFactError(
            "target_shape_outside_contract", "selected target must be a library or executable"
        )
    selected_sources: set[str] = set()
    consumer_sources: set[str] = set()
    declared_roles: dict[str, str] = {}
    for target in targets:
        base = str(target.get("path", "")).rstrip("/")
        sources = {f"{base}/{source}" for source in target.get("sources", [])}
        target_type = target.get("type")
        if target.get("name") == target_name:
            selected_sources.update(sources)
            role = "selected-production"
        elif target_type == "test":
            role = "test"
        elif target_name in target.get("target_dependencies", []):
            consumer_sources.update(sources)
            role = "selected-consumer"
        else:
            role = "other-target"
        for source in sources:
            declared_roles[source] = role
    rows: list[dict] = []
    seen: set[str] = set()
    for directory, directories, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        relative_parent = parent.relative_to(root)
        directories[:] = [name for name in directories if name != ".git"]
        for name in sorted(files):
            if not name.endswith(".swift"):
                continue
            path = parent / name
            relative = (relative_parent / name).as_posix()
            role = (
                "symlink-excluded"
                if path.is_symlink()
                else declared_roles.get(relative, _role_for_path(Path(relative)))
            )
            included = (
                role in {"selected-production", "selected-consumer"} and not path.is_symlink()
            )
            rows.append(
                {
                    "path": relative,
                    "role": role,
                    "included": included,
                    "sha256": _sha256(path) if path.is_file() and not path.is_symlink() else None,
                }
            )
            seen.add(relative)
    missing = sorted(selected_sources - seen)
    if missing:
        raise SwiftFactError(
            "selected_source_missing", f"selected SwiftPM sources are missing: {', '.join(missing)}"
        )
    unsafe = [
        row["path"]
        for row in rows
        if row["role"] == "symlink-excluded" and row["path"] in selected_sources
    ]
    if unsafe:
        raise SwiftFactError(
            "unsafe_selected_source", f"selected sources are symbolic links: {', '.join(unsafe)}"
        )
    semantic = [root / row["path"] for row in rows if row["included"]]
    rows.sort(key=lambda row: row["path"])
    return rows, semantic, selected


def _location(raw: dict[str, Any], root: Path) -> dict[str, Any] | None:
    uri = raw.get("targetUri") or raw.get("uri") or raw.get("location", {}).get("uri")
    if not isinstance(uri, str):
        return None
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return {"path": f"external:{uri}", "line": 0, "column": 0}
    path = Path(os.path.realpath(unquote(parsed.path)))
    try:
        rendered = path.relative_to(root).as_posix()
        external = False
    except ValueError:
        rendered = f"external:{path.name}"
        external = True
    location = (
        raw.get("targetSelectionRange")
        or raw.get("range")
        or raw.get("location", {}).get("range")
        or {}
    )
    start = location.get("start", {})
    return {
        "path": rendered,
        "line": int(start.get("line", 0)) + 1,
        "column": int(start.get("character", 0)) + 1,
        "external": external,
    }


def _call_item(raw: dict[str, Any], root: Path) -> dict[str, Any]:
    location = _location(raw, root) or {
        "path": "external:unknown",
        "line": 0,
        "column": 0,
        "external": True,
    }
    return {
        "name": raw.get("name"),
        "kind": raw.get("kind"),
        "symbol_id": raw.get("data", {}).get("usr"),
        **location,
    }


def _definition_semantic_id(location: dict[str, Any]) -> str | None:
    """Name a SourceKit-resolved declaration without inventing a compiler USR."""
    if location.get("external") or not location.get("path") or not location.get("line"):
        return None
    identity = {
        "path": location["path"],
        "line": location["line"],
        "column": location.get("column", 0),
    }
    return f"sourcekit-definition:{_canonical_hash(identity)}"


def _base_name(display: str | None) -> str:
    if not isinstance(display, str):
        return ""
    return display.split("(", 1)[0].split(".")[-1]


def _flatten_symbols(
    values: Any, source: str, role: str, parent: str | None = None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values or []:
        if not isinstance(value, dict):
            continue
        selection = value.get("selectionRange") or value.get("location", {}).get("range") or {}
        start = selection.get("start", {})
        display = value.get("name")
        row = {
            "name": _base_name(display),
            "display_name": display,
            "kind": value.get("kind"),
            "file": source,
            "role": role,
            "line": int(start.get("line", 0)) + 1,
            "column": int(start.get("character", 0)) + 1,
            "parent": parent,
            "top_level": parent is None,
            "detail": value.get("detail"),
        }
        rows.append(row)
        rows.extend(_flatten_symbols(value.get("children"), source, role, str(display)))
    return rows


class _LspClient:
    """Small JSON-RPC client using only standard LSP methods."""

    def __init__(self, argv: list[str], root: Path) -> None:
        self.root = root
        self.process = subprocess.Popen(
            argv,
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.stderr: list[bytes] = []
        self.pending: dict[int, dict[str, Any]] = {}
        self.request_id = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.error_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self.reader.start()
        self.error_reader.start()

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        while chunk := self.process.stderr.readline():
            self.stderr.append(chunk)

    def _read(self) -> None:
        assert self.process.stdout is not None
        try:
            while True:
                headers: dict[str, str] = {}
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        return
                    if line in {b"\r\n", b"\n"}:
                        break
                    if b":" not in line:
                        raise SwiftFactError("sourcekit_lsp_malformed", "malformed LSP header")
                    key, value = line.decode("ascii", errors="strict").split(":", 1)
                    headers[key.lower().strip()] = value.strip()
                length = int(headers.get("content-length", "-1"))
                if length < 0:
                    raise SwiftFactError(
                        "sourcekit_lsp_malformed", "LSP message omitted Content-Length"
                    )
                body = self.process.stdout.read(length)
                if len(body) != length:
                    raise SwiftFactError("sourcekit_lsp_malformed", "truncated LSP message")
                self.messages.put(json.loads(body.decode("utf-8")))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError, SwiftFactError) as exc:
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
            raise SwiftFactError("sourcekit_lsp_malformed", message["_reader_error"])
        if "id" in message and ("result" in message or "error" in message):
            self.pending[int(message["id"])] = message
            return
        if "id" not in message or "method" not in message:
            return
        method = message.get("method")
        if method == "workspace/configuration":
            result: Any = [{} for _ in message.get("params", {}).get("items", [])]
        elif method == "workspace/workspaceFolders":
            result = [{"uri": self.root.as_uri(), "name": self.root.name}]
        else:
            result = None
        self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})

    def request(self, method: str, params: Any, timeout: float = 60) -> Any:
        self.request_id += 1
        request_id = self.request_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self.pending.pop(request_id, None)
            if response is not None:
                if "error" in response:
                    raise SwiftFactError(
                        "sourcekit_lsp_request_failed", f"{method}: {response['error']}"
                    )
                return response.get("result")
            if self.process.poll() is not None:
                detail = b"".join(self.stderr).decode(errors="replace")[-2000:]
                raise SwiftFactError(
                    "sourcekit_lsp_failed",
                    f"SourceKit-LSP exited {self.process.returncode}: {detail}",
                )
            try:
                self._dispatch(self.messages.get(timeout=min(0.1, deadline - time.monotonic())))
            except queue.Empty:
                continue
        raise SwiftFactError("sourcekit_lsp_timeout", f"LSP request timed out: {method}")

    def close(self) -> dict[str, Any]:
        shutdown = False
        exited = False
        try:
            if self.process.poll() is None:
                self.request("shutdown", None, 10)
                shutdown = True
                self.notify("exit", None)
                self.process.wait(timeout=10)
                exited = True
        except (OSError, SwiftFactError, subprocess.TimeoutExpired):
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


def _capabilities(raw: dict[str, Any]) -> dict[str, bool]:
    rename = raw.get("renameProvider")
    return {
        "call_hierarchy": bool(raw.get("callHierarchyProvider")),
        "definition": bool(raw.get("definitionProvider")),
        "document_symbol": bool(raw.get("documentSymbolProvider")),
        "prepare_rename": bool(rename and (rename is True or rename.get("prepareProvider"))),
        "references": bool(raw.get("referencesProvider")),
    }


def _lsp_facts(
    sourcekit: Path,
    root: Path,
    scratch: Path,
    configuration: str,
    files: list[Path],
    roles: dict[str, str],
    queries: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    client = _LspClient(
        [
            str(sourcekit),
            "--configuration",
            configuration,
            "--scratch-path",
            str(scratch),
        ],
        root,
    )
    close: dict[str, Any] = {}
    try:
        initialized = client.request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": root.as_uri(),
                "capabilities": {
                    "workspace": {"workspaceFolders": True, "symbol": {}},
                    "textDocument": {
                        "callHierarchy": {"dynamicRegistration": False},
                        "definition": {"linkSupport": True},
                        "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                        "hover": {},
                        "references": {},
                        "rename": {"prepareSupport": True},
                    },
                },
                "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
            },
            60,
        )
        advertised = _capabilities(initialized.get("capabilities", {}))
        if not all(advertised.values()):
            raise SwiftFactError(
                "sourcekit_lsp_capability_gap",
                f"required stable LSP capabilities are missing: {advertised}",
            )
        client.notify("initialized", {})
        for source in files:
            client.notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": source.as_uri(),
                        "languageId": "swift",
                        "version": 1,
                        "text": source.read_text(encoding="utf-8"),
                    }
                },
            )
        symbols: list[dict[str, Any]] = []
        document_failures: list[str] = []
        for source in files:
            relative = source.relative_to(root).as_posix()
            try:
                raw = client.request(
                    "textDocument/documentSymbol",
                    {"textDocument": {"uri": source.as_uri()}},
                    60,
                )
            except SwiftFactError:
                document_failures.append(relative)
                continue
            symbols.extend(_flatten_symbols(raw, relative, roles[relative]))
        selected: list[dict[str, Any]] = []
        query_set = set(queries)
        for symbol in symbols:
            if symbol["name"] not in query_set:
                continue
            source = root / symbol["file"]
            position = {"line": symbol["line"] - 1, "character": symbol["column"] - 1}
            request = {"textDocument": {"uri": source.as_uri()}, "position": position}
            enriched = dict(symbol)
            prepared = client.request("textDocument/prepareCallHierarchy", request, 60)
            item = (prepared or [None])[0] if isinstance(prepared, list) else prepared
            enriched["symbol_id"] = item.get("data", {}).get("usr") if item else None
            definitions = client.request("textDocument/definition", request, 60)
            if isinstance(definitions, dict):
                definitions = [definitions]
            enriched["definitions"] = [
                location for row in definitions or [] if (location := _location(row, root))
            ]
            definition_ids = sorted(
                {
                    identity
                    for location in enriched["definitions"]
                    if (identity := _definition_semantic_id(location))
                }
            )
            enriched["semantic_id"] = definition_ids[0] if len(definition_ids) == 1 else None
            enriched["semantic_identity_kind"] = (
                "sourcekit-definition-location" if len(definition_ids) == 1 else None
            )
            references = client.request(
                "textDocument/references",
                {**request, "context": {"includeDeclaration": True}},
                60,
            )
            enriched["references"] = [
                location for row in references or [] if (location := _location(row, root))
            ]
            enriched["hover"] = client.request("textDocument/hover", request, 60)
            enriched["prepare_rename"] = client.request("textDocument/prepareRename", request, 60)
            enriched["call_hierarchy"] = {"incoming": [], "outgoing": []}
            if item and symbol.get("kind") in CALLABLE_KINDS:
                outgoing = client.request("callHierarchy/outgoingCalls", {"item": item}, 60)
                enriched["call_hierarchy"]["outgoing"] = [
                    {
                        "target": _call_item(row.get("to", {}), root),
                        "from_ranges": row.get("fromRanges", []),
                    }
                    for row in outgoing or []
                ]
                incoming = client.request("callHierarchy/incomingCalls", {"item": item}, 60)
                enriched["call_hierarchy"]["incoming"] = [
                    {
                        "caller": _call_item(row.get("from", {}), root),
                        "from_ranges": row.get("fromRanges", []),
                    }
                    for row in incoming or []
                ]
            selected.append(enriched)
        definition_occurrences: list[dict[str, Any]] = []
        for source in files:
            relative = source.relative_to(root).as_posix()
            for line_index, line in enumerate(source.read_text(encoding="utf-8").splitlines()):
                for query in queries:
                    for match in re.finditer(rf"\b{re.escape(query)}\b", line):
                        request = {
                            "textDocument": {"uri": source.as_uri()},
                            "position": {"line": line_index, "character": match.start()},
                        }
                        definitions = client.request("textDocument/definition", request, 60)
                        if isinstance(definitions, dict):
                            definitions = [definitions]
                        resolved = [
                            location
                            for row in definitions or []
                            if (location := _location(row, root))
                        ]
                        definition_occurrences.append(
                            {
                                "name": query,
                                "source": relative,
                                "line": line_index + 1,
                                "column": match.start() + 1,
                                "definitions": resolved,
                                "definition_semantic_ids": sorted(
                                    {
                                        identity
                                        for location in resolved
                                        if (identity := _definition_semantic_id(location))
                                    }
                                ),
                                "evidence": "textDocument/definition",
                            }
                        )
        semantic = {
            "state": "complete" if not document_failures else "partial",
            "protocol": "LSP",
            "unstable_cli_used": False,
            "capabilities": advertised,
            "document_failures": document_failures,
            "query_count": len(queries),
            "selected_symbol_count": len(selected),
        }
        return (
            semantic,
            selected,
            definition_occurrences,
            {"returncode": 0, "detail": "stable LSP requests completed"},
        )
    finally:
        close = client.close()
        if close and not close.get("exited_cleanly"):
            # Request facts can be valid even if shutdown cleanup was imperfect;
            # retain the exact process evidence without upgrading the claim.
            pass


def _terminal(
    root: Path, target_name: str, configuration: str, queries: list[str]
) -> dict[str, Any]:
    snapshot = _snapshot(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "language": "swift",
        "analyzer": "swiftpm-fresh-index+sourcekit-lsp-stable",
        "status": "partial",
        "failure_kind": None,
        "failure_detail": None,
        "read_only": True,
        "identity": {
            "target_name": target_name,
            "configuration": configuration,
            "package_sha256": _sha256(root / "Package.swift")
            if (root / "Package.swift").is_file()
            else None,
        },
        "query_names": sorted(set(queries)),
        "query_plan_sha256": _canonical_hash(sorted(set(queries))),
        "tools": {},
        "native_checks": [],
        "source_inventory": [],
        "source_hashes": [
            {"path": path, "sha256": value}
            for path, value in sorted(snapshot.items())
            if not value.startswith("symlink:")
        ],
        "source_manifest_sha256": _manifest_hash(snapshot),
        "index": {"fresh_scratch": False, "all_selected_sources_indexed": False},
        "semantic": {
            "state": "not-run",
            "capabilities": {
                "call_hierarchy": False,
                "definition": False,
                "document_symbol": False,
                "prepare_rename": False,
                "references": False,
            },
        },
        "symbols": [],
        "definition_occurrences": [],
        "limits": LIMITS,
    }


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    without_hash = dict(payload)
    without_hash.pop("fact_pack_sha256", None)
    payload["fact_pack_sha256"] = _canonical_hash(without_hash)
    return payload


def _tool_terminal(payload: dict[str, Any], tools: dict[str, Any]) -> bool:
    payload["tools"] = tools
    order = ("swift", "swiftc", "swift_format")
    for name in order:
        state = tools[name]["state"]
        if state == "ready":
            continue
        payload["status"] = "failed" if state == "failed" else "partial"
        payload["failure_kind"] = tools[name]["failure_kind"]
        payload["failure_detail"] = tools[name].get("detail")
        return True
    if tools["sourcekit_lsp"]["state"] != "ready":
        payload["status"] = "partial"
        payload["failure_kind"] = "sourcekit_lsp_missing"
        return True
    return False


def collect(
    root: Path,
    target_name: str,
    queries: Iterable[str],
    *,
    configuration: str = "debug",
    swift: str | Path = "swift",
    swiftc: str | Path = "swiftc",
    sourcekit_lsp: str | Path = "sourcekit-lsp",
    swift_format: str | Path = "swift-format",
    check_product: str,
    expected_check: str,
    smoke_product: str,
    expected_smoke: str,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Collect one content-bound selected-configuration semantic pack."""
    root = Path(os.path.realpath(root.resolve(strict=True)))
    query_names = sorted(
        {query for query in queries if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", query)}
    )
    payload = _terminal(root, target_name, configuration, query_names)
    if configuration not in {"debug", "release"}:
        payload.update(status="failed", failure_kind="configuration_invalid")
        return _finalize(payload)
    if not (root / "Package.swift").is_file():
        payload.update(status="partial", failure_kind="swiftpm_manifest_missing")
        return _finalize(payload)
    paths = {
        "swift": _which(swift),
        "swiftc": _which(swiftc),
        "sourcekit_lsp": _which(sourcekit_lsp),
        "swift_format": _which(swift_format),
    }
    tools = {
        "swift": _probe_version(paths["swift"], root, "swift"),
        "swiftc": _probe_version(paths["swiftc"], root, "swiftc"),
        "swift_format": _probe_version(paths["swift_format"], root, "swift_format"),
        "sourcekit_lsp": {
            "state": "ready" if paths["sourcekit_lsp"] else "missing",
            "path": str(paths["sourcekit_lsp"]) if paths["sourcekit_lsp"] else None,
            "executable_sha256": (
                _sha256(paths["sourcekit_lsp"]) if paths["sourcekit_lsp"] else None
            ),
            "failure_kind": None if paths["sourcekit_lsp"] else "sourcekit_lsp_missing",
        },
    }
    if _tool_terminal(payload, tools):
        return _finalize(payload)

    owned_state = state_dir is None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if owned_state:
        temporary = tempfile.TemporaryDirectory(prefix="swift-semantic-a3-")
        state = Path(temporary.name)
    else:
        state = Path(os.path.abspath(state_dir))
        if state.exists() and (state.is_symlink() or any(state.iterdir())):
            payload.update(status="partial", failure_kind="semantic_state_not_fresh")
            return _finalize(payload)
        state.mkdir(parents=True, exist_ok=True)
    payload["index"]["fresh_scratch"] = True
    try:
        for name in ("cache", "config", "security", "build"):
            (state / name).mkdir(parents=True, exist_ok=True)
        assert (
            paths["swift"] and paths["swiftc"] and paths["sourcekit_lsp"] and paths["swift_format"]
        )
        base = _swiftpm_base(paths["swift"], root, state)
        dump_argv = [*base, "dump-package"]
        dump = _run(dump_argv, root)
        payload["native_checks"].append(_check("swiftpm-dump-package", dump_argv, dump))
        if dump.returncode:
            payload.update(
                status="failed",
                failure_kind="swiftpm_dump_failed",
                failure_detail=(dump.stderr or dump.stdout)[-2000:],
            )
            return _finalize(payload)
        try:
            manifest = json.loads(dump.stdout)
        except json.JSONDecodeError as exc:
            payload.update(
                status="failed", failure_kind="swiftpm_dump_invalid", failure_detail=str(exc)
            )
            return _finalize(payload)
        if manifest.get("dependencies"):
            payload.update(status="partial", failure_kind="swiftpm_dependencies_outside_contract")
            return _finalize(payload)
        if any(row.get("resources") or row.get("settings") for row in manifest.get("targets", [])):
            payload.update(
                status="partial", failure_kind="swiftpm_settings_or_resources_outside_contract"
            )
            return _finalize(payload)

        describe_argv = [*base, "describe", "--type", "json"]
        describe = _run(describe_argv, root)
        payload["native_checks"].append(_check("swiftpm-describe", describe_argv, describe))
        if describe.returncode:
            payload.update(
                status="failed",
                failure_kind="swiftpm_describe_failed",
                failure_detail=(describe.stderr or describe.stdout)[-2000:],
            )
            return _finalize(payload)
        try:
            description = json.loads(describe.stdout)
        except json.JSONDecodeError as exc:
            payload.update(
                status="failed", failure_kind="swiftpm_describe_invalid", failure_detail=str(exc)
            )
            return _finalize(payload)
        if any(
            row.get("type") not in {"library", "executable", "test"}
            for row in description.get("targets", [])
        ):
            payload.update(status="partial", failure_kind="swiftpm_target_shape_outside_contract")
            return _finalize(payload)
        try:
            inventory, semantic_files, selected = _inventory(root, description, target_name)
        except SwiftFactError as exc:
            payload.update(status="partial", failure_kind=exc.kind, failure_detail=str(exc))
            return _finalize(payload)
        payload["source_inventory"] = inventory
        before = _snapshot(root)
        payload["source_hashes"] = [
            {"path": path, "sha256": value}
            for path, value in sorted(before.items())
            if not value.startswith("symlink:")
        ]
        payload["source_manifest_sha256"] = _manifest_hash(before)
        target_graph = [
            {
                "name": row.get("name"),
                "type": row.get("type"),
                "path": row.get("path"),
                "sources": row.get("sources", []),
                "target_dependencies": row.get("target_dependencies", []),
            }
            for row in description.get("targets", [])
        ]
        payload["identity"] = {
            "package_name": description.get("name"),
            "package_sha256": _sha256(root / "Package.swift"),
            "tools_version": description.get("tools_version"),
            "target_name": target_name,
            "target_type": selected.get("type"),
            "target_path": selected.get("path"),
            "target_sources": selected.get("sources", []),
            "target_graph_sha256": _canonical_hash(target_graph),
            "configuration": configuration,
            "toolchain_sha256": _canonical_hash(tools),
        }

        build_argv = [
            str(paths["swift"]),
            "build",
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
            "--configuration",
            configuration,
            "--enable-index-store",
        ]
        build_started_ns = time.time_ns()
        build = _run(build_argv, root)
        build_finished_ns = time.time_ns()
        payload["native_checks"].append(_check("swiftpm-build-index", build_argv, build))
        if build.returncode:
            payload.update(
                status="failed",
                failure_kind="swiftpm_build_failed",
                failure_detail=(build.stdout + build.stderr)[-3000:],
            )
            return _finalize(payload)
        units = [
            path
            for path in (state / "build").rglob("*")
            if path.is_file() and "index/store" in path.as_posix() and "/units/" in path.as_posix()
        ]
        selected_files = [
            root / row["path"] for row in inventory if row["role"] == "selected-production"
        ]
        covered = {
            source.relative_to(root).as_posix(): any(
                path.name.startswith(f"{source.name}.o-") for path in units
            )
            for source in selected_files
        }
        fresh_units = bool(units) and all(
            path.stat().st_mtime_ns >= build_started_ns - 2_000_000_000 for path in units
        )
        index_ok = bool(covered) and all(covered.values()) and fresh_units
        payload["index"].update(
            {
                "build_started_ns": build_started_ns,
                "build_finished_ns": build_finished_ns,
                "unit_count": len(units),
                "selected_source_units": covered,
                "all_selected_sources_indexed": index_ok,
                "recent_build_required": True,
            }
        )
        index_result = subprocess.CompletedProcess(
            ["fresh-index-units"], 0 if index_ok else 1, json.dumps(covered), ""
        )
        payload["native_checks"].append(
            _check("fresh-index-units", ["fresh-index-units"], index_result)
        )
        if not index_ok:
            payload.update(status="partial", failure_kind="fresh_index_missing_or_incomplete")
            return _finalize(payload)

        parse_argv = [str(paths["swiftc"]), "-frontend", "-parse", "<each-selected-source>"]
        parse_runs = [
            _run([str(paths["swiftc"]), "-frontend", "-parse", str(source)], root)
            for source in semantic_files
        ]
        parse = subprocess.CompletedProcess(
            parse_argv,
            next((row.returncode for row in parse_runs if row.returncode), 0),
            "\n".join(row.stdout for row in parse_runs),
            "\n".join(row.stderr for row in parse_runs),
        )
        payload["native_checks"].append(_check("compiler-parse", parse_argv, parse))
        if parse.returncode:
            payload.update(
                status="failed",
                failure_kind="compiler_parse_failed",
                failure_detail=parse.stderr[-2000:],
            )
            return _finalize(payload)

        format_argv = [str(paths["swift_format"]), "lint", "--strict", "--recursive", "Sources"]
        formatted = _run(format_argv, root)
        payload["native_checks"].append(_check("swift-format-lint", format_argv, formatted))
        if formatted.returncode:
            payload.update(
                status="failed",
                failure_kind="swift_format_failed",
                failure_detail=(formatted.stdout + formatted.stderr)[-3000:],
            )
            return _finalize(payload)
        for identifier, product, expected in (
            ("direct-check", check_product, expected_check),
            ("executable-smoke", smoke_product, expected_smoke),
        ):
            executable = state / "build" / configuration / product
            run = _run([str(executable)], root, timeout=30)
            payload["native_checks"].append(_check(identifier, [str(executable)], run))
            if run.returncode or run.stdout.strip() != expected:
                payload.update(
                    status="failed",
                    failure_kind=f"{identifier.replace('-', '_')}_failed",
                    failure_detail=(run.stdout + run.stderr)[-2000:],
                )
                return _finalize(payload)

        roles = {row["path"]: row["role"] for row in inventory}
        try:
            semantic, symbols, definition_occurrences, lsp_result = _lsp_facts(
                paths["sourcekit_lsp"],
                root,
                state / "build",
                configuration,
                semantic_files,
                roles,
                query_names,
            )
        except SwiftFactError as exc:
            semantic = {
                "state": "partial",
                "failure_kind": exc.kind,
                "detail": str(exc),
                "capabilities": payload["semantic"]["capabilities"],
            }
            symbols = []
            definition_occurrences = []
            lsp_result = {"returncode": 1, "detail": str(exc)}
        lsp_check = subprocess.CompletedProcess(
            [str(paths["sourcekit_lsp"])],
            lsp_result["returncode"],
            lsp_result.get("detail", ""),
            "",
        )
        payload["native_checks"].append(
            _check("sourcekit-lsp", [str(paths["sourcekit_lsp"]), "<stable-lsp>"], lsp_check)
        )
        payload["semantic"] = semantic
        payload["symbols"] = symbols
        payload["definition_occurrences"] = definition_occurrences
        if semantic.get("state") != "complete":
            payload.update(
                status="partial",
                failure_kind=semantic.get("failure_kind", "sourcekit_lsp_incomplete"),
                failure_detail=semantic.get("detail"),
            )
        else:
            payload.update(status="complete", failure_kind=None, failure_detail=None)
        after = _snapshot(root)
        if before != after:
            payload.update(
                status="failed",
                failure_kind="unexpected_source_mutation",
                failure_detail="native semantic analysis changed a non-artifact host file",
            )
        payload["source_preserved"] = before == after
        return _finalize(payload)
    finally:
        if temporary is not None:
            temporary.cleanup()


def load_fact_pack(
    path: Path,
    root: Path,
    target_name: str,
    required_queries: Iterable[str],
) -> dict[str, Any]:
    """Validate a supplied fact pack against source/configuration and query scope."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SwiftFactError("fact_pack_invalid", f"cannot read fact pack: {exc}") from exc
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SwiftFactError("fact_pack_invalid", "incompatible Swift semantic fact pack")
    supplied = payload.get("fact_pack_sha256")
    without_hash = dict(payload)
    without_hash.pop("fact_pack_sha256", None)
    if supplied != _canonical_hash(without_hash):
        raise SwiftFactError("fact_pack_invalid", "Swift semantic fact pack hash does not verify")
    if payload.get("identity", {}).get("target_name") != target_name:
        raise SwiftFactError(
            "fact_pack_scope_mismatch", "fact pack target does not match consumer target"
        )
    missing = sorted(set(required_queries) - set(payload.get("query_names", [])))
    if missing:
        raise SwiftFactError(
            "fact_pack_scope_mismatch", f"fact pack misses required queries: {', '.join(missing)}"
        )
    root = Path(os.path.realpath(root.resolve(strict=True)))
    if _manifest_hash(_snapshot(root)) != payload.get("source_manifest_sha256"):
        raise SwiftFactError("fact_pack_stale", "fact pack source manifest is stale")
    for row in payload.get("source_hashes", []):
        source = root / row.get("path", "")
        if not source.is_file() or source.is_symlink() or _sha256(source) != row.get("sha256"):
            raise SwiftFactError("fact_pack_stale", f"fact pack is stale for {row.get('path')}")
    package = root / "Package.swift"
    if not package.is_file() or _sha256(package) != payload.get("identity", {}).get(
        "package_sha256"
    ):
        raise SwiftFactError("fact_pack_stale", "fact pack package configuration is stale")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--configuration", choices=("debug", "release"), default="debug")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--swift", default="swift")
    parser.add_argument("--swiftc", default="swiftc")
    parser.add_argument("--sourcekit-lsp", default="sourcekit-lsp")
    parser.add_argument("--swift-format", default="swift-format")
    parser.add_argument("--check-product", required=True)
    parser.add_argument("--expected-check", required=True)
    parser.add_argument("--smoke-product", required=True)
    parser.add_argument("--expected-smoke", required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
        output = safe_output(root, args.output, "reports/swift-semantic-facts")
        payload = collect(
            root,
            args.target_name,
            args.query,
            configuration=args.configuration,
            swift=args.swift,
            swiftc=args.swiftc,
            sourcekit_lsp=args.sourcekit_lsp,
            swift_format=args.swift_format,
            check_product=args.check_product,
            expected_check=args.expected_check,
            smoke_product=args.smoke_product,
            expected_smoke=args.expected_smoke,
            state_dir=args.state_dir,
        )
        atomic_json(output, payload)
        print(f"wrote Swift semantic fact pack: {output}")
        return 2 if payload["status"] == "failed" else 0
    except (OSError, SwiftFactError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
