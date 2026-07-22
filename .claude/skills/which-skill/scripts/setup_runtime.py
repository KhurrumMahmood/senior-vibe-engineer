#!/usr/bin/env python3
"""Create and verify the Python runtime used by engineering-skills."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


MINIMUM_PYTHON = (3, 11)
PROBE_TIMEOUT_SECONDS = 5
PROBE_CODE = """
import json
import shutil
import ssl
import sys
import venv

print(json.dumps({
    "version": list(sys.version_info[:3]),
    "prefix": sys.prefix,
}))
"""


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _resolve_executable(value: str) -> Path | None:
    candidate = Path(value).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        return candidate.resolve()
    found = shutil.which(value)
    return Path(found).resolve() if found else None


def _pyenv_candidates() -> list[Path]:
    versions_root = Path.home() / ".pyenv" / "versions"
    if not versions_root.is_dir():
        return []
    candidates: list[Path] = []
    for minor in ("3.11", "3.12", "3.13"):
        for version_root in sorted(versions_root.glob(f"{minor}*"), reverse=True):
            for name in (f"python{minor}", "python3", "python"):
                candidate = version_root / "bin" / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    candidates.append(candidate.resolve())
                    break
    return candidates


def interpreter_candidates(explicit: str | None = None) -> list[Path]:
    if explicit:
        resolved = _resolve_executable(explicit)
        return [resolved] if resolved else []

    raw: list[Path] = [Path(sys.executable).resolve()]
    for name in ("python3.11", "python3.12", "python3.13", "python3"):
        found = shutil.which(name)
        if found:
            raw.append(Path(found).resolve())
    raw.extend(_pyenv_candidates())

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in raw:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def probe_interpreter(
    candidate: Path,
    *,
    expected_prefix: Path | None = None,
) -> tuple[tuple[int, int, int] | None, str | None]:
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        return None, "not an executable file"
    isolation_flags = ["-I"] if expected_prefix is not None else ["-I", "-S"]
    try:
        result = _run(
            [str(candidate), *isolation_flags, "-c", PROBE_CODE],
            cwd=candidate.parent,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return None, f"health probe timed out after {PROBE_TIMEOUT_SECONDS}s"
    except OSError as exc:
        return None, str(exc)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "probe failed"
        return None, detail
    try:
        payload = json.loads(result.stdout)
        version = tuple(int(part) for part in payload["version"])
        prefix = Path(payload["prefix"]).resolve()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return None, f"invalid health-probe output: {exc}"
    if version < MINIMUM_PYTHON:
        return None, f"Python {'.'.join(map(str, version))} is below 3.11"
    if expected_prefix is not None and prefix != expected_prefix.resolve():
        return None, f"runtime prefix is {prefix}, expected {expected_prefix.resolve()}"
    if expected_prefix is not None:
        config = expected_prefix / "pyvenv.cfg"
        try:
            command_line = next(
                (
                    line
                    for line in config.read_text(encoding="utf-8").splitlines()
                    if line.startswith("command = ")
                ),
                None,
            )
        except (OSError, UnicodeError) as exc:
            return None, f"cannot read {config}: {exc}"
        if command_line and str(expected_prefix.resolve()) not in command_line:
            return None, f"venv was created for another location: {command_line[10:]}"
    return version, None


def select_interpreter(explicit: str | None = None) -> tuple[Path, tuple[int, int, int]]:
    failures: list[str] = []
    candidates = interpreter_candidates(explicit)
    if explicit and not candidates:
        raise ValueError(f"requested Python executable was not found: {explicit}")
    for candidate in candidates:
        version, error = probe_interpreter(candidate)
        if version is not None:
            return candidate, version
        failures.append(f"{candidate}: {error}")
    detail = "; ".join(failures) if failures else "no candidates found"
    raise ValueError(
        "no healthy Python >= 3.11 interpreter was found; "
        f"checked {detail}. Install Python 3.11+ and rerun with --python /absolute/path."
    )


def _dependencies_healthy(project_root: Path, runtime_python: Path) -> tuple[bool, str]:
    pip_check = _run(
        [str(runtime_python), "-m", "pip", "check"],
        cwd=project_root,
    )
    if pip_check.returncode != 0:
        return False, pip_check.stdout.strip() or pip_check.stderr.strip()

    requirements = (project_root / "requirements.txt").read_text(encoding="utf-8")
    if "pyyaml" in requirements.lower():
        yaml_check = _run(
            [str(runtime_python), "-I", "-c", "import yaml"],
            cwd=project_root,
        )
        if yaml_check.returncode != 0:
            return False, yaml_check.stderr.strip() or "PyYAML import failed"
    return True, "dependencies resolve"


def setup_runtime(
    *,
    project_root: Path,
    explicit_python: str | None,
    check_only: bool,
    install_hooks: bool,
) -> tuple[Path, tuple[int, int, int], str, str]:
    project_root = project_root.resolve()
    requirements = project_root / "requirements.txt"
    if not requirements.is_file():
        raise ValueError(f"requirements file not found: {requirements}")

    venv_root = project_root / ".venv"
    runtime_python = venv_root / "bin" / "python"
    current_version, current_error = probe_interpreter(
        runtime_python,
        expected_prefix=venv_root,
    )
    if check_only:
        if current_version is None:
            raise ValueError(f"runtime is not ready at {runtime_python}: {current_error}")
        dependencies_ok, detail = _dependencies_healthy(project_root, runtime_python)
        if not dependencies_ok:
            raise ValueError(f"runtime dependencies are not ready: {detail}")
        return runtime_python, current_version, "already present", "not changed"

    venv_state = "already present"
    if current_version is None:
        interpreter, _ = select_interpreter(explicit_python)
        if venv_root.exists() or venv_root.is_symlink():
            if venv_root.is_symlink() or venv_root.is_file():
                venv_root.unlink()
            else:
                shutil.rmtree(venv_root)
            venv_state = "rebuilt"
        else:
            venv_state = "created"
        created = _run(
            [str(interpreter), "-m", "venv", str(venv_root)],
            cwd=project_root,
        )
        if created.returncode != 0:
            detail = created.stderr.strip() or created.stdout.strip() or "venv creation failed"
            raise ValueError(detail)

    installed = _run(
        [
            str(runtime_python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(requirements),
        ],
        cwd=project_root,
    )
    if installed.returncode != 0:
        detail = installed.stderr.strip() or installed.stdout.strip() or "dependency install failed"
        raise ValueError(detail)

    version, error = probe_interpreter(runtime_python, expected_prefix=venv_root)
    if version is None:
        raise ValueError(f"created runtime failed its health probe: {error}")
    dependencies_ok, detail = _dependencies_healthy(project_root, runtime_python)
    if not dependencies_ok:
        raise ValueError(f"runtime dependency verification failed: {detail}")

    hook_state = "not requested"
    if install_hooks:
        git_check = _run(
            ["git", "-C", str(project_root), "rev-parse", "--is-inside-work-tree"],
            cwd=project_root,
        )
        if git_check.returncode == 0 and git_check.stdout.strip() == "true":
            hook = _run(
                [str(runtime_python), "-m", "pre_commit", "install"],
                cwd=project_root,
            )
            if hook.returncode != 0:
                detail = hook.stderr.strip() or hook.stdout.strip() or "pre-commit install failed"
                raise ValueError(detail)
            hook_state = "installed"
        else:
            hook_state = "skipped (not a git worktree)"
    return runtime_python, version, venv_state, hook_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--python", help="exact Python executable to use when creating the venv")
    parser.add_argument("--check", action="store_true", help="verify without changing anything")
    parser.add_argument(
        "--no-hooks",
        action="store_true",
        help="do not install pre-commit hooks (used by the external on-demand library)",
    )
    args = parser.parse_args(argv)
    try:
        runtime_python, version, venv_state, hook_state = setup_runtime(
            project_root=args.project_root,
            explicit_python=args.python,
            check_only=args.check,
            install_hooks=not args.no_hooks,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Python: {'.'.join(map(str, version))}")
    print(f"venv: {venv_state} ({runtime_python})")
    print("dependencies: verified from requirements.txt")
    print(f"pre-commit hooks: {hook_state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
