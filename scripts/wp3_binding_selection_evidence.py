#!/usr/bin/env python3
"""Emit deterministic WP3 per-root binding-selection evidence."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib.binding_loader import BindingLoadError, compose_skill_bindings  # noqa: E402
from _lib.capability_registry import CapabilityRegistry, load_registry  # noqa: E402
from _lib.host_profile import profile_host  # noqa: E402
from _lib.skill_catalog import SkillCatalogEntry, load_catalog  # noqa: E402


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value: object) -> str:
    return _sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_python(root: Path, *, django: bool = False) -> None:
    _write(root / "requirements.txt", "Django==5.2\n" if django else "pytest==9\n")
    _write(root / "app.py", "value = 1\n")
    if django:
        _write(root / "manage.py", "#!/usr/bin/env python3\n")


def _seed_typescript(root: Path, *, react: bool = False) -> None:
    dependencies = {"vite": "7.0.0"}
    if react:
        dependencies["react"] = "19.0.0"
    _write(root / "package.json", json.dumps({"dependencies": dependencies}) + "\n")
    _write(root / "tsconfig.json", "{}\n")
    _write(root / "src" / "app.ts", "export const value = 1;\n")


def _entry(bindings: tuple[str, ...]) -> SkillCatalogEntry:
    return SkillCatalogEntry(
        name="portable-enum",
        path=".claude/skills/portable-enum/SKILL.md",
        current_language="any",
        current_framework="any",
        layer="core",
        binding="core",
        bindings=bindings,
        placement="concept-plus-binding",
        readiness="exemplar-ready",
        rationale="deterministic-evidence-fixture",
        ar3_foundation_member=False,
        raw={},
    )


def _skill(root: Path, bindings: tuple[str, ...]) -> Path:
    skill = root / "portable-enum"
    _write(
        skill / "SKILL.md",
        "---\nname: portable-enum\ndescription: Evidence fixture.\n---\n\n"
        "# Core\n\nShared invariant.\n",
    )
    for binding in bindings:
        if binding != "core":
            _write(
                skill / "bindings" / f"{binding}.md",
                f"# {binding}\n\n{binding} mechanics.\n",
            )
    return skill


def _render_record(render) -> dict[str, Any]:
    sources = render.evidence["sources"]
    core = next(item for item in sources if item["binding"] == "core")
    bindings = {
        item["binding"]: item["sha256"]
        for item in sources
        if item["binding"] != "core"
    }
    return {
        "root": render.root,
        "selected_bindings": list(render.selected_bindings),
        "profile_sha256": render.evidence["profile_sha256"],
        "core_sha256": core["sha256"],
        "binding_sha256": bindings,
        "rendered_sha256": render.evidence["rendered_sha256"],
        "evidence_sha256": _canonical_hash(render.evidence),
    }


def _negative(case: str, callback) -> tuple[str, dict[str, Any]]:
    try:
        callback()
    except BindingLoadError as exc:
        message = str(exc)
        return case, {
            "rejected": True,
            "error": message,
            "error_sha256": _sha256(message.encode("utf-8")),
        }
    raise ValueError(f"negative binding-selection case {case!r} unexpectedly succeeded")


def build_evidence() -> dict[str, Any]:
    registry = load_registry()
    with tempfile.TemporaryDirectory(prefix="wp3-binding-selection-") as raw_tmp:
        temp = Path(raw_tmp)

        actual_project = temp / "actual-fixture"
        _seed_python(actual_project, django=True)
        actual_profile = profile_host(actual_project)
        actual_entry = load_catalog().entries_by_name["extract-enum"]
        actual_skill = REPO_ROOT / ".claude" / "skills" / "extract-enum"
        actual_renders = compose_skill_bindings(
            actual_skill, actual_entry, actual_profile, registry=registry
        )

        bindings = ("core", "python", "javascript-typescript", "django", "react")
        synthetic_skill = _skill(temp / "synthetic-skill", bindings)
        multi_project = temp / "multi-root-fixture"
        _seed_python(multi_project / "backend", django=True)
        _seed_typescript(multi_project / "web", react=True)
        multi_profile = profile_host(multi_project, registry=registry)
        baseline = compose_skill_bindings(
            synthetic_skill,
            _entry(bindings),
            multi_profile,
            registry=registry,
        )
        reversed_data = copy.deepcopy(registry.data)
        reversed_data["bindings"] = dict(
            reversed(tuple(reversed_data["bindings"].items()))
        )
        reversed_registry = CapabilityRegistry(data=reversed_data, path=registry.path)
        reordered_profile = profile_host(multi_project, registry=reversed_registry)
        reordered = compose_skill_bindings(
            synthetic_skill,
            _entry(bindings),
            reordered_profile,
            registry=reversed_registry,
        )
        baseline_records = [_render_record(render) for render in baseline]
        reordered_records = [_render_record(render) for render in reordered]
        by_root = {render.root: render for render in baseline}
        leak = (
            "javascript-typescript mechanics" in by_root["backend"].content
            or "react mechanics" in by_root["backend"].content
            or "python mechanics" in by_root["web"].content
            or "django mechanics" in by_root["web"].content
        )

        ambiguous_registry_data = copy.deepcopy(registry.data)
        ambiguous_registry_data["bindings"]["python-alt"] = {
            "kind": "language",
            "layer": "language",
            "languages": ["python"],
            "frameworks": ["any", "none"],
        }
        ambiguous_registry = CapabilityRegistry(
            data=ambiguous_registry_data, path=registry.path
        )
        ambiguous_project = temp / "ambiguity-fixture"
        _seed_python(ambiguous_project)
        ambiguous_skill = _skill(
            temp / "ambiguous-skill", ("core", "python", "python-alt")
        )
        ambiguous_profile = profile_host(
            ambiguous_project, registry=ambiguous_registry
        )

        typescript_project = temp / "typescript-fixture"
        _seed_typescript(typescript_project)
        typescript_profile = profile_host(typescript_project, registry=registry)
        python_skill = _skill(
            temp / "python-only-skill", ("core", "python", "django")
        )
        negative_outcomes = dict(
            [
                _negative(
                    "ambiguity",
                    lambda: compose_skill_bindings(
                        ambiguous_skill,
                        _entry(("core", "python", "python-alt")),
                        ambiguous_profile,
                        registry=ambiguous_registry,
                    ),
                ),
                _negative(
                    "incompatibility",
                    lambda: compose_skill_bindings(
                        python_skill,
                        _entry(("core", "python", "django")),
                        typescript_profile,
                        registry=registry,
                        explicit_bindings_by_root={".": ["django"]},
                    ),
                ),
                _negative(
                    "zero_match",
                    lambda: compose_skill_bindings(
                        python_skill,
                        _entry(("core", "python", "django")),
                        typescript_profile,
                        registry=registry,
                    ),
                ),
            ]
        )

        baseline_hash = _canonical_hash(baseline_records)
        reordered_hash = _canonical_hash(reordered_records)
        return {
            "schema_version": 1,
            "successful_selection": {
                "profile_sha256": actual_profile["profile_sha256"],
                "roots": [_render_record(render) for render in actual_renders],
            },
            "negative_outcomes": negative_outcomes,
            "root_isolation": {
                "profile_sha256": multi_profile["profile_sha256"],
                "roots": baseline_records,
                "cross_root_binding_leak": leak,
                "evidence_sha256": baseline_hash,
            },
            "order_independence": {
                "equal": baseline_records == reordered_records,
                "baseline_sha256": baseline_hash,
                "reordered_registry_sha256": reordered_hash,
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        payload = build_evidence()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("WP3 binding-selection evidence: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
