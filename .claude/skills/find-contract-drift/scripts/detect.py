#!/usr/bin/env python3
"""Detect cross-layer `/sites` contract drift."""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
COMMON_DIR = PROJECT_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

# Route the Python parse path (the registry-key extraction in
# ``_literal_dict_keys``) through the shared per-language adapter so it
# capability-gates on Python and gracefully skips non-Python inputs
# instead of crashing. The regex/template scanning paths are untouched.
_SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from _lib.lang_adapter import CAP_PYTHON_AST, get_adapter  # noqa: E402

from product_health import (  # noqa: E402
    expand_paths,
    finding,
    line_for_offset,
    load_module,
    normalize_record,
    read_text,
)
from workflows import workflow_template_roots  # noqa: E402
from product_topology import write_jsonl  # noqa: E402

SUFFIXES = (".py", ".js", ".html")
WINDOW_METHOD_CALL_RE = re.compile(r"window\.([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*\(")
WINDOW_EXPORT_RE = re.compile(r"window\.([A-Za-z_$][\w$]*)\s*=\s*\{")
WINDOW_PROP_EXPORT_RE = re.compile(r"window\.([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*=")
ENDPOINT_RE = re.compile(
    r"(?:window\.)?SiteConfigCore\.siteEndpoint(?:WithQuery|For)?\(\s*['\"]([^'\"]+)['\"]"
)
ID_RE = re.compile(r"\bid\s*=\s*['\"]([^'\"]+)['\"]")
DATA_ATTR_RE = re.compile(r"\s(data-[A-Za-z0-9_-]+)(?:\s|=|>)")
INCLUDE_BRAND_PICKER_ID_RE = re.compile(
    r"{%\s*include\s+['\"]core/_brand_picker\.html['\"].*?\bbp_id\s*=\s*['\"]([^'\"]+)['\"]",
    re.DOTALL,
)
JSON_SCRIPT_RE = re.compile(r"json_script\s*:\s*['\"]([^'\"]+)['\"]")
GET_ID_RE = re.compile(r"getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)")
DATA_SELECTOR_RE = re.compile(r"querySelector(?:All)?\(\s*['\"][^'\"]*\[(data-[A-Za-z0-9_-]+)")
DATASET_PROP_RE = re.compile(r"\.dataset\.([A-Za-z_$][\w$]*)\b")
SET_DATA_ATTR_RE = re.compile(r"\.setAttribute\(\s*['\"](data-[A-Za-z0-9_-]+)['\"]")
KNOWN_EXTERNAL_DOM_IDS = frozenset({"jss_textarea"})


def _matching_brace(text: str, open_pos: int) -> int | None:
    depth = 0
    in_string: str | None = None
    escaped = False
    for idx in range(open_pos, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {"'", '"', "`"}:
            in_string = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return idx
    return None


def _iter_object_entries(object_block: str) -> list[str]:
    body = object_block.strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]
    names: list[str] = []
    for raw in body.split(","):
        entry = raw.strip()
        if not entry or entry.startswith("//"):
            continue
        name = entry.split(":", 1)[0].strip().strip("'\"")
        if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
            names.append(name)
    return names


def _namespace_exports(js_paths: list[Path]) -> dict[str, set[str]]:
    exports: dict[str, set[str]] = {}
    for path in js_paths:
        text = read_text(path)
        for match in WINDOW_EXPORT_RE.finditer(text):
            open_pos = text.find("{", match.start(), match.end())
            close_pos = _matching_brace(text, open_pos) if open_pos != -1 else None
            if close_pos is None:
                continue
            namespace = match.group(1)
            exports.setdefault(namespace, set()).update(_iter_object_entries(text[open_pos : close_pos + 1]))
        for match in WINDOW_PROP_EXPORT_RE.finditer(text):
            exports.setdefault(match.group(1), set()).add(match.group(2))
    return exports


def _literal_dict_keys(path: Path, attr_names: set[str]) -> set[str]:
    if not path.exists():
        return set()
    adapter = get_adapter(path)
    if adapter is None or CAP_PYTHON_AST not in adapter.capabilities:
        return set()
    tree = adapter.parse(read_text(path))
    if tree is None:
        return set()
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        target_names: set[str] = set()
        for target in node.targets:
            if isinstance(target, ast.Name):
                target_names.add(target.id)
            elif isinstance(target, ast.Attribute):
                target_names.add(target.attr)
        if not target_names.intersection(attr_names) or not isinstance(node.value, ast.Dict):
            continue
        for key_node in node.value.keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                keys.add(key_node.value)
    return keys


def _endpoint_keys(project_root: Path) -> set[str]:
    workflow_paths = [
        project_root / "app" / "services" / "sites" / "site_workflow.py",
        project_root / "app" / "services" / "sites.py",
    ]
    keys: set[str] = set()
    for path in workflow_paths:
        keys.update(_literal_dict_keys(path, {"SITE_ENDPOINTS", "SITE_ENDPOINT_TEMPLATES"}))
    return keys


def _known_dom_contracts(template_paths: list[Path], js_paths: list[Path]) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    data_attrs: set[str] = set()
    for path in [*template_paths, *js_paths]:
        text = read_text(path)
        ids.update(ID_RE.findall(text))
        ids.update(INCLUDE_BRAND_PICKER_ID_RE.findall(text))
        ids.update(JSON_SCRIPT_RE.findall(text))
        data_attrs.update(DATA_ATTR_RE.findall(text))
        data_attrs.update(SET_DATA_ATTR_RE.findall(text))
        data_attrs.update(_dataset_prop_to_attr(match) for match in DATASET_PROP_RE.findall(text))
    return ids, data_attrs


def _dataset_prop_to_attr(prop: str) -> str:
    attr = []
    for char in prop:
        if char.isupper():
            attr.append("-")
            attr.append(char.lower())
        else:
            attr.append(char)
    return "data-" + "".join(attr).replace("_", "-")


def _sites_file(file: str) -> bool:
    return (
        file.startswith("templates/core/site_config")
        or file.startswith("templates/core/_site_checklist")
        or file.startswith("app/pages/sites")
        or file.startswith("static/js/site-config")
        or file.startswith("static/js/export-")
        or file.startswith("static/js/download-")
        or file.startswith("static/js/app-")
        or file.startswith("static/js/brand-picker")
    )


def _call_frontend_detector(project_root: Path) -> list[dict[str, Any]]:
    detector_path = PROJECT_ROOT / ".claude" / "skills" / "find-frontend-contract-drift" / "scripts" / "detect.py"
    if not detector_path.exists():
        return []
    module = load_module("frontend_contract_drift_detector", detector_path)
    js_root = project_root / "static" / "js"
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str, str]] = set()
    for root in workflow_template_roots(project_root):
        template_root = project_root / root
        if not template_root.exists():
            continue
        scope = module._scope.load_scope(project_root, module.SKILL_NAME)
        for record in module.detect(
            project_root=project_root,
            scope=scope,
            boot_threshold=3,
            template_root=template_root,
            js_root=js_root,
        ):
            file = str(record.get("file", ""))
            if not _sites_file(file):
                continue
            key = (
                file,
                int(record.get("lineno") or 0),
                str(record.get("pattern") or ""),
                str(record.get("summary") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                normalize_record(
                    record,
                    project_root,
                    default_confidence="medium",
                    next_skill="extract-workflow-registry",
                    guard_candidate=True,
                )
            )
    return findings


def detect(project_root: Path, paths: list[str] | None = None, include_frontend_detector: bool = True) -> list[dict[str, Any]]:
    scan_paths = expand_paths(project_root, paths, SUFFIXES)
    if paths is None:
        scan_paths = sorted(
            dict.fromkeys(
                [
                    *scan_paths,
                    *expand_paths(project_root, ["templates/core/includes"], (".html",)),
                ]
            )
        )
    template_paths = [path for path in scan_paths if path.suffix == ".html"]
    js_paths = [path for path in scan_paths if path.suffix == ".js"]

    records: list[dict[str, Any]] = []
    if include_frontend_detector:
        records.extend(_call_frontend_detector(project_root))

    exported = _namespace_exports(js_paths)
    endpoint_keys = _endpoint_keys(project_root)
    html_ids, data_attrs = _known_dom_contracts(template_paths, js_paths)

    for path in template_paths:
        text = read_text(path)
        for match in WINDOW_METHOD_CALL_RE.finditer(text):
            namespace, method = match.groups()
            if namespace in exported and method in exported[namespace]:
                continue
            if namespace not in exported and not namespace.startswith("SiteConfig"):
                continue
            records.append(
                finding(
                    "missing_js_export",
                    path,
                    line_for_offset(text, match.start()),
                    f"Template calls `window.{namespace}.{method}()` but the scanned JS export does not expose it.",
                    "Move the call behind an exported method, rename the template call, or drop stale inline startup code.",
                    project_root,
                    confidence="high" if namespace in exported else "medium",
                    next_skill="fix-workflow",
                    guard_candidate=True,
                    namespace=namespace,
                    method=method,
                )
            )

    for path in js_paths:
        text = read_text(path)
        for match in ENDPOINT_RE.finditer(text):
            key = match.group(1)
            if key in endpoint_keys:
                continue
            records.append(
                finding(
                    "missing_endpoint_key",
                    path,
                    line_for_offset(text, match.start()),
                    f"JS asks `SiteConfigCore` for endpoint key `{key}`, but the site workflow registry does not define it.",
                    "Add the endpoint key to `SiteWorkflowRegistry`, or replace the stale JS call with the canonical key.",
                    project_root,
                    confidence="high",
                    next_skill="extract-workflow-registry",
                    guard_candidate=True,
                    endpoint_key=key,
                )
            )
        for match in GET_ID_RE.finditer(text):
            dom_id = match.group(1)
            if dom_id in html_ids or dom_id in KNOWN_EXTERNAL_DOM_IDS:
                continue
            records.append(
                finding(
                    "missing_dom_id",
                    path,
                    line_for_offset(text, match.start()),
                    f"JS queries `#{dom_id}`, but no scanned `/sites` template defines that ID.",
                    "Confirm whether the element is generated dynamically; otherwise align the template ID or JS selector.",
                    project_root,
                    confidence="low",
                    next_skill="triage-debt",
                    guard_candidate=False,
                    dom_id=dom_id,
                )
            )
        for match in DATA_SELECTOR_RE.finditer(text):
            attr = match.group(1)
            if attr in data_attrs:
                continue
            records.append(
                finding(
                    "missing_data_selector",
                    path,
                    line_for_offset(text, match.start()),
                    f"JS queries `[${attr}]`, but no scanned `/sites` template defines that data attribute.",
                    "Confirm whether this selector belongs to another page; otherwise add the template attribute or remove stale JS.",
                    project_root,
                    confidence="low",
                    next_skill="triage-debt",
                    guard_candidate=False,
                    data_attr=attr,
                )
            )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--no-frontend-detector", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    records = detect(project_root, args.paths or None, not args.no_frontend_detector)
    write_jsonl(records, args.output)
    print(f"wrote {args.output}: {len(records)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
