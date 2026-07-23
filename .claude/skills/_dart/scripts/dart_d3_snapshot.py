#!/usr/bin/env python3
"""Key one accepted Dart syntax-provider result for the four D3 consumers.

This module owns provider invocation, provenance, and validation only. It does
not assign complexity scores, normalize clone groups, select explanation
targets, or grade omnibus candidates.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

sys.dont_write_bytecode = True


SCHEMA_VERSION = 1
ANALYZER = "dart-d3-union-syntax-snapshot-v1"
ACCEPTED_TOOL_PACKAGE_SHA256 = "77486420178671884b4b0e409e44ad0d58080d6a29eaef41bd2bab56314acb6e"
CONSUMER_UNION = (
    "explain-code",
    "find-complexity-hotspots",
    "find-duplication",
    "find-omnibus",
)


class SnapshotError(ValueError):
    """A bounded snapshot refusal that consumers must publish visibly."""

    def __init__(self, failure_kind: str, detail: str, *, status: str = "failed") -> None:
        super().__init__(detail)
        self.failure_kind = failure_kind
        self.status = status


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_hash(payload: Any) -> str:
    return _hash(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SnapshotError("dart_syntax_provider_unloadable", f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _provider() -> ModuleType | None:
    path = Path(__file__).resolve().with_name("dart_syntax_facts.py")
    return _module(path, "dart_syntax_facts") if path.is_file() else None


def _source_manifest(files: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in sorted(files, key=lambda item: item["file"]):
        digest.update(row["file"].encode())
        digest.update(b"\0")
        digest.update(row["source_sha256"].encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    key = payload["snapshot_key"]
    payload["snapshot_key_sha256"] = _canonical_hash(key)
    payload.pop("snapshot_sha256", None)
    payload["snapshot_sha256"] = _canonical_hash(payload)
    return payload


def terminal(status: str, failure_kind: str, detail: str | None = None) -> dict[str, Any]:
    provider = {
        "schema_version": 1,
        "analyzer": "dart-syntax-facts-v1",
        "status": status,
        "failure_kind": failure_kind,
        "inventory": [],
        "files": [],
        "source_manifest": {"preserved": True},
        "tool_package": {},
        "tools": {},
        "native": {},
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "analyzer": ANALYZER,
        "status": status,
        "failure_kind": failure_kind,
        "consumer_union": list(CONSUMER_UNION),
        "snapshot_key": {
            "source_manifest_sha256": None,
            "selected_source_manifest_sha256": None,
            "tool_package_sha256": None,
            "analyzer_package": None,
            "dart_sdk_version": None,
            "target": None,
            "native_options": {},
        },
        "provider": provider,
    }
    if detail:
        payload["failure_detail"] = detail
    return _finalize(payload)


def collect(
    project_root: Path,
    target: Path,
    *,
    dart: str | None,
    pub_cache: Path | None,
    native_test: Path | None,
    smoke: Path | None,
    smoke_stdout: str | None,
    tool_root: Path | None,
) -> tuple[dict[str, Any], int]:
    provider_module = _provider()
    if provider_module is None:
        return terminal("partial", "dart_syntax_provider_missing"), 2
    provider, code = provider_module.produce(
        project_root,
        target,
        dart=dart,
        pub_cache=pub_cache,
        native_test=native_test,
        smoke=smoke,
        smoke_stdout=smoke_stdout,
        tool_root=tool_root,
    )
    tool_sha = provider.get("tool_package", {}).get("sha256")
    status = provider.get("status", "failed")
    failure_kind = provider.get("failure_kind", "provider_payload_invalid")
    if tool_sha and tool_sha != ACCEPTED_TOOL_PACKAGE_SHA256:
        status, failure_kind, code = "failed", "stale_dart_syntax_provider", 2
    source_manifest = provider.get("source_manifest", {})
    payload = {
        "schema_version": SCHEMA_VERSION,
        "analyzer": ANALYZER,
        "status": status,
        "failure_kind": failure_kind,
        "consumer_union": list(CONSUMER_UNION),
        "snapshot_key": {
            "source_manifest_sha256": source_manifest.get("before_sha256"),
            "selected_source_manifest_sha256": _source_manifest(provider.get("files", [])),
            "tool_package_sha256": tool_sha,
            "analyzer_package": provider.get("analyzer_package"),
            "dart_sdk_version": provider.get("tools", {}).get("dart", {}).get("version"),
            "target": provider.get("target"),
            "native_options": {
                "native_test": None if native_test is None else str(native_test),
                "smoke": None if smoke is None else str(smoke),
                "smoke_stdout": smoke_stdout,
            },
        },
        "provider": provider,
    }
    return _finalize(payload), 0 if status == "complete" and code == 0 else 2


def _verify_hashes(payload: dict[str, Any]) -> None:
    supplied = payload.get("snapshot_sha256")
    unsigned = dict(payload)
    unsigned.pop("snapshot_sha256", None)
    if supplied != _canonical_hash(unsigned):
        raise SnapshotError("dart_d3_snapshot_integrity_failed", "snapshot hash does not verify")
    if payload.get("snapshot_key_sha256") != _canonical_hash(payload.get("snapshot_key")):
        raise SnapshotError(
            "dart_d3_snapshot_integrity_failed", "snapshot key hash does not verify"
        )


def _covered_target(root: Path, requested: Path, packed: str | None) -> None:
    if packed is None:
        return
    target = requested if requested.is_absolute() else root / requested
    try:
        relative = target.resolve().relative_to(root)
        relative.relative_to(Path(packed))
    except ValueError as exc:
        raise SnapshotError(
            "dart_d3_snapshot_target_mismatch",
            "snapshot does not cover the consumer target",
        ) from exc


def load_for_consumer(
    facts: Path,
    project_root: Path,
    target: Path,
    *,
    consumer: str,
    required_fact_groups: tuple[str, ...],
) -> dict[str, Any]:
    if not facts.is_file():
        raise SnapshotError(
            "dart_d3_snapshot_missing",
            f"snapshot does not exist: {facts}",
            status="partial",
        )
    try:
        payload = json.loads(facts.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError("dart_d3_snapshot_invalid", str(exc)) from exc
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("analyzer") != ANALYZER:
        raise SnapshotError("dart_d3_snapshot_incompatible", "unexpected snapshot schema")
    _verify_hashes(payload)
    if consumer not in payload.get("consumer_union", []):
        raise SnapshotError("dart_d3_snapshot_consumer_missing", consumer)
    root = project_root.resolve()
    provider = payload.get("provider")
    if not isinstance(provider, dict):
        raise SnapshotError("dart_d3_snapshot_invalid", "provider payload is missing")
    _covered_target(root, target, payload.get("snapshot_key", {}).get("target"))
    tool_sha = payload.get("snapshot_key", {}).get("tool_package_sha256")
    if tool_sha is not None and tool_sha != ACCEPTED_TOOL_PACKAGE_SHA256:
        raise SnapshotError("stale_dart_syntax_provider", "provider manifest is not accepted")
    if provider.get("source_manifest", {}).get("preserved") is False:
        raise SnapshotError("unexpected_source_mutation", "provider observed source mutation")
    for row in provider.get("files", []):
        source = root / row.get("file", "")
        if (
            not source.is_file()
            or source.is_symlink()
            or _hash(source.read_bytes()) != row.get("source_sha256")
        ):
            raise SnapshotError(
                "dart_d3_snapshot_stale",
                f"snapshot is stale for {row.get('file', '<unknown>')}",
            )
    if payload.get("status") == "complete":
        if provider.get("status") != "complete":
            raise SnapshotError(
                "dart_d3_snapshot_invalid", "complete wrapper has incomplete provider"
            )
        for row in provider.get("files", []):
            missing = [name for name in required_fact_groups if not isinstance(row.get(name), list)]
            if missing:
                raise SnapshotError(
                    "dart_d3_required_facts_missing",
                    f"{row.get('file')}: missing {', '.join(missing)}",
                )
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dart")
    parser.add_argument("--pub-cache", type=Path)
    parser.add_argument("--native-test", type=Path)
    parser.add_argument("--smoke", type=Path)
    parser.add_argument("--smoke-stdout")
    parser.add_argument("--tool-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output.is_symlink() or args.output.suffix.casefold() == ".dart":
        _parser().error("--output must be a non-symlink, non-source artifact")
    payload, code = collect(
        args.project_root,
        args.target,
        dart=args.dart,
        pub_cache=args.pub_cache,
        native_test=args.native_test,
        smoke=args.smoke,
        smoke_stdout=args.smoke_stdout,
        tool_root=args.tool_root,
    )
    _atomic(args.output.resolve(), json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.output.resolve())
    return code


if __name__ == "__main__":
    raise SystemExit(main())
