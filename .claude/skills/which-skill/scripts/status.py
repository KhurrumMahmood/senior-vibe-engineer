#!/usr/bin/env python3
"""Report installed-router, library, and host-schema compatibility without writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROUTERS = ("which-shape", "which-skill", "which-cleanup")


def default_library_root(project_root: Path) -> Path:
    return project_root.parent / ".engineering-skills" / project_root.name


def _tree_digest(root: Path) -> str | None:
    if not root.is_dir() or root.is_symlink():
        return None
    digest = hashlib.sha256()
    files = [path for path in sorted(root.rglob("*")) if path.is_file()]
    for path in files:
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git_state(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        return {"head": None, "dirty": None}
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {"head": None, "dirty": None}
    value = head.stdout.strip()
    return {
        "head": value if head.returncode == 0 and value else None,
        "dirty": bool(dirty.stdout) if dirty.returncode == 0 else None,
    }


def _lock_rows(project_root: Path) -> tuple[str, dict[str, Any]]:
    path = project_root / "skills-lock.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["skills"]
        if not isinstance(payload, dict) or not isinstance(rows, dict):
            raise TypeError("invalid lock shape")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return str(path), {}
    return str(path), rows


def _migration_status(project_root: Path, library_root: Path) -> dict[str, Any]:
    script = library_root / "scripts" / "host_migrations.py"
    if not script.is_file():
        return {
            "available": False,
            "reason": "migration_runner_missing",
            "runner": str(script),
        }
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-I",
            "-S",
            str(script),
            "--project-root",
            str(project_root),
            "status",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise TypeError("status is not an object")
    except (json.JSONDecodeError, TypeError):
        return {
            "available": False,
            "reason": "migration_status_invalid",
            "runner": str(script),
            "exit_code": result.returncode,
            "stderr": result.stderr.strip(),
        }
    return {
        "available": True,
        "runner": str(script),
        "exit_code": result.returncode,
        "status": payload.get("status"),
        "current_schema": payload.get("current_schema"),
        "target_schema": payload.get("target_schema"),
        "pending_migrations": payload.get("pending_migrations", []),
        "applied_migrations": payload.get("applied_migrations", []),
        "blockers": payload.get("blockers", []),
    }


def build_status(
    *, project_root: Path, library_root: Path, router_root: Path
) -> dict[str, Any]:
    lock_path, lock_rows = _lock_rows(project_root)
    library_git = _git_state(library_root)
    routers = []
    for name in ROUTERS:
        installed = router_root / name
        library = library_root / ".claude" / "skills" / name
        installed_digest = _tree_digest(installed)
        library_digest = _tree_digest(library)
        byte_match = bool(installed_digest and installed_digest == library_digest)
        lock = lock_rows.get(name) if isinstance(lock_rows.get(name), dict) else None
        effective_ref = (
            library_git["head"]
            if byte_match and library_git["dirty"] is False
            else None
        )
        routers.append(
            {
                "skill": name,
                "installed_root": str(installed),
                "installed_digest": installed_digest,
                "library_root": str(library),
                "library_digest": library_digest,
                "matches_library": byte_match,
                "lock": lock,
                "effective_ref": effective_ref,
                "effective_ref_basis": (
                    "installed bytes equal the router tree at library HEAD"
                    if effective_ref
                    else None
                ),
            }
        )
    migration = _migration_status(project_root, library_root)
    code_match = all(row["matches_library"] for row in routers)
    state_match = bool(
        migration.get("available")
        and migration.get("status") in {"ready", "current"}
        and migration.get("current_schema") == migration.get("target_schema")
        and not migration.get("pending_migrations")
        and not migration.get("blockers")
    )
    return {
        "schema_version": 1,
        "project_root": str(project_root),
        "router_root": str(router_root),
        "skills_lock": lock_path,
        "library_root": str(library_root),
        "library_git": library_git,
        "routers": routers,
        "host_state": migration,
        "compatibility": {
            "router_code_matches_library": code_match,
            "host_state_matches_library": state_match,
            "overall": "match" if code_match and state_match else "mismatch",
        },
    }


def render(payload: dict[str, Any]) -> str:
    lines = [
        f"Compatibility: {payload['compatibility']['overall']}",
        f"Library HEAD: {payload['library_git']['head'] or 'unavailable'}",
    ]
    for row in payload["routers"]:
        state = "matches" if row["matches_library"] else "mismatch"
        lines.append(f"Router /{row['skill']}: {state}")
    host = payload["host_state"]
    if host.get("available"):
        lines.append(
            "Host schema: "
            f"{host.get('current_schema')} -> {host.get('target_schema')} "
            f"(pending: {len(host.get('pending_migrations', []))})"
        )
    else:
        lines.append(f"Host schema: unavailable ({host.get('reason')})")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--library-root", type=Path)
    parser.add_argument("--router-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    library_root = args.library_root or default_library_root(project_root)
    if not library_root.is_absolute():
        library_root = project_root / library_root
    router_root = args.router_root or Path(__file__).resolve().parents[2]
    if not router_root.is_absolute():
        router_root = project_root / router_root
    payload = build_status(
        project_root=project_root,
        library_root=library_root.resolve(),
        router_root=router_root.resolve(),
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
