#!/usr/bin/env python3
"""Copied Ruby project/lexical facts for five read-only consumers.

Own only the facts shared by the Ruby A1 family: source roles and hashes,
Ruby/Bundler/Prism preflight, per-file syntax, a frozen local bundle check,
explicit native test/smoke evidence, and direct Prism declaration/method spans.
Consumers retain their final schemas and interpretations. Syntax is never
promoted to runtime identity, reachability, visibility, or behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_RUBY = (3, 3, 0)
MINIMUM_BUNDLER = (2, 6, 0)
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen"})
BUILD_DIRS = frozenset({"build", "dist", "out", "tmp", "target", ".bundle"})
REPORT_DIRS = frozenset({"reports", "report"})
CONFIG_NAMES = frozenset(
    {"Gemfile", "Gemfile.lock", "gems.rb", "gems.locked", "Rakefile", ".ruby-version"}
)
CONFIG_SUFFIXES = frozenset({".gemspec", ".rake", ".ru"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
RUBY_SHEBANG_RE = re.compile(rb"^\#![^\n]*\bruby(?:\s|$)")

RUBY_PROVIDER = r'''# frozen_string_literal: true
require "json"
require "prism"

path = ARGV.fetch(0)
result = Prism.parse_file(path)
unless result.success?
  STDOUT.write(JSON.generate({success: false, errors: result.errors.map(&:message)}))
  exit 2
end

class LexicalCollector
  attr_reader :declarations, :methods, :dynamic

  def initialize
    @declarations = []
    @methods = []
    @dynamic = []
  end

  def location(node)
    value = node.location
    {
      start_offset: value.start_offset,
      end_offset: value.end_offset,
      start_line: value.start_line,
      start_column: value.start_column,
      end_line: value.end_line,
      end_column: value.end_column,
    }
  end

  def qualify(spelling, scopes)
    return spelling.sub(/\A::/, "") if spelling.start_with?("::")
    return spelling if spelling.include?("::") || scopes.empty?
    "#{scopes.last}::#{spelling}"
  end

  def visit(node, scopes = [], owner = nil)
    return unless node
    case node
    when Prism::ModuleNode, Prism::ClassNode
      spelling = node.constant_path.slice
      qualified = qualify(spelling, scopes)
      kind = node.is_a?(Prism::ClassNode) ? "class" : "module"
      @declarations << location(node).merge(
        kind: kind,
        spelling: spelling,
        qualified_name: qualified,
        visibility: "runtime-unresolved",
      )
      visit(node.body, scopes + [qualified], qualified)
    when Prism::DefNode
      receiver = node.receiver
      method_owner = owner || "<top-level>"
      method_owner = receiver.slice if receiver
      @methods << location(node).merge(
        name: node.name.to_s,
        owner: method_owner,
        singleton: !receiver.nil?,
        visibility: "runtime-unresolved",
        body: node.body ? node.body.slice : "",
      )
      @dynamic << location(node).merge(kind: "method-missing", operation: "def") if node.name.to_s == "method_missing"
      visit(node.parameters, scopes, method_owner)
      visit(node.body, scopes, method_owner)
    when Prism::CallNode
      name = node.name.to_s
      kind = case name
      when "require", "require_relative", "load" then
        arguments = node.arguments&.arguments || []
        literal = arguments.length == 1 && arguments.first.is_a?(Prism::StringNode)
        literal ? nil : "dynamic-load"
      when "autoload" then "autoload"
      when "const_get", "const_missing" then "runtime-constant-reflection"
      when "send", "public_send", "__send__" then "dynamic-send"
      when "define_method" then "define-method"
      when "eval", "class_eval", "module_eval", "instance_eval" then "eval-family"
      when "prepend", "include", "extend" then "runtime-mixin"
      end
      if kind.nil? && name.match?(/\A(?:before|after|around)_(?:action|save|create|update|destroy|commit|validation)\z/)
        kind = "framework-callback"
      end
      @dynamic << location(node).merge(kind: kind, operation: name) if kind
      node.child_nodes.compact.each { |child| visit(child, scopes, owner) }
    else
      node.child_nodes.compact.each { |child| visit(child, scopes, owner) }
    end
  end
end

collector = LexicalCollector.new
collector.visit(result.value)
STDOUT.write(JSON.generate({
  success: true,
  prism_version: Prism::VERSION,
  declarations: collector.declarations,
  methods: collector.methods,
  dynamic: collector.dynamic,
}))
'''


def add_snapshot_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ruby", type=Path, default=Path("ruby"))
    parser.add_argument("--bundler", type=Path, default=Path("bundle"))
    parser.add_argument("--test", help="Project-relative dependency-free Ruby test file")
    parser.add_argument("--smoke", help="Project-relative dependency-free Ruby smoke file")


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def clear_artifacts(paths: Iterable[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _which(configured: Path) -> Path | None:
    if configured.is_absolute():
        return configured
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory or ".") / configured
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def _probe(
    configured: Path,
    name: str,
    minimum: tuple[int, int, int],
    root: Path,
) -> dict[str, Any]:
    path = _which(configured)
    if path is None or not path.is_file() or not os.access(path, os.X_OK):
        return {"state": "missing", "failure_kind": f"{name}-tool-missing"}
    result = _run([str(path), "--version"], root, timeout=10)
    if result.returncode:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-failed",
            "detail": (result.stderr or result.stdout).strip(),
        }
    label = "Bundler version" if name == "bundler" else "ruby"
    match = re.search(rf"\b{re.escape(label)}\s+(\d+)\.(\d+)\.(\d+)", result.stdout, re.I)
    if match is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-unrecognized",
            "detail": result.stdout.strip(),
        }
    version = tuple(map(int, match.groups()))
    ready = version >= minimum
    return {
        "state": "ready" if ready else "too-old",
        "path": str(path),
        "version": ".".join(match.groups()),
        "minimum_version": ".".join(map(str, minimum)),
        **({"failure_kind": f"{name}-version-too-old"} if not ready else {}),
    }


def _ruby_input(path: Path) -> bool:
    if path.suffix.casefold() == ".rb":
        return True
    try:
        with path.open("rb") as handle:
            return RUBY_SHEBANG_RE.search(handle.readline(512)) is not None
    except OSError:
        return False


def _role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if "vendor" in parts:
        return "excluded", "vendor"
    if parts & REPORT_DIRS:
        return "excluded", "report"
    if parts & BUILD_DIRS:
        return "excluded", "build"
    if parts & TEST_DIRS or name.endswith("_test.rb") or name.startswith("test_"):
        return "test", "test"
    if parts & GENERATED_DIRS:
        return "excluded", "generated"
    if relative.parts and relative.parts[0] == "bin":
        return "entrypoint", "entrypoint"
    if GENERATED_RE.search(text[:4096]):
        return "excluded", "generated-marker"
    return "candidate", None


def _logical_targets(root: Path, targets: Iterable[str]) -> tuple[list[Path], list[str]]:
    selected: list[Path] = []
    errors: list[str] = []
    for raw in targets:
        path = Path(raw)
        path = path if path.is_absolute() else root / path
        path = Path(os.path.abspath(path))
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"target-outside-project:{raw}")
            continue
        if not path.exists() and not path.is_symlink():
            errors.append(f"target-missing:{raw}")
            continue
        selected.append(path)
    return selected, errors


def _is_selected(path: Path, targets: list[Path]) -> bool:
    for target in targets:
        if target.is_symlink() or target.is_file():
            if path == target:
                return True
            continue
        try:
            path.relative_to(target)
            return True
        except ValueError:
            continue
    return False


def _inventory(root: Path, targets: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    selected, errors = _logical_targets(root, targets)
    paths: dict[str, Path] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        symlink_dirs = [name for name in dirnames if (current / name).is_symlink()]
        for name in symlink_dirs:
            path = current / name
            paths[path.relative_to(root).as_posix()] = path
        dirnames[:] = sorted(name for name in dirnames if name not in symlink_dirs)
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink() or _ruby_input(path) or name in CONFIG_NAMES or path.suffix in CONFIG_SUFFIXES:
                paths[path.relative_to(root).as_posix()] = path

    inventory: list[dict[str, Any]] = []
    for relative, path in sorted(paths.items()):
        if path.is_symlink():
            inventory.append(
                {
                    "file": relative,
                    "role": "excluded",
                    "reason": "symlink",
                    "selected": _is_selected(path, selected),
                    "_path": path,
                }
            )
            continue
        try:
            source = path.read_bytes()
            text = source.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            inventory.append(
                {
                    "file": relative,
                    "role": "failed",
                    "reason": "read-error",
                    "detail": str(exc),
                    "selected": _is_selected(path, selected),
                    "_path": path,
                }
            )
            continue
        if path.name in CONFIG_NAMES or path.suffix in CONFIG_SUFFIXES:
            role, reason = "configuration", "configuration"
        else:
            role, reason = _role(path, root, text)
        inventory.append(
            {
                "file": relative,
                "role": role,
                **({"reason": reason} if reason else {}),
                "selected": _is_selected(path, selected),
                "source_sha256": hash_bytes(source),
                "source_bytes": len(source),
                "_path": path,
                "_source": source,
            }
        )
    return inventory, errors


def _manifest(inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    rows = [
        {
            "file": row["file"],
            "source_sha256": row["source_sha256"],
            "source_bytes": row["source_bytes"],
        }
        for row in inventory
        if "source_sha256" in row
    ]
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["file"].encode() + b"\0" + row["source_sha256"].encode() + b"\n")
    return rows, digest.hexdigest()


def _span(location: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_byte": location["start_offset"],
        "end_byte": location["end_offset"],
        "start": {"line": location["start_line"], "column": location["start_column"] + 1},
        "end": {"line": location["end_line"], "column": location["end_column"] + 1},
    }


def declaration_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    facts = []
    for item in row.get("_prism", {}).get("declarations", []):
        start, end = item["start_offset"], item["end_offset"]
        facts.append(
            {
                "symbol": item["qualified_name"],
                "kind": item["kind"],
                "visibility": "runtime-unresolved",
                "file": row["file"],
                "span": _span(item),
                "source_sha256": row["source_sha256"],
                "spelling_sha256": hash_bytes(source[start:end]),
            }
        )
    facts.extend(method_facts(row))
    return sorted(facts, key=lambda fact: (fact["file"], fact["span"]["start_byte"], fact["symbol"]))


def method_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    facts = []
    for item in row.get("_prism", {}).get("methods", []):
        start, end = item["start_offset"], item["end_offset"]
        body = re.sub(r"\s+", " ", item.get("body", "").strip())
        symbol = f"{item['owner']}#{item['name']}"
        facts.append(
            {
                "symbol": symbol,
                "method_name": item["name"],
                "owner": item["owner"],
                "kind": "method",
                "visibility": "runtime-unresolved",
                "file": row["file"],
                "span": _span(item),
                "line_count": item["end_line"] - item["start_line"] + 1,
                "source_sha256": row["source_sha256"],
                "spelling_sha256": hash_bytes(source[start:end]),
                "normalized_body": body,
                "normalized_body_sha256": hash_bytes(body.encode()),
            }
        )
    return facts


def public_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (
            [{k: v for k, v in row.items() if not k.startswith("_")} for row in value]
            if key == "inventory"
            else value
        )
        for key, value in snapshot.items()
        if not key.startswith("_")
    }


def sources_preserved(snapshot: dict[str, Any]) -> bool:
    for row in snapshot["inventory"]:
        path = row.get("_path")
        if row.get("source_sha256") and isinstance(path, Path):
            try:
                if hash_bytes(path.read_bytes()) != row["source_sha256"]:
                    return False
            except OSError:
                return False
    return True


def terminal_return_code(snapshot: dict[str, Any]) -> int:
    if snapshot["status"] == "failed":
        return 1
    if snapshot["status"] == "partial":
        return 2
    return 0


def _safe_project_file(root: Path, raw: str) -> Path | None:
    path = Path(raw)
    path = path if path.is_absolute() else root / path
    path = Path(os.path.abspath(path))
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file() or path.is_symlink():
        return None
    current = path.parent
    while current != root:
        if current.is_symlink():
            return None
        current = current.parent
    return path


def collect_snapshot(
    project_root: Path,
    targets: Iterable[str],
    *,
    ruby: Path,
    bundler: Path,
    test: str | None,
    smoke: str | None,
) -> dict[str, Any]:
    """Collect one immutable Ruby project/lexical snapshot."""
    root = project_root.resolve()
    inventory, errors = _inventory(root, targets)
    manifest, manifest_hash = _manifest(inventory)
    tools = {
        "ruby": _probe(ruby, "ruby", MINIMUM_RUBY, root),
        "bundler": _probe(bundler, "bundler", MINIMUM_BUNDLER, root),
    }
    snapshot: dict[str, Any] = {
        "language": "ruby",
        "analyzer": "ruby-project-lexical-prism-v1",
        "status": "complete",
        "inventory": inventory,
        "errors": errors,
        "tools": tools,
        "source_manifest": manifest,
        "source_manifest_sha256": manifest_hash,
        "source_preserved": True,
        "limits": [
            "Prism syntax and spelling are not runtime constant, method, visibility, or call identity",
            "dynamic require/load, load-path mutation, autoload, Rails, and Zeitwerk are unresolved",
            "class/module reopening, monkey patches, refinements, and execution order are unresolved",
            "send/public_send, const_get/const_missing, method_missing, eval, and define_method are unresolved",
            "reflection, callbacks, native extensions, and runtime-generated code are unresolved",
        ],
    }
    bad = [tool for tool in tools.values() if tool["state"] != "ready"]
    if bad:
        first = bad[0]
        snapshot.update(
            status="failed" if first["state"] == "failed" else "partial",
            failure_kind=first["failure_kind"],
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": len(bad)},
        )
        return snapshot
    gemspecs = sorted(root.glob("*.gemspec"))
    if not (root / "Gemfile").is_file() or not (root / "Gemfile.lock").is_file() or not gemspecs:
        snapshot.update(
            status="partial",
            failure_kind="ruby-project-incomplete",
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        return snapshot

    ruby_path = tools["ruby"]["path"]
    prism = _run(
        [ruby_path, "--disable-gems", "-rprism", "-e", "puts Prism::VERSION"],
        root,
        timeout=10,
    )
    if prism.returncode or not re.fullmatch(r"\d+(?:\.\d+){1,2}\n?", prism.stdout):
        snapshot.update(
            status="failed",
            failure_kind="prism-probe-failed",
            native_detail=(prism.stderr or prism.stdout).strip(),
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        return snapshot
    snapshot["prism"] = {"version": prism.stdout.strip(), "source": "selected Ruby bundled/default Prism"}

    with tempfile.TemporaryDirectory(prefix="ruby-project-lexical-") as temporary:
        state = Path(temporary)
        env = os.environ.copy()
        env.update(
            BUNDLE_APP_CONFIG=str(state / "bundle-config"),
            BUNDLE_DISABLE_VERSION_CHECK="true",
            BUNDLE_FROZEN="true",
            BUNDLE_GEMFILE=str(root / "Gemfile"),
            BUNDLE_USER_HOME=str(state / "bundle-home"),
            ALL_PROXY="http://127.0.0.1:9",
            http_proxy="http://127.0.0.1:9",
            https_proxy="http://127.0.0.1:9",
        )
        bundle_result = _run([tools["bundler"]["path"], "check"], root, env=env, timeout=30)
    snapshot["bundle_check"] = {
        "command": "bundle check (frozen, isolated config, no install/update)",
        "returncode": bundle_result.returncode,
    }
    if bundle_result.returncode:
        snapshot.update(
            status="failed",
            failure_kind="bundle-check-failed",
            native_detail=(bundle_result.stderr or bundle_result.stdout).strip()[-4000:],
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        return snapshot

    syntax_rows = [row for row in inventory if row["role"] in {"candidate", "test", "entrypoint"}]
    syntax_checks = []
    for row in syntax_rows:
        result = _run([ruby_path, "--disable-gems", "-c", str(row["_path"])], root, timeout=20)
        syntax_checks.append({"file": row["file"], "returncode": result.returncode})
        if result.returncode:
            row.update(role="failed", reason="syntax-error", detail=(result.stderr or result.stdout).strip())
            errors.append(f"{row['file']}:syntax-error")
    snapshot["syntax_checks"] = syntax_checks

    eligible = [row for row in inventory if row["role"] == "candidate" and row["selected"]]
    provider_failures = 0
    dynamic_signals = []
    for row in eligible:
        provided = _run(
            [ruby_path, "--disable-gems", "-rjson", "-rprism", "-e", RUBY_PROVIDER, str(row["_path"])],
            root,
            timeout=30,
        )
        if provided.returncode:
            row.update(role="failed", reason="prism-provider-failed", detail=(provided.stderr or provided.stdout).strip())
            errors.append(f"{row['file']}:prism-provider-failed")
            provider_failures += 1
            continue
        try:
            payload = json.loads(provided.stdout)
            if payload.get("success") is not True or not all(
                isinstance(payload.get(key), list) for key in ("declarations", "methods", "dynamic")
            ):
                raise ValueError("provider payload lacks successful Prism facts")
        except (json.JSONDecodeError, ValueError) as exc:
            row.update(role="failed", reason="prism-provider-invalid", detail=str(exc))
            errors.append(f"{row['file']}:prism-provider-invalid")
            provider_failures += 1
            continue
        row.update(role="eligible", native_syntax="ruby-c+prism", _prism=payload)
        dynamic_signals.extend({**item, "file": row["file"]} for item in payload["dynamic"])

    native: dict[str, Any] = {}
    for kind, raw in (("test", test), ("smoke", smoke)):
        if not raw:
            native[kind] = {"status": "not-run", "path": None}
            continue
        path = _safe_project_file(root, raw)
        if path is None:
            snapshot.update(status="failed", failure_kind=f"native-{kind}-unsafe")
            native[kind] = {"status": "failed", "path": raw, "returncode": 2}
            continue
        result = _run([ruby_path, "--disable-gems", f"-I{root / 'lib'}", str(path)], root, timeout=30)
        native[kind] = {
            "status": "passed" if result.returncode == 0 else "failed",
            "path": path.relative_to(root).as_posix(),
            "returncode": result.returncode,
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:4000],
        }
        if result.returncode:
            snapshot.update(status="failed", failure_kind=f"native-{kind}-failed")
    snapshot["native"] = native
    snapshot["dynamic_signals"] = sorted(
        dynamic_signals, key=lambda item: (item["file"], item["start_line"], item["kind"])
    )

    completed = sum(row["role"] == "eligible" for row in inventory)
    excluded = sum(row["role"] in {"excluded", "test", "entrypoint", "configuration"} for row in inventory)
    failed = sum(row["role"] == "failed" for row in inventory) + sum(
        error.startswith("target-") for error in errors
    )
    if snapshot["status"] != "failed":
        if provider_failures and completed == 0:
            snapshot.update(status="failed", failure_kind="prism-provider-failed")
        elif failed:
            snapshot.update(status="partial", failure_kind="ruby-source-incomplete")
        elif not eligible:
            snapshot.update(status="partial", failure_kind="no-eligible-ruby-files")
        elif not test or not smoke:
            snapshot.update(status="partial", failure_kind="native-gates-incomplete")
    snapshot["errors"] = errors
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    snapshot["summary"] = {
        "discovered": len(inventory),
        "eligible": completed,
        "excluded": excluded,
        "failed": failed,
    }
    return snapshot
