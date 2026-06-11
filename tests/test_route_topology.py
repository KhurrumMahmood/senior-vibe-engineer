"""Tests for host-shaped route classification (.claude/skills/_common).

The product-topology route detectors used to hardcode host-a's `/sites|/api`
shape. Classification is now driven by a host-authored `## Routes` block in
`.engineering/docs/product-workflows.md` (page/api prefixes + the instance-scope
converter param). These tests pin: shape parsing, `classify_route`, the
`RouteRecord` family field + derived booleans, converter-generic
`normalized_path`, `extract_routes` discovery + classification, `extract_docs_routes`,
and `normalize_doc_site_route` — plus the empty-shape (no descriptor) fallback
where nothing classifies. Deterministic and disk-isolated against ``tmp_path``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# _common is not on the path conftest sets up (that's scripts/).
_COMMON = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

import product_topology as pt  # noqa: E402
import workflows  # noqa: E402

_ROUTES_BLOCK = (
    "## Routes\n"
    "- `page_prefix | sites`\n"
    "- `api_prefix | api`\n"
    "- `scoped_id_param | site_id`\n"
)

_URLS = (
    "from django.urls import path\n\n"
    "urlpatterns = [\n"
    '    path("sites/<int:site_id>/setup/", views.setup, name="site_setup"),\n'
    '    path("api/sites/<int:site_id>/status/", views.status, name="site_status"),\n'
    '    path("api/health/", views.health, name="health"),\n'
    '    path("sites/", views.site_list, name="site_list"),\n'
    "]\n"
)


def _write_descriptor(root: Path, body: str) -> None:
    p = root / ".engineering" / "docs" / "product-workflows.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _write_urls(root: Path, rel: str = "app/urls.py") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_URLS, encoding="utf-8")
    return p


# ---- shape parsing -------------------------------------------------------

def test_workflow_route_shape_parses_key_value_rows(tmp_path):
    _write_descriptor(tmp_path, _ROUTES_BLOCK)
    assert workflows.workflow_route_shape(tmp_path) == {
        "page_prefix": "sites",
        "api_prefix": "api",
        "scoped_id_param": "site_id",
    }


def test_workflow_route_shape_absent_is_empty(tmp_path):
    assert workflows.workflow_route_shape(tmp_path) == {}


def test_route_shape_for_builds_dataclass(tmp_path):
    _write_descriptor(tmp_path, _ROUTES_BLOCK)
    shape = pt.route_shape_for(tmp_path)
    assert (shape.page_prefix, shape.api_prefix, shape.scoped_id_param) == ("sites", "api", "site_id")
    assert not shape.is_empty


def test_route_shape_for_absent_is_empty(tmp_path):
    shape = pt.route_shape_for(tmp_path)
    assert shape.is_empty
    assert shape.page_prefix is None


# ---- classify_route ------------------------------------------------------

def test_classify_route_families():
    shape = pt.RouteShape(page_prefix="sites", api_prefix="api", scoped_id_param="site_id")
    assert pt.classify_route("sites/<int:site_id>/setup/", shape) == "site_page"
    assert pt.classify_route("api/sites/<int:site_id>/status/", shape) == "site_scoped_api"
    assert pt.classify_route("api/health/", shape) == "global_api"
    assert pt.classify_route("sites/", shape) == "other"
    assert pt.classify_route("about/", shape) == "other"


def test_classify_route_honours_alternate_converter_and_prefix():
    shape = pt.RouteShape(page_prefix="accounts", api_prefix="rest", scoped_id_param="pk")
    assert pt.classify_route("accounts/<slug:pk>/profile/", shape) == "site_page"
    assert pt.classify_route("accounts/<pk>/profile/", shape) == "site_page"  # bare converter
    assert pt.classify_route("rest/<int:pk>/detail/", shape) == "site_scoped_api"
    # host-a's literal shape must NOT classify another host's routes.
    assert pt.classify_route("sites/<int:site_id>/setup/", shape) == "other"


def test_classify_route_empty_shape_is_all_other():
    empty = pt.RouteShape()
    for route in ("sites/<int:site_id>/setup/", "api/health/", "anything/"):
        assert pt.classify_route(route, empty) == "other"


# ---- RouteRecord ---------------------------------------------------------

def test_route_record_booleans_derive_from_family():
    page = pt.RouteRecord(route="sites/<int:site_id>/x/", name="", view="", file="u.py", lineno=1, route_family="site_page")
    api = pt.RouteRecord(route="api/sites/<int:site_id>/x/", name="", view="", file="u.py", lineno=2, route_family="site_scoped_api")
    other = pt.RouteRecord(route="x/", name="", view="", file="u.py", lineno=3)  # default family "other"
    assert page.is_site_page and not page.is_site_scoped_api
    assert api.is_site_scoped_api and not api.is_site_page
    assert other.route_family == "other" and not other.is_site_page


def test_normalized_path_is_converter_generic():
    r = pt.RouteRecord(route="sites/<int:site_id>/export/data/", name="", view="", file="u.py", lineno=1)
    assert r.normalized_path == "/sites/{site_id}/export/data"
    r2 = pt.RouteRecord(route="api/<slug:pk>/detail/", name="", view="", file="u.py", lineno=1)
    assert r2.normalized_path == "/api/{pk}/detail"


# ---- extract_routes ------------------------------------------------------

def test_extract_routes_classifies_with_descriptor(tmp_path):
    _write_descriptor(tmp_path, _ROUTES_BLOCK)
    urls = _write_urls(tmp_path)
    by_name = {r.name: r for r in pt.extract_routes(tmp_path, [urls])}
    assert by_name["site_setup"].route_family == "site_page"
    assert by_name["site_status"].route_family == "site_scoped_api"
    assert by_name["health"].route_family == "global_api"
    assert by_name["site_list"].route_family == "other"


def test_extract_routes_discovers_urls_without_source_root(tmp_path):
    # No url_paths arg -> ignore-first discovery must find app/urls.py (no core/ assumption).
    _write_descriptor(tmp_path, _ROUTES_BLOCK)
    _write_urls(tmp_path, "app/urls.py")
    names = {r.name for r in pt.extract_routes(tmp_path)}
    assert {"site_setup", "site_status", "health"} <= names


def test_extract_routes_empty_shape_classifies_nothing(tmp_path):
    urls = _write_urls(tmp_path)  # no descriptor
    families = {r.route_family for r in pt.extract_routes(tmp_path, [urls])}
    assert families == {"other"}


# ---- extract_docs_routes -------------------------------------------------

def test_extract_docs_routes_uses_shape(tmp_path):
    _write_descriptor(tmp_path, _ROUTES_BLOCK)
    doc = tmp_path / "docs" / "routes.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "See `/sites/{id}/setup/` and `/sites/<id>/export/`.\n"
        "`/sites/{id}/old/` redirects to `/sites/{site_id}/new/`.\n",
        encoding="utf-8",
    )
    mentions, claims = pt.extract_docs_routes(tmp_path, [doc])
    # The redirect-claim source `/sites/{id}/old/` is itself a route mention.
    assert sorted(m.route for m in mentions) == [
        "/sites/<id>/export/",
        "/sites/{id}/old/",
        "/sites/{id}/setup/",
    ]
    assert len(claims) == 1 and claims[0].target == "/sites/{site_id}/new/"


def test_extract_docs_routes_empty_shape_finds_nothing(tmp_path):
    doc = tmp_path / "docs" / "routes.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("See `/sites/{id}/setup/`.\n", encoding="utf-8")
    mentions, claims = pt.extract_docs_routes(tmp_path, [doc])  # no descriptor
    assert mentions == [] and claims == []


# ---- normalize_doc_site_route -------------------------------------------

def test_normalize_doc_site_route_host_defaults():
    assert pt.normalize_doc_site_route("/sites/{id}/setup/") == "/sites/{site_id}/setup/"
    assert pt.normalize_doc_site_route("/sites/<id>/setup/") == "/sites/{site_id}/setup/"


def test_normalize_doc_site_route_custom_shape():
    assert (
        pt.normalize_doc_site_route("/accounts/{id}/profile/", "accounts", "pk")
        == "/accounts/{pk}/profile/"
    )
    # Falsy prefix -> route unchanged (an api-only host has no page prefix).
    assert pt.normalize_doc_site_route("/api/{id}/x/", "") == "/api/{id}/x/"
