#!/usr/bin/env python3
"""Shared library for the idea ledger (Tier 1) and pattern library (Tier 2).

Used by every idea-tracking skill:
    track-idea               (write: intake, event, lesson)
    find-orphaned-ideas      (read: projection + stale/harvest/dropout)
    query-patterns           (read: pattern frontmatter + body)
    extract-existing-ideas   (write: bulk intake from filesystem)
    audit-ideas              (read: lineage reconciliation, supersession chains)
    promote-idea-to-pattern  (read ledger, write pattern Markdown)
    mature-existing-ideas    (write: pattern research log + ledger markers)
    brainstorm-ideas         (write: bulk proposed intakes from research)

The library is JSONL-aware, schema-validating, and side-effect-free
unless an explicit write function is called.

Schema: .claude/docs/idea-ledger.md
ADR:    ai-docs/decisions/0013-idea-tracking-system.md
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATES = {"proposed", "in-flight", "stalled", "done"}
VALID_OUTCOMES = {"adopted", "rejected", "deferred", "harvested", "superseded"}
VALID_MARKERS = {"underdeveloped", "needs-research", "has-more-potential"}
VALID_QUALIFIERS = {"single-constraint-set", "validated-across-N", "broadly-applicable"}
VALID_RECORD_KINDS = {"intake", "event", "lesson"}
VALID_EVENT_KINDS = {"transition", "marker", "edge", "adoption", "dev-note", "note"}
DEFAULT_STALE_DAYS = 14


def utc_now_iso() -> str:
    """Current UTC time in canonical ledger ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(ts: str) -> datetime:
    """Parse a canonical ledger ISO timestamp into an aware datetime."""
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def load_ledger(path: Path) -> list[dict]:
    """Load every record from a JSONL ledger. Empty/missing → []."""
    if not path.exists():
        return []
    records: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return records


def validate_record(rec: dict) -> list[str]:
    """Return list of validation errors; empty list = valid."""
    errors: list[str] = []
    kind = rec.get("record_kind")
    if kind not in VALID_RECORD_KINDS:
        return [f"invalid record_kind: {kind!r}"]
    if not rec.get("id"):
        errors.append("missing id")

    if kind == "intake":
        if rec.get("state") not in VALID_STATES:
            errors.append(f"invalid state: {rec.get('state')!r}")
        for m in rec.get("quality_markers", []):
            if m not in VALID_MARKERS:
                errors.append(f"unknown marker: {m!r}")
        for field in ("title", "created_at", "origin", "subsystem_kind", "summary"):
            if not rec.get(field):
                errors.append(f"intake missing required field: {field}")
        outcome = rec.get("outcome")
        if outcome is not None and outcome not in VALID_OUTCOMES:
            errors.append(f"invalid outcome: {outcome!r}")
    elif kind == "event":
        if rec.get("event_kind") not in VALID_EVENT_KINDS:
            errors.append(f"invalid event_kind: {rec.get('event_kind')!r}")
        if not rec.get("event_at"):
            errors.append("event missing event_at")
        if rec.get("event_kind") == "transition":
            if rec.get("to_state") not in VALID_STATES:
                errors.append(f"transition bad to_state: {rec.get('to_state')!r}")
            if rec.get("to_state") == "done":
                if rec.get("outcome") not in VALID_OUTCOMES:
                    errors.append(f"done transition needs outcome; got {rec.get('outcome')!r}")
        for m in list(rec.get("markers_added", [])) + list(rec.get("markers_removed", [])):
            if m not in VALID_MARKERS:
                errors.append(f"unknown marker in event: {m!r}")
    elif kind == "lesson":
        for field in ("lesson_at", "lesson_title", "lesson_body"):
            if not rec.get(field):
                errors.append(f"lesson missing required field: {field}")
    return errors


def project(records: list[dict], idea_id: str) -> dict | None:
    """Project an idea's current state by overlaying ordered events on its intake.

    Returns the projected dict, or None if no intake exists for idea_id.
    Projection rules are in .claude/docs/idea-ledger.md.
    """
    intake = next(
        (r for r in records if r.get("record_kind") == "intake" and r.get("id") == idea_id),
        None,
    )
    if intake is None:
        return None

    proj: dict[str, Any] = {
        "id": idea_id,
        "title": intake.get("title", ""),
        "created_at": intake.get("created_at", ""),
        "origin": intake.get("origin", ""),
        "subsystem_kind": intake.get("subsystem_kind", ""),
        "state": intake.get("state", "proposed"),
        "outcome": intake.get("outcome"),
        "quality_markers": list(intake.get("quality_markers", [])),
        "feeds_into": list(intake.get("feeds_into", [])),
        "composes_with": list(intake.get("composes_with", [])),
        "lineage_parents": list(intake.get("lineage_parents", [])),
        "lineage_children": list(intake.get("lineage_children", [])),
        "superseded_by": intake.get("superseded_by"),
        "adoption_count": 0,
        "adoption_evidence": [],
        "last_event_at": intake.get("created_at", ""),
        "tags": list(intake.get("tags", [])),
        "summary": intake.get("summary", ""),
        "hypothesis": intake.get("hypothesis"),
        "lessons": [],
    }

    events = sorted(
        (r for r in records if r.get("record_kind") == "event" and r.get("id") == idea_id),
        key=lambda r: r.get("event_at", ""),
    )
    for ev in events:
        ev_at = ev.get("event_at", "")
        if ev_at > proj["last_event_at"]:
            proj["last_event_at"] = ev_at
        if ev.get("to_state"):
            proj["state"] = ev["to_state"]
        if ev.get("to_state") == "done" and ev.get("outcome"):
            proj["outcome"] = ev["outcome"]
        for m in ev.get("markers_added", []) or []:
            if m not in proj["quality_markers"]:
                proj["quality_markers"].append(m)
        for m in ev.get("markers_removed", []) or []:
            if m in proj["quality_markers"]:
                proj["quality_markers"].remove(m)
        edges = ev.get("edges_added") or {}
        for field in ("feeds_into", "composes_with", "lineage_parents"):
            for v in edges.get(field, []) or []:
                if v not in proj[field]:
                    proj[field].append(v)
        if ev.get("adoption_evidence"):
            proj["adoption_count"] += 1
            proj["adoption_evidence"].append(ev["adoption_evidence"])
        if ev.get("superseded_by"):
            proj["superseded_by"] = ev["superseded_by"]

    proj["lessons"] = sorted(
        (r for r in records if r.get("record_kind") == "lesson" and r.get("id") == idea_id),
        key=lambda r: r.get("lesson_at", ""),
    )
    return proj


def project_all(records: list[dict]) -> dict[str, dict]:
    """Project every idea in the ledger."""
    intake_ids = sorted({r["id"] for r in records if r.get("record_kind") == "intake"})
    return {i: project(records, i) for i in intake_ids}  # type: ignore[misc]


def find_stalled(
    records: list[dict],
    now: str | None = None,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> list[str]:
    """Return ids of in-flight ideas whose last_event_at is older than stale_days.

    `now` may be a canonical-ISO string for deterministic tests; defaults to
    current UTC. Returns sorted ids.
    """
    now_dt = parse_iso(now) if now else datetime.now(timezone.utc)
    cutoff = now_dt.timestamp() - stale_days * 86400
    out: list[str] = []
    for idea_id, proj in project_all(records).items():
        if proj["state"] != "in-flight":
            continue
        try:
            last_ts = parse_iso(proj["last_event_at"]).timestamp()
        except (ValueError, TypeError):
            continue
        if last_ts < cutoff:
            out.append(idea_id)
    return sorted(out)


def find_harvest_opportunities(records: list[dict]) -> list[str]:
    """Return ids of ideas carrying has-more-potential that are not in-flight."""
    out: list[str] = []
    for idea_id, proj in project_all(records).items():
        if "has-more-potential" in proj["quality_markers"] and proj["state"] != "in-flight":
            out.append(idea_id)
    return sorted(out)


def _norm_token(s: str) -> str:
    """Normalize a string to a slug-like comparison token."""
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def find_plan_dropouts(records: list[dict], plan_items: list[str]) -> list[str]:
    """Return plan items that have no matching intake (by id or title token-equality).

    Match is intentionally loose: an item like "Item A (extraction)" matches an
    intake titled "Item A" or id "item-a". This is heuristic by design; the
    skill layer can use richer matching if needed.
    """
    intakes = [r for r in records if r.get("record_kind") == "intake"]
    intake_ids = {r["id"] for r in intakes}
    intake_title_tokens = {_norm_token(r.get("title") or "") for r in intakes}

    dropouts: list[str] = []
    for item in plan_items:
        tok = _norm_token(item)
        if tok in intake_ids or tok in intake_title_tokens:
            continue
        if any(tok.startswith(other) or other.startswith(tok) for other in intake_ids if other):
            continue
        dropouts.append(item)
    return dropouts


def promotion_eligible(records: list[dict]) -> list[dict]:
    """Return sorted list of promotion-eligible ideas with proposed qualifier.

    Eligibility (per pattern-library.md):
      - adoption_count >= 1
      - state == done with outcome in {adopted, harvested}, OR state == in-flight
    """
    out: list[dict] = []
    for idea_id, proj in project_all(records).items():
        if proj["adoption_count"] < 1:
            continue
        if proj["state"] == "done" and proj["outcome"] not in {"adopted", "harvested"}:
            continue
        if proj["state"] not in {"in-flight", "done"}:
            continue
        if proj["adoption_count"] >= 4:
            qualifier = "broadly-applicable"
        elif proj["adoption_count"] >= 2:
            qualifier = "validated-across-N"
        else:
            qualifier = "single-constraint-set"
        out.append({
            "id": idea_id,
            "title": proj["title"],
            "qualifier": qualifier,
            "adoption_evidence": list(proj["adoption_evidence"]),
            "adoption_count": proj["adoption_count"],
        })
    out.sort(key=lambda r: r["id"])
    return out


def supersession_chain(records: list[dict], idea_id: str) -> list[str]:
    """Walk superseded_by forward from idea_id. Detects cycles."""
    projs = project_all(records)
    chain = [idea_id]
    current = idea_id
    while current in projs and projs[current].get("superseded_by"):
        nxt = projs[current]["superseded_by"]
        if nxt in chain:
            chain.append(f"!CYCLE:{nxt}")
            return chain
        chain.append(nxt)
        current = nxt
    return chain


def reconcile_lineage(records: list[dict]) -> dict[str, list[str]]:
    """Compute lineage_parents → lineage_children back-pointers.

    Returns {parent_id: sorted [child_ids]} for each parent referenced by a
    child's lineage_parents. The result is the *correct* back-pointer map;
    audit-ideas compares this to stored lineage_children to flag drift.
    """
    children: dict[str, list[str]] = {}
    for idea_id, proj in project_all(records).items():
        for parent in proj["lineage_parents"]:
            children.setdefault(parent, []).append(idea_id)
    return {k: sorted(v) for k, v in children.items()}


def append_record(path: Path, rec: dict) -> None:
    """Append a single record to the JSONL ledger after validation."""
    errors = validate_record(rec)
    if errors:
        raise ValueError(f"invalid record: {'; '.join(errors)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


_BACKLOG_KIND_MAP = {
    "bugs": "bug",
    "bug": "bug",
    "extraction quality": "extraction",
    "extraction": "extraction",
    "refactor": "refactor",
    "refactors": "refactor",
    "ux polish": "ux",
    "ux": "ux",
    "test gaps": "test",
    "tests": "test",
    "deferred": "deferred",
    "deferred projects": "deferred",
    "feature": "feature",
    "feature work": "feature",
    "features": "feature",
    "skill": "skill",
    "skills": "skill",
    "ui": "UI",
    "doc": "doc",
    "docs": "doc",
    "documentation": "doc",
}


def _slugify(text: str, max_len: int = 60) -> str:
    """Lowercase alnum-runs joined with single dashes, capped at max_len."""
    s = "".join(c.lower() if c.isalnum() else "-" for c in text)
    while "--" in s:
        s = s.replace("--", "-")
    s = s.strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s


def _map_backlog_heading(heading: str) -> str:
    """Resolve a ## heading to a subsystem_kind.

    Exact match wins; otherwise the heading's first word is used as a
    fallback so suffixes like 'Bugs / needs fix soon' or 'Refactor later'
    still resolve. Unknown headings default to 'general'.
    """
    h = heading.strip().lower().rstrip(":").strip()
    if h in _BACKLOG_KIND_MAP:
        return _BACKLOG_KIND_MAP[h]
    parts = h.split()
    if parts and parts[0] in _BACKLOG_KIND_MAP:
        return _BACKLOG_KIND_MAP[parts[0]]
    return "general"


def _extract_backlog_md(path: Path, root: Path) -> list[dict]:
    """Bullet items under ## headings → candidate intakes.

    Bullets appearing before any ## heading are treated as preamble
    (file conventions, file header) and skipped.
    """
    out: list[dict] = []
    rel = str(path.relative_to(root))
    current_kind = "general"
    seen_heading = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s.startswith("## ") and not s.startswith("### "):
            seen_heading = True
            current_kind = _map_backlog_heading(s[3:])
            continue
        if not seen_heading:
            continue
        if s.startswith("- ") and len(s) > 2:
            bullet = s[2:].strip().replace("`", "")
            if not bullet:
                continue
            title = _clean_bullet_title(bullet)
            out.append({
                "slug": _slugify(title),
                "title": title,
                "subsystem_kind": current_kind,
                "summary": bullet,
                "origin": "backlog-extract",
                "quality_markers": ["underdeveloped"],
                "tags": [current_kind, "backlog"],
                "source_path": rel,
                "source_kind": "backlog",
            })
    return out


def _clean_bullet_title(bullet: str, max_len: int = 80) -> str:
    """Derive a short title from a bullet that may carry its own explanation.

    Resolution order:
      1. `**bold**` prefix → the bold span is the title.
      2. First em-dash / sentence boundary → text up to that boundary.
      3. Bullet itself, capped at max_len characters.
    Backticks are stripped.
    """
    text = bullet.strip().replace("`", "")
    if text.startswith("**"):
        end = text.find("**", 2)
        if end > 2:
            return text[2:end].strip().rstrip(" :.,—-")
    for sep in (" — ", "—", ". ", "? ", "! "):
        idx = text.find(sep)
        if 0 < idx <= max_len + 20:
            return text[:idx].strip()
    return text[:max_len].rstrip()


def _extract_lessons_md(path: Path, root: Path) -> list[dict]:
    """## heading + body OR ## heading + - bullets → harvest candidates.

    Two shapes are common:
      (a) one lesson per ## heading with prose body underneath
      (b) ## heading as a category with `- ...` bullets underneath, each
          bullet being a separate lesson

    The parser inspects each section: if any `- ` bullets exist under
    a heading, treat each bullet as a candidate. Otherwise treat the
    heading + body as a single candidate.
    """
    out: list[dict] = []
    rel = str(path.relative_to(root))

    sections: list[dict] = []
    cur: dict | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s.startswith("## ") and not s.startswith("### "):
            if cur is not None:
                sections.append(cur)
            cur = {"title": s[3:].strip(), "bullets": [], "body_lines": []}
            continue
        if cur is None:
            continue
        if s.startswith("- ") and len(s) > 2:
            cur["bullets"].append(s[2:].strip())
        else:
            cur["body_lines"].append(raw.rstrip())
    if cur is not None:
        sections.append(cur)

    for sec in sections:
        if sec["bullets"]:
            for bullet in sec["bullets"]:
                cleaned = bullet.replace("`", "")
                title = _clean_bullet_title(cleaned)
                if not title:
                    continue
                out.append({
                    "slug": _slugify(title),
                    "title": title,
                    "subsystem_kind": "lesson",
                    "summary": cleaned,
                    "origin": "lesson-extract",
                    "quality_markers": ["has-more-potential"],
                    "tags": ["lesson"],
                    "source_path": rel,
                    "source_kind": "lesson",
                })
        else:
            body = "\n".join(sec["body_lines"]).strip()
            out.append({
                "slug": _slugify(sec["title"]),
                "title": sec["title"],
                "subsystem_kind": "lesson",
                "summary": body or sec["title"],
                "origin": "lesson-extract",
                "quality_markers": ["has-more-potential"],
                "tags": ["lesson"],
                "source_path": rel,
                "source_kind": "lesson",
            })
    return out


def extract_candidates(root: Path | str) -> list[dict]:
    """Walk a directory for prose surfaces and return candidate intake dicts.

    Recognised sources:
      <root>/BACKLOG.md   bullet items under ## headings → backlog candidates
      <root>/lessons.md   ## heading + body → harvest candidates

    Each returned candidate is shaped for brainstorm-ideas/scripts/brainstorm.py
    (slug / title / subsystem_kind / summary / origin / quality_markers / tags)
    plus two extra fields source_path / source_kind that the skill report uses.

    Order is deterministic: (source_kind, source_path, title).
    """
    root_p = Path(root)
    candidates: list[dict] = []
    backlog = root_p / "BACKLOG.md"
    if backlog.exists():
        candidates.extend(_extract_backlog_md(backlog, root_p))
    lessons = root_p / "lessons.md"
    if lessons.exists():
        candidates.extend(_extract_lessons_md(lessons, root_p))
    candidates.sort(key=lambda c: (c.get("source_kind", ""), c.get("source_path", ""), c["title"]))
    return candidates


def self_test() -> None:
    """Quick smoke test exercising every primitive."""
    intake = {
        "record_kind": "intake",
        "id": "test-idea",
        "title": "Test idea",
        "created_at": "2026-01-01T00:00:00Z",
        "origin": "test",
        "subsystem_kind": "test",
        "state": "proposed",
        "summary": "A test.",
    }
    assert validate_record(intake) == [], "valid intake should pass"
    assert validate_record({"record_kind": "intake", "id": "x"}), "missing fields should fail"

    transition = {
        "record_kind": "event",
        "id": "test-idea",
        "event_at": "2026-01-02T00:00:00Z",
        "event_kind": "transition",
        "from_state": "proposed",
        "to_state": "in-flight",
    }
    assert validate_record(transition) == []

    adoption = {
        "record_kind": "event",
        "id": "test-idea",
        "event_at": "2026-01-03T00:00:00Z",
        "event_kind": "adoption",
        "adoption_evidence": "app/test.py",
        "summary": "Adopted.",
    }
    records = [intake, transition, adoption]
    proj = project(records, "test-idea")
    assert proj is not None
    assert proj["state"] == "in-flight"
    assert proj["adoption_count"] == 1

    elig = promotion_eligible(records)
    assert len(elig) == 1
    assert elig[0]["qualifier"] == "single-constraint-set"

    stalled = find_stalled(records, now="2026-06-01T00:00:00Z", stale_days=14)
    assert stalled == ["test-idea"], f"expected stale; got {stalled}"

    print("ideas_lib self-test OK")


if __name__ == "__main__":
    self_test()
