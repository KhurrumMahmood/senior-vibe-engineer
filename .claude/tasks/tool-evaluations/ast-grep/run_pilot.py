#!/usr/bin/env python3
"""Compare pinned ast-grep structural facts with accepted native detectors."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
RESULT = HERE.parent / "ast-grep-results.json"
LOCAL = HERE.parent / "local" / "ast-grep"
CONFIG = HERE / "sgconfig.yml"
SKILL = REPO / ".claude" / "skills" / "find-complexity-hotspots"
DETECTOR = SKILL / "scripts" / "detect.py"
AST_GREP = ("npx", "--yes", "--package", "@ast-grep/cli@0.44.1", "ast-grep")

FIXTURES = {
    "typescript": REPO / "tests" / "fixtures" / "find-complexity-hotspots-typescript",
    "go": REPO / "tests" / "fixtures" / "find-complexity-hotspots-go",
    "java": REPO / "tests" / "fixtures" / "find-complexity-hotspots-java",
}
SUFFIXES = {"typescript": {".ts", ".tsx"}, "go": {".go"}, "java": {".java"}}
SKIP_DIRS = {
    "typescript": {
        "__tests__", "build", "coverage", "dist", "fixture", "fixtures",
        "generated", "node_modules", "reports", "spec", "specs", "test",
        "tests", "vendor",
    },
    "go": {
        "__tests__", "build", "coverage", "dist", "fixture", "fixtures",
        "gen", "generated", "spec", "specs", "test", "testdata", "tests",
        "vendor",
    },
    "java": {
        ".gradle", "build", "coverage", "dist", "fixture", "fixtures",
        "generated", "integrationtest", "out", "reports", "target", "test",
        "testdata", "testfixtures", "tests", "vendor",
    },
}
SKIP_GLOBS = {
    "typescript": (
        "*.d.ts", "*.d.tsx", "*.generated.ts", "*.generated.tsx", "*.min.ts",
        "*.min.tsx", "*.spec.ts", "*.spec.tsx", "*.test.ts", "*.test.tsx",
    ),
    "go": ("*_test.go", "*.generated.go", "*_generated.go"),
    "java": ("*Test.java", "*Tests.java", "*IT.java", "*Generated.java", "*.generated.java"),
}


def run(*argv: str, cwd: Path = REPO, env: dict[str, str] | None = None) -> dict:
    started = time.perf_counter()
    completed = subprocess.run(
        argv, cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    return {
        "argv": list(argv),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "wall_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def tree_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def portable(value, temporary_root: Path):
    """Remove machine-local and ephemeral paths from committed evidence."""
    if isinstance(value, dict):
        return {key: portable(item, temporary_root) for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item, temporary_root) for item in value]
    if isinstance(value, str):
        replacements = (
            (str(temporary_root), "<temporary>"),
            (str(REPO), "."),
            (sys.executable, "<python>"),
        )
        for source, replacement in replacements:
            value = value.replace(source, replacement)
    return value


def source_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for language, root in FIXTURES.items():
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUFFIXES[language]:
                key = f"{language}/{path.relative_to(root).as_posix()}"
                result[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def compact(records: list[dict]) -> list[dict]:
    keys = ("file", "symbol", "kind", "branch_score", "lineno", "end_lineno", "loc")
    return sorted(
        [{key: record.get(key) for key in keys} for record in records],
        key=lambda row: (str(row["file"]), int(row["lineno"] or 0), str(row["symbol"])),
    )


def native_baselines(tmp: Path) -> tuple[dict, dict]:
    baselines: dict[str, list[dict]] = {}
    executions: dict[str, dict] = {}
    roots = {**FIXTURES}
    ts_root = tmp / "typescript-host"
    shutil.copytree(FIXTURES["typescript"], ts_root)
    install = run("npm", "ci", "--offline", "--ignore-scripts", cwd=ts_root)
    executions["typescript_npm_ci"] = {
        key: value for key, value in install.items() if key != "stdout"
    }
    if install["returncode"] != 0:
        raise RuntimeError(f"offline TypeScript fixture setup failed: {install['stderr']}")
    roots["typescript"] = ts_root

    for language, root in roots.items():
        output = tmp / f"native-{language}.jsonl"
        result = run(
            sys.executable,
            str(DETECTOR),
            "--project-root", str(root),
            "--output", str(output),
            "--language", language,
            "src",
            cwd=root,
        )
        executions[language] = {key: value for key, value in result.items() if key != "stdout"}
        if result["returncode"] != 0:
            raise RuntimeError(f"native {language} baseline failed: {result['stderr']}")
        records = [json.loads(line) for line in output.read_text().splitlines() if line]
        baselines[language] = compact(records)
    return baselines, executions


def scan(root: Path, *, npm_cache: Path | None = None) -> tuple[list[dict], dict]:
    env = os.environ.copy()
    if npm_cache is not None:
        env["npm_config_cache"] = str(npm_cache)
    result = run(
        *AST_GREP,
        "scan", "--config", str(CONFIG), "--json=compact", str(root),
        env=env,
    )
    try:
        rows = json.loads(result["stdout"] or "[]")
    except json.JSONDecodeError as error:
        raise RuntimeError(f"invalid ast-grep JSON for {root}: {error}: {result['stderr']}") from error
    # ast-grep can return 1 when an error-severity parse finding is present.
    if result["returncode"] not in {0, 1}:
        raise RuntimeError(f"ast-grep scan failed for {root}: {result['stderr']}")
    return rows, {key: value for key, value in result.items() if key != "stdout"}


def relative_file(row: dict, root: Path) -> str:
    path = Path(row["file"])
    if not path.is_absolute():
        path = REPO / path
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def eligible(language: str, relative: str, root: Path) -> tuple[bool, str]:
    path = Path(relative)
    lowered_parts = {part.lower() for part in path.parts[:-1]}
    if lowered_parts & SKIP_DIRS[language]:
        return False, "excluded_directory"
    if any(fnmatch.fnmatch(path.name, pattern) for pattern in SKIP_GLOBS[language]):
        return False, "excluded_filename"
    source_head = (root / relative).read_text(encoding="utf-8")[:2048].lower()
    if language == "go" and (
        source_head.startswith("//go:build") or "\n// +build" in source_head.split("package", 1)[0]
    ):
        return False, "build_constraint_ambiguous"
    if "generated by" in source_head and "do not edit" in source_head:
        return False, "generated_marker"
    return True, "eligible"


def byte_range(row: dict) -> tuple[int, int]:
    offsets = row["range"]["byteOffset"]
    return int(offsets["start"]), int(offsets["end"])


def enclosing(row: dict, candidates: list[dict]) -> dict | None:
    start, end = byte_range(row)
    matches = []
    for candidate in candidates:
        outer_start, outer_end = byte_range(candidate)
        if outer_start <= start and end <= outer_end and (outer_start, outer_end) != (start, end):
            matches.append(candidate)
    return min(matches, key=lambda item: byte_range(item)[1] - byte_range(item)[0], default=None)


def class_name(row: dict) -> str:
    match = re.search(r"\bclass\s+([A-Za-z_$][\w$]*)", str(row.get("text", "")))
    return match.group(1) if match else ""


def function_identity(language: str, row: dict, source: str, containers: list[dict]) -> tuple[str, str] | None:
    text = row["text"]
    first = text.splitlines()[0]
    if language == "typescript":
        if first.lstrip().startswith("function "):
            match = re.search(r"\bfunction\s+([A-Za-z_$][\w$]*)", first)
            return (match.group(1), "function") if match else None
        if "=>" in first:
            start = byte_range(row)[0]
            line_start = source.rfind("\n", 0, start) + 1
            prefix = source[line_start:start]
            match = re.search(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*$", prefix)
            return (match.group(1), "arrow") if match else None
        match = re.search(r"(?:^|\s)([A-Za-z_$][\w$]*)\s*(?:<[^>]+>)?\s*\(", first)
        if not match:
            return None
        owner = class_name(enclosing(row, containers) or {})
        name = match.group(1)
        return (f"{owner}.{name}" if owner else name, "method")
    if language == "go":
        receiver = re.match(r"func\s*\(([^)]*)\)\s*([A-Za-z_]\w*)\s*\(", first)
        if receiver:
            receiver_type = receiver.group(1).split()[-1]
            return (f"({receiver_type}).{receiver.group(2)}", "method")
        named = re.match(r"func\s+([A-Za-z_]\w*)", first)
        return (named.group(1), "function") if named else None
    if "->" in text:
        return None
    names = re.findall(r"([A-Za-z_$][\w$]*)\s*\(", first)
    if not names:
        return None
    name = names[-1]
    owner = class_name(enclosing(row, containers) or {})
    return (f"{owner}.{name}" if owner else name, "constructor" if owner == name else "method")


def project(language: str, root: Path, rows: list[dict]) -> dict:
    prefix = f"pilot-{language}-"
    functions_by_file: dict[str, list[dict]] = {}
    branches_by_file: dict[str, list[dict]] = {}
    containers_by_file: dict[str, list[dict]] = {}
    errors: list[dict] = []
    exclusions: dict[str, str] = {}
    for row in rows:
        relative = relative_file(row, root)
        ok, reason = eligible(language, relative, root)
        if not ok:
            exclusions[relative] = reason
            continue
        rule = row.get("ruleId", "")
        if rule == prefix + "functions":
            functions_by_file.setdefault(relative, []).append(row)
        elif rule == prefix + "branches":
            branches_by_file.setdefault(relative, []).append(row)
        elif rule == prefix + "containers":
            containers_by_file.setdefault(relative, []).append(row)
        elif rule == prefix + "errors":
            errors.append({"file": relative, "range": row["range"]})

    records: list[dict] = []
    all_files = sorted(set(functions_by_file) | set(branches_by_file))
    for relative in all_files:
        source = (root / relative).read_text(encoding="utf-8")
        functions = functions_by_file.get(relative, [])
        counts = {id(function): 0 for function in functions}
        for branch in branches_by_file.get(relative, []):
            owner = enclosing(branch, functions)
            if owner is not None:
                counts[id(owner)] += 1
        for function in functions:
            identity = function_identity(
                language, function, source, containers_by_file.get(relative, [])
            )
            if identity is None:
                continue
            symbol, kind = identity
            start = int(function["range"]["start"]["line"]) + 1
            end = int(function["range"]["end"]["line"]) + 1
            score = counts[id(function)]
            loc = max(1, end - start + 1)
            if score >= 18 or (score >= 12 and loc >= 120):
                records.append({
                    "file": relative,
                    "symbol": symbol,
                    "kind": kind,
                    "branch_score": score,
                    "lineno": start,
                    "end_lineno": end,
                    "loc": loc,
                })
    return {
        "records": compact(records),
        "parse_errors": errors,
        "policy_exclusions": [{"file": file, "reason": reason} for file, reason in sorted(exclusions.items())],
        "raw_matches": len(rows),
    }


def malformed_checks(tmp: Path) -> dict:
    samples = {
        "typescript": ("Broken.ts", "export function ok() { return 1; }\nexport function broken(: number {\n"),
        "go": ("broken.go", "package sample\nfunc ok() int { return 1 }\nfunc broken( {\n"),
        "java": ("Broken.java", "class Broken { int ok() { return 1; } void bad( { } }\n"),
    }
    result = {}
    for language, (name, content) in samples.items():
        root = tmp / f"malformed-{language}"
        root.mkdir()
        (root / name).write_text(content, encoding="utf-8")
        rows, execution = scan(root)
        error_rows = [row for row in rows if row.get("ruleId") == f"pilot-{language}-errors"]
        result[language] = {
            "returncode": execution["returncode"],
            "error_nodes": len(error_rows),
            "non_error_matches_also_returned": len(rows) - len(error_rows),
            "stderr": execution["stderr"],
        }
    return result


def loc(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> int:
    LOCAL.mkdir(parents=True, exist_ok=True)
    before = source_hashes()
    with tempfile.TemporaryDirectory(prefix="ast-grep-pilot-") as raw_tmp:
        tmp = Path(raw_tmp)
        native, native_execution = native_baselines(tmp)

        projected: dict[str, dict] = {}
        executions: dict[str, dict] = {}
        for language, root in FIXTURES.items():
            rows, execution = scan(root)
            projected[language] = project(language, root, rows)
            executions[language] = execution

        cold_cache = LOCAL / "npm-cold-cache"
        shutil.rmtree(cold_cache, ignore_errors=True)
        cold_rows, cold = scan(FIXTURES["java"], npm_cache=cold_cache)
        warm_rows, warm = scan(FIXTURES["java"], npm_cache=cold_cache)
        malformed = malformed_checks(tmp)

    after = source_hashes()
    parity = {
        language: projected[language]["records"] == native[language]
        for language in FIXTURES
    }
    example_tests = {
        language: {
            "native_findings": len(native[language]),
            "ast_grep_findings": len(projected[language]["records"]),
            "exact_record_parity": parity[language],
        }
        for language in FIXTURES
    }
    malformed_visible = all(row["error_nodes"] > 0 for row in malformed.values())

    native_helpers = [
        SKILL / "scripts" / "detect_typescript_complexity.mjs",
        SKILL / "scripts" / "detect_go_complexity.go",
        SKILL / "scripts" / "detect_java_complexity.java",
    ]
    rule_files = sorted((HERE / "rules").glob("*.yml"))
    measurements = {
        "native_helper_nonblank_loc": sum(loc(path) for path in native_helpers),
        "pilot_rule_nonblank_loc": sum(loc(path) for path in rule_files),
        "pilot_harness_nonblank_loc": loc(Path(__file__)),
        "cold_java_scan_ms": cold["wall_ms"],
        "warm_java_scan_ms": warm["wall_ms"],
        "cold_cache_bytes": tree_size(cold_cache),
        "cold_npx_runtime_bytes": tree_size(cold_cache / "_npx"),
        "cold_matches": len(cold_rows),
        "warm_matches": len(warm_rows),
    }

    if all(parity.values()) and malformed_visible:
        disposition = "continue_pilot"
        reason = (
            "Exact fixture facts are reproducible and parse errors are queryable, but the common "
            "harness still owns language-specific identity and source-policy code. Test one simpler "
            "queued-language structural family before adopting ast-grep in product closures."
        )
    else:
        disposition = "reject"
        reason = (
            "The pinned structural provider did not preserve the accepted complexity facts and "
            "failure boundary across all three languages."
        )

    payload = {
        "schema_version": 1,
        "experiment": "X1-ast-grep-structural-facts",
        "base_revision": run("git", "rev-parse", "HEAD")["stdout"].strip(),
        "tool": {
            "package": "@ast-grep/cli",
            "version": "0.44.1",
            "invocation": list(AST_GREP),
            "default_product_dependency": False,
        },
        "capability_claim": {
            "provided": "syntax facts from tested grammars/rules",
            "not_provided": ["symbol resolution", "types", "project graph", "framework semantics"],
        },
        "source_hashes_unchanged": before == after,
        "native": native,
        "native_execution": native_execution,
        "ast_grep": projected,
        "ast_grep_execution": executions,
        "example_tests": example_tests,
        "malformed": malformed,
        "measurements": measurements,
        "disposition": disposition,
        "disposition_reason": reason,
        "next_revisit": "Use one queued-language declaration/standard-gap outcome; do not replace the native complexity helpers now.",
    }
    payload = portable(payload, tmp)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": str(RESULT.relative_to(REPO)),
        "parity": parity,
        "malformed_visible": malformed_visible,
        "source_hashes_unchanged": before == after,
        "measurements": measurements,
        "disposition": disposition,
    }, indent=2))
    return 0 if all(parity.values()) and malformed_visible and before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
