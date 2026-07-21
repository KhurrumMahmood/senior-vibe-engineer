#!/usr/bin/env python3
"""Detect comment/docstring/JSDoc drift.

The output format intentionally matches the simple product-topology report
shape: JSONL records with `pattern`, `file`, `lineno`, `summary`, and
`recommendation`.
"""
from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from support import (  # noqa: E402
    go_scan_payload,
    inventory_go,
    inventory_java,
    iter_files,
    java_scan_payload,
    probe_go,
    relpath,
    resolve_project_root,
    write_json,
    write_jsonl,
)

SUFFIXES = (".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".html")
JAVASCRIPT_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})
DEFAULT_TARGETS = (
    "app/pages/sites",
    "app/site_management",
    "app/api/site_config",
    "app/api/sitemaps.py",
    "app/api/field_config.py",
    "app/api/brand_downloads",
    "app/api/collections.py",
    "app/api/ptid.py",
    "app/api/visual_extraction.py",
    "app/api/training.py",
    "app/api/tier_detection.py",
    "app/api/brand_mapping.py",
    "app/api/site_checklist.py",
    "app/api/crawling/legacy_dispatch.py",
    "app/api/crawling/orphan_jobs.py",
    "app/pages/crawling.py",
    "app/services/sites",
    "static/js/site-config-core.js",
    "static/js/site-config-sidebar.js",
    "static/js/site-config-preview.js",
    "static/js/site-config-ui.js",
    "static/js/site-config-discovery.js",
    "static/js/site-config-custom-import.js",
    "static/js/site-config-external_source-brand.js",
    "static/js/site-config-agent-review.js",
    "static/js/site-config-brand-detection.js",
    "static/js/site-config-external_source-summary.js",
    "static/js/site-config-forms.js",
    "static/js/site-config-proxy.js",
    "static/js/site-config-jobs.js",
    "static/js/site-config-flatdata-chat.js",
    "static/js/site-config-flatdata-preview.js",
    "static/js/site-config-fields.js",
    "static/js/site-config-training.js",
    "static/js/site-config-ptid.js",
    "static/js/site-config-pages.js",
    "static/js/site-config-images.js",
    "static/js/site-config-brand-mapping.js",
    "static/js/download-filters.js",
    "static/js/export-preview.js",
    "static/js/export-filters.js",
    "static/js/export-viewer-utils.js",
    "static/js/export-progress.js",
    "static/js/brand-picker.js",
    "static/js/app-dialog.js",
    "static/js/app-modal.js",
    "static/js/app-csrf.js",
    "templates/core/site_config_base.html",
    "templates/core/_site_checklist.html",
    "app/pages/sites/templates/core",
)

STALE_TERM_RE = re.compile(
    r"\b(?:SiteConfig|Site Configuration|site configuration|site config)\b"
)
DOC_REF_RE = re.compile(
    r"\b(?:L\d{2,}|line\s+\d{2,}|[A-Za-z0-9_./-]+\.(?:py|js|jsx|mjs|cjs|ts|tsx|html|go|java):\d{1,5})\b",
    re.IGNORECASE,
)
NARRATION_RE = re.compile(
    r"^(?:"
    r"get|create|update|delete|remove|save|return|format|parse|load|build|"
    r"render|initialize|validate|check|set|clear|find|filter|sort|count|"
    r"calculate|fetch|call|loop|iterate|append|add|show|hide|toggle|"
    r"populate|test|open|close|wire|bind|store|reset|refresh|delegate|"
    r"replace|group|compute|sync|start|stop|resume"
    r")\b",
    re.IGNORECASE,
)
WHY_WORD_RE = re.compile(
    r"\b(?:why|because|compat|legacy|intentional|avoid|must|cannot|workaround|"
    r"race|safety|security|performance|cache|contract|Django|ScraperAPI|Celery|"
    r"temporary|until|fallback|fall\s+back|preserve|exclude|server-side|client-side|"
    r"since|so|if|when|while|after|before|for|via|with|without|from|against|"
    r"only|needed|first|external|min|attached|json_script|stale|once|AI|"
    r"pending|already|escaped|XSS|injection|restores)\b",
    re.IGNORECASE,
)
SECTION_LABEL_RE = re.compile(
    r"^(?:"
    r"module state|state|detail panel state|job management state|"
    r"global auto-process state management|helpers?|utilities|utility functions|"
    r"public query api|data fetching|rendering|actions?|init|initialization|"
    r"window export|exports?|export functions(?: for use by other modules)?|"
    r"toolbar handlers?|event bindings?|index management|classification|results?|"
    r"url dropdown|screenshot\s*/\s*html viewer|load\s*/\s*render field configs|"
    r"additional extracted data section|re-process all pages|identity|breadcrumbs|"
    r"description|marketing copy|features|specifications|product attributes|"
    r"attachments|video|missing fields|other arrays|header|body|"
    r"pies quality|tier info banner|job banner"
    r")$",
    re.IGNORECASE,
)
JS_FUNCTION_RE = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:(?P<async1>async)\s+)?function\s+(?P<fn>[A-Za-z_$][\w$]*)\s*\("
    r"|^\s*(?:export\s+)?(?:const|let|var)\s+(?P<const>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:"
    r"function\b|\([^)]*\)\s*(?::\s*[^=\n]+?)?\s*=>|[A-Za-z_$][\w$]*\s*=>)"
    r"|^\s*window\.(?P<win>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\b"
)
JSDOC_NAME_RE = re.compile(
    r"^(?:initialize|handle|start|open|submit|run)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    pattern: str
    file: str
    lineno: int
    summary: str
    recommendation: str
    language: str = ""


def emit(
    pattern: str,
    path: Path,
    lineno: int,
    summary: str,
    recommendation: str,
    project_root: Path,
    language: str = "",
) -> Finding:
    return Finding(
        pattern=pattern,
        file=relpath(path, project_root),
        lineno=lineno,
        summary=summary.strip(),
        recommendation=recommendation.strip(),
        language=language,
    )


def is_comment_noise(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith(("TODO", "FIXME", "NOTE", "noqa", "type:", "pylint", "ruff", "fmt")):
        return False
    if WHY_WORD_RE.search(stripped):
        return False
    normalized = re.sub(r"^[A-Z]{1,4}\d+:\s*", "", stripped)
    words = re.findall(r"[A-Za-z]+", normalized)
    return len(words) <= 14 and bool(NARRATION_RE.match(normalized))


def is_banner_text(text: str) -> bool:
    stripped = text.strip().strip("/#*").strip()
    if not stripped:
        return False
    if re.search(r"[─━═]{2,}", stripped):
        return True
    if re.fullmatch(r"[-_=*\s]{3,}", stripped):
        return True
    if re.fullmatch(r"[-_=*\s]{3,}.+[-_=*\s]{3,}", stripped):
        return True
    if re.match(r"^section\s+\d+", stripped, re.IGNORECASE):
        return True
    if stripped.isupper() and len(stripped.split()) <= 5:
        return True
    if SECTION_LABEL_RE.match(stripped):
        return True
    return False


def should_keep_html_comment(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:conditional|shared|payload|gotcha|Django|HTMX|modal target|JavaScript owns|"
            r"required|do not|compat|legacy|intentional|template)\b",
            text,
            re.IGNORECASE,
        )
    )


def is_noisy_html_comment(text: str) -> bool:
    stripped = re.sub(r"\s+", " ", text.strip())
    if not stripped or should_keep_html_comment(stripped):
        return False
    return bool(
        re.match(
            r"^(?:section\s+\d+[:.-]?\s*)?(?:header|content|main content|sidebar|navigation|"
            r"tabs?|buttons?|save button|top save button|scripts?|styles?|modal|forms?|"
            r"site information|credentials|settings|status|actions?)$",
            stripped,
            re.IGNORECASE,
        )
        or stripped.upper().startswith("SECTION ")
    )


def scan_stale_and_refs(
    path: Path,
    lineno: int,
    text: str,
    findings: list[Finding],
    project_root: Path,
) -> None:
    if STALE_TERM_RE.search(text):
        findings.append(
            emit(
                "stale_comment_term",
                path,
                lineno,
                text[:180],
                "Update comments/docstrings to current Site/SiteConfig terminology unless the text names the intentional BrandMapping exception.",
                project_root,
            )
        )
    if DOC_REF_RE.search(text):
        findings.append(
            emit(
                "malformed_doc_reference",
                path,
                lineno,
                text[:180],
                "Replace brittle line-number references with a durable symbol, route, doc section, or repo-relative path.",
                project_root,
            )
        )


def next_nonblank_line(lines: list[str], start_index: int) -> tuple[int, str] | None:
    for idx in range(start_index, len(lines)):
        if lines[idx].strip():
            return idx + 1, lines[idx]
    return None


def previous_nonblank_line(lines: list[str], start_index: int) -> tuple[int, str] | None:
    for idx in range(start_index, -1, -1):
        if lines[idx].strip():
            return idx + 1, lines[idx]
    return None


def scan_python(path: Path, project_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings
    lines = text.splitlines()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue
            lineno = token.start[0]
            comment = token.string.lstrip("#").strip()
            if lineno == 1 and token.string.startswith("#!"):
                continue
            scan_stale_and_refs(path, lineno, comment, findings, project_root)
            line = lines[lineno - 1] if lineno - 1 < len(lines) else ""
            if token.start[1] > len(line) - len(line.lstrip()):
                continue
            if is_banner_text(comment):
                findings.append(
                    emit(
                        "detached_section_banner",
                        path,
                        lineno,
                        comment[:180],
                        "Delete the banner, or convert it to an adjacent docstring/JSDoc-style comment on the symbol it describes.",
                        project_root,
                    )
                )
            elif is_comment_noise(comment):
                findings.append(
                    emit(
                        "obvious_narration_comment",
                        path,
                        lineno,
                        comment[:180],
                        "Delete comments that narrate the next line; keep or rewrite only when they explain why, contract, caveat, or history.",
                        project_root,
                    )
                )
    except tokenize.TokenError:
        pass

    try:
        module = ast.parse(text, filename=str(path))
    except SyntaxError:
        return findings

    for node in ast.walk(module):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc:
                scan_stale_and_refs(path, getattr(node, "lineno", 1), doc, findings, project_root)

        if not isinstance(node, ast.ClassDef):
            continue
        if node.name.startswith("_") or node.name == "Meta":
            continue
        doc = ast.get_docstring(node)
        if not doc:
            findings.append(
                emit(
                    "missing_public_class_docstring",
                    path,
                    node.lineno,
                    f"class {node.name}",
                    "Add a concise class docstring explaining ownership, contract, or route/service role.",
                    project_root,
                )
            )
            continue
        first = doc.strip().splitlines()[0].strip()
        word_count = len(re.findall(r"[A-Za-z0-9_]+", first))
        generic = re.match(r"^(?:View|Handler|Manager|Service|Helper|Utility|Class)\.?$", first, re.IGNORECASE)
        if word_count < 5 or generic:
            findings.append(
                emit(
                    "thin_public_class_docstring",
                    path,
                    node.lineno,
                    f"class {node.name}: {first}",
                    "Strengthen the class docstring so it names the responsibility or contract, not just the noun.",
                    project_root,
                )
            )
    return findings


def extract_js_comment_text(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("//"):
        return stripped[2:].strip()
    if stripped.startswith("/*") or stripped.startswith("*"):
        return stripped.strip("/* ").strip()
    return None


def jsdoc_before(lines: list[str], line_index: int) -> str | None:
    idx = line_index - 1
    blanks_seen = 0
    while idx >= 0 and blanks_seen <= 2:
        stripped = lines[idx].strip()
        if not stripped:
            blanks_seen += 1
            idx -= 1
            continue
        if stripped.endswith("*/"):
            block: list[str] = []
            while idx >= 0:
                block.append(lines[idx].strip())
                if lines[idx].strip().startswith("/**"):
                    return "\n".join(reversed(block))
                if lines[idx].strip().startswith("/*"):
                    return None
                idx -= 1
        return None
    return None


def has_jsdoc_before(lines: list[str], line_index: int) -> bool:
    return jsdoc_before(lines, line_index) is not None


def extract_js_params(line: str) -> list[str]:
    signature = line.split("{", 1)[0]
    match = re.search(r"\((?P<params>[^)]*)\)", signature)
    if not match:
        arrow = re.search(r"=\s*(?:async\s+)?(?P<param>[A-Za-z_$][\w$]*)\s*=>", signature)
        return [arrow.group("param")] if arrow else []
    params: list[str] = []
    for raw_param in match.group("params").split(","):
        param = raw_param.strip()
        if not param or param.startswith(("...", "{", "[")):
            continue
        param = param.split("=", 1)[0].strip()
        param = param.split(":", 1)[0].strip().rstrip("?")
        if re.fullmatch(r"[A-Za-z_$][\w$]*", param):
            params.append(param)
    return params


def is_thin_jsdoc(jsdoc: str, params: list[str]) -> bool:
    body_lines = [
        re.sub(r"^/\*\*|^\*/?$|^\*\s?", "", line).strip()
        for line in jsdoc.splitlines()
    ]
    body = "\n".join(line for line in body_lines if line)
    if not body:
        return True
    if params and "@param" not in body:
        return True
    words = re.findall(r"[A-Za-z0-9_]+", body)
    return len(words) <= 4 and "@" not in body


def scan_javascript(path: Path, project_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings
    lines = text.splitlines()
    in_block_comment = False
    in_jsdoc_comment = False
    for idx, line in enumerate(lines):
        lineno = idx + 1
        stripped = line.strip()
        comment_text = None
        is_jsdoc_line = in_jsdoc_comment
        if in_block_comment:
            comment_text = stripped.strip("/* ").strip()
            if "*/" in stripped:
                in_block_comment = False
                in_jsdoc_comment = False
        elif stripped.startswith("/*"):
            comment_text = stripped.strip("/* ").strip()
            is_jsdoc_line = stripped.startswith("/**")
            if "*/" not in stripped:
                in_block_comment = True
                in_jsdoc_comment = is_jsdoc_line
        elif stripped.startswith("//"):
            comment_text = stripped[2:].strip()

        if comment_text is not None:
            scan_stale_and_refs(path, lineno, comment_text, findings, project_root)
            if is_jsdoc_line:
                continue
            if is_banner_text(comment_text):
                findings.append(
                    emit(
                        "detached_section_banner",
                        path,
                        lineno,
                        comment_text[:180],
                        "Replace banner comments with adjacent JSDoc for public-ish functions, or delete them when names already carry the structure.",
                        project_root,
                    )
                )
            elif is_comment_noise(comment_text):
                findings.append(
                    emit(
                        "obvious_narration_comment",
                        path,
                        lineno,
                        comment_text[:180],
                        "Delete narration comments; use JSDoc or a caveat comment only when there is contract or intent to preserve.",
                        project_root,
                    )
                )

        match = JS_FUNCTION_RE.match(line)
        if not match:
            continue
        name = match.group("fn") or match.group("const") or match.group("win")
        if not name or name.startswith("_"):
            continue
        if not JSDOC_NAME_RE.match(name) and not match.group("win") and not match.group("async1"):
            continue
        jsdoc = jsdoc_before(lines, idx)
        if jsdoc:
            params = extract_js_params(line)
            if is_thin_jsdoc(jsdoc, params):
                findings.append(
                    emit(
                        "thin_jsdoc_comment",
                        path,
                        lineno,
                        f"{name}() has JSDoc without the useful contract detail",
                        "Make public-ish JSDoc describe parameters, return values, side effects, or workflow contract; otherwise prefer no comment.",
                        project_root,
                    )
                )
            continue
        findings.append(
            emit(
                "jsdoc_candidate",
                path,
                lineno,
                f"{name}() lacks adjacent JSDoc",
                "Add real JSDoc when this function is public-ish, async, global, shared, or carries non-obvious side effects; otherwise rename/delete nearby banner comments.",
                project_root,
            )
        )
    return findings


def extract_go_comments(text: str) -> tuple[list[tuple[int, str, bool]], str | None]:
    """Extract real Go comments while ignoring quoted and raw string contents."""
    comments: list[tuple[int, str, bool]] = []
    index = 0
    line = 1
    line_start = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\n":
            line += 1
            line_start = index + 1
            index += 1
            continue
        if char in {'"', "'", "`"}:
            quote = char
            index += 1
            escaped = False
            while index < length:
                current = text[index]
                if current == "\n":
                    line += 1
                    line_start = index + 1
                    if quote != "`":
                        return comments, f"unterminated quoted literal at line {line - 1}"
                if quote != "`" and escaped:
                    escaped = False
                elif quote != "`" and current == "\\":
                    escaped = True
                elif current == quote:
                    index += 1
                    break
                index += 1
            else:
                return comments, f"unterminated quoted literal at line {line}"
            continue
        if char != "/" or index + 1 >= length or text[index + 1] not in {"/", "*"}:
            index += 1
            continue
        start_line = line
        standalone = not text[line_start:index].strip()
        if text[index + 1] == "/":
            end = text.find("\n", index + 2)
            if end < 0:
                end = length
            comments.append((start_line, text[index + 2:end].strip(), standalone))
            index = end
            continue
        end = text.find("*/", index + 2)
        if end < 0:
            return comments, f"unterminated block comment at line {start_line}"
        body = text[index + 2:end]
        comments.append((start_line, body.strip(), standalone))
        line += body.count("\n")
        last_newline = body.rfind("\n")
        if last_newline >= 0:
            line_start = index + 2 + last_newline + 1
        index = end + 2
    return comments, None


def scan_go(path: Path, project_root: Path) -> tuple[list[Finding], str | None]:
    """Scan Go's lexical comment surface without making syntax/API claims."""
    text = path.read_text(encoding="utf-8")
    comments, lexical_error = extract_go_comments(text)
    findings: list[Finding] = []
    for lineno, comment, standalone in comments:
        scan_stale_and_refs(path, lineno, comment, findings, project_root)
        # Mark generic findings emitted above with their actual language.
        for index in range(len(findings) - 1, -1, -1):
            finding = findings[index]
            if finding.lineno != lineno or finding.language:
                break
            findings[index] = Finding(**{**asdict(finding), "language": "go"})
        if not standalone:
            continue
        if is_banner_text(comment):
            findings.append(
                emit(
                    "detached_section_banner",
                    path,
                    lineno,
                    comment[:180],
                    "Delete the banner or replace it with an adjacent Go comment that explains ownership or contract.",
                    project_root,
                    "go",
                )
            )
        elif is_comment_noise(comment):
            findings.append(
                emit(
                    "obvious_narration_comment",
                    path,
                    lineno,
                    comment[:180],
                    "Delete narration comments; keep Go comments that explain intent, constraints, or compatibility.",
                    project_root,
                    "go",
                )
            )
    return findings, lexical_error


def extract_java_comments(text: str) -> tuple[list[tuple[int, str, bool]], str | None]:
    """Extract Java comments while ignoring strings, chars, and text blocks."""
    comments: list[tuple[int, str, bool]] = []
    index = 0
    line = 1
    line_start = 0
    length = len(text)
    while index < length:
        if text[index] == "\n":
            line += 1
            line_start = index + 1
            index += 1
            continue
        if text.startswith('"""', index):
            start_line = line
            index += 3
            while index < length:
                if text.startswith('"""', index) and (
                    index == 0 or text[index - 1] != "\\"
                ):
                    index += 3
                    break
                if text[index] == "\n":
                    line += 1
                    line_start = index + 1
                index += 1
            else:
                return comments, f"unterminated text block at line {start_line}"
            continue
        if text[index] in {'"', "'"}:
            quote = text[index]
            start_line = line
            index += 1
            escaped = False
            while index < length:
                current = text[index]
                if current == "\n":
                    return comments, f"unterminated quoted literal at line {start_line}"
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    index += 1
                    break
                index += 1
            else:
                return comments, f"unterminated quoted literal at line {start_line}"
            continue
        if text[index] != "/" or index + 1 >= length or text[index + 1] not in {"/", "*"}:
            index += 1
            continue
        start_line = line
        standalone = not text[line_start:index].strip()
        if text[index + 1] == "/":
            end = text.find("\n", index + 2)
            if end < 0:
                end = length
            comments.append((start_line, text[index + 2:end].strip(), standalone))
            index = end
            continue
        end = text.find("*/", index + 2)
        if end < 0:
            return comments, f"unterminated block comment at line {start_line}"
        body = text[index + 2:end]
        comments.append((start_line, body.strip(), standalone))
        line += body.count("\n")
        last_newline = body.rfind("\n")
        if last_newline >= 0:
            line_start = index + 2 + last_newline + 1
        index = end + 2
    return comments, None


def scan_java(path: Path, project_root: Path) -> tuple[list[Finding], str | None]:
    """Scan Java's bounded lexical comment surface without parsing source."""
    text = path.read_text(encoding="utf-8")
    comments, lexical_error = extract_java_comments(text)
    findings: list[Finding] = []
    for lineno, comment, standalone in comments:
        before = len(findings)
        scan_stale_and_refs(path, lineno, comment, findings, project_root)
        for index in range(before, len(findings)):
            findings[index] = Finding(**{**asdict(findings[index]), "language": "java"})
        if not standalone:
            continue
        if is_banner_text(comment):
            findings.append(
                emit(
                    "detached_section_banner",
                    path,
                    lineno,
                    comment[:180],
                    "Delete the banner or replace it with adjacent Java documentation that explains ownership or contract.",
                    project_root,
                    "java",
                )
            )
        elif is_comment_noise(comment):
            findings.append(
                emit(
                    "obvious_narration_comment",
                    path,
                    lineno,
                    comment[:180],
                    "Delete narration comments; keep Java comments that explain intent, constraints, or compatibility.",
                    project_root,
                    "java",
                )
            )
    return findings, lexical_error


def scan_html(path: Path, project_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings
    for match in re.finditer(r"<!--(?P<body>.*?)-->", text, re.DOTALL):
        lineno = text.count("\n", 0, match.start()) + 1
        body = re.sub(r"\s+", " ", match.group("body").strip())
        scan_stale_and_refs(path, lineno, body, findings, project_root)
        if is_noisy_html_comment(body):
            findings.append(
                emit(
                    "noisy_html_comment",
                    path,
                    lineno,
                    body[:180],
                    "Delete template comments that only duplicate visible headings or obvious HTML structure.",
                    project_root,
                )
            )
    for match in re.finditer(r"<script\b[^>]*>(?P<body>.*?)</script>", text, re.IGNORECASE | re.DOTALL):
        body = match.group("body")
        start_line = text.count("\n", 0, match.start("body")) + 1
        for offset, line in enumerate(body.splitlines()):
            lineno = start_line + offset
            stripped = line.strip()
            if not stripped.startswith("//"):
                continue
            comment = stripped[2:].strip()
            scan_stale_and_refs(path, lineno, comment, findings, project_root)
            if is_banner_text(comment):
                findings.append(
                    emit(
                        "detached_section_banner",
                        path,
                        lineno,
                        comment[:180],
                        "Replace script banner comments with adjacent JSDoc or delete them when function and variable names already carry the structure.",
                        project_root,
                    )
                )
            elif is_comment_noise(comment):
                findings.append(
                    emit(
                        "obvious_narration_comment",
                        path,
                        lineno,
                        comment[:180],
                        "Delete comments that narrate inline template scripts; keep only intent, caveat, or template/JS ownership notes.",
                        project_root,
                    )
                )
    return findings


def collect_files(paths: Iterable[str], project_root: Path) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = project_root / path
        if path.is_dir():
            candidates = iter_files(path, SUFFIXES)
        elif path.is_file() and not path.is_symlink() and path.suffix in SUFFIXES:
            candidates = [path]
        else:
            candidates = []
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(candidate)
    return sorted(files)


def scan_files(files: Iterable[Path], project_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        if path.suffix == ".py":
            findings.extend(scan_python(path, project_root))
        elif path.suffix.lower() in JAVASCRIPT_SUFFIXES:
            findings.extend(scan_javascript(path, project_root))
        elif path.suffix == ".html":
            findings.extend(scan_html(path, project_root))
        elif path.suffix.lower() == ".go":
            go_findings, _error = scan_go(path, project_root)
            findings.extend(go_findings)
    return sorted(findings, key=lambda item: (item.file, item.lineno, item.pattern, item.summary))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect comment/docstring/JSDoc drift.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to scan. Defaults to the legacy site-workflow surface.",
    )
    parser.add_argument("--output", required=True, type=Path, help="JSONL output path.")
    parser.add_argument(
        "--language",
        choices=("auto", "go", "java"),
        default="auto",
        help="Use `go` or `java` for a bounded language inventory/comment contract.",
    )
    parser.add_argument("--project-root", type=Path, default=None,
                        help="Target project root anchoring relative paths "
                             "(default: git toplevel of cwd, else cwd)")
    args = parser.parse_args(argv)

    project_root = resolve_project_root(args.project_root)
    target_paths = args.paths or list(DEFAULT_TARGETS)
    if args.language == "go":
        scan_path = args.output.with_name("scan.json")
        tool, tool_rc = probe_go()
        if tool_rc:
            write_json(
                {
                    **tool,
                    "language": "go",
                    "analyzer": "python-go-comment-lexer",
                    "inventory": [],
                    "errors": [],
                    "summary": {"discovered": 0, "eligible": 0, "excluded": 0, "failed": 0},
                },
                scan_path,
            )
            write_jsonl([], args.output)
            return tool_rc
        inventory, files, errors = inventory_go(target_paths, project_root)
        scan = go_scan_payload(tool, inventory, errors)
        findings: list[Finding] = []
        for path in files:
            go_findings, lexical_error = scan_go(path, project_root)
            findings.extend(go_findings)
            if lexical_error:
                scan["errors"].append(f"{relpath(path, project_root)}:{lexical_error}")
        if scan["errors"]:
            scan["status"] = "partial"
            scan["summary"]["failed"] = len(scan["errors"]) + sum(
                row["role"] == "failed" for row in inventory
            )
        if not inventory:
            scan["status"] = "unsupported"
            scan["failure_kind"] = "no-go-files"
        findings.sort(key=lambda item: (item.file, item.lineno, item.pattern, item.summary))
        write_jsonl(
            (
                {key: value for key, value in asdict(finding).items() if value != ""}
                for finding in findings
            ),
            args.output,
        )
        write_json(scan, scan_path)
        print(
            f"scanned {scan['summary']['eligible']} eligible Go files from "
            f"{scan['summary']['discovered']} inventoried; wrote {len(findings)} findings "
            f"to {relpath(args.output, project_root)}"
        )
        return 2 if scan["status"] == "unsupported" else 0
    if args.language == "java":
        scan_path = args.output.with_name("scan.json")
        inventory, files, errors = inventory_java(target_paths, project_root)
        findings = []
        for path in files:
            java_findings, lexical_error = scan_java(path, project_root)
            findings.extend(java_findings)
            if lexical_error:
                relative = relpath(path, project_root)
                errors.append(f"{relative}:{lexical_error}")
                for row in inventory:
                    if row["file"] == relative:
                        row.update(
                            role="failed", reason="lexical-error", detail=lexical_error
                        )
                        break
        scan = java_scan_payload(inventory, errors)
        if not inventory:
            scan["status"] = "unsupported"
            scan["failure_kind"] = "no-java-files"
        findings.sort(key=lambda item: (item.file, item.lineno, item.pattern, item.summary))
        write_jsonl(
            (
                {key: value for key, value in asdict(finding).items() if value != ""}
                for finding in findings
            ),
            args.output,
        )
        write_json(scan, scan_path)
        print(
            f"scanned {scan['summary']['eligible']} eligible Java files from "
            f"{scan['summary']['discovered']} inventoried; wrote {len(findings)} findings "
            f"to {relpath(args.output, project_root)}"
        )
        return 2 if scan["status"] == "unsupported" else 0
    args.output.with_name("scan.json").unlink(missing_ok=True)
    files = collect_files(target_paths, project_root)
    findings = scan_files(files, project_root)
    write_jsonl(
        ({key: value for key, value in asdict(finding).items() if value != ""} for finding in findings),
        args.output,
    )
    print(f"scanned {len(files)} files; wrote {len(findings)} findings to {relpath(args.output, project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
