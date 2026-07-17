from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from _lib.finding_identity import FindingIdentity, finding_record
from sweep import schemas
from sweep.serialization import canonical_json_bytes, canonical_sha256
from sweep_shims import resolve_shims


ROOT = Path(__file__).resolve().parent.parent
ORACLE = ROOT / "tests" / "fixtures" / "sweep" / "prototype-oracle"


def _load(name: str) -> dict:
    return json.loads(ORACLE.joinpath(name).read_text(encoding="utf-8"))


def test_ar_1_copied_prototype_oracle_pins_determinism_digest_and_ratchet_semantics():
    manifest_path = ORACLE / "prototype-manifest.json"
    manifest = _load("prototype-manifest.json")
    evidence = _load("characterization.json")["ar_1"]
    digest_path = ORACLE / "prototype-digest.md"
    digest = digest_path.read_text(encoding="utf-8")

    assert manifest["total"] == 6
    assert manifest["counts"] == {"cx": 6}
    assert [row["id"] for row in manifest["findings"]] == [
        "011a6cd88c34",
        "dac219221c4c",
        "f564686bc6fe",
        "557518c5e120",
        "ca5f84f3f00b",
        "529e4d595d50",
    ]
    assert evidence["candidate_families"] == ["cx", "omnibus", "ruff", "strdisp"]
    assert (evidence["fixed"], evidence["new"], evidence["persisting"]) == (
        ["fixed-id"],
        ["new-id"],
        ["persist-id"],
    )
    assert all(evidence["ratchet"].values())
    assert digest.count("\n- `") == 1
    assert "… 5 more (see manifest)" in digest
    assert evidence["source_manifest_sha256"] == (
        "c89752953b3d8a8d37ae3553e8e9c11ba9a8a31effd18f382beb0b2659d7dfe9"
    )
    assert manifest["target"] == evidence["copy_normalization"]["target"]
    assert evidence["copy_normalization"]["reason"] == "machine-local absolute target redacted"
    assert hashlib.sha256(manifest_path.read_bytes().removesuffix(b"\n")).hexdigest() == evidence[
        "copied_manifest_sha256"
    ]
    assert hashlib.sha256(digest_path.read_bytes()).hexdigest() == evidence[
        "source_digest_sha256"
    ]


def test_ar_2_prototype_defects_are_reversal_oracles_not_accepted_schemas():
    evidence = _load("characterization.json")["ar_2"]
    assert set(evidence["reverse_not_preserve"]) == {
        "sha1_identity",
        "hard_coded_provider_paths",
        "silent_json_failure",
        "failed_scan_exit_zero",
        "raw_count_consumption",
        "executor_adjacent_verification",
    }
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate_manifest(_load("prototype-manifest.json"))
    assert schemas.validate_manifest(
        _load("prototype-manifest.json"), allow_prototype=True
    )["total"] == 6


def test_ar_3_identity_v2_oracles_and_manifest_collision_rejection():
    base = dict(
        provider="ruff",
        rule="F401:v1",
        language="python",
        path="src/example.py",
        semantic_anchor="native:F401:unused-import",
    )
    first = FindingIdentity(**base, occurrence=0, case_sensitive=True)
    repeated = FindingIdentity(**base, occurrence=1, case_sensitive=True)

    assert first.identifier() != repeated.identifier()
    assert finding_record(first, tool_version="1", line=1)["id"] == finding_record(
        first, tool_version="2", line=999
    )["id"]

    manifest = copy.deepcopy(_load("schema-cases.json")["good"]["manifest"])
    duplicate = copy.deepcopy(manifest["findings"][0])
    duplicate["message"] = "unequal payload under the same ID"
    manifest["findings"].append(duplicate)
    manifest["total"] = 2
    manifest["counts"] = {"ruff": 2}
    with pytest.raises(schemas.SchemaValidationError, match="duplicate finding id"):
        schemas.validate_manifest(manifest)


def test_ar_4_resolution_stays_registry_driven_without_activation_manifest_coupling():
    resolved = resolve_shims(["typescript", "rust", "go", "css"])
    source = ROOT.joinpath("scripts/sweep_shims.py").read_text(encoding="utf-8")

    assert resolved["typescript"]["provider"] == "typescript-syntax"
    assert resolved["rust"]["provider"] == "cargo"
    assert resolved["go"]["provider"] == "go-toolchain"
    assert resolved["css"] == {"status": "unsupported"}
    assert "capability_registry" in source
    assert "import manifest" not in source
    assert "Enum" not in source


def test_ar_5_parser_fixture_behavior_stays_frozen_after_slice_5_promotion():
    evidence = _load("characterization.json")["ar_5"]

    assert evidence == {
        "complexity_bad_findings": 6,
        "complexity_good_findings": 0,
        "omnibus_fixture_cases": 4,
        "invalid_python_currently_becomes_clean_zero": True,
        "required_reversal": "typed_provider_failure",
    }
    sweep_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(ROOT.joinpath("scripts/sweep").glob("*.py"))
    )
    assert "find-complexity-hotspots" in sweep_sources
    assert "find-omnibus" in sweep_sources
    assert ".claude/tasks/sweep-prototype" not in sweep_sources


def test_ar_6_judgment_and_packet_schemas_are_manifest_bound_and_non_nullable():
    cases = _load("schema-cases.json")
    evidence = _load("characterization.json")["ar_6"]

    assert evidence["legacy_projection_tests_passed"] == 21
    assert schemas.validate_judgment(cases["good"]["judgment"])["manifest_hash"]
    assert schemas.validate_packet(cases["good"]["packet"])["finding_ids"]
    nullable = copy.deepcopy(cases["good"]["packet"])
    nullable.update(scope=[], verification=None, expected_delta=None, token_budget=None)
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate_packet(nullable)


def test_ar_7_activation_and_sweep_manifests_have_distinct_schema_boundaries():
    cases = _load("schema-cases.json")

    assert schemas.validate_manifest(cases["good"]["manifest"])["schema_version"] == 1
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate_manifest({"version": 1, "skills": {}})
    assert schemas.DEFAULT_MANIFEST_PATH == ".engineering/sweep/manifest.json"
    assert schemas.DEFAULT_MANIFEST_PATH != ".engineering/manifest.json"


def test_ar_8_failed_empty_observation_is_not_a_completed_clean_manifest():
    cases = _load("schema-cases.json")
    completed = schemas.validate_provider_observation(cases["good"]["provider_observation"])
    failed = schemas.validate_provider_observation(cases["good"]["failed_provider_observation"])

    assert completed["status"] == "completed"
    assert failed["status"] == "failed"
    assert failed["failure"]["kind"] == "parse_failure"

    failed_manifest = copy.deepcopy(cases["good"]["manifest"])
    failed_manifest.update(providers=[failed], findings=[], counts={}, total=0, status="failed")
    with pytest.raises(schemas.SchemaValidationError, match="publish a sweep manifest"):
        schemas.validate_manifest(failed_manifest)


def test_ar_9_provider_schema_retains_native_location_version_and_raw_hashes():
    cases = _load("schema-cases.json")
    evidence = _load("characterization.json")["ar_9"]
    provider = schemas.validate_provider_observation(cases["good"]["provider_observation"])
    finding = schemas.validate_manifest(cases["good"]["manifest"])["findings"][0]

    assert finding["native_rule_id"] == evidence["native_rule"]
    assert finding["location"]["line"] == evidence["line"]
    assert finding["location"]["column"] == evidence["start_column"]
    assert finding["location"]["end_column"] == evidence["end_column"]
    assert provider["tool_version"] == "0.6.9"
    assert provider["raw"]["stdout_sha256"] == evidence["stdout_sha256"]
    assert provider["raw"]["stderr_sha256"] == evidence["stderr_sha256"]


def test_ar_10_slice_zero_detection_contract_has_no_network_or_model_surface():
    evidence = _load("characterization.json")["ar_10"]
    forbidden = ("anthropic", "httpx", "openai", "requests", "socket", "urllib")
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(ROOT.joinpath("scripts/sweep").glob("*.py"))
        if path.name != "provider_process.py"
    )

    assert evidence["detection_is_agent_free"] is True
    assert not any(token in source for token in forbidden)


def test_ar_11_executor_self_attestation_is_not_a_valid_packet_or_verification():
    evidence = _load("characterization.json")["ar_11"]
    fake = {"verification": evidence["executor_claim"], "status": "done"}

    assert evidence["required_result"] == "reject"
    assert evidence["has_harness_manifest"] is False
    assert evidence["has_harness_diff"] is False
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate_packet(fake)


def test_ar_12_wp5_does_not_take_adr_0003_or_ac_8_9_ownership():
    evidence = _load("characterization.json")["ar_12"]
    adr = ROOT.joinpath("ai-docs/decisions/0003-canonical-findings-ledger.md").read_text(
        encoding="utf-8"
    )
    plan = ROOT.joinpath("ai-docs/plans/portable-skill-ecosystem-completion.md").read_text(
        encoding="utf-8"
    )

    assert evidence["wp5_may_change"] == ["0036", "0040"]
    assert evidence["wp5_must_not_own"] == ["0003", "AC-8.9"]
    assert "status: proposed" in adr
    assert "pending:portable-skill-ecosystem-completion AC-8.9 formal disposition" in adr
    assert "0026 → 0027 → 0028 → 0029/0030 → 0003" in " ".join(plan.split())


# spec:portable-batch-sweep::IM-16
def test_im_16_decision_embodiment_names_only_productized_paths() -> None:
    def frontmatter(decision: str) -> dict[str, object]:
        source = ROOT.joinpath("ai-docs/decisions", decision).read_text(encoding="utf-8")
        return yaml.safe_load(source.split("---", 2)[1])

    sweep = frontmatter("0036-batch-sweep-harness.md")
    identity = frontmatter("0040-stable-finding-identity-v2.md")
    ledger = frontmatter("0003-canonical-findings-ledger.md")

    assert sweep["applies_to"] == [
        "scripts/sweep/",
        "scripts/sweep_shims.py",
        "scripts/status.py",
        "scripts/queue_status.py",
    ]
    assert sweep["embodied_by"] == [
        "script:scripts/sweep/__main__.py",
        "script:scripts/sweep/commands.py",
        "script:scripts/sweep/manifest.py",
        "script:scripts/sweep/pipeline.py",
        "script:scripts/sweep_shims.py",
        "script:scripts/status.py",
        "script:scripts/queue_status.py",
        "contract:tests/test_sweep_cli.py",
        "contract:tests/test_sweep_manifest.py",
        "contract:tests/test_sweep_pipeline.py",
        "contract:tests/test_sweep_live_pipeline.py",
    ]
    assert identity["applies_to"] == [
        "scripts/_lib/finding_identity.py",
        "scripts/sweep/manifest.py",
    ]
    assert identity["embodied_by"] == [
        "script:scripts/_lib/finding_identity.py",
        "script:scripts/sweep/manifest.py",
        "contract:tests/test_finding_identity.py",
        "contract:tests/test_sweep_manifest.py",
    ]
    assert not any(
        str(value).startswith("pending:")
        for decision in (sweep, identity)
        for value in decision["embodied_by"]
    )
    assert ledger["status"] == "proposed"
    assert ledger["embodied_by"] == [
        "pending:portable-skill-ecosystem-completion AC-8.9 formal disposition"
    ]


def test_im_2_adversarial_bad_schemas_are_rejected_before_good_schemas():
    cases = _load("schema-cases.json")
    validators = {
        "manifest": schemas.validate_manifest,
        "provider_observation": schemas.validate_provider_observation,
        "diff": schemas.validate_diff,
        "judgment": schemas.validate_judgment,
        "packet": schemas.validate_packet,
        "failure": schemas.validate_failure,
    }

    attempted: list[str] = []
    for case in cases["bad"]:
        attempted.append(f"bad:{case['name']}")
        with pytest.raises(schemas.SchemaValidationError):
            validators[case["schema"]](case["document"])

    for attack in cases["unknown_field_attacks"]:
        attempted.append(f"bad:unknown-{attack['schema']}")
        attacked = copy.deepcopy(cases["good"][attack["schema"]])
        target = attacked
        for component in attack["path"]:
            target = target[component]
        target[attack["field"]] = True
        with pytest.raises(schemas.SchemaValidationError, match="unknown fields"):
            validators[attack["schema"]](attacked)

    for name in ("failure", "provider_observation", "diff", "judgment", "packet", "manifest"):
        attempted.append(f"good:{name}")
        validators[name](cases["good"][name])

    first_good = next(index for index, value in enumerate(attempted) if value.startswith("good:"))
    assert all(value.startswith("bad:") for value in attempted[:first_good])


def test_im_2_canonical_json_and_hash_helpers_are_byte_deterministic():
    left = {"z": [3, 2, 1], "a": {"two": 2, "one": 1}}
    right = {"a": {"one": 1, "two": 2}, "z": [3, 2, 1]}

    encoded = canonical_json_bytes(left)
    assert encoded == canonical_json_bytes(right)
    assert encoded.endswith(b"\n")
    assert encoded == b'{"a":{"one":1,"two":2},"z":[3,2,1]}\n'
    assert canonical_sha256(left) == canonical_sha256(right)
    assert canonical_sha256(left) == hashlib.sha256(encoded).hexdigest()
