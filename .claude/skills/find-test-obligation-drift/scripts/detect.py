#!/usr/bin/env python3
"""Detect verification obligation drift for touched files."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
COMMON_DIR = PROJECT_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

from product_health import expand_paths, finding  # noqa: E402
from product_topology import relpath, write_jsonl  # noqa: E402

SUFFIXES = (".py", ".js", ".html", ".md", ".yaml", ".yml", ".toml")


def _run_git_name_only(project_root: Path, cmd: list[str]) -> list[str]:
    try:
        result = subprocess.run(cmd, cwd=project_root, text=True, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_files(project_root: Path, *, staged: bool = False, changed_from: str | None = None) -> list[str]:
    if changed_from:
        cmd = ["git", "diff", "--name-only", changed_from]
        return _run_git_name_only(project_root, cmd)
    elif staged:
        cmd = ["git", "diff", "--cached", "--name-only"]
        return _run_git_name_only(project_root, cmd)
    else:
        cmd = ["git", "diff", "--name-only"]
        untracked_cmd = ["git", "ls-files", "--others", "--exclude-standard"]
        return sorted(set(_run_git_name_only(project_root, cmd) + _run_git_name_only(project_root, untracked_cmd)))


def _changed_paths(
    project_root: Path,
    paths: list[str] | None,
    *,
    staged: bool = False,
    changed_from: str | None = None,
) -> list[Path]:
    if paths:
        return expand_paths(project_root, paths, SUFFIXES)
    return [project_root / file for file in _git_files(project_root, staged=staged, changed_from=changed_from)]


def _is_backend_runtime(file: str) -> bool:
    return file.startswith(("app/api/", "app/services/sites", "app/pages/sites")) and file.endswith(".py")


def _is_ui_runtime(file: str) -> bool:
    return (
        (file.startswith("static/js/") and file.endswith(".js"))
        or (file.startswith(("templates/", "app/pages/sites/templates/")) and file.endswith(".html"))
    )


def _is_quality_tool(file: str) -> bool:
    return file.startswith(("scripts/lint/", "scripts/")) and file.endswith(".py")


def _skill_root(file: str) -> str | None:
    parts = file.split("/")
    if len(parts) >= 3 and parts[0] == ".claude" and parts[1] == "skills":
        if parts[2] == "_common":
            return None
        return "/".join(parts[:3])
    return None


def _has_skill_smoke_equivalent(root: str, file_set: set[str]) -> bool:
    skill_name = root.rsplit("/", 1)[-1]
    if skill_name == "which-skill":
        return any(file.startswith("tests/scripts/test_which_skill") for file in file_set)
    return False


def _is_ui_test(file: str) -> bool:
    return (
        file.startswith("testing/") and file.endswith(".py")
    ) or file in {
        "tests/test_site_config_sidebar.py",
    }


def detect(
    project_root: Path,
    paths: list[str] | None = None,
    *,
    staged: bool = False,
    changed_from: str | None = None,
) -> list[dict[str, object]]:
    changed = [path for path in _changed_paths(project_root, paths, staged=staged, changed_from=changed_from) if path.exists()]
    files = [relpath(path, project_root) for path in changed]
    file_set = set(files)
    records: list[dict[str, object]] = []

    backend_files = [file for file in files if _is_backend_runtime(file)]
    ui_files = [file for file in files if _is_ui_runtime(file)]
    quality_files = [
        file
        for file in files
        if _is_quality_tool(file) and not file.startswith(("scripts/_lib/", "scripts/log_effectiveness.py"))
    ]
    skill_roots = sorted({root for file in files if (root := _skill_root(file))})

    has_backend_test = any(file.startswith("tests/") and file.endswith(".py") for file in files)
    has_ui_test = any(_is_ui_test(file) for file in files)
    has_quality_test = any(file.startswith("tests/scripts/") or file == "tests/test_quality_tools.py" for file in files)

    if backend_files and not has_backend_test:
        first = project_root / backend_files[0]
        records.append(
            finding(
                "missing_backend_test_obligation",
                first,
                1,
                f"{len(backend_files)} backend `/sites` file(s) changed without a touched backend test file.",
                "Add or update targeted tests, or record why this is docs/comment-only despite touching backend runtime code.",
                project_root,
                confidence="medium",
                next_skill="prevent-regression",
                guard_candidate=False,
                obligation="backend targeted or always-suite verification",
            )
        )
    if ui_files and not has_ui_test:
        first = project_root / ui_files[0]
        records.append(
            finding(
                "missing_ui_test_obligation",
                first,
                1,
                f"{len(ui_files)} UI/template/static file(s) changed without a touched Playwright or site-page DOM contract test.",
                "Update `testing/test_site_pages.py` or a targeted site-page DOM contract test for the affected `/sites` surface, or capture why text-only changes do not need it.",
                project_root,
                confidence="medium",
                next_skill="prevent-regression",
                guard_candidate=False,
                obligation="Playwright or site-page DOM contract verification",
            )
        )
    for root in skill_roots:
        smoke = project_root / root / "scripts" / "smoke.py"
        touched_script = any(file.startswith(f"{root}/scripts/") for file in file_set)
        if not touched_script:
            continue
        has_smoke_in_diff = f"{root}/scripts/smoke.py" in file_set
        if smoke.exists() or has_smoke_in_diff or _has_skill_smoke_equivalent(root, file_set):
            continue
        records.append(
            finding(
                "missing_skill_smoke_obligation",
                project_root / root / "SKILL.md" if (project_root / root / "SKILL.md").exists() else root,
                1,
                f"`{root}` changed without a detector smoke test.",
                "Add a `scripts/smoke.py` or an equivalent shared fixture test before treating the skill output as reliable.",
                project_root,
                confidence="high",
                next_skill="prevent-regression",
                guard_candidate=True,
                obligation="skill smoke test",
            )
        )
    if quality_files and not has_quality_test:
        first = project_root / quality_files[0]
        records.append(
            finding(
                "missing_quality_tool_test_obligation",
                first,
                1,
                f"{len(quality_files)} quality/tooling script file(s) changed without tests/scripts or quality-tool coverage.",
                "Add fixture coverage under `tests/scripts/` or update `tests/test_quality_tools.py` for the changed lint/tool behavior.",
                project_root,
                confidence="medium",
                next_skill="prevent-regression",
                guard_candidate=True,
                obligation="quality-tool test",
            )
        )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--changed-from")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    records = detect(
        args.project_root.resolve(),
        args.paths or None,
        staged=args.staged,
        changed_from=args.changed_from,
    )
    write_jsonl(records, args.output)
    print(f"wrote {args.output}: {len(records)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
