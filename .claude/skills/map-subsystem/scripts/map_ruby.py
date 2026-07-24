#!/usr/bin/env python3
"""Map bounded plain-Ruby/gem structure without claiming runtime reachability."""
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
from datetime import datetime, timezone
from pathlib import Path


INTERNAL_PARTS = {".agents", ".claude", ".engineering", ".git", "reports"}
EXCLUDED_PARTS = {
    "build": "build",
    "dist": "build",
    "out": "build",
    "tmp": "build",
    "vendor": "vendor",
    "generated": "generated",
    "gen": "generated",
}
LIMITATIONS = [
    "Dynamic require/load arguments and load-path mutation are not resolved",
    "autoload and Rails/Zeitwerk conventions are not resolved",
    "const_get, const_missing, send/public_send, method_missing, and dynamic delegation are not resolved",
    "eval/class_eval/module_eval, define_method, refinements, and runtime reopening are not resolved",
    "framework callbacks, dependency injection, native extensions, and runtime-generated code are not resolved",
    "syntactic constant candidates and mixin spellings are not runtime symbol identity or reachability",
    "RBS and TypeProf availability alone does not establish project semantics",
]


RUBY_ANALYZER = r'''# frozen_string_literal: true
require "json"
require "prism"

path = ARGV.fetch(0)
result = Prism.parse_file(path)
unless result.success?
  puts JSON.generate({success: false, errors: result.errors.map { |error|
    {message: error.message, line: error.location.start_line, column: error.location.start_column}
  }})
  exit 2
end

class MapCollector
  attr_reader :declarations, :methods, :loads, :mixins, :constants, :dynamic

  def initialize
    @declarations = []
    @methods = []
    @loads = []
    @mixins = []
    @constants = []
    @dynamic = []
  end

  def constant_text(node)
    return nil unless node
    case node
    when Prism::ConstantReadNode, Prism::ConstantPathNode
      node.slice
    else
      nil
    end
  end

  def qualify(spelling, scopes)
    return spelling.sub(/\A::/, "") if spelling.start_with?("::")
    return spelling if spelling.include?("::") || scopes.empty?
    "#{scopes.last}::#{spelling}"
  end

  def location(node)
    {line: node.location.start_line, column: node.location.start_column}
  end

  def record_constant(node, owner, scopes)
    spelling = constant_text(node)
    return unless spelling
    @constants << location(node).merge(
      spelling: spelling,
      owner: owner || "<top-level>",
      lexical_scope: scopes.last,
    )
  end

  def record_call(node, owner, scopes)
    name = node.name.to_s
    arguments = node.arguments&.arguments || []
    bare = node.receiver.nil?
    if bare && %w[require require_relative load].include?(name)
      literal = arguments.length == 1 && arguments.first.is_a?(Prism::StringNode)
      if literal
        @loads << location(node).merge(operation: name, specifier: arguments.first.unescaped)
      else
        @dynamic << location(node).merge(kind: "dynamic-#{name.tr('_', '-')}", operation: name)
      end
    end
    if bare && %w[include extend prepend].include?(name)
      arguments.each do |argument|
        spelling = constant_text(argument)
        @mixins << location(node).merge(
          operation: name,
          owner: owner || "<top-level>",
          target_spelling: spelling || argument.slice,
          target_kind: spelling ? "constant-spelling" : "dynamic-expression",
        )
      end
    end
    kind = case name
    when "autoload" then "autoload"
    when "const_get", "const_missing" then "const-get"
    when "send", "public_send", "__send__" then "dynamic-send"
    when "define_method" then "define-method"
    when "eval" then "eval"
    when "class_eval" then "class-eval"
    when "module_eval" then "module-eval"
    end
    if kind
      @dynamic << location(node).merge(kind: kind, operation: name)
    elsif name.match?(/\A(?:before|after|around)_(?:action|save|create|update|destroy|commit|validation)\z/)
      @dynamic << location(node).merge(kind: "framework-callback", operation: name)
    end
  end

  def visit(node, scopes = [], owner = nil)
    return unless node
    case node
    when Prism::ModuleNode
      spelling = node.constant_path.slice
      qualified = qualify(spelling, scopes)
      @declarations << location(node).merge(
        kind: "module", spelling: spelling, qualified_name: qualified,
        lexical_scope: scopes.last, superclass_spelling: nil,
      )
      visit(node.body, scopes + [qualified], qualified)
    when Prism::ClassNode
      spelling = node.constant_path.slice
      qualified = qualify(spelling, scopes)
      @declarations << location(node).merge(
        kind: "class", spelling: spelling, qualified_name: qualified,
        lexical_scope: scopes.last, superclass_spelling: constant_text(node.superclass),
      )
      visit(node.superclass, scopes, qualified) if node.superclass
      visit(node.body, scopes + [qualified], qualified)
    when Prism::DefNode
      receiver = node.receiver
      singleton = !receiver.nil?
      method_owner = owner || "<top-level>"
      receiver_spelling = constant_text(receiver)
      method_owner = receiver_spelling if receiver_spelling
      @methods << location(node).merge(
        owner: method_owner,
        name: node.name.to_s,
        singleton: singleton,
        receiver_spelling: receiver_spelling || (receiver ? receiver.slice : nil),
        visibility: "unavailable",
      )
      if node.name.to_s == "method_missing"
        @dynamic << location(node).merge(kind: "method-missing", operation: "def method_missing")
      end
      visit(node.parameters, scopes, method_owner)
      visit(node.body, scopes, method_owner)
    when Prism::CallNode
      record_call(node, owner, scopes)
      node.child_nodes.compact.each { |child| visit(child, scopes, owner) }
    when Prism::ConstantReadNode, Prism::ConstantPathNode
      record_constant(node, owner, scopes)
    else
      node.child_nodes.compact.each { |child| visit(child, scopes, owner) }
    end
  end
end

collector = MapCollector.new
collector.visit(result.value)
puts JSON.generate({
  success: true,
  prism_version: Prism::VERSION,
  declarations: collector.declarations,
  methods: collector.methods,
  loads: collector.loads,
  mixins: collector.mixins,
  constants: collector.constants,
  dynamic: collector.dynamic,
})
'''


class UserError(Exception):
    """Unsafe or malformed CLI input that must not write artifacts."""


class Terminal(Exception):
    """A safe terminal outcome that replaces both final artifacts."""

    def __init__(
        self,
        status: str,
        kind: str,
        message: str,
        *,
        exit_code: int = 0,
        **facts: object,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.kind = kind
        self.exit_code = exit_code
        self.facts = facts


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(
    argv: list[str],
    *,
    cwd: Path,
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


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: dict) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _has_symlink(path: Path, root: Path) -> bool:
    if not _inside(path, root):
        return True
    current = path
    while current != root:
        if current.is_symlink():
            return True
        current = current.parent
    return root.is_symlink()


def _validate_paths(
    args: argparse.Namespace,
) -> tuple[Path, list[Path], Path, Path]:
    root_input = Path(args.project_root)
    if not root_input.is_dir() or root_input.is_symlink():
        raise UserError("project root must be a regular directory")
    root = root_input.resolve()
    targets: list[Path] = []
    for raw in args.target:
        candidate = Path(raw)
        candidate = candidate if candidate.is_absolute() else root / candidate
        candidate = Path(os.path.abspath(candidate))
        if not _inside(candidate, root):
            raise UserError("target must stay inside project root")
        targets.append(candidate)
    output = Path(os.path.abspath(args.output))
    evidence = Path(os.path.abspath(args.evidence))
    docs = root / ".engineering" / "docs" / "subsystems"
    reports = root / "reports" / "map"
    if output == docs or not _inside(output, docs):
        raise UserError("output must stay below .engineering/docs/subsystems")
    if evidence == reports or not _inside(evidence, reports):
        raise UserError("evidence must stay below reports/map")
    if output == evidence:
        raise UserError("output and evidence must be different paths")
    if _has_symlink(output, root) or _has_symlink(evidence, root):
        raise UserError("artifact output must not traverse a symbolic link")
    return root, targets, output, evidence


def _version_argument(value: str, flag: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", value):
        raise UserError(f"{flag} must be a numeric major.minor[.patch] version")
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0])[:3])


def _resolve_tool(value: str) -> str | None:
    if "/" in value:
        path = Path(value)
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(value)


def _ruby_version(tool: str, root: Path) -> tuple[tuple[int, int, int] | None, str]:
    completed = _run([tool, "--version"], cwd=root, timeout=10)
    text = (completed.stdout + completed.stderr).strip()
    match = re.search(r"\bruby\s+(\d+)\.(\d+)(?:\.(\d+))?", text, re.I)
    if completed.returncode != 0 or match is None:
        return None, text or "Ruby version probe failed"
    return tuple(int(part or 0) for part in match.groups()), text.splitlines()[0]


def _bundler_version(tool: str, root: Path) -> tuple[tuple[int, int, int] | None, str]:
    completed = _run([tool, "--version"], cwd=root, timeout=10)
    text = (completed.stdout + completed.stderr).strip()
    match = re.search(r"\bBundler\s+version\s+(\d+)\.(\d+)(?:\.(\d+))?", text, re.I)
    if completed.returncode != 0 or match is None:
        return None, text or "Bundler version probe failed"
    return tuple(int(part or 0) for part in match.groups()), text.splitlines()[0]


def _optional_tool(value: str, root: Path) -> dict:
    tool = _resolve_tool(value)
    if tool is None:
        return {"path": None, "status": "unavailable", "used": False}
    completed = _run([tool, "--version"], cwd=root, timeout=10)
    text = (completed.stdout + completed.stderr).strip()
    return {
        "path": tool,
        "status": "available" if completed.returncode == 0 else "unavailable",
        "version_probe": text.splitlines()[0] if text else None,
        "used": False,
        "reason": "availability alone is not project-owned semantic evidence",
    }


def _role(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    parts = relative.parts
    name = path.name
    if path.is_symlink():
        return "symlink"
    for part in parts:
        if part in EXCLUDED_PARTS:
            return EXCLUDED_PARTS[part]
    if any(part in {"test", "tests", "spec"} for part in parts):
        return "test"
    if parts and parts[0] == "bin":
        return "entrypoint"
    if path.suffix == ".rbs":
        return "signature"
    if name in {"Gemfile", "Gemfile.lock", "Rakefile", "gems.rb", "gems.locked"}:
        return "configuration"
    if path.suffix in {".gemspec", ".rake", ".ru"}:
        return "configuration"
    return "source"


def _candidate_paths(root: Path) -> list[Path]:
    rows: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in INTERNAL_PARTS for part in relative.parts):
            continue
        if not (path.is_file() or path.is_symlink()):
            continue
        candidate = (
            path.suffix in {".rb", ".rbs", ".gemspec", ".rake", ".ru"}
            or path.name in {"Gemfile", "Gemfile.lock", "Rakefile", "gems.rb", "gems.locked"}
            or (relative.parts and relative.parts[0] == "bin")
        )
        if candidate:
            rows.append(path)
    return rows


def _source_state(root: Path, paths: list[Path]) -> tuple[str, dict[str, str]]:
    files: dict[str, str] = {}
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(root).as_posix()
        value = (
            f"symlink:{os.readlink(path)}"
            if path.is_symlink()
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        files[relative] = value
        digest.update(relative.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest(), files


def _inventory(root: Path, paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        role = _role(path, root)
        rows.append({
            "path": path.relative_to(root).as_posix(),
            "role": role,
            "included": role in {"source", "test", "entrypoint"},
            "sha256": None if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return rows


def _target_results(root: Path, targets: list[Path], inventory: list[dict]) -> tuple[list[dict], list[str]]:
    production = [root / row["path"] for row in inventory if row["role"] == "source" and row["path"].endswith(".rb")]
    results = []
    selected: set[str] = set()
    for target in targets:
        relative = target.relative_to(root).as_posix()
        if _has_symlink(target, root):
            results.append({"target": relative, "status": "unsupported", "reason": "unsafe-symlink-target", "source_files": []})
            continue
        if not target.exists():
            results.append({"target": relative, "status": "unsupported", "reason": "missing-target", "source_files": []})
            continue
        if target.is_file():
            files = [target] if target.suffix == ".rb" and _role(target, root) == "source" else []
        elif target.is_dir():
            files = [path for path in production if _inside(path, target)]
        else:
            files = []
        if not files:
            results.append({"target": relative, "status": "unsupported", "reason": "no-production-ruby-source", "source_files": []})
            continue
        names = sorted(path.relative_to(root).as_posix() for path in files)
        selected.update(names)
        results.append({"target": relative, "status": "complete", "reason": "bounded-static-selection", "source_files": names})
    return results, sorted(selected)


def _prism_file(ruby: str, root: Path, path: Path) -> dict:
    completed = _run(
        [ruby, "--disable-gems", "-e", RUBY_ANALYZER, str(path)],
        cwd=root,
        timeout=30,
    )
    if completed.returncode != 0:
        raise Terminal(
            "failed",
            "prism_analysis_failed",
            (completed.stderr or completed.stdout or f"Prism analysis failed for {path.name}").strip()[:4000],
            exit_code=2,
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise Terminal("failed", "prism_output_invalid", str(exc), exit_code=2) from exc
    if not payload.get("success"):
        raise Terminal("failed", "prism_analysis_failed", f"Prism rejected {path.name}.", exit_code=2, prism_errors=payload.get("errors", []))
    return payload


def _resolve_load(root: Path, caller: Path, operation: str, specifier: str) -> tuple[str | None, str]:
    candidates: list[Path] = []
    if operation == "require_relative":
        base = caller.parent / specifier
        candidates.extend([base, Path(f"{base}.rb")])
    elif not Path(specifier).is_absolute():
        normalized = specifier[:-3] if specifier.endswith(".rb") else specifier
        candidates.extend([root / "lib" / f"{normalized}.rb", root / "lib" / normalized])
        if operation == "load":
            candidates.extend([root / specifier, root / "lib" / specifier])
    for candidate in candidates:
        lexical = Path(os.path.abspath(candidate))
        if _inside(lexical, root) and lexical.is_file() and not _has_symlink(lexical, root):
            return lexical.relative_to(root).as_posix(), "resolved-first-party-literal-layout"
    if operation == "require_relative":
        return None, "unresolved-relative-literal"
    return None, "external-or-standard-library"


def _constant_candidates(spelling: str, owner: str) -> list[str]:
    spelling = spelling.removeprefix("::")
    if "::" in spelling:
        return [spelling]
    if owner == "<top-level>":
        return [spelling]
    parts = owner.split("::")
    return ["::".join([*parts[:index], spelling]) for index in range(len(parts), 0, -1)] + [spelling]


def _render(payload: dict) -> str:
    lines = [
        "---",
        f"subsystem: {payload['name']}",
        "language: ruby",
        f"status: {payload['status']}",
        f"regenerated: {payload['generated_at']}",
        "---",
        "",
        f"# {payload['name']}",
        "",
        f"Status: **{payload['status']}**",
        "",
        payload.get("message", ""),
        "",
    ]
    if payload.get("source_inventory"):
        lines.extend(["## Source inventory", "", "| Path | Role | Included | SHA-256 |", "|---|---|---:|---|"])
        for row in payload["source_inventory"]:
            digest = row["sha256"] or "symlink-not-read"
            lines.append(f"| `{row['path']}` | {row['role']} | {str(row['included']).lower()} | `{digest}` |")
    if payload.get("declarations") is not None:
        lines.extend(["", "## Modules and classes", ""])
        if payload["declarations"]:
            lines.extend(f"- `{row['qualified_name']}` — {row['kind']} at `{row['file']}:{row['line']}`" for row in payload["declarations"])
        else:
            lines.append("- No module or class declarations in the analyzed project files.")
        lines.extend(["", "## Declared methods", ""])
        if payload.get("methods"):
            lines.extend(f"- `{row['owner']}#{row['name']}` at `{row['file']}:{row['line']}` (visibility unavailable)" for row in payload["methods"])
        else:
            lines.append("- No method declarations.")
        lines.extend(["", "## Namespace and reopening evidence", ""])
        for row in payload.get("namespace_and_reopening_evidence", []):
            label = "statically reopened" if row["statically_reopened"] else "one syntax declaration"
            lines.append(f"- `{row['qualified_name']}` — {label}; {row['definition_count']} definition(s).")
        lines.extend(["", "## Mixins", ""])
        if payload.get("mixins"):
            lines.extend(f"- `{row['owner']}` {row['operation']} `{row['target_spelling']}` at `{row['file']}:{row['line']}` (syntax spelling only)" for row in payload["mixins"])
        else:
            lines.append("- No statically spelled include/extend/prepend calls.")
        lines.extend(["", "## Literal load edges", ""])
        if payload.get("literal_load_edges"):
            for row in payload["literal_load_edges"]:
                destination = row["resolved_path"] or row["resolution"]
                lines.append(f"- `{row['caller']}` --{row['operation']} `{row['specifier']}`--> `{destination}`")
        else:
            lines.append("- No literal require/require_relative/load calls.")
        lines.extend(["", "## Tests, entrypoints, and native evidence", ""])
        lines.extend(f"- `{row['kind']}`: `{row['path']}`" for row in payload.get("entrypoints", []))
        native = payload.get("native_evidence", {})
        for key in ("bundle_check", "test", "smoke"):
            if key in native:
                lines.append(f"- {key.replace('_', ' ').title()}: `{native[key]['status']}`")
        lines.extend(["", "## Completeness", ""])
        for key, value in payload.get("completeness", {}).items():
            lines.append(f"- {key.replace('_', ' ')}: **{value}**")
    lines.extend(["", "## Explicit limitations", ""])
    lines.extend(f"- {item}." for item in payload.get("limitations", LIMITATIONS))
    signals = {row.get("kind") for row in payload.get("dynamic_signals", [])}
    if "dynamic-require" in signals:
        lines.append("- Dynamic require was observed and is intentionally unresolved.")
    lines.append("")
    return "\n".join(lines)


def _write(output: Path, evidence: Path, payload: dict) -> None:
    _atomic_json(evidence, payload)
    _atomic_text(output, _render(payload))


def _base_payload(args: argparse.Namespace, root: Path, targets: list[Path]) -> dict:
    return {
        "schema_version": 1,
        "language": "ruby",
        "analyzer": "ruby-3.3+-syntax+prism-ast+literal-load-layout",
        "name": args.name,
        "targets": [path.relative_to(root).as_posix() for path in targets],
        "generated_at": _now(),
        "limitations": LIMITATIONS,
    }


def _terminal_lifecycle(status: str) -> dict:
    return {
        "artifact_pair": "complete",
        "bounded_static_map": "failed" if status == "failed" else "not-run",
        "semantic_reachability": "not-run",
        "run": status,
    }


def _execute(
    args: argparse.Namespace,
    root: Path,
    targets: list[Path],
    evidence: Path,
) -> dict:
    paths = _candidate_paths(root)
    inventory = _inventory(root, paths)
    before_digest, before_files = _source_state(root, paths)
    if args.expected_source_sha256 and args.expected_source_sha256 != before_digest:
        raise Terminal(
            "failed",
            "stale_source_snapshot",
            "The current project-source manifest does not match --expected-source-sha256.",
            exit_code=2,
            source_fingerprints={"before": before_digest, "after": before_digest, "unchanged": True},
            expected_source_sha256=args.expected_source_sha256,
        )
    required = [root / "Gemfile", root / "Gemfile.lock"]
    gemspecs = sorted(root.glob("*.gemspec"))
    if any(not path.is_file() for path in required) or not gemspecs:
        raise Terminal(
            "unsupported",
            "project_metadata_missing",
            "Plain-Ruby/gem mapping requires Gemfile, Gemfile.lock, and a root gemspec.",
            source_inventory=inventory,
            source_fingerprints={"before": before_digest, "after": before_digest, "unchanged": True},
        )
    results, selected = _target_results(root, targets, inventory)
    if not selected:
        raise Terminal(
            "unsupported",
            "no_supported_target",
            "No selected target contains ordinary production .rb source.",
            target_results=results,
            source_inventory=inventory,
            source_fingerprints={"before": before_digest, "after": before_digest, "unchanged": True},
        )

    ruby = _resolve_tool(args.ruby)
    if ruby is None:
        raise Terminal("unsupported", "ruby_missing", "Ruby 3.3+ is required.")
    ruby_version, ruby_probe = _ruby_version(ruby, root)
    if ruby_version is None:
        raise Terminal("unsupported", "ruby_version_unavailable", ruby_probe)
    if ruby_version < args.minimum_ruby:
        raise Terminal("unsupported", "ruby_version_too_old", f"Ruby {ruby_version} is below {args.minimum_ruby}.")
    bundle = _resolve_tool(args.bundle)
    if bundle is None:
        raise Terminal("unsupported", "bundler_missing", "Bundler 2.6+ is required.")
    bundler_version, bundler_probe = _bundler_version(bundle, root)
    if bundler_version is None:
        raise Terminal("unsupported", "bundler_version_unavailable", bundler_probe)
    if bundler_version < args.minimum_bundler:
        raise Terminal("unsupported", "bundler_version_too_old", f"Bundler {bundler_version} is below {args.minimum_bundler}.")
    prism = _run([ruby, "--disable-gems", "-rprism", "-e", "puts Prism::VERSION"], cwd=root, timeout=10)
    if prism.returncode != 0 or not re.fullmatch(r"\d+(?:\.\d+){1,2}", prism.stdout.strip()):
        raise Terminal("unsupported", "prism_unavailable", (prism.stderr or prism.stdout or "Prism probe failed").strip())

    analysis_rows = [row for row in inventory if row["included"] and row["role"] != "symlink"]
    analysis_paths = [root / row["path"] for row in analysis_rows]
    syntax_checks = []
    for path in analysis_paths:
        completed = _run([ruby, "--disable-gems", "-c", str(path)], cwd=root, timeout=20)
        syntax_checks.append({
            "path": path.relative_to(root).as_posix(),
            "status": "passed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
        })
        if completed.returncode != 0:
            raise Terminal(
                "failed",
                "ruby_syntax_failed",
                (completed.stderr or completed.stdout or f"Ruby syntax failed for {path.name}").strip()[:4000],
                exit_code=2,
                syntax_errors=[syntax_checks[-1]],
            )

    bundle_state = evidence.parent / ".bundle-config"
    bundle_env = {
        **os.environ,
        "BUNDLE_APP_CONFIG": str(bundle_state),
        "BUNDLE_DISABLE_VERSION_CHECK": "true",
        "BUNDLE_FROZEN": "true",
        "BUNDLE_GEMFILE": str(root / "Gemfile"),
        "ALL_PROXY": "http://127.0.0.1:9",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
    }
    bundle_check = _run([bundle, "check"], cwd=root, env=bundle_env, timeout=30)
    if bundle_check.returncode != 0:
        raise Terminal(
            "failed",
            "bundle_check_failed",
            (bundle_check.stderr or bundle_check.stdout or "Frozen bundle check failed").strip()[:4000],
            exit_code=2,
        )

    declarations: list[dict] = []
    methods: list[dict] = []
    loads: list[dict] = []
    mixins: list[dict] = []
    constants: list[dict] = []
    dynamic: list[dict] = []
    for path in analysis_paths:
        relative = path.relative_to(root).as_posix()
        parsed = _prism_file(ruby, root, path)
        for key, destination in (
            ("declarations", declarations), ("methods", methods), ("loads", loads),
            ("mixins", mixins), ("constants", constants), ("dynamic", dynamic),
        ):
            destination.extend({**row, "file": relative} for row in parsed[key])

    declaration_names = {row["qualified_name"] for row in declarations}
    for row in constants:
        candidates = _constant_candidates(row["spelling"], row["owner"])
        matches = [candidate for candidate in candidates if candidate in declaration_names]
        row["candidate_declaration"] = matches[0] if len(matches) == 1 else None
        row["resolution"] = "lexical-static-candidate-not-runtime-identity"
    for row in mixins:
        candidates = _constant_candidates(row["target_spelling"], row["owner"])
        matches = [candidate for candidate in candidates if candidate in declaration_names]
        row["candidate_declaration"] = matches[0] if len(matches) == 1 else None
        row["resolution"] = "syntactic-mixin-spelling-not-runtime-application"

    literal_edges = []
    for row in loads:
        resolved, resolution = _resolve_load(root, root / row["file"], row["operation"], row["specifier"])
        edge = {key: value for key, value in row.items() if key != "file"}
        literal_edges.append({
            **edge,
            "caller": row["file"],
            "resolved_path": resolved,
            "resolution": resolution,
        })
    literal_edges = sorted(literal_edges, key=lambda row: (row["caller"], row["line"], row["operation"]))

    grouped: dict[str, list[dict]] = {}
    for row in declarations:
        grouped.setdefault(row["qualified_name"], []).append(row)
    namespace = [{
        "qualified_name": name,
        "definition_count": len(rows),
        "statically_reopened": len(rows) > 1,
        "definitions": [{"kind": row["kind"], "file": row["file"], "line": row["line"]} for row in rows],
        "claim": "syntax definitions only; runtime identity and execution order are unresolved",
    } for name, rows in sorted(grouped.items())]

    def _native(kind: str, raw: str | None) -> dict:
        if not raw:
            return {"status": "not-run", "path": None, "stdout": "", "stderr": "", "exit_code": None}
        path = Path(os.path.abspath(root / raw))
        if not _inside(path, root) or _has_symlink(path, root) or not path.is_file():
            raise Terminal("failed", f"native_{kind}_unsafe", f"Native {kind} path must be a regular file inside the project.", exit_code=2)
        completed = _run([ruby, "--disable-gems", f"-I{root / 'lib'}", str(path)], cwd=root, timeout=30)
        result = {
            "status": "passed" if completed.returncode == 0 else "failed",
            "path": path.relative_to(root).as_posix(),
            "stdout": completed.stdout[:4000],
            "stderr": completed.stderr[:4000],
            "exit_code": completed.returncode,
        }
        if completed.returncode != 0:
            raise Terminal("failed", f"native_{kind}_failed", (completed.stderr or completed.stdout or f"Native {kind} failed").strip()[:4000], exit_code=2, native_evidence={kind: result})
        return result

    test_result = _native("test", args.test)
    smoke_result = _native("smoke", args.smoke)
    optional_tools = {
        "rbs": _optional_tool(args.rbs, root),
        "typeprof": _optional_tool(args.typeprof, root),
    }
    after_paths = _candidate_paths(root)
    after_digest, after_files = _source_state(root, after_paths)
    if before_files != after_files:
        raise Terminal(
            "failed",
            "source_mutated",
            "Project source/configuration fingerprints changed during read-only mapping.",
            exit_code=2,
            source_fingerprints={"before": before_digest, "after": after_digest, "unchanged": False},
        )

    test_files = [row["path"] for row in inventory if row["role"] == "test"]
    entrypoints = []
    if args.test:
        entrypoints.append({"kind": "test", "path": args.test})
    if args.smoke:
        entrypoints.append({"kind": "executable", "path": args.smoke})
    target_coverage = "complete" if all(row["status"] == "complete" for row in results) else "partial"
    native_status = "complete" if args.test and args.smoke else "partial"
    return {
        "status": "partial",
        "failure_kind": "none",
        "message": "The bounded static Ruby/gem snapshot is complete; runtime semantic reachability remains partial by design.",
        "lifecycle": {
            "artifact_pair": "complete",
            "bounded_static_map": "complete",
            "semantic_reachability": "partial",
            "run": "partial",
        },
        "toolchain": {
            "ruby": {"path": ruby, "version": ".".join(map(str, ruby_version)), "probe": ruby_probe},
            "bundler": {"path": bundle, "version": ".".join(map(str, bundler_version)), "probe": bundler_probe},
            "prism": {"version": prism.stdout.strip(), "source": "selected Ruby default gem", "used": True},
            **optional_tools,
        },
        "target_results": results,
        "selected_source_files": selected,
        "source_inventory": inventory,
        "source_fingerprints": {"before": before_digest, "after": after_digest, "unchanged": True},
        "declarations": sorted(declarations, key=lambda row: (row["file"], row["line"], row["qualified_name"])),
        "methods": sorted(methods, key=lambda row: (row["file"], row["line"], row["owner"], row["name"])),
        "namespace_and_reopening_evidence": namespace,
        "mixins": sorted(mixins, key=lambda row: (row["file"], row["line"], row["operation"])),
        "literal_load_edges": literal_edges,
        "syntactic_constant_references": sorted(constants, key=lambda row: (row["file"], row["line"], row["spelling"])),
        "dynamic_signals": sorted(dynamic, key=lambda row: (row["file"], row["line"], row["kind"])),
        "test_files": test_files,
        "entrypoints": entrypoints,
        "native_evidence": {
            "syntax_checks": syntax_checks,
            "bundle_check": {
                "status": "passed",
                "exit_code": bundle_check.returncode,
                "stdout": bundle_check.stdout[:4000],
                "stderr": bundle_check.stderr[:4000],
                "policy": "frozen check only; no install or update",
            },
            "test": test_result,
            "smoke": smoke_result,
        },
        "completeness": {
            "source_inventory": "complete",
            "selected_target_coverage": target_coverage,
            "ruby_syntax": "complete",
            "declarations_and_methods": "complete",
            "literal_load_edges": "complete",
            "namespace_reopening_and_mixins": "complete-as-syntax-evidence",
            "native_test_and_smoke": native_status,
            "syntactic_constant_candidates": "complete-as-syntax-evidence",
            "dynamic_require_autoload_eval_and_metaprogramming": "partial",
            "runtime_symbol_identity": "partial",
            "rails_zeitwerk_framework_semantics": "unsupported",
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--ruby", default="ruby")
    parser.add_argument("--bundle", default="bundle")
    parser.add_argument("--rbs", default="rbs")
    parser.add_argument("--typeprof", default="typeprof")
    parser.add_argument("--minimum-ruby", default="3.3.0")
    parser.add_argument("--minimum-bundler", default="2.6.0")
    parser.add_argument("--test")
    parser.add_argument("--smoke")
    parser.add_argument("--expected-source-sha256")
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.name):
            raise UserError("name must be lowercase kebab-case")
        args.minimum_ruby = _version_argument(args.minimum_ruby, "--minimum-ruby")
        args.minimum_bundler = _version_argument(args.minimum_bundler, "--minimum-bundler")
        if args.expected_source_sha256 and not re.fullmatch(r"[0-9a-f]{64}", args.expected_source_sha256):
            raise UserError("--expected-source-sha256 must be a lowercase SHA-256 digest")
        root, targets, output, evidence = _validate_paths(args)
        output.unlink(missing_ok=True)
        evidence.unlink(missing_ok=True)
        base = _base_payload(args, root, targets)
        try:
            result = _execute(args, root, targets, evidence)
        except Terminal as terminal:
            payload = {
                **base,
                "status": terminal.status,
                "failure_kind": terminal.kind,
                "message": str(terminal),
                "lifecycle": _terminal_lifecycle(terminal.status),
                **terminal.facts,
            }
            _write(output, evidence, payload)
            return terminal.exit_code
        payload = {**base, **result}
        _write(output, evidence, payload)
        return 0
    except UserError as exc:
        print(f"map_ruby.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
