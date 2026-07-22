"""Frozen PHP pilot host, source-role, and native preflight evidence."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "php-pilot"
BASELINE = ROOT / ".claude" / "tasks" / "p4-baseline" / "php-pilot-baseline.json"
INVENTORY = ROOT / "scripts" / "source_inventory.py"


def _manifest(root: Path) -> tuple[str, int, list[str]]:
    rows: list[tuple[str, str, int]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        content = path.read_bytes()
        rows.append(
            (
                path.relative_to(root).as_posix(),
                hashlib.sha256(content).hexdigest(),
                len(content),
            )
        )
    digest = hashlib.sha256()
    for path, file_digest, _size in rows:
        digest.update(path.encode() + b"\0" + file_digest.encode() + b"\n")
    return digest.hexdigest(), sum(row[2] for row in rows), [row[0] for row in rows]


def test_php_pilot_fixture_matches_frozen_manifest() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["fixture"]

    digest, total_bytes, files = _manifest(FIXTURE)

    assert digest == baseline["manifest_sha256"]
    assert total_bytes == baseline["total_bytes"]
    assert files == baseline["files"]


def test_php_pilot_inventory_roles_are_honest_and_read_only(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    before = _manifest(host)
    output = host / "inventory.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(INVENTORY),
            "--project-root",
            str(host),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    after_without_output = _manifest(host)
    assert before[0] != after_without_output[0]
    payload = json.loads(output.read_text(encoding="utf-8"))
    output.unlink()
    assert _manifest(host) == before
    files = {row["path"]: row for row in payload["files"]}
    assert files["src/Billing/InvoiceService.php"]["role"] == "source"
    assert files["tests/Billing/InvoiceServiceTest.php"]["role"] == "test"
    assert files["generated/GeneratedProxy.php"]["role"] == "generated"
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded["build"] == "build"
    assert excluded["vendor"] == "vendor"


def test_php_pilot_native_valid_and_malformed_boundaries() -> None:
    php = shutil.which("php")
    if php is None:
        pytest.skip("PHP is unavailable; the profile doctor reports this boundary")
    host = FIXTURE / "host"
    for script in ("tests/lint.php", "tests/smoke.php"):
        completed = subprocess.run(
            [php, script], cwd=host, capture_output=True, text=True, check=False
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr

    malformed = subprocess.run(
        [php, "-l", str(FIXTURE / "malformed" / "Broken.php")],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    assert malformed.returncode != 0
    assert "Errors parsing" in malformed.stdout + malformed.stderr
