#!/usr/bin/env python3
"""Run the fixed ML-009 serial-versus-parallel read-only-lenses benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "audit-decisions-typescript" / "host"
LANES = ("audit-decisions", "find-complexity-hotspots", "find-standard-gaps")
LANGUAGES = ("typescript", "javascript")
CLOSURE_FILES = {
    "audit-decisions": (
        "SKILL.md",
        "scripts/audit.py",
        "scripts/detect_typescript_comments.mjs",
    ),
    "find-complexity-hotspots": (
        "SKILL.md",
        "scripts/run.py",
        "scripts/detect.py",
        "scripts/detect_typescript_complexity.mjs",
    ),
    "find-standard-gaps": (
        "SKILL.md",
        "scripts/scan_coverage.py",
        "scripts/project_state.py",
        "scripts/engineering_home.py",
        "scripts/detect_typescript_calls.mjs",
    ),
}


def _ms(start: int) -> float:
    return round((time.perf_counter_ns() - start) / 1_000_000, 3)


def _run(command: list[str], cwd: Path) -> tuple[int | None, float]:
    started = time.perf_counter_ns()
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    except OSError:
        return None, _ms(started)
    return result.returncode, _ms(started)


def _check(host: Path, language: str) -> tuple[int | None, float]:
    return _run(["npm", "run", "typecheck" if language == "typescript" else "check-js"], host)


def _source(language: str) -> str:
    parameter = "value: number" if language == "typescript" else "value"
    payload = "payload: string" if language == "typescript" else "payload"
    number_return = ": number" if language == "typescript" else ""
    unknown_return = ": unknown" if language == "typescript" else ""
    jsdoc = "" if language == "typescript" else "/** @param {number} value @returns {number} */\n"
    json_jsdoc = "" if language == "typescript" else "/** @param {string} payload @returns {unknown} */\n"
    branches = "\n".join(f"  if (value > {number}) value -= 1;" for number in range(18))
    return (
        "// decision:0001\n"
        "const commentLikeText = \"decision:9999\";\n\n"
        f"{jsdoc}export function benchmarkHotspot({parameter}){number_return} {{\n"
        f"{branches}\n  return value;\n}}\n\n"
        f"{json_jsdoc}export function unsafeJson({payload}){unknown_return} {{\n"
        "  return JSON.parse(payload);\n}\n\n"
        f"{json_jsdoc}export function protectedJson({payload}){unknown_return} {{\n"
        "  try {\n    return JSON.parse(payload);\n  } catch {\n    return null;\n  }\n}\n"
    )


def _source_path(host: Path, language: str) -> Path:
    return host / "src" / f"benchmark.{'ts' if language == 'typescript' else 'js'}"


def _write_host(host: Path, language: str) -> None:
    source = _source_path(host, language)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(_source(language), encoding="utf-8")
    if language == "typescript":
        config = {
            "compilerOptions": {
                "module": "NodeNext",
                "moduleResolution": "NodeNext",
                "noEmit": True,
                "strict": True,
                "target": "ES2022",
            },
            "include": ["src/**/*.ts"],
        }
        (host / "tsconfig.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        return
    package_path = host / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package.setdefault("scripts", {})["check-js"] = "tsc --project jsconfig.json"
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    config = {
        "compilerOptions": {
            "allowJs": True,
            "checkJs": True,
            "module": "NodeNext",
            "moduleResolution": "NodeNext",
            "noEmit": True,
            "target": "ES2022",
        },
        "include": ["src/**/*.js"],
    }
    (host / "jsconfig.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def _template(work: Path, language: str) -> tuple[Path, dict[str, Any]]:
    host = work / "templates" / language
    host.mkdir(parents=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copy2(FIXTURE / name, host / name)
    shutil.copytree(FIXTURE / "ai-docs" / "decisions", host / "ai-docs" / "decisions")
    _write_host(host, language)
    install_exit, setup_ms = _run(["npm", "ci", "--offline", "--ignore-scripts"], host)
    before_exit, _ = _check(host, language)
    after_exit, _ = _check(host, language)
    return host, {
        "npm_ci_setup_ms": setup_ms,
        "npm_ci_passed": install_exit == 0,
        "native_check_before_passed": before_exit == 0,
        "native_check_after_passed": after_exit == 0,
    }


def _copy_library(work: Path) -> tuple[Path, dict[str, int]]:
    library = work / "on_demand_library"
    sizes: dict[str, int] = {}
    for lane in LANES:
        total = 0
        for relative in CLOSURE_FILES[lane]:
            source = ROOT / ".claude" / "skills" / lane / relative
            destination = library / lane / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            total += destination.stat().st_size
        sizes[lane] = total
    return library, sizes


def _clone(template: Path, host: Path) -> None:
    shutil.copytree(template, host, ignore=shutil.ignore_patterns("node_modules", "reports"))
    (host / "node_modules").symlink_to(template / "node_modules", target_is_directory=True)


def _digest(host: Path, language: str) -> str:
    return hashlib.sha256(_source_path(host, language).read_bytes()).hexdigest()


def _ideas(host: Path, condition: str) -> Path:
    path = host / "reports" / "find-standard-gaps" / condition / "ideas.json"
    path.parent.mkdir(parents=True, exist_ok=True)
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
                            },
                        },
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _audit_projection(path: Path) -> tuple[list[dict[str, str]], int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    projection = [
        {"path": str(row["path"]), "id": str(row["id"]), "language": str(row["language"])}
        for row in raw["references"]
    ]
    projection.sort(key=lambda row: (row["path"], row["id"], row["language"]))
    return projection, 1 if raw["drift"] else 0


def _complexity_projection(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    projection = [
        {
            "file": str(row["file"]),
            "symbol": str(row["symbol"]),
            "pattern": str(row["pattern"]),
            "branch_score": int(row["branch_score"]),
            "language": str(row["language"]),
            "analyzer": str(row["analyzer"]),
        }
        for row in raw["findings"]
    ]
    projection.sort(key=lambda row: (row["file"], row["symbol"], row["pattern"]))
    return projection


def _standard_projection(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))["results"][0]
    gaps = [{"file": str(gap["file"]), "line": int(gap["line"])} for gap in result["gaps"]]
    gaps.sort(key=lambda gap: (gap["file"], gap["line"]))
    return {
        "status": str(result["status"]),
        "scanned_files": int(result.get("scanned_files", 0)),
        "situation_sites": int(result.get("situation_sites", 0)),
        "gaps": gaps,
    }


def _lane(
    lane: str,
    language: str,
    library: Path,
    host: Path,
    condition: str,
) -> tuple[float, Any, str | None]:
    scripts = library / lane / "scripts"
    prefix = [sys.executable, "-I", "-S"]
    if lane == "audit-decisions":
        output = host / "reports" / "audit-decisions" / condition
        command = prefix + [
            str(scripts / "audit.py"), "--project-root", str(host), "--target", "src",
            "--output-dir", str(output),
        ]
        projection = _audit_projection
        artifact = output / "raw-drift.json"
    elif lane == "find-complexity-hotspots":
        command = prefix + [
            str(scripts / "run.py"), "--project-root", str(host), "--language", language,
            "--skip-effectiveness-log", "src",
        ]
        projection = _complexity_projection
        artifact = host / "reports" / "find-complexity-hotspots" / "latest" / "findings.json"
    else:
        output = host / "reports" / "find-standard-gaps" / condition
        command = prefix + [
            str(scripts / "scan_coverage.py"), "--ideas", str(_ideas(host, condition)),
            "--project-root", str(host), "--output-dir", str(output),
        ]
        projection = _standard_projection
        artifact = output / "coverage.json"
    exit_code, duration = _run(command, host)
    try:
        if lane == "audit-decisions":
            semantic, expected_exit = projection(artifact)
        else:
            semantic, expected_exit = projection(artifact), 0
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return duration, None, f"{lane} final artifact was unavailable or invalid"
    if exit_code != expected_exit:
        return duration, semantic, f"{lane} exited {exit_code}; expected {expected_exit}"
    return duration, semantic, None


def _condition(
    name: str,
    language: str,
    library: Path,
    host: Path,
) -> tuple[dict[str, Any], dict[str, Any], bool, bool, list[str]]:
    before = _digest(host, language)
    native_before, _ = _check(host, language)
    started = time.perf_counter_ns()
    if name == "serial":
        rows = [_lane(lane, language, library, host, name) for lane in LANES]
    else:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(_lane, lane, language, library, host, name) for lane in LANES]
            rows = [future.result() for future in futures]
    wall_ms = _ms(started)
    native_after, _ = _check(host, language)
    after = _digest(host, language)
    errors = [error for _, _, error in rows if error]
    if native_before != 0 or native_after != 0:
        errors.append(f"{name} native check failed")
    if before != after:
        errors.append(f"{name} source changed")
    return (
        {"wall_ms": wall_ms, "per_lens_ms": dict(zip(LANES, (row[0] for row in rows), strict=True))},
        dict(zip(LANES, (row[1] for row in rows), strict=True)),
        before == after,
        native_before == 0 and native_after == 0,
        errors,
    )


def _expected(language: str) -> dict[str, Any]:
    suffix = "ts" if language == "typescript" else "js"
    unsafe_line = _source(language).splitlines().index("  return JSON.parse(payload);") + 1
    return {
        "audit-decisions": [{"path": f"src/benchmark.{suffix}", "id": "0001", "language": language}],
        "find-complexity-hotspots": [
            {
                "file": f"src/benchmark.{suffix}",
                "symbol": "benchmarkHotspot",
                "pattern": "high-branch-function",
                "branch_score": 18,
                "language": language,
                "analyzer": "typescript-compiler-api",
            },
        ],
        "find-standard-gaps": {
            "status": "scanned",
            "scanned_files": 1,
            "situation_sites": 2,
            "gaps": [{"file": f"src/benchmark.{suffix}", "line": unsafe_line}],
        },
    }


def _packets(language: str) -> dict[str, int]:
    return {
        lane: len(
            json.dumps(
                {
                    "benchmark": "ML-009", "guide": f"{lane}/SKILL.md", "lane": lane,
                    "language": language, "read_only": True, "target": "src",
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        for lane in LANES
    }


def _trial(
    number: int,
    language: str,
    template: Path,
    library: Path,
    work: Path,
    closure_bytes: dict[str, int],
) -> dict[str, Any]:
    order = ["serial", "parallel"] if number % 2 else ["parallel", "serial"]
    hosts = {name: work / "trials" / language / f"trial-{number}" / name for name in ("serial", "parallel")}
    for host in hosts.values():
        _clone(template, host)
    outcomes = {}
    for name in order:
        outcomes[name] = _condition(name, language, library, hosts[name])
    serial, serial_semantic, serial_safe, serial_native, serial_failures = outcomes["serial"]
    parallel, parallel_semantic, parallel_safe, parallel_native, parallel_failures = outcomes["parallel"]
    expected = _expected(language)
    failures = [*serial_failures, *parallel_failures]
    semantic_equal = serial_semantic == parallel_semantic
    fixed_oracle = serial_semantic == expected and parallel_semantic == expected
    if not semantic_equal:
        failures.append("serial and parallel semantic projections differ")
    if not fixed_oracle:
        failures.append("semantic projection did not match the fixed oracle")
    packets = _packets(language)
    source_size = _source_path(hosts["serial"], language).stat().st_size
    return {
        "language": language,
        "trial": number,
        "condition_order": order,
        "serial": serial,
        "parallel": parallel,
        "semantic_equal": semantic_equal,
        "fixed_oracle": fixed_oracle,
        "source_unchanged": serial_safe and parallel_safe,
        "native_checks_passed": serial_native and parallel_native,
        "task_packet_utf8_bytes": {
            "per_lens": packets,
            "serial_total": sum(packets.values()),
            "parallel_total": sum(packets.values()),
        },
        "copied_closure_bytes": {"per_lens": closure_bytes, "total": sum(closure_bytes.values())},
        "eligible_input_overlap_proxy_bytes": len(LANES) * source_size - source_size,
        "actual_filesystem_read_bytes": None,
        "model_tokens": None,
        "interventions": 0,
        "failure_count": len(failures),
        "failures": failures,
    }


def _summary(trials: list[dict[str, Any]], languages: list[str]) -> tuple[dict[str, Any], bool]:
    by_language: dict[str, Any] = {}
    for language in languages:
        rows = [row for row in trials if row["language"] == language]
        savings = [row["serial"]["wall_ms"] - row["parallel"]["wall_ms"] for row in rows]
        percentages = [
            100 * saving / row["serial"]["wall_ms"]
            for row, saving in zip(rows, savings, strict=True)
            if row["serial"]["wall_ms"]
        ]
        wins = sum(saving > 0 for saving in savings)
        percent_saving = median(percentages) if percentages else None
        absolute_saving = median(savings)
        gate_evaluable = len(rows) == 7
        percent_gate = percent_saving is not None and percent_saving >= 20
        absolute_gate = absolute_saving >= 100
        wins_gate = wins >= 5
        by_language[language] = {
            "trial_count": len(rows),
            "median_absolute_saving_ms": absolute_saving,
            "median_percent_saving": percent_saving,
            "parallel_win_count": wins,
            "gate_evaluable": gate_evaluable,
            "median_percent_saving_gte_20": percent_gate,
            "median_absolute_saving_gte_100ms": absolute_gate,
            "parallel_wins_gte_5_of_7": wins_gate,
            "materiality_gate_passed": gate_evaluable and percent_gate and absolute_gate and wins_gate,
        }
    complete_language_set = len(languages) == len(LANGUAGES) and set(languages) == set(LANGUAGES)
    overall = complete_language_set and all(
        row["materiality_gate_passed"] for row in by_language.values()
    )
    return {"by_language": by_language, "materiality_gate_passed": overall}, overall


def _languages(raw: str) -> list[str]:
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if len(values) != len(LANGUAGES) or set(values) != set(LANGUAGES):
        raise argparse.ArgumentTypeError(
            f"fixed ML-009 contract requires exactly {', '.join(LANGUAGES)}"
        )
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=7)
    parser.add_argument("--languages", type=_languages, default=list(LANGUAGES))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keep-workdir", type=Path)
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be >= 1")
    if args.keep_workdir and args.keep_workdir.exists():
        parser.error("--keep-workdir must name a new path")

    keep = args.keep_workdir is not None
    work = args.keep_workdir.resolve() if keep else Path(tempfile.mkdtemp(prefix="readonly-lenses-benchmark-"))
    if keep:
        work.mkdir(parents=True)
    try:
        library, closure_bytes = _copy_library(work)
        templates: dict[str, Path] = {}
        setup: dict[str, Any] = {}
        for language in args.languages:
            templates[language], setup[language] = _template(work, language)
        trials = [
            _trial(number, language, templates[language], library, work, closure_bytes)
            for language in args.languages
            for number in range(1, args.trials + 1)
        ]
        failures = [failure for row in trials for failure in row["failures"]]
        for language, result in setup.items():
            if not all(result[key] for key in result if key.endswith("passed")):
                failures.append(f"{language} template setup or native check failed")
        summary, materiality = _summary(trials, args.languages)
        payload: dict[str, Any] = {
            "benchmark": "ML-009 fixed read-only lenses",
            "schema_version": 2,
            "configuration": {
                "trials": args.trials,
                "languages": args.languages,
                "lane_order": list(LANES),
                "parallel_workers": 3,
            },
            "expected_semantic_projection": {language: _expected(language) for language in args.languages},
            "setup": setup,
            "trials": trials,
            "summary": summary,
            "correct": not failures,
            "materiality_gate_passed": materiality and not failures,
            "failure_count": len(failures),
            "failures": failures,
        }
        if keep:
            payload["kept_workdir"] = str(work)
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(output)
        return 0 if not failures else 1
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
