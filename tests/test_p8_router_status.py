from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTERS = ("which-shape", "which-skill", "which-cleanup")


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _snapshot(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    library = tmp_path / "library"
    skills = library / ".claude" / "skills"
    for name in (*ROUTERS, "_common"):
        shutil.copytree(ROOT / ".claude" / "skills" / name, skills / name)
    (library / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "host_migrations.py", library / "scripts")
    _git(library, "init", "--quiet")
    _git(library, "add", ".")
    _git(
        library,
        "-c",
        "user.name=Status Test",
        "-c",
        "user.email=status@example.com",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )

    host = tmp_path / "host"
    installed = host / ".agents" / "skills"
    for name in ROUTERS:
        shutil.copytree(skills / name, installed / name)
    engineering = host / ".engineering"
    engineering.mkdir()
    (engineering / ".gitignore").write_text("/local/\n", encoding="utf-8")
    (engineering / "manifest.json").write_text(
        json.dumps(
            {
                "version": 3,
                "applied_migrations": [
                    "0001-subsystem-registry-home",
                    "0002-subsystem-maps-home",
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (host / "skills-lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    name: {
                        "source": str(library),
                        "sourceType": "local",
                        "computedHash": f"lock-{name}",
                    }
                    for name in ROUTERS
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return host, library, installed


def _status(host: Path, library: Path, installed: Path) -> dict:
    script = installed / "which-skill" / "scripts" / "status.py"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-I",
            "-S",
            str(script),
            "--project-root",
            str(host),
            "--library-root",
            str(library),
            "--json",
        ],
        cwd=host,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_status_reports_exact_code_and_schema_match_without_writes(tmp_path):
    host, library, installed = _fixture(tmp_path)
    before = _snapshot(host)

    payload = _status(host, library, installed)

    assert payload["compatibility"] == {
        "router_code_matches_library": True,
        "host_state_matches_library": True,
        "overall": "match",
    }
    assert payload["library_git"] == {
        "head": _git(library, "rev-parse", "HEAD"),
        "dirty": False,
    }
    assert all(row["matches_library"] for row in payload["routers"])
    assert all(row["effective_ref"] == payload["library_git"]["head"] for row in payload["routers"])
    assert payload["host_state"]["current_schema"] == 3
    assert payload["host_state"]["target_schema"] == 3
    assert payload["host_state"]["pending_migrations"] == []
    assert _snapshot(host) == before


def test_status_reports_installed_router_drift(tmp_path):
    host, library, installed = _fixture(tmp_path)
    guide = installed / "which-cleanup" / "SKILL.md"
    guide.write_text(guide.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")

    payload = _status(host, library, installed)

    cleanup = next(row for row in payload["routers"] if row["skill"] == "which-cleanup")
    assert cleanup["matches_library"] is False
    assert cleanup["effective_ref"] is None
    assert payload["compatibility"]["overall"] == "mismatch"
