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


def adapter_kind(contract: dict[str, Any]) -> str:
    """Name the one shared adapter implied by reviewed diff semantics."""
    return {
        "filter-findings": "line-filter",
        "seed-analysis": "path-seed",
        "trigger-analysis": "project-trigger",
        "not-applicable": "scope-neutral",
    }[contract["diff_semantics"]]


def recommendation_scan(
    request,
    contract: dict[str, Any] | None,
    *,
    supported_modes_field: str = "current_modes",
    allow_compatible_widening: bool = True,
) -> dict[str, Any]:
    """Return an honest effective mode for one recommended scanner."""
    base = {
        "requested_mode": request.requested_mode,
        "selector": request.selector,
    }
    if contract is None:
        return {
            **base,
            "status": "unavailable",
            "adapter": None,
            "effective_mode": None,
            "diff_semantics": None,
            "reason": "scope_contract_unavailable",
        }
    if supported_modes_field not in {"current_modes", "target_modes"}:
        raise ValueError("supported modes field must be current_modes or target_modes")
    supported = contract[supported_modes_field]
    default_field = (
        "current_default_mode"
        if supported_modes_field == "current_modes"
        else "target_default_mode"
    )
    adapter = adapter_kind(contract)
    if request.requested_mode == "auto":
        selector_default = {
            "paths": "paths",
            "project": "project",
        }.get(request.selector["kind"], "changed-files")
        effective = (
            selector_default
            if selector_default in supported
            else contract[default_field]
        )
    else:
        effective = request.requested_mode
    if (
        effective == "changed-files"
        and effective in supported
        and contract["diff_semantics"] == "trigger-analysis"
    ):
        return {
            **base,
            "status": "widened",
            "adapter": adapter,
            "effective_mode": "project",
            "diff_semantics": contract["diff_semantics"],
            "reason": "project_analysis_required",
        }
    if effective not in supported:
        if not allow_compatible_widening:
            return {
                **base,
                "status": "unsupported",
                "adapter": adapter,
                "effective_mode": None,
                "diff_semantics": contract["diff_semantics"],
                "reason": "scope_mode_not_supported",
                "supported_modes": supported,
            }
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
        elif effective == "changed-files":
            if contract["diff_semantics"] == "trigger-analysis" and "project" in supported:
                compatible = "project"
                reason = "project_analysis_required"
            elif "paths" in supported:
                compatible = "paths"
                reason = "complete_selected_paths_equivalent"
        if compatible is not None:
            return {
                **base,
                "status": "widened" if effective == "diff-lines" else "adapted",
                "adapter": adapter,
                "effective_mode": compatible,
                "diff_semantics": contract["diff_semantics"],
                "reason": reason,
            }
        return {
            **base,
            "status": "unsupported",
            "adapter": adapter,
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
                "adapter": adapter,
                "effective_mode": None,
                "diff_semantics": contract["diff_semantics"],
                "reason": "content_basis_mismatch",
            }
        return {
            **base,
            "status": "degraded",
            "adapter": adapter,
            "effective_mode": "changed-files",
            "diff_semantics": contract["diff_semantics"],
            "reason": "content_basis_mismatch",
        }
    return {
        **base,
        "status": "ready",
        "adapter": adapter,
        "effective_mode": effective,
        "diff_semantics": contract["diff_semantics"],
    }
