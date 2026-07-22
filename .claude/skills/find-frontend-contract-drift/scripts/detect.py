#!/usr/bin/env python3
"""Detect implicit frontend boot contracts between templates and JS."""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
import scope as _scope  # noqa: E402
from product_topology import extract_window_accesses, write_jsonl  # noqa: E402

SKILL_NAME = "find-frontend-contract-drift"

BROWSER_GLOBALS = {
    "document",
    "location",
    "localStorage",
    "sessionStorage",
    "console",
    "open",
    "fetch",
    "setTimeout",
    "clearTimeout",
}

TOP_LEVEL_DECL_RE = re.compile(r"^(?:let|const|var)\s+([A-Za-z_$][\w$]*)\b")
GLOBAL_AUTO_INIT_RE = (
    ("dom_content_loaded", re.compile(r"document\.addEventListener\(\s*['\"]DOMContentLoaded['\"]")),
    ("window_load", re.compile(r"window\.addEventListener\(\s*['\"]load['\"]")),
)
INIT_FUNCTION_RE = re.compile(
    r"^\s*function\s+(init[A-Za-z0-9_$]*|setup[A-Za-z0-9_$]*|boot[A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{",
    re.MULTILINE,
)
WINDOW_METHOD_CALL_RE = re.compile(r"window\.([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*\(")
STATIC_JS_RE = re.compile(r"{%\s*static\s+['\"]js/([^'\"]+\.js)['\"]\s*%}")
SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
FETCH_RE = re.compile(r"\bfetch\s*\(")
CALLBACK_BLOCK_START_RE = re.compile(
    r"(?:addEventListener|\.then|\.catch|\.finally|\.forEach|\.map|\.filter|\.reduce)\s*\([^{};]*"
    r"(?:function\s*\([^)]*\)|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)\s*\{"
)
EXPRESSION_CALLBACK_RE = re.compile(
    r"(?:addEventListener|\.then|\.catch|\.finally|\.forEach|\.map|\.filter|\.reduce)\s*"
    r"\([^;\n]*(?:function\s*\([^)]*\)|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)[^;\n]*\)"
)
DOM_MUTATION_RE = re.compile(
    r"\.(?:innerHTML|innerText|textContent|value)\s*=|"
    r"\.classList\.(?:add|remove|toggle|replace)\(|"
    r"\.(?:appendChild|append|prepend|remove|insertAdjacentHTML)\(|"
    r"\.style\.[A-Za-z-]+\s*="
)
PAGE_MARKER_RE = re.compile(
    r"document\.body\.dataset|"
    r"dataset\.[A-Za-z0-9_$]*page|"
    r"body\.classList\.contains\(|"
    r"querySelector\(\s*['\"]\[data-|"
    r"getAttribute\(\s*['\"]data-",
    re.IGNORECASE,
)
ELEMENT_MARKER_NAME_RE = (
    r"[^'\"]*(?:banner|panel|card|page|root|container|section|list|modal|form)[^'\"]*"
)
DIRECT_ELEMENT_GUARD_RE = re.compile(
    rf"if\s*\(\s*!\s*document\.getElementById\("
    rf"\s*['\"]{ELEMENT_MARKER_NAME_RE}['\"]\s*\)\s*\)\s*"
    r"(?:return|throw|\{\s*return)",
    re.IGNORECASE,
)
ELEMENT_LOOKUP_RE = re.compile(
    rf"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
    rf"(?:!!\s*)?document\.getElementById\(\s*['\"]({ELEMENT_MARKER_NAME_RE})['\"]\s*\)",
    re.IGNORECASE,
)
CANONICAL_BOOT_GLOBAL = "SITES_CONFIG"
COMPAT_BOOT_GLOBALS = {
    "DISCOVERY_LOCKED",
    "PRODUCT_URL_FILTER_ENABLED",
    "PRODUCT_URL_REGEX",
    "SETUP_MODE",
    "SIDEBAR_CURRENT_TAB",
    "SITEMAP_DISCOVERY_STATUS",
    "TEMPLATE_SITE_ID",
}


def _is_boot_global(name: str) -> bool:
    return name.isupper() or name.endswith("Config") or name.endswith("CONFIG")


def _is_sites_config_compat_assignment(name: str, accesses: list[object]) -> bool:
    if name not in COMPAT_BOOT_GLOBALS:
        return False
    return any("window.SITES_CONFIG" in str(access.evidence) for access in accesses)


def _workflow_scope(file: str) -> str:
    if file.startswith("templates/core/site_config") or file.startswith("static/js/site-config"):
        return "sites_workflow"
    if "external_source" in file:
        return "other_product_surface"
    return "repo_wide"


def _with_scope(finding: dict[str, object]) -> dict[str, object]:
    file = str(finding.get("file", ""))
    finding["workflow_scope"] = _workflow_scope(file)
    return finding


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


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


def _block_from_open_brace(text: str, open_pos: int) -> str | None:
    close_pos = _matching_brace(text, open_pos)
    if close_pos is None:
        return None
    return text[open_pos : close_pos + 1]


def _top_level_function_block(text: str, match: re.Match[str]) -> str | None:
    """Extract a top-level function body using its column-0 closing brace.

    JavaScript template literals often contain `${...}` braces, which
    makes a lightweight brace matcher noisy. Top-level functions in this
    codebase close with `}` at column 0, so use that stable shape.
    """
    open_pos = text.find("{", match.start(), match.end())
    if open_pos == -1:
        return None
    tail = text[match.end() :]
    close_match = re.search(r"^}\s*$", tail, re.MULTILINE)
    if close_match is None:
        return None
    return text[open_pos : match.end() + close_match.end()]


def _top_level_text(block: str) -> str:
    """Return only statements at the block's outermost brace depth."""
    out: list[str] = []
    depth = 0
    in_string: str | None = None
    escaped = False
    for char in block:
        if in_string:
            if depth == 1:
                out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {"'", '"', "`"}:
            in_string = char
            if depth == 1:
                out.append(char)
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            continue
        if depth == 1:
            out.append(char)
    return "".join(out)


def _actions_in_text(text: str) -> list[str]:
    actions: list[str] = []
    if FETCH_RE.search(text):
        actions.append("fetch")
    if DOM_MUTATION_RE.search(text):
        actions.append("dom_mutation")
    return actions


def _called_function_names(text: str) -> set[str]:
    names = set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", text))
    names.update(match.group(2) for match in WINDOW_METHOD_CALL_RE.finditer(text))
    names.update(
        re.findall(r"\b(?:setTimeout|setInterval)\s*\(\s*([A-Za-z_$][\w$]*)", text)
    )
    return names - {"if", "for", "while", "switch", "catch", "function", "fetch"}


def _function_blocks(js_paths: list[Path], project_root: Path) -> dict[str, dict[str, dict[str, object]]]:
    functions: dict[str, dict[str, dict[str, object]]] = {}
    for path in js_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        file = str(path.relative_to(project_root))
        file_functions = functions.setdefault(file, {})
        for match in FUNCTION_DECL_RE.finditer(text):
            block = _top_level_function_block(text, match)
            if block is None:
                continue
            file_functions.setdefault(
                match.group(1),
                {
                    "file": file,
                    "lineno": _line_for_offset(text, match.start()),
                    "block": block,
                },
            )
    return functions


def _strip_callback_blocks(text: str) -> str:
    """Remove callback bodies that are registered for later execution."""
    chars = list(text)
    for match in CALLBACK_BLOCK_START_RE.finditer(text):
        open_pos = text.rfind("{", match.start(), match.end())
        if open_pos == -1:
            continue
        close_pos = _matching_brace(text, open_pos)
        if close_pos is None:
            continue
        for idx in range(open_pos, close_pos + 1):
            chars[idx] = " "
    stripped = "".join(chars)
    return EXPRESSION_CALLBACK_RE.sub(lambda match: " " * len(match.group(0)), stripped)


def _actions_for_block(
    block: str,
    functions: dict[str, dict[str, object]],
    seen: set[str] | None = None,
) -> list[str]:
    seen = seen or set()
    immediate = _strip_callback_blocks(block)
    actions = set(_actions_in_text(immediate))
    for name in _called_function_names(immediate):
        if name in seen or name not in functions:
            continue
        seen.add(name)
        nested_block = str(functions[name]["block"])
        actions.update(_actions_for_block(nested_block, functions, seen))
    return sorted(actions)


def _has_page_marker(block: str) -> bool:
    if PAGE_MARKER_RE.search(block) or DIRECT_ELEMENT_GUARD_RE.search(block):
        return True
    for variable, _marker_name in ELEMENT_LOOKUP_RE.findall(block):
        variable_re = re.escape(variable)
        if re.search(
            rf"if\s*\(\s*!\s*{variable_re}\s*\)\s*(?:return|throw|\{{\s*return)",
            block,
        ):
            return True
        if re.search(rf"if\s*\(\s*{variable_re}\s*\)", block):
            return True
    return False


def _iter_export_entries(object_block: str) -> list[tuple[str, str]]:
    inner = object_block.strip()
    if inner.startswith("{") and inner.endswith("}"):
        inner = inner[1:-1]
    entries: list[tuple[str, str]] = []
    for raw_entry in inner.split(","):
        entry = raw_entry.strip()
        if not entry or entry.startswith("//"):
            continue
        if ":" in entry:
            method_name, function_name = [part.strip() for part in entry.split(":", 1)]
        else:
            method_name = function_name = entry
        method_name = method_name.strip("'\"")
        function_name = function_name.strip("'\"")
        if method_name and function_name:
            entries.append((method_name, function_name))
    return entries


def _namespace_exports(
    js_paths: list[Path],
    project_root: Path,
    functions_by_file: dict[str, dict[str, dict[str, object]]],
) -> dict[tuple[str, str], dict[str, object]]:
    exports: dict[tuple[str, str], dict[str, object]] = {}
    for path in js_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        file = str(path.relative_to(project_root))
        file_functions = functions_by_file.get(file, {})
        for match in re.finditer(r"window\.([A-Za-z_$][\w$]*)\s*=\s*\{", text):
            namespace = match.group(1)
            open_pos = text.find("{", match.start(), match.end())
            if open_pos == -1:
                continue
            object_block = _block_from_open_brace(text, open_pos)
            if object_block is None:
                continue
            for method_name, function_name in _iter_export_entries(object_block):
                if method_name in file_functions:
                    exports[(namespace, method_name)] = file_functions[method_name]
                elif function_name in file_functions:
                    exports[(namespace, method_name)] = file_functions[function_name]
    return exports


def _auto_init_blocks(
    text: str,
    functions: dict[str, dict[str, object]],
) -> list[tuple[str, int, str, list[str]]]:
    blocks: list[tuple[str, int, str, list[str]]] = []
    for label, pattern in GLOBAL_AUTO_INIT_RE:
        for match in pattern.finditer(text):
            open_pos = text.find("{", match.start(), min(len(text), match.end() + 500))
            if open_pos == -1:
                continue
            block = _block_from_open_brace(text, open_pos)
            if block is None:
                continue
            actions = _actions_for_block(block, functions)
            blocks.append((label, _line_for_offset(text, match.start()), block, actions))

    for match in INIT_FUNCTION_RE.finditer(text):
        name = match.group(1)
        call_re = re.compile(rf"^{re.escape(name)}\s*\(\s*\)\s*;?\s*$", re.MULTILINE)
        if not any(call.start() > match.end() for call in call_re.finditer(text)):
            continue
        block = _top_level_function_block(text, match)
        if block is None:
            continue
        actions = _actions_for_block(block, functions)
        blocks.append((f"top_level_call:{name}", _line_for_offset(text, match.start()), block, actions))
    return blocks


def _auto_init_findings(
    js_paths: list[Path],
    project_root: Path,
    functions: dict[str, dict[str, object]],
    shared_js_files: set[str],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    seen: set[tuple[str, int, str]] = set()
    for path in js_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        file = str(path.relative_to(project_root))
        if file not in shared_js_files:
            continue
        for label, lineno, block, actions in _auto_init_blocks(text, functions):
            if not actions or _has_page_marker(block):
                continue
            key = (file, lineno, label)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                _with_scope(
                    {
                        "pattern": "unscoped_global_auto_init",
                        "file": file,
                        "lineno": lineno,
                        "auto_init": label,
                        "actions": actions,
                        "summary": (
                            "Global JS auto-init performs "
                            f"{', '.join(actions)} without a page-marker check."
                        ),
                        "recommendation": (
                            "Gate this initializer on a page marker such as "
                            "`document.body.dataset`, `body.classList.contains(...)`, "
                            "or a `[data-*]` selector before fetching or mutating DOM."
                        ),
                    }
                )
            )
    return findings


def _is_shared_template(path: Path, project_root: Path) -> bool:
    rel = str(path.relative_to(project_root))
    return (
        "base" in path.name
        or "/includes/" in rel
        or rel.endswith("site_config_base.html")
    )


def _shared_script_files(template_paths: list[Path], project_root: Path) -> set[str]:
    files: set[str] = set()
    for path in template_paths:
        if not path.exists() or not _is_shared_template(path, project_root):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in STATIC_JS_RE.finditer(text):
            files.add(f"static/js/{match.group(1)}")
    return files


def _template_startup_regions(text: str) -> list[tuple[int, str]]:
    regions: list[tuple[int, str]] = []
    for script in SCRIPT_BLOCK_RE.finditer(text):
        script_text = script.group(1)
        script_start = script.start(1)
        masked = list(script_text)
        for _label, pattern in GLOBAL_AUTO_INIT_RE:
            for match in pattern.finditer(script_text):
                open_pos = script_text.find("{", match.start(), min(len(script_text), match.end() + 500))
                if open_pos == -1:
                    continue
                block = _block_from_open_brace(script_text, open_pos)
                if block is None:
                    continue
                close_pos = open_pos + len(block) - 1
                regions.append((script_start + open_pos, block))
                for idx in range(open_pos, close_pos + 1):
                    masked[idx] = " "
        immediate = _strip_callback_blocks("".join(masked))
        if immediate.strip():
            regions.append((script_start, immediate))
    return regions


def _shared_template_auto_init_findings(
    template_paths: list[Path],
    project_root: Path,
    exports: dict[tuple[str, str], dict[str, object]],
    functions_by_file: dict[str, dict[str, dict[str, object]]],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    seen: set[tuple[str, int, str]] = set()
    for path in template_paths:
        if not path.exists() or not _is_shared_template(path, project_root):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        file = str(path.relative_to(project_root))
        for region_offset, region in _template_startup_regions(text):
            for match in WINDOW_METHOD_CALL_RE.finditer(region):
                namespace = match.group(1)
                method_name = match.group(2)
                function = exports.get((namespace, method_name))
                if not function:
                    continue
                block = str(function["block"])
                file_functions = functions_by_file.get(str(function["file"]), {})
                actions = _actions_for_block(block, file_functions)
                if not actions or _has_page_marker(block):
                    continue
                lineno = _line_for_offset(text, region_offset + match.start())
                label = f"shared_template_call:window.{match.group(1)}.{method_name}"
                key = (file, lineno, label)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    _with_scope(
                        {
                            "pattern": "unscoped_global_auto_init",
                            "file": file,
                            "lineno": lineno,
                            "auto_init": label,
                            "js_file": function["file"],
                            "js_lineno": function["lineno"],
                            "actions": actions,
                            "summary": (
                                "Shared template calls JS initializer "
                                f"`window.{match.group(1)}.{method_name}()` which performs "
                                f"{', '.join(actions)} without a page-marker check."
                            ),
                            "recommendation": (
                                "Gate the exported initializer on a page marker before "
                                "starting fetch/polling or DOM mutation from a shared template."
                            ),
                        }
                    )
                )
    return findings


def _top_level_js_declarations(js_paths: list[Path], project_root: Path) -> dict[str, dict[str, object]]:
    declarations: dict[str, dict[str, object]] = {}
    for path in js_paths:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if line[:1].isspace():
                continue
            match = TOP_LEVEL_DECL_RE.match(line.strip())
            if not match:
                continue
            name = match.group(1)
            declarations.setdefault(
                name,
                {
                    "file": str(path.relative_to(project_root)),
                    "lineno": lineno,
                    "evidence": line.strip()[:200],
                },
            )
    return declarations


def _is_under(path: Path, root: Path) -> bool:
    """True if ``path`` is ``root`` or lives beneath it (resolved)."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def detect(
    *,
    project_root: Path,
    scope: _scope.Scope,
    boot_threshold: int,
    template_root: Path | None = None,
    js_root: Path | None = None,
) -> list[dict[str, object]]:
    # Select frontend files by EXTENSION over the whole repo, ignore-first
    # (BUILTIN_SKIP_DIRS + repo-wide ignore.md + this skill's `## Ignore`),
    # narrowed only by the host's `## Roots` — no baked `templates/` or
    # `static/js` scan root (ADR 0021). The optional `--template-root` /
    # `--js-root` overrides are a per-invocation narrowing applied on top of
    # the extension-selected set, not a layout assumption.
    template_paths = _scope.iter_paths(project_root, scope, extensions={".html"})
    js_paths = _scope.iter_paths(project_root, scope, extensions={".js"})
    if template_root is not None:
        template_paths = [p for p in template_paths if _is_under(p, template_root)]
    if js_root is not None:
        js_paths = [p for p in js_paths if _is_under(p, js_root)]
    functions_by_file = _function_blocks(js_paths, project_root)
    exports = _namespace_exports(js_paths, project_root, functions_by_file)
    shared_js_files = _shared_script_files(template_paths, project_root)
    template_accesses = extract_window_accesses(project_root, template_paths)
    js_accesses = extract_window_accesses(project_root, js_paths)

    template_assignments = [access for access in template_accesses if access.kind == "assignment"]
    js_reads = [access for access in js_accesses if access.kind == "read"]
    js_assignments = [access for access in js_accesses if access.kind == "assignment"]
    lexical_globals = _top_level_js_declarations(js_paths, project_root)

    assigned_by_template = defaultdict(list)
    for access in template_assignments:
        assigned_by_template[access.name].append(access)
    sites_config_compat_aliases = {
        name
        for name, accesses in assigned_by_template.items()
        if _is_sites_config_compat_assignment(name, accesses)
    }
    assigned_by_js = {access.name for access in js_assignments}
    reads_by_name = defaultdict(list)
    for access in js_reads:
        reads_by_name[access.name].append(access)

    findings: list[dict[str, object]] = []
    boot_names = sorted(
        name
        for name in assigned_by_template
        if (
            name != CANONICAL_BOOT_GLOBAL
            and name not in sites_config_compat_aliases
            and _is_boot_global(name)
        )
    )
    if len(boot_names) > boot_threshold:
        first = assigned_by_template[boot_names[0]][0]
        findings.append(
            _with_scope(
                {
                    "pattern": "boot_global_sprawl",
                    "file": first.file,
                    "lineno": first.lineno,
                    "globals": boot_names,
                    "summary": f"{len(boot_names)} template-injected `window.*` boot globals were found.",
                    "recommendation": "Replace scattered globals with one typed `window.SITES_CONFIG` payload.",
                }
            )
        )

    for name, accesses in sorted(assigned_by_template.items()):
        if name == CANONICAL_BOOT_GLOBAL or name in sites_config_compat_aliases:
            continue
        if _is_boot_global(name):
            findings.append(
                _with_scope(
                    {
                        "pattern": "implicit_template_global",
                        "file": accesses[0].file,
                        "lineno": accesses[0].lineno,
                        "global": name,
                        "read_count": len(reads_by_name.get(name, [])),
                        "summary": f"`window.{name}` is assigned directly by a template.",
                        "recommendation": "Prefer adding this field to the canonical workflow boot payload.",
                    }
                )
            )

    for name, accesses in sorted(reads_by_name.items()):
        if name in BROWSER_GLOBALS or name in assigned_by_js or name in assigned_by_template:
            continue
        if not _is_boot_global(name):
            continue
        first = accesses[0]
        lexical_global = lexical_globals.get(name)
        if lexical_global:
            findings.append(
                _with_scope(
                    {
                        "pattern": "window_read_with_lexical_fallback",
                        "file": first.file,
                        "lineno": first.lineno,
                        "global": name,
                        "lexical_file": lexical_global["file"],
                        "lexical_lineno": lexical_global["lineno"],
                        "summary": (
                            f"JS reads `window.{name}`, while `{name}` exists only as a "
                            "top-level lexical global."
                        ),
                        "recommendation": (
                            "Prefer reading this value through the canonical boot payload "
                            "or a frontend config accessor."
                        ),
                    }
                )
            )
            continue
        findings.append(
            _with_scope(
                {
                    "pattern": "undeclared_window_read",
                    "file": first.file,
                    "lineno": first.lineno,
                    "global": name,
                    "summary": f"JS reads `window.{name}` but no template or JS assignment was found in the scanned roots.",
                    "recommendation": "Declare the value in the boot payload or remove the implicit dependency.",
                }
            )
        )

    read_counts = Counter(access.name for access in js_reads)
    for name, count in sorted(read_counts.items()):
        if name == CANONICAL_BOOT_GLOBAL or name in BROWSER_GLOBALS or name in sites_config_compat_aliases:
            continue
        if count >= 4 and name in assigned_by_template:
            first = reads_by_name[name][0]
            findings.append(
                _with_scope(
                    {
                        "pattern": "widely_read_boot_global",
                        "file": first.file,
                        "lineno": first.lineno,
                        "global": name,
                        "read_count": count,
                        "summary": f"`window.{name}` is read {count} times across JS modules.",
                        "recommendation": "Route repeated reads through a single frontend config accessor.",
                    }
                )
            )
    for path in js_paths:
        file = str(path.relative_to(project_root))
        file_functions = functions_by_file.get(file, {})
        if file not in shared_js_files:
            continue
        findings.extend(_auto_init_findings([path], project_root, file_functions, shared_js_files))
    findings.extend(
        _shared_template_auto_init_findings(
            template_paths,
            project_root,
            exports,
            functions_by_file,
        )
    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--template-root",
        type=Path,
        default=None,
        help=(
            "optional per-invocation override; default is the whole repo, "
            "narrowed only by the host's scope/ignore descriptors."
        ),
    )
    parser.add_argument(
        "--js-root",
        type=Path,
        default=None,
        help=(
            "optional per-invocation override; default is the whole repo, "
            "narrowed only by the host's scope/ignore descriptors."
        ),
    )
    parser.add_argument("--boot-threshold", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    scope = _scope.load_scope(project_root, SKILL_NAME)
    template_root = None
    if args.template_root is not None:
        template_root = (
            args.template_root if args.template_root.is_absolute()
            else project_root / args.template_root
        )
    js_root = None
    if args.js_root is not None:
        js_root = (
            args.js_root if args.js_root.is_absolute()
            else project_root / args.js_root
        )
    findings = detect(
        project_root=project_root,
        scope=scope,
        boot_threshold=args.boot_threshold,
        template_root=template_root,
        js_root=js_root,
    )
    write_jsonl(findings, args.output)
    print(f"wrote {args.output}: {len(findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
