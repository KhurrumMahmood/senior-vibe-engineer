#!/usr/bin/env python3
"""Shared scanners for product-topology skills.

The product-topology skills look above individual files: routes,
templates, JavaScript boot contracts, docs, and product workflow labels.
This module stays stdlib-only so every skill can reuse the same parser in
read-only scans and guard proposals.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# The product workflow (steps, labels, tab ids, scan globs) is host-authored
# data, not baked-in code — read it from `.engineering/docs/product-workflows.md`
# via this sibling loader. A repo with no descriptor yields empty workflow data,
# so the toolkit ships with zero assumptions about any one host's product flow.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope as _scope  # noqa: E402
import workflows  # noqa: E402

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "staticfiles",
    "migrations",
}

WINDOW_ACCESS_RE = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*)\b")
WINDOW_ASSIGN_RE = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*)\s*=")

# How a host shapes product routes is host-authored data (`## Routes` in
# `.engineering/docs/product-workflows.md`), not a baked-in `/sites|/api`
# assumption. The route detectors load a RouteShape and classify against it; an
# empty shape (no descriptor) classifies nothing — the ignore-first contract.


@dataclass(frozen=True)
class RouteShape:
    """Host route conventions: page/api URL prefixes + the instance-scope param."""
    page_prefix: str | None = None
    api_prefix: str | None = None
    scoped_id_param: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.page_prefix or self.api_prefix or self.scoped_id_param)


def route_shape_for(project_root: Path) -> RouteShape:
    """Load the host's RouteShape from the workflow descriptor (empty if absent)."""
    raw = workflows.workflow_route_shape(project_root)
    return RouteShape(
        page_prefix=raw.get("page_prefix") or None,
        api_prefix=raw.get("api_prefix") or None,
        scoped_id_param=raw.get("scoped_id_param") or None,
    )


def _scoped_id_re(scoped_id_param: str) -> str:
    # `<int:site_id>`, `<slug:site_id>`, or bare `<site_id>` — any converter.
    return r"<(?:\w+:)?" + re.escape(scoped_id_param) + r">"


def _has_scoped_id(route: str, scoped_id_param: str | None) -> bool:
    if not scoped_id_param:
        return False
    return re.search(_scoped_id_re(scoped_id_param), route) is not None


def classify_route(route: str, shape: RouteShape) -> str:
    """Family of a urlconf route under the host's shape.

    ``site_page`` (page prefix + instance-scope param) > ``site_scoped_api``
    (api prefix + instance-scope param) > ``global_api`` (api prefix) >
    ``other``. An empty shape yields ``other`` for everything.
    """
    page, api = shape.page_prefix, shape.api_prefix
    if page and route.startswith(page + "/") and _has_scoped_id(route, shape.scoped_id_param):
        return "site_page"
    if api and route.startswith(api + "/"):
        if _has_scoped_id(route, shape.scoped_id_param):
            return "site_scoped_api"
        return "global_api"
    return "other"


def _route_literal_re(shape: RouteShape) -> re.Pattern[str] | None:
    """Match `/<prefix>/...` route literals in text; ``None`` when no prefixes."""
    prefixes = [p for p in (shape.page_prefix, shape.api_prefix) if p]
    if not prefixes:
        return None
    alt = "|".join(re.escape(p) for p in prefixes)
    return re.compile(r"/(?:" + alt + r")/[^`'\"<),]+")


def _doc_route_re(shape: RouteShape) -> re.Pattern[str] | None:
    """Match doc-form `/<prefix>/{id}/...` or `/<prefix>/<id>/...`; ``None`` when no prefixes."""
    prefixes = [p for p in (shape.page_prefix, shape.api_prefix) if p]
    if not prefixes:
        return None
    alt = "|".join(re.escape(p) for p in prefixes)
    return re.compile(
        r"/(?:" + alt + r")/\{id\}/[^`'\"\s)<,]+"
        r"|/(?:" + alt + r")/<id>/[^`'\"\s)<,]+"
    )


def _redirect_claim_re(shape: RouteShape) -> re.Pattern[str] | None:
    """Match a doc "`/<page>/{id}/..` redirects to `..`" claim; ``None`` without a page prefix."""
    page = shape.page_prefix
    if not page:
        return None
    p = re.escape(page)
    return re.compile(
        r"`?(?P<src>/" + p + r"/(?:\{id\}|<id>)/[^`'\"\s)<,]+)`?.*?"
        r"redirects?\s+to\s+`?(?P<target>/[^`'\"\s)<,]+)`?",
        re.IGNORECASE,
    )


@dataclass(frozen=True)
class RouteRecord:
    route: str
    name: str
    view: str
    file: str
    lineno: int
    is_include: bool = False
    # Classified at construction against the host RouteShape (``classify_route``).
    # Defaults to "other" so a record built without a shape stays unclassified.
    route_family: str = "other"

    @property
    def normalized_path(self) -> str:
        # Canonicalise any Django converter (`<int:site_id>` -> `{site_id}`,
        # `<slug:pk>` -> `{pk}`) — shape-independent, so docs and code routes
        # compare in one brace syntax.
        return "/" + re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", self.route).strip("/")

    @property
    def is_site_page(self) -> bool:
        return self.route_family == "site_page"

    @property
    def is_site_scoped_api(self) -> bool:
        return self.route_family == "site_scoped_api"


@dataclass(frozen=True)
class RedirectRecord:
    symbol: str
    target_name: str
    file: str
    lineno: int
    evidence: str


@dataclass(frozen=True)
class TemplateRender:
    symbol: str
    template: str
    file: str
    lineno: int


@dataclass(frozen=True)
class WindowAccess:
    name: str
    file: str
    lineno: int
    kind: str
    evidence: str


@dataclass(frozen=True)
class DocsRouteMention:
    route: str
    file: str
    lineno: int
    line: str


@dataclass(frozen=True)
class RedirectClaim:
    source: str
    target: str
    file: str
    lineno: int
    line: str


def utc_scan_id(prefix: str = "scan") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not root.exists():
        return []
    paths: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in suffixes:
            paths.append(path)
    return sorted(paths)


def relpath(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def expr_to_string(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{expr_to_string(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return f"{expr_to_string(node.func)}()"
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return type(node).__name__


def _constant_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _route_name_from_registry_call(node: ast.AST, steps: list[dict[str, str]]) -> str | None:
    # Resolves `…SiteWorkflowRegistry.canonical_route_name("setup")` to its route
    # name via the host's declared steps. Fully dormant unless a host both ships a
    # workflow descriptor *and* calls that exact registry API.
    if not isinstance(node, ast.Call):
        return None
    func_name = expr_to_string(node.func)
    if not func_name.endswith("SiteWorkflowRegistry.canonical_route_name"):
        return None
    step_key = _constant_string(node.args[0]) if node.args else None
    if not step_key:
        return None
    for step in steps:
        if step["id"] == step_key:
            return step["route_name"]
    return None


def _route_name_from_redirect_arg(node: ast.AST | None, steps: list[dict[str, str]]) -> str | None:
    if node is None:
        return None
    direct = _constant_string(node)
    if direct:
        return direct.split(":")[-1]
    return _route_name_from_registry_call(node, steps)


def _module_file(project_root: Path, module: str) -> Path:
    return project_root.joinpath(*module.split(".")).with_suffix(".py")


def _urlpatterns_imports(tree: ast.AST, project_root: Path) -> dict[str, Path]:
    imports: dict[str, Path] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for alias in node.names:
            if alias.name != "urlpatterns":
                continue
            imports[alias.asname or alias.name] = _module_file(project_root, node.module)
    return imports


def _include_target_file(
    node: ast.AST | None,
    urlpatterns_imports: dict[str, Path],
    project_root: Path,
) -> Path | None:
    if not isinstance(node, ast.Call) or not expr_to_string(node.func).endswith("include"):
        return None
    include_arg = node.args[0] if node.args else None
    module = _constant_string(include_arg)
    if module:
        return _module_file(project_root, module)
    if isinstance(include_arg, ast.Name):
        return urlpatterns_imports.get(include_arg.id)
    return None


def _join_routes(prefix: str, route: str) -> str:
    if not prefix:
        return route
    if not route:
        return prefix
    return f"{prefix.rstrip('/')}/{route.lstrip('/')}"


def discover_url_modules(project_root: Path) -> list[Path]:
    """All `urls.py` / `*_urls.py` in the repo, ignore-first (no source-root assumption).

    Walks the scope universe (whole repo minus builtin skips) rather than a baked
    `core/`+`app/` pair, so any host layout's urlconfs are found.
    """
    return [
        path
        for path in _scope.iter_paths(project_root, _scope.Scope(), extensions=frozenset({".py"}))
        if path.name == "urls.py" or path.name.endswith("_urls.py")
    ]


def extract_routes(
    project_root: Path,
    url_paths: list[Path] | None = None,
    shape: RouteShape | None = None,
) -> list[RouteRecord]:
    if url_paths is None:
        url_paths = discover_url_modules(project_root)
    if shape is None:
        shape = route_shape_for(project_root)

    routes: list[RouteRecord] = []
    scanned: set[tuple[Path, str]] = set()

    def scan(path: Path, prefix: str = "") -> None:
        key = (path.resolve(), prefix)
        if key in scanned:
            return
        scanned.add(key)
        if not path.exists():
            return
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            return
        imports = _urlpatterns_imports(tree, project_root)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = expr_to_string(node.func)
            if func_name not in {"path", "re_path", "django.urls.path", "django.urls.re_path"}:
                continue
            route = _constant_string(node.args[0]) if node.args else None
            if route is None:
                continue
            view_node = node.args[1] if len(node.args) > 1 else None
            view = expr_to_string(view_node) if view_node is not None else ""
            name = ""
            for kw in node.keywords:
                if kw.arg == "name":
                    name = _constant_string(kw.value) or ""
            include_file = _include_target_file(view_node, imports, project_root)
            full_route = _join_routes(prefix, route)
            routes.append(
                RouteRecord(
                    route=full_route,
                    name=name,
                    view=view,
                    file=relpath(path, project_root),
                    lineno=getattr(node, "lineno", 0),
                    is_include=include_file is not None or "include" in view,
                    route_family=classify_route(full_route, shape),
                )
            )
            if include_file is not None:
                scan(include_file, _join_routes(prefix, route))

    for path in dict.fromkeys(url_paths):
        scan(path)

    unique = {
        (route.file, route.lineno, route.route, route.name, route.view): route
        for route in routes
    }
    return sorted(unique.values(), key=lambda r: (r.file, r.lineno, r.route))


class _PythonSurfaceVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, project_root: Path, source_lines: list[str]) -> None:
        self.path = path
        self.project_root = project_root
        self.source_lines = source_lines
        self.stack: list[str] = []
        self.redirects: list[RedirectRecord] = []
        self.templates: list[TemplateRender] = []
        self.workflow_steps = workflows.workflow_steps(project_root)

    def _symbol(self) -> str:
        return ".".join(self.stack) if self.stack else "<module>"

    def _line(self, node: ast.AST) -> str:
        lineno = getattr(node, "lineno", 0)
        if lineno < 1 or lineno > len(self.source_lines):
            return ""
        return self.source_lines[lineno - 1].strip()

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> Any:
        func_name = expr_to_string(node.func)
        first_arg = _route_name_from_redirect_arg(node.args[0], self.workflow_steps) if node.args else None
        if func_name.endswith("redirect") and first_arg:
            self.redirects.append(
                RedirectRecord(
                    symbol=self._symbol(),
                    target_name=first_arg,
                    file=relpath(self.path, self.project_root),
                    lineno=getattr(node, "lineno", 0),
                    evidence=self._line(node),
                )
            )
        if func_name.endswith("reverse") and first_arg:
            self.redirects.append(
                RedirectRecord(
                    symbol=self._symbol(),
                    target_name=first_arg.split(":")[-1],
                    file=relpath(self.path, self.project_root),
                    lineno=getattr(node, "lineno", 0),
                    evidence=self._line(node),
                )
            )
        if func_name.endswith("render") and len(node.args) >= 2:
            template = _constant_string(node.args[1])
            if template:
                self.templates.append(
                    TemplateRender(
                        symbol=self._symbol(),
                        template=template,
                        file=relpath(self.path, self.project_root),
                        lineno=getattr(node, "lineno", 0),
                    )
                )
        self.generic_visit(node)


def extract_python_surface(project_root: Path, paths: list[Path] | None = None) -> tuple[list[RedirectRecord], list[TemplateRender]]:
    if paths is None:
        paths = _scope.iter_paths(project_root, _scope.Scope(), extensions=frozenset({".py"}))
    redirects: list[RedirectRecord] = []
    templates: list[TemplateRender] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError):
            continue
        visitor = _PythonSurfaceVisitor(path, project_root, source.splitlines())
        visitor.visit(tree)
        redirects.extend(visitor.redirects)
        templates.extend(visitor.templates)
    return redirects, templates


def extract_window_accesses(project_root: Path, paths: list[Path]) -> list[WindowAccess]:
    accesses: list[WindowAccess] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            assigned = {match.group(1) for match in WINDOW_ASSIGN_RE.finditer(line)}
            for match in WINDOW_ACCESS_RE.finditer(line):
                name = match.group(1)
                kind = "assignment" if name in assigned else "read"
                accesses.append(
                    WindowAccess(
                        name=name,
                        file=relpath(path, project_root),
                        lineno=lineno,
                        kind=kind,
                        evidence=line.strip()[:240],
                    )
                )
    return accesses


def extract_docs_routes(
    project_root: Path,
    paths: list[Path] | None = None,
    shape: RouteShape | None = None,
) -> tuple[list[DocsRouteMention], list[RedirectClaim]]:
    if paths is None:
        paths = iter_files(project_root / "docs", (".md",)) + iter_files(
            project_root / ".claude" / "docs", (".md",)
        )
    if shape is None:
        shape = route_shape_for(project_root)
    doc_route_re = _doc_route_re(shape)
    redirect_claim_re = _redirect_claim_re(shape)
    mentions: list[DocsRouteMention] = []
    claims: list[RedirectClaim] = []
    # No host route prefixes -> nothing to recognise in docs (ignore-first).
    if doc_route_re is None and redirect_claim_re is None:
        return mentions, claims
    for path in paths:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for match in (doc_route_re.finditer(line) if doc_route_re else ()):
                if "..." in match.group(0):
                    continue
                mentions.append(
                    DocsRouteMention(
                        route=match.group(0),
                        file=relpath(path, project_root),
                        lineno=lineno,
                        line=line.strip()[:240],
                    )
                )
            claim_match = redirect_claim_re.search(line) if redirect_claim_re else None
            if claim_match:
                claims.append(
                    RedirectClaim(
                        source=claim_match.group("src"),
                        target=claim_match.group("target"),
                        file=relpath(path, project_root),
                        lineno=lineno,
                        line=line.strip()[:240],
                    )
                )
    return mentions, claims


def normalize_doc_site_route(
    route: str, page_prefix: str = "sites", scoped_id_param: str = "site_id"
) -> str:
    """Canonicalise a documented `/ptr/{id}/` or `/ptr/<id>/` to `/ptr/{scoped_id}/`.

    Defaults reproduce the pnci ``sites``/``site_id`` behaviour; callers pass the
    host's RouteShape values. ``page_prefix`` falsy -> route returned unchanged.
    """
    if not page_prefix:
        return route
    prefix = "/" + page_prefix + "/"
    canonical = prefix + "{" + scoped_id_param + "}/"
    return route.replace(prefix + "{id}/", canonical).replace(prefix + "<id>/", canonical)


def normalize_route_literal(route: str, placeholder: str = "site_id") -> str:
    """Collapse `{{x}}`/`${x}`/`{x}` interpolations to one `{placeholder}` sentinel.

    The sentinel only needs to be consistent within a scan (it groups route
    literals that differ solely in their id slot); defaults to ``site_id`` to
    match ``RouteRecord.normalized_path``'s converter canonicalisation.
    """
    token = "{" + placeholder + "}"
    normalized = re.sub(r"\{\{\s*[^}]+\s*\}\}", token, route)
    normalized = re.sub(r"\$\{[^}]+\}", token, normalized)
    normalized = re.sub(r"\{[^}/]+\}", token, normalized)
    return normalized.strip()


def route_by_name(routes: list[RouteRecord]) -> dict[str, RouteRecord]:
    return {route.name: route for route in routes if route.name}


def route_by_view_class(routes: list[RouteRecord]) -> dict[str, RouteRecord]:
    by_view: dict[str, RouteRecord] = {}
    for route in routes:
        view = route.view
        if ".as_view" in view:
            parts = view.split(".")
            if len(parts) >= 2:
                by_view[parts[-3] if parts[-2] == "as_view" else parts[-2]] = route
        if "views." in view:
            name = view.split("views.", 1)[1].split(".", 1)[0]
            by_view[name] = route
    return by_view


def status_provider_names(project_root: Path, paths: list[Path] | None = None) -> list[dict[str, Any]]:
    if paths is None:
        paths = _scope.iter_paths(project_root, _scope.Scope(), extensions=frozenset({".py"}))
    providers: list[dict[str, Any]] = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name.lower()
                if "status" in name and ("site" in name or "sidebar" in name or "discovery" in name):
                    providers.append(
                        {
                            "name": node.name,
                            "file": relpath(path, project_root),
                            "lineno": getattr(node, "lineno", 0),
                        }
                    )
    return sorted(providers, key=lambda item: (item["file"], item["lineno"]))


def workflow_text_files(project_root: Path) -> list[Path]:
    """Files scanned for duplicated workflow knowledge.

    Driven by the host's ``## Text-file globs`` (see ``workflows.py``); empty
    when no descriptor exists — the toolkit assumes no product flow until a host
    declares one. Globs are evaluated relative to ``project_root`` (e.g.
    ``app/urls.py``, ``templates/sites/*.html``, ``docs/**/*.md``) and only
    file matches outside builtin skip dirs are kept. This intentionally scans a
    curated, host-declared set rather than every model/test/service file, so
    incidental domain vocabulary doesn't masquerade as workflow-label drift.
    """
    found: list[Path] = []
    for pattern in workflows.workflow_text_globs(project_root):
        for path in project_root.glob(pattern):
            if path.is_file() and not any(part in SKIP_DIRS for part in path.parts):
                found.append(path)
    return sorted(dict.fromkeys(found))


def label_hits(project_root: Path, paths: list[Path] | None = None) -> list[dict[str, Any]]:
    paths = paths or workflow_text_files(project_root)
    labels = workflows.workflow_labels(project_root)
    tab_ids = workflows.workflow_tab_ids(project_root)
    shape = route_shape_for(project_root)
    route_pattern = _route_literal_re(shape)
    placeholder = shape.scoped_id_param or "site_id"
    # Empty alternation `(...)` would compile to a pattern matching the empty
    # string at every position — skip the label/tab/route scan entirely when the
    # host declares no workflow or no route prefixes (ignore-first).
    label_pattern = (
        re.compile(r"\b(" + "|".join(re.escape(label) for label in labels) + r")\b") if labels else None
    )
    tab_pattern = (
        re.compile(r"['\"](" + "|".join(re.escape(tab) for tab in tab_ids) + r")['\"]") if tab_ids else None
    )
    hits: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for match in label_pattern.finditer(line) if label_pattern else ():
                hits.append(
                    {
                        "kind": "label",
                        "value": match.group(1),
                        "file": relpath(path, project_root),
                        "lineno": lineno,
                        "evidence": line.strip()[:200],
                    }
                )
            for match in tab_pattern.finditer(line) if tab_pattern else ():
                hits.append(
                    {
                        "kind": "tab_id",
                        "value": match.group(1),
                        "file": relpath(path, project_root),
                        "lineno": lineno,
                        "evidence": line.strip()[:200],
                    }
                )
            for match in (route_pattern.finditer(line) if route_pattern else ()):
                hits.append(
                    {
                        "kind": "route_literal",
                        "value": normalize_route_literal(match.group(0), placeholder),
                        "file": relpath(path, project_root),
                        "lineno": lineno,
                        "evidence": line.strip()[:200],
                    }
                )
    return hits


def dataclass_dicts(records: Iterable[Any]) -> list[dict[str, Any]]:
    return [asdict(record) for record in records]


def render_simple_report(title: str, records: list[dict[str, Any]], target: str) -> tuple[str, dict[str, Any]]:
    buckets: dict[str, int] = {}
    for record in records:
        key = str(record.get("pattern") or record.get("bucket") or "finding")
        buckets[key] = buckets.get(key, 0) + 1

    lines = [f"# {title}", "", f"**Target:** `{target}`", f"**Findings:** {len(records)}", ""]
    if buckets:
        lines.extend(["## Buckets", "", "| Bucket | Count |", "|---|---|"])
        for bucket, count in sorted(buckets.items()):
            lines.append(f"| `{bucket}` | {count} |")
        lines.append("")
    if records:
        lines.extend(["## Findings", ""])
        for idx, record in enumerate(records, start=1):
            file = record.get("file", "?")
            line = record.get("lineno", "?")
            pattern = record.get("pattern", record.get("bucket", "finding"))
            summary = record.get("summary") or record.get("message") or record.get("evidence") or ""
            lines.append(f"### {idx}. `{pattern}`")
            lines.append("")
            lines.append(f"- **Location:** `{file}:{line}`")
            if summary:
                lines.append(f"- **Evidence:** {summary}")
            recommendation = record.get("recommendation")
            if recommendation:
                lines.append(f"- **Recommendation:** {recommendation}")
            lines.append("")

    findings = {
        "summary": {"findings_total": len(records), "buckets": buckets},
        "findings": records,
    }
    return "\n".join(lines), findings
