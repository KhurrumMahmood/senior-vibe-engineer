#!/usr/bin/env python3
"""Benchmark the real code-health launcher in paired serial/parallel runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "audit-decisions-typescript" / "host"
LAUNCHER = ROOT / ".claude" / "skill-families" / "code-health-readonly" / "scripts" / "run.py"
MODES = ("serial", "parallel")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "node_modules" in path.relative_to(root).parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _prepare_template(run_root: Path) -> tuple[Path, Path]:
    template = run_root / "template"
    if not template.exists():
        shutil.copytree(FIXTURE, template)
        install = subprocess.run(
            ["npm", "ci", "--offline", "--ignore-scripts"],
            cwd=template,
            check=False,
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            raise RuntimeError(install.stdout + install.stderr)
        branches = "\n".join(
            f"  if (value > {number}) value -= 1;" for number in range(18)
        )
        (template / "src" / "health.ts").write_text(
            "// decision:0001\n"
            "export function hotspot(value: number): number {\n"
            f"{branches}\n"
            "  return value;\n"
            "}\n"
            "export function unsafe(payload: string): unknown {\n"
            "  return JSON.parse(payload);\n"
            "}\n",
            encoding="utf-8",
        )
        (template / "standards.json").write_text(
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
    return template, template / "standards.json"


def _projection(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "lanes": [
            {
                "skill": row["skill"],
                "status": row["status"],
                "reason": row.get("reason"),
                "semantic_projection": row.get("semantic_projection"),
            }
            for row in payload["lanes"]
        ],
        "synthesis": payload["synthesis"],
        "source_mutated": payload["source_mutated"],
        "failures": payload["failures"],
    }


def _run_condition(
    *, run_root: Path, template: Path, trial: int, mode: str
) -> dict[str, Any]:
    checkpoint = run_root / "trials" / f"trial-{trial}" / f"{mode}.json"
    if checkpoint.is_file():
        return json.loads(checkpoint.read_text(encoding="utf-8"))
    host = run_root / "hosts" / f"trial-{trial}" / mode
    if not host.exists():
        shutil.copytree(template, host)
    output = host / "reports" / "code-health" / f"trial-{trial}-{mode}"
    command = [
        sys.executable,
        "-B",
        "-I",
        "-S",
        str(LAUNCHER),
        "--project-root",
        str(host),
        "--library-root",
        str(ROOT),
        "--target",
        "src",
        "--language",
        "typescript",
        "--standards",
        str(host / "standards.json"),
        "--mode",
        mode,
        "--run-id",
        f"trial-{trial}-{mode}",
        "--output-dir",
        str(output),
    ]
    started = time.perf_counter_ns()
    result = subprocess.run(
        command,
        cwd=host,
        check=False,
        capture_output=True,
        text=True,
    )
    outer_wall_ms = (time.perf_counter_ns() - started) / 1_000_000
    artifact = output / "family-result.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    projection = _projection(payload)
    record = {
        "trial": trial,
        "mode": mode,
        "exit_code": result.returncode,
        "outer_wall_ms": round(outer_wall_ms, 3),
        "launcher_wall_ms": payload["wall_ms"],
        "projection_sha256": _sha(projection),
        "projection": projection,
        "scanner_invocations": sum("command" in row for row in payload["lanes"]),
        "native_tool_invocations": None,
        "native_tool_invocations_reason": "nested scanner tool calls are not event-instrumented",
        "controlled_context_utf8_bytes": 0,
        "repeated_context_utf8_bytes": 0,
        "cache_state": "unavailable",
        "human_interventions": [],
        "recoverable_failures": [],
    }
    _write_json(checkpoint, record)
    return record


def benchmark(run_root: Path, pairs: int) -> dict[str, Any]:
    template, _standards = _prepare_template(run_root)
    trials = []
    for number in range(1, pairs + 1):
        order = MODES if number % 2 else tuple(reversed(MODES))
        records = {
            mode: _run_condition(
                run_root=run_root,
                template=template,
                trial=number,
                mode=mode,
            )
            for mode in order
        }
        trials.append(
            {
                "number": number,
                "order": list(order),
                "serial": records["serial"],
                "parallel": records["parallel"],
                "semantic_equal": (
                    records["serial"]["projection_sha256"]
                    == records["parallel"]["projection_sha256"]
                ),
            }
        )
    serial_wall = [row["serial"]["outer_wall_ms"] for row in trials]
    parallel_wall = [row["parallel"]["outer_wall_ms"] for row in trials]
    serial_median = median(serial_wall)
    parallel_median = median(parallel_wall)
    improvement = 100 * (serial_median - parallel_median) / serial_median
    passed = all(
        row["semantic_equal"]
        and row["serial"]["exit_code"] == 0
        and row["parallel"]["exit_code"] == 0
        and not row["serial"]["projection"]["source_mutated"]
        and not row["parallel"]["projection"]["source_mutated"]
        for row in trials
    )
    summary = {
        "schema_version": 1,
        "benchmark": "actual product code-health launcher",
        "execution_revision": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "source_tree_diff_sha256": hashlib.sha256(
            subprocess.run(
                ["git", "diff", "--no-ext-diff", "--binary"],
                cwd=ROOT,
                check=True,
                capture_output=True,
            ).stdout
        ).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "launcher_sha256": hashlib.sha256(LAUNCHER.read_bytes()).hexdigest(),
        "fixture_sha256": _tree_sha(FIXTURE),
        "paired_trials": pairs,
        "trial_record_schema": {
            "required": [
                "trial",
                "mode",
                "exit_code",
                "outer_wall_ms",
                "launcher_wall_ms",
                "projection_sha256",
                "scanner_invocations",
                "native_tool_invocations",
                "controlled_context_utf8_bytes",
                "repeated_context_utf8_bytes",
                "cache_state",
                "human_interventions",
                "recoverable_failures",
            ]
        },
        "cache_state": "unavailable; fresh host copies used but OS/tool caches were not controlled",
        "serial_median_outer_wall_ms": round(serial_median, 3),
        "parallel_median_outer_wall_ms": round(parallel_median, 3),
        "parallel_improvement_percent": improvement,
        "all_semantically_equal": all(row["semantic_equal"] for row in trials),
        "passed": passed,
        "trials": trials,
    }
    _write_json(run_root / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=5)
    args = parser.parse_args(argv)
    if args.pairs < 1:
        parser.error("--pairs must be >= 1")
    summary = benchmark(args.run_root.resolve(), args.pairs)
    print(args.run_root.resolve() / "summary.json")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
