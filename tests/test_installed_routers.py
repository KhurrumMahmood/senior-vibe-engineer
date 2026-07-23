from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"
DEFAULT_ROUTERS = ("which-shape", "which-skill", "which-cleanup")
STACK_BOUND_SKILLS = (
    "extract-cotton-primitive",
    "extract-state-type",
    "extract-workflow-registry",
    "find-async-lifecycle-drift",
    "find-contract-drift",
    "find-dead-route-surface",
    "find-doc-route-drift",
    "find-frontend-contract-drift",
    "find-frontend-duplication",
    "find-layer-violation",
    "find-query-mutation",
    "find-route-sprawl",
    "find-test-obligation-drift",
    "find-transaction-overreach",
    "find-workflow-duplication",
    "find-workflow-state-gaps",
    "fix-workflow",
    "impact-feature",
    "introduce-fk",
    "map-product-workflow",
    "plan-feature",
    "refactor-subsystem",
)


def _install_router(host: Path, name: str) -> Path:
    destination = host / ".agents" / "skills" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILLS_ROOT / name, destination)
    return destination


def _run_isolated(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(script), *args],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )


def _json_output(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_default_routers_materialize_an_on_demand_library_outside_discovery(tmp_path):
    host = tmp_path / "host"
    installed = {
        name: _install_router(host, name)
        for name in DEFAULT_ROUTERS
    }

    cleanup_smoke = _run_isolated(
        installed["which-cleanup"] / "scripts" / "smoke.py",
        cwd=host,
    )
    assert cleanup_smoke.returncode == 0, cleanup_smoke.stdout + cleanup_smoke.stderr
    assert "which-cleanup smoke: OK" in cleanup_smoke.stdout

    bootstrap = _run_isolated(
        installed["which-skill"] / "scripts" / "bootstrap_library.py",
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        "--skip-runtime",
        cwd=host,
    )

    assert bootstrap.returncode == 0, bootstrap.stdout + bootstrap.stderr
    library_root = host.parent / ".engineering-skills" / host.name
    assert (library_root / ".claude" / "skills" / "diagnose" / "SKILL.md").is_file()
    assert (library_root / "scripts").is_dir()
    assert {
        path.name
        for path in (host / ".agents" / "skills").iterdir()
        if path.is_dir()
    } == set(DEFAULT_ROUTERS)

    repeated = _run_isolated(
        installed["which-skill"] / "scripts" / "bootstrap_library.py",
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        "--skip-runtime",
        cwd=host,
    )
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert "already available" in repeated.stdout

    routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "diagnose failing export job regression with no reproduction yet",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )

    payload = _json_output(routed)
    assert "install" not in payload
    assert payload["handoff"]["mode"] == "on_demand_library"
    assert payload["handoff"]["available"] is True
    assert payload["handoff"]["default_execution"] == "fresh_non_context_subagent"
    assert payload["handoff"]["guides"] == [
        {
            "skill": "diagnose",
            "skill_root": str(library_root / ".claude" / "skills" / "diagnose"),
            "guide": str(library_root / ".claude" / "skills" / "diagnose" / "SKILL.md"),
            "bundled_tooling": str(
                library_root / ".claude" / "skills" / "diagnose" / "scripts"
            ),
        }
    ]
    assert payload["handoff"]["shared_tooling"] == str(library_root / "scripts")
    assert payload["handoff"]["common_guidance"] == str(
        library_root / ".claude" / "skills" / "_common"
    )
    assert payload["handoff"]["shared_guidance"] == str(library_root / ".claude" / "docs")
    assert payload["handoff"]["source_inventory_tool"] == str(
        library_root / "scripts" / "source_inventory.py"
    )
    assert payload["handoff"]["runtime"] == {
        "available": False,
        "python": str(library_root / ".venv" / "bin" / "python"),
    }
    assert payload["handoff"]["capabilities"]["available"] is True
    assert payload["handoff"]["capabilities"]["manifest"] == str(
        library_root / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
    )
    assert payload["handoff"]["capabilities"]["skills"] == [
        {
            "skill": "diagnose",
            "expansion_disposition": "validated-neutral",
            "typescript_disposition": "validated-neutral",
            "javascript_disposition": "validated-neutral",
            "go_disposition": "validated-neutral",
            "java_disposition": "validated-neutral",
            "php_disposition": "validated-neutral",
            "swift_disposition": "validated-neutral",
            "c_disposition": "validated-neutral",
            "cpp_disposition": "validated-neutral",
            "ruby_disposition": "validated-neutral",
            "rust_disposition": "validated-neutral",
            "fact_level": "neutral",
            "outcome_class": "not-applicable",
            "framework_family": None,
            "closure_skills": ["diagnose"],
            "optional_install_status": "passed",
        }
    ]
    assert payload["optional_install"]["available"] is True
    assert payload["optional_install"]["evidence"] == [
        {"skill": "diagnose", "status": "passed"}
    ]
    assert "--skill diagnose" in payload["optional_install"]["command"]

    resource_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use plan-feature to plan this Django workflow",
        "--project-root",
        str(host),
        "--language",
        "python",
        "--framework",
        "django",
        "--json",
        cwd=host,
    )
    resource_payload = _json_output(resource_routed)
    assert resource_payload["recommendation"] == "plan-feature"
    selected_root = Path(resource_payload["handoff"]["guides"][0]["skill_root"])
    assert (selected_root / "agents" / "impact-scout.md").is_file()
    assert (selected_root / "knowledge").is_dir()
    assert resource_payload["handoff"]["capabilities"]["skills"][0] == {
        "skill": "plan-feature",
        "expansion_disposition": "framework-bound",
        "typescript_disposition": "stack-bound",
        "javascript_disposition": "stack-bound",
        "go_disposition": "stack-bound",
        "java_disposition": "stack-bound",
        "php_disposition": "stack-bound",
        "swift_disposition": "stack-bound",
        "c_disposition": "stack-bound",
        "cpp_disposition": "stack-bound",
        "ruby_disposition": "stack-bound",
        "rust_disposition": "stack-bound",
        "fact_level": "framework",
        "outcome_class": "framework-specific",
        "framework_family": "architecture-planning",
        "closure_skills": ["plan-feature"],
        "optional_install_status": "deferred-named-stack",
    }
    assert resource_payload["optional_install"]["available"] is False
    assert (
        resource_payload["optional_install"]["reason"]
        == "selected_skill_install_not_validated"
    )
    assert "command" not in resource_payload["optional_install"]

    typescript_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "find repeated bare status literals in src/job.ts",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )
    typescript_payload = _json_output(typescript_routed)
    assert typescript_payload["handoff"]["capabilities"]["skills"][0] == {
        "skill": "find-implicit-state",
        "expansion_disposition": "language-level",
        "typescript_disposition": "typescript-supported",
        "javascript_disposition": "javascript-supported",
        "go_disposition": "go-supported",
        "java_disposition": "java-supported",
        "php_disposition": "php-pending-implementation",
        "swift_disposition": "swift-pending-implementation",
        "c_disposition": "c-pending-implementation",
        "cpp_disposition": "cpp-pending-implementation",
        "ruby_disposition": "ruby-pending-implementation",
        "rust_disposition": "rust-supported",
        "fact_level": "semantic-project",
        "outcome_class": "read-only-report",
        "framework_family": None,
        "closure_skills": ["find-implicit-state", "map-subsystem"],
        "optional_install_status": "passed",
    }

    java_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "audit syntactic branch complexity in Java methods and constructors",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )
    java_payload = _json_output(java_routed)
    assert java_payload["routing_context"]["language"] == "java"
    assert java_payload["recommendation"] == "find-complexity-hotspots"
    assert java_payload["handoff"]["skills"] == ["find-complexity-hotspots"]
    assert java_payload["handoff"]["capabilities"]["skills"][0][
        "java_disposition"
    ] == "java-supported"

    for skill, task in (
        ("propose-boundary", "use propose-boundary for a Java package boundary"),
        ("move-path", "use move-path to move a Java package directory"),
    ):
        routed = _run_isolated(
            installed["which-skill"] / "scripts" / "match.py",
            task,
            "--project-root",
            str(host),
            "--json",
            cwd=host,
        )
        routed_payload = _json_output(routed)
        assert routed_payload["recommendation"] == skill
        assert routed_payload["handoff"]["capabilities"]["skills"][0][
            "java_disposition"
        ] == "java-supported"

    for skill, task in (
        ("find-complexity-hotspots", "use find-complexity-hotspots on Go source"),
        (
            "find-duplication",
            "audit exact normalized duplicate Golang function bodies without "
            "claiming that consolidation is safe",
        ),
        ("find-dormant", "use find-dormant to review dormant Golang functions"),
        ("map-subsystem", "use map-subsystem on this Golang package"),
        ("propose-boundary", "use propose-boundary for a Go package boundary"),
        ("move-path", "use move-path to move a Go package directory"),
    ):
        go_routed = _run_isolated(
            installed["which-skill"] / "scripts" / "match.py",
            task,
            "--project-root",
            str(host),
            "--json",
            cwd=host,
        )
        go_payload = _json_output(go_routed)
        assert go_payload["recommendation"] == skill
        assert go_payload["handoff"]["available"] is True
        assert go_payload["handoff"]["capabilities"]["skills"][0][
            "go_disposition"
        ] == "go-supported"
        assert Path(go_payload["handoff"]["guides"][0]["guide"]).is_file()

    php_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use find-comment-drift on PHP source",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "php",
        "--json",
        cwd=host,
    )
    php_payload = _json_output(php_routed)
    assert php_payload["recommendation"] == "find-comment-drift"
    assert php_payload["handoff"]["available"] is True
    assert php_payload["handoff"]["capabilities"]["skills"][0][
        "php_disposition"
    ] == "php-supported"

    pending_php = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use adapt-project on this PHP repository",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "php",
        "--json",
        cwd=host,
    )
    assert pending_php.returncode == 1
    pending_php_payload = json.loads(pending_php.stdout)
    assert pending_php_payload["recommendation"] == "pending-implementation"
    assert pending_php_payload["unavailable"]["classification"] == (
        "pending-implementation"
    )
    assert pending_php_payload["unavailable"]["reason"] == (
        "/adapt-project declares php_disposition=php-pending-implementation"
    )

    swift_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use find-omnibus on Swift source",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "swift",
        "--json",
        cwd=host,
    )
    swift_payload = _json_output(swift_routed)
    assert swift_payload["recommendation"] == "find-omnibus"
    assert swift_payload["handoff"]["available"] is True
    assert swift_payload["handoff"]["capabilities"]["skills"][0][
        "swift_disposition"
    ] == "swift-supported"

    pending_swift = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use adapt-project on this Swift repository",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "swift",
        "--json",
        cwd=host,
    )
    assert pending_swift.returncode == 1
    pending_swift_payload = json.loads(pending_swift.stdout)
    assert pending_swift_payload["recommendation"] == "pending-implementation"
    assert pending_swift_payload["unavailable"]["classification"] == (
        "pending-implementation"
    )
    assert pending_swift_payload["unavailable"]["reason"] == (
        "/adapt-project declares swift_disposition=swift-pending-implementation"
    )

    c_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use find-comment-drift on C17 source",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "c",
        "--json",
        cwd=host,
    )
    c_payload = _json_output(c_routed)
    assert c_payload["recommendation"] == "find-comment-drift"
    assert c_payload["handoff"]["available"] is True
    assert c_payload["handoff"]["capabilities"]["skills"][0][
        "c_disposition"
    ] == "c-supported"

    pending_c = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use adapt-project on this C17 repository",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "c",
        "--json",
        cwd=host,
    )
    assert pending_c.returncode == 1
    pending_c_payload = json.loads(pending_c.stdout)
    assert pending_c_payload["recommendation"] == "pending-implementation"
    assert pending_c_payload["unavailable"]["classification"] == (
        "pending-implementation"
    )
    assert pending_c_payload["unavailable"]["reason"] == (
        "/adapt-project declares c_disposition=c-pending-implementation"
    )

    cpp_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use map-subsystem on this C++ repository",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "cpp",
        "--json",
        cwd=host,
    )
    cpp_payload = _json_output(cpp_routed)
    assert cpp_payload["recommendation"] == "map-subsystem"
    assert cpp_payload["handoff"]["available"] is True
    assert cpp_payload["handoff"]["capabilities"]["skills"][0][
        "cpp_disposition"
    ] == "cpp-supported"

    pending_cpp = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use adapt-project on this C++ repository",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "cpp",
        "--json",
        cwd=host,
    )
    assert pending_cpp.returncode == 1
    pending_cpp_payload = json.loads(pending_cpp.stdout)
    assert pending_cpp_payload["routing_context"]["language"] == "cpp"
    assert pending_cpp_payload["recommendation"] == "pending-implementation"
    assert pending_cpp_payload["unavailable"]["classification"] == (
        "pending-implementation"
    )
    assert pending_cpp_payload["unavailable"]["reason"] == (
        "/adapt-project declares cpp_disposition=cpp-pending-implementation"
    )

    ruby_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use find-comment-drift on Ruby source",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "ruby",
        "--json",
        cwd=host,
    )
    ruby_payload = _json_output(ruby_routed)
    assert ruby_payload["recommendation"] == "find-comment-drift"
    assert ruby_payload["handoff"]["available"] is True
    assert ruby_payload["handoff"]["capabilities"]["skills"][0][
        "ruby_disposition"
    ] == "ruby-supported"

    partial_ruby = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use map-subsystem on this Ruby repository",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "ruby",
        "--json",
        cwd=host,
    )
    assert partial_ruby.returncode == 1
    partial_ruby_payload = json.loads(partial_ruby.stdout)
    assert partial_ruby_payload["recommendation"] == "partial"
    assert partial_ruby_payload["unavailable"]["classification"] == "partial"
    assert partial_ruby_payload["unavailable"]["reason"] == (
        "/map-subsystem declares ruby_disposition=ruby-partial"
    )

    pending_ruby = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use adapt-project on this Ruby repository",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "ruby",
        "--json",
        cwd=host,
    )
    assert pending_ruby.returncode == 1
    pending_ruby_payload = json.loads(pending_ruby.stdout)
    assert pending_ruby_payload["recommendation"] == "pending-implementation"
    assert pending_ruby_payload["unavailable"]["reason"] == (
        "/adapt-project declares ruby_disposition=ruby-pending-implementation"
    )

    for skill, task in (
        ("adapt-project", "use adapt-project on this Rust repository"),
        ("audit-decisions", "use audit-decisions on this Rust repository"),
        ("explain-code", "use explain-code on this Rust source"),
        ("extract-enum", "use extract-enum on this Rust state finding"),
        (
            "find-complexity-hotspots",
            "use find-complexity-hotspots on this Rust source",
        ),
        (
            "find-concept-divergence",
            "use find-concept-divergence on this Rust source",
        ),
        ("find-duplication", "use find-duplication on this Rust source"),
        (
            "find-folder-topology-drift",
            "use find-folder-topology-drift on this Rust source root",
        ),
        ("find-dormant", "use find-dormant on this Rust repository"),
        (
            "find-implicit-state",
            "use find-implicit-state on this Rust repository",
        ),
        (
            "find-incomplete-sweep",
            "use find-incomplete-sweep on this Rust repository",
        ),
        ("find-omnibus", "use find-omnibus on this Rust source"),
        (
            "find-semantic-duplication",
            "use find-semantic-duplication on this Rust source",
        ),
        (
            "find-standard-gaps",
            "use find-standard-gaps on this Rust source",
        ),
        (
            "prevent-regression",
            "use prevent-regression for this reviewed Rust state migration",
        ),
        ("propose-boundary", "use propose-boundary on this Rust package"),
        (
            "propose-folder-reorganization",
            "use propose-folder-reorganization on this Rust source folder",
        ),
        ("rename-concept", "use rename-concept on this Rust repository"),
        ("unify-shadows", "use unify-shadows on this Rust semantic finding"),
    ):
        rust_family = _run_isolated(
            installed["which-skill"] / "scripts" / "match.py",
            task,
            "--project-root",
            str(host),
            "--library-root",
            str(library_root),
            "--language",
            "rust",
            "--json",
            cwd=host,
        )
        rust_family_payload = _json_output(rust_family)
        assert rust_family_payload["recommendation"] == skill
        assert rust_family_payload["handoff"]["available"] is True
        assert rust_family_payload["handoff"]["capabilities"]["skills"][0][
            "rust_disposition"
        ] == "rust-supported"

    rust_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use find-comment-drift on Rust source",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "rust",
        "--json",
        cwd=host,
    )
    rust_payload = _json_output(rust_routed)
    assert rust_payload["recommendation"] == "find-comment-drift"
    assert rust_payload["handoff"]["available"] is True
    assert rust_payload["handoff"]["capabilities"]["skills"][0][
        "rust_disposition"
    ] == "rust-supported"

    rust_move = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use move-path for a Rust module file move",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "rust",
        "--json",
        cwd=host,
    )
    rust_move_payload = _json_output(rust_move)
    assert rust_move_payload["recommendation"] == "move-path"
    assert rust_move_payload["handoff"]["available"] is True
    assert rust_move_payload["handoff"]["capabilities"]["skills"][0][
        "rust_disposition"
    ] == "rust-supported"

    rust_map = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use map-subsystem on this Rust repository",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--language",
        "rust",
        "--json",
        cwd=host,
    )
    assert rust_map.returncode == 1
    rust_map_payload = json.loads(rust_map.stdout)
    assert rust_map_payload["recommendation"] == "partial"
    assert rust_map_payload["unavailable"]["classification"] == "partial"
    assert rust_map_payload["unavailable"]["reason"] == (
        "/map-subsystem declares rust_disposition=rust-partial"
    )

    shape_routed = _run_isolated(
        installed["which-shape"] / "scripts" / "route.py",
        "onboard an unknown inherited repo and figure out what loop to run",
        "--project-root",
        str(host),
        "--json",
        "--skip-log",
        cwd=host,
    )
    shape_payload = _json_output(shape_routed)
    assert shape_payload["handoff"]["capabilities"]["skills"][0] == {
        "skill": "adapt-project",
        "expansion_disposition": "language-level",
        "typescript_disposition": "typescript-supported",
        "javascript_disposition": "javascript-supported",
        "go_disposition": "go-supported",
        "java_disposition": "java-supported",
        "php_disposition": "php-pending-implementation",
        "swift_disposition": "swift-pending-implementation",
        "c_disposition": "c-pending-implementation",
        "cpp_disposition": "cpp-pending-implementation",
        "ruby_disposition": "ruby-pending-implementation",
        "rust_disposition": "rust-supported",
        "fact_level": "lexical-filesystem",
        "outcome_class": "configuration-output",
        "framework_family": None,
        "closure_skills": ["adapt-project"],
        "optional_install_status": "passed",
    }

    php_shape = _run_isolated(
        installed["which-shape"] / "scripts" / "route.py",
        "onboard an unknown inherited PHP repository and figure out what loop to run",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--json",
        "--skip-log",
        cwd=host,
    )
    php_shape_payload = _json_output(php_shape)
    assert php_shape_payload["recommendation"]["first_next"] == "/adapt-project"
    assert php_shape_payload["handoff"]["available"] is False
    assert php_shape_payload["handoff"]["reason"] == (
        "selected_skill_pending_implementation"
    )
    assert php_shape_payload["handoff"]["blocked"] == [
        {
            "skill": "adapt-project",
            "language": "php",
            "disposition": "php-pending-implementation",
        }
    ]

    swift_shape = _run_isolated(
        installed["which-shape"] / "scripts" / "route.py",
        "onboard an unknown inherited Swift repository and figure out what loop to run",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--json",
        "--skip-log",
        cwd=host,
    )
    swift_shape_payload = _json_output(swift_shape)
    assert swift_shape_payload["recommendation"]["first_next"] == "/adapt-project"
    assert swift_shape_payload["handoff"]["available"] is False
    assert swift_shape_payload["handoff"]["reason"] == (
        "selected_skill_pending_implementation"
    )
    assert swift_shape_payload["handoff"]["blocked"] == [
        {
            "skill": "adapt-project",
            "language": "swift",
            "disposition": "swift-pending-implementation",
        }
    ]

    c_shape = _run_isolated(
        installed["which-shape"] / "scripts" / "route.py",
        "onboard an unknown inherited C17 repository and figure out what loop to run",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--json",
        "--skip-log",
        cwd=host,
    )
    c_shape_payload = _json_output(c_shape)
    assert c_shape_payload["recommendation"]["first_next"] == "/adapt-project"
    assert c_shape_payload["handoff"]["available"] is False
    assert c_shape_payload["handoff"]["reason"] == (
        "selected_skill_pending_implementation"
    )
    assert c_shape_payload["handoff"]["blocked"] == [
        {
            "skill": "adapt-project",
            "language": "c",
            "disposition": "c-pending-implementation",
        }
    ]

    cpp_shape = _run_isolated(
        installed["which-shape"] / "scripts" / "route.py",
        "onboard an unknown inherited C++ repository and figure out what loop to run",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--json",
        "--skip-log",
        cwd=host,
    )
    cpp_shape_payload = _json_output(cpp_shape)
    assert cpp_shape_payload["recommendation"]["first_next"] == "/adapt-project"
    assert cpp_shape_payload["handoff"]["available"] is False
    assert cpp_shape_payload["handoff"]["reason"] == (
        "selected_skill_pending_implementation"
    )
    assert cpp_shape_payload["handoff"]["blocked"] == [
        {
            "skill": "adapt-project",
            "language": "cpp",
            "disposition": "cpp-pending-implementation",
        }
    ]

    ruby_shape = _run_isolated(
        installed["which-shape"] / "scripts" / "route.py",
        "onboard an unknown inherited Ruby repository and figure out what loop to run",
        "--project-root",
        str(host),
        "--library-root",
        str(library_root),
        "--json",
        "--skip-log",
        cwd=host,
    )
    ruby_shape_payload = _json_output(ruby_shape)
    assert ruby_shape_payload["recommendation"]["first_next"] == "/adapt-project"
    assert ruby_shape_payload["handoff"]["available"] is False
    assert ruby_shape_payload["handoff"]["reason"] == (
        "selected_skill_pending_implementation"
    )
    assert ruby_shape_payload["handoff"]["blocked"] == [
        {
            "skill": "adapt-project",
            "language": "ruby",
            "disposition": "ruby-pending-implementation",
        }
    ]

    cleanup_routed = _run_isolated(
        installed["which-cleanup"] / "scripts" / "route.py",
        "src/app.py",
        "tests/test_app.py",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )
    cleanup_payload = _json_output(cleanup_routed)
    cleanup_recommendations = {
        item["skill"]: item for item in cleanup_payload["recommendations"]
    }
    assert cleanup_recommendations["find-test-obligation-drift"]["handoff"][
        "capabilities"
    ]["skills"][0] == {
        "skill": "find-test-obligation-drift",
        "expansion_disposition": "framework-bound",
        "typescript_disposition": "stack-bound",
        "javascript_disposition": "stack-bound",
        "go_disposition": "stack-bound",
        "java_disposition": "stack-bound",
        "php_disposition": "stack-bound",
        "swift_disposition": "stack-bound",
        "c_disposition": "stack-bound",
        "cpp_disposition": "stack-bound",
        "ruby_disposition": "stack-bound",
        "rust_disposition": "stack-bound",
        "fact_level": "framework",
        "outcome_class": "framework-specific",
        "framework_family": "framework-quality",
        "closure_skills": ["find-test-obligation-drift"],
        "optional_install_status": "deferred-named-stack",
    }
    cleanup_install = cleanup_recommendations["find-test-obligation-drift"][
        "optional_install"
    ]
    assert cleanup_install["available"] is False
    assert cleanup_install["reason"] == "selected_skill_install_not_validated"
    assert "command" not in cleanup_install

    regression = cleanup_recommendations["prevent-regression"]
    assert regression["handoff"]["skills"] == [
        "prevent-regression",
        "find-implicit-state",
        "map-subsystem",
    ]
    assert [guide["skill"] for guide in regression["handoff"]["guides"]] == [
        "prevent-regression",
        "find-implicit-state",
        "map-subsystem",
    ]
    assert regression["handoff"]["capabilities"]["available"] is True
    assert [
        row["skill"] for row in regression["handoff"]["capabilities"]["skills"]
    ] == ["prevent-regression", "find-implicit-state", "map-subsystem"]
    assert regression["optional_install"]["available"] is True
    assert "--skill prevent-regression" in regression["optional_install"]["command"]
    assert "--skill find-implicit-state" in regression["optional_install"]["command"]
    assert "--skill map-subsystem" in regression["optional_install"]["command"]

    rename_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use rename-concept to rename the TypeScript domain term",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )
    rename_payload = _json_output(rename_routed)
    rename_capabilities = rename_payload["handoff"]["capabilities"]
    assert rename_payload["handoff"]["skills"] == [
        "rename-concept",
        "find-concept-divergence",
        "map-subsystem",
    ]
    assert rename_capabilities["available"] is True
    assert rename_capabilities["skills"][0]["closure_skills"] == [
        "rename-concept",
        "find-concept-divergence",
        "map-subsystem",
    ]
    assert [row["optional_install_status"] for row in rename_capabilities["skills"]] == [
        "passed",
        "passed",
        "passed",
    ]
    assert rename_payload["optional_install"]["available"] is True
    assert "--skill rename-concept" in rename_payload["optional_install"]["command"]
    assert "--skill find-concept-divergence" in rename_payload["optional_install"][
        "command"
    ]
    assert "--skill map-subsystem" in rename_payload["optional_install"]["command"]


def test_library_bootstrap_creates_and_verifies_runtime_by_default(tmp_path):
    source = tmp_path / "source"
    for router in DEFAULT_ROUTERS:
        guide = source / ".claude" / "skills" / router / "SKILL.md"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text(f"# {router}\n", encoding="utf-8")
    scripts = source / "scripts"
    scripts.mkdir()
    (scripts / ".keep").write_text("\n", encoding="utf-8")
    (source / "requirements.txt").write_text("# no packages needed\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Router Test",
            "-c",
            "user.email=router@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=source,
        check=True,
    )

    host = tmp_path / "host"
    router = _install_router(host, "which-skill")
    bootstrap = _run_isolated(
        router / "scripts" / "bootstrap_library.py",
        "--project-root",
        str(host),
        "--source",
        str(source),
        "--python",
        sys.executable,
        cwd=host,
    )

    assert bootstrap.returncode == 0, bootstrap.stdout + bootstrap.stderr
    library_root = host.parent / ".engineering-skills" / host.name
    runtime_python = library_root / ".venv" / "bin" / "python"
    assert runtime_python.is_file()
    assert "dependencies: verified from requirements.txt" in bootstrap.stdout

    checked = _run_isolated(
        router / "scripts" / "setup_runtime.py",
        "--project-root",
        str(library_root),
        "--check",
        "--no-hooks",
        cwd=host,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "venv: already present" in checked.stdout

    routed = _run_isolated(
        router / "scripts" / "match.py",
        "choose which skill to use for this ambiguous task",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )
    payload = _json_output(routed)
    assert payload["recommendation"] == "which-skill"
    assert payload["handoff"]["runtime"] == {
        "available": True,
        "python": str(runtime_python),
    }


def test_runtime_setup_rejects_an_explicit_python_below_the_minimum(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "requirements.txt").write_text("# no packages needed\n", encoding="utf-8")
    fake_python = tmp_path / "python3.10"
    fake_python.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' '{\"version\":[3,10,14],\"prefix\":\"/tmp/fake\"}'\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    router = _install_router(project_root, "which-skill")

    result = _run_isolated(
        router / "scripts" / "setup_runtime.py",
        "--project-root",
        str(project_root),
        "--python",
        str(fake_python),
        "--no-hooks",
        cwd=project_root,
    )

    assert result.returncode == 2
    assert "below 3.11" in result.stderr
    assert not (project_root / ".venv").exists()


def test_runtime_setup_rebuilds_a_venv_moved_from_another_root(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "requirements.txt").write_text("# no packages needed\n", encoding="utf-8")
    old_venv = tmp_path / "old-venv"
    subprocess.run([sys.executable, "-m", "venv", str(old_venv)], check=True)
    old_venv.rename(project_root / ".venv")
    router = _install_router(project_root, "which-skill")

    result = _run_isolated(
        router / "scripts" / "setup_runtime.py",
        "--project-root",
        str(project_root),
        "--python",
        sys.executable,
        "--no-hooks",
        cwd=project_root,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "venv: rebuilt" in result.stdout
    config = (project_root / ".venv" / "pyvenv.cfg").read_text(encoding="utf-8")
    assert str(project_root / ".venv") in config


def test_library_bootstrap_refuses_to_overwrite_an_existing_incomplete_destination(tmp_path):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")
    library_root = host.parent / ".engineering-skills" / host.name
    library_root.mkdir(parents=True)
    sentinel = library_root / "KEEP.txt"
    sentinel.write_text("owned by host\n", encoding="utf-8")

    result = _run_isolated(
        router / "scripts" / "bootstrap_library.py",
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        cwd=host,
    )

    assert result.returncode == 2
    assert "existing library is incomplete" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "owned by host\n"


@pytest.mark.parametrize(
    "corruption",
    ["wrong-root", "schema", "duplicate", "missing-selected", "closure-mismatch"],
)
def test_installed_router_reports_invalid_capability_manifest(tmp_path, corruption):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")
    library_root = host.parent / ".engineering-skills" / host.name
    guide = library_root / ".claude" / "skills" / "diagnose" / "SKILL.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("# diagnose\n", encoding="utf-8")
    manifest = library_root / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
    manifest.parent.mkdir(parents=True)
    payload = json.loads(
        (REPO_ROOT / ".claude" / "tasks" / "multilanguage-skill-matrix.json").read_text(
            encoding="utf-8"
        )
    )
    diagnose = next(row for row in payload["skills"] if row["skill"] == "diagnose")
    if corruption == "wrong-root":
        payload = []
    elif corruption == "schema":
        payload["schema_version"] = 999
    elif corruption == "duplicate":
        payload["skills"].append(dict(diagnose))
    elif corruption == "missing-selected":
        payload["skills"] = [row for row in payload["skills"] if row["skill"] != "diagnose"]
    else:
        diagnose["on_demand_closure"]["closure_skills"] = [
            "diagnose",
            "find-duplication",
        ]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_isolated(
        router / "scripts" / "match.py",
        "diagnose failing export job regression with no reproduction yet",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )

    routed = _json_output(result)
    assert routed["recommendation"] == "diagnose"
    assert routed["handoff"]["capabilities"] == {
        "available": False,
        "manifest": str(manifest),
        "skills": [],
        "reason": "manifest_invalid_or_incomplete",
    }


@pytest.mark.parametrize(
    ("task", "expected_shape"),
    [
        ("fix one-line typo in the status label", "direct-change"),
        ("this inherited repo feels slow and chaotic", "project-intake"),
    ],
)
def test_installed_which_shape_runs_without_repository_runtime(
    tmp_path, task, expected_shape
):
    host = tmp_path / "host"
    router = _install_router(host, "which-shape")

    result = _run_isolated(
        router / "scripts" / "route.py",
        task,
        "--project-root",
        str(host),
        "--json",
        "--skip-log",
        cwd=host,
    )

    payload = _json_output(result)
    assert payload["recommendation"]["shape"] == expected_shape
    if expected_shape == "project-intake":
        assert payload["handoff"]["skills"] == ["adapt-project"]
        assert payload["optional_install"]["skill"] == "adapt-project"
        assert payload["optional_install"]["available"] is False
        assert payload["optional_install"]["reason"] == "manifest_missing"
        assert "command" not in payload["optional_install"]
    else:
        assert "handoff" not in payload
        assert "optional_install" not in payload


@pytest.mark.parametrize(
    ("task", "expected_skill"),
    [
        ("diagnose failing export job regression with no reproduction yet", "diagnose"),
        ("create a new skill for constructive UI forms", "plan-skill"),
    ],
)
def test_installed_which_skill_runs_with_bundled_catalog(
    tmp_path, task, expected_skill
):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        task,
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )

    payload = _json_output(result)
    assert payload["recommendation"] == expected_skill
    assert payload["task_packet"]["produces"]
    assert payload["handoff"]["skills"] == [expected_skill]
    assert payload["optional_install"]["available"] is False
    assert payload["optional_install"]["reason"] == "manifest_missing"
    assert "command" not in payload["optional_install"]


def test_installed_which_skill_routes_earned_typescript_state_skill(tmp_path):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        "find repeated bare status literals in src/job.ts",
        "--project-root",
        str(host),
        "--top",
        "10",
        "--json",
        cwd=host,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["routing_context"]["language_source"] == "task_marker"
    assert payload["recommendation"] == "find-implicit-state"
    assert payload["handoff"]["skills"] == ["find-implicit-state"]
    assert payload["handoff"]["capabilities"]["available"] is False
    assert payload["handoff"]["capabilities"]["reason"] == "manifest_missing"


def test_installed_which_skill_routes_typescript_explanation(tmp_path):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        "produce an annotated behavior doc for the direct public exports "
        "in this TypeScript module",
        "--project-root",
        str(host),
        "--top",
        "10",
        "--json",
        cwd=host,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "explain-code"
    assert payload["handoff"]["skills"] == ["explain-code"]


@pytest.mark.parametrize(
    ("task", "expected_skill"),
    [
        (
            "find an omnibus TypeScript module with too many unrelated "
            "responsibilities",
            "find-omnibus",
        ),
        (
            "audit TypeScript lexical clone clusters with reliable source "
            "spans and enclosing symbols",
            "find-duplication",
        ),
        (
            "audit syntactic branch complexity in TypeScript functions and methods",
            "find-complexity-hotspots",
        ),
        (
            "audit a TypeScript source root for a flat prefix filename cluster "
            "among direct siblings",
            "find-folder-topology-drift",
        ),
        (
            "onboard a TypeScript repository by discovering objective stack CI "
            "test and source-root facts",
            "adapt-project",
        ),
        (
            "check coverage gaps where a declared TypeScript standard requires "
            "direct JSON.parse calls to be enclosed by try",
            "find-standard-gaps",
        ),
        (
            "audit decision registry drift and TypeScript decision references",
            "audit-decisions",
        ),
        (
            "map a TypeScript subsystem exported surface and resolved imports",
            "map-subsystem",
        ),
        (
            "assess a TypeScript glossary concept rename lifecycle and completeness gate",
            "rename-concept",
        ),
        (
            "propose a TypeScript boundary from resolved symbol import and call evidence",
            "propose-boundary",
        ),
        (
            "propose reorganizing a TypeScript flat prefix folder cluster with resolved "
            "import impact",
            "propose-folder-reorganization",
        ),
        (
            "audit TypeScript private implementations for statically unreferenced "
            "dormant code",
            "find-dormant",
        ),
        (
            "audit TypeScript call sites for an incomplete option property sweep",
            "find-incomplete-sweep",
        ),
        (
            "audit TypeScript functions for semantic duplication with the same "
            "typed outcome and different code",
            "find-semantic-duplication",
        ),
        (
            "turn a confirmed TypeScript semantic finding into an implementation-ready "
            "proposal with caller impact and a stop condition",
            "unify-shadows",
        ),
    ],
)
def test_installed_which_skill_routes_typescript_analysis_skills(
    tmp_path, task, expected_skill
):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        task,
        "--project-root",
        str(host),
        "--top",
        "10",
        "--json",
        cwd=host,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == expected_skill
    assert payload["handoff"]["skills"][0] == expected_skill


def test_default_router_set_is_exactly_three():
    assert DEFAULT_ROUTERS == ("which-shape", "which-skill", "which-cleanup")


def test_installed_router_returns_code_health_family_from_on_demand_library(tmp_path):
    host = tmp_path / "host"
    installed = {name: _install_router(host, name) for name in DEFAULT_ROUTERS}
    (host / "src").mkdir(parents=True)
    (host / "ai-docs" / "decisions").mkdir(parents=True)
    standards = host / "standards.json"
    standards.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "checked-json-parse",
                        "contract": {
                            "detector": {
                                "kind": "ast",
                                "call_matches": "^JSON\\.parse$",
                                "enclosed_by": "try",
                                "paths": ["src/**/*"],
                            }
                        },
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "Run a broad read-only TypeScript code health audit across src",
        "--project-root",
        str(host),
        "--library-root",
        str(REPO_ROOT),
        "--standards",
        str(standards),
        "--json",
        cwd=host,
    )

    payload = _json_output(result)
    assert payload["recommendation"] == "find-complexity-hotspots"
    family = payload["coverage_family"]
    assert family["available"] is True
    assert family["runnable"] == family["coverage_set"]
    assert family["skips"] == []
    assert family["paths"]["root"] == str(
        REPO_ROOT / ".claude" / "skill-families" / "code-health-readonly"
    )
    assert all(
        member["on_demand_closure"]["capabilities"]["available"] is True
        for member in family["members"]
    )
    assert "optional_install" not in family
    assert {
        path.name
        for path in (host / ".agents" / "skills").iterdir()
        if path.is_dir()
    } == set(DEFAULT_ROUTERS)


@pytest.mark.parametrize(
    ("task", "excluded_skill"),
    [
        ("plan a TypeScript feature across one workflow", "plan-feature"),
        (
            "use impact-feature to map TypeScript touched subsystem blast radius",
            "impact-feature",
        ),
    ],
)
def test_installed_which_skill_excludes_stack_bound_planning_claims(
    tmp_path, task, excluded_skill
):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        task,
        "--project-root",
        str(host),
        "--top",
        "20",
        "--json",
        cwd=host,
    )

    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "native-alternative-required"
    assert payload["unavailable"]["name"] == excluded_skill
    excluded = {item["name"] for item in payload["excluded_ineligible"]}
    assert excluded_skill in excluded


@pytest.mark.parametrize("skill", STACK_BOUND_SKILLS)
def test_installed_which_skill_never_substitutes_for_named_stack_bound_skill(
    tmp_path, skill
):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        f"use {skill} on this TypeScript project",
        "--project-root",
        str(host),
        "--top",
        "20",
        "--json",
        cwd=host,
    )

    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recommendation"] == "native-alternative-required"
    assert payload["unavailable"]["name"] == skill


def test_installed_which_cleanup_routes_without_repository_runtime(tmp_path):
    host = tmp_path / "host"
    router = _install_router(host, "which-cleanup")

    result = _run_isolated(
        router / "scripts" / "route.py",
        "src/app.py",
        "tests/test_app.py",
        "--project-root",
        str(host),
        "--source",
        "/tmp/engineering-skills-source",
        "--json",
        cwd=host,
    )

    payload = _json_output(result)
    assert payload["scope_band"] == "small"
    recommendations = {item["skill"]: item for item in payload["recommendations"]}
    assert "find-test-obligation-drift" in recommendations
    handoff = recommendations["find-test-obligation-drift"]["handoff"]
    assert handoff["skills"] == ["find-test-obligation-drift"]
    assert handoff["capabilities"]["available"] is False
    assert handoff["capabilities"]["reason"] == "manifest_missing"
    optional_install = recommendations["find-test-obligation-drift"]["optional_install"]
    assert optional_install["source"] == "/tmp/engineering-skills-source"
    assert optional_install["available"] is False
    assert optional_install["reason"] == "manifest_missing"
    assert "command" not in optional_install
