from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import project_adapt


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_django_repo(root: Path) -> None:
    _write(root / "manage.py", "#!/usr/bin/env python3\n")
    _write(root / "requirements.txt", "Django>=4.2\nruff==0.6.9\n")
    _write(root / "pyproject.toml", "[tool.ruff]\n")
    _write(root / "CONTEXT.md", "**Site**: A configured crawl target.\n")
    _write(root / ".claude" / "CLAUDE.md", "# CLAUDE\n")
    _write(root / ".claude" / "docs" / "workflows" / "sites.md", "# Sites\n")
    _write(root / "app" / "services" / "site_intelligence" / "resolver.py", "VALUE = 1\n")
    _write(root / "scripts" / "agent_policy" / "policy.py", "VALUE = 1\n")
    _write(root / "scripts" / "lint" / "no_retailer_references.py", "VALUE = 1\n")
    _write(
        root / ".pre-commit-config.yaml",
        "repos:\n  - repo: local\n    hooks:\n      - id: no-retailer-references\n",
    )


def seed_react_repo(root: Path) -> None:
    _write(
        root / "package.json",
        '{"scripts":{"test":"vitest --run","lint":"eslint .","dev":"vite"},'
        '"dependencies":{"react":"latest","vite":"latest"}}',
    )
    _write(root / "pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
    _write(root / "src" / "App.tsx", "export function App() { return null }\n")


def test_discover_django_repo_detects_stack_and_guardrails(tmp_path):
    seed_django_repo(tmp_path)

    adapter = project_adapt.discover_project(tmp_path)

    assert "python" in adapter["stack"]["languages"]
    assert "django" in adapter["stack"]["frameworks"]
    assert any(".venv/bin/python" in command or "python3" in command
               for command in adapter["commands"]["test"])
    assert adapter["domain_terms"][0]["term"] == "Site"
    assert any("site_intelligence" in row["path"] for row in adapter["sensitive_surfaces"])
    assert adapter["standardization"]["observed_patterns_are_not_canonical"] is True


def test_discover_react_repo_detects_node_stack(tmp_path):
    seed_react_repo(tmp_path)

    adapter = project_adapt.discover_project(tmp_path)

    assert "javascript/typescript" in adapter["stack"]["languages"]
    assert "react" in adapter["stack"]["frameworks"]
    assert "pnpm" in adapter["stack"]["package_managers"]
    assert any("pnpm test" in command for command in adapter["commands"]["test"])


def test_interview_profile_requires_human_approval(tmp_path):
    seed_django_repo(tmp_path)
    adapter = project_adapt.discover_project(tmp_path)

    profile = project_adapt.build_profile_from_discovery(adapter)

    assert profile["user_approved"] is False
    assert profile["standardization_policy"]["do_not_canonize_by_frequency"] is True
    assert "critical_workflows" in profile["needs_user_input"]


def test_no_host_write_stores_artifacts_outside_target(tmp_path):
    project = tmp_path / "project"
    artifacts = tmp_path / "artifacts"
    seed_django_repo(project)

    scan_dir = project_adapt.write_discovery(
        project,
        artifacts,
        timestamp="20260517-120000",
        apply=False,
        no_host_write=True,
    )

    assert scan_dir == artifacts / "reports" / "adapt-project" / "scan-20260517-120000"
    assert (scan_dir / "adapter.yml").is_file()
    assert not (project / ".claude" / "project" / "adapter.yml").exists()


def test_no_host_write_rejects_artifact_root_inside_target(tmp_path):
    project = tmp_path / "project"
    seed_django_repo(project)

    with pytest.raises(ValueError, match="outside --project-root"):
        project_adapt.write_discovery(
            project,
            project / "reports",
            timestamp="20260517-120000",
            apply=False,
            no_host_write=True,
        )

    assert not (project / "reports").exists()
    assert not (project / ".claude" / "project" / "adapter.yml").exists()


def test_apply_writes_project_adapter(tmp_path):
    seed_django_repo(tmp_path)

    project_adapt.write_discovery(
        tmp_path,
        tmp_path,
        timestamp="20260517-120000",
        apply=True,
        no_host_write=False,
    )

    assert (tmp_path / ".claude" / "project" / "adapter.yml").is_file()


def test_schema_validators_accept_generated_artifacts(tmp_path):
    project = tmp_path / "project"
    artifact_root = tmp_path / "artifacts"
    seed_django_repo(project)

    adapt_dir = project_adapt.write_discovery(
        project,
        artifact_root,
        timestamp="20260517-120000",
        apply=False,
        no_host_write=True,
    )
    profile_dir = project_adapt.write_profile_draft(
        project,
        artifact_root,
        timestamp="20260517-120001",
        apply=False,
        no_host_write=True,
    )
    adapter = yaml.safe_load((adapt_dir / "adapter.yml").read_text(encoding="utf-8"))
    profile = yaml.safe_load((profile_dir / "profile.yml").read_text(encoding="utf-8"))

    assert project_adapt.validate_adapter_payload(adapter) == []
    assert project_adapt.validate_profile_payload(profile) == []


def test_evaluate_dogfood_writes_required_sections(tmp_path):
    project = tmp_path / "pnci-pricing"
    artifacts = tmp_path / "dogfood"
    seed_django_repo(project)

    path = project_adapt.evaluate_dogfood(project, artifacts, reference="pnci-pricing")

    text = path.read_text(encoding="utf-8")
    assert "## Good Inference" in text
    assert "## Needs Interview" in text
    assert "## Kernel Candidate" in text


def test_evaluate_dogfood_rejects_artifact_root_inside_target(tmp_path):
    project = tmp_path / "pnci-pricing"
    seed_django_repo(project)

    with pytest.raises(ValueError, match="outside --project-root"):
        project_adapt.evaluate_dogfood(project, project / "reports", reference="pnci-pricing")
