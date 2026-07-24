#!/usr/bin/env python3
"""Consume accepted Kotlin structure evidence and prove read-only proposals."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "kotlin-jvm-structure-proposal-v1"
ACCEPTANCE_SCHEMA = "kotlin-structure-accepted-evidence-v1"
COMPILER_SHA256 = "db12b1af0db0e10eeedfc15d5dac0316604e5c556321f60e3bcd73075a66f0a3"
STDLIB_SHA256 = "4ec0293bc3751423b203f1d8493251c57c42e73eb6377a6b8560d0974ff0a6df"
BOUNDARY_VERDICTS = {
    "overload_ambiguity": "none",
    "reflection_callable_references": "none",
    "delegation": "none",
    "generated_kapt_ksp_plugins": "none",
    "gradle_variants": "none",
    "java_external_callers": "none",
    "runtime_dispatch_equivalence": "not_established",
    "jvm_abi": "separate_approval_required",
}
NONCLAIMS = [
    "K1 compiler facts are pinned to Kotlin/JVM 2.4.10 and are not the stable Analysis API",
    "direct resolved calls do not establish override dispatch, reflection, callable-reference, delegation, framework, or runtime reachability",
    "generated/KAPT/KSP and plugin sources, Gradle variants, Java and external callers, Android, and Multiplatform remain excluded",
    "the disposable JVM 17 build proves only the exact accepted manifest after-tree, not JVM ABI or binary compatibility",
    "proposal.md, evidence.json, and scope.json are read-only and grant no mutation or release authority",
]


class ProposalError(RuntimeError):
    """A typed refusal that still replaces the terminal artifact bundle."""

    def __init__(self, status: str, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.kind = kind
        self.detail = detail


def _canonical(value: Any) -> str:
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ProposalError("failed", "invalid_selection", f"{label} is missing")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ProposalError("failed", "invalid_selection", f"{label} is unsafe")
    return value


def _input(root: Path, supplied: Path, label: str) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    try:
        path = raw.resolve(strict=True)
        path.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label}: {exc}") from exc
    if not path.is_file() or path.is_symlink():
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is unavailable")
    return path


def _output(root: Path, supplied: Path, consumer: str) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    path = Path(os.path.abspath(raw))
    allowed = root / "reports" / consumer
    try:
        relative = path.relative_to(allowed)
    except ValueError as exc:
        raise ProposalError(
            "failed", "unsafe_output_path", f"output must stay below reports/{consumer}"
        ) from exc
    if not relative.parts:
        raise ProposalError("failed", "unsafe_output_path", "output must name a run")
    current = allowed
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ProposalError("failed", "unsafe_output_path", "output traverses a symlink")
    return path


def _read(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is not an object")
    return payload


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _scope(payload: dict[str, Any], consumer: str) -> dict[str, Any]:
    fields = (
        "status",
        "outcome",
        "failure_kind",
        "message",
        "target",
        "domain",
        "parent",
        "prefix",
        "declarations",
        "caller_impact",
        "package_impact",
        "exact_edits",
        "create_files",
        "exact_moves",
        "manifest_sources_after",
        "test_surface",
        "nonclaims",
    )
    return {
        "schema_version": SCHEMA,
        "skill": consumer,
        "language": "kotlin",
        "read_only": True,
        "mutation_authorized": False,
        **{field: payload[field] for field in fields if field in payload},
    }


def _replace(output: Path, payload: dict[str, Any], proposal: str, consumer: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.parent / f".{output.name}.stage-{uuid.uuid4().hex}"
    backup = output.parent / f".{output.name}.old-{uuid.uuid4().hex}"
    staged.mkdir()
    try:
        _atomic(staged / "evidence.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
        _atomic(
            staged / "scope.json",
            json.dumps(_scope(payload, consumer), indent=2, sort_keys=True) + "\n",
        )
        _atomic(staged / "proposal.md", proposal)
        if output.exists():
            output.replace(backup)
        try:
            staged.replace(output)
        except OSError:
            if backup.exists():
                backup.replace(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def _artifact_hashes(
    root: Path, acceptance: dict[str, Any], supplied: dict[str, Path]
) -> dict[str, str]:
    rows = acceptance.get("artifacts")
    if not isinstance(rows, list):
        raise ProposalError("failed", "invalid_accepted_evidence", "artifact hashes are missing")
    accepted = {
        row.get("kind"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("kind"), str)
    }
    if set(accepted) != set(supplied):
        raise ProposalError("failed", "invalid_accepted_evidence", "accepted artifact set changed")
    hashes: dict[str, str] = {}
    for kind, path in supplied.items():
        expected = root / _relative(accepted[kind].get("path"), f"{kind} path")
        if expected.resolve() != path.resolve():
            raise ProposalError("failed", "invalid_accepted_evidence", f"{kind} path changed")
        digest = _sha256(path)
        if accepted[kind].get("sha256") != digest:
            raise ProposalError("failed", "stale_accepted_evidence", f"{kind} hash changed")
        hashes[kind] = digest
    return hashes


def _validate_acceptance(
    root: Path,
    consumer: str,
    acceptance: dict[str, Any],
    map_payload: dict[str, Any],
    supplied: dict[str, Path],
) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    accepted_hash = acceptance.get("acceptance_sha256")
    unsigned = dict(acceptance)
    unsigned.pop("acceptance_sha256", None)
    if accepted_hash != _canonical(unsigned):
        raise ProposalError("failed", "invalid_accepted_evidence", "acceptance hash does not verify")
    if (
        acceptance.get("schema_version") != ACCEPTANCE_SCHEMA
        or acceptance.get("consumer") != consumer
    ):
        raise ProposalError("failed", "invalid_accepted_evidence", "acceptance contract is wrong")
    verdict = acceptance.get("human_verdict")
    if (
        not isinstance(verdict, dict)
        or verdict.get("status") != "accepted"
        or not isinstance(verdict.get("reviewer"), str)
        or not verdict["reviewer"].strip()
    ):
        raise ProposalError("failed", "human_acceptance_required", "human verdict is not accepted")
    if verdict.get("boundary_verdicts") != BOUNDARY_VERDICTS:
        raise ProposalError(
            "failed",
            "kotlin_uncertainty_unresolved",
            "reflection/overload/delegation/generated/Gradle/Java/runtime/ABI boundaries are unresolved",
        )
    hashes = _artifact_hashes(root, acceptance, supplied)
    semantic = map_payload.get("analysis", {}).get("kotlin_semantic", {})
    lexical = map_payload.get("analysis", {}).get("kotlin", {})
    if (
        map_payload.get("status") != "complete"
        or map_payload.get("manifest_state") != "current-complete-and-coherent"
        or semantic.get("status") != "complete"
        or lexical.get("status") != "complete"
        or semantic.get("semantic_authority", {}).get("kotlin_version") != "2.4.10"
        or "k1-api" not in semantic.get("semantic_authority", {}).get("kind", "")
        or semantic.get("tools", {}).get("compiler_jar", {}).get("sha256")
        != COMPILER_SHA256
        or semantic.get("tools", {}).get("stdlib_jar", {}).get("sha256")
        != STDLIB_SHA256
        or lexical.get("source_manifest", {}).get("preserved") is not True
    ):
        raise ProposalError("partial", "upstream_not_complete", "Kotlin map evidence is incomplete")
    manifest = semantic.get("manifest")
    lexical_manifest = lexical.get("project_manifest")
    if (
        not isinstance(manifest, dict)
        or not isinstance(lexical_manifest, dict)
        or manifest.get("sources") != lexical_manifest.get("sources")
        or manifest.get("tests") != lexical_manifest.get("tests")
    ):
        raise ProposalError("partial", "upstream_not_complete", "Kotlin manifests diverge")
    expected_paths = {
        "kotlin-project.json",
        "kotlin-semantic-project.json",
        *manifest["sources"],
        *manifest["tests"],
    }
    source_rows = acceptance.get("source_hashes")
    if not isinstance(source_rows, list):
        raise ProposalError("failed", "invalid_accepted_evidence", "source hashes are missing")
    accepted_sources: dict[str, str] = {}
    for row in source_rows:
        if not isinstance(row, dict):
            raise ProposalError("failed", "invalid_accepted_evidence", "source hash row is invalid")
        path = _relative(row.get("path"), "accepted source path")
        digest = row.get("sha256")
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or path in accepted_sources
        ):
            raise ProposalError("failed", "invalid_accepted_evidence", "source hash is invalid")
        accepted_sources[path] = digest
    if set(accepted_sources) != expected_paths:
        raise ProposalError("failed", "invalid_accepted_evidence", "accepted source census changed")
    for path, digest in accepted_sources.items():
        candidate = root / path
        if not candidate.is_file() or candidate.is_symlink() or _sha256(candidate) != digest:
            raise ProposalError("failed", "stale_accepted_source", f"accepted source changed: {path}")
    selection = acceptance.get("selection")
    if not isinstance(selection, dict):
        raise ProposalError("failed", "invalid_selection", "selection is missing")
    return selection, hashes, accepted_sources


def _same_rows(left: Any, right: Any) -> bool:
    return _canonical(left) == _canonical(right)


def _callers(map_payload: dict[str, Any], signatures: set[str], paths: set[str]) -> list[dict[str, Any]]:
    return [
        row
        for row in map_payload.get("direct_resolved_calls", [])
        if row.get("target_signature") in signatures or row.get("path") in paths
    ]


def _manifest_after(
    selection: dict[str, Any], expected: dict[str, list[str]]
) -> dict[str, list[str]]:
    supplied = selection.get("manifest_sources_after")
    if not isinstance(supplied, dict) or set(supplied) != set(expected):
        raise ProposalError("failed", "invalid_selection", "manifest impact is incomplete")
    for name, sources in supplied.items():
        if (
            not isinstance(sources, list)
            or sources != expected[name]
            or len(sources) != len(set(sources))
            or any(not isinstance(path, str) or not path.endswith(".kt") for path in sources)
        ):
            raise ProposalError("failed", "invalid_selection", f"{name} sources changed")
    return supplied


def _boundary_plan(
    root: Path,
    selection: dict[str, Any],
    upstream: dict[str, Any],
    map_payload: dict[str, Any],
) -> dict[str, Any]:
    findings = upstream.get("findings")
    matches = [
        row
        for row in findings if isinstance(row, dict)
        and row.get("candidate_id") == selection.get("candidate_id")
    ] if isinstance(findings, list) else []
    if len(matches) != 1 or matches[0].get("bucket") != "confirmed_omnibus":
        raise ProposalError("failed", "invalid_selection", "accepted omnibus candidate changed")
    candidate = matches[0]
    target = _relative(selection.get("target"), "boundary target")
    domain = selection.get("domain")
    expected_names = candidate.get("clusters", {}).get(domain)
    rows = selection.get("declarations")
    if (
        candidate.get("file") != target
        or candidate.get("scout_verdict") != "explicit"
        or not isinstance(expected_names, list)
        or not isinstance(rows, list)
        or len(rows) < 2
    ):
        raise ProposalError("failed", "invalid_selection", "accepted Kotlin domain changed")
    map_rows = map_payload.get("qualified_declarations", [])
    declarations: list[dict[str, Any]] = []
    for row in rows:
        matches = [fact for fact in map_rows if _same_rows(fact, row)]
        if len(matches) != 1 or row.get("path") != target or row.get("kind") != "function":
            raise ProposalError("failed", "ambiguous_declaration", "declaration identity changed")
        declarations.append(row)
    if {row.get("fq_name") for row in declarations} != set(expected_names):
        raise ProposalError("failed", "ambiguous_overload_set", "accepted domain is incomplete")
    signatures = {row.get("signature") for row in declarations}
    if None in signatures or len(signatures) != len(declarations):
        raise ProposalError("failed", "ambiguous_overload_set", "signature inventory is ambiguous")
    expected_callers = _callers(map_payload, signatures, {target})
    if not _same_rows(selection.get("caller_impact"), expected_callers):
        raise ProposalError("failed", "ambiguous_callers", "accepted caller inventory changed")
    package = {row.get("path"): row.get("package") for row in map_payload.get("files", [])}
    impact = selection.get("package_impact")
    if impact != {
        "before": package.get(target),
        "after": package.get(target),
        "jvm_identity_change": False,
    }:
        raise ProposalError("failed", "invalid_selection", "package/JVM impact changed")
    edits = selection.get("exact_edits")
    creates = selection.get("create_files")
    if not isinstance(edits, list) or len(edits) != len(declarations) or not isinstance(creates, list) or len(creates) != 1:
        raise ProposalError("failed", "invalid_selection", "exact boundary edits are incomplete")
    for row in edits:
        if row.get("path") != target or row.get("after") != "" or row.get("expected_occurrences") != 1:
            raise ProposalError("failed", "invalid_selection", "boundary edit is invalid")
        before = row.get("before")
        if not isinstance(before, str) or (root / target).read_text(encoding="utf-8").count(before) != 1:
            raise ProposalError("failed", "stale_accepted_source", "boundary source block changed")
    created = creates[0]
    new_path = _relative(created.get("path"), "new boundary file")
    if (root / new_path).exists() or not isinstance(created.get("contents"), str):
        raise ProposalError("failed", "invalid_selection", "new boundary file is invalid")
    semantic_sources = map_payload["analysis"]["kotlin_semantic"]["manifest"]["sources"]
    lexical_sources = map_payload["analysis"]["kotlin"]["project_manifest"]["sources"]
    manifests = _manifest_after(
        selection,
        {
            "kotlin-project.json": [*lexical_sources, new_path],
            "kotlin-semantic-project.json": [*semantic_sources, new_path],
        },
    )
    return {
        "target": target,
        "domain": domain,
        "declarations": declarations,
        "caller_impact": expected_callers,
        "package_impact": impact,
        "exact_edits": edits,
        "create_files": creates,
        "exact_moves": [],
        "manifest_sources_after": manifests,
        "test_surface": selection.get("test_surface", []),
    }


def _folder_plan(
    root: Path,
    selection: dict[str, Any],
    upstream: dict[str, Any],
    map_payload: dict[str, Any],
) -> dict[str, Any]:
    findings = upstream.get("findings")
    matches = [
        row
        for row in findings if isinstance(row, dict)
        and row.get("evidence_sha256") == selection.get("finding_evidence_sha256")
    ] if isinstance(findings, list) else []
    if len(matches) != 1:
        raise ProposalError("failed", "invalid_selection", "accepted topology finding changed")
    finding = matches[0]
    parent = _relative(selection.get("parent"), "cluster parent")
    prefix = selection.get("prefix")
    files = selection.get("files")
    if (
        finding.get("pattern") != "flat_prefix_cluster"
        or finding.get("language") != "kotlin"
        or finding.get("file") != parent
        or finding.get("prefix") != prefix
        or finding.get("files") != files
        or finding.get("count", 0) < 3
    ):
        raise ProposalError("failed", "invalid_selection", "accepted Kotlin cluster changed")
    if selection.get("project_convention") != "group-three-or-more-authored-kotlin-siblings":
        raise ProposalError("failed", "project_convention_required", "project convention changed")
    moves = selection.get("exact_moves")
    if not isinstance(moves, list) or len(moves) != len(files):
        raise ProposalError("failed", "invalid_selection", "exact move plan is incomplete")
    destinations: set[str] = set()
    replacements: dict[str, str] = {}
    expected_parent = f"{parent}/{str(prefix).casefold()}"
    for row in moves:
        source = _relative(row.get("from"), "move source")
        destination = _relative(row.get("to"), "move destination")
        if (
            source not in files
            or source in replacements
            or PurePosixPath(destination).parent.as_posix() != expected_parent
            or PurePosixPath(source).name != PurePosixPath(destination).name
            or destination in destinations
            or not (root / source).is_file()
            or (root / destination).exists()
        ):
            raise ProposalError("failed", "invalid_selection", "folder move changed")
        replacements[source] = destination
        destinations.add(destination)
    if set(replacements) != set(files):
        raise ProposalError("failed", "invalid_selection", "cluster member accounting changed")
    map_files = {row.get("path"): row for row in map_payload.get("files", [])}
    declarations = [
        row for row in map_payload.get("qualified_declarations", []) if row.get("path") in files
    ]
    if set(files) - set(map_files) or not declarations:
        raise ProposalError("partial", "upstream_not_complete", "cluster lacks map coverage")
    packages = sorted({map_files[path].get("package") for path in files})
    impact = selection.get("package_impact")
    if impact != {
        "before": packages,
        "after": packages,
        "package_declarations_changed": False,
    }:
        raise ProposalError("failed", "invalid_selection", "package impact changed")
    signatures = {row.get("signature") for row in declarations}
    expected_callers = _callers(map_payload, signatures, set(files))
    if not _same_rows(selection.get("caller_impact"), expected_callers):
        raise ProposalError("failed", "ambiguous_callers", "accepted caller inventory changed")
    semantic_sources = map_payload["analysis"]["kotlin_semantic"]["manifest"]["sources"]
    lexical_sources = map_payload["analysis"]["kotlin"]["project_manifest"]["sources"]
    manifests = _manifest_after(
        selection,
        {
            "kotlin-project.json": [replacements.get(path, path) for path in lexical_sources],
            "kotlin-semantic-project.json": [replacements.get(path, path) for path in semantic_sources],
        },
    )
    return {
        "parent": parent,
        "prefix": prefix,
        "target": parent,
        "declarations": declarations,
        "caller_impact": expected_callers,
        "package_impact": impact,
        "exact_edits": [],
        "create_files": [],
        "exact_moves": moves,
        "manifest_sources_after": manifests,
        "test_surface": selection.get("test_surface", []),
    }


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProposalError("failed", "native_verification_failed", str(exc)) from exc


def _native(root: Path, kotlinc: Path, java: Path) -> dict[str, Any]:
    manifest = _read(root / "kotlin-semantic-project.json", "semantic manifest")
    sources = [_relative(path, "manifest source") for path in manifest.get("sources", [])]
    tests = [_relative(path, "manifest test") for path in manifest.get("tests", [])]
    if not sources or not tests or any(not (root / path).is_file() for path in [*sources, *tests]):
        raise ProposalError("failed", "native_verification_failed", "manifest inputs are unavailable")
    versions = {
        "kotlinc": _run([str(kotlinc), "-version"], root),
        "java": _run([str(java), "-version"], root),
    }
    kotlin_text = versions["kotlinc"].stdout + versions["kotlinc"].stderr
    java_text = versions["java"].stdout + versions["java"].stderr
    if versions["kotlinc"].returncode or not re.search(r"kotlinc-jvm 2\.4\.10(?:\s|$)", kotlin_text):
        raise ProposalError("failed", "native_verification_failed", "Kotlin 2.4.10 is required")
    if versions["java"].returncode or not re.search(r'version "17\.', java_text):
        raise ProposalError("failed", "native_verification_failed", "JDK 17 is required")
    with tempfile.TemporaryDirectory(prefix="kotlin-structure-native-") as temporary:
        build = Path(temporary)
        app = build / "app.jar"
        test = build / "tests.jar"
        common = [str(kotlinc), "-jvm-target", "17", "-Werror", "-include-runtime"]
        commands = {
            "compile": [*common, "-d", str(app), *(str(root / path) for path in sources)],
            "compile_tests": [
                *common,
                "-d",
                str(test),
                *(str(root / path) for path in sources),
                *(str(root / path) for path in tests),
            ],
            "test": [str(java), "-cp", str(test), manifest.get("test_main")],
            "smoke": [str(java), "-cp", str(app), manifest.get("smoke_main")],
        }
        results: dict[str, dict[str, Any]] = {}
        for name, argv in commands.items():
            if not all(isinstance(item, str) for item in argv):
                raise ProposalError("failed", "native_verification_failed", f"{name} is malformed")
            completed = _run(argv, root)
            if completed.returncode:
                raise ProposalError(
                    "failed", "native_verification_failed", f"{name}: {completed.stderr.strip()}"
                )
            results[name] = {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        if results["test"]["stdout"] != manifest.get("test_output"):
            raise ProposalError("failed", "native_verification_failed", "test output changed")
        if results["smoke"]["stdout"] != manifest.get("smoke_output"):
            raise ProposalError("failed", "native_verification_failed", "smoke output changed")
    return {
        "status": "passed",
        "kotlin_version": "2.4.10",
        "jdk": "17",
        "jvm_target": "17",
        "manifest_sources": sources,
        "manifest_tests": tests,
        "test_main": manifest["test_main"],
        "test_stdout": results["test"]["stdout"],
        "smoke_main": manifest["smoke_main"],
        "smoke_stdout": results["smoke"]["stdout"],
    }


def _apply(root: Path, plan: dict[str, Any]) -> None:
    for row in plan["exact_moves"]:
        destination = root / row["to"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        (root / row["from"]).replace(destination)
    for row in plan["exact_edits"]:
        path = root / row["path"]
        text = path.read_text(encoding="utf-8")
        if text.count(row["before"]) != row["expected_occurrences"]:
            raise ProposalError("failed", "disposable_plan_mismatch", f"edit changed: {row['path']}")
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")
    for row in plan["create_files"]:
        path = root / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["contents"], encoding="utf-8")
    for manifest_name, sources in plan["manifest_sources_after"].items():
        path = root / manifest_name
        payload = _read(path, manifest_name)
        payload["sources"] = sources
        _atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _disposable(root: Path, plan: dict[str, Any], kotlinc: Path, java: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="kotlin-structure-after-") as temporary:
        host = Path(temporary) / "host"
        shutil.copytree(
            root,
            host,
            ignore=shutil.ignore_patterns(".git", "reports", ".native-build", ".engineering"),
        )
        _apply(host, plan)
        result = _native(host, kotlinc, java)
        result["disposable"] = True
        result["manifest_sources_after"] = plan["manifest_sources_after"]
        return result


def _proposal(payload: dict[str, Any], consumer: str) -> str:
    title = "Kotlin boundary proposal" if consumer == "propose-boundary" else "Kotlin folder reorganization proposal"
    lines = [
        "---",
        "language: kotlin",
        "status: ready_for_human_review",
        "read_only: true",
        "---",
        "",
        f"# {title}",
        "",
        f"Target: `{payload['target']}`",
        "",
        "## Exact declarations",
        "",
        *[
            f"- `{row['fq_name']}` — `{row['signature']}` at `{row['path']}:{row['line']}`"
            for row in payload["declarations"]
        ],
        "",
        "## Caller and package impact",
        "",
        f"- Exact resolved caller rows: **{len(payload['caller_impact'])}**",
        f"- Package impact: `{json.dumps(payload['package_impact'], sort_keys=True)}`",
        "",
        "## Manifest and native stop condition",
        "",
        "- Apply only the exact scope.json edits/moves and manifest source lists.",
        "- Kotlin/JVM 2.4.10 and JDK 17 test/smoke must match before and after.",
        "- Stop on any source, artifact, caller, declaration, package, or manifest mismatch.",
        "",
        "## Nonclaims",
        "",
        *[f"- {item}" for item in NONCLAIMS],
        "",
        "Human approval is still required before any host mutation.",
        "",
    ]
    return "\n".join(lines)


def _failure(consumer: str, error: ProposalError) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "skill": consumer,
        "language": "kotlin",
        "status": error.status,
        "outcome": "refused",
        "failure_kind": error.kind,
        "message": error.detail,
        "read_only": True,
        "source_mutations": 0,
        "nonclaims": NONCLAIMS,
    }


def main(consumer: str, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    producer_flag = "--omnibus" if consumer == "propose-boundary" else "--topology"
    parser.add_argument(producer_flag, required=True, type=Path, dest="producer")
    parser.add_argument("--map-evidence", required=True, type=Path)
    parser.add_argument("--acceptance", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--kotlinc", required=True, type=Path)
    parser.add_argument("--java", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        if not root.is_dir() or root.is_symlink():
            raise ProposalError("failed", "invalid_project_root", "project root is unsafe")
        output = _output(root, args.output_dir, consumer)
    except (OSError, RuntimeError, ProposalError) as exc:
        parser.error(str(exc))
    try:
        producer = _input(root, args.producer, "producer")
        map_path = _input(root, args.map_evidence, "map evidence")
        acceptance_path = _input(root, args.acceptance, "acceptance")
        kotlinc = args.kotlinc.resolve(strict=True)
        java = args.java.resolve(strict=True)
        upstream = _read(producer, "producer")
        map_payload = _read(map_path, "Kotlin map")
        acceptance = _read(acceptance_path, "acceptance")
        kind = "confirmed-omnibus" if consumer == "propose-boundary" else "lexical-topology"
        selection, artifact_hashes, accepted_sources = _validate_acceptance(
            root,
            consumer,
            acceptance,
            map_payload,
            {kind: producer, "kotlin-map": map_path},
        )
        if upstream.get("status") != "complete" or upstream.get("outcome") == "incomplete":
            raise ProposalError("partial", "upstream_not_complete", "producer is incomplete")
        before = {path: _sha256(root / path) for path in accepted_sources}
        plan = (
            _boundary_plan(root, selection, upstream, map_payload)
            if consumer == "propose-boundary"
            else _folder_plan(root, selection, upstream, map_payload)
        )
        current = _native(root, kotlinc, java)
        disposable = _disposable(root, plan, kotlinc, java)
        after = {path: _sha256(root / path) for path in accepted_sources}
        if after != before:
            raise ProposalError("failed", "unexpected_source_mutation", "host source changed")
        payload = {
            "schema_version": SCHEMA,
            "skill": consumer,
            "language": "kotlin",
            "status": "ready_for_human_review",
            "outcome": "proposal_ready",
            "failure_kind": "none",
            "read_only": True,
            "source_mutations": 0,
            "accepted_evidence": {
                "acceptance_sha256": acceptance["acceptance_sha256"],
                "artifact_sha256": artifact_hashes,
                "source_sha256": accepted_sources,
            },
            **plan,
            "native_verification": {
                "current_tree": current,
                "disposable_after_tree": disposable,
            },
            "source_preservation": {
                "verified": True,
                "before_sha256": _canonical(before),
                "after_sha256": _canonical(after),
            },
            "semantic_authority": map_payload["semantic_authority"],
            "boundary_verdicts": BOUNDARY_VERDICTS,
            "nonclaims": NONCLAIMS,
        }
        _replace(output, payload, _proposal(payload, consumer), consumer)
        return 0
    except (OSError, RuntimeError, UnicodeDecodeError, ProposalError) as exc:
        error = exc if isinstance(exc, ProposalError) else ProposalError("failed", "consumer_failed", str(exc))
        payload = _failure(consumer, error)
        proposal = (
            f"# Kotlin structure proposal refused\n\n"
            f"Status: `{error.status}`\n\nFailure: `{error.kind}` — {error.detail}\n"
        )
        _replace(output, payload, proposal, consumer)
        return 2
