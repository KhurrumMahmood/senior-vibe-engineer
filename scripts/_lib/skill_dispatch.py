"""Deterministic ADR 0042 routers and selected-only dispatch decisions.

The module has no catalog discovery path.  Callers must provide a catalog and
ordered root set that were already selected and verified through the release
trust chain.  Advisory routers never load procedure bodies; only a terminal
``selected`` dispatcher decision may call the injected body loader.
"""
from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from _lib.distribution_contracts import validate_distribution_contract


NORMALIZER_ID = "ascii-wordset-v1"
SHAPE_ROUTER_ID = "which-shape-lexical-v1"
SKILL_ROUTER_ID = "which-skill-overlap-v1"
SKILL_THRESHOLD = 5

_WORD_RE = re.compile(r"[a-z][a-z0-9_-]+", re.ASCII)
_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}", re.ASCII)
_SHA256_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)
_UUID4_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.ASCII,
)

# v1 arrays preserve the lexical policy used by both pre-contract routers.
# Tuple order is the checked-in scorer input even where membership uses a set.
STOPWORDS_V1 = (
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could",
    "do", "for", "from", "get", "has", "have", "i", "if", "in", "into",
    "is", "it", "just", "make", "may", "might", "must", "need", "of", "on",
    "or", "really", "right", "set", "should", "that", "the", "this", "to",
    "use", "using", "want", "was", "we", "what", "will", "with", "would",
    "you",
)
QUICK_HINTS_V1 = (
    "minor", "one-line", "oneline", "quick", "rename", "simple", "single",
    "small", "tiny", "trivial", "typo",
)
SKILL_DEVELOPMENT_SUBJECTS_V1 = ("dogfood", "frontmatter", "skill", "skills")
SKILL_DEVELOPMENT_ACTIONS_V1 = (
    "author", "build", "create", "dogfood", "new", "plan", "revise", "update",
    "validation", "write",
)
OBLIGATION_CHANGE_HINTS_V1 = ("changed", "diff", "staged", "touched")
OBLIGATION_VERIFY_HINTS_V1 = (
    "obligation", "obligations", "smoke", "test", "testing", "tests", "tier",
    "tiers", "verification", "verify",
)
TIER_HINTS_V1 = (
    ("feature", ("add", "endpoint", "expose", "feature", "override", "ttl")),
    (
        "system",
        ("architecture", "cross", "cross-cutting", "multi-workflow", "redesign", "rework", "subsystem"),
    ),
    (
        "maintenance",
        (
            "broken", "bug", "dead", "debug", "diagnose", "dormant", "duplicate",
            "duplication", "failing", "fat", "flake", "omnibus", "regression",
            "reproduce", "smell", "stringly", "tuple",
        ),
    ),
    ("new-project", ("bootstrap", "greenfield", "init", "new project", "scaffold")),
    ("cross-cutting", ("adr", "convention", "decision")),
)
JOB_HINTS_V1 = (
    ("plan", ("design", "plan", "planning", "scope")),
    ("map", ("atlas", "inventory", "list", "map", "topology")),
    ("suspect", ("audit", "detect", "discover", "find", "look", "scan", "search")),
    ("explain", ("annotate", "describe", "explain", "summarize", "understand")),
    ("refactor", ("clean", "extract", "fix", "merge", "refactor", "rewrite", "split", "unify")),
    ("guard", ("enforce", "guard", "lint", "prevent", "regression", "rule")),
    ("decide", ("adr", "choose", "decide", "decision", "record")),
    ("triage", ("accumulating", "debt", "prioritize", "queue", "triage")),
    ("teach", ("briefing", "explain why", "teach", "tutorial", "walkthrough")),
    ("construct", ("author", "construct", "create", "draft", "pattern", "write")),
    ("diagnose", ("cause", "debug", "diagnose", "flake", "regression", "reproduce", "root")),
    ("meta", ("audit", "drift", "healthy", "hygiene", "registry", "stale")),
)

_STOPWORDS = frozenset(STOPWORDS_V1)
_QUICK_HINTS = frozenset(QUICK_HINTS_V1)
_SKILL_SUBJECTS = frozenset(SKILL_DEVELOPMENT_SUBJECTS_V1)
_SKILL_ACTIONS = frozenset(SKILL_DEVELOPMENT_ACTIONS_V1)
_OBLIGATION_CHANGE = frozenset(OBLIGATION_CHANGE_HINTS_V1)
_OBLIGATION_VERIFY = frozenset(OBLIGATION_VERIFY_HINTS_V1)
_EXCLUSION_CODES = frozenset(
    {
        "not_for",
        "layer_inapplicable",
        "language_incompatible",
        "framework_incompatible",
        "binding_missing",
        "binding_ambiguous",
        "binding_incompatible",
        "explicit_name_mismatch",
    }
)


class RoutingContractError(ValueError):
    """A caller-supplied routing input violates the deterministic contract."""


@dataclass(frozen=True)
class _ShapeEntry:
    shape_id: str
    strong: frozenset[str]
    normal: frozenset[str]
    negative: frozenset[str]
    context_exempt: bool
    boost: Mapping[str, Any]


@dataclass(frozen=True)
class _SkillEntry:
    canonical_name: str
    public_name: str
    best_for: str
    not_for: str
    description: str
    tier: str
    job: str
    source_sha256: str
    rendered_sha256: str
    roots: tuple[dict[str, Any], ...]
    exclusions: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedRoutingCatalogV1:
    """Manifest-selected router inputs after the external trust gate.

    The factory validates the bounded in-memory interface.  It deliberately
    accepts no project path, manifest path, catalog locator, or body bytes.
    """

    profile_sha256: str
    ordered_root_sha256s: tuple[str, ...]
    context_state: str
    context_required: bool
    shapes: tuple[_ShapeEntry, ...]
    skills: tuple[_SkillEntry, ...]
    aliases: tuple[tuple[str, str], ...]

    @classmethod
    def from_verified_manifest_selection(
        cls,
        *,
        profile_sha256: str,
        ordered_root_sha256s: Sequence[str],
        context_state: str,
        context_required: bool,
        shapes: Sequence[Mapping[str, Any]],
        skills: Sequence[Mapping[str, Any]],
        aliases: Mapping[str, str],
    ) -> VerifiedRoutingCatalogV1:
        if _SHA256_RE.fullmatch(profile_sha256) is None:
            raise RoutingContractError("profile_sha256 is invalid")
        roots = tuple(ordered_root_sha256s)
        if not 1 <= len(roots) <= 32 or len(set(roots)) != len(roots):
            raise RoutingContractError("ordered root set must contain 1 through 32 unique roots")
        if any(_SHA256_RE.fullmatch(root) is None for root in roots):
            raise RoutingContractError("ordered root set contains an invalid digest")
        if context_state not in {"complete", "partial", "missing"}:
            raise RoutingContractError("context_state is invalid")
        if type(context_required) is not bool:
            raise RoutingContractError("context_required must be boolean")

        shape_rows = tuple(_parse_shape(row) for row in shapes)
        if not shape_rows or len(shape_rows) > 256:
            raise RoutingContractError("shape registry must contain 1 through 256 rows")
        shape_ids = [row.shape_id for row in shape_rows]
        if len(set(shape_ids)) != len(shape_ids):
            raise RoutingContractError("shape registry contains duplicate ids")
        _validate_shape_boosts(shape_rows)

        skill_rows = tuple(_parse_skill(row, roots) for row in skills)
        if not skill_rows or len(skill_rows) > 256:
            raise RoutingContractError("catalog must contain 1 through 256 skills")
        canonical_names = [row.canonical_name for row in skill_rows]
        public_names = [row.public_name for row in skill_rows]
        if len(set(canonical_names)) != len(canonical_names):
            raise RoutingContractError("catalog contains duplicate canonical names")
        if len(set(public_names)) != len(public_names):
            raise RoutingContractError("catalog contains duplicate public names")
        name_targets: dict[str, str] = {}
        for skill in skill_rows:
            for name in (skill.canonical_name, skill.public_name):
                prior_target = name_targets.setdefault(name, skill.canonical_name)
                if prior_target != skill.canonical_name:
                    raise RoutingContractError(
                        f"cross-skill canonical/public name collision: {name}"
                    )

        raw_alias_rows = tuple(aliases.items())
        if any(not isinstance(name, str) for row in raw_alias_rows for name in row):
            raise RoutingContractError("alias names and targets must be strings")
        alias_rows = tuple(sorted(raw_alias_rows, key=lambda item: _utf8(item[0])))
        occupied = set(canonical_names) | set(public_names)
        seen_aliases: set[str] = set()
        for public_name, target in alias_rows:
            _require_id(public_name, "alias public_name")
            _require_id(target, "alias canonical_target")
            if public_name in occupied or public_name in seen_aliases:
                raise RoutingContractError(f"alias collision: {public_name}")
            if target not in set(canonical_names):
                raise RoutingContractError(f"alias has unknown target: {target}")
            seen_aliases.add(public_name)

        return cls(
            profile_sha256=profile_sha256,
            ordered_root_sha256s=roots,
            context_state=context_state,
            context_required=context_required,
            shapes=shape_rows,
            skills=skill_rows,
            aliases=alias_rows,
        )

    def resolve_compatible_name(self, name: str) -> tuple[_SkillEntry, str] | None:
        alias_map = dict(self.aliases)
        target = alias_map.get(name, name)
        for skill in self.skills:
            if (
                target in {skill.canonical_name, skill.public_name}
                and not skill.exclusions
            ):
                return skill, name
        return None


def _utf8(value: str) -> bytes:
    return value.encode("utf-8", errors="strict")


def _require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise RoutingContractError(f"{label} is invalid")
    return value


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise RoutingContractError(f"{label} is invalid")
    return value


def _token_array(value: object, label: str) -> frozenset[str]:
    if not isinstance(value, (list, tuple)) or len(value) > 256 or any(
        not isinstance(item, str) or item not in normalize_task(item) for item in value
    ):
        raise RoutingContractError(f"{label} must contain normalized tokens")
    if len(set(value)) != len(value):
        raise RoutingContractError(f"{label} must not contain duplicate tokens")
    return frozenset(value)


def _parse_shape(row: Mapping[str, Any]) -> _ShapeEntry:
    expected = {"shape_id", "strong", "normal", "negative", "context_exempt", "boost"}
    if not isinstance(row, Mapping) or set(row) != expected:
        raise RoutingContractError(f"shape row must contain exactly {sorted(expected)}")
    context_exempt = row["context_exempt"]
    if type(context_exempt) is not bool:
        raise RoutingContractError("shape context_exempt must be boolean")
    boost = row["boost"]
    if not isinstance(boost, Mapping):
        raise RoutingContractError("shape boost must be an object")
    return _ShapeEntry(
        shape_id=_require_id(row["shape_id"], "shape_id"),
        strong=_token_array(row["strong"], "shape strong cues"),
        normal=_token_array(row["normal"], "shape normal cues"),
        negative=_token_array(row["negative"], "shape negative cues"),
        context_exempt=context_exempt,
        boost=deepcopy(dict(boost)),
    )


def _validate_shape_boosts(shapes: tuple[_ShapeEntry, ...]) -> None:
    ids = {shape.shape_id for shape in shapes}
    for shape in shapes:
        boost = shape.boost
        if not boost:
            continue
        if "rules" not in boost and "mode" not in boost:
            if set(boost) - {"cues", "weight", "rationale", "narrow_signal"}:
                raise RoutingContractError(f"shape {shape.shape_id} boost has unknown fields")
            _token_array(boost.get("cues"), "boost cues")
            if type(boost.get("weight")) is not int:
                raise RoutingContractError("boost rule weight must be an integer")
            if not isinstance(boost.get("rationale"), str) or not boost["rationale"]:
                raise RoutingContractError("boost rationale must be non-empty")
            if "narrow_signal" in boost and type(boost["narrow_signal"]) is not bool:
                raise RoutingContractError("boost narrow_signal must be boolean")
            continue
        mode = boost.get("mode")
        rules = boost.get("rules")
        if (
            mode not in {"first-match", "additive"}
            or not isinstance(rules, list)
            or not rules
        ):
            raise RoutingContractError(f"shape {shape.shape_id} has an invalid boost")
        if set(boost) - {"mode", "rules", "narrow_signal"}:
            raise RoutingContractError(f"shape {shape.shape_id} boost has unknown fields")
        if "narrow_signal" in boost and type(boost["narrow_signal"]) is not bool:
            raise RoutingContractError("boost narrow_signal must be boolean")
        for rule in rules:
            if not isinstance(rule, Mapping) or set(rule) != {
                "conditions", "weight", "rationale"
            }:
                raise RoutingContractError(
                    "boost rule must contain conditions, weight, and rationale"
                )
            if type(rule["weight"]) is not int:
                raise RoutingContractError("boost rule weight must be an integer")
            if not isinstance(rule["rationale"], str) or not rule["rationale"]:
                raise RoutingContractError("boost rationale must be non-empty")
            conditions = rule["conditions"]
            if not isinstance(conditions, list):
                raise RoutingContractError("boost rule conditions must be an array")
            for condition in conditions:
                if not isinstance(condition, Mapping) or condition.get("type") not in {
                    "cue-hit", "context-missing", "not-narrow"
                }:
                    raise RoutingContractError("boost condition is invalid")
                if condition["type"] == "cue-hit":
                    if ("cues" in condition) == ("cues_from" in condition):
                        raise RoutingContractError("cue-hit needs exactly one cue source")
                    if "cues" in condition:
                        _token_array(condition["cues"], "boost cues")
                    else:
                        source_id = condition["cues_from"]
                        if source_id not in ids:
                            raise RoutingContractError("boost cues_from is unknown")
                        source = next(item for item in shapes if item.shape_id == source_id)
                        if "cues" not in source.boost:
                            raise RoutingContractError(
                                "boost cues_from must reference a simple boost"
                            )
                    expected_condition_fields = {
                        "type", "cues" if "cues" in condition else "cues_from"
                    }
                else:
                    expected_condition_fields = {"type"}
                if set(condition) != expected_condition_fields:
                    raise RoutingContractError("boost condition has unknown fields")


def _parse_skill(row: Mapping[str, Any], roots: tuple[str, ...]) -> _SkillEntry:
    expected = {
        "canonical_name", "public_name", "best_for", "not_for", "description",
        "tier", "job", "source_sha256", "rendered_sha256", "roots", "exclusions",
    }
    if not isinstance(row, Mapping) or set(row) != expected:
        raise RoutingContractError(f"skill row must contain exactly {sorted(expected)}")
    for field in ("best_for", "not_for", "description", "tier", "job"):
        if not isinstance(row[field], str):
            raise RoutingContractError(f"skill {field} must be a string")
        _utf8(row[field])
    exclusions = row["exclusions"]
    if not isinstance(exclusions, list) or any(code not in _EXCLUSION_CODES for code in exclusions):
        raise RoutingContractError("skill exclusions are invalid")
    if len(set(exclusions)) != len(exclusions) or len(exclusions) > 16:
        raise RoutingContractError("skill exclusions must be unique and bounded")
    root_rows = _parse_roots(row["roots"])
    if exclusions:
        if root_rows:
            raise RoutingContractError("excluded skill cannot carry compatible root bindings")
    elif tuple(root["project_root_sha256"] for root in root_rows) != roots:
        raise RoutingContractError("compatible skill roots must equal the ordered root set")
    return _SkillEntry(
        canonical_name=_require_id(row["canonical_name"], "canonical_name"),
        public_name=_require_id(row["public_name"], "public_name"),
        best_for=row["best_for"],
        not_for=row["not_for"],
        description=row["description"],
        tier=row["tier"],
        job=row["job"],
        source_sha256=_require_digest(row["source_sha256"], "source_sha256"),
        rendered_sha256=_require_digest(row["rendered_sha256"], "rendered_sha256"),
        roots=root_rows,
        exclusions=tuple(exclusions),
    )


def _parse_roots(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or len(value) > 32:
        raise RoutingContractError("skill roots must be a bounded array")
    out: list[dict[str, Any]] = []
    for root in value:
        if not isinstance(root, Mapping) or set(root) != {"project_root_sha256", "bindings"}:
            raise RoutingContractError("skill root binding row is malformed")
        bindings = root["bindings"]
        if not isinstance(bindings, list) or len(bindings) > 16:
            raise RoutingContractError("bindings must be a bounded array")
        parsed_bindings: list[dict[str, str]] = []
        seen: set[str] = set()
        for binding in bindings:
            fields = {"binding_id", "source_sha256", "rendered_sha256"}
            if not isinstance(binding, Mapping) or set(binding) != fields:
                raise RoutingContractError("binding row is malformed")
            binding_id = _require_id(binding["binding_id"], "binding_id")
            if binding_id in seen:
                raise RoutingContractError("binding ids must be unique per root")
            seen.add(binding_id)
            parsed_bindings.append(
                {
                    "binding_id": binding_id,
                    "source_sha256": _require_digest(binding["source_sha256"], "binding source_sha256"),
                    "rendered_sha256": _require_digest(binding["rendered_sha256"], "binding rendered_sha256"),
                }
            )
        out.append(
            {
                "project_root_sha256": _require_digest(root["project_root_sha256"], "project root digest"),
                "bindings": parsed_bindings,
            }
        )
    return tuple(out)


def _task_bytes(task: str | bytes) -> bytes:
    try:
        if isinstance(task, bytes):
            text = task.decode("utf-8", errors="strict")
            if not text.strip():
                raise RoutingContractError("task must not be empty")
            return task
        if isinstance(task, str):
            raw = task.encode("utf-8", errors="strict")
            if not task.strip():
                raise RoutingContractError("task must not be empty")
            return raw
    except (UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise RoutingContractError("task is not strict UTF-8") from exc
    raise RoutingContractError("task must be strict UTF-8 text or bytes")


def normalize_task(task: str | bytes) -> tuple[str, ...]:
    """Apply ``ascii-wordset-v1`` and return UTF-8-byte-sorted tokens."""
    raw = _task_bytes(task)
    return _normalize_text(raw.decode("utf-8", errors="strict"))


def _normalize_text(text: str) -> tuple[str, ...]:
    """Normalize trusted catalog metadata, where an empty field is valid."""
    try:
        lowered = text.encode("utf-8", errors="strict").decode("utf-8").lower()
    except UnicodeError as exc:
        raise RoutingContractError("catalog text is not strict UTF-8") from exc
    tokens = {
        token for token in _WORD_RE.findall(lowered)
        if len(token) > 1 and token not in _STOPWORDS
    }
    return tuple(sorted(tokens, key=_utf8))


def _task_sha256(task: str | bytes) -> str:
    return hashlib.sha256(_task_bytes(task)).hexdigest()


def _boost_condition(
    condition: Mapping[str, Any],
    *,
    tokens: frozenset[str],
    context_missing: bool,
    narrow: bool,
    shapes: Mapping[str, _ShapeEntry],
) -> bool:
    condition_type = condition["type"]
    if condition_type == "context-missing":
        return context_missing
    if condition_type == "not-narrow":
        return not narrow
    cues = (
        frozenset(condition["cues"])
        if "cues" in condition
        else frozenset(shapes[str(condition["cues_from"])].boost["cues"])
    )
    return bool(tokens & cues)


def _boost_rules(boost: Mapping[str, Any]) -> tuple[str, list[Mapping[str, Any]]]:
    if not boost:
        return "additive", []
    if "rules" in boost:
        return str(boost["mode"]), list(boost["rules"])
    return (
        "additive",
        [
            {
                "conditions": [{"type": "cue-hit", "cues": boost["cues"]}],
                "weight": boost["weight"],
                "rationale": boost["rationale"],
            }
        ],
    )


def _literal_boost_cues(boost: Mapping[str, Any]) -> frozenset[str]:
    if "cues" in boost:
        return frozenset(boost["cues"])
    return frozenset(
        cue
        for rule in boost.get("rules", [])
        for condition in rule["conditions"]
        if condition["type"] == "cue-hit" and "cues" in condition
        for cue in condition["cues"]
    )


def route_shape(
    task: str | bytes,
    catalog: VerifiedRoutingCatalogV1,
    *,
    validate_contract: Callable[[str, dict[str, Any]], None] = validate_distribution_contract,
) -> dict[str, Any]:
    """Return a schema-bound advisory ``WhichShapeResultV1`` record."""
    if not isinstance(catalog, VerifiedRoutingCatalogV1):
        raise RoutingContractError("routing catalog is not verified")
    tokens = frozenset(normalize_task(task))
    shapes = {shape.shape_id: shape for shape in catalog.shapes}
    narrow_cues = frozenset(
        cue
        for shape in catalog.shapes
        if shape.boost.get("narrow_signal") is True
        for cue in _literal_boost_cues(shape.boost)
    )
    context_missing = catalog.context_state == "missing"
    candidates: list[dict[str, Any]] = []
    for shape in catalog.shapes:
        strong_hits = tokens & shape.strong
        normal_hits = tokens & shape.normal
        negative_hits = tokens & shape.negative
        score = 12 * len(strong_hits) + 4 * len(normal_hits) - 10 * len(negative_hits)
        rationales: list[str] = []
        if strong_hits:
            rationales.append("strong_match")
        if normal_hits:
            rationales.append("normal_match")
        if negative_hits:
            rationales.append("negative_match")
        boost = shape.boost
        if boost:
            boost_mode, boost_rules = _boost_rules(boost)
            for rule in boost_rules:
                if all(
                    _boost_condition(
                        condition,
                        tokens=tokens,
                        context_missing=context_missing,
                        narrow=bool(tokens & narrow_cues),
                        shapes=shapes,
                    )
                    for condition in rule["conditions"]
                ):
                    score += rule["weight"]
                    if "boost_rule" not in rationales:
                        rationales.append("boost_rule")
                    if boost_mode == "first-match":
                        break
        if context_missing and not shape.context_exempt:
            score -= 4
            rationales.append("missing_context")
        elif not context_missing:
            rationales.append("context_present")
        if not -(2**31) <= score <= 2**31 - 1:
            raise RoutingContractError("shape score exceeds signed 32-bit range")
        confidence = "high" if score >= 40 else "medium" if score >= 24 else "low"
        candidates.append(
            {
                "shape_id": shape.shape_id,
                "score": score,
                "confidence": confidence,
                "rationales": rationales,
            }
        )
    candidates.sort(key=lambda row: (-row["score"], _utf8(row["shape_id"])))
    top_is_tied = len(candidates) > 1 and candidates[0]["score"] == candidates[1]["score"]
    if catalog.context_required and context_missing:
        status = "required_context"
        error = None
    elif not candidates or candidates[0]["score"] < 24 or top_is_tied:
        status = "clarification"
        error = None
    else:
        status = "ok"
        error = None
    result = {
        "schema_version": 1,
        "router_id": SHAPE_ROUTER_ID,
        "normalizer_id": NORMALIZER_ID,
        "task_sha256": _task_sha256(task),
        "profile_sha256": catalog.profile_sha256,
        "status": status,
        "candidates": candidates,
        "error": error,
    }
    validate_contract("which-shape-result-v1", result)
    return result


def _infer_signal(
    tokens: frozenset[str], hints: tuple[tuple[str, tuple[str, ...]], ...]
) -> tuple[str | None, frozenset[str]]:
    best: str | None = None
    best_hits: frozenset[str] = frozenset()
    for identifier, vocabulary in hints:
        hits = tokens & frozenset(vocabulary)
        if len(hits) > len(best_hits):
            best = identifier
            best_hits = hits
    return best, best_hits


def _score_skill(
    skill: _SkillEntry,
    tokens: frozenset[str],
    tier: str | None,
    job: str | None,
    *,
    skill_development_override: bool,
) -> tuple[int, list[str]]:
    best_for = frozenset(_normalize_text(skill.best_for))
    not_for = frozenset(_normalize_text(skill.not_for))
    description = frozenset(_normalize_text(skill.description))
    name = frozenset(_normalize_text(skill.canonical_name))
    best_hits = tokens & best_for
    not_hits = tokens & not_for
    description_hits = (tokens & description) - best_hits
    name_hits = (tokens & name) - best_hits - description_hits
    score = 5 * len(best_hits) - 10 * len(not_hits)
    score += 2 * (len(description_hits) + len(name_hits))
    rationales: list[str] = []
    if best_hits:
        rationales.append("best_for_overlap")
    if not_hits:
        rationales.append("not_for_overlap")
    if description_hits:
        rationales.append("description_overlap")
    if name_hits:
        rationales.append("name_overlap")
    if skill.tier and tier and skill.tier == tier:
        score += 8
        rationales.append("exact_tier")
    elif skill.tier == "cross-cutting" and tier:
        score += 3
        rationales.append("cross_cutting_tier")
    if skill.job and job and skill.job == job:
        score += 6
        rationales.append("exact_job")
    if skill_development_override:
        rationales.append("skill_development_override")
    if not skill.exclusions:
        rationales.append("binding_compatible")
    return score, rationales


def route_skill(
    task: str | bytes,
    catalog: VerifiedRoutingCatalogV1,
    *,
    validate_contract: Callable[[str, dict[str, Any]], None] = validate_distribution_contract,
) -> dict[str, Any]:
    """Return a schema-bound advisory ``WhichSkillResultV1`` record."""
    if not isinstance(catalog, VerifiedRoutingCatalogV1):
        raise RoutingContractError("routing catalog is not verified")
    tokens = frozenset(normalize_task(task))
    skill_development = bool(tokens & _SKILL_SUBJECTS) and bool(tokens & _SKILL_ACTIONS)
    quick = bool(tokens & _QUICK_HINTS) and not skill_development
    tier, _tier_hits = _infer_signal(tokens, TIER_HINTS_V1)
    job, _job_hits = _infer_signal(tokens, JOB_HINTS_V1)
    obligation_override = bool(tokens & _OBLIGATION_CHANGE) and bool(tokens & _OBLIGATION_VERIFY)
    if obligation_override:
        job = "suspect"
    if skill_development:
        tier = "cross-cutting"
        job = "plan"

    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    compatible_count = 0
    for skill in catalog.skills:
        score, rationales = _score_skill(
            skill,
            tokens,
            tier,
            job,
            skill_development_override=skill_development,
        )
        if not -(2**31) <= score <= 2**31 - 1:
            raise RoutingContractError("skill score exceeds signed 32-bit range")
        if skill.exclusions:
            excluded.append(
                {
                    "canonical_name": skill.canonical_name,
                    "public_name": skill.public_name,
                    "score": score,
                    "exclusions": list(skill.exclusions),
                }
            )
        else:
            compatible_count += 1
            if not quick:
                candidates.append(
                    {
                        "canonical_name": skill.canonical_name,
                        "public_name": skill.public_name,
                        "score": score,
                        "applicability": "compatible",
                        "roots": [
                            {
                                "project_root_sha256": root["project_root_sha256"],
                                "bindings": [dict(binding) for binding in root["bindings"]],
                            }
                            for root in skill.roots
                        ],
                        "rationales": rationales,
                    }
                )
    def row_key(row: dict[str, Any]) -> tuple[int, bytes, bytes]:
        return (
            -row["score"],
            _utf8(row["canonical_name"]),
            _utf8(row["public_name"]),
        )
    candidates.sort(key=row_key)
    excluded.sort(key=row_key)
    if compatible_count == 0:
        status = "error"
        error = "no_compatible_candidate"
    elif quick or candidates[0]["score"] < SKILL_THRESHOLD:
        status = "proceed_directly"
        error = None
    else:
        status = "ok"
        error = None
    result = {
        "schema_version": 1,
        "router_id": SKILL_ROUTER_ID,
        "normalizer_id": NORMALIZER_ID,
        "scorer_id": SKILL_ROUTER_ID,
        "threshold": SKILL_THRESHOLD,
        "task_sha256": _task_sha256(task),
        "profile_sha256": catalog.profile_sha256,
        "quick": quick,
        "status": status,
        "candidates": candidates,
        "excluded": excluded,
        "error": error,
    }
    validate_contract("which-skill-result-v1", result)
    return result


def _decision(
    outcome: str,
    *,
    selection: dict[str, Any] | None = None,
    clarification: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "selection": selection,
        "clarification": clarification,
        "error": error,
    }


def _validate_router_result(
    name: str,
    supplied: dict[str, Any],
    expected: dict[str, Any],
    validator: Callable[[str, dict[str, Any]], None],
) -> str | None:
    try:
        validator(name, supplied)
    except Exception:  # noqa: BLE001 - validator failures are closed outcomes
        return "malformed_router_result"
    if supplied != expected:
        return "router_result_mismatch"
    return None


def _load_selected(
    catalog: VerifiedRoutingCatalogV1,
    *,
    requested_name: str,
    selection_basis: str,
    clarification_id: str | None,
    sequence_step: int | None,
    load_procedure: Callable[[str], bytes],
) -> dict[str, Any]:
    if not isinstance(requested_name, str) or _ID_RE.fullmatch(requested_name) is None:
        return _decision("error", error="explicit_unknown_or_incompatible_name")
    resolved = catalog.resolve_compatible_name(requested_name)
    if resolved is None:
        return _decision("error", error="explicit_unknown_or_incompatible_name")
    skill, public_name = resolved
    try:
        body = load_procedure(skill.canonical_name)
    except Exception:  # noqa: BLE001 - injected loader failures are a closed error outcome
        return _decision("error", error="selected_procedure_load_failed")
    if not isinstance(body, bytes):
        return _decision("error", error="selected_procedure_load_failed")
    # The selected catalog row already binds raw source through the caller's
    # release trust gate.  This loader contract returns rendered execution
    # bytes, which are checked independently when raw and rendered hashes differ.
    if hashlib.sha256(body).hexdigest() != skill.rendered_sha256:
        return _decision("error", error="selected_procedure_hash_mismatch")
    return _decision(
        "selected",
        selection={
            "canonical_name": skill.canonical_name,
            "public_name": public_name,
            "selection_basis": selection_basis,
            "clarification_id": clarification_id,
            "sequence_step": sequence_step,
            "source_sha256": skill.source_sha256,
            "rendered_sha256": skill.rendered_sha256,
            "roots": [
                {
                    "project_root_sha256": root["project_root_sha256"],
                    "bindings": [dict(binding) for binding in root["bindings"]],
                }
                for root in skill.roots
            ],
            "procedure_body_kind": "rendered",
            "procedure_body": body,
        },
    )


def dispatch_selection(
    task: str | bytes,
    catalog: VerifiedRoutingCatalogV1 | None,
    *,
    load_procedure: Callable[[str], bytes],
    shape_result: dict[str, Any] | None = None,
    skill_result: dict[str, Any] | None = None,
    explicit_name: str | None = None,
    clarification_answer: str | None = None,
    prior_clarification_id: str | None = None,
    required_procedures: Sequence[str] = (),
    confirmed_sequence: bool = False,
    sequence_step: int | None = None,
    validate_contract: Callable[[str, dict[str, Any]], None] = validate_distribution_contract,
) -> dict[str, Any]:
    """Apply the total ADR 0042 outcome table and load only a final selection."""
    if not isinstance(catalog, VerifiedRoutingCatalogV1):
        return _decision("error", error="unverified_routing_catalog")
    try:
        expected_shape = route_shape(task, catalog, validate_contract=validate_contract)
        expected_skill = route_skill(task, catalog, validate_contract=validate_contract)
    except Exception:  # noqa: BLE001 - routing/trust failures are closed outcomes
        return _decision("error", error="invalid_task_profile_catalog_or_binding")
    actual_shape = shape_result if shape_result is not None else expected_shape
    actual_skill = skill_result if skill_result is not None else expected_skill
    for name, supplied, expected in (
        ("which-shape-result-v1", actual_shape, expected_shape),
        ("which-skill-result-v1", actual_skill, expected_skill),
    ):
        error = _validate_router_result(name, supplied, expected, validate_contract)
        if error is not None:
            return _decision("error", error=error)
    if actual_shape["status"] == "error" or actual_skill["status"] == "error":
        return _decision("error", error=actual_shape["error"] or actual_skill["error"])

    if clarification_answer is not None:
        if prior_clarification_id is None or _UUID4_RE.fullmatch(prior_clarification_id) is None:
            return _decision("error", error="invalid_prior_clarification")
        return _load_selected(
            catalog,
            requested_name=clarification_answer,
            selection_basis="user_confirmed",
            clarification_id=prior_clarification_id,
            sequence_step=sequence_step,
            load_procedure=load_procedure,
        )
    if explicit_name is not None:
        return _load_selected(
            catalog,
            requested_name=explicit_name,
            selection_basis="user_explicit",
            clarification_id=None,
            sequence_step=None,
            load_procedure=load_procedure,
        )

    try:
        raw_procedure_names = tuple(required_procedures)
    except TypeError:
        return _decision("error", error="invalid_required_procedure_sequence")
    if (
        any(not isinstance(name, str) or _ID_RE.fullmatch(name) is None for name in raw_procedure_names)
        or len(raw_procedure_names) > 16
    ):
        return _decision("error", error="invalid_required_procedure_sequence")
    procedure_names = tuple(dict.fromkeys(raw_procedure_names))
    if any(catalog.resolve_compatible_name(name) is None for name in procedure_names):
        return _decision("error", error="explicit_unknown_or_incompatible_name")
    if len(procedure_names) > 1:
        if not confirmed_sequence:
            return _decision(
                "clarification_required",
                clarification={"reason": "simultaneous_different_procedures", "candidates": list(procedure_names)},
            )
        if (
            prior_clarification_id is None
            or _UUID4_RE.fullmatch(prior_clarification_id) is None
            or type(sequence_step) is not int
            or not 1 <= sequence_step <= len(procedure_names)
        ):
            return _decision("error", error="invalid_confirmed_sequence")
        return _load_selected(
            catalog,
            requested_name=procedure_names[sequence_step - 1],
            selection_basis="user_confirmed",
            clarification_id=prior_clarification_id,
            sequence_step=sequence_step,
            load_procedure=load_procedure,
        )

    candidates = actual_shape["candidates"]
    shape_tie = len(candidates) > 1 and candidates[0]["score"] == candidates[1]["score"]
    if (
        actual_shape["status"] in {"clarification", "required_context"}
        or not candidates
        or candidates[0]["score"] < 24
        or shape_tie
    ):
        return _decision(
            "clarification_required",
            clarification={"reason": "shape_ambiguous_or_low_confidence", "candidates": candidates},
        )
    if actual_skill["status"] == "proceed_directly":
        return _decision("proceed_directly")

    skills = actual_skill["candidates"]
    if not skills:
        return _decision("error", error="no_compatible_candidate")
    top_score = skills[0]["score"]
    if top_score < SKILL_THRESHOLD:
        return _decision("proceed_directly")
    tied = [row for row in skills if row["score"] == top_score]
    if len(tied) != 1:
        return _decision(
            "clarification_required",
            clarification={"reason": "skill_top_score_tie", "candidates": tied},
        )
    return _load_selected(
        catalog,
        requested_name=tied[0]["canonical_name"],
        selection_basis="unique_winner",
        clarification_id=None,
        sequence_step=None,
        load_procedure=load_procedure,
    )
