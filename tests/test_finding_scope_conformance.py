"""All-producer conformance for normalized findings and scan-scope adapters."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".claude" / "skills" / "which-cleanup" / "scripts"
CONTRACT = ROOT / ".claude" / "skills" / "_common" / "scan_scope_contracts.json"


def _load(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"scope_conformance_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _request(mode: str):
    scan_request = _load("scan_request")
    if mode == "paths":
        return scan_request.ScanRequest(
            project_root="/tmp/project",
            requested_mode=mode,
            selector={"kind": "paths", "paths": ["src/app.py"]},
            content_basis="working-tree",
            line_filter_safe=None,
            changes=(
                scan_request.PathChange(
                    path="src/app.py",
                    change_type="explicit",
                    old_path=None,
                    current_exists=True,
                    binary=False,
                    line_ranges=(),
                ),
            ),
        )
    if mode == "project":
        return scan_request.ScanRequest(
            project_root="/tmp/project",
            requested_mode=mode,
            selector={"kind": "project"},
            content_basis="working-tree",
            line_filter_safe=None,
            changes=(),
        )
    return scan_request.ScanRequest(
        project_root="/tmp/project",
        requested_mode=mode,
        selector={"kind": "working-tree"},
        content_basis="working-tree",
        line_filter_safe=True,
        changes=(
            scan_request.PathChange(
                path="src/app.py",
                change_type="modified",
                old_path=None,
                current_exists=True,
                binary=False,
                line_ranges=(scan_request.LineRange(5, 5),),
            ),
        ),
    )


def _raw(line: int | None, *, subject: str = "app:example") -> dict:
    return {
        "kind": "example",
        "subject": subject,
        "path": "src/app.py",
        "line_start": line,
        "line_end": line,
        "evidence": {"summary": "bounded fake evidence"},
        "completeness": "complete",
        "detail": {"source": "conformance-fixture"},
    }


def test_every_producer_target_mode_conforms_through_declared_adapter() -> None:
    envelope = _load("finding_envelope")
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    exercised = set()

    for contract in payload["skills"]:
        default_request = replace(
            _request(contract["target_default_mode"]), requested_mode="auto"
        )
        default_result = envelope.build_finding_artifact(
            detector=contract["skill"],
            detector_version="fixture-v1",
            raw_findings=[_raw(5)],
            request=default_request,
            contract=contract,
            supported_modes_field="target_modes",
            allow_compatible_widening=False,
        )
        assert default_result["scan"]["effective_mode"] == contract[
            "target_default_mode"
        ]
        assert default_result["scan"]["status"] == "ready"
        exercised.add((contract["skill"], "auto"))

        for mode in contract["target_modes"]:
            request = _request(mode)
            result = envelope.build_finding_artifact(
                detector=contract["skill"],
                detector_version="fixture-v1",
                raw_findings=[_raw(5), _raw(20, subject="app:outside")],
                request=request,
                contract=contract,
                supported_modes_field="target_modes",
                allow_compatible_widening=False,
            )

            trigger_widens = (
                contract["diff_semantics"] == "trigger-analysis"
                and mode == "changed-files"
            )
            assert result["scan"]["status"] == (
                "widened" if trigger_widens else "ready"
            )
            assert result["scan"]["effective_mode"] == (
                "project" if trigger_widens else mode
            )
            assert result["scan"]["adapter"] == envelope.adapter_kind(contract)
            assert result["scan_request"] == request.to_dict()
            assert result["metrics"]["raw_finding_count"] == 2
            expected = 1 if mode == "diff-lines" else 2
            assert result["metrics"]["actionable_finding_count"] == expected
            exercised.add((contract["skill"], mode))

    assert len(exercised) == len(payload["skills"]) + sum(
        len(contract["target_modes"]) for contract in payload["skills"]
    )


def test_unclaimed_direct_mode_returns_structured_refusal() -> None:
    envelope = _load("finding_envelope")
    contracts = json.loads(CONTRACT.read_text(encoding="utf-8"))["skills"]
    contract = next(row for row in contracts if row["skill"] == "find-duplication")

    result = envelope.build_finding_artifact(
        detector=contract["skill"],
        detector_version="fixture-v1",
        raw_findings=[_raw(5)],
        request=_request("diff-lines"),
        contract=contract,
        supported_modes_field="target_modes",
        allow_compatible_widening=False,
    )

    assert result["scan"] == {
        "adapter": "path-seed",
        "diff_semantics": "seed-analysis",
        "effective_mode": None,
        "reason": "scope_mode_not_supported",
        "requested_mode": "diff-lines",
        "selector": {"kind": "working-tree"},
        "status": "unsupported",
        "supported_modes": ["changed-files", "paths", "project"],
    }
    assert result["findings"] == []
    assert result["metrics"]["incomplete_or_error_count"] == 1


def test_unlocated_line_finding_is_preserved_for_review_not_silently_filtered() -> None:
    envelope = _load("finding_envelope")
    contract = next(
        row
        for row in json.loads(CONTRACT.read_text(encoding="utf-8"))["skills"]
        if row["skill"] == "find-comment-drift"
    )

    result = envelope.build_finding_artifact(
        detector=contract["skill"],
        detector_version="fixture-v1",
        raw_findings=[_raw(None)],
        request=_request("diff-lines"),
        contract=contract,
        supported_modes_field="target_modes",
        allow_compatible_widening=False,
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0]["scope_attribution"] == "unlocated-review-required"
    assert result["metrics"]["scope_filtered_count"] == 0
    assert result["metrics"]["incomplete_or_error_count"] == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.pop("subject"),
        lambda row: row.update(line_start=0),
        lambda row: row.update(line_start=8, line_end=3),
        lambda row: row.update(completeness="clean-ish"),
        lambda row: row.update(evidence="not-an-object"),
    ],
)
def test_invalid_finding_envelopes_fail_closed(mutation) -> None:
    envelope = _load("finding_envelope")
    contract = next(
        row
        for row in json.loads(CONTRACT.read_text(encoding="utf-8"))["skills"]
        if row["skill"] == "find-comment-drift"
    )
    finding = _raw(5)
    mutation(finding)

    with pytest.raises(envelope.FindingEnvelopeError):
        envelope.build_finding_artifact(
            detector=contract["skill"],
            detector_version="fixture-v1",
            raw_findings=[finding],
            request=_request("diff-lines"),
            contract=contract,
            supported_modes_field="target_modes",
            allow_compatible_widening=False,
        )


def test_copied_router_scope_adapter_runs_without_repository_imports(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "installed" / "which-cleanup"
    shutil.copytree(SCRIPTS.parent, copied)
    runner = tmp_path / "runner.py"
    runner.write_text(
        "import json, sys\n"
        f"sys.path.insert(0, {str(copied / 'scripts')!r})\n"
        "from finding_envelope import build_finding_artifact\n"
        "from scan_request import LineRange, PathChange, ScanRequest\n"
        "request = ScanRequest('/tmp/project', 'diff-lines', "
        "{'kind': 'working-tree'}, 'working-tree', True, "
        "(PathChange('src/app.py', 'modified', None, True, False, "
        "(LineRange(5, 5),)),))\n"
        "contract = {'skill': 'find-comment-drift', "
        "'current_modes': ['diff-lines', 'changed-files', 'paths', 'project'], "
        "'target_modes': ['diff-lines', 'changed-files', 'paths', 'project'], "
        "'current_default_mode': 'paths', 'target_default_mode': 'paths', "
        "'finding_granularity': 'line', 'diff_semantics': 'filter-findings', "
        "'behavior_family': 'line-local'}\n"
        "artifact = build_finding_artifact(detector='find-comment-drift', "
        "detector_version='copied-v1', raw_findings=[{'kind': 'example', "
        "'subject': 'app:example', 'path': 'src/app.py', 'line_start': 5, "
        "'line_end': 5, 'evidence': {}, 'completeness': 'complete'}], "
        "request=request, contract=contract)\n"
        "print(json.dumps(artifact, sort_keys=True))\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-I", "-S", str(runner)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    artifact = json.loads(result.stdout)
    assert artifact["scan"]["adapter"] == "line-filter"
    assert artifact["metrics"]["actionable_finding_count"] == 1
