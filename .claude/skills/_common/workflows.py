#!/usr/bin/env python3
"""Host-authored product-workflow definition — de-pnci'd out of `_common` code.

The product-topology skills (`/map-product-workflow`,
`/extract-workflow-registry`, `/find-workflow-duplication`) and the advisory
product-health skills used to carry one host's workflow baked into module
constants (`SITE_WORKFLOW_STEPS`, the `/sites` text-file whitelist,
`DEFAULT_SITES_TARGETS`). That made the toolkit assume pnci's product flow.

A workflow is now **host-authored data**: an optional
`.engineering/docs/product-workflows.md` descriptor in the cross-agent state
home (`engineering_home.docs_path`). The toolkit ships with **no** workflow —
an adopter declares theirs, and a repo with no descriptor yields empty results
(the skills run clean and find nothing rather than reporting another project's
flow). This mirrors `scope.py`'s ignore-first contract for the workflow layer.

Descriptor format (loose markdown, stdlib-parseable — reuses
``scope.parse_sections``; no PyYAML):

    ## Steps
    - `setup | Setup | site_setup | /sites/{id}/setup/`
    - `export | Export | site_export_data | /sites/{id}/export/data/`

    ## Extra labels        (workflow labels beyond the step labels)
    - Downloads
    - Brands

    ## Extra tab ids       (active-tab keys beyond the step ids)
    - extraction_fields
    - export_data

    ## Targets             (scan-target globs for product-health skills)
    - app/pages/sites
    - static/js/site-config-*.js

    ## Template roots       (template dirs for cross-layer contract scans)
    - templates/sites

    ## Text-file globs      (files scanned for duplicated workflow knowledge)
    - app/urls.py
    - templates/sites/*.html

    ## UI template globs    (templates that assign frontend boot globals)
    - templates/sites/site_config*.html

    ## UI script globs      (frontend scripts that read those boot globals)
    - static/js/site-config-*.js

    ## Routes               (how this host shapes product routes)
    - `page_prefix | sites`
    - `api_prefix | api`
    - `scoped_id_param | site_id`

Each ``## Steps`` bullet is a backtick-delimited row of four ``|``-separated
fields: ``id | label | route_name | path``. ``## Routes`` bullets are
``key | value`` rows (same backtick grammar) declaring how the host shapes its
routes — which URL prefix carries product pages vs APIs and which converter
param scopes a route to one product instance. Other sections are plain
backtick/text glob bullets (same bullet grammar as ``scope.py``).

Stdlib-only. Read-only against the project.
"""
from __future__ import annotations

import sys
from pathlib import Path

# _common siblings; importable regardless of who imported us.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import engineering_home as _home  # noqa: E402
import scope as _scope  # noqa: E402

DESCRIPTOR_NAME = "product-workflows.md"

# result key -> accepted (lowercased) headings that fill it.
_SECTION_MAP: dict[str, set[str]] = {
    "steps": {"steps", "workflow steps"},
    "extra_labels": {"extra labels", "labels"},
    "extra_tab_ids": {"extra tab ids", "tab ids", "extra tabs"},
    "targets": {"targets", "scan targets"},
    "template_roots": {"template roots", "templates"},
    "text_globs": {"text-file globs", "text file globs", "text globs"},
    "ui_template_globs": {"ui template globs", "frontend template globs"},
    "ui_script_globs": {"ui script globs", "frontend script globs"},
    "routes": {"routes", "route shape"},
}

_STEP_FIELDS = ("id", "label", "route_name", "path")


def _descriptor_text(repo_root: Path | str) -> str | None:
    """Raw text of `.engineering/docs/product-workflows.md`, or ``None``."""
    path, _used_legacy = _home.docs_path(repo_root, DESCRIPTOR_NAME)
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _sections(repo_root: Path | str) -> dict[str, list[str]]:
    """Parse all workflow sections at once; every key present (empty if absent)."""
    text = _descriptor_text(repo_root)
    if text is None:
        return {key: [] for key in _SECTION_MAP}
    return _scope.parse_sections(text, _SECTION_MAP)


def workflow_steps(repo_root: Path | str) -> list[dict[str, str]]:
    """Ordered workflow steps as ``{id,label,route_name,path}`` dicts.

    Empty list when no descriptor (or no ``## Steps`` section) exists. Rows that
    do not split into exactly four ``|`` fields are skipped (malformed, not
    fatal — a read-only audit must not crash on a typo'd descriptor).
    """
    steps: list[dict[str, str]] = []
    for row in _sections(repo_root)["steps"]:
        parts = [part.strip() for part in row.split("|")]
        if len(parts) != len(_STEP_FIELDS):
            continue
        steps.append(dict(zip(_STEP_FIELDS, parts, strict=True)))
    return steps


def workflow_labels(repo_root: Path | str) -> list[str]:
    """Step labels followed by any ``## Extra labels`` (order preserved, deduped)."""
    secs = _sections(repo_root)
    step_labels = [step["label"] for step in workflow_steps(repo_root)]
    return _dedupe(step_labels + secs["extra_labels"])


def workflow_tab_ids(repo_root: Path | str) -> list[str]:
    """Step ids followed by any ``## Extra tab ids`` (order preserved, deduped)."""
    secs = _sections(repo_root)
    step_ids = [step["id"] for step in workflow_steps(repo_root)]
    return _dedupe(step_ids + secs["extra_tab_ids"])


def workflow_targets(repo_root: Path | str) -> list[str]:
    """Scan-target globs for the product-health skills (``## Targets``)."""
    return list(_sections(repo_root)["targets"])


def workflow_template_roots(repo_root: Path | str) -> list[str]:
    """Template-root dirs for cross-layer contract scans (``## Template roots``)."""
    return list(_sections(repo_root)["template_roots"])


def workflow_text_globs(repo_root: Path | str) -> list[str]:
    """Globs for files scanned for duplicated workflow knowledge (``## Text-file globs``)."""
    return list(_sections(repo_root)["text_globs"])


def workflow_ui_template_globs(repo_root: Path | str) -> list[str]:
    """Globs for the workflow's UI templates — those that assign frontend boot
    globals (``## UI template globs``). Empty when no descriptor — the toolkit
    assumes no host template layout."""
    return list(_sections(repo_root)["ui_template_globs"])


def workflow_ui_script_globs(repo_root: Path | str) -> list[str]:
    """Globs for the workflow's UI scripts — those that read the boot globals
    (``## UI script globs``). Empty when no descriptor — the toolkit assumes no
    host script layout."""
    return list(_sections(repo_root)["ui_script_globs"])


def workflow_route_shape(repo_root: Path | str) -> dict[str, str]:
    """Host route shape as a ``{key: value}`` map (``## Routes``).

    Recognised keys: ``page_prefix`` (URL prefix carrying product *pages*),
    ``api_prefix`` (prefix carrying APIs), ``scoped_id_param`` (the converter
    param that scopes a route to one product instance, e.g. ``site_id``). Empty
    dict when no descriptor (or no ``## Routes`` section) exists — the route
    detectors then classify nothing, mirroring the ignore-first contract.
    Rows that are not ``key | value`` pairs are skipped (malformed, not fatal).
    """
    shape: dict[str, str] = {}
    for row in _sections(repo_root)["routes"]:
        if "|" not in row:
            continue
        key, _, value = row.partition("|")
        key = key.strip()
        if key:
            shape[key] = value.strip()
    return shape


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
