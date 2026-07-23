"""Public contract tests for the additive Dart D2 provider facts used by D3."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / ".claude/skills/_dart/scripts/dart_syntax_facts.py"
DART = Path("/opt/homebrew/bin/dart")
pytestmark = pytest.mark.skipif(not DART.is_file(), reason="Dart 3.12 SDK unavailable")


SCHEMA_SOURCE = """\
import 'dart:math' as math;

export 'exported.dart';

part 'schema_part.dart';

typedef LegacyMapper = int Function(String value);
typedef Mapper<T> = T Function(T value);

class PublicClass {
  PublicClass();
  PublicClass.named();

  int method(int value) => math.max(value, partValue);

  int get total => 1;

  set total(int value) {}

  PublicClass operator +(PublicClass other) => this;

  void _privateMethod() {}
}

enum PublicEnum {
  one;

  int enumMethod() => 1;
}

extension PublicExtension on int {
  int extensionMethod() => this;
}

extension on String {
  int anonymousMethod() => length;
}

mixin PublicMixin {
  void mixinMethod() {}
}

class _PrivateClass {
  void visibleInsidePrivate() {}
}

int usePrivateShapes() {
  PublicClass()._privateMethod();
  _PrivateClass().visibleInsidePrivate();
  return 'value'.anonymousMethod();
}

int get topLevelGetter => 1;

set topLevelSetter(int value) {}

int cloneOne(int value) {
  return value * 2;
}

int cloneTwo(int value) {
  return value * 2;
}

int branchOwner(int value, List<int> values) {
  if (value > 0 && value < 5 || values.isEmpty) {
    value++;
  }
  for (final item in values) {
    value += item;
  }
  while (value < -10) {
    value++;
  }
  do {
    value--;
  } while (value > 100);
  switch (value) {
    case 1:
      value += 1;
      break;
    case > 2:
      value += 2;
      break;
    default:
      value += 3;
  }
  try {
    if (value == 42) {
      throw StateError('bounded');
    }
  } on StateError catch (_) {
    value = 0;
  }

  int localBranch(int nested) {
    if (nested > 0 && values.isNotEmpty) {
      nested++;
    }
    return nested;
  }

  final closure = (int nested) {
    while (nested < 0 || values.isEmpty) {
      nested++;
    }
    return nested;
  };
  return localBranch(closure(value));
}
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    _write(
        host / "pubspec.yaml",
        """\
name: dart_d2_provider_extension_fixture
environment:
  sdk: \">=3.12.0 <3.13.0\"
""",
    )
    _write(host / "lib/schema.dart", SCHEMA_SOURCE)
    _write(host / "lib/exported.dart", "class ExportedClass {}\n")
    _write(
        host / "lib/schema_part.dart",
        """\
part of 'schema.dart';

const partValue = 3;
""",
    )
    _write(
        host / "tool/provider_native_test.dart",
        """\
import '../lib/schema.dart';

void main() {
  if (cloneOne(2) != cloneTwo(2)) {
    throw StateError('clone mismatch');
  }
}
""",
    )
    _write(
        host / "bin/provider_smoke.dart",
        """\
import '../lib/schema.dart';

void main() {
  print('dart-d2-provider:${cloneOne(2)}');
}
""",
    )
    _write(host / "test/excluded_test.dart", "class ExcludedTestClass {}\n")
    _write(host / "generated/excluded.g.dart", "class ExcludedGeneratedClass {}\n")
    external = tmp_path / "external"
    _write(external / "excluded_link.dart", "class ExcludedLinkedClass {}\n")
    (host / "linked-external").symlink_to(external, target_is_directory=True)
    return host


def _state(root: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return state


def _provider(host: Path, *, provider: Path = PROVIDER) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(provider),
            "--project-root",
            str(host),
            "--target",
            ".",
            "--dart",
            str(DART),
            "--native-test",
            "tool/provider_native_test.dart",
            "--smoke",
            "bin/provider_smoke.dart",
            "--smoke-stdout",
            "dart-d2-provider:4\n",
            "--json",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def test_provider_emits_exact_d3_fact_groups_spans_and_owner_boundaries(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    before = _state(host)
    result = _provider(host)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert (payload["status"], payload["failure_kind"]) == ("complete", "none")
    assert payload["source_manifest"]["preserved"] is True
    assert _state(host) == before

    inventory = {row["file"]: row for row in payload["inventory"]}
    assert inventory["test/excluded_test.dart"]["role"] == "test"
    assert inventory["generated/excluded.g.dart"]["role"] == "generated"
    assert inventory["linked-external"]["role"] == "symlink"
    serialized_files = json.dumps(payload["files"])
    assert "ExcludedTestClass" not in serialized_files
    assert "ExcludedGeneratedClass" not in serialized_files
    assert "ExcludedLinkedClass" not in serialized_files

    files = {row["file"]: row for row in payload["files"]}
    assert {
        "calls",
        "comments",
        "declarations",
        "diagnostics",
        "direct_body_branches",
        "directives",
        "file",
        "functions",
        "named_bodies",
        "body_tokens",
        "source_sha256",
    } == set(files["lib/schema.dart"])

    directives = [row for file in files.values() for row in file["directives"]]
    assert {(row["kind"], row["uri"]) for row in directives} >= {
        ("import", "dart:math"),
        ("export", "exported.dart"),
        ("part", "schema_part.dart"),
        ("part_of", "schema.dart"),
    }
    assert all(
        set(row)
        == {
            "column",
            "end",
            "kind",
            "line",
            "offset",
            "supported",
            "unsupported_reason",
            "uri",
        }
        for row in directives
    )
    assert all(row["supported"] is True and row["unsupported_reason"] is None for row in directives)

    source = (host / "lib/schema.dart").read_text(encoding="utf-8")
    declarations = files["lib/schema.dart"]["declarations"]
    assert all(
        set(row)
        == {
            "anonymous",
            "container",
            "container_offset",
            "end",
            "end_line",
            "kind",
            "line",
            "name",
            "offset",
            "private",
            "supported",
            "top_level",
            "unsupported_reason",
        }
        for row in declarations
    )
    declared_shapes = {(row["kind"], row["name"], row["container"]) for row in declarations}
    assert declared_shapes >= {
        ("typedef", "LegacyMapper", None),
        ("typedef", "Mapper", None),
        ("class", "PublicClass", None),
        ("constructor", "PublicClass", "PublicClass"),
        ("constructor", "PublicClass.named", "PublicClass"),
        ("method", "method", "PublicClass"),
        ("getter", "total", "PublicClass"),
        ("setter", "total", "PublicClass"),
        ("operator", "+", "PublicClass"),
        ("enum", "PublicEnum", None),
        ("method", "enumMethod", "PublicEnum"),
        ("extension", "PublicExtension", None),
        ("method", "extensionMethod", "PublicExtension"),
        ("extension", None, None),
        ("method", "anonymousMethod", None),
        ("mixin", "PublicMixin", None),
        ("method", "mixinMethod", "PublicMixin"),
        ("getter", "topLevelGetter", None),
        ("setter", "topLevelSetter", None),
        ("top_level_function", "cloneOne", None),
        ("top_level_function", "branchOwner", None),
    }
    assert not any(row["name"] == "localBranch" for row in declarations)
    anonymous = next(row for row in declarations if row["kind"] == "extension" and row["name"] is None)
    assert (anonymous["anonymous"], anonymous["private"]) == (True, True)
    private_container_member = next(row for row in declarations if row["name"] == "visibleInsidePrivate")
    assert private_container_member["private"] is True
    for row in declarations:
        assert row["line"] == _line(source, row["offset"])
        assert row["end_line"] == _line(source, row["end"] - 1)
        assert source[row["offset"] : row["end"]]

    bodies = files["lib/schema.dart"]["named_bodies"]
    assert all(
        set(row)
        == {
            "body_end",
            "body_end_line",
            "body_line",
            "body_offset",
            "container",
            "declaration_end",
            "declaration_offset",
            "kind",
            "name",
        }
        for row in bodies
    )
    body_shapes = {(row["kind"], row["name"], row["container"]) for row in bodies}
    assert body_shapes >= {
        ("constructor", "PublicClass", "PublicClass"),
        ("constructor", "PublicClass.named", "PublicClass"),
        ("method", "method", "PublicClass"),
        ("getter", "total", "PublicClass"),
        ("setter", "total", "PublicClass"),
        ("operator", "+", "PublicClass"),
        ("top_level_function", "cloneOne", None),
        ("top_level_function", "cloneTwo", None),
        ("top_level_function", "branchOwner", None),
    }
    assert not any(row["name"] == "localBranch" for row in bodies)
    declarations_by_offset = {row["offset"]: row for row in declarations}
    for row in bodies:
        declaration = declarations_by_offset[row["declaration_offset"]]
        assert (row["name"], row["kind"], row["container"]) == (
            declaration["name"],
            declaration["kind"],
            declaration["container"],
        )
        assert row["body_line"] == _line(source, row["body_offset"])
        assert row["body_end_line"] == _line(source, row["body_end"] - 1)
        assert source[row["body_offset"] : row["body_end"]]

    branch_body = next(row for row in bodies if row["name"] == "branchOwner")
    branches = [
        row
        for row in files["lib/schema.dart"]["direct_body_branches"]
        if row["declaration_offset"] == branch_body["declaration_offset"]
    ]
    assert all(
        set(row) == {"column", "declaration_offset", "end", "kind", "line", "offset"}
        for row in branches
    )
    assert Counter(row["kind"] for row in branches) == {
        "if": 2,
        "logical_and": 1,
        "logical_or": 1,
        "for": 1,
        "while": 1,
        "do": 1,
        "switch_case": 2,
        "catch": 1,
    }
    event_lexemes = {
        "if": "if",
        "logical_and": "&&",
        "logical_or": "||",
        "for": "for",
        "while": "while",
        "do": "do",
        "switch_case": "case",
        "catch": "catch",
    }
    for row in branches:
        assert source[row["offset"] : row["end"]] == event_lexemes[row["kind"]]
        assert row["line"] == _line(source, row["offset"])
    nested_offsets = {
        source.index("if (nested > 0"),
        source.index("&& values.isNotEmpty"),
        source.index("while (nested < 0"),
        source.index("|| values.isEmpty", source.index("final closure")),
    }
    assert not nested_offsets & {row["offset"] for row in branches}

    tokens = files["lib/schema.dart"]["body_tokens"]
    assert all(
        set(row)
        == {"declaration_offset", "end", "index", "lexeme", "offset", "token_kind"}
        for row in tokens
    )
    for body in bodies:
        body_tokens = [row for row in tokens if row["declaration_offset"] == body["declaration_offset"]]
        assert [row["index"] for row in body_tokens] == list(range(len(body_tokens)))
        assert [row["offset"] for row in body_tokens] == sorted(row["offset"] for row in body_tokens)
        assert all(
            source[row["offset"] : row["end"]] == row["lexeme"]
            and body["body_offset"] <= row["offset"] < row["end"] <= body["body_end"]
            for row in body_tokens
        )
    clone_bodies = {row["name"]: row for row in bodies if row["name"] in {"cloneOne", "cloneTwo"}}
    clone_sequences = {
        name: [
            (row["token_kind"], row["lexeme"])
            for row in tokens
            if row["declaration_offset"] == body["declaration_offset"]
        ]
        for name, body in clone_bodies.items()
    }
    assert clone_sequences["cloneOne"] == clone_sequences["cloneTwo"]


def test_conditional_directive_is_partial_and_valid_recovers(tmp_path: Path) -> None:
    host = _host(tmp_path)
    first = _provider(host)
    assert first.returncode == 0, first.stdout + first.stderr

    source_path = host / "lib/schema.dart"
    original = source_path.read_text(encoding="utf-8")
    conditional = original.replace(
        "import 'dart:math' as math;",
        "import 'platform_stub.dart' if (dart.library.io) 'dart:math' as math;",
        1,
    )
    source_path.write_text(conditional, encoding="utf-8")
    _write(
        host / "lib/platform_stub.dart",
        """\
int max(int left, int right) => left > right ? left : right;
""",
    )
    before_partial = _state(host)
    partial = _provider(host)
    assert partial.returncode == 2, partial.stdout + partial.stderr
    partial_payload = json.loads(partial.stdout)
    assert (partial_payload["status"], partial_payload["failure_kind"]) == (
        "partial",
        "unsupported_dart_syntax",
    )
    conditional_row = next(
        row
        for file in partial_payload["files"]
        for row in file["directives"]
        if row["kind"] == "import" and row["uri"] == "platform_stub.dart"
    )
    assert (conditional_row["supported"], conditional_row["unsupported_reason"]) == (
        False,
        "conditional_configuration",
    )
    assert partial_payload["source_manifest"]["preserved"] is True
    assert _state(host) == before_partial

    source_path.write_text(original, encoding="utf-8")
    (host / "lib/platform_stub.dart").unlink()
    recovered = _provider(host)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    recovered_payload = json.loads(recovered.stdout)
    assert (recovered_payload["status"], recovered_payload["failure_kind"]) == (
        "complete",
        "none",
    )


def test_additive_contract_runs_from_copied_dart_closure(tmp_path: Path) -> None:
    host = _host(tmp_path)
    installed = tmp_path / "installed" / ".agents" / "skills" / "_dart"
    shutil.copytree(ROOT / ".claude/skills/_dart", installed)
    copied_provider = installed / "scripts/dart_syntax_facts.py"
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(copied_provider),
            "--project-root",
            str(host),
            "--target",
            ".",
            "--dart",
            str(DART),
            "--native-test",
            "tool/provider_native_test.dart",
            "--smoke",
            "bin/provider_smoke.dart",
            "--smoke-stdout",
            "dart-d2-provider:4\n",
            "--json",
        ],
        cwd=unrelated,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    source = next(row for row in payload["files"] if row["file"] == "lib/schema.dart")
    assert all(source[key] for key in ("directives", "declarations", "named_bodies", "body_tokens"))
    assert source["direct_body_branches"]
    assert payload["source_manifest"]["preserved"] is True
