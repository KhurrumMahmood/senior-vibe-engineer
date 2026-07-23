#!/usr/bin/env python3
"""Collect the deliberately small RBS-backed Ruby A3 fact pack.

The pack's semantic authority is an already-authored ``sig/**/*.rbs`` tree
validated by the project's RBS command.  Prism is used only to correlate
source spans and to expose dynamic boundaries; it never resolves a Ruby call,
constant, load path, or runtime type.  Consumers own their own reports and
their own review verdicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "ruby-rbs-semantic-facts-v1"
MINIMUM_RUBY = (3, 3, 0)
MINIMUM_BUNDLER = (2, 6, 0)
MINIMUM_RBS = (3, 4, 0)
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen", "__generated__"})
VENDOR_DIRS = frozenset({"vendor", "vendors", "third_party", "third-party", "deps"})
BUILD_DIRS = frozenset({"build", "dist", "out", "tmp", "target", ".bundle"})
IGNORED_DIRS = frozenset({".git", ".agents", "reports", ".bundle"})
CONFIG_NAMES = frozenset(
    {"Gemfile", "Gemfile.lock", "gems.rb", "gems.locked", "Rakefile", ".ruby-version"}
)
CONFIG_SUFFIXES = frozenset({".gemspec", ".rake", ".ru"})
DYNAMIC_NAMES = frozenset(
    {
        "send",
        "public_send",
        "__send__",
        "const_get",
        "const_missing",
        "method_missing",
        "define_method",
        "eval",
        "class_eval",
        "module_eval",
        "instance_eval",
        "autoload",
    }
)
LIMITS = [
    "RBS declarations are project-authored contract evidence, not proof that Ruby source implements or dispatches them at runtime.",
    "Prism source spans are syntax correlations only; they do not resolve constants, receivers, overloads, aliases, or calls.",
    "Dynamic dispatch, send/public_send, const_get/const_missing, method_missing, callbacks, reflection, eval, define_method, refinements, reopening, monkey patches, and runtime-generated code remain explicit boundaries.",
    "Dynamic require/load, $LOAD_PATH changes, autoload, Rails, Zeitwerk, framework DSLs, externally invoked APIs, native extensions, and configuration-dependent behavior remain unresolved.",
    "No report certifies deletion safety, closed state domains, behavioral equivalence, refactor safety, or a complete rename.",
]


PRISM_COLLECTOR = r'''# frozen_string_literal: true
require "json"
require "prism"

path = ARGV.fetch(0)
result = Prism.parse_file(path)
unless result.success?
  STDOUT.write(JSON.generate({success: false, errors: result.errors.map(&:message)}))
  exit 2
end

class A3Collector
  DYNAMIC = %w[send public_send __send__ const_get const_missing method_missing define_method eval class_eval module_eval instance_eval autoload].freeze

  def initialize
    @classes = []
    @methods = []
    @calls = []
    @writes = []
    @dynamic = []
    @mixins = []
  end

  def location(node)
    value = node.location
    {
      start_line: value.start_line,
      end_line: value.end_line,
      start_column: value.start_column,
      end_column: value.end_column,
      start_offset: value.start_offset,
      end_offset: value.end_offset,
    }
  end

  def qualified(spelling, scopes)
    return spelling.sub(/\A::/, "") if spelling.start_with?("::") || spelling.include?("::")
    return spelling if scopes.empty?
    "#{scopes.last}::#{spelling}"
  end

  def literal_load?(node)
    arguments = node.arguments&.arguments || []
    arguments.length == 1 && arguments.first.is_a?(Prism::StringNode)
  end

  def call_row(node, owner)
    receiver = node.receiver
    arguments = node.arguments&.arguments || []
    location(node).merge(
      owner: owner,
      name: node.name.to_s,
      receiver: receiver&.slice,
      arguments: arguments.map(&:slice),
      source: node.slice,
    )
  end

  def visit(node, scopes = [], method_owner = nil)
    return unless node
    case node
    when Prism::ClassNode, Prism::ModuleNode
      spelling = node.constant_path&.slice || "<anonymous>"
      owner = qualified(spelling, scopes)
      @classes << location(node).merge(name: owner, kind: node.is_a?(Prism::ClassNode) ? "class" : "module")
      visit(node.superclass, scopes, method_owner) if node.is_a?(Prism::ClassNode)
      visit(node.body, scopes + [owner], method_owner)
    when Prism::DefNode
      owner = node.receiver ? node.receiver.slice : (scopes.last || "<top-level>")
      row = location(node).merge(
        owner: owner.sub(/\A::/, ""),
        name: node.name.to_s,
        singleton: !node.receiver.nil?,
        body: node.body&.slice.to_s,
      )
      @methods << row
      visit(node.body, scopes, row[:owner])
    when Prism::InstanceVariableWriteNode
      @writes << location(node).merge(owner: scopes.last || "<top-level>", name: node.name.to_s, value: node.value&.slice.to_s)
      node.child_nodes.compact.each { |child| visit(child, scopes, method_owner) }
    when Prism::CallNode
      owner = scopes.last || method_owner || "<top-level>"
      row = call_row(node, owner)
      @calls << row
      if DYNAMIC.include?(row[:name]) || (["require", "require_relative", "load"].include?(row[:name]) && !literal_load?(node))
        @dynamic << row.merge(kind: "ruby_dynamic_#{row[:name]}")
      end
      if ["include", "extend", "prepend"].include?(row[:name])
        @mixins << row
      end
      node.child_nodes.compact.each { |child| visit(child, scopes, method_owner) }
    else
      node.child_nodes.compact.each { |child| visit(child, scopes, method_owner) }
    end
  end

  def payload(result)
    visit(result.value)
    {
      success: true,
      prism_version: Prism::VERSION,
      classes: @classes.sort_by { |row| [row[:name], row[:start_offset]] },
      methods: @methods.sort_by { |row| [row[:owner], row[:name], row[:start_offset]] },
      calls: @calls.sort_by { |row| [row[:start_offset], row[:name]] },
      writes: @writes.sort_by { |row| [row[:owner], row[:name], row[:start_offset]] },
      dynamic: @dynamic.uniq.sort_by { |row| [row[:start_offset], row[:name]] },
      mixins: @mixins.uniq.sort_by { |row| [row[:start_offset], row[:name]] },
    }
  end
end

STDOUT.write(JSON.generate(A3Collector.new.payload(result)))
'''


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 90,
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


def _which(configured: str | Path) -> Path | None:
    value = str(configured)
    candidate = Path(value)
    if candidate.is_absolute() or os.sep in value:
        return candidate.resolve() if candidate.is_file() and os.access(candidate, os.X_OK) else None
    located = shutil.which(value)
    return Path(located).resolve() if located else None


def _version_tuple(rendered: str) -> tuple[int, int, int] | None:
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", rendered)
    return tuple(map(int, match.groups())) if match else None


def _probe(configured: str | Path, name: str, minimum: tuple[int, int, int], root: Path) -> dict[str, Any]:
    path = _which(configured)
    if path is None:
        return {"state": "missing", "failure_kind": f"{name}_missing"}
    result = _run([str(path), "--version"], root, timeout=10)
    if result.returncode:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}_version_failed",
            "detail": (result.stderr or result.stdout).strip(),
        }
    version = _version_tuple(result.stdout)
    if version is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}_version_unrecognized",
            "detail": result.stdout.strip(),
        }
    return {
        "state": "ready" if version >= minimum else "too_old",
        "path": str(path),
        "version": ".".join(map(str, version)),
        "minimum_version": ".".join(map(str, minimum)),
        **({"failure_kind": f"{name}_version_too_old"} if version < minimum else {}),
    }


def _within(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_project_root(value: Path) -> Path:
    return Path(os.path.realpath(value.resolve(strict=True)))


def _safe_target(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    target = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not _within(root, target) or target.is_symlink() or not target.is_dir():
        raise ValueError("target must be a non-symlink directory beneath project-root")
    return target


def _role(root: Path, path: Path, target: Path) -> str:
    relative = path.relative_to(root)
    if path.is_symlink():
        return "symlink"
    if relative.parts and relative.parts[0] == "sig":
        return "signature"
    if any(part in TEST_DIRS for part in relative.parts):
        return "test"
    if any(part in GENERATED_DIRS for part in relative.parts):
        return "generated"
    if any(part in VENDOR_DIRS for part in relative.parts):
        return "vendor"
    if any(part in BUILD_DIRS for part in relative.parts):
        return "build"
    if path.name in CONFIG_NAMES or path.suffix in CONFIG_SUFFIXES:
        return "configuration"
    if relative.parts and relative.parts[0] == "bin":
        return "entrypoint"
    if path.suffix == ".rb" and _within(target, path):
        return "production"
    return "other"


def _walk_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        rows.extend(
            current_path / name
            for name in directories
            if (current_path / name).is_symlink()
        )
        directories[:] = sorted(
            name
            for name in directories
            if name not in IGNORED_DIRS and not (current_path / name).is_symlink()
        )
        for name in sorted(filenames):
            path = current_path / name
            if path.is_file() or path.is_symlink():
                rows.append(path)
    return rows


def _inventory(root: Path, target: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _walk_files(root):
        relative = path.relative_to(root).as_posix()
        role = _role(root, path, target)
        row = {"path": relative, "role": role, "symlink": path.is_symlink()}
        if path.is_file() and not path.is_symlink():
            row["sha256"] = _sha256(path.read_bytes())
        rows.append(row)
    return rows


def _manifest(inventory: Iterable[dict[str, Any]]) -> tuple[list[dict[str, str]], str]:
    rows = [
        {"path": row["path"], "sha256": row["sha256"], "role": row["role"]}
        for row in inventory
        if "sha256" in row
    ]
    rows.sort(key=lambda row: row["path"])
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["path"].encode())
        digest.update(b"\0")
        digest.update(row["sha256"].encode())
        digest.update(b"\n")
    return rows, digest.hexdigest()


def _ruby_inputs(root: Path, inventory: Iterable[dict[str, Any]]) -> list[Path]:
    rows: list[Path] = []
    for row in inventory:
        if row["role"] not in {"production", "test", "entrypoint"} or row.get("symlink"):
            continue
        path = root / row["path"]
        if path.suffix == ".rb":
            rows.append(path)
            continue
        try:
            if b"ruby" in path.read_bytes()[:256].splitlines()[0:1][0]:
                rows.append(path)
        except (IndexError, OSError):
            continue
    return sorted(rows)


def _command_row(result: subprocess.CompletedProcess[str], argv: list[str]) -> dict[str, Any]:
    return {
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _rbs_ast(rbs: Path, root: Path, files: list[Path]) -> tuple[list[Any] | None, dict[str, Any]]:
    relative = [path.relative_to(root).as_posix() for path in files]
    argv = [str(rbs), "--no-collection", "--no-stdlib", "-I", "sig", "ast", *relative]
    result = _run(argv, root)
    row = _command_row(result, argv)
    if result.returncode:
        return None, row
    try:
        return json.loads(result.stdout), row
    except json.JSONDecodeError:
        row["returncode"] = 1
        row["stderr"] = f"invalid RBS AST JSON: {result.stdout[:240]}"
        return None, row


def _literal_strings(value: Any) -> list[str]:
    rows: list[str] = []
    if isinstance(value, dict):
        if value.get("class") == "literal" and isinstance(value.get("literal"), str):
            literal = value["literal"].strip()
            if len(literal) >= 2 and literal[0] == literal[-1] == '"':
                rows.append(literal[1:-1])
        for item in value.values():
            rows.extend(_literal_strings(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_literal_strings(item))
    return sorted(set(rows))


def _semantic_shape(value: Any) -> Any:
    """Drop source locations before comparing RBS-declared type shapes."""
    if isinstance(value, dict):
        return {
            key: _semantic_shape(item)
            for key, item in value.items()
            if key not in {"location", "annotations", "comment"}
        }
    if isinstance(value, list):
        return [_semantic_shape(item) for item in value]
    return value


def _location(row: dict[str, Any]) -> tuple[str | None, int | None]:
    location = row.get("location") or {}
    buffer = (location.get("buffer") or {}).get("name")
    line = (location.get("start") or {}).get("line")
    return buffer, line


def _rbs_contracts(ast: list[Any]) -> dict[str, list[dict[str, Any]]]:
    methods: list[dict[str, Any]] = []
    attributes: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []
    declarations: list[dict[str, Any]] = []

    def visit(row: Any, enclosing: str | None = None) -> None:
        if not isinstance(row, dict):
            return
        declaration = row.get("declaration")
        if declaration in {"class", "module", "interface"}:
            owner = str(row.get("name", "")).removeprefix("::")
            buffer, line = _location(row)
            declarations.append(
                {"owner": owner, "kind": declaration, "rbs_path": buffer, "line": line}
            )
            visibility = "public"
            for member in row.get("members", []):
                if not isinstance(member, dict):
                    continue
                marker = member.get("member")
                if marker in {"public", "private"}:
                    visibility = marker
                    continue
                buffer, line = _location(member)
                if marker == "method_definition":
                    methods.append(
                        {
                            "owner": owner,
                            "name": member.get("name"),
                            "kind": member.get("kind"),
                            "visibility": member.get("visibility") or visibility,
                            "rbs_path": buffer,
                            "line": line,
                            "overloads": member.get("overloads", []),
                            "type_sha256": _canonical_hash(_semantic_shape(member.get("overloads", []))),
                        }
                    )
                elif marker in {"attr_reader", "attr_writer", "attr_accessor"}:
                    attributes.append(
                        {
                            "owner": owner,
                            "name": member.get("name"),
                            "kind": marker,
                            "type": member.get("type"),
                            "rbs_path": buffer,
                            "line": line,
                            "type_sha256": _canonical_hash(_semantic_shape(member.get("type"))),
                        }
                    )
                else:
                    visit(member, owner)
            return
        if declaration == "alias":
            name = str(row.get("name", "")).removeprefix("::")
            buffer, line = _location(row)
            aliases.append(
                {
                    "name": name,
                    "owner": name.rsplit("::", 1)[0] if "::" in name else enclosing,
                    "rbs_path": buffer,
                    "line": line,
                    "literals": _literal_strings(row.get("type")),
                    "type": row.get("type"),
                    "type_sha256": _canonical_hash(_semantic_shape(row.get("type"))),
                }
            )

    for row in ast:
        visit(row)
    return {
        "declarations": sorted(declarations, key=lambda row: (row["owner"], row["line"] or 0)),
        "methods": sorted(methods, key=lambda row: (row["owner"], str(row["name"]), row["line"] or 0)),
        "attributes": sorted(attributes, key=lambda row: (row["owner"], str(row["name"]))),
        "aliases": sorted(aliases, key=lambda row: (str(row["name"]), row["line"] or 0)),
    }


def _prism_source(ruby: Path, root: Path, files: Iterable[Path]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    classes: list[dict[str, Any]] = []
    methods: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    writes: list[dict[str, Any]] = []
    dynamic: list[dict[str, Any]] = []
    mixins: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    for path in files:
        parse = _run([str(ruby), "--disable-gems", "-c", str(path)], root, timeout=30)
        commands.append(_command_row(parse, [str(ruby), "--disable-gems", "-c", str(path)]))
        if parse.returncode:
            return None, commands
        result = _run(
            [str(ruby), "--disable-gems", "-rprism", "-e", PRISM_COLLECTOR, str(path)],
            root,
            timeout=30,
        )
        commands.append(_command_row(result, [str(ruby), "--disable-gems", "-rprism", "-e", "<collector>", str(path)]))
        if result.returncode:
            return None, commands
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None, commands
        if not payload.get("success"):
            return None, commands
        relative = path.relative_to(root).as_posix()
        for key, target in (
            ("classes", classes),
            ("methods", methods),
            ("calls", calls),
            ("writes", writes),
            ("dynamic", dynamic),
            ("mixins", mixins),
        ):
            target.extend({"path": relative, **row} for row in payload.get(key, []))
    return {
        "classes": sorted(classes, key=lambda row: (row["path"], row["start_offset"])),
        "methods": sorted(methods, key=lambda row: (row["path"], row["start_offset"])),
        "calls": sorted(calls, key=lambda row: (row["path"], row["start_offset"])),
        "writes": sorted(writes, key=lambda row: (row["path"], row["start_offset"])),
        "dynamic": sorted(dynamic, key=lambda row: (row["path"], row["start_offset"])),
        "mixins": sorted(mixins, key=lambda row: (row["path"], row["start_offset"])),
    }, commands


def _correlations(contracts: dict[str, list[dict[str, Any]]], source: dict[str, Any]) -> list[dict[str, Any]]:
    class_counts = Counter(row["name"] for row in source["classes"])
    rows: list[dict[str, Any]] = []
    for contract in contracts["methods"]:
        matches = [
            row
            for row in source["methods"]
            if row["owner"] == contract["owner"] and row["name"] == contract["name"]
        ]
        rows.append(
            {
                "owner": contract["owner"],
                "name": contract["name"],
                "kind": contract["kind"],
                "rbs_path": contract["rbs_path"],
                "rbs_line": contract["line"],
                "source_definitions": [
                    {key: row[key] for key in ("path", "start_line", "end_line", "start_column", "end_column", "body")}
                    for row in matches
                ],
                "owner_reopened": class_counts[contract["owner"]] > 1,
                "source_definition_count": len(matches),
            }
        )
    return rows


def _terminal(status: str, failure_kind: str, detail: str, *, inventory: list[dict[str, Any]], tools: dict[str, Any]) -> tuple[dict[str, Any], int]:
    manifest, digest = _manifest(inventory)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "language": "ruby",
        "analyzer": "project-owned-rbs+prism-source-boundaries",
        "status": status,
        "failure_kind": failure_kind,
        "detail": detail,
        "source_inventory": inventory,
        "source_hashes": manifest,
        "source_manifest_sha256": digest,
        "tools": tools,
        "limits": LIMITS,
    }
    payload["fact_pack_sha256"] = _canonical_hash(payload)
    return payload, 1 if status == "failed" else 2


def collect(
    project_root: Path,
    target: str | Path,
    *,
    ruby: str | Path = "ruby",
    bundler: str | Path = "bundle",
    rbs: str | Path = "rbs",
    test: str | None = None,
    smoke: str | None = None,
) -> tuple[dict[str, Any], int]:
    root = _safe_project_root(project_root)
    target_path = _safe_target(root, target)
    inventory = _inventory(root, target_path)
    tools = {
        "ruby": _probe(ruby, "ruby", MINIMUM_RUBY, root),
        "bundler": _probe(bundler, "bundler", MINIMUM_BUNDLER, root),
        "rbs": _probe(rbs, "rbs", MINIMUM_RBS, root),
    }
    for name, tool in tools.items():
        if tool["state"] != "ready":
            return _terminal(
                "partial",
                tool.get("failure_kind", f"{name}_unavailable"),
                f"{name} is not available at the required version",
                inventory=inventory,
                tools=tools,
            )
    if not (root / "Gemfile").is_file() or not (root / "Gemfile.lock").is_file() or not list(root.glob("*.gemspec")):
        return _terminal(
            "partial",
            "ruby_project_metadata_missing",
            "Gemfile, Gemfile.lock, and a gemspec are required for this bounded plain-gem contract",
            inventory=inventory,
            tools=tools,
        )
    signature_files = [
        root / row["path"]
        for row in inventory
        if row["role"] == "signature" and row["path"].endswith(".rbs") and not row["symlink"]
    ]
    if not signature_files:
        return _terminal(
            "partial",
            "project_rbs_signatures_missing",
            "sig/**/*.rbs is required; RBS must be authored by the project rather than inferred from Prism",
            inventory=inventory,
            tools=tools,
        )
    inputs = _ruby_inputs(root, inventory)
    source, ruby_commands = _prism_source(Path(tools["ruby"]["path"]), root, inputs)
    if source is None:
        return _terminal(
            "partial",
            "ruby_syntax_failed",
            "every selected Ruby source, test, and executable must pass ruby -c and Prism",
            inventory=inventory,
            tools={**tools, "ruby_commands": ruby_commands},
        )
    validate_argv = [str(tools["rbs"]["path"]), "--no-collection", "-I", "sig", "validate"]
    validate = _run(validate_argv, root)
    ast, ast_command = _rbs_ast(Path(tools["rbs"]["path"]), root, signature_files)
    semantic_commands = {
        "rbs_validate": _command_row(validate, validate_argv),
        "rbs_ast": ast_command,
    }
    if validate.returncode or ast is None:
        return _terminal(
            "partial",
            "project_rbs_validation_failed",
            "the project-owned RBS contract did not validate or yield a local AST",
            inventory=inventory,
            tools={**tools, "ruby_commands": ruby_commands, **semantic_commands},
        )
    before_rows, before_digest = _manifest(inventory)
    bundle_env = dict(os.environ)
    bundle_env.update(
        {
            "BUNDLE_FROZEN": "true",
            "BUNDLE_DISABLE_VERSION_CHECK": "true",
            "BUNDLE_GEMFILE": str(root / "Gemfile"),
        }
    )
    with tempfile.TemporaryDirectory(prefix="ruby-semantic-bundle-") as app_config:
        bundle_env["BUNDLE_APP_CONFIG"] = app_config
        bundle_argv = [str(tools["bundler"]["path"]), "check"]
        bundle = _run(bundle_argv, root, env=bundle_env)
    native: dict[str, Any] = {"bundle_check": _command_row(bundle, bundle_argv)}
    if bundle.returncode:
        return _terminal(
            "failed",
            "frozen_bundle_check_failed",
            "frozen Bundler check failed; no semantic report can be trusted",
            inventory=inventory,
            tools={**tools, "ruby_commands": ruby_commands, **semantic_commands, "native": native},
        )
    for name, supplied in (("test", test), ("smoke", smoke)):
        if not supplied:
            continue
        command_path = root / supplied
        argv = [str(tools["ruby"]["path"]), "--disable-gems", f"-I{root / 'lib'}", str(command_path)]
        result = _run(argv, root, env=bundle_env)
        native[name] = _command_row(result, argv)
        if result.returncode:
            return _terminal(
                "failed",
                f"native_{name}_failed",
                f"the supplied native {name} command failed",
                inventory=inventory,
                tools={**tools, "ruby_commands": ruby_commands, **semantic_commands, "native": native},
            )
    after_inventory = _inventory(root, target_path)
    source_hashes, source_manifest = _manifest(after_inventory)
    if before_digest != source_manifest or before_rows != source_hashes:
        return _terminal(
            "failed",
            "unexpected_source_mutation",
            "project source or configuration changed while semantic facts were collected",
            inventory=after_inventory,
            tools={**tools, "ruby_commands": ruby_commands, **semantic_commands, "native": native},
        )
    contracts = _rbs_contracts(ast)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "language": "ruby",
        "analyzer": "project-owned-rbs+prism-source-boundaries",
        "status": "complete",
        "target": target_path.relative_to(root).as_posix(),
        "semantic_authority": {
            "kind": "project_owned_rbs",
            "validated": True,
            "signature_files": [path.relative_to(root).as_posix() for path in signature_files],
        },
        "tools": {**tools, "ruby_commands": ruby_commands, **semantic_commands, "native": native},
        "source_inventory": after_inventory,
        "source_hashes": source_hashes,
        "source_manifest_sha256": source_manifest,
        "rbs": contracts,
        "source": source,
        "correlations": _correlations(contracts, source),
        "limits": LIMITS,
    }
    payload["fact_pack_sha256"] = _canonical_hash(payload)
    return payload, 0


def load_or_collect(
    *,
    facts: Path | None,
    project_root: Path,
    target: str | Path,
    ruby: str | Path = "ruby",
    bundler: str | Path = "bundle",
    rbs: str | Path = "rbs",
    test: str | None = None,
    smoke: str | None = None,
) -> tuple[dict[str, Any], int]:
    root = _safe_project_root(project_root)
    if facts is None:
        return collect(root, target, ruby=ruby, bundler=bundler, rbs=rbs, test=test, smoke=smoke)
    supplied = facts if facts.is_absolute() else root / facts
    try:
        payload = json.loads(supplied.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _terminal(
            "partial",
            "ruby_semantic_fact_pack_unreadable",
            str(exc),
            inventory=_inventory(root, _safe_target(root, target)),
            tools={},
        )
    current_inventory = _inventory(root, _safe_target(root, target))
    _, current_manifest = _manifest(current_inventory)
    if payload.get("source_manifest_sha256") != current_manifest:
        return _terminal(
            "partial",
            "ruby_semantic_fact_pack_stale",
            "fact pack source manifest does not match the current project",
            inventory=current_inventory,
            tools=payload.get("tools", {}),
        )
    return payload, 0 if payload.get("status") == "complete" else (1 if payload.get("status") == "failed" else 2)


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


def _safe_output(root: Path, value: Path) -> Path:
    output = value if value.is_absolute() else root / value
    output = Path(os.path.abspath(output))
    allowed = root / "reports" / "ruby-semantic"
    if not _within(allowed, output) or output == allowed:
        raise ValueError("output must name a file beneath reports/ruby-semantic")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output cannot traverse a symlink")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", default="lib")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ruby", default="ruby")
    parser.add_argument("--bundler", default="bundle")
    parser.add_argument("--rbs", default="rbs")
    parser.add_argument("--test")
    parser.add_argument("--smoke")
    args = parser.parse_args(argv)
    try:
        payload, code = collect(
            args.project_root,
            args.target,
            ruby=args.ruby,
            bundler=args.bundler,
            rbs=args.rbs,
            test=args.test,
            smoke=args.smoke,
        )
        output = _safe_output(_safe_project_root(args.project_root), args.output)
    except ValueError as exc:
        parser.error(str(exc))
    _atomic(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote Ruby semantic fact pack: {output}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
