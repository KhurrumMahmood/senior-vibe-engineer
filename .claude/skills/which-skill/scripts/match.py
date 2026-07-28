#!/usr/bin/env python3
"""Skill matcher — primitive recommender for /which-skill.

Reads the bundled metadata-only skill catalog and ranks skills against a
free-text task description. Emits a top-N JSON or markdown report; in JSON
mode the winning candidate also carries a
`task_packet` block (PR B-lite's optional fields: lanes, stage, entrypoint,
consumes, produces, evidence_required, risk_triggers, max_overhead) so an
orchestrator can know not just which skill to invoke but how.

Two purposes:
1. Defend against agent misapplication (the wrong skill is the most
   common failure mode — `/refactor-subsystem` for a typo, etc.).
2. Surface metadata mismatches fast — if /which-skill consistently
   picks wrong, the `not_for` / `best_for` fields are wrong, and the
   PR2 audit knows where to focus.

Exit codes: 0 = ranked successfully, 1 = no skill applies (suggest
proceeding directly), 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
SKILL_DIR = SCRIPT_PATH.parents[1]
DEFAULT_CATALOG = SKILL_DIR / "catalog.json"
DEFAULT_SOURCE = "https://github.com/KhurrumMahmood/senior-vibe-engineer"  # host-ref-allow: public distribution repository
DEFAULT_CLI_VERSION = "1.5.19"
HELP_EPILOG = """\
Role:
  Choose the most relevant tactical skill for the task in front of you.
  Use which-shape instead when you need an overall workflow; use which-cleanup
  after recent changes need a standards-oriented closeout.

Operation:
  --help only prints this text; it never routes, installs, or edits anything.
  Normal routing is read-only and returns an on-demand guide/tool closure.
  Non-router skills stay in the external project-scoped library by default.
  If that library is missing, the result prints an exact bootstrap command.
  Read-only compatibility status:
    python3 .agents/skills/which-skill/scripts/status.py --project-root "$PWD"

Requirements and limits:
  The router needs Python 3.11+. Selected skills may require language-native
  tools or manual review; capability output reports unavailable or slow paths
  instead of pretending they ran. Ambient installation is optional and occurs
  only when the user explicitly requests it.
"""
CODE_HEALTH_FAMILY = "code-health-readonly"
CODE_HEALTH_MEMBERS = (
    "audit-decisions",
    "find-complexity-hotspots",
    "find-standard-gaps",
)

# Optional task-packet fields surfaced on the winning candidate (PR B-lite).
TASK_PACKET_FIELDS = (
    "lanes", "stage", "entrypoint",
    "consumes", "produces", "evidence_required",
    "risk_triggers", "max_overhead",
)

# Words that don't disambiguate. Loose stopword list — biased toward
# recall over precision so single-word matches stay meaningful.
STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
    "has", "have", "i", "if", "in", "into", "is", "it", "of", "on", "or",
    "that", "the", "this", "to", "was", "we", "will", "with", "you", "use",
    "using", "make", "set", "get", "want", "need", "should", "must",
    "can", "could", "would", "may", "might", "just", "really",
})

# Verbs that signal the job the user is asking for.
JOB_HINTS: dict[str, set[str]] = {
    "plan": {"plan", "planning", "design", "scope"},
    "map": {"map", "inventory", "atlas", "topology", "list"},
    "suspect": {"audit", "find", "scan", "detect", "search", "discover", "look"},
    "explain": {"explain", "understand", "describe", "annotate", "summarize"},
    "refactor": {"refactor", "rewrite", "extract", "split", "clean", "merge", "unify", "fix"},
    "guard": {"guard", "lint", "rule", "prevent", "regression", "enforce"},
    "decide": {"decide", "decision", "adr", "record", "choose"},
    "triage": {"triage", "prioritize", "queue", "debt", "accumulating"},
    "teach": {"teach", "explain why", "tutorial", "walkthrough", "briefing"},
    "construct": {"construct", "author", "write", "create", "draft", "pattern"},
    "diagnose": {"diagnose", "debug", "reproduce", "root", "cause", "regression", "flake"},
    "meta": {"audit", "drift", "stale", "healthy", "registry", "hygiene"},
}

# Words that strongly imply Quick tier (no planning skill applies).
QUICK_HINTS = frozenset({
    "typo", "one-line", "oneline", "small", "trivial", "simple",
    "quick", "tiny", "minor", "single",
})

TIER_HINTS: dict[str, set[str]] = {
    "feature": {"feature", "endpoint", "ttl", "override", "expose", "add"},
    "system": {"subsystem", "cross-cutting", "cross", "multi-workflow",
               "redesign", "rework", "architecture"},
    "maintenance": {"dead", "duplicate", "duplication", "dormant", "fat",
                    "omnibus", "stringly", "tuple", "smell", "bug",
                    "broken", "failing", "debug", "diagnose", "reproduce",
                    "regression", "flake"},
    "new-project": {"greenfield", "scaffold", "init", "bootstrap", "new project"},
    "cross-cutting": {"adr", "decision", "convention"},
}

OBLIGATION_CHANGE_HINTS = frozenset({"changed", "touched", "diff", "staged"})
OBLIGATION_VERIFY_HINTS = frozenset({
    "test", "tests", "testing", "verify", "verification", "smoke",
    "obligation", "obligations", "tier", "tiers",
})
SKILL_DEVELOPMENT_HINTS = frozenset({"skill", "skills", "frontmatter", "dogfood"})
SKILL_DEVELOPMENT_ACTIONS = frozenset({
    "create", "write", "plan", "new", "revise", "update", "validation",
    "dogfood", "author", "build",
})

WORD_RE = re.compile(r"[a-z][a-z0-9_-]+")

LANGUAGE_ALIASES = {
    "c": "c",
    "c#": "csharp",
    "cs": "csharp",
    "csharp": "csharp",
    "c++": "cpp",
    "cpp": "cpp",
    "dart": "dart",
    "go": "go",
    "golang": "go",
    "java": "java",
    "kt": "kotlin",
    "kotlin": "kotlin",
    "php": "php",
    "swift": "swift",
    "js": "javascript",
    "javascript": "javascript",
    "py": "python",
    "python": "python",
    "rb": "ruby",
    "ruby": "ruby",
    "rs": "rust",
    "rust": "rust",
    "ts": "typescript",
    "typescript": "typescript",
}
LEXICAL_LANGUAGE_TOKENS = frozenset(LANGUAGE_ALIASES)
LANGUAGE_MARKERS = {
    "csharp": re.compile(
        r"(?i)(?:\bC#(?=\d|\s|$)|\bcsharp\b|\.cs\b|\.csproj\b|\.slnx?\b)"
    ),
    "cpp": re.compile(
        r"(?i)(?:\bC\+\+(?=\d|\s|$)|\bcpp\b|\.(?:cc|cpp|cxx|c\+\+|hpp|hh|hxx|h\+\+|ipp|inl|tpp)\b)"
    ),
    "dart": re.compile(r"(?i)(?:\bdart\b|\.dart\b|pubspec\.yaml\b)"),
    "c": re.compile(
        r"(?i)(?:\bC(?:17|23)?\b(?=\s+(?:project|repo|repository|library|code|source|file))|\.c\b|\.i\b)"
    ),
    "go": re.compile(
        r"(?:\bGolang\b|\bGo\b(?=\s+(?:project|repo|repository|module|service|"
        r"package|code|source|file|CLI|application|app)\b)|\.go\b)"
    ),
    "java": re.compile(r"(?i)(?:\bjava\b|\.java\b)"),
    "kotlin": re.compile(r"(?i)(?:\bkotlin\b|\.kt\b|build\.gradle\.kts\b)"),
    "php": re.compile(r"(?i)(?:\bphp\b|\.php\b)"),
    "swift": re.compile(r"(?i)(?:\bswift(?:pm)?\b|\.swift\b|Package\.swift\b)"),
    "typescript": re.compile(r"(?i)(?:\btypescript\b|\.tsx?\b)"),
    "javascript": re.compile(r"(?i)(?:\bjavascript\b|(?:\.[cm]?js|\.jsx)\b)"),
    "python": re.compile(r"(?i)(?:\bpython\b|\.py\b)"),
    "ruby": re.compile(r"(?i)(?:\bruby\b|\.rb\b)"),
    "rust": re.compile(r"(?i)(?:\brust\b|\.rs\b)"),
}

# Planning verbs and broad technical nouns occur throughout the catalog. They
# describe a task's form, not the evidence needed to select one particular
# skill. A match composed only of these terms must not clear the threshold on
# job/tier boosts alone.
NON_DISCRIMINATING_MATCH_TOKENS = frozenset({
    "again", "already", "api", "cause", "compatibility", "database", "diagnose",
    "diagnosis", "draft", "failure", "fix", "guard", "implementation",
    "known", "migration", "migrations", "narrow", "not", "plan", "planning",
    "proposal", "propose", "refactor", "regression", "reproduce", "reproduced",
    "root", "table", "tables", "upgrade", "upgrades", "upgrading", "user",
    "users", "verify", "verification", "write",
})

# These words express sentence polarity or result cardinality, not a skill
# boundary by themselves. Penalizing them makes careful phrasing such as "do
# not edit" or "report only" count against the read-only skill it describes.
NON_DISCRIMINATING_NOT_FOR_TOKENS = frozenset({"not", "only"})

NEGATED_DIAGNOSIS_RE = re.compile(
    r"\b(?:do\s+not|don't|dont|avoid|stop|no\s+need\s+to)"
    r"(?:\s+\w+){0,2}\s+(?:diagnose|debug|investigate)\b",
    re.IGNORECASE,
)
KNOWN_ROOT_CAUSE_RE = re.compile(
    r"\b(?:root\s+cause|cause)\s+(?:is\s+)?(?:already\s+)?"
    r"(?:known|identified|confirmed)\b",
    re.IGNORECASE,
)
COMPLETED_REPRODUCTION_RE = re.compile(
    r"\b(?:already\s+)?(?:reproduced|reproducible|confirmed)\b",
    re.IGNORECASE,
)
ORDERED_PHASE_RE = re.compile(r"\b(?:then|after|before|finally|next)\b", re.IGNORECASE)
CODE_HEALTH_RE = re.compile(
    r"\b(?:code|codebase|engineering|project|repo(?:sitory)?)\s+health\b|"
    r"\b(?:broad|overall|whole(?:\s+(?:project|repo(?:sitory)?))?)\b"
    r"(?:\s+\w+){0,4}\s+(?:code\s+quality|health\s+check)\b|"
    r"\bhealth\s+check\b(?:\s+\w+){0,6}\s+"
    r"(?:code|codebase|project|repo(?:sitory)?)\b",
    re.IGNORECASE,
)
READ_ONLY_RE = re.compile(
    r"\bread[- ]only\b|\bwithout\s+(?:changing|editing|modifying|fixing)\b|"
    r"\bdo\s+not\s+(?:change|edit|modify|fix)\b",
    re.IGNORECASE,
)
MUTATION_RE = re.compile(
    r"\b(?:fix|change|edit|modify|refactor|rewrite|apply|implement)\b",
    re.IGNORECASE,
)


def _read_manifest(root: Path) -> dict:
    path = root / ".engineering" / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _skill_activation(root: Path) -> dict:
    block = _read_manifest(root).get("skills")
    if not isinstance(block, dict):
        block = {}
    default = block.get("default")
    if default not in {"active", "inactive"}:
        default = "active"

    def reasons(value: object) -> dict[str, str]:
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


def tokenize(text: str) -> set[str]:
    return {
        w for w in WORD_RE.findall(text.lower())
        if w not in STOPWORDS and len(w) > 1
    }


def infer_tier_signal(task_tokens: set[str]) -> tuple[str | None, list[str]]:
    """Return (inferred_tier, matched_hints).

    Returns ('quick', [...]) if the task looks trivial, in which case
    the matcher will suppress all skill recommendations.
    """
    if task_tokens & QUICK_HINTS:
        return "quick", sorted(task_tokens & QUICK_HINTS)
    best_tier: str | None = None
    best_hits: list[str] = []
    for tier, hints in TIER_HINTS.items():
        hits = sorted(task_tokens & hints)
        if len(hits) > len(best_hits):
            best_tier = tier
            best_hits = hits
    return best_tier, best_hits


def infer_job_signal(task_tokens: set[str]) -> tuple[str | None, list[str]]:
    best_job: str | None = None
    best_hits: list[str] = []
    for job, hints in JOB_HINTS.items():
        hits = sorted(task_tokens & hints)
        if len(hits) > len(best_hits):
            best_job = job
            best_hits = hits
    return best_job, best_hits


def is_test_obligation_signal(task_tokens: set[str]) -> bool:
    """True when wording is about changed files and expected verification.

    This narrow override keeps "map touched files to expected tests" from
    routing to inventory-map skills just because the user used "map" as a
    verb rather than asking for a product workflow map.
    """
    return bool(task_tokens & OBLIGATION_CHANGE_HINTS) and bool(task_tokens & OBLIGATION_VERIFY_HINTS)


def is_skill_development_signal(task_tokens: set[str]) -> bool:
    """True when wording is about designing/writing an agent skill.

    Without this override, generic words like "new" and "ui" can route
    "create a new skill" prompts to product-feature or obligation scans.
    """
    return bool(task_tokens & SKILL_DEVELOPMENT_HINTS) and bool(task_tokens & SKILL_DEVELOPMENT_ACTIONS)


def is_completed_or_negated_diagnosis(task: str) -> bool:
    """Whether the prompt says diagnostic work is already complete or unwanted."""
    if NEGATED_DIAGNOSIS_RE.search(task):
        return True
    return bool(
        KNOWN_ROOT_CAUSE_RE.search(task)
        and COMPLETED_REPRODUCTION_RE.search(task)
    )


def is_ordered_multi_phase_task(task: str, task_tokens: set[str]) -> bool:
    """Recognize an ordered workflow that needs shape routing before a phase skill."""
    if not ORDERED_PHASE_RE.search(task):
        return False
    phase_jobs = {
        job
        for job in ("map", "suspect", "refactor", "guard")
        if task_tokens & JOB_HINTS[job]
    }
    return len(phase_jobs) >= 2


def is_code_health_family_request(task: str, routing_context: dict) -> bool:
    """Select the one proven family only for an explicit broad JS/TS health ask."""
    languages = set(routing_context["languages"])
    normalized_task = re.sub(r"[-–—,;:/]+", " ", task)
    return bool(
        CODE_HEALTH_RE.search(normalized_task)
        and len(languages) == 1
        and languages <= {"typescript", "javascript"}
        and (READ_ONLY_RE.search(task) or not MUTATION_RE.search(task))
    )


def _host_standards_dependency(path: Path | None) -> dict:
    """Validate only the minimum file-level shape worth scanner dispatch."""
    if path is None:
        return {"available": False, "reason": "host_standards_path_not_supplied"}
    dependency = {"available": False, "path": str(path)}
    if not path.is_file():
        return {**dependency, "reason": "host_standards_path_missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {**dependency, "reason": "host_standards_invalid"}
    ideas = payload.get("ideas") if isinstance(payload, dict) else None
    executable = isinstance(ideas, list) and any(
        _detector_dispatchable(row) for row in ideas
    )
    if not executable:
        return {**dependency, "reason": "host_standards_invalid"}
    return {"available": True, "path": str(path)}


def _detector_dispatchable(idea: object) -> bool:
    """Check only fields needed to start a scanner detector."""
    if not isinstance(idea, dict) or not isinstance(idea.get("contract"), dict):
        return False
    detector = idea["contract"].get("detector")
    if not isinstance(detector, dict):
        return False
    paths = detector.get("paths")
    if paths is not None and (
        not isinstance(paths, list)
        or not paths
        or any(
            not isinstance(path, str) or not path or Path(path).is_absolute()
            for path in paths
        )
    ):
        return False
    try:
        if detector.get("kind") == "grep":
            re.compile(detector["situation"])
            satisfied_by = detector.get("satisfied_by")
            if satisfied_by is not None:
                re.compile(satisfied_by)
            window = int(detector.get("window", 20))
            return detector.get("scope", "window") in {"window", "file"} and window >= 0
        if detector.get("kind") == "ast":
            re.compile(detector["call_matches"])
            enclosed_by = detector.get("enclosed_by")
            requires_kwarg = detector.get("requires_kwarg")
            return (
                bool(enclosed_by) != bool(requires_kwarg)
                and (not enclosed_by or enclosed_by in {"try", "with", "defer"})
                and (not requires_kwarg or isinstance(requires_kwarg, str))
            )
    except (KeyError, TypeError, ValueError, re.error):
        return False
    return False


def has_explicit_skill_request(skill: dict, task_tokens: set[str]) -> bool:
    skill_name = str(skill.get("name", "")).strip().lower()
    return bool(skill_name and skill_name in task_tokens)


def has_substantive_skill_evidence(skill: dict, task_tokens: set[str]) -> bool:
    """Return whether task wording identifies this skill beyond generic routing form.

    Catalog prose necessarily mentions common delivery verbs ("plan", "fix")
    and broad artifacts ("API", "migration"). Those overlaps are useful for
    ranking *after* a skill is grounded, but they cannot alone authorize a
    recommendation. Explicit and natural skill names remain authoritative.
    """
    skill_name = str(skill.get("name", ""))
    natural_name_tokens = tokenize(skill_name.replace("-", " "))
    if has_explicit_skill_request(skill, task_tokens):
        return True
    if len(natural_name_tokens) > 1 and natural_name_tokens <= task_tokens:
        return True
    best_for_tokens = tokenize(skill.get("best_for", ""))
    return bool((task_tokens & best_for_tokens) - NON_DISCRIMINATING_MATCH_TOKENS)


def _normalize_values(values: list[str] | None, aliases: dict[str, str] | None = None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        item = value.strip().lower()
        if not item:
            continue
        item = (aliases or {}).get(item, item)
        if item not in normalized:
            normalized.append(item)
    return normalized


def resolve_routing_context(
    task: str,
    explicit_languages: list[str] | None,
    explicit_frameworks: list[str] | None,
) -> dict:
    languages = _normalize_values(explicit_languages, LANGUAGE_ALIASES)
    language_source: str | None = "explicit" if languages else None
    if not languages:
        marker_hits = [
            language
            for language, pattern in LANGUAGE_MARKERS.items()
            if pattern.search(task)
        ]
        if marker_hits:
            languages = marker_hits
            language_source = "task_marker"
    else:
        marker_hits = []

    frameworks = _normalize_values(explicit_frameworks)
    framework_source: str | None = "explicit" if frameworks else None
    return {
        "language": languages[0] if len(languages) == 1 else None,
        "languages": languages,
        "language_source": language_source,
        "task_language_markers": marker_hits,
        "framework": frameworks[0] if len(frameworks) == 1 else None,
        "frameworks": frameworks,
        "framework_source": framework_source,
        "filtering_applied": bool(languages or frameworks),
    }


def portability_exclusion(
    skill: dict, routing_context: dict
) -> dict[str, str] | None:
    """Return the precise reason and next disposition for an ineligible skill."""
    languages = set(routing_context["languages"])
    frameworks = set(routing_context["frameworks"])
    declared_language = str(skill.get("language", "any")).strip().lower()
    declared_framework = str(skill.get("framework", "any")).strip().lower()

    if languages and declared_language != "any" and declared_language not in languages:
        return {
            "classification": "native-alternative-required",
            "reason": f"declares language={declared_language}",
        }
    if (
        (languages or frameworks)
        and declared_framework != "any"
        and declared_framework not in frameworks
    ):
        return {
            "classification": "native-alternative-required",
            "reason": f"requires framework={declared_framework}",
        }

    scans = skill.get("scans")
    if languages and skill.get("job") == "suspect" and isinstance(scans, list):
        declared_scans = {
            LANGUAGE_ALIASES.get(str(item).strip().lower(), str(item).strip().lower())
            for item in scans
        }
        missing = sorted(languages - declared_scans)
        if missing:
            return {
                "classification": "pending-implementation",
                "reason": f"scanner does not declare scans={','.join(missing)}",
            }
    return None


def score_skill(
    skill: dict,
    task_tokens: set[str],
    inferred_tier: str | None,
    inferred_job: str | None,
) -> tuple[int, list[str]]:
    """Return (score, rationale_lines)."""
    rationale: list[str] = []
    score = 0

    best_for_tokens = tokenize(skill.get("best_for", ""))
    not_for_tokens = (
        tokenize(skill.get("not_for", "")) - NON_DISCRIMINATING_NOT_FOR_TOKENS
    )
    desc_tokens = tokenize(skill.get("description", ""))
    skill_name = str(skill.get("name", ""))
    name_tokens = tokenize(skill_name)
    natural_name_tokens = tokenize(skill_name.replace("-", " "))

    # An explicitly named skill is an authoritative routing request. Give it
    # enough weight that portability filtering returns `unsupported` instead
    # of silently substituting a vaguely related eligible skill.
    exact_name = skill_name.strip().lower()
    if exact_name and exact_name in task_tokens:
        score += 100
        rationale.append(f"explicit skill name: {exact_name}")
    elif len(natural_name_tokens) > 1 and natural_name_tokens <= task_tokens:
        score += 40
        rationale.append(f"natural skill name: {' '.join(sorted(natural_name_tokens))}")

    # 1. best_for overlap is the strongest positive signal.
    bf_hits = task_tokens & best_for_tokens
    if bf_hits:
        score += 5 * len(bf_hits)
        rationale.append(f"best_for hit: {', '.join(sorted(bf_hits))}")

    # 2. not_for overlap is the strongest negative signal.
    nf_hits = task_tokens & not_for_tokens
    if nf_hits:
        score -= 10 * len(nf_hits)
        rationale.append(f"not_for hit (penalty): {', '.join(sorted(nf_hits))}")

    # 3. description/name overlap — secondary positive signal.
    other_hits = task_tokens & (desc_tokens | name_tokens)
    other_hits -= bf_hits
    if other_hits:
        score += 2 * len(other_hits)
        rationale.append(f"description/name hit: {', '.join(sorted(other_hits))}")

    # 4. Tier match — boost if skill.tier == inferred tier.
    skill_tier = skill.get("tier")
    if skill_tier and inferred_tier and skill_tier == inferred_tier:
        score += 8
        rationale.append(f"tier match: {skill_tier}")
    elif skill_tier == "cross-cutting" and inferred_tier:
        # cross-cutting is tier-agnostic (decide, which-skill); small boost.
        score += 3

    # 5. Job match — boost if skill.job matches inferred job.
    skill_job = skill.get("job")
    if skill_job and inferred_job and skill_job == inferred_job:
        score += 6
        rationale.append(f"job match: {skill_job}")

    return score, rationale


def load_skills(catalog_path: Path) -> list[dict]:
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read skill catalog {catalog_path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError(f"unsupported skill catalog: {catalog_path}")
    skills = payload.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError(f"skill catalog has no skills: {catalog_path}")
    if any(not isinstance(skill, dict) or not skill.get("name") for skill in skills):
        raise ValueError(f"skill catalog contains an invalid entry: {catalog_path}")
    names = {str(skill["name"]) for skill in skills}
    for skill in skills:
        companions = skill.get("install_with", [])
        if (
            not isinstance(companions, list)
            or any(not isinstance(name, str) or name not in names for name in companions)
            or len(companions) != len(set(companions))
            or skill["name"] in companions
        ):
            raise ValueError(
                f"skill catalog contains invalid install_with metadata: {skill['name']}"
            )
    return list(skills)


def install_command(*, source: str, version: str, skills: list[str], agent: str) -> str:
    command = [
        "npx",
        "--yes",
        f"skills@{version}",
        "add",
        source,
    ]
    for skill in skills:
        command.extend(["--skill", skill])
    command.extend(["--agent", agent, "--copy", "-y"])
    return "DO_NOT_TRACK=1 " + shlex.join(command)


def resolve_library_root(project_root: Path, library_root: Path | None) -> Path:
    root = library_root or project_root.parent / ".engineering-skills" / project_root.name
    if not root.is_absolute():
        root = project_root / root
    return root.resolve()


CAPABILITY_FIELDS = (
    "skill",
    "expansion_disposition",
    "typescript_disposition",
    "javascript_disposition",
    "go_disposition",
    "java_disposition",
    "php_disposition",
    "swift_disposition",
    "c_disposition",
    "cpp_disposition",
    "ruby_disposition",
    "rust_disposition",
    "dart_disposition",
    "kotlin_disposition",
    "csharp_disposition",
    "fact_level",
    "outcome_class",
    "framework_family",
)


def capability_handoff(library_root: Path, skills: list[str]) -> dict:
    manifest = library_root / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
    unavailable = {
        "available": False,
        "manifest": str(manifest),
        "skills": [],
    }
    if not manifest.is_file():
        return {**unavailable, "reason": "manifest_missing"}
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 5:
            raise TypeError("unsupported capability manifest schema")
        rows = payload["skills"]
        if not isinstance(rows, list):
            raise TypeError("skills must be a list")
        by_name = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("skill"), str):
                raise TypeError("capability row must have a skill name")
            name = row["skill"]
            if not name or name in by_name:
                raise TypeError("capability skill names must be unique and non-empty")
            by_name[name] = row
        selected = []
        for skill in skills:
            row = by_name[skill]
            if any(field not in row for field in CAPABILITY_FIELDS):
                raise KeyError("selected capability row is incomplete")
            if any(
                not isinstance(row[field], str) or not row[field]
                for field in CAPABILITY_FIELDS
                if field != "framework_family"
            ) or not (
                row["framework_family"] is None
                or isinstance(row["framework_family"], str)
            ):
                raise TypeError("selected capability fields are invalid")
            closure = row["on_demand_closure"]["closure_skills"]
            closure_helpers = row["on_demand_closure"].get("language_helpers", {})
            install_status = row["optional_install"]["status"]
            if (
                not isinstance(closure, list)
                or not closure
                or closure[0] != skill
                or len(closure) != len(set(closure))
                or any(not isinstance(member, str) or not member for member in closure)
                or any(member not in by_name for member in closure)
                or not isinstance(closure_helpers, dict)
                or any(
                    not isinstance(language, str)
                    or not language
                    or not isinstance(paths, list)
                    or not paths
                    or any(not isinstance(path, str) or not path for path in paths)
                    for language, paths in closure_helpers.items()
                )
                or not isinstance(install_status, str)
            ):
                raise TypeError("selected capability closure is invalid")
            capability = {
                **{field: row[field] for field in CAPABILITY_FIELDS},
                "closure_skills": closure,
                "optional_install_status": install_status,
            }
            if closure_helpers:
                resolved_helpers: dict[str, list[str]] = {}
                for language, paths in closure_helpers.items():
                    resolved_paths = []
                    for path in paths:
                        relative = Path(path)
                        if relative.is_absolute() or ".." in relative.parts:
                            raise TypeError("selected capability helper path is unsafe")
                        helper = library_root / relative
                        if not helper.is_file():
                            return {**unavailable, "reason": "required_helper_missing"}
                        resolved_paths.append(str(helper))
                    resolved_helpers[language] = resolved_paths
                capability["closure_helpers"] = resolved_helpers
            selected.append(capability)
        if selected and selected[0]["closure_skills"] != skills:
            raise TypeError("router handoff does not match the declared closure")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return {**unavailable, "reason": "manifest_invalid_or_incomplete"}
    return {
        "available": True,
        "manifest": str(manifest),
        "skills": selected,
    }


def _capability_exclusion(disposition: str, reason: str) -> dict[str, str]:
    if disposition.endswith("-pending-implementation"):
        classification = "pending-implementation"
    elif disposition.endswith("-unsupported"):
        classification = "unsupported"
    elif disposition == "not-applicable":
        classification = "not-applicable"
    elif disposition.endswith("-partial"):
        classification = "partial"
    else:
        classification = "not-validated"
    return {"classification": classification, "reason": reason}


def capability_language_exclusion(
    capabilities: dict, routing_context: dict
) -> dict[str, str] | None:
    if not capabilities.get("available"):
        return None
    # The selected skill's accepted coverage row owns the outcome claim for
    # its full declared closure. Companions may intentionally expose a useful
    # partial evidence layer (for example, a selected-configuration map) that
    # is sufficient for the primary skill's bounded supported outcome.
    primary_rows = capabilities["skills"][:1]
    for language in routing_context["languages"]:
        for row in primary_rows:
            if language == "go" and row["go_disposition"] not in {
                "go-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["go_disposition"],
                    f"/{row['skill']} declares go_disposition={row['go_disposition']}",
                )
            if language == "java" and row["java_disposition"] not in {
                "java-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["java_disposition"],
                    f"/{row['skill']} declares java_disposition={row['java_disposition']}",
                )
            if language == "php" and row["php_disposition"] not in {
                "php-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["php_disposition"],
                    f"/{row['skill']} declares php_disposition={row['php_disposition']}",
                )
            if language == "swift" and row["swift_disposition"] not in {
                "swift-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["swift_disposition"],
                    f"/{row['skill']} declares swift_disposition={row['swift_disposition']}",
                )
            if language == "c" and row["c_disposition"] not in {
                "c-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["c_disposition"],
                    f"/{row['skill']} declares c_disposition={row['c_disposition']}",
                )
            if language == "cpp" and row["cpp_disposition"] not in {
                "cpp-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["cpp_disposition"],
                    f"/{row['skill']} declares cpp_disposition={row['cpp_disposition']}",
                )
            if language == "ruby" and row["ruby_disposition"] not in {
                "ruby-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["ruby_disposition"],
                    f"/{row['skill']} declares ruby_disposition={row['ruby_disposition']}",
                )
            if language == "rust" and row["rust_disposition"] not in {
                "rust-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["rust_disposition"],
                    f"/{row['skill']} declares rust_disposition={row['rust_disposition']}",
                )
            if language == "dart" and row["dart_disposition"] not in {
                "dart-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["dart_disposition"],
                    f"/{row['skill']} declares dart_disposition={row['dart_disposition']}",
                )
            if language == "kotlin" and row["kotlin_disposition"] not in {
                "kotlin-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["kotlin_disposition"],
                    f"/{row['skill']} declares kotlin_disposition={row['kotlin_disposition']}",
                )
            if language == "csharp" and row["csharp_disposition"] not in {
                "csharp-supported",
                "validated-neutral",
            }:
                return _capability_exclusion(
                    row["csharp_disposition"],
                    f"/{row['skill']} declares csharp_disposition={row['csharp_disposition']}",
                )
    return None


def bootstrap_command(*, project_root: Path, source: str) -> str:
    """Return the exact command that repairs a missing on-demand library."""
    script = (
        project_root
        / ".agents"
        / "skills"
        / "which-skill"
        / "scripts"
        / "bootstrap_library.py"
    )
    return shlex.join(
        [
            "python3",
            "-I",
            "-S",
            str(script),
            "--project-root",
            str(project_root),
            "--source",
            source,
        ]
    )


def library_handoff(
    library_root: Path,
    skills: list[str],
    *,
    project_root: Path,
    source: str,
) -> dict:
    guides = []
    for skill in skills:
        guide = library_root / ".claude" / "skills" / skill / "SKILL.md"
        bundled_tooling = guide.parent / "scripts"
        guides.append(
            {
                "skill": skill,
                "skill_root": str(guide.parent),
                "guide": str(guide),
                "bundled_tooling": str(bundled_tooling) if bundled_tooling.is_dir() else None,
            }
        )
    shared_tooling = library_root / "scripts"
    source_inventory = shared_tooling / "source_inventory.py"
    capability_inventory = shared_tooling / "capability_inventory.py"
    common_guidance = library_root / ".claude" / "skills" / "_common"
    shared_guidance = library_root / ".claude" / "docs"
    runtime_python = library_root / ".venv" / "bin" / "python"
    capabilities = capability_handoff(library_root, skills)
    guides_available = all(Path(item["guide"]).is_file() for item in guides)
    available = guides_available and capabilities["available"]
    return {
        "mode": "on_demand_library",
        "available": available,
        "default_execution": "fresh_non_context_subagent",
        "library_root": str(library_root),
        "skills": skills,
        "guides": guides if guides_available else [],
        "shared_tooling": str(shared_tooling) if shared_tooling.is_dir() else None,
        "source_inventory_tool": str(source_inventory) if source_inventory.is_file() else None,
        "capability_inventory_tool": (
            str(capability_inventory) if capability_inventory.is_file() else None
        ),
        "common_guidance": str(common_guidance) if common_guidance.is_dir() else None,
        "shared_guidance": str(shared_guidance) if shared_guidance.is_dir() else None,
        "runtime": {
            "available": runtime_python.is_file(),
            "python": str(runtime_python),
        },
        "capabilities": capabilities,
        "repair": (
            None
            if available
            else {
                "action": "bootstrap_library",
                "command": bootstrap_command(
                    project_root=project_root,
                    source=source,
                ),
            }
        ),
        "instruction": (
            "For non-trivial work, give a fresh non-context sub-agent the task, project root, "
            "task packet, selected skill roots, library runtime Python, and shared guidance/tool "
            "paths. For small work, read from the same bounded roots directly. Do not install "
            "the skills unless the user explicitly asks."
        ),
    }


def code_health_family_handoff(
    *,
    library_root: Path,
    project_root: Path,
    source: str,
    standards: Path | None,
    routing_context: dict,
) -> dict:
    """Return the bounded family closure without ambiently installing members."""
    root = library_root / ".claude" / "skill-families" / CODE_HEALTH_FAMILY
    paths = {
        "root": str(root),
        "manifest": str(root / "manifest.json"),
        "core": str(root / "CORE.md"),
        "launcher": str(root / "scripts" / "run.py"),
    }
    standards_path = standards
    if standards_path is not None and not standards_path.is_absolute():
        standards_path = project_root / standards_path
    if standards_path is not None:
        standards_path = standards_path.resolve()
    decision_registry = project_root / "ai-docs" / "decisions"
    dependencies = {
        "decision_registry": {
            "available": decision_registry.is_dir(),
            "path": str(decision_registry),
        },
        "host_standards": _host_standards_dependency(standards_path),
    }
    dependency_by_skill = {
        "audit-decisions": "decision_registry",
        "find-complexity-hotspots": None,
        "find-standard-gaps": "host_standards",
    }
    family_available = all(Path(value).exists() for value in paths.values())
    members = []
    runnable = []
    skips = []
    for skill in CODE_HEALTH_MEMBERS:
        skill_root = library_root / ".claude" / "skills" / skill
        guide = root / "members" / f"{skill}.md"
        member = {
            "skill": skill,
            "guide": str(guide),
            "skill_root": str(skill_root),
            "full_skill_guide": str(skill_root / "SKILL.md"),
            "bundled_tooling": str(skill_root / "scripts"),
            "dependency": dependency_by_skill[skill],
            "on_demand_closure": library_handoff(
                library_root,
                [skill],
                project_root=project_root,
                source=source,
            ),
        }
        members.append(member)
        dependency = dependency_by_skill[skill]
        capability_reason = capability_language_exclusion(
            member["on_demand_closure"]["capabilities"], routing_context
        )
        if not family_available or not guide.is_file() or not (skill_root / "SKILL.md").is_file():
            skips.append({"skill": skill, "reason": "family_closure_unavailable"})
        elif not _is_skill_active(project_root, skill):
            skips.append(
                {
                    "skill": skill,
                    "reason": _inactive_reason(project_root, skill) or "host_skill_inactive",
                }
            )
        elif not member["on_demand_closure"]["capabilities"]["available"]:
            skips.append({"skill": skill, "reason": "capability_evidence_unavailable"})
        elif capability_reason is not None:
            skips.append(
                {
                    "skill": skill,
                    "classification": capability_reason["classification"],
                    "reason": capability_reason["reason"],
                }
            )
        elif dependency and not dependencies[dependency]["available"]:
            if dependency == "host_standards":
                reason = dependencies[dependency]["reason"]
            else:
                reason = "decision_registry_missing"
            skips.append({"skill": skill, "reason": reason})
        else:
            runnable.append(skill)
    return {
        "name": CODE_HEALTH_FAMILY,
        "available": family_available,
        "primary": "find-complexity-hotspots",
        "coverage_set": list(CODE_HEALTH_MEMBERS),
        "runnable": runnable,
        "skips": skips,
        "dependencies": dependencies,
        "execution": {
            "max_parallel_read_only": 3,
            "mutation": "forbidden",
            "synthesis_owner": "family-launcher",
        },
        "paths": paths,
        "members": members,
        "instruction": (
            "Give a fresh non-context sub-agent only the task, project root, family core, "
            "runnable member guides, launcher path, and exact on-demand skill roots. "
            "Report every skip; do not ambiently install member skills."
        ),
    }


def optional_install_handoff(
    *,
    skill: str,
    skills: list[str],
    source: str,
    version: str,
    agent: str,
    capabilities: dict,
    language: str | None,
) -> dict:
    result = {
        "skill": skill,
        "skills": skills,
        "source": source,
        "skills_cli_version": version,
        "agent": agent,
    }
    if not capabilities["available"]:
        return {
            **result,
            "available": False,
            "reason": capabilities["reason"],
            "evidence": [],
        }
    if language:
        closure_field = f"{language}_closure_mode"
        try:
            manifest = Path(capabilities["manifest"])
            rows = json.loads(manifest.read_text(encoding="utf-8"))["skills"]
            by_name = {row["skill"]: row for row in rows}
            closure_modes = {
                skill_name: by_name[skill_name][closure_field]
                for skill_name in skills
                if closure_field in by_name[skill_name]
            }
            if closure_modes and (
                len(closure_modes) != len(skills)
                or any(
                    mode not in {"stock-selected-install", "external-library"}
                    for mode in closure_modes.values()
                )
            ):
                raise ValueError("invalid language closure mode")
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return {
                **result,
                "available": False,
                "reason": "selected_language_closure_mode_unavailable",
                "evidence": [],
            }
        external_only = [
            name for name, mode in closure_modes.items() if mode == "external-library"
        ]
        if external_only:
            return {
                **result,
                "available": False,
                "reason": "selected_language_requires_external_library",
                "evidence": [
                    {"skill": name, "status": "external-library-only"}
                    for name in external_only
                ],
            }
    evidence = [
        {"skill": row["skill"], "status": row["optional_install_status"]}
        for row in capabilities["skills"]
    ]
    if any(row["status"] != "passed" for row in evidence):
        return {
            **result,
            "available": False,
            "reason": "selected_skill_install_not_validated",
            "evidence": evidence,
        }
    return {
        **result,
        "available": True,
        "evidence": evidence,
        "command": install_command(
            source=source,
            version=version,
            skills=skills,
            agent=agent,
        ),
    }


def _build_task_packet(skill: dict) -> dict:
    """Pull the optional task-packet fields off a skill, omitting any
    that aren't declared. Returns {} if the skill carries none."""
    return {f: skill[f] for f in TASK_PACKET_FIELDS if f in skill}


def cmd_match(args, catalog_path: Path) -> int:
    task = args.task.strip()
    if not task:
        print("error: empty task description", file=sys.stderr)
        return 2

    task_tokens = tokenize(task)
    routing_context = resolve_routing_context(
        task,
        args.language,
        args.framework,
    )
    # Language names establish portability context; they do not distinguish
    # between skills that support the same host. Keeping them in lexical
    # scoring rewards whichever metadata repeats the host language most often
    # and can even penalize the correct skill for restating a language boundary
    # in not_for. Preserve the original tokens for exact skill requests and
    # routing signals, but exclude all known aliases from semantic ranking.
    scoring_tokens = task_tokens - LEXICAL_LANGUAGE_TOKENS
    inferred_tier, tier_hits = infer_tier_signal(task_tokens)
    inferred_job, job_hits = infer_job_signal(task_tokens)
    if is_test_obligation_signal(task_tokens):
        inferred_job = "suspect"
        job_hits = sorted(set(job_hits) | {"verification-obligation"})
    if is_skill_development_signal(task_tokens):
        inferred_tier = "cross-cutting"
        inferred_job = "plan"
        tier_hits = sorted(set(tier_hits) | {"skill-development"})
        job_hits = sorted(set(job_hits) | {"skill-development"})
    diagnosis_is_complete = is_completed_or_negated_diagnosis(task)
    ordered_multi_phase = is_ordered_multi_phase_task(task, task_tokens)
    code_health_family_requested = is_code_health_family_request(task, routing_context)

    try:
        skills = load_skills(catalog_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not skills:
        print(f"error: no skills found in {catalog_path}", file=sys.stderr)
        return 2

    # Quick tier short-circuit — recommend no planning skill.
    if inferred_tier == "quick":
        out = {
            "task": task,
            "inferred_tier": "quick",
            "tier_hints": tier_hits,
            "recommendation": "proceed_directly",
            "routing_context": routing_context,
            "rationale": (
                "Task description matches Quick-tier signals "
                f"({', '.join(tier_hits)}). No planning skill applies. "
                "Optional: /decide if a real choice is being made along the way."
            ),
            "candidates": [],
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"Task: {task}")
            print(f"Inferred tier: quick (hints: {', '.join(tier_hits)})")
            print()
            print("Recommendation: proceed directly — no planning skill applies.")
            print(
                "Optional: /decide if a real choice is being made along the way."
            )
        return 1

    explicit_skill_requested = any(
        has_explicit_skill_request(skill, task_tokens)
        for skill in skills
    )
    project_root = args.project_root.resolve()
    if explicit_skill_requested or not _is_skill_active(
        project_root, "find-complexity-hotspots"
    ):
        code_health_family_requested = False
    ranked = []
    for sk in skills:
        score, rationale = score_skill(sk, scoring_tokens, inferred_tier, inferred_job)
        if code_health_family_requested and sk.get("name") == "find-complexity-hotspots":
            score += 200
            rationale.append("broad JS/TS code-health family primary")
        if (
            ordered_multi_phase
            and not explicit_skill_requested
            and sk.get("name") == "which-shape"
        ):
            score += 100
            rationale.append("ordered multi-phase workflow: route through which-shape")
        ranked.append((score, sk, rationale))
    ranked.sort(key=lambda t: (-t[0], t[1].get("name", "")))

    threshold = args.threshold
    # Activation gate — a skill the host has opted out of cannot be
    # recommended for this repo, no matter how well it scores. Drop inactive
    # skills from the candidate pool; surface any that *would* have qualified
    # (score >= threshold) with their recorded reason, so a suppressed
    # high-scorer is explained rather than silently missing.
    active_ranked = []
    excluded_inactive = []
    excluded_ineligible = []
    for score, sk, rationale in ranked:
        name = sk.get("name", "")
        recommendable = (
            has_substantive_skill_evidence(sk, scoring_tokens)
            or (
                code_health_family_requested
                and name == "find-complexity-hotspots"
            )
            or (
                ordered_multi_phase
                and not explicit_skill_requested
                and name == "which-shape"
            )
        ) and not (diagnosis_is_complete and name == "diagnose")
        if name and not _is_skill_active(project_root, name):
            if score >= threshold and recommendable:
                excluded_inactive.append({
                    "name": name,
                    "score": score,
                    "reason": _inactive_reason(project_root, name) or "",
                })
            continue
        portability = portability_exclusion(sk, routing_context)
        if portability is not None:
            if score >= threshold and recommendable:
                excluded_ineligible.append(
                    {
                        "name": name,
                        "score": score,
                        "classification": portability["classification"],
                        "reason": portability["reason"],
                    }
                )
            continue
        if recommendable:
            active_ranked.append((score, sk, rationale))

    top = active_ranked[: args.top]
    above = [r for r in top if r[0] >= threshold]

    out = {
        "task": task,
        "inferred_tier": inferred_tier,
        "inferred_job": inferred_job,
        "tier_hints": tier_hits,
        "job_hints": job_hits,
        "routing_context": routing_context,
        "excluded_inactive": excluded_inactive,
        "excluded_ineligible": excluded_ineligible,
        "candidates": [
            {
                "name": sk.get("name", "?"),
                "score": score,
                "tier": sk.get("tier", ""),
                "job": sk.get("job", ""),
                "language": sk.get("language", "any"),
                "framework": sk.get("framework", "any"),
                "scans": sk.get("scans", []),
                "rationale": rationale,
                "path": sk.get("_path", ""),
                "task_packet": _build_task_packet(sk),
            }
            for score, sk, rationale in top
        ],
    }
    blocked_best = max(
        excluded_ineligible,
        key=lambda item: (item["score"], item["name"]),
        default=None,
    )
    if (
        blocked_best is not None
        and routing_context["filtering_applied"]
        and (not above or blocked_best["score"] > above[0][0])
    ):
        classification = blocked_best["classification"]
        out["recommendation"] = classification
        out["unavailable"] = blocked_best
        out["rationale"] = (
            f"The strongest matching skill, /{blocked_best['name']}, requires "
            f"{classification} for the resolved language/framework: "
            f"{blocked_best['reason']}. No weaker skill was substituted."
        )
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"Task: {task}")
            print(out["rationale"])
        return 1
    if not above:
        out["recommendation"] = "proceed_directly"
        out["rationale"] = (
            f"No skill scored above the threshold ({threshold}). "
            "Either the task is genuinely Quick tier, or no current skill "
            "matches. Proceed directly; consider /decide if a meaningful "
            "choice is being made."
        )
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"Task: {task}")
            print(
                f"Inferred tier: {inferred_tier} | job: {inferred_job}"
            )
            print()
            print(out["rationale"])
            print()
            print("Top candidates anyway (none above threshold):")
            for score, sk, _rationale in top:
                print(f"  {sk.get('name', '?'):<25} score={score}")
            if excluded_inactive:
                print()
                print("Excluded (inactive for this repo):")
                for item in excluded_inactive:
                    reason = f" — {item['reason']}" if item["reason"] else ""
                    print(f"  /{item['name']:<25} score={item['score']}{reason}")
            if excluded_ineligible:
                print()
                print("Excluded (not eligible for resolved language/framework):")
                for item in excluded_ineligible:
                    print(f"  /{item['name']:<25} score={item['score']} — {item['reason']}")
        return 1

    winner = above[0][1]
    out["recommendation"] = winner.get("name", "")
    out["task_packet"] = _build_task_packet(winner)
    install_skills = [out["recommendation"], *winner.get("install_with", [])]
    library_root = resolve_library_root(args.project_root.resolve(), args.library_root)
    out["handoff"] = library_handoff(
        library_root,
        install_skills,
        project_root=args.project_root.resolve(),
        source=args.source,
    )
    capability_reason = capability_language_exclusion(
        out["handoff"]["capabilities"], routing_context
    )
    if capability_reason is not None:
        blocked_name = out["recommendation"]
        out.pop("handoff")
        out.pop("task_packet", None)
        classification = capability_reason["classification"]
        out["recommendation"] = classification
        out["unavailable"] = {
            "name": blocked_name,
            "score": above[0][0],
            "classification": classification,
            "reason": capability_reason["reason"],
        }
        out["rationale"] = (
            f"The strongest matching skill, /{blocked_name}, is currently "
            f"{classification} for the resolved language/framework: "
            f"{capability_reason['reason']}. No weaker skill was substituted."
        )
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"Task: {task}")
            print(out["rationale"])
        return 1
    out["optional_install"] = optional_install_handoff(
        skill=out["recommendation"],
        skills=install_skills,
        source=args.source,
        version=args.skills_cli_version,
        agent=args.agent,
        capabilities=out["handoff"]["capabilities"],
        language=routing_context["language"],
    )
    if code_health_family_requested:
        out["coverage_family"] = code_health_family_handoff(
            library_root=library_root,
            project_root=project_root,
            source=args.source,
            standards=args.standards,
            routing_context=routing_context,
        )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Task: {task}")
        print(
            f"Inferred tier: {inferred_tier or '(unknown)'} | "
            f"job: {inferred_job or '(unknown)'}"
        )
        print()
        print("Top candidates:")
        for score, sk, rationale in above:
            print(
                f"  /{sk.get('name', '?')} (tier={sk.get('tier', '?')}, "
                f"job={sk.get('job', '?')}, score={score})"
            )
            for r in rationale:
                print(f"    - {r}")
        if out["task_packet"]:
            print()
            print(f"Task packet for /{out['recommendation']}:")
            for field, value in out["task_packet"].items():
                print(f"    {field}: {value}")
        print()
        print(f"Use /{out['recommendation']} on demand:")
        if out["handoff"]["available"]:
            print(f"  Guide: {out['handoff']['guides'][0]['guide']}")
            print(f"  Default: {out['handoff']['default_execution']}")
            if out["handoff"]["runtime"]["available"]:
                print(f"  Runtime Python: {out['handoff']['runtime']['python']}")
        else:
            print("  Library unavailable. Bootstrap it without running the task:")
            print(f"    {out['handoff']['repair']['command']}")
        if out["optional_install"]["available"]:
            print("  Optional ambient install (only when explicitly requested):")
            print(f"    {out['optional_install']['command']}")
        else:
            print(
                "  Optional ambient install unavailable: "
                f"{out['optional_install']['reason']}"
            )
        if "coverage_family" in out:
            family = out["coverage_family"]
            print()
            print(f"Complementary coverage: {family['name']}")
            print(f"  Core: {family['paths']['core']}")
            print(f"  Launcher: {family['paths']['launcher']}")
            print(f"  Runnable: {', '.join('/' + name for name in family['runnable']) or 'none'}")
            for skip in family["skips"]:
                print(f"  Skip /{skip['skill']}: {skip['reason']}")
            print("  Members stay in the on-demand library; do not ambiently install them.")
        if len(above) < len(top):
            print()
            print("Below threshold (shown for context):")
            for score, sk, _rationale in top[len(above):]:
                print(f"  /{sk.get('name', '?'):<25} score={score}")
        if excluded_inactive:
            print()
            print("Excluded (inactive for this repo):")
            for item in excluded_inactive:
                reason = f" — {item['reason']}" if item["reason"] else ""
                print(f"  /{item['name']:<25} score={item['score']}{reason}")
        if excluded_ineligible:
            print()
            print("Excluded (not eligible for resolved language/framework):")
            for item in excluded_ineligible:
                print(f"  /{item['name']:<25} score={item['score']} — {item['reason']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Rank skills against a free-text task description.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "task",
        help="Free-text description of the task ('add per-site export TTL override').",
    )
    p.add_argument(
        "--catalog", type=Path, default=DEFAULT_CATALOG,
        help="Override the bundled metadata catalog",
    )
    p.add_argument(
        "--project-root", type=Path, default=Path.cwd(),
        help=(
            "Repo whose .engineering/manifest.json declares skill activation; "
            "inactive skills are excluded from recommendations (default: cwd)."
        ),
    )
    p.add_argument(
        "--source", default=DEFAULT_SOURCE,
        help="Skill source used only for the optional ambient-install handoff",
    )
    p.add_argument(
        "--library-root", type=Path,
        help="On-demand library root (default: <project-parent>/.engineering-skills/<project-name>)",
    )
    p.add_argument(
        "--skills-cli-version", default=DEFAULT_CLI_VERSION,
        help="Pinned skills CLI version used in the install handoff",
    )
    p.add_argument(
        "--agent", default="codex",
        help="Agent target used in the install handoff (default: codex)",
    )
    p.add_argument(
        "--language",
        action="append",
        help=(
            "Explicit host language (repeatable). Without this flag, only exact "
            "language names or file suffixes in the task establish a language."
        ),
    )
    p.add_argument(
        "--framework",
        action="append",
        help="Explicit host framework (repeatable); framework-specific skills require it.",
    )
    p.add_argument(
        "--standards",
        type=Path,
        help=(
            "Host-owned standards JSON for the bounded code-health coverage family; "
            "without it, find-standard-gaps is returned as an explicit skip."
        ),
    )
    p.add_argument("--top", type=int, default=3, help="How many candidates to show")
    p.add_argument(
        "--threshold", type=int, default=5,
        help="Minimum score to count as a real recommendation (default: 5)",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = p.parse_args(argv)
    return cmd_match(args, args.catalog)


if __name__ == "__main__":
    sys.exit(main())
