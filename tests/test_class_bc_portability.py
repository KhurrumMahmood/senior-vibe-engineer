from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from _lib.host_profile import profile_host


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMON = REPO_ROOT / ".claude" / "skills" / "_common"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))

import product_health  # noqa: E402
import product_topology  # noqa: E402
import scope  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPONENTS = _load(
    "portable_component_inventory",
    REPO_ROOT
    / ".claude"
    / "skills"
    / "find-frontend-duplication"
    / "scripts"
    / "cotton_inventory.py",
)
FOLDER = _load(
    "portable_folder_detector",
    REPO_ROOT
    / ".claude"
    / "skills"
    / "find-folder-topology-drift"
    / "scripts"
    / "detect.py",
)
FRONTEND = _load(
    "portable_frontend_detector",
    REPO_ROOT
    / ".claude"
    / "skills"
    / "find-frontend-contract-drift"
    / "scripts"
    / "detect.py",
)
FRONTEND_REPORT = _load(
    "portable_frontend_report",
    REPO_ROOT
    / ".claude"
    / "skills"
    / "find-frontend-contract-drift"
    / "scripts"
    / "report.py",
)


def _write(root: Path, relative: str, text: str = "x\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_durable_profile(root: Path, manifest: dict) -> dict:
    manifest_path = root / ".engineering" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    profile = profile_host(root)
    profile_path = root / ".engineering" / "project" / "host-profile.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    manifest_path.unlink()
    return profile


def _scope_descriptor(root: Path, skill: str) -> None:
    _write(
        root,
        f".engineering/docs/{skill}-scope.md",
        "## Roots\n- `src/`\n\n## Ignore\n- `src/ignored/`\n",
    )


# spec:portable-host-profile-routing::IM-9
def test_component_inventory_comes_from_durable_profile_and_empty_is_default(tmp_path):
    _write(tmp_path, "package.json", '{"devDependencies":{"typescript":"5.9.3"}}')
    _write(tmp_path, "tsconfig.json", "{}\n")
    _write(tmp_path, "ui/components/Button.tsx", "export const Button = () => <button />;\n")
    _write(tmp_path, "src/App.tsx", "export const App = () => <Button />;\n")
    _write_durable_profile(
        tmp_path,
        {
            "component_profile": {
                "kind": "jsx",
                "definitions_root": "ui/components",
                "reference_pattern": "<{name}\\b",
                "extensions": [".tsx"],
            }
        },
    )

    inventory = COMPONENTS.build_inventory(tmp_path)

    assert inventory["component_system"] == "jsx"
    assert inventory["primitive_count"] == 1
    assert inventory["primitives"][0]["name"] == "Button"
    assert inventory["primitives"][0]["callsite_count"] == 1

    profile_path = tmp_path / ".engineering" / "project" / "host-profile.json"
    tampered = json.loads(profile_path.read_text(encoding="utf-8"))
    tampered["component_profile"]["kind"] = "cotton"
    profile_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert COMPONENTS.build_inventory(tmp_path)["component_system"] == "none"
    assert COMPONENTS.build_inventory(tmp_path / "undeclared") == {
        "generated_by": "scripts/cotton_inventory.py",
        "component_system": "none",
        "definitions_root": None,
        "primitive_count": 0,
        "primitives": [],
    }


def test_product_health_surfaces_are_profile_derived_and_neutral(tmp_path):
    _write(tmp_path, "package.json", '{"devDependencies":{"typescript":"5.9.3"}}')
    _write(tmp_path, "tsconfig.json", "{}\n")
    _write(tmp_path, "src/ui/App.tsx", "export const App = () => null;\n")
    _write_durable_profile(
        tmp_path,
        {
            "surface_labels": {
                "src/ui": "client_ui",
                "src/ui/admin/**": "admin_ui",
                "src/api/**": "service_api",
            }
        },
    )

    assert product_health.infer_surface("src/ui/App.tsx", tmp_path) == "client_ui"
    assert product_health.infer_surface("src/ui/admin/Panel.tsx", tmp_path) == "admin_ui"
    assert product_health.infer_surface("src/api/routes.ts", tmp_path) == "service_api"
    assert product_health.infer_surface("src/worker/job.ts", tmp_path) == "product_surface"
    record = product_health.finding(
        "probe",
        "src/ui/App.tsx",
        1,
        "summary",
        "recommendation",
        tmp_path,
    )
    assert record["surface"] == "client_ui"
    assert not any(str(value).startswith("sites_") for value in record.values())


def test_folder_detector_matches_route_exemplar_scope_and_marker_selection(tmp_path):
    for skill in ("find-folder-topology-drift", "find-route-sprawl"):
        _scope_descriptor(tmp_path, skill)
    for name in ("alpha_one.py", "alpha_two.py", "alpha_three.py"):
        _write(tmp_path, f"src/good/{name}")
    for name in ("beta_one.py", "beta_two.py", "beta_three.py", "urls.py"):
        _write(tmp_path, f"src/ignored/{name}")
    for name in ("gamma_one.py", "gamma_two.py", "gamma_three.py"):
        _write(tmp_path, f"outside/{name}")
    _write(tmp_path, "src/urls.py")

    route_universe = scope.scan(tmp_path, "find-route-sprawl", extensions=frozenset({".py"}))
    route_marker = product_topology.discover_root_urlconf(tmp_path, "find-route-sprawl")
    folder_scope = scope.load_scope(tmp_path, "find-folder-topology-drift")
    folder_universe = scope.iter_paths(tmp_path, folder_scope, extensions=frozenset({".py"}))
    findings = FOLDER.detect(
        project_root=tmp_path,
        scope=folder_scope,
        min_cluster_size=3,
    )

    assert route_universe == folder_universe
    assert route_marker == tmp_path / "src" / "urls.py"
    assert {path.relative_to(tmp_path).as_posix() for path in route_universe} == {
        "src/good/alpha_one.py",
        "src/good/alpha_two.py",
        "src/good/alpha_three.py",
        "src/urls.py",
    }
    clusters = [item for item in findings if item["pattern"] == "flat_prefix_cluster"]
    assert [(item["file"], "alpha_" in item["summary"]) for item in clusters] == [
        ("src/good", True)
    ]


def test_frontend_detector_matches_scope_and_uses_profile_surface_labels(tmp_path):
    for skill in ("find-frontend-contract-drift", "find-route-sprawl"):
        _scope_descriptor(tmp_path, skill)
    _write(tmp_path, "package.json", '{"devDependencies":{"typescript":"5.9.3"}}')
    _write(tmp_path, "tsconfig.json", "{}\n")
    _write(
        tmp_path,
        "src/ui/base.html",
        "{% load static %}<script>window.APP_BOOT = {};</script>"
        "<script src=\"{% static 'assets/app.js' %}\"></script>\n",
    )
    _write(
        tmp_path,
        "src/assets/app.js",
        "console.log(window.APP_BOOT, window.MISSING_CONFIG);\n",
    )
    _write(tmp_path, "src/ignored/base.html", "<script>window.IGNORED_CONFIG = {};</script>\n")
    _write(tmp_path, "src/ignored/bad.js", "console.log(window.OTHER_CONFIG);\n")
    _write(tmp_path, "outside/base.html", "<script>window.OUTSIDE_CONFIG = {};</script>\n")
    _write_durable_profile(
        tmp_path,
        {"surface_labels": {"src/assets": "client_assets", "src/ui": "client_templates"}},
    )

    route_scope = scope.load_scope(tmp_path, "find-route-sprawl")
    frontend_scope = scope.load_scope(tmp_path, "find-frontend-contract-drift")
    route_universe = scope.iter_paths(
        tmp_path,
        route_scope,
        extensions=frozenset({".html", ".js"}),
    )
    frontend_universe = scope.iter_paths(
        tmp_path,
        frontend_scope,
        extensions=frozenset({".html", ".js"}),
    )
    findings = FRONTEND.detect(
        project_root=tmp_path,
        scope=frontend_scope,
        boot_threshold=3,
    )

    assert route_universe == frontend_universe
    assert {path.relative_to(tmp_path).as_posix() for path in frontend_universe} == {
        "src/assets/app.js",
        "src/ui/base.html",
    }
    missing = [item for item in findings if item["pattern"] == "undeclared_window_read"]
    assert [item["global"] for item in missing] == ["MISSING_CONFIG"]
    assert missing[0]["workflow_scope"] == "client_assets"
    assert not [item for item in findings if item["pattern"] == "implicit_template_global"]
    assert FRONTEND_REPORT._target_scope("src/assets", tmp_path) == "client_assets"
    assert FRONTEND_REPORT._target_scope("all", tmp_path) is None


def test_migrated_executable_paths_contain_no_seed_host_identifiers():
    paths = [
        COMMON / "product_health.py",
        REPO_ROOT
        / ".claude"
        / "skills"
        / "find-frontend-contract-drift"
        / "scripts"
        / "detect.py",
        REPO_ROOT
        / ".claude"
        / "skills"
        / "find-frontend-contract-drift"
        / "scripts"
        / "report.py",
        REPO_ROOT
        / ".claude"
        / "skills"
        / "find-frontend-duplication"
        / "scripts"
        / "cotton_inventory.py",
        REPO_ROOT
        / ".claude"
        / "skills"
        / "find-folder-topology-drift"
        / "scripts"
        / "detect.py",
    ]
    forbidden = (
        "sites_",
        "SITES_CONFIG",
        "templates/core/site_config",
        "static/js/site-config",
        "app/pages/sites",
        "app/site_management",
        "app/services/sites",
    )

    hits = {
        str(path.relative_to(REPO_ROOT)): token
        for path in paths
        for token in forbidden
        if token in path.read_text(encoding="utf-8")
    }

    assert hits == {}
