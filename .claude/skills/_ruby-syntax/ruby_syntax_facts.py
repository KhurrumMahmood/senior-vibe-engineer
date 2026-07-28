#!/usr/bin/env python3
"""Produce bounded, source-preserving Ruby Prism syntax facts.

This language-local producer owns only the facts immediately consumed by the
Ruby A2 syntax family: comments, declared method spelling, direct method-body
branch nodes, and direct call syntax. It deliberately does not establish
runtime identity, dispatch, loading, metaprogramming, framework behavior,
semantic equivalence, or refactor authority.
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
GENERATED_DIRS = frozenset({"generated", "gen", "__generated__"})
VENDOR_DIRS = frozenset({"vendor", "vendors", "third_party", "third-party", "deps"})
BUILD_DIRS = frozenset({"build", "dist", "out", "tmp", "target", ".bundle"})
REPORT_DIRS = frozenset({"reports", "report"})
CONFIG_NAMES = frozenset(
    {"Gemfile", "Gemfile.lock", "gems.rb", "gems.locked", "Rakefile", ".ruby-version"}
)
CONFIG_SUFFIXES = frozenset({".gemspec", ".rake", ".ru"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
RUBY_SHEBANG_RE = re.compile(rb"^\#![^\n]*\bruby(?:\s|$)")
FRAMEWORK_RE = re.compile(r"\brequire(?:_relative)?\s*[(\"'][^)]*rails/|\bRails\.(?:application|autoloaders)")


RUBY_COLLECTOR = r'''# frozen_string_literal: true
require "json"
require "prism"

path = ARGV.fetch(0)
result = Prism.parse_file(path)
unless result.success?
  STDOUT.write(JSON.generate({success: false, errors: result.errors.map(&:message)}))
  exit 2
end

class SyntaxCollector
  BRANCHES = {
    Prism::IfNode => "if",
    Prism::UnlessNode => "unless",
    Prism::AndNode => "logical_and",
    Prism::OrNode => "logical_or",
    Prism::WhileNode => "while",
    Prism::UntilNode => "until",
    Prism::ForNode => "for",
    Prism::CaseNode => "case",
    Prism::CaseMatchNode => "case",
  }.freeze
  DYNAMIC = {
    "send" => "ruby_dynamic_dispatch_ambiguity",
    "public_send" => "ruby_dynamic_dispatch_ambiguity",
    "__send__" => "ruby_dynamic_dispatch_ambiguity",
    "const_get" => "ruby_runtime_constant_ambiguity",
    "const_missing" => "ruby_runtime_constant_ambiguity",
    "method_missing" => "ruby_dynamic_dispatch_ambiguity",
    "define_method" => "ruby_metaprogramming_ambiguity",
    "eval" => "ruby_metaprogramming_ambiguity",
    "class_eval" => "ruby_metaprogramming_ambiguity",
    "module_eval" => "ruby_metaprogramming_ambiguity",
    "instance_eval" => "ruby_metaprogramming_ambiguity",
    "autoload" => "ruby_dynamic_loading_ambiguity",
  }.freeze

  attr_reader :functions, :calls, :dynamic, :declarations

  def initialize
    @functions = []
    @calls = []
    @dynamic = []
    @declarations = []
  end

  def location(node)
    value = node.location
    {
      start_offset: value.start_offset,
      end_offset: value.end_offset,
      start_line: value.start_line,
      end_line: value.end_line,
      start_column: value.start_column,
      end_column: value.end_column,
    }
  end

  def qualified(spelling, scopes)
    return spelling.sub(/\A::/, "") if spelling.start_with?("::")
    return spelling if spelling.include?("::") || scopes.empty?
    "#{scopes.last}::#{spelling}"
  end

  def comment_form(comment)
    return "line" if comment.is_a?(Prism::InlineComment)
    return "embedded" if defined?(Prism::EmbDocComment) && comment.is_a?(Prism::EmbDocComment)
    "comment"
  end

  def record_dynamic(node, kind, operation)
    @dynamic << location(node).merge(kind: kind, operation: operation)
  end

  def literal_load?(node)
    arguments = node.arguments&.arguments || []
    arguments.length == 1 && arguments.first.is_a?(Prism::StringNode)
  end

  def call_spelling(node)
    receiver = node.receiver
    receiver ? "#{receiver.slice}.#{node.name}" : node.name.to_s
  end

  def visit(node, scopes = [], context = nil, enclosures = [])
    return unless node
    case node
    when Prism::ClassNode, Prism::ModuleNode
      spelling = node.constant_path&.slice || "<anonymous>"
      name = qualified(spelling, scopes)
      @declarations << location(node).merge(kind: node.is_a?(Prism::ClassNode) ? "class" : "module", name: name)
      visit(node.body, scopes + [name], context, enclosures)
    when Prism::DefNode
      receiver = node.receiver&.slice
      owner = receiver && receiver != "self" ? receiver : (scopes.last || "<top-level>")
      row = location(node).merge(
        name: node.name.to_s,
        owner: owner,
        singleton: !node.receiver.nil?,
        branches: [],
        direct_calls: [],
      )
      @functions << row
      visit(node.body, scopes, {function: row, nested: false}, enclosures)
    when Prism::BlockNode, Prism::LambdaNode
      nested = context ? context.merge(nested: true) : nil
      node.child_nodes.compact.each { |child| visit(child, scopes, nested, enclosures) }
    when Prism::BeginNode
      protected = node.rescue_clause ? enclosures + ["rescue"] : enclosures
      visit(node.statements, scopes, context, protected)
      visit(node.rescue_clause, scopes, context, protected)
      visit(node.else_clause, scopes, context, protected)
      visit(node.ensure_clause, scopes, context, protected)
    when Prism::RescueNode
      node.child_nodes.compact.each { |child| visit(child, scopes, context, enclosures + ["rescue"]) }
    else
      if context && !context[:nested] && (kind = BRANCHES[node.class])
        context[:function][:branches] << location(node).merge(kind: kind)
      end
      if node.is_a?(Prism::CallNode)
        name = node.name.to_s
        if DYNAMIC.key?(name)
          record_dynamic(node, DYNAMIC.fetch(name), name)
        elsif ["require", "require_relative", "load"].include?(name) && !literal_load?(node)
          record_dynamic(node, "ruby_dynamic_loading_ambiguity", name)
        end
        if context && !context[:nested]
          row = location(node).merge(
            spelling: call_spelling(node),
            function: context[:function][:name],
            enclosures: enclosures.uniq.sort,
          )
          context[:function][:direct_calls] << row
          @calls << row
        end
      end
      node.child_nodes.compact.each { |child| visit(child, scopes, context, enclosures) }
    end
  end

  def payload(result)
    visit(result.value)
    functions = @functions.map do |row|
      start_line = row[:start_line]
      end_line = row[:end_line]
      row.merge(
        line: start_line,
        end_line: end_line,
        loc: end_line - start_line + 1,
        branch_score: row[:branches].length,
        branches: row[:branches].sort_by { |branch| [branch[:start_offset], branch[:kind]] },
      )
    end
    {
      success: true,
      prism_version: Prism::VERSION,
      comments: result.comments.map do |comment|
        location(comment).merge(text: comment.slice, form: comment_form(comment)).then do |row|
          row.merge(line: row.delete(:start_line), end_line: row.delete(:end_line))
        end
      end,
      declarations: @declarations,
      functions: functions.sort_by { |row| [row[:start_offset], row[:name]] },
      calls: @calls.sort_by { |row| [row[:start_offset], row[:spelling]] },
      dynamic: @dynamic.uniq.sort_by { |row| [row[:start_offset], row[:kind], row[:operation]] },
    }
  end
end

collector = SyntaxCollector.new
STDOUT.write(JSON.generate(collector.payload(result)))
'''


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _which(configured: str | Path) -> Path | None:
    value = str(configured)
    candidate = Path(value)
    if candidate.is_absolute() or os.sep in value:
        return candidate.resolve() if candidate.is_file() and os.access(candidate, os.X_OK) else None
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        found = Path(directory or ".") / value
        if found.is_file() and os.access(found, os.X_OK):
            return found.resolve()
    return None


def _probe(
    configured: str | Path,
    name: str,
    minimum: tuple[int, int, int],
    root: Path,
) -> dict[str, Any]:
    path = _which(configured)
    if path is None:
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
    match = re.search(
        rf"\b{re.escape(label)}\s+(\d+)\.(\d+)\.(\d+)", result.stdout, re.I
    )
    if match is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-unrecognized",
            "detail": result.stdout.strip(),
        }
    version = tuple(map(int, match.groups()))
    return {
        "state": "ready" if version >= minimum else "too-old",
        "path": str(path),
        "version": ".".join(match.groups()),
        "minimum_version": ".".join(map(str, minimum)),
        **({"failure_kind": f"{name}-version-too-old"} if version < minimum else {}),
    }


def _ruby_input(path: Path) -> bool:
    if path.suffix.casefold() == ".rb":
        return True
    try:
        with path.open("rb") as handle:
            return RUBY_SHEBANG_RE.search(handle.readline(512)) is not None
    except OSError:
        return False


def _logical_targets(root: Path, targets: Iterable[str | Path]) -> tuple[list[Path], list[str]]:
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


def _role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if parts & VENDOR_DIRS:
        return "excluded", "vendor"
    if parts & REPORT_DIRS:
        return "excluded", "report"
    if parts & BUILD_DIRS:
        return "excluded", "build"
    if parts & TEST_DIRS or name.endswith("_test.rb") or name.startswith("test_"):
        return "test", "test"
    if parts & GENERATED_DIRS or GENERATED_RE.search(text[:4096]):
        return "excluded", "generated"
    if relative.parts and relative.parts[0] == "bin":
        return "entrypoint", "entrypoint"
    return "candidate", None


def _inventory(root: Path, targets: Iterable[str | Path]) -> tuple[list[dict[str, Any]], list[str]]:
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
                "source_sha256": _hash(source),
                "source_bytes": len(source),
                "_path": path,
                "_source": source,
            }
        )
    return inventory, errors


def _project_manifest(root: Path) -> dict[str, str]:
    state: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        relative_dir = current.relative_to(root)
        if relative_dir.parts and relative_dir.parts[0] in REPORT_DIRS:
            dirnames[:] = []
            continue
        symlink_dirs = [name for name in dirnames if (current / name).is_symlink()]
        for name in symlink_dirs:
            path = current / name
            state[path.relative_to(root).as_posix()] = f"symlink:{os.readlink(path)}"
        dirnames[:] = sorted(name for name in dirnames if name not in symlink_dirs)
        for name in sorted(filenames):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                state[relative] = f"symlink:{os.readlink(path)}"
            else:
                try:
                    state[relative] = _hash(path.read_bytes())
                except OSError:
                    state[relative] = "read-error"
    return state


def _manifest_hash(manifest: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(manifest.items()):
        digest.update(path.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest()


def _public_inventory(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if not key.startswith("_")} for row in inventory]


def _terminal(
    *,
    status: str,
    failure_kind: str,
    root: Path,
    target: Path,
    before: dict[str, str],
    after: dict[str, str],
    inventory: list[dict[str, Any]],
    files: list[dict[str, Any]],
    ambiguities: list[dict[str, Any]],
    tools: dict[str, Any],
    prism: dict[str, Any],
    bundle_check: dict[str, Any],
    syntax_checks: list[dict[str, Any]],
    native: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "language": "ruby",
        "analyzer": "ruby-syntax-prism-v1",
        "status": status,
        "failure_kind": failure_kind,
        "project_root": str(root),
        "target": target.relative_to(root).as_posix() if target != root else ".",
        "claim_boundary": (
            "Prism comments, declared method spelling, direct syntactic branches and direct call "
            "shapes only; not runtime identity, dynamic dispatch/loading, metaprogramming, "
            "Rails/Zeitwerk behavior, semantic equivalence, or refactor authority"
        ),
        "tools": tools,
        "prism": prism,
        "bundle_check": bundle_check,
        "syntax_checks": syntax_checks,
        "native": native,
        "inventory": _public_inventory(inventory),
        "files": files,
        "ambiguities": ambiguities,
        "errors": errors,
        "source_manifest": {
            "before_sha256": _manifest_hash(before),
            "after_sha256": _manifest_hash(after),
            "preserved": before == after,
            "changed": sorted(path for path in before.keys() & after.keys() if before[path] != after[path]),
            "missing": sorted(before.keys() - after.keys()),
            "unexpected": sorted(after.keys() - before.keys()),
        },
    }


def _bundle_check(root: Path, bundler: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="ruby-syntax-") as raw_state:
        state = Path(raw_state)
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
        return _run([bundler, "check"], root, env=env, timeout=30)


def _safe_project_file(root: Path, raw: str | None) -> Path | None:
    if not raw:
        return None
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


def _native(root: Path, ruby: str, test: str | None, smoke: str | None) -> tuple[dict[str, Any], str | None]:
    native: dict[str, Any] = {}
    for kind, raw in (("test", test), ("smoke", smoke)):
        path = _safe_project_file(root, raw)
        if path is None:
            native[kind] = {"status": "not-run" if raw is None else "failed", "path": raw}
            return native, f"native-{kind}-unsafe" if raw else "native-gates-incomplete"
        result = _run([ruby, "--disable-gems", f"-I{root / 'lib'}", str(path)], root, timeout=30)
        native[kind] = {
            "status": "passed" if result.returncode == 0 else "failed",
            "path": path.relative_to(root).as_posix(),
            "returncode": result.returncode,
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:4000],
        }
        if result.returncode:
            return native, f"native-{kind}-failed"
    return native, None


def _syntax_facts(root: Path, ruby: str, row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    result = _run(
        [ruby, "--disable-gems", "-rjson", "-rprism", "-e", RUBY_COLLECTOR, str(row["_path"])],
        root,
        timeout=30,
    )
    if result.returncode:
        return None, (result.stderr or result.stdout).strip()[-4000:]
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, str(exc)
    expected = {"comments", "functions", "calls", "dynamic"}
    if payload.get("success") is not True or not expected <= set(payload):
        return None, "Prism collector emitted an incomplete payload"
    return payload, None


def _public_file(row: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    def clean_location(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key not in {"start_column", "end_column"}}

    functions = []
    for function in facts["functions"]:
        branches = [clean_location(branch) for branch in function.get("branches", [])]
        direct_calls = [clean_location(call) for call in function.get("direct_calls", [])]
        functions.append(
            {
                "name": function["name"],
                "owner": function["owner"],
                "singleton": function["singleton"],
                "line": function["line"],
                "end_line": function["end_line"],
                "loc": function["loc"],
                "branch_score": function["branch_score"],
                "branches": branches,
                "direct_calls": direct_calls,
            }
        )
    return {
        "file": row["file"],
        "source_sha256": row["source_sha256"],
        "comments": [clean_location(comment) for comment in facts["comments"]],
        "functions": functions,
        "calls": [clean_location(call) for call in facts["calls"]],
    }


def produce(
    project_root: Path,
    target: str | Path,
    *,
    ruby: str | Path = "ruby",
    bundler: str | Path = "bundle",
    test: str | None = None,
    smoke: str | None = None,
    allow_partial_syntax: bool = False,
) -> tuple[dict[str, Any], int]:
    root = project_root.resolve()
    target_path = Path(target)
    target_path = target_path if target_path.is_absolute() else root / target_path
    target_path = Path(os.path.abspath(target_path))
    if not root.is_dir() or not target_path.exists():
        return {
            "schema_version": 1,
            "analyzer": "ruby-syntax-prism-v1",
            "status": "failed",
            "failure_kind": "invalid_project_or_target",
            "inventory": [],
            "files": [],
            "ambiguities": [],
            "source_manifest": {"preserved": True},
        }, 1
    try:
        target_path.relative_to(root)
    except ValueError:
        return {
            "schema_version": 1,
            "analyzer": "ruby-syntax-prism-v1",
            "status": "failed",
            "failure_kind": "unsafe_target",
            "inventory": [],
            "files": [],
            "ambiguities": [],
            "source_manifest": {"preserved": True},
        }, 1

    before = _project_manifest(root)
    inventory, errors = _inventory(root, [target_path])
    tools = {
        "ruby": _probe(ruby, "ruby", MINIMUM_RUBY, root),
        "bundler": _probe(bundler, "bundler", MINIMUM_BUNDLER, root),
    }
    empty: dict[str, Any] = {}
    bad_tools = [tool for tool in tools.values() if tool["state"] != "ready"]
    if bad_tools:
        failed = bad_tools[0]
        after = _project_manifest(root)
        status = "failed" if failed["state"] == "failed" else "partial"
        return _terminal(
            status=status,
            failure_kind=failed["failure_kind"],
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=[],
            ambiguities=[],
            tools=tools,
            prism=empty,
            bundle_check=empty,
            syntax_checks=[],
            native=empty,
            errors=errors,
        ), 1 if status == "failed" else 2

    prerequisites = (root / "Gemfile", root / "Gemfile.lock")
    project_incomplete = not all(path.is_file() for path in prerequisites) or not any(
        root.glob("*.gemspec")
    )
    if project_incomplete and not allow_partial_syntax:
        after = _project_manifest(root)
        return _terminal(
            status="partial",
            failure_kind="ruby-project-incomplete",
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=[],
            ambiguities=[],
            tools=tools,
            prism=empty,
            bundle_check=empty,
            syntax_checks=[],
            native=empty,
            errors=errors,
        ), 2

    ruby_path = tools["ruby"]["path"]
    prism_probe = _run([ruby_path, "--disable-gems", "-rprism", "-e", "puts Prism::VERSION"], root, timeout=10)
    prism = {"version": prism_probe.stdout.strip(), "source": "selected Ruby bundled/default Prism"}
    if prism_probe.returncode or not re.fullmatch(r"\d+(?:\.\d+){1,2}", prism["version"]):
        after = _project_manifest(root)
        return _terminal(
            status="failed",
            failure_kind="prism-probe-failed",
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=[],
            ambiguities=[],
            tools=tools,
            prism=prism,
            bundle_check=empty,
            syntax_checks=[],
            native=empty,
            errors=errors,
        ), 1

    bundled = None if project_incomplete else _bundle_check(root, tools["bundler"]["path"])
    bundle_check = (
        {"status": "not-run", "reason": "ruby-project-incomplete"}
        if bundled is None
        else {
            "command": "bundle check (frozen, isolated config, no install/update)",
            "returncode": bundled.returncode,
            "stderr": bundled.stderr[-4000:],
        }
    )
    if bundled is not None and bundled.returncode and not allow_partial_syntax:
        after = _project_manifest(root)
        return _terminal(
            status="failed",
            failure_kind="bundle-check-failed",
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=[],
            ambiguities=[],
            tools=tools,
            prism=prism,
            bundle_check=bundle_check,
            syntax_checks=[],
            native=empty,
            errors=errors,
        ), 1

    syntax_checks: list[dict[str, Any]] = []
    selected_rows = [
        row
        for row in inventory
        if row["selected"] and row["role"] in {"candidate", "test", "entrypoint"}
    ]
    for row in selected_rows:
        checked = _run([ruby_path, "--disable-gems", "-c", str(row["_path"])], root, timeout=20)
        syntax_checks.append({"file": row["file"], "returncode": checked.returncode})
        if checked.returncode:
            row.update(role="failed", reason="syntax-error", detail=(checked.stderr or checked.stdout).strip())
            errors.append(f"{row['file']}:syntax-error")

    files: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []
    provider_failures = []
    for row in inventory:
        if row["role"] != "candidate" or not row["selected"]:
            continue
        facts, error = _syntax_facts(root, ruby_path, row)
        if error:
            row.update(role="failed", reason="prism-provider-failed", detail=error)
            errors.append(f"{row['file']}:prism-provider-failed")
            provider_failures.append(row["file"])
            continue
        assert facts is not None
        row["role"] = "eligible"
        files.append(_public_file(row, facts))
        ambiguities.extend({**item, "file": row["file"]} for item in facts["dynamic"])

    for row in inventory:
        source = row.get("_source")
        if isinstance(source, bytes) and FRAMEWORK_RE.search(source.decode("utf-8", errors="ignore")):
            ambiguities.append({"kind": "ruby_framework_loader_ambiguity", "file": row["file"]})

    if any(row["role"] == "failed" for row in inventory) or provider_failures:
        after = _project_manifest(root)
        return _terminal(
            status="partial",
            failure_kind="ruby_source_incomplete",
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=files,
            ambiguities=sorted(ambiguities, key=lambda row: (row["file"], row["kind"])),
            tools=tools,
            prism=prism,
            bundle_check=bundle_check,
            syntax_checks=syntax_checks,
            native=empty,
            errors=errors,
        ), 2
    if not files:
        after = _project_manifest(root)
        return _terminal(
            status="partial",
            failure_kind="no_eligible_ruby_files",
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=[],
            ambiguities=ambiguities,
            tools=tools,
            prism=prism,
            bundle_check=bundle_check,
            syntax_checks=syntax_checks,
            native=empty,
            errors=errors,
        ), 2

    if project_incomplete or (bundled is not None and bundled.returncode):
        after = _project_manifest(root)
        return _terminal(
            status="partial",
            failure_kind=(
                "ruby-project-incomplete"
                if project_incomplete
                else "bundle-check-failed"
            ),
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=files,
            ambiguities=sorted(ambiguities, key=lambda row: (row["file"], row["kind"])),
            tools=tools,
            prism=prism,
            bundle_check=bundle_check,
            syntax_checks=syntax_checks,
            native=empty,
            errors=errors,
        ), 2

    native, native_failure = _native(root, ruby_path, test, smoke)
    after = _project_manifest(root)
    if before != after:
        return _terminal(
            status="failed",
            failure_kind="source_mutated_by_native_check",
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=files,
            ambiguities=ambiguities,
            tools=tools,
            prism=prism,
            bundle_check=bundle_check,
            syntax_checks=syntax_checks,
            native=native,
            errors=errors,
        ), 1
    if native_failure:
        return _terminal(
            status="failed" if native_failure != "native-gates-incomplete" else "partial",
            failure_kind=native_failure,
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=files,
            ambiguities=ambiguities,
            tools=tools,
            prism=prism,
            bundle_check=bundle_check,
            syntax_checks=syntax_checks,
            native=native,
            errors=errors,
        ), 2 if native_failure == "native-gates-incomplete" else 1
    if ambiguities:
        return _terminal(
            status="partial",
            failure_kind=sorted(ambiguities, key=lambda row: (row["file"], row["kind"]))[0]["kind"],
            root=root,
            target=target_path,
            before=before,
            after=after,
            inventory=inventory,
            files=files,
            ambiguities=sorted(ambiguities, key=lambda row: (row["file"], row["kind"])),
            tools=tools,
            prism=prism,
            bundle_check=bundle_check,
            syntax_checks=syntax_checks,
            native=native,
            errors=errors,
        ), 2
    return _terminal(
        status="complete",
        failure_kind="none",
        root=root,
        target=target_path,
        before=before,
        after=after,
        inventory=inventory,
        files=files,
        ambiguities=[],
        tools=tools,
        prism=prism,
        bundle_check=bundle_check,
        syntax_checks=syntax_checks,
        native=native,
        errors=errors,
    ), 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--ruby", default="ruby")
    parser.add_argument("--bundler", default="bundle")
    parser.add_argument("--test")
    parser.add_argument("--smoke")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload, code = produce(
        args.project_root,
        args.target,
        ruby=args.ruby,
        bundler=args.bundler,
        test=args.test,
        smoke=args.smoke,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
