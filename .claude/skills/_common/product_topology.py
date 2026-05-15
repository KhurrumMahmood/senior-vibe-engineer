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
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SITE_WORKFLOW_STEPS: tuple[dict[str, str], ...] = (
    {"id": "setup", "label": "Setup", "route_name": "site_setup", "path": "/sites/{site_id}/setup/"},
    {
        "id": "extraction",
        "label": "Extraction",
        "route_name": "site_extraction_fields",
        "path": "/sites/{site_id}/extraction/fields/",
    },
    {"id": "pages", "label": "Pages", "route_name": "site_pages", "path": "/sites/{site_id}/pages/"},
    {"id": "images", "label": "Images", "route_name": "site_images", "path": "/sites/{site_id}/images/"},
    {
        "id": "external",
        "label": "External",
        "route_name": "site_external",
        "path": "/sites/{site_id}/external/",
    },
    {"id": "tagging", "label": "Tagging", "route_name": "site_tagging", "path": "/sites/{site_id}/tagging/"},
    {
        "id": "export",
        "label": "Export",
        "route_name": "site_export_data",
        "path": "/sites/{site_id}/export/data/",
    },
)

WORKFLOW_LABELS = tuple(step["label"] for step in SITE_WORKFLOW_STEPS) + (
    "Downloads",
    "Brands",
    "Training",
)
WORKFLOW_TAB_IDS = tuple(step["id"] for step in SITE_WORKFLOW_STEPS) + (
    "extraction_urls",
    "extraction_fields",
    "export_data",
    "export_images",
    "downloads",
    "brands",
    "training",
)

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "staticfiles",
    "migrations",
}

ROUTE_LITERAL_RE = re.compile(r"/(?:sites|api)/[^`'\"<),]+")
DOC_ROUTE_RE = re.compile(r"/(?:sites|api)/\{id\}/[^`'\"\s)<,]+|/(?:sites|api)/<id>/[^`'\"\s)<,]+")
REDIRECT_CLAIM_RE = re.compile(
    r"`?(?P<src>/sites/(?:\{id\}|<id>)/[^`'\"\s)<,]+)`?.*?"
    r"redirects?\s+to\s+`?(?P<target>/[^`'\"\s)<,]+)`?",
    re.IGNORECASE,
)
WINDOW_ACCESS_RE = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*)\b")
WINDOW_ASSIGN_RE = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*)\s*=")


@dataclass(frozen=True)
class RouteRecord:
    route: str
    name: str
    view: str
    file: str
    lineno: int
    is_include: bool = False

    @property
    def normalized_path(self) -> str:
        return "/" + self.route.replace("<int:site_id>", "{site_id}").strip("/")

    @property
    def is_site_page(self) -> bool:
        return self.route.startswith("sites/<int:site_id>/")

    @property
    def is_site_scoped_api(self) -> bool:
        return self.route.startswith("api/") and "<int:site_id>" in self.route

    @property
    def route_family(self) -> str:
        if self.is_site_page:
            return "site_page"
        if self.is_site_scoped_api:
            return "site_scoped_api"
        if self.route.startswith("api/"):
            return "global_api"
        return "other"


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


def _route_name_from_registry_call(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func_name = expr_to_string(node.func)
    if not func_name.endswith("SiteWorkflowRegistry.canonical_route_name"):
        return None
    step_key = _constant_string(node.args[0]) if node.args else None
    if not step_key:
        return None
    for step in SITE_WORKFLOW_STEPS:
        if step["id"] == step_key:
            return step["route_name"]
    return None


def _route_name_from_redirect_arg(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    direct = _constant_string(node)
    if direct:
        return direct.split(":")[-1]
    return _route_name_from_registry_call(node)


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


def extract_routes(project_root: Path, url_paths: list[Path] | None = None) -> list[RouteRecord]:
    if url_paths is None:
        url_paths = [project_root / "core" / "urls.py"]
        for route_root in (project_root / "core", project_root / "app"):
            url_paths.extend(
                path
                for path in iter_files(route_root, (".py",))
                if path.name == "urls.py" or path.name.endswith("_urls.py")
            )

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
            routes.append(
                RouteRecord(
                    route=_join_routes(prefix, route),
                    name=name,
                    view=view,
                    file=relpath(path, project_root),
                    lineno=getattr(node, "lineno", 0),
                    is_include=include_file is not None or "include" in view,
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
        first_arg = _route_name_from_redirect_arg(node.args[0]) if node.args else None
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
        paths = iter_files(project_root / "core" / "views", (".py",))
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


def extract_docs_routes(project_root: Path, paths: list[Path] | None = None) -> tuple[list[DocsRouteMention], list[RedirectClaim]]:
    if paths is None:
        paths = iter_files(project_root / "docs", (".md",)) + iter_files(
            project_root / ".claude" / "docs", (".md",)
        )
    mentions: list[DocsRouteMention] = []
    claims: list[RedirectClaim] = []
    for path in paths:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for match in DOC_ROUTE_RE.finditer(line):
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
            claim_match = REDIRECT_CLAIM_RE.search(line)
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


def normalize_doc_site_route(route: str) -> str:
    return route.replace("/sites/{id}/", "/sites/{site_id}/").replace(
        "/sites/<id>/", "/sites/{site_id}/"
    )


def normalize_route_literal(route: str) -> str:
    normalized = re.sub(r"\{\{\s*[^}]+\s*\}\}", "{site_id}", route)
    normalized = re.sub(r"\$\{[^}]+\}", "{site_id}", normalized)
    normalized = re.sub(r"\{[^}/]+\}", "{site_id}", normalized)
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


def status_provider_names(project_root: Path) -> list[dict[str, Any]]:
    paths = iter_files(project_root / "core" / "views", (".py",)) + iter_files(
        project_root / "core" / "services", (".py",)
    )
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
    candidates: list[Path] = []
    candidates.extend(iter_files(project_root / "core", (".py",)))
    candidates.extend(iter_files(project_root / "templates", (".html",)))
    candidates.extend(iter_files(project_root / "static" / "js", (".js",)))
    candidates.extend(iter_files(project_root / "docs", (".md",)))
    candidates.extend(iter_files(project_root / ".claude" / "docs", (".md",)))
    return candidates


def sites_workflow_text_files(project_root: Path) -> list[Path]:
    """Return files likely to carry `/sites` workflow topology.

    This intentionally avoids scanning every model/test/service file for
    common words like "Setup" or "Export"; product-topology duplication is
    about workflow ownership surfaces, not incidental domain vocabulary.
    """
    candidates: list[Path] = []
    explicit = [
        project_root / "core" / "urls.py",
        project_root / "core" / "views" / "site_config.py",
        project_root / "core" / "views" / "sitemaps.py",
        project_root / "core" / "views" / "field_config.py",
        project_root / "core" / "views" / "external.py",
        project_root / "core" / "views" / "tagging.py",
        project_root / "core" / "views" / "agent.py",
    ]
    candidates.extend(path for path in explicit if path.exists())
    candidates.extend(iter_files(project_root / "core" / "views" / "brand_downloads", (".py",)))
    candidates.extend(sorted((project_root / "templates" / "core").glob("site_config*.html")))
    candidates.extend(sorted((project_root / "templates" / "core" / "includes").glob("*sub_tabs.html")))
    candidates.extend(sorted((project_root / "static" / "js").glob("site-config*.js")))
    candidates.extend(sorted((project_root / "static" / "js").glob("export-*.js")))
    candidates.extend(sorted((project_root / "static" / "js").glob("download-*.js")))
    for path in iter_files(project_root / ".claude" / "docs", (".md",)) + iter_files(
        project_root / "docs", (".md",)
    ):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "/sites/" in text or "site_config" in text:
            candidates.append(path)
    return sorted(dict.fromkeys(candidates))


def label_hits(project_root: Path, paths: list[Path] | None = None) -> list[dict[str, Any]]:
    paths = paths or workflow_text_files(project_root)
    hits: list[dict[str, Any]] = []
    label_pattern = re.compile(r"\b(" + "|".join(re.escape(label) for label in WORKFLOW_LABELS) + r")\b")
    tab_pattern = re.compile(r"['\"](" + "|".join(re.escape(tab) for tab in WORKFLOW_TAB_IDS) + r")['\"]")
    for path in paths:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for match in label_pattern.finditer(line):
                hits.append(
                    {
                        "kind": "label",
                        "value": match.group(1),
                        "file": relpath(path, project_root),
                        "lineno": lineno,
                        "evidence": line.strip()[:200],
                    }
                )
            for match in tab_pattern.finditer(line):
                hits.append(
                    {
                        "kind": "tab_id",
                        "value": match.group(1),
                        "file": relpath(path, project_root),
                        "lineno": lineno,
                        "evidence": line.strip()[:200],
                    }
                )
            for match in ROUTE_LITERAL_RE.finditer(line):
                hits.append(
                    {
                        "kind": "route_literal",
                        "value": normalize_route_literal(match.group(0)),
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
