"""Resolve scanner-specific scope modes from the shared scan request."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_scope_contracts(library_root: Path) -> dict[str, dict[str, Any]]:
    """Load reviewed current scanner capabilities, or return no claims."""
    path = library_root / ".claude" / "skills" / "_common" / "scan_scope_contracts.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["skills"]
        if payload.get("schema_version") != 1 or not isinstance(rows, list):
            raise TypeError("unsupported scope-contract schema")
        contracts = {row["skill"]: row for row in rows}
        if len(contracts) != len(rows):
            raise TypeError("duplicate scope-contract skill")
        return contracts
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return {}


def recommendation_scan(request, contract: dict[str, Any] | None) -> dict[str, Any]:
    """Return an honest effective mode for one recommended scanner."""
    base = {
        "requested_mode": request.requested_mode,
        "selector": request.selector,
    }
    if contract is None:
        return {
            **base,
            "status": "unavailable",
            "effective_mode": None,
            "diff_semantics": None,
            "reason": "scope_contract_unavailable",
        }
    supported = contract["current_modes"]
    if request.requested_mode == "auto":
        selector_default = {
            "paths": "paths",
            "project": "project",
        }.get(request.selector["kind"], "changed-files")
        effective = (
            selector_default
            if selector_default in supported
            else contract["current_default_mode"]
        )
    else:
        effective = request.requested_mode
    if effective not in supported:
        compatible = None
        reason = None
        if effective == "diff-lines":
            if contract["diff_semantics"] == "seed-analysis":
                compatible = next(
                    (mode for mode in ("changed-files", "paths") if mode in supported),
                    None,
                )
            elif (
                contract["diff_semantics"] == "trigger-analysis"
                and "project" in supported
            ):
                compatible = "project"
            if compatible is not None:
                reason = "wider_semantics_required"
        elif effective == "changed-files" and "paths" in supported:
            compatible = "paths"
            reason = "complete_selected_paths_equivalent"
        if compatible is not None:
            return {
                **base,
                "status": "widened" if effective == "diff-lines" else "adapted",
                "effective_mode": compatible,
                "diff_semantics": contract["diff_semantics"],
                "reason": reason,
            }
        return {
            **base,
            "status": "unsupported",
            "effective_mode": None,
            "diff_semantics": contract["diff_semantics"],
            "reason": "scope_mode_not_supported",
            "supported_modes": supported,
        }
    if effective == "diff-lines" and request.line_filter_safe is not True:
        if "changed-files" not in supported:
            return {
                **base,
                "status": "unsafe",
                "effective_mode": None,
                "diff_semantics": contract["diff_semantics"],
                "reason": "content_basis_mismatch",
            }
        return {
            **base,
            "status": "degraded",
            "effective_mode": "changed-files",
            "diff_semantics": contract["diff_semantics"],
            "reason": "content_basis_mismatch",
        }
    return {
        **base,
        "status": "ready",
        "effective_mode": effective,
        "diff_semantics": contract["diff_semantics"],
    }
