from __future__ import annotations

import copy
import hashlib

import pytest

from _lib.skill_dispatch import (
    NORMALIZER_ID,
    SHAPE_ROUTER_ID,
    SKILL_ROUTER_ID,
    RoutingContractError,
    VerifiedRoutingCatalogV1,
    dispatch_selection,
    normalize_task,
    route_shape,
    route_skill,
)


HASH = "a" * 64
OTHER_HASH = "b" * 64
ROOT_HASH = "c" * 64
PROCEDURE_BODY = b"selected procedure"
PROCEDURE_HASH = hashlib.sha256(PROCEDURE_BODY).hexdigest()


def _root(*binding_ids: str) -> dict[str, object]:
    return {
        "project_root_sha256": ROOT_HASH,
        "bindings": [
            {
                "binding_id": binding_id,
                "source_sha256": HASH,
                "rendered_sha256": OTHER_HASH,
            }
            for binding_id in binding_ids
        ],
    }


def _shape(
    shape_id: str,
    *,
    strong: tuple[str, ...] = (),
    normal: tuple[str, ...] = (),
    negative: tuple[str, ...] = (),
    context_exempt: bool = True,
    boost: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "shape_id": shape_id,
        "strong": list(strong),
        "normal": list(normal),
        "negative": list(negative),
        "context_exempt": context_exempt,
        "boost": boost or {},
    }


def _skill(
    name: str,
    *,
    best_for: str = "",
    not_for: str = "",
    description: str = "",
    tier: str = "feature",
    job: str = "plan",
    exclusions: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "canonical_name": name,
        "public_name": name,
        "best_for": best_for,
        "not_for": not_for,
        "description": description,
        "tier": tier,
        "job": job,
        "source_sha256": PROCEDURE_HASH,
        "rendered_sha256": PROCEDURE_HASH,
        "roots": [] if exclusions else [_root("core")],
        "exclusions": list(exclusions),
    }


def _catalog(
    *,
    shapes: tuple[dict[str, object], ...] | None = None,
    skills: tuple[dict[str, object], ...] | None = None,
    aliases: dict[str, str] | None = None,
    context_state: str = "complete",
    context_required: bool = False,
) -> VerifiedRoutingCatalogV1:
    return VerifiedRoutingCatalogV1.from_verified_manifest_selection(
        profile_sha256=HASH,
        ordered_root_sha256s=(ROOT_HASH,),
        context_state=context_state,
        context_required=context_required,
        shapes=shapes
        or (
            _shape("feature", strong=("feature", "build", "endpoint")),
            _shape("maintenance", strong=("bug", "broken", "fix")),
        ),
        skills=skills
        or (
            _skill("plan-feature", best_for="feature build endpoint"),
            _skill("fix-workflow", best_for="bug broken fix", tier="maintenance", job="refactor"),
        ),
        aliases=aliases or {},
    )


class BodyReads:
    def __init__(self) -> None:
        self.names: list[str] = []

    def __call__(self, canonical_name: str) -> bytes:
        self.names.append(canonical_name)
        return PROCEDURE_BODY


def _dispatch(
    task: str | bytes,
    catalog: VerifiedRoutingCatalogV1 | None,
    reads: BodyReads,
    **kwargs: object,
) -> dict[str, object]:
    return dispatch_selection(task, catalog, load_procedure=reads, **kwargs)


def test_ascii_wordset_v1_normalizes_strict_utf8_once_and_in_utf8_order() -> None:
    assert normalize_task("The ZED zed alpha_beta A café BETA-2") == (
        "alpha_beta",
        "beta-2",
        "caf",
        "zed",
    )
    assert normalize_task(b"BUG bug endpoint") == ("bug", "endpoint")

    with pytest.raises(RoutingContractError, match="strict UTF-8"):
        normalize_task(b"\xff")
    with pytest.raises(RoutingContractError, match="strict UTF-8"):
        normalize_task("\ud800")
    with pytest.raises(RoutingContractError, match="must not be empty"):
        normalize_task("  \n")


def test_which_shape_uses_exact_weights_boost_order_context_and_confidence() -> None:
    catalog = _catalog(
        context_state="missing",
        shapes=(
            _shape(
                "alpha",
                strong=("feature",),
                normal=("build",),
                negative=("legacy",),
                context_exempt=False,
                boost={
                    "mode": "first-match",
                    "rules": [
                        {
                            "conditions": [{"type": "cue-hit", "cues": ["feature"]}],
                            "weight": 30,
                            "rationale": "first declared boost",
                        },
                        {
                            "conditions": [{"type": "cue-hit", "cues": ["build"]}],
                            "weight": 99,
                            "rationale": "must not run in first-match mode",
                        },
                    ],
                },
            ),
            _shape("zeta", strong=("feature",), normal=("build",)),
        ),
    )

    result = route_shape("feature build legacy", catalog)

    assert result["schema_version"] == 1
    assert result["router_id"] == SHAPE_ROUTER_ID
    assert result["normalizer_id"] == NORMALIZER_ID
    assert result["status"] == "ok"
    assert result["candidates"] == [
        {
            "shape_id": "alpha",
            "score": 32,
            "confidence": "medium",
            "rationales": [
                "strong_match",
                "normal_match",
                "negative_match",
                "boost_rule",
                "missing_context",
            ],
        },
        {
            "shape_id": "zeta",
            "score": 16,
            "confidence": "low",
            "rationales": ["strong_match", "normal_match"],
        },
    ]


def test_verified_catalog_rejects_duplicate_tokens_and_cross_skill_name_collisions() -> None:
    duplicate_cues = _shape("feature", strong=("feature", "feature"))
    first = _skill("alpha")
    first["public_name"] = "alpha-public"
    second = _skill("alpha-public")
    second["public_name"] = "zeta"

    with pytest.raises(RoutingContractError, match="duplicate tokens"):
        _catalog(shapes=(duplicate_cues,))
    with pytest.raises(RoutingContractError, match="canonical/public name collision"):
        _catalog(skills=(first, second))


def test_which_skill_uses_exact_weights_threshold_and_sorted_ties() -> None:
    catalog = _catalog(
        skills=(
            _skill(
                "zeta",
                best_for="feature endpoint",
                not_for="legacy",
                description="build release",
                tier="feature",
                job="plan",
            ),
            _skill(
                "alpha",
                best_for="feature endpoint",
                not_for="legacy",
                description="build release",
                tier="feature",
                job="plan",
            ),
        )
    )

    result = route_skill("plan feature endpoint build legacy", catalog)

    # 2 best-for hits (+10), one not-for (-10), one other (+2), exact tier
    # (+8), and exact job (+6) = 16.
    assert result["router_id"] == SKILL_ROUTER_ID
    assert result["scorer_id"] == SKILL_ROUTER_ID
    assert result["threshold"] == 5
    assert result["status"] == "ok"
    assert [row["canonical_name"] for row in result["candidates"]] == ["alpha", "zeta"]
    assert [row["score"] for row in result["candidates"]] == [16, 16]


def test_skill_development_override_precedes_quick_short_circuit() -> None:
    catalog = _catalog(
        skills=(
            _skill(
                "plan-skill",
                best_for="create skill",
                tier="cross-cutting",
                job="plan",
            ),
        )
    )

    result = route_skill("quick create a skill", catalog)

    assert result["quick"] is False
    assert result["status"] == "ok"
    assert result["candidates"][0]["score"] == 24
    assert "skill_development_override" in result["candidates"][0]["rationales"]


def test_quick_classification_cannot_hide_zero_compatible_candidates() -> None:
    catalog = _catalog(
        skills=(
            _skill("alpha", best_for="quick typo", exclusions=("binding_missing",)),
        )
    )

    # Integration dependency: the trust lane is repairing the production
    # validator so the higher-precedence no-compatible error can coexist with
    # exact quick=true classification.  Keep this scorer/outcome test isolated
    # from that owned repair through the explicit validator seam.
    def trust_lane_pending(_name: str, _document: dict[str, object]) -> None:
        return None

    result = route_skill("quick typo", catalog, validate_contract=trust_lane_pending)

    assert result["quick"] is True
    assert result["status"] == "error"
    assert result["error"] == "no_compatible_candidate"
    assert result["candidates"] == []
    assert result["excluded"][0]["canonical_name"] == "alpha"


@pytest.mark.parametrize(
    ("case", "expected_outcome"),
    [
        ("zero-compatible", "error"),
        ("no-match", "proceed_directly"),
        ("below-threshold", "proceed_directly"),
        ("unique", "selected"),
        ("tie", "clarification_required"),
        ("low-shape", "clarification_required"),
        ("multi-procedure", "clarification_required"),
    ],
)
def test_dispatcher_total_ranked_outcomes_do_not_read_unselected_bodies(
    case: str, expected_outcome: str
) -> None:
    reads = BodyReads()
    kwargs: dict[str, object] = {}
    if case == "zero-compatible":
        catalog = _catalog(
            skills=(
                _skill("alpha", best_for="feature", exclusions=("binding_missing",)),
            )
        )
        task = "feature feature feature feature"
    elif case == "no-match":
        catalog = _catalog(
            skills=(_skill("alpha", description="unrelated", tier="system", job="decide"),)
        )
        task = "feature build endpoint"
    elif case == "below-threshold":
        catalog = _catalog(
            skills=(_skill("alpha", description="feature", tier="system", job="decide"),)
        )
        task = "feature build endpoint"
    elif case == "unique":
        catalog = _catalog(
            skills=(
                _skill("alpha", best_for="feature build endpoint"),
                _skill("zeta", description="feature"),
            )
        )
        task = "feature build endpoint"
    elif case == "tie":
        catalog = _catalog(
            skills=(
                _skill("zeta", best_for="feature build endpoint"),
                _skill("alpha", best_for="feature build endpoint"),
            )
        )
        task = "feature build endpoint"
    elif case == "low-shape":
        catalog = _catalog(shapes=(_shape("feature", normal=("feature",)),))
        task = "feature"
    else:
        catalog = _catalog()
        task = "feature build endpoint"
        kwargs["required_procedures"] = ("plan-feature", "fix-workflow")

    decision = _dispatch(task, catalog, reads, **kwargs)

    assert decision["outcome"] == expected_outcome
    assert reads.names == (["alpha"] if case == "unique" else [])


def test_answered_clarification_precedes_generic_explicit_selection() -> None:
    catalog = _catalog(aliases={"feature-plan-v1": "plan-feature"})
    reads = BodyReads()

    decision = _dispatch(
        "feature build endpoint",
        catalog,
        reads,
        explicit_name="fix-workflow",
        clarification_answer="feature-plan-v1",
        prior_clarification_id="123e4567-e89b-42d3-a456-426614174000",
    )

    assert decision["outcome"] == "selected"
    assert decision["selection"]["canonical_name"] == "plan-feature"
    assert decision["selection"]["public_name"] == "feature-plan-v1"
    assert decision["selection"]["selection_basis"] == "user_confirmed"
    assert decision["selection"]["clarification_id"] == (
        "123e4567-e89b-42d3-a456-426614174000"
    )
    assert reads.names == ["plan-feature"]


def test_explicit_valid_bypasses_advisory_low_confidence_but_invalid_fails_closed() -> None:
    catalog = _catalog(shapes=(_shape("feature", normal=("feature",)),))
    reads = BodyReads()

    selected = _dispatch(
        "feature", catalog, reads, explicit_name="plan-feature"
    )
    invalid = _dispatch(
        "feature", catalog, reads, explicit_name="unknown-procedure"
    )

    assert selected["outcome"] == "selected"
    assert selected["selection"]["selection_basis"] == "user_explicit"
    assert invalid == {
        "outcome": "error",
        "selection": None,
        "clarification": None,
        "error": "explicit_unknown_or_incompatible_name",
    }
    assert reads.names == ["plan-feature"]


def test_confirmed_multi_procedure_sequence_selects_only_requested_step() -> None:
    catalog = _catalog()
    reads = BodyReads()

    decision = _dispatch(
        "feature build endpoint",
        catalog,
        reads,
        required_procedures=("fix-workflow", "plan-feature"),
        confirmed_sequence=True,
        sequence_step=2,
        prior_clarification_id="123e4567-e89b-42d3-a456-426614174000",
    )

    assert decision["outcome"] == "selected"
    assert decision["selection"]["canonical_name"] == "plan-feature"
    assert decision["selection"]["selection_basis"] == "user_confirmed"
    assert decision["selection"]["sequence_step"] == 2
    assert reads.names == ["plan-feature"]


def test_malformed_router_and_trust_profile_catalog_binding_errors_fail_closed() -> None:
    catalog = _catalog()
    reads = BodyReads()
    shape_result = route_shape("feature build endpoint", catalog)
    shape_result["router_id"] = "forged-router"

    malformed = _dispatch(
        "feature build endpoint", catalog, reads, shape_result=shape_result
    )
    missing_trust = _dispatch("feature build endpoint", None, reads)
    zero_compatible = _dispatch(
        "feature build endpoint",
        _catalog(
            skills=(
                _skill("alpha", best_for="feature", exclusions=("binding_incompatible",)),
            )
        ),
        reads,
    )

    assert malformed["outcome"] == "error"
    assert malformed["error"] == "malformed_router_result"
    assert missing_trust["outcome"] == "error"
    assert missing_trust["error"] == "unverified_routing_catalog"
    assert zero_compatible["outcome"] == "error"
    assert zero_compatible["error"] == "no_compatible_candidate"
    assert reads.names == []


def test_structural_validator_seam_rejects_unknown_router_fields() -> None:
    catalog = _catalog()
    reads = BodyReads()
    shape_result = route_shape("feature build endpoint", catalog)
    shape_result["unknown"] = True

    def reject_unknown(name: str, document: dict[str, object]) -> None:
        if "unknown" in document:
            raise RoutingContractError(f"{name}: unknown field")

    decision = _dispatch(
        "feature build endpoint",
        catalog,
        reads,
        shape_result=shape_result,
        validate_contract=reject_unknown,
    )

    assert decision["outcome"] == "error"
    assert reads.names == []


def test_candidate_and_input_order_never_break_ties_or_change_replay() -> None:
    shapes = (
        _shape("zeta", strong=("feature", "build")),
        _shape("alpha", strong=("feature", "build")),
    )
    skills = (
        _skill("zeta", best_for="feature build endpoint"),
        _skill("alpha", best_for="feature build endpoint"),
    )
    forward = _catalog(shapes=shapes, skills=skills)
    reverse = _catalog(shapes=tuple(reversed(shapes)), skills=tuple(reversed(skills)))
    reads = BodyReads()

    first_shape = route_shape("feature build endpoint", forward)
    second_shape = route_shape("feature build endpoint", reverse)
    first_skill = route_skill("feature build endpoint", forward)
    second_skill = route_skill("feature build endpoint", reverse)
    first_dispatch = _dispatch("feature build endpoint", forward, reads)
    replay_dispatch = _dispatch("feature build endpoint", reverse, reads)

    assert first_shape == second_shape
    assert first_skill == second_skill
    assert first_dispatch == replay_dispatch
    assert first_dispatch["outcome"] == "clarification_required"
    assert reads.names == []


def test_dispatcher_rejects_structurally_valid_score_forgery_before_loading() -> None:
    catalog = _catalog()
    reads = BodyReads()
    skill_result = route_skill("feature build endpoint", catalog)
    forged = copy.deepcopy(skill_result)
    forged["candidates"][0]["score"] += 100

    decision = _dispatch(
        "feature build endpoint", catalog, reads, skill_result=forged
    )

    assert decision["outcome"] == "error"
    assert decision["error"] == "router_result_mismatch"
    assert reads.names == []


def test_selected_body_hash_mismatch_is_error_not_fallback() -> None:
    catalog = _catalog()

    def reads(_name: str) -> bytes:
        return b"tampered"

    decision = dispatch_selection(
        "feature build endpoint", catalog, load_procedure=reads
    )

    assert decision["outcome"] == "error"
    assert decision["error"] == "selected_procedure_hash_mismatch"


def test_selected_loader_returns_and_checks_rendered_body_when_hashes_differ() -> None:
    skill = _skill("plan-feature", best_for="feature build endpoint")
    skill["source_sha256"] = HASH
    skill["rendered_sha256"] = PROCEDURE_HASH
    catalog = _catalog(skills=(skill,))
    reads = BodyReads()

    decision = dispatch_selection(
        "feature build endpoint", catalog, load_procedure=reads
    )

    assert decision["outcome"] == "selected"
    assert decision["selection"]["source_sha256"] == HASH
    assert decision["selection"]["rendered_sha256"] == PROCEDURE_HASH
    assert decision["selection"]["procedure_body_kind"] == "rendered"
    assert decision["selection"]["procedure_body"] == PROCEDURE_BODY
