#!/usr/bin/env python3
"""Route a situation to a problem-solving shape.

`/which-shape` is advisory. It recommends an operating loop; it never
invokes the skills in that loop.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

SCRIPT_PATH = Path(__file__).resolve()
SKILL_DIR = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[4]
SKILLS_DIR = SCRIPT_PATH.parents[2]  # .claude/skills — to resolve /skill steps
DEFAULT_SHAPES = SKILL_DIR / "shapes.yml"

# A `/skill-name` reference inside a shape's first_next / sequence text.
SKILL_TOKEN_RE = re.compile(r"/([a-z][a-z0-9]+(?:-[a-z0-9]+)*)")

COMMON_DIR = REPO_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

import engineering_home as _eh  # noqa: E402
from skill_use import log_event  # noqa: E402

SCHEMA_VERSION = 1
WORD_RE = re.compile(r"[a-z][a-z0-9_-]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
    "has", "have", "i", "if", "in", "into", "is", "it", "of", "on", "or",
    "that", "the", "this", "to", "was", "we", "will", "with", "you", "use",
    "using", "make", "set", "get", "want", "need", "should", "must", "can",
    "could", "would", "may", "might", "just", "really", "right", "what",
}

DIRECT_CUES = {"typo", "one-line", "oneline", "trivial", "tiny", "narrow", "obvious"}
BUG_CUES = {"bug", "broken", "failing", "failure", "traceback", "exception", "error", "crash"}
PROJECT_INTAKE_CUES = {"adapt", "adapter", "onboard", "onboarding", "unknown", "repo", "project", "codebase"}
INTAKE_FORCE_CUES = {"adapt", "adapter", "onboard", "onboarding", "unknown", "inherited"}
LEGACY_CUES = {"legacy", "messy", "chaotic", "stabilize", "stabilization", "vibe-coded"}
HEALTH_CUES = {"audit", "scan", "health", "sweep"}
REGRESSION_CUES = {"prevent", "guard", "recurring", "repeated", "again", "regression", "keeps", "back"}
DECISION_CUES = {"decision", "decide", "adr", "tradeoff", "choose"}
FEATURE_CUES = {"feature", "add", "endpoint", "capability", "workflow", "new"}
REFACTOR_CUES = {"approved", "proposal", "execute", "refactor", "extract", "split"}


def tokenize(text: str) -> set[str]:
    return {word for word in WORD_RE.findall(text.lower()) if word not in STOPWORDS and len(word) > 1}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def validate_shapes_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported or missing schema_version")
    shapes = payload.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        errors.append("shapes must be a non-empty list")
        return errors

    seen: set[str] = set()
    required = {"id", "title", "summary", "first_next", "sequence", "stop", "cues", "alternatives"}
    for index, shape in enumerate(shapes):
        if not isinstance(shape, dict):
            errors.append(f"shape {index} must be a mapping")
            continue
        sid = shape.get("id")
        if not isinstance(sid, str) or not sid:
            errors.append(f"shape {index} has invalid id")
        elif sid in seen:
            errors.append(f"duplicate shape id: {sid}")
        else:
            seen.add(sid)
        missing = required - set(shape)
        if missing:
            errors.append(f"{sid or index}: missing keys {sorted(missing)}")
        if not isinstance(shape.get("sequence"), list) or not shape.get("sequence"):
            errors.append(f"{sid or index}: sequence must be a non-empty list")
        cues = shape.get("cues")
        if not isinstance(cues, dict):
            errors.append(f"{sid or index}: cues must be a mapping")
            continue
        for key in ("strong", "normal", "negative"):
            values = cues.get(key, [])
            if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
                errors.append(f"{sid or index}: cues.{key} must be a list of strings")
    return errors


def load_shapes(path: Path = DEFAULT_SHAPES) -> list[dict[str, Any]]:
    payload = _load_yaml(path)
    errors = validate_shapes_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return list(payload["shapes"])


def project_context_state(project_root: Path) -> dict[str, Any]:
    project_dir = _eh.project_dir(project_root)
    adapter = project_dir / "adapter.yml"
    profile = project_dir / "profile.yml"
    open_questions = project_dir / "open-questions.md"
    profile_payload: dict[str, Any] = {}
    if profile.is_file():
        try:
            data = yaml.safe_load(profile.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                profile_payload = data
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            profile_payload = {}

    user_approved = bool(profile_payload.get("user_approved"))
    if adapter.is_file() and profile.is_file() and user_approved:
        state = "complete"
    elif adapter.is_file() or profile.is_file() or open_questions.is_file():
        state = "partial"
    else:
        state = "missing"

    return {
        "state": state,
        "adapter_present": adapter.is_file(),
        "profile_present": profile.is_file(),
        "profile_user_approved": user_approved,
        "open_questions_present": open_questions.is_file(),
    }


def _cue_set(shape: dict[str, Any], key: str) -> set[str]:
    return set(shape.get("cues", {}).get(key, []))


def _score_shape(shape: dict[str, Any], task_tokens: set[str], context: dict[str, Any]) -> tuple[int, list[str]]:
    sid = str(shape["id"])
    strong_hits = task_tokens & _cue_set(shape, "strong")
    normal_hits = task_tokens & _cue_set(shape, "normal")
    negative_hits = task_tokens & _cue_set(shape, "negative")
    score = (12 * len(strong_hits)) + (4 * len(normal_hits)) - (10 * len(negative_hits))
    rationale: list[str] = []
    if strong_hits:
        rationale.append(f"strong cues: {', '.join(sorted(strong_hits))}")
    if normal_hits:
        rationale.append(f"supporting cues: {', '.join(sorted(normal_hits))}")
    if negative_hits:
        rationale.append(f"negative cues: {', '.join(sorted(negative_hits))}")

    context_missing = context["state"] == "missing"
    narrow = bool(task_tokens & (DIRECT_CUES | BUG_CUES | DECISION_CUES | REGRESSION_CUES))

    if sid == "project-intake":
        intake_hits = task_tokens & PROJECT_INTAKE_CUES
        forced = bool(task_tokens & INTAKE_FORCE_CUES)
        if context_missing and intake_hits and (forced or not narrow):
            score += 36
            rationale.append("project context is missing and the task asks for repo/project orientation")
        elif context_missing and forced:
            score += 18
            rationale.append("project context is missing")
        else:
            score -= 30
            rationale.append("project intake is not the immediate blocker")
    elif sid == "direct-change" and task_tokens & DIRECT_CUES:
        score += 34
        rationale.append("task looks narrow enough to skip routing overhead")
    elif sid == "bug-fix" and task_tokens & BUG_CUES:
        score += 30
        rationale.append("task starts from a failure symptom")
    elif sid == "legacy-stabilization" and task_tokens & LEGACY_CUES:
        score += 30
        rationale.append("task describes messy or inherited structure")
    elif sid == "health-audit" and task_tokens & HEALTH_CUES:
        score += 30
        rationale.append("task asks for an advisory scan")
    elif sid == "regression-prevention" and task_tokens & REGRESSION_CUES:
        score += 30
        rationale.append("task is about recurrence or guardrails")
        if task_tokens & BUG_CUES:
            score += 8
            rationale.append("failure symptom is paired with recurrence language")
    elif sid == "decision-capture" and task_tokens & DECISION_CUES:
        score += 34
        rationale.append("task names a durable choice")
    elif sid == "feature-shaping" and task_tokens & FEATURE_CUES:
        score += 26
        rationale.append("task asks for new behavior")
    elif sid == "refactor-execution" and task_tokens & REFACTOR_CUES:
        score += 24
        rationale.append("task names an approved refactor/proposal shape")

    if context_missing and sid not in {"project-intake", "direct-change", "bug-fix", "decision-capture"}:
        score -= 4
    return score, rationale or ["fallback shape candidate"]


def _inactive_steps(
    first_next: str, sequence: list[str], project_root: Path, skills_dir: Path
) -> list[dict[str, str]]:
    """Concrete skill steps in a shape that the host has opted out of.

    Scans the recommended loop's text for `/skill-name` references, keeps only
    those that name a real skill (a `<skills_dir>/<name>/SKILL.md` exists) and
    are inactive for this repo, and returns each with its recorded reason.
    Generic placeholders like `/find-*` resolve to no skill and are ignored.
    """
    out: dict[str, str] = {}
    for part in [first_next, *sequence]:
        for name in SKILL_TOKEN_RE.findall(part):
            if name in out:
                continue
            if not (skills_dir / name / "SKILL.md").is_file():
                continue
            if not _eh.is_skill_active(project_root, name):
                out[name] = _eh.inactive_reason(project_root, name) or ""
    return [{"skill": name, "reason": reason} for name, reason in out.items()]


# spec:status-projection-and-presentation::IM-9
def load_status_signals(project_root: Path, status_path: Path | None = None) -> list[str]:
    """Projection-derived rationale extras (ADR 0037: advisory, additive-only).

    Returns [] when status.json is absent, unreadable, or stale (its
    generated_at predates the live context sources route.py reads
    directly) — the live read stays authoritative, and with the file
    absent the route output is byte-identical to the ungrounded run.
    """
    from datetime import datetime, timezone

    path = status_path or project_root / ".engineering" / "local" / "status.json"
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        generated_at = datetime.fromisoformat(doc["generated_at"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return []  # noqa: silent-catch: malformed projection = no grounding, never an error (degrade-silently contract)
    live_sources = [
        _eh.project_dir(project_root) / "adapter.yml",
        _eh.project_dir(project_root) / "profile.yml",
        _eh.project_dir(project_root) / "open-questions.md",
        project_root / ".engineering" / "project-state.json",
    ]
    for source in live_sources:
        if source.is_file():
            mtime = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
            if mtime > generated_at:
                return []  # projection predates a live source — drop silently

    sections = doc.get("sections") or {}
    signals: list[str] = []

    approvals = sections.get("pending_approvals") or {}
    if approvals.get("available") and approvals.get("pending_count"):
        signals.append(
            f"project status: {approvals['pending_count']} proposal(s) pending approval"
        )
    staleness = sections.get("staleness") or {}
    if staleness.get("available") and staleness.get("stale_count"):
        signals.append(
            f"project status: {staleness['stale_count']} artifact(s) stale against their inputs"
        )
    queue = sections.get("queue") or {}
    staged = [i for i in queue.get("items", []) if i.get("status") == "staged"]
    if queue.get("available") and staged:
        signals.append(f"project status: {len(staged)} staged work item(s) in the queue")
    in_flight = sections.get("in_flight") or {}
    if in_flight.get("available") and in_flight.get("active_plans"):
        signals.append(
            f"project status: {len(in_flight['active_plans'])} plan(s) in flight"
        )
    return signals[:3]


def route(
    task: str,
    project_root: Path,
    shapes_path: Path = DEFAULT_SHAPES,
    skills_dir: Path = SKILLS_DIR,
    status_path: Path | None = None,
) -> dict[str, Any]:
    if not task.strip():
        raise ValueError("empty situation description")
    shapes = load_shapes(shapes_path)
    context = project_context_state(project_root)
    task_tokens = tokenize(task)
    ranked: list[tuple[int, dict[str, Any], list[str]]] = []
    for shape in shapes:
        score, rationale = _score_shape(shape, task_tokens, context)
        ranked.append((score, shape, rationale))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))

    score, winner, rationale = ranked[0]
    confidence = "high" if score >= 40 else "medium" if score >= 24 else "low"
    recommendation = {
        "shape": winner["id"],
        "title": winner["title"],
        "summary": winner["summary"],
        "confidence": confidence,
        "score": score,
        "first_next": winner["first_next"],
        "sequence": winner["sequence"],
        "stop": winner["stop"],
        "rationale": rationale + load_status_signals(project_root, status_path),
        "inactive_steps": _inactive_steps(
            winner["first_next"], winner["sequence"], project_root, skills_dir
        ),
    }
    alternatives = [
        {
            "shape": shape["id"],
            "title": shape["title"],
            "score": alt_score,
            "first_next": shape["first_next"],
        }
        for alt_score, shape, _ in ranked[1:4]
    ]
    return {
        "task": task,
        "project_context": context,
        "recommendation": recommendation,
        "alternatives": alternatives,
    }


def render_markdown(result: dict[str, Any]) -> str:
    rec = result["recommendation"]
    ctx = result["project_context"]
    lines = [
        f"Task: {result['task']}",
        f"Project context: {ctx['state']} "
        f"(adapter={ctx['adapter_present']}, profile={ctx['profile_present']}, "
        f"approved={ctx['profile_user_approved']})",
        "",
        f"Recommended shape: {rec['title']} (`{rec['shape']}`)",
        f"Confidence: {rec['confidence']} (score={rec['score']})",
        "",
        "Why:",
    ]
    lines.extend(f"- {line}" for line in rec["rationale"])
    lines.extend(["", f"First next: {rec['first_next']}", "", "Loop:"])
    lines.extend(f"- {step}" for step in rec["sequence"])
    lines.extend(["", f"Stop/reassess: {rec['stop']}"])
    if rec.get("inactive_steps"):
        lines.extend(["", "Inactive here (skipped for this repo):"])
        for step in rec["inactive_steps"]:
            reason = f" — {step['reason']}" if step["reason"] else ""
            lines.append(f"- /{step['skill']}{reason}")
    if result.get("alternatives"):
        lines.extend(["", "Alternatives:"])
        for alt in result["alternatives"]:
            lines.append(f"- `{alt['shape']}` ({alt['title']}), score={alt['score']}")
    return "\n".join(lines) + "\n"


def log_recommendation(
    result: dict[str, Any],
    *,
    elapsed_s: float,
    log_path: Path | None,
    outcome: str,
    human_override: str | None,
) -> None:
    rec = result["recommendation"]
    log_event(
        skill="which-shape",
        target=result["task"],
        artifact=None,
        elapsed_s=elapsed_s,
        outcome=outcome,
        human_override=human_override,
        event_kind="recommendation",
        log_path=log_path,
        shape=rec["shape"],
        confidence=rec["confidence"],
        project_context_state=result["project_context"]["state"],
        recommended_first_skill=rec["first_next"],
    )


def main(argv: list[str] | None = None) -> int:
    start = time.monotonic()
    parser = argparse.ArgumentParser(description="Recommend the right problem-solving shape.")
    parser.add_argument("task", nargs="*", help="Free-text situation or task description.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--shapes", type=Path, default=DEFAULT_SHAPES)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--status", type=Path, default=None,
        help="status.json override (default: <project-root>/.engineering/local/status.json; "
             "absent file = ungrounded run, byte-identical output).",
    )
    parser.add_argument("--validate", action="store_true", help="Validate shapes.yml and exit.")
    parser.add_argument("--skip-log", action="store_true")
    parser.add_argument("--log", type=Path, default=None, help="Override skill-use log path.")
    parser.add_argument("--outcome", choices=["useful", "partial", "noop", "overridden"], default="useful")
    parser.add_argument("--human-override", default=None)
    args = parser.parse_args(argv)

    try:
        if args.validate:
            load_shapes(args.shapes)
            print("shapes OK")
            return 0
        task = " ".join(args.task).strip()
        result = route(task, args.project_root.resolve(), args.shapes, status_path=args.status)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not args.skip_log:
        log_recommendation(
            result,
            elapsed_s=time.monotonic() - start,
            log_path=args.log,
            outcome=args.outcome,
            human_override=args.human_override,
        )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_markdown(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
