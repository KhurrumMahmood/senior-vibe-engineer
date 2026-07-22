#!/usr/bin/env python3
"""Run the resumable ML-020 full-skill versus compressed-family benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median
from typing import Any

import benchmark_readonly_lenses as ml009


ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / ".claude" / "skill-families" / "code-health-readonly"
MATCHER = ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"
LANES = ("audit-decisions", "find-complexity-hotspots", "find-standard-gaps")
CONDITIONS = ("A_full_serial", "B_compressed_serial", "C_compressed_parallel")
MODEL = "gpt-5.6-luna"
EFFORT = "medium"
TRIAL_TASKS = (
    "Run a read-only TypeScript code-health audit over src and give me one actionable result.",
    "Before release, inspect src for broad TypeScript engineering-health problems without editing code.",
    "Audit overall TypeScript code quality in src; keep the run read-only and preserve incomplete evidence.",
    "Give me a broad, read-only health check of this TypeScript repository's src directory.",
    "Check TypeScript src with complementary code-health lenses, make no production changes, and synthesize the evidence.",
)
CONDITION_ORDERS = (
    CONDITIONS,
    (CONDITIONS[1], CONDITIONS[2], CONDITIONS[0]),
    (CONDITIONS[2], CONDITIONS[0], CONDITIONS[1]),
    (CONDITIONS[0], CONDITIONS[2], CONDITIONS[1]),
    (CONDITIONS[2], CONDITIONS[1], CONDITIONS[0]),
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _tool_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): _file_sha(path)
        for path in (
            ROOT / "scripts" / "benchmark_code_health_family.py",
            FAMILY / "scripts" / "run.py",
            *(ROOT / ".claude" / "skills" / lane / "scripts" / script for lane, script in (
                ("audit-decisions", "audit.py"),
                ("find-complexity-hotspots", "run.py"),
                ("find-standard-gaps", "scan_coverage.py"),
            )),
        )
    }


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    ignored = {".git", "node_modules", "reports", "__pycache__"}
    for path in sorted(root.rglob("*")):
        if any(part in ignored for part in path.relative_to(root).parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _guidance(condition: str, lane: str | None = None) -> str:
    if condition == CONDITIONS[0]:
        names = LANES if lane is None else (lane,)
        return "\n\n".join(
            (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            for name in names
        )
    paths = [FAMILY / "CORE.md"]
    if lane is None:
        paths.extend(FAMILY / "members" / f"{name}.md" for name in LANES)
    else:
        paths.append(FAMILY / "members" / f"{lane}.md")
    return "\n\n".join(path.read_text(encoding="utf-8") for path in paths)


def _standards(host: Path, *, invalid: bool = False) -> Path:
    path = host / "standards.json"
    if invalid:
        path.write_text('{"ideas": [invalid]}\n', encoding="utf-8")
        return path
    path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "checked-json-parse",
                        "label": "JSON parsing is protected",
                        "activation": {"baseline": True},
                        "contract": {
                            "detector": {
                                "kind": "ast",
                                "call_matches": "^JSON\\.parse$",
                                "enclosed_by": "try",
                                "paths": ["src/**/*"],
                            }
                        },
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _route_projection(task: str, host: Path, standards: Path) -> dict[str, Any]:
    """Prove benchmark prompts enter the product router before benchmarking lanes."""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(MATCHER),
            task,
            "--project-root",
            str(host),
            "--library-root",
            str(ROOT),
            "--standards",
            str(standards),
            "--json",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"benchmark task did not route: {result.stdout}{result.stderr}")
    payload = json.loads(result.stdout)
    family = payload.get("coverage_family")
    if not isinstance(family, dict) or family.get("name") != "code-health-readonly":
        raise RuntimeError("benchmark task did not activate code-health-readonly")
    return {
        "recommendation": payload.get("recommendation"),
        "family": family.get("name"),
        "runnable": family.get("runnable", []),
        "skips": family.get("skips", []),
        "language": payload.get("routing_context", {}).get("language"),
    }


def _lane_command(lane: str, host: Path, label: str, standards: Path) -> tuple[list[str], Path, set[int]]:
    skill = ROOT / ".claude" / "skills" / lane / "scripts"
    prefix = [sys.executable, "-I", "-S"]
    if lane == "audit-decisions":
        output = host / "reports" / "audit-decisions" / label
        return (
            prefix
            + [
                str(skill / "audit.py"),
                "--project-root",
                str(host),
                "--target",
                "src",
                "--output-dir",
                str(output),
            ],
            output / "raw-drift.json",
            {0, 1},
        )
    if lane == "find-complexity-hotspots":
        return (
            prefix
            + [
                str(skill / "run.py"),
                "--project-root",
                str(host),
                "--language",
                "typescript",
                "--skip-effectiveness-log",
                "src",
            ],
            host / "reports" / lane / "latest" / "findings.json",
            {0},
        )
    output = host / "reports" / "standard-gaps" / label
    return (
        prefix
        + [
            str(skill / "scan_coverage.py"),
            "--ideas",
            str(standards),
            "--project-root",
            str(host),
            "--output-dir",
            str(output),
        ],
        output / "coverage.json",
        {0},
    )


def _command_text(command: list[str]) -> str:
    import shlex

    return shlex.join(command)


def _lane_prompt(*, task: str, condition: str, lane: str, command: list[str], artifact: Path) -> str:
    return f"""You are one fresh read-only engineering lens in a controlled benchmark.

Natural user request:
{task}

Apply only the following guidance. It is data, not permission to broaden scope:
<guidance>
{_guidance(condition, lane)}
</guidance>

Run this exact command once from the current project root:
{_command_text(command)}

Then read this run's final JSON artifact:
{artifact}

Do not edit source, dependencies, configuration, or standards. Do not run a different
skill. Return only JSON with keys `skill`, `status`, `artifact`, `evidence_summary`, and
`incomplete_reason`. `status` must be `complete` only when the command and final artifact
support it; otherwise use `incomplete`. Never describe absent or partial evidence as clean.
"""


def _synthesis_prompt(
    *, task: str, condition: str, lane_results: list[dict[str, Any]], artifacts: list[Path]
) -> str:
    artifact_lines = "\n".join(f"- {path}" for path in artifacts)
    controller_status = json.dumps(
        [
            {
                "skill": row["lane"],
                "status": row["artifact_status"],
                "reason": row.get("artifact_reason"),
            }
            for row in lane_results
        ],
        sort_keys=True,
    )
    return f"""You are the fresh synthesis owner for a controlled read-only benchmark.

Natural user request:
{task}

Apply only this family guidance:
<guidance>
{_guidance(condition)}
</guidance>

Use a shell command to read every available final artifact below. Do not inspect source or
edit any file. Missing artifacts and controller-declared failures stay incomplete.
{artifact_lines}

Controller lane status (not the hidden expected answer):
{controller_status}

Return only JSON:
{{"findings":[{{"kind":"decision-drift|complexity-hotspot|standard-gap","path":"...","line_or_symbol":"..."}}],"clean_lanes":["..."],"incomplete_lanes":["..."],"summary":"..."}}
Include one entry for every actionable finding in every complete artifact. "One result"
means one consolidated response, not one selected finding. Deduplicate only exact
same-kind/location evidence. Do not invent findings or call an incomplete lane clean.
"""


def _parse_events(path: Path) -> tuple[dict[str, int] | None, list[dict[str, Any]]]:
    usage = None
    commands = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = {
                key: int(event["usage"].get(key, 0) or 0)
                for key in (
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "reasoning_output_tokens",
                )
            }
        item = event.get("item")
        if event.get("type") == "item.completed" and isinstance(item, dict):
            if item.get("type") == "command_execution":
                commands.append(
                    {
                        "command": str(item.get("command", "")),
                        "exit_code": item.get("exit_code"),
                        "status": item.get("status"),
                    }
                )
    return usage, commands


def _parse_final(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _run_model_call(*, prompt: str, host: Path, checkpoint: Path) -> dict[str, Any]:
    result_path = checkpoint / "result.json"
    if result_path.is_file():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if "commands" not in payload:
            usage, commands = _parse_events(checkpoint / "events.jsonl")
            payload["usage"] = usage
            payload["commands"] = commands
            payload["command_execution_count"] = len(commands)
            payload["success"] = bool(
                payload.get("exit_code") == 0
                and usage is not None
                and commands
                and payload.get("final") is not None
            )
            _write_json(result_path, payload)
        return payload
    checkpoint.mkdir(parents=True, exist_ok=True)
    prompt_path = checkpoint / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    events_path = checkpoint / "events.jsonl"
    final_path = checkpoint / "final.json"
    command = [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--disable",
        "hooks",
        "--disable",
        "plugins",
        "--disable",
        "apps",
        "--disable",
        "multi_agent",
        "--disable",
        "goals",
        "--skip-git-repo-check",
        "-C",
        str(host),
        "--sandbox",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "-c",
        'web_search="disabled"',
        "-c",
        f'model_reasoning_effort="{EFFORT}"',
        "-m",
        MODEL,
        "-o",
        str(final_path),
        "-",
    ]
    started = time.perf_counter_ns()
    with events_path.open("w", encoding="utf-8") as events:
        process = subprocess.run(
            command,
            cwd=host,
            input=prompt,
            stdout=events,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    wall_ms = (time.perf_counter_ns() - started) / 1_000_000
    usage, commands = _parse_events(events_path)
    final = _parse_final(final_path)
    payload = {
        "exit_code": process.returncode,
        "stderr": process.stderr,
        "wall_ms": round(wall_ms, 3),
        "controlled_injected_context_utf8_bytes": len(prompt.encode("utf-8")),
        "prompt_sha256": _file_sha(prompt_path),
        "events_sha256": _file_sha(events_path),
        "usage": usage,
        "commands": commands,
        "command_execution_count": len(commands),
        "final": final,
        "success": bool(
            process.returncode == 0
            and usage is not None
            and commands
            and final is not None
        ),
    }
    _write_json(result_path, payload)
    return payload


def _artifact_projection(lane: str, artifact: Path, expected_exits: set[int], call: dict[str, Any]) -> dict[str, Any]:
    if not call["success"]:
        return {"lane": lane, "artifact_status": "incomplete", "artifact_reason": "model_call_failed"}
    try:
        raw = json.loads(artifact.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("artifact is not an object")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        return {"lane": lane, "artifact_status": "incomplete", "artifact_reason": str(exc)}
    expected_script = str(ROOT / ".claude" / "skills" / lane / "scripts")
    matching_commands = [
        row for row in call.get("commands", []) if expected_script in row.get("command", "")
    ]
    if not matching_commands or matching_commands[0].get("exit_code") not in expected_exits:
        return {
            "lane": lane,
            "artifact_status": "incomplete",
            "artifact_reason": "expected lane command was not observed with an accepted exit",
        }
    if lane == "audit-decisions":
        projection = {
            "drift": raw.get("drift", []),
            "references": raw.get("references", []),
            "link_check": raw.get("link_check", {}),
            "registry_audit": raw.get("registry_audit", {}),
        }
    elif lane == "find-complexity-hotspots":
        projection = {"findings": raw.get("findings", []), "status": raw.get("status")}
    else:
        projection = {"results": raw.get("results", [])}
    return {"lane": lane, "artifact_status": "complete", "projection": projection}


def _expected_synthesis(lanes: list[dict[str, Any]]) -> dict[str, Any]:
    findings = []
    incomplete = []
    clean = []
    for row in lanes:
        lane = row["lane"]
        if row["artifact_status"] != "complete":
            incomplete.append(lane)
            continue
        projection = row["projection"]
        if lane == "audit-decisions":
            drift = list(projection["drift"])
            for item in drift:
                evidence = item.get("evidence", {})
                findings.append(("decision-drift", str(evidence.get("path", ""))))
            nested_drift = [
                *projection.get("link_check", {}).get("drift", []),
                *projection.get("registry_audit", {}).get("drift", []),
            ]
            if nested_drift:
                findings.append(("decision-drift", "ai-docs/decisions"))
            if not drift and not nested_drift:
                clean.append(lane)
        elif lane == "find-complexity-hotspots":
            for item in projection["findings"]:
                findings.append(("complexity-hotspot", str(item.get("file", ""))))
            if projection.get("status") in {"partial", "error"}:
                incomplete.append(lane)
            elif not projection["findings"]:
                clean.append(lane)
        else:
            non_clean = False
            gaps = 0
            for standard in projection["results"]:
                if standard.get("status") != "scanned":
                    non_clean = True
                    continue
                for gap in standard.get("gaps", []):
                    gaps += 1
                    findings.append(("standard-gap", str(gap.get("file", ""))))
            if non_clean:
                incomplete.append(lane)
            elif gaps == 0:
                clean.append(lane)
    return {
        "findings": sorted(set(findings)),
        "incomplete_lanes": sorted(set(incomplete)),
        "clean_lanes": sorted(set(clean)),
    }


def _score_synthesis(final: dict[str, Any] | None, expected: dict[str, Any]) -> tuple[bool, list[str]]:
    if final is None:
        return False, ["synthesis_final_not_json"]
    actual_findings = {
        (str(row.get("kind", "")), str(row.get("path", "")))
        for row in final.get("findings", [])
        if isinstance(row, dict)
    }
    failures = []
    for finding in expected["findings"]:
        if finding[0] == "decision-drift":
            matched = any(actual[0] == "decision-drift" for actual in actual_findings)
        else:
            matched = finding in actual_findings
        if not matched:
            failures.append(f"missing finding {finding}")
    if sorted(final.get("incomplete_lanes", [])) != expected["incomplete_lanes"]:
        failures.append("incomplete lane mismatch")
    if any(lane in final.get("clean_lanes", []) for lane in expected["incomplete_lanes"]):
        failures.append("incomplete lane presented as clean")
    return not failures, failures


class Budget:
    def __init__(self, maximum: int) -> None:
        self.maximum = maximum
        self.used = 0

    def reserve(self, amount: int = 1) -> bool:
        if self.used + amount > self.maximum:
            return False
        self.used += amount
        return True


def _condition(
    *,
    task: str,
    condition: str,
    host: Path,
    checkpoint: Path,
    standards: Path,
    initial_digest: str,
    label: str,
    budget: Budget,
) -> dict[str, Any] | None:
    result_path = checkpoint / "condition-result.json"
    if result_path.is_file():
        return json.loads(result_path.read_text(encoding="utf-8"))
    before = _tree_digest(host)
    if before != initial_digest:
        raise RuntimeError(
            f"{label} non-report host bytes differ from frozen initial_digest before resume"
        )
    native_before, _ = ml009._check(host, "typescript")
    started = time.perf_counter_ns()

    def lane_call(lane: str) -> tuple[dict[str, Any], Path, set[int]] | None:
        call_path = checkpoint / "lanes" / lane
        if not (call_path / "result.json").is_file() and not budget.reserve():
            return None
        command, artifact, exits = _lane_command(lane, host, label, standards)
        prompt = _lane_prompt(task=task, condition=condition, lane=lane, command=command, artifact=artifact)
        call = _run_model_call(prompt=prompt, host=host, checkpoint=call_path)
        return call, artifact, exits

    lane_calls: dict[str, tuple[dict[str, Any], Path, set[int]]] = {}
    if condition == CONDITIONS[2]:
        missing = sum(
            not (checkpoint / "lanes" / lane / "result.json").is_file()
            for lane in LANES
        )
        if not budget.reserve(missing):
            return None
        # Reservations are already accounted for; let each worker see an unlimited local budget.
        def parallel_lane(lane: str) -> tuple[dict[str, Any], Path, set[int]]:
            command, artifact, exits = _lane_command(lane, host, label, standards)
            prompt = _lane_prompt(task=task, condition=condition, lane=lane, command=command, artifact=artifact)
            call = _run_model_call(prompt=prompt, host=host, checkpoint=checkpoint / "lanes" / lane)
            return call, artifact, exits

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {lane: executor.submit(parallel_lane, lane) for lane in LANES}
            lane_calls = {lane: futures[lane].result() for lane in LANES}
    else:
        for lane in LANES:
            value = lane_call(lane)
            if value is None:
                return None
            lane_calls[lane] = value

    projections = [
        _artifact_projection(lane, lane_calls[lane][1], lane_calls[lane][2], lane_calls[lane][0])
        for lane in LANES
    ]
    synthesis_path = checkpoint / "synthesis"
    if not (synthesis_path / "result.json").is_file() and not budget.reserve():
        return None
    prompt = _synthesis_prompt(
        task=task,
        condition=condition,
        lane_results=projections,
        artifacts=[lane_calls[lane][1] for lane in LANES],
    )
    synthesis = _run_model_call(prompt=prompt, host=host, checkpoint=synthesis_path)
    _controller_elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    native_after, _ = ml009._check(host, "typescript")
    after = _tree_digest(host)
    expected = _expected_synthesis(projections)
    semantic_equal, semantic_failures = _score_synthesis(synthesis.get("final"), expected)
    calls = [lane_calls[lane][0] for lane in LANES] + [synthesis]
    lane_wall = [lane_calls[lane][0]["wall_ms"] for lane in LANES]
    if condition == CONDITIONS[2]:
        wall_ms = max(lane_wall) + synthesis["wall_ms"]
    else:
        wall_ms = sum(lane_wall) + synthesis["wall_ms"]
    failures = list(semantic_failures)
    if initial_digest != after:
        failures.append("non-report host bytes changed")
    if native_before != 0 or native_after != 0:
        failures.append("native check failed")
    if any(not call["success"] for call in calls):
        failures.append("one or more model calls failed")
    usage_keys = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
    usage = {
        key: sum((call.get("usage") or {}).get(key, 0) for call in calls)
        for key in usage_keys
    }
    payload = {
        "condition": condition,
        "wall_ms": round(wall_ms, 3),
        "controlled_injected_context_utf8_bytes": sum(
            call["controlled_injected_context_utf8_bytes"] for call in calls
        ),
        "usage": usage,
        "reported_token_aggregate": (
            usage["input_tokens"] + usage["output_tokens"] + usage["reasoning_output_tokens"]
        ),
        "lane_projections": projections,
        "expected_synthesis": expected,
        "semantic_equal": semantic_equal,
        "source_unchanged": initial_digest == after,
        "native_checks_passed": native_before == 0 and native_after == 0,
        "call_count": len(calls),
        "failures": failures,
        "passed": not failures,
    }
    _write_json(result_path, payload)
    return payload


def _prepare(run_root: Path) -> dict[str, Any]:
    manifest_path = run_root / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        changed = False
        current_hashes = _tool_hashes()
        if manifest.get("protocol_frozen") and manifest.get("tool_sha256") != current_hashes:
            raise RuntimeError("ML-020 benchmark tools changed after the protocol was frozen")
        if not manifest.get("protocol_frozen"):
            manifest["tool_sha256"] = current_hashes
            manifest["protocol_frozen"] = True
            changed = True
        if "validation" not in manifest:
            manifest["validation"] = _prepare_validation(run_root)
            manifest["planned_model_calls"] = 72
            changed = True
        if changed:
            _write_json(manifest_path, manifest)
        return manifest
    run_root.mkdir(parents=True, exist_ok=True)
    template, setup = ml009._template(run_root, "typescript")
    trials = []
    for number, task in enumerate(TRIAL_TASKS, 1):
        conditions = {}
        for condition in CONDITIONS:
            host = run_root / "hosts" / f"trial-{number}" / condition
            ml009._clone(template, host)
            standards = _standards(host)
            conditions[condition] = {
                "host": str(host),
                "standards": str(standards),
                "initial_digest": _tree_digest(host),
                "route_projection": _route_projection(task, host, standards),
            }
        trials.append(
            {
                "number": number,
                "task": task,
                "condition_order": list(CONDITION_ORDERS[number - 1]),
                "conditions": conditions,
            }
        )
    manifest = {
        "schema_version": 1,
        "benchmark": "ML-020 code-health family compression",
        "model": MODEL,
        "reasoning_effort": EFFORT,
        "no_automatic_retries": True,
        "protocol_frozen": True,
        "planned_model_calls": 72,
        "setup": setup,
        "source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip(),
        "source_tree_diff_sha256": _sha(
            subprocess.run(
                ["git", "diff", "--no-ext-diff", "--binary"],
                cwd=ROOT,
                capture_output=True,
                check=True,
            ).stdout
        ),
        "guidance_sha256": {
            f"{condition}:{lane or 'synthesis'}": _sha(_guidance(condition, lane).encode("utf-8"))
            for condition in CONDITIONS
            for lane in (*LANES, None)
        },
        "tool_sha256": _tool_hashes(),
        "trials": trials,
        "validation": _prepare_validation(run_root),
    }
    _write_json(manifest_path, manifest)
    return manifest


def _prepare_validation(run_root: Path) -> list[dict[str, Any]]:
    """Create one unseen replay and two untimed incomplete-evidence sentinels."""
    entries = []
    unseen_template = run_root / "templates" / "unseen-typescript"
    if not unseen_template.exists():
        shutil.copytree(ROOT / "tests" / "fixtures" / "find-complexity-hotspots-typescript", unseen_template)
        decisions = unseen_template / "ai-docs" / "decisions"
        decisions.mkdir(parents=True)
        shutil.copy2(
            ml009.FIXTURE / "ai-docs" / "decisions" / "0001-runtime-boundary.md",
            decisions / "0001-runtime-boundary.md",
        )
        (unseen_template / "src" / "health_support.ts").write_text(
            "// decision:0001\n"
            "export function unsafe(payload: string): unknown { return JSON.parse(payload); }\n",
            encoding="utf-8",
        )
        install, _ = ml009._run(["npm", "ci", "--offline", "--ignore-scripts"], unseen_template)
        native, _ = ml009._check(unseen_template, "typescript")
        if install != 0 or native != 0:
            raise RuntimeError("unseen TypeScript validation host setup failed")
    unseen_host = run_root / "hosts" / "validation" / "unseen" / CONDITIONS[2]
    if not unseen_host.exists():
        ml009._clone(unseen_template, unseen_host)
    unseen_standards = unseen_host / "standards.json"
    if not unseen_standards.exists():
        unseen_standards = _standards(unseen_host)
    entries.append(
        {
            "name": "unseen_host",
            "task": "Run a read-only TypeScript code-health audit of this unfamiliar src tree and preserve unsupported evidence.",
            "condition": CONDITIONS[2],
            "host": str(unseen_host),
            "standards": str(unseen_standards),
            "initial_digest": _tree_digest(unseen_host),
            "route_projection": _route_projection(
                "Run a read-only TypeScript code-health audit of this unfamiliar src tree and preserve unsupported evidence.",
                unseen_host,
                unseen_standards,
            ),
        }
    )
    timed_template = run_root / "templates" / "typescript"
    for condition in CONDITIONS[1:]:
        host = run_root / "hosts" / "validation" / "invalid-standards" / condition
        if not host.exists():
            ml009._clone(timed_template, host)
        standards = host / "standards.json"
        if not standards.exists():
            standards = _standards(host, invalid=True)
        entries.append(
            {
                "name": f"invalid_standards_{condition}",
                "task": "Run a read-only TypeScript code-health audit and do not call unavailable evidence clean.",
                "condition": condition,
                "host": str(host),
                "standards": str(standards),
                "initial_digest": _tree_digest(host),
                "route_projection": _route_projection(
                    "Run a read-only TypeScript code-health audit and do not call unavailable evidence clean.",
                    host,
                    standards,
                ),
            }
        )
    return entries


def _summarize(manifest: dict[str, Any], run_root: Path) -> dict[str, Any]:
    trials = []
    for trial in manifest["trials"]:
        conditions = {}
        for condition in CONDITIONS:
            path = run_root / "calls" / f"trial-{trial['number']}" / condition / "condition-result.json"
            if path.is_file():
                conditions[condition] = json.loads(path.read_text(encoding="utf-8"))
        trials.append({"number": trial["number"], "conditions": conditions})
    validation = []
    for entry in manifest.get("validation", []):
        path = run_root / "calls" / "validation" / entry["name"] / "condition-result.json"
        validation.append(
            {
                "name": entry["name"],
                "result": json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None,
            }
        )
    complete = all(len(row["conditions"]) == 3 for row in trials) and all(
        row["result"] is not None for row in validation
    )
    summary: dict[str, Any] = {
        "benchmark": manifest["benchmark"],
        "schema_version": 1,
        "model": manifest["model"],
        "reasoning_effort": manifest["reasoning_effort"],
        "trial_count": len(trials),
        "complete": complete,
        "trials": trials,
        "validation": validation,
    }
    if complete:
        by_condition = {condition: [row["conditions"][condition] for row in trials] for condition in CONDITIONS}
        a_context = sum(row["controlled_injected_context_utf8_bytes"] for row in by_condition[CONDITIONS[0]])
        gates = {}
        for condition in CONDITIONS[1:]:
            context = sum(row["controlled_injected_context_utf8_bytes"] for row in by_condition[condition])
            a_tokens = sum(row["reported_token_aggregate"] for row in by_condition[CONDITIONS[0]])
            tokens = sum(row["reported_token_aggregate"] for row in by_condition[condition])
            gates[condition] = {
                "context_reduction_percent": 100 * (a_context - context) / a_context,
                "context_reduction_gte_30": context <= 0.70 * a_context,
                "token_growth_percent": 100 * (tokens - a_tokens) / a_tokens if a_tokens else None,
                "token_growth_lte_10": bool(a_tokens and tokens <= 1.10 * a_tokens),
            }
        a_wall = [row["wall_ms"] for row in by_condition[CONDITIONS[0]]]
        c_wall = [row["wall_ms"] for row in by_condition[CONDITIONS[2]]]
        wall_improvement = 100 * (median(a_wall) - median(c_wall)) / median(a_wall)
        gates[CONDITIONS[2]]["median_wall_improvement_percent"] = wall_improvement
        gates[CONDITIONS[2]]["median_wall_improvement_gte_20"] = wall_improvement >= 20
        gates["semantic_and_safety"] = all(
            row["passed"] for condition in CONDITIONS for row in by_condition[condition]
        )
        summary["gates"] = gates
        validation_passed = all(row["result"]["passed"] for row in validation)
        summary["validation_passed"] = validation_passed
        summary["passed"] = bool(
            gates["semantic_and_safety"]
            and all(gates[c]["context_reduction_gte_30"] for c in CONDITIONS[1:])
            and all(gates[c]["token_growth_lte_10"] for c in CONDITIONS[1:])
            and gates[CONDITIONS[2]]["median_wall_improvement_gte_20"]
            and validation_passed
        )
    _write_json(run_root / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--max-new-calls", type=int, default=0)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    run_root = args.run_root.resolve()
    manifest = _prepare(run_root)
    if args.prepare_only:
        print(run_root / "manifest.json")
        return 0
    if args.max_new_calls < 0:
        parser.error("--max-new-calls must be >= 0")
    if args.max_new_calls and os.environ.get("ML020_MODEL_BUDGET_ACCEPTED") != "1":
        parser.error("set ML020_MODEL_BUDGET_ACCEPTED=1 to authorize planned model calls")
    budget = Budget(args.max_new_calls)
    for trial in manifest["trials"]:
        for condition in trial["condition_order"]:
            config = trial["conditions"][condition]
            result = _condition(
                task=trial["task"],
                condition=condition,
                host=Path(config["host"]),
                checkpoint=run_root / "calls" / f"trial-{trial['number']}" / condition,
                standards=Path(config["standards"]),
                initial_digest=config["initial_digest"],
                label=f"trial-{trial['number']}-{condition}",
                budget=budget,
            )
            if result is None:
                summary = _summarize(manifest, run_root)
                print(json.dumps({"new_calls": budget.used, "complete": summary["complete"]}))
                return 3
    for entry in manifest.get("validation", []):
        result = _condition(
            task=entry["task"],
            condition=entry["condition"],
            host=Path(entry["host"]),
            checkpoint=run_root / "calls" / "validation" / entry["name"],
            standards=Path(entry["standards"]),
            initial_digest=entry["initial_digest"],
            label=entry["name"],
            budget=budget,
        )
        if result is None:
            summary = _summarize(manifest, run_root)
            print(json.dumps({"new_calls": budget.used, "complete": summary["complete"]}))
            return 3
    summary = _summarize(manifest, run_root)
    print(run_root / "summary.json")
    return 0 if summary.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
