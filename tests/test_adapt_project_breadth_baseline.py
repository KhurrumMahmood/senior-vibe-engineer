"""Canonical filesystem discovery for the first specialized-language slice."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DISCOVER = ROOT / ".claude/skills/adapt-project/scripts/discover.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _state(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _discover(host: Path, artifacts: Path, language: str) -> tuple[dict, Path]:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DISCOVER),
            "--project-root",
            str(host),
            "--artifact-root",
            str(artifacts),
            "--timestamp",
            language,
            "--no-host-write",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    scan = Path(result.stdout.strip())
    return json.loads((scan / "adapter.json").read_text(encoding="utf-8")), scan


@pytest.mark.parametrize("language", ["php", "ruby", "rust", "dart"])
def test_canonical_discovery_identifies_specialized_real_repo_shapes(
    tmp_path: Path,
    language: str,
) -> None:
    host = tmp_path / language
    if language == "php":
        _write(
            host / "composer.json",
            json.dumps({"autoload": {"psr-4": {"Slim\\": "Slim"}}, "scripts": {"test": "phpunit"}}),
        )
        _write(host / "Slim/App.php", "<?php\nnamespace Slim;\nfinal class App {}\n")
        _write(host / "tests/AppTest.php", "<?php\nfinal class AppTest {}\n")
        expected_root, expected_commands = "Slim", {
            "test": "composer test",
            "lint": "composer validate --no-check-publish --no-interaction",
            "setup": "composer install --no-interaction",
        }
    elif language == "ruby":
        _write(host / "Gemfile", "source 'https://rubygems.org'\n")
        _write(host / "Rakefile", "task :test\n")
        _write(host / "sinatra.gemspec", "Gem::Specification.new { |spec| spec.name = 'sinatra' }\n")
        _write(host / "lib/sinatra/base.rb", "module Sinatra\n  class Base\n  end\nend\n")
        _write(host / "spec/base_spec.rb", "describe 'Base' do\nend\n")
        _write(host / "examples/demo.rb", "puts 'demo'\n")
        expected_root, expected_commands = "lib", {
            "test": "bundle exec rake test",
            "setup": "bundle install",
        }
    elif language == "rust":
        _write(host / "Cargo.toml", "[workspace]\nmembers = ['crates/core']\n")
        _write(host / "Cargo.lock", "version = 4\n")
        _write(host / "crates/core/src/lib.rs", "pub fn run() {}\n")
        _write(host / "crates/core/tests/integration.rs", "#[test]\nfn integration() {}\n")
        expected_root, expected_commands = "crates", {
            "test": "cargo test --locked",
            "lint": "cargo clippy --locked --all-targets",
            "setup": "cargo fetch --locked",
        }
    else:
        _write(host / "pubspec.yaml", "name: path\nenvironment:\n  sdk: ^3.12.0\n")
        _write(host / "lib/path.dart", "String join(String a, String b) => '$a/$b';\n")
        _write(host / "lib/generated.g.dart", "// generated\n")
        _write(host / "test/path_test.dart", "void main() {}\n")
        _write(host / "benchmark/path_benchmark.dart", "void main() {}\n")
        expected_root, expected_commands = "lib", {
            "test": "dart test",
            "lint": "dart analyze",
            "setup": "dart pub get",
        }
    before = _state(host)

    adapter, scan = _discover(host, tmp_path / f"{language}-artifacts", language)

    source = next(row for row in adapter["source_roots"] if row["path"] == expected_root)
    assert adapter["status"] == "complete"
    assert adapter["stack"]["languages"] == [language]
    assert source["source_languages"] == [language]
    assert source[f"{language}_files"] == 1
    assert not any(
        row["path"] in {"benchmark", "examples", "spec", "tests"}
        and language in row["source_languages"]
        for row in adapter["source_roots"]
    )
    assert adapter["analysis"][language] == {
        "status": "complete",
        "analyzer": "filesystem-source-inventory",
    }
    for kind, command in expected_commands.items():
        assert command in adapter["commands"][kind]
    assert f"{language.title() if language != 'php' else 'PHP'}: 1" in (
        scan / "report.md"
    ).read_text(encoding="utf-8")
    assert _state(host) == before
