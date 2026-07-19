#!/usr/bin/env python3
"""Route a situation to a problem-solving shape.

`/which-shape` is advisory. It recommends an operating loop; it never
invokes the skills in that loop.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shlex
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
SKILL_DIR = SCRIPT_PATH.parents[1]
SKILLS_DIR = SKILL_DIR.parent
DEFAULT_SHAPES = SKILL_DIR / "shapes.json"
DEFAULT_SOURCE = "https://github.com/KhurrumMahmood/senior-vibe-engineer"  # host-ref-allow: public distribution repository
DEFAULT_CLI_VERSION = "1.5.19"

# A `/skill-name` reference inside a shape's first_next / sequence text.
SKILL_TOKEN_RE = re.compile(r"/([a-z][a-z0-9]+(?:-[a-z0-9]+)*)")

SCHEMA_VERSION = 1
WORD_RE = re.compile(r"[a-z][a-z0-9_-]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
    "has", "have", "i", "if", "in", "into", "is", "it", "of", "on", "or",
    "that", "the", "this", "to", "was", "we", "will", "with", "you", "use",
    "using", "make", "set", "get", "want", "need", "should", "must", "can",
    "could", "would", "may", "might", "just", "really", "right", "what",
}

# Boost weights live in shapes.json as data (frame review F4b / Path A);
# there is no in-code per-shape table left. A shape's `boost:` block is
# either the simple form {cues, weight, rationale} or the rules form
# {mode, rules}, where each rule = {conditions, weight, rationale} and
# conditions are AND-ed, [] meaning "always". The condition vocabulary is
# deliberately tiny and schema-validated — not an expression language.
BOOST_MODES = {"first-match", "additive"}
BOOST_CONDITION_TYPES = {"cue-hit", "context-missing", "not-narrow"}
_SIMPLE_BOOST_KEYS = {"cues", "weight", "rationale", "narrow_signal"}
_RULES_BOOST_KEYS = {"mode", "rules", "narrow_signal"}
_RULE_KEYS = {"conditions", "weight", "rationale"}


def tokenize(text: str) -> set[str]:
    return {word for word in WORD_RE.findall(text.lower()) if word not in STOPWORDS and len(word) > 1}


def _load_registry(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _read_manifest(root: Path) -> dict[str, Any]:
    path = root / ".engineering" / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _skill_activation(root: Path) -> dict[str, Any]:
    block = _read_manifest(root).get("skills")
    if not isinstance(block, dict):
        block = {}
    default = block.get("default")
    if default not in {"active", "inactive"}:
        default = "active"

    def reasons(value: Any) -> dict[str, str]:
        if isinstance(value, dict):
            return {str(key): str(reason) for key, reason in value.items()}
        if isinstance(value, list):
            return {str(item): "" for item in value}
        return {}

    return {
        "default": default,
        "active": reasons(block.get("active")),
        "inactive": reasons(block.get("inactive")),
    }


def _is_skill_active(root: Path, name: str) -> bool:
    activation = _skill_activation(root)
    if activation["default"] == "inactive":
        return name in activation["active"]
    return name not in activation["inactive"]


def _inactive_reason(root: Path, name: str) -> str | None:
    if _is_skill_active(root, name):
        return None
    return _skill_activation(root)["inactive"].get(name) or None


def _append_event(path: Path, event: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except (OSError, TypeError, ValueError):
        return


def _is_cue_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def _is_weight(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _simple_boost_ids(shapes: list[Any]) -> set[str]:
    """Shape ids whose boost is the simple {cues, weight, rationale} form."""
    out: set[str] = set()
    for shape in shapes:
        if not isinstance(shape, dict):
            continue
        boost = shape.get("boost")
        if isinstance(boost, dict) and "cues" in boost and "rules" not in boost and "mode" not in boost:
            out.add(str(shape.get("id")))
    return out


def _validate_condition(label: str, cond: Any, simple_ids: set[str], errors: list[str]) -> None:
    if not isinstance(cond, dict):
        errors.append(f"{label} must be a mapping")
        return
    ctype = cond.get("type")
    if ctype not in BOOST_CONDITION_TYPES:
        errors.append(f"{label}: unknown condition type {ctype!r} (allowed: {sorted(BOOST_CONDITION_TYPES)})")
        return
    if ctype == "cue-hit":
        if ("cues" in cond) == ("cues_from" in cond):
            errors.append(f"{label}: cue-hit needs exactly one of cues / cues_from")
        if "cues" in cond and not _is_cue_list(cond["cues"]):
            errors.append(f"{label}: cues must be a non-empty list of strings")
        if "cues_from" in cond and cond["cues_from"] not in simple_ids:
            errors.append(f"{label}: cues_from must name a shape with a simple cues/weight boost")
        extra = set(cond) - {"type", "cues", "cues_from"}
    else:
        extra = set(cond) - {"type"}
    if extra:
        errors.append(f"{label}: unexpected keys {sorted(extra)}")


def _validate_boost(sid: str, boost: Any, simple_ids: set[str], errors: list[str]) -> None:
    label = f"{sid}: boost"
    if not isinstance(boost, dict):
        errors.append(f"{label} must be a mapping (use {{}} to declare no boost)")
        return
    if not boost:
        return  # explicit opt-out: the shape deliberately has no boost
    if "narrow_signal" in boost and not isinstance(boost["narrow_signal"], bool):
        errors.append(f"{label}.narrow_signal must be a boolean")
    if "rules" in boost or "mode" in boost:
        extra = set(boost) - _RULES_BOOST_KEYS
        if extra:
            errors.append(f"{label}: unexpected keys {sorted(extra)}")
        if boost.get("mode") not in BOOST_MODES:
            errors.append(f"{label}.mode must be one of {sorted(BOOST_MODES)}")
        rules = boost.get("rules")
        if not isinstance(rules, list) or not rules:
            errors.append(f"{label}.rules must be a non-empty list")
            return
        for rindex, rule in enumerate(rules):
            rlabel = f"{label}.rules[{rindex}]"
            if not isinstance(rule, dict):
                errors.append(f"{rlabel} must be a mapping")
                continue
            extra = set(rule) - _RULE_KEYS
            if extra:
                errors.append(f"{rlabel}: unexpected keys {sorted(extra)}")
            if not _is_weight(rule.get("weight")):
                errors.append(f"{rlabel}.weight must be an integer")
            if not isinstance(rule.get("rationale"), str) or not rule.get("rationale"):
                errors.append(f"{rlabel}.rationale must be a non-empty string")
            conditions = rule.get("conditions")
            if not isinstance(conditions, list):
                errors.append(f"{rlabel}.conditions must be a list ([] means always)")
                continue
            for cindex, cond in enumerate(conditions):
                _validate_condition(f"{rlabel}.conditions[{cindex}]", cond, simple_ids, errors)
    else:
        extra = set(boost) - _SIMPLE_BOOST_KEYS
        if extra:
            errors.append(f"{label}: unexpected keys {sorted(extra)}")
        if not _is_cue_list(boost.get("cues")):
            errors.append(f"{label}.cues must be a non-empty list of strings")
        if not _is_weight(boost.get("weight")):
            errors.append(f"{label}.weight must be an integer")
        if not isinstance(boost.get("rationale"), str) or not boost.get("rationale"):
            errors.append(f"{label}.rationale must be a non-empty string")


def validate_shapes_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported or missing schema_version")
    shapes = payload.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        errors.append("shapes must be a non-empty list")
        return errors

    simple_ids = _simple_boost_ids(shapes)
    seen: set[str] = set()
    required = {"id", "title", "summary", "first_next", "sequence", "stop", "cues", "alternatives", "boost"}
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
        if "boost" in shape:
            _validate_boost(str(sid or index), shape["boost"], simple_ids, errors)
        if "context_exempt" in shape and not isinstance(shape["context_exempt"], bool):
            errors.append(f"{sid or index}: context_exempt must be a boolean")
        install_with = shape.get("install_with", [])
        if (
            not isinstance(install_with, list)
            or any(not isinstance(item, str) or not item for item in install_with)
            or len(install_with) != len(set(install_with))
        ):
            errors.append(
                f"{sid or index}: install_with must be a unique list of non-empty skill names"
            )
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
    payload = _load_registry(path)
    errors = validate_shapes_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return list(payload["shapes"])


def project_context_state(project_root: Path) -> dict[str, Any]:
    project_dir = project_root / ".engineering" / "project"
    adapter = project_dir / "adapter.yml"
    profile = project_dir / "profile.yml"
    open_questions = project_dir / "open-questions.md"
    user_approved = False
    if profile.is_file():
        try:
            profile_text = profile.read_text(encoding="utf-8")
            user_approved = bool(
                re.search(
                    r"(?im)^\s*user_approved\s*:\s*(true|yes|on)\s*(?:#.*)?$",
                    profile_text,
                )
            )
        except (OSError, UnicodeDecodeError):
            user_approved = False
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


def _boost_block(shape: dict[str, Any]) -> dict[str, Any]:
    boost = shape.get("boost")
    return boost if isinstance(boost, dict) else {}


def _boost_rules(shape: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Normalize a boost block to (mode, rules); the simple form is sugar
    for one additive cue-hit rule."""
    boost = _boost_block(shape)
    if not boost:
        return "additive", []
    if "rules" in boost:
        return str(boost["mode"]), list(boost["rules"])
    return "additive", [{
        "conditions": [{"type": "cue-hit", "cues": boost["cues"]}],
        "weight": boost["weight"],
        "rationale": boost["rationale"],
    }]


def _boost_cue_vocabulary(shape: dict[str, Any]) -> set[str]:
    """The literal boost-trigger tokens a shape declares (cues_from
    references resolve to the other shape and are excluded here)."""
    boost = _boost_block(shape)
    if "cues" in boost:
        return set(boost["cues"])
    vocab: set[str] = set()
    for rule in boost.get("rules", []):
        for cond in rule.get("conditions", []):
            if cond.get("type") == "cue-hit" and "cues" in cond:
                vocab |= set(cond["cues"])
    return vocab


def narrow_cue_union(shapes: list[dict[str, Any]]) -> set[str]:
    """Tokens marking a task as narrow: the boost vocabularies of shapes
    flagged `narrow_signal: true` (read by the not-narrow condition)."""
    out: set[str] = set()
    for shape in shapes:
        if _boost_block(shape).get("narrow_signal"):
            out |= _boost_cue_vocabulary(shape)
    return out


def _condition_holds(
    cond: dict[str, Any],
    task_tokens: set[str],
    context_missing: bool,
    narrow: bool,
    shapes_by_id: dict[str, dict[str, Any]],
) -> bool:
    ctype = cond["type"]
    if ctype == "cue-hit":
        if "cues" in cond:
            cues = set(cond["cues"])
        else:
            cues = set(_boost_block(shapes_by_id[cond["cues_from"]])["cues"])
        return bool(task_tokens & cues)
    if ctype == "context-missing":
        return context_missing
    return not narrow  # not-narrow — the only remaining schema-validated type


def _score_shape(
    shape: dict[str, Any],
    task_tokens: set[str],
    context: dict[str, Any],
    shapes_by_id: dict[str, dict[str, Any]],
    narrow_cues: set[str],
) -> tuple[int, list[str]]:
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
    narrow = bool(task_tokens & narrow_cues)

    mode, rules = _boost_rules(shape)
    for rule in rules:
        if all(
            _condition_holds(cond, task_tokens, context_missing, narrow, shapes_by_id)
            for cond in rule["conditions"]
        ):
            score += rule["weight"]
            rationale.append(rule["rationale"])
            if mode == "first-match":
                break

    if context_missing and not shape.get("context_exempt"):
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
            if not _is_skill_active(project_root, name):
                out[name] = _inactive_reason(project_root, name) or ""
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
    project_dir = project_root / ".engineering" / "project"
    live_sources = [
        project_dir / "adapter.yml",
        project_dir / "profile.yml",
        project_dir / "open-questions.md",
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
    shapes_by_id = {str(shape["id"]): shape for shape in shapes}
    narrow_cues = narrow_cue_union(shapes)
    ranked: list[tuple[int, dict[str, Any], list[str]]] = []
    for shape in shapes:
        score, rationale = _score_shape(shape, task_tokens, context, shapes_by_id, narrow_cues)
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
    if winner.get("install_with"):
        recommendation["install_with"] = list(winner["install_with"])
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


def _skill_handoff(result: dict[str, Any], *, source: str, version: str, agent: str) -> dict | None:
    rec = result["recommendation"]
    match = SKILL_TOKEN_RE.search(rec["first_next"])
    if match is None:
        return None
    skill = match.group(1)
    skills = [skill, *rec.get("install_with", [])]
    command = [
        "npx", "--yes", f"skills@{version}", "add", source,
    ]
    for selected_skill in skills:
        command.extend(["--skill", selected_skill])
    command.extend(["--agent", agent, "--copy", "-y"])
    return {
        "skill": skill,
        "skills": skills,
        "source": source,
        "skills_cli_version": version,
        "agent": agent,
        "command": "DO_NOT_TRACK=1 " + shlex.join(command),
        "locations": {
            "definition": f"{source}::.claude/skills/{skill}/SKILL.md",
            "bundled_tooling": f"{source}::.claude/skills/{skill}/scripts/",
            "shared_tooling": f"{source}::scripts/",
        },
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
    if result.get("install"):
        lines.extend(
            [
                "",
                f"Install /{result['install']['skill']}:",
                f"  {result['install']['command']}",
                f"Definition/tooling: {result['install']['locations']['definition']}",
            ]
        )
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
    if log_path is None:
        return
    _append_event(log_path, {
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "skill": "which-shape",
        "event_kind": "recommendation",
        "target": result["task"],
        "artifact": None,
        "outcome": outcome,
        "human_override": human_override,
        "duration_s": round(elapsed_s, 3),
        "follow_up_skill": None,
        "shape": rec["shape"],
        "confidence": rec["confidence"],
        "project_context_state": result["project_context"]["state"],
        "recommended_first_skill": rec["first_next"],
    })


def main(argv: list[str] | None = None) -> int:
    start = time.monotonic()
    parser = argparse.ArgumentParser(description="Recommend the right problem-solving shape.")
    parser.add_argument("task", nargs="*", help="Free-text situation or task description.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--shapes", type=Path, default=DEFAULT_SHAPES)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--skills-cli-version", default=DEFAULT_CLI_VERSION)
    parser.add_argument("--agent", default="codex")
    parser.add_argument(
        "--status", type=Path, default=None,
        help="status.json override (default: <project-root>/.engineering/local/status.json; "
             "absent file = ungrounded run, byte-identical output).",
    )
    parser.add_argument("--validate", action="store_true", help="Validate shapes.json and exit.")
    parser.add_argument("--skip-log", action="store_true")
    parser.add_argument("--log", type=Path, default=None, help="Override skill-use log path.")
    parser.add_argument(
        "--outcome", choices=["unscored", "useful", "partial", "noop", "overridden"],
        default="unscored",
        help="Default 'unscored': a recommendation is not evidence of usefulness; "
             "rerun with an explicit outcome to score it.",
    )
    parser.add_argument("--human-override", default=None)
    args = parser.parse_args(argv)

    try:
        if args.validate:
            load_shapes(args.shapes)  # schema includes the boost blocks
            print("shapes OK")
            return 0
        task = " ".join(args.task).strip()
        result = route(task, args.project_root.resolve(), args.shapes, status_path=args.status)
        handoff = _skill_handoff(
            result,
            source=args.source,
            version=args.skills_cli_version,
            agent=args.agent,
        )
        if handoff is not None:
            result["install"] = handoff
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not args.skip_log:
        log_recommendation(
            result,
            elapsed_s=time.monotonic() - start,
            log_path=args.log or args.project_root / ".claude" / "skill-use" / "log.jsonl",
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
