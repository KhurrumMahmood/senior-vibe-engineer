"""status.json schema contract (ADR 0037).

Single source for the closed vocabularies the projection producer
(`scripts/status.py`), the lens renderer, the router grounding read, and
the tests all share. The schema is versioned: removing or renaming a
section or field requires a SCHEMA_VERSION bump; adding an optional
section does not. Consumers must tolerate absent sections and unknown
additional sections.

Source decision: `core:status-projection-schema` (ADR 0037) — provenance,
not required reading; behavior is fully specified here.
"""
# spec:status-projection-and-presentation::IM-1
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1

# Closed section vocabulary (ADR 0037 §2). `goals` is reserved in v1 for
# the goal-layer work: emitted absent until a goal artifact convention
# exists, so populating it later needs no version bump.
SECTIONS = (
    "lifecycle",
    "structural_health",
    "pending_approvals",
    "in_flight",
    "staleness",
    "queue",
    "goals",
)

# Pending-approval item statuses (AR-11 honesty: closure is reliably
# detectable for only two chains; the rest stay pending until a human
# drops a dismissal marker in the proposal directory).
APPROVAL_PENDING = "pending"
APPROVAL_CLOSED = "closed"
APPROVAL_DISMISSED = "dismissed"
APPROVAL_STATUSES = (APPROVAL_PENDING, APPROVAL_CLOSED, APPROVAL_DISMISSED)

# A human dismisses a proposal by creating one of these files inside the
# proposal directory (content optional — a one-line reason is welcome).
DISMISSAL_MARKERS = ("DISMISSED", "dismissed.md")

# Proposal-emitting chains the pending-approvals section watches.
# `closure`:
#   none           — no execution artifact is reliably detectable; the item
#                    reports pending until explicitly dismissed.
#   installed_lint — closed when every `scripts/lint/<rule>.py` path named
#                    in proposal.md exists on disk (prevent-regression).
#   spec_link      — closed when an `ai-docs/specs/<id>.md` path named in
#                    proposal.md exists on disk (propose-boundary).
PROPOSAL_CHAINS: tuple[dict[str, str], ...] = (
    {"skill": "unify-shadows", "closure": "none"},
    {"skill": "extract-enum", "closure": "none"},
    {"skill": "extract-state-type", "closure": "none"},
    {"skill": "introduce-fk", "closure": "none"},
    {"skill": "extract-workflow-registry", "closure": "none"},
    {"skill": "extract-cotton-primitive", "closure": "none"},
    {"skill": "propose-folder-reorganization", "closure": "none"},
    {"skill": "propose-boundary", "closure": "spec_link"},
    {"skill": "prevent-regression", "closure": "installed_lint"},
)

# Staleness states for scope.json-tracked artifacts.
FRESH = "fresh"
STALE = "stale"
STALENESS_STATES = (FRESH, STALE)


def absent(reason: str) -> dict[str, Any]:
    """The uniform absent-marker every degraded section emits."""
    return {"available": False, "reason": reason}


def is_absent(section: dict[str, Any]) -> bool:
    return not section.get("available", False)


def validate(doc: Any) -> list[str]:
    """Validate a status.json document; returns a list of errors (empty = valid).

    Checks the envelope and the per-section availability contract only —
    section-internal fields are additive by design and not pinned here.
    """
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["document is not a JSON object"]
    if doc.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION}, got {doc.get('schema_version')!r}"
        )
    if not isinstance(doc.get("generated_at"), str) or not doc.get("generated_at"):
        errors.append("generated_at must be a non-empty ISO-8601 string")
    if not isinstance(doc.get("root"), str) or not doc.get("root"):
        errors.append("root must be a non-empty string")
    sections = doc.get("sections")
    if not isinstance(sections, dict):
        return errors + ["sections must be an object"]
    for name in SECTIONS:
        if name not in sections:
            errors.append(f"missing section: {name}")
            continue
        sec = sections[name]
        if not isinstance(sec, dict):
            errors.append(f"section {name} must be an object")
            continue
        if not isinstance(sec.get("available"), bool):
            errors.append(f"section {name} missing boolean 'available'")
        elif not sec["available"] and not sec.get("reason"):
            errors.append(f"absent section {name} missing 'reason'")
    return errors
