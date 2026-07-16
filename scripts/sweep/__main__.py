"""Command-line entry point for the productized batch sweep."""
# spec:portable-batch-sweep::IM-8
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .commands import (
    EXIT_CHANGED,
    EXIT_INPUT,
    EXIT_OK,
    EXIT_OUTPUT,
    EXIT_PROVIDER,
    apply_ratchet,
    atomic_write_bytes,
    render_digest,
    scan_native,
    scan_profile,
)
from .manifest import ManifestIdentityError, build_diff, read_manifest, write_manifest
from .native import ProviderExecutionError
from .pipeline import (
    build_judgment,
    build_judgment_input,
    build_packet,
    run_scan_command,
    verify_packet,
)
from .profile import load_sweep_profile
from .schemas import SchemaValidationError, trusted_parser_run_context
from .serialization import canonical_json_bytes


def _tool_map(values: Sequence[str]) -> dict[str, Path]:
    tools: dict[str, Path] = {}
    for value in values:
        provider, separator, path = value.partition("=")
        if not separator or not provider.strip() or not path.strip():
            raise ValueError("--tool must use PROVIDER=/absolute/path")
        candidate = Path(path)
        if not candidate.is_absolute():
            raise ValueError("--tool paths must be absolute")
        if provider in tools:
            raise ValueError(f"duplicate --tool provider: {provider}")
        tools[provider] = candidate
    return tools


def _source(args: argparse.Namespace) -> dict[str, object]:
    return {
        "revision": args.revision,
        "dirty": args.dirty,
        "dirty_state_hash": args.dirty_state_hash,
    }


def _manifest_context(root: Path | None):
    return trusted_parser_run_context(root) if root is not None else None


def _read_manifest(path: Path, *, root: Path | None = None) -> dict[str, object]:
    return read_manifest(path, parser_run_context=_manifest_context(root))


def _scan(args: argparse.Namespace) -> int:
    tools = _tool_map(args.tool)
    if args.profile is not None:
        if args.scope or args.case_sensitive is not None:
            raise ValueError(
                "--profile cannot be combined with --scope or an explicit case policy"
            )
        manifest = scan_profile(
            root=args.root,
            profile=load_sweep_profile(args.profile),
            source=_source(args),
            executables=tools,
        )
    else:
        if args.case_sensitive is None:
            raise ValueError("legacy --language scans require an explicit case policy")
        manifest = scan_native(
            root=args.root,
            languages=args.language,
            scopes=args.scope or (".",),
            case_sensitive=args.case_sensitive,
            source=_source(args),
            executables=tools,
        )
    written = write_manifest(
        args.out,
        manifest,
        parser_run_context=_manifest_context(args.root),
    )
    sys.stdout.buffer.write(canonical_json_bytes(written))
    return EXIT_OK


def _digest(args: argparse.Namespace) -> int:
    parser_run_context = _manifest_context(args.root)
    content = render_digest(
        _read_manifest(args.manifest, root=args.root),
        _read_json(args.judgments, "judgment"),
        purpose=args.purpose,
        finding_limit=args.top,
        byte_limit=args.byte_limit,
        parser_run_context=parser_run_context,
    )
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    return EXIT_OK


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} JSON: {exc}") from exc


def _judgment_input(args: argparse.Namespace) -> int:
    parser_run_context = _manifest_context(args.root)
    document = build_judgment_input(
        _read_manifest(args.manifest, root=args.root),
        offset=args.offset,
        finding_limit=args.top,
        byte_limit=args.byte_limit,
        parser_run_context=parser_run_context,
    )
    content = canonical_json_bytes(document)
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    return EXIT_OK


def _judgment_import(args: argparse.Namespace) -> int:
    outcomes = _read_json(args.outcomes, "outcomes")
    if not isinstance(outcomes, list):
        raise ValueError("outcomes JSON must be an array")
    document = build_judgment(
        _read_manifest(args.manifest, root=args.root),
        judge_identity=args.judge_identity,
        judge_version=args.judge_version,
        outcomes=outcomes,
        parser_run_context=_manifest_context(args.root),
    )
    content = canonical_json_bytes(document)
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    return EXIT_OK


def _packet(args: argparse.Namespace) -> int:
    expected = _read_json(args.expected_delta, "expected delta")
    if not isinstance(expected, dict):
        raise ValueError("expected delta JSON must be an object")
    document = build_packet(
        _read_manifest(args.manifest, root=args.root),
        _read_json(args.judgments, "judgment"),
        finding_ids=args.finding_id,
        scope=args.scope,
        recipe=args.recipe,
        verification=args.verification,
        expected_delta=expected,
        token_budget=args.token_budget,
        parser_run_context=_manifest_context(args.root),
    )
    content = canonical_json_bytes(document)
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    return EXIT_OK


def _verify(args: argparse.Namespace) -> int:
    packet = _read_json(args.packet, "packet")
    judgment = _read_json(args.judgments, "judgment")
    if not isinstance(packet, dict) or not isinstance(judgment, dict):
        raise ValueError("packet and judgment JSON must be objects")
    before = _read_manifest(args.before_manifest, root=args.root)
    evidence = verify_packet(
        packet,
        before,
        judgment,
        root=args.root,
        scanner=lambda: run_scan_command(args.scan_command, args.root),
    )
    content = canonical_json_bytes(evidence)
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    return EXIT_OK


def _diff(args: argparse.Namespace) -> int:
    parser_run_context = _manifest_context(args.root)
    document = build_diff(
        _read_manifest(args.before, root=args.root),
        _read_manifest(args.after, root=args.root),
        parser_run_context=parser_run_context,
    )
    content = canonical_json_bytes(document)
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    return EXIT_CHANGED if document["new"] else EXIT_OK


def _read_accepts(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read accept file: {exc}") from exc
    if not isinstance(document, list) or any(not isinstance(row, dict) for row in document):
        raise ValueError("accept file must contain a JSON array of objects")
    return document


def _ratchet(args: argparse.Namespace) -> int:
    parser_run_context = _manifest_context(args.root)
    baseline = _read_manifest(args.baseline, root=args.root)
    current = _read_manifest(args.current, root=args.root)
    result = apply_ratchet(
        baseline,
        current,
        accepts=_read_accepts(args.accept_file),
        parser_run_context=parser_run_context,
    )
    content = canonical_json_bytes(result.diff)
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    if result.violations:
        for violation in result.violations:
            print(violation, file=sys.stderr)
        return EXIT_CHANGED
    if result.tighten and not args.no_update:
        write_manifest(
            args.baseline,
            current,
            parser_run_context=parser_run_context,
        )
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sweep", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    scan = subcommands.add_parser(
        "scan", help="run a registry-selected native and parser battery"
    )
    scan.add_argument("--root", type=Path, required=True)
    scan.add_argument("--out", type=Path, required=True)
    selection = scan.add_mutually_exclusive_group(required=True)
    selection.add_argument("--profile", type=Path)
    selection.add_argument("--language", action="append")
    scan.add_argument("--scope", action="append")
    case = scan.add_mutually_exclusive_group()
    case.add_argument("--case-sensitive", action="store_true", dest="case_sensitive")
    case.add_argument("--case-insensitive", action="store_false", dest="case_sensitive")
    scan.set_defaults(case_sensitive=None)
    dirty = scan.add_mutually_exclusive_group(required=True)
    dirty.add_argument("--dirty", action="store_true", dest="dirty")
    dirty.add_argument("--clean", action="store_false", dest="dirty")
    scan.add_argument("--revision", required=True)
    scan.add_argument("--dirty-state-hash", required=True)
    scan.add_argument(
        "--tool",
        action="append",
        required=True,
        metavar="PROVIDER=/ABSOLUTE/PATH",
    )
    scan.set_defaults(handler=_scan)

    judgment_input = subcommands.add_parser(
        "judgment-input", help="write one bounded classification batch"
    )
    judgment_input.add_argument("--manifest", type=Path, required=True)
    judgment_input.add_argument("--root", type=Path)
    judgment_input.add_argument("--out", type=Path, required=True)
    judgment_input.add_argument("--offset", type=int, default=0)
    judgment_input.add_argument("--top", type=int, default=50)
    judgment_input.add_argument("--byte-limit", type=int, default=65_536)
    judgment_input.set_defaults(handler=_judgment_input)

    judgment_import = subcommands.add_parser(
        "judgment-import", help="validate and bind run-local outcomes"
    )
    judgment_import.add_argument("--manifest", type=Path, required=True)
    judgment_import.add_argument("--root", type=Path)
    judgment_import.add_argument("--outcomes", type=Path, required=True)
    judgment_import.add_argument("--judge-identity", required=True)
    judgment_import.add_argument("--judge-version", required=True)
    judgment_import.add_argument("--out", type=Path, required=True)
    judgment_import.set_defaults(handler=_judgment_import)

    digest = subcommands.add_parser("digest", help="write a judgment-gated bounded digest")
    digest.add_argument("--manifest", type=Path, required=True)
    digest.add_argument("--root", type=Path)
    digest.add_argument("--judgments", type=Path, required=True)
    digest.add_argument("--purpose", choices=("agent", "dashboard", "rank"), required=True)
    digest.add_argument("--out", type=Path, required=True)
    digest.add_argument("--top", type=int, default=50)
    digest.add_argument("--byte-limit", type=int, default=65_536)
    digest.set_defaults(handler=_digest)

    packet = subcommands.add_parser("packet", help="create a fresh actionable sweep packet")
    packet.add_argument("--manifest", type=Path, required=True)
    packet.add_argument("--root", type=Path)
    packet.add_argument("--judgments", type=Path, required=True)
    packet.add_argument("--finding-id", action="append", required=True)
    packet.add_argument("--scope", action="append", required=True)
    packet.add_argument("--recipe", required=True)
    packet.add_argument("--verification", required=True)
    packet.add_argument("--expected-delta", type=Path, required=True)
    packet.add_argument("--token-budget", type=int, required=True)
    packet.add_argument("--out", type=Path, required=True)
    packet.set_defaults(handler=_packet)

    verify = subcommands.add_parser(
        "verify", help="run harness-owned verification, rescan, and expected-delta gates"
    )
    verify.add_argument("--packet", type=Path, required=True)
    verify.add_argument("--before-manifest", type=Path, required=True)
    verify.add_argument("--judgments", type=Path, required=True)
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument(
        "--scan-command",
        required=True,
        help="Harness-selected shell-free scanner command emitting one canonical manifest.",
    )
    verify.add_argument("--out", type=Path, required=True)
    verify.set_defaults(handler=_verify)

    diff = subcommands.add_parser("diff", help="compare two complete manifests")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--root", type=Path)
    diff.add_argument("--out", type=Path, required=True)
    diff.set_defaults(handler=_diff)

    ratchet = subcommands.add_parser("ratchet", help="enforce and tighten a manifest baseline")
    ratchet.add_argument("--baseline", type=Path, required=True)
    ratchet.add_argument("--current", type=Path, required=True)
    ratchet.add_argument("--root", type=Path)
    ratchet.add_argument("--out", type=Path, required=True)
    ratchet.add_argument("--accept-file", type=Path)
    ratchet.add_argument("--no-update", action="store_true")
    ratchet.set_defaults(handler=_ratchet)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ProviderExecutionError as exc:
        sys.stderr.buffer.write(canonical_json_bytes(exc.failure))
        return EXIT_PROVIDER
    except (SchemaValidationError, ManifestIdentityError, ValueError) as exc:
        print(f"input_error: {exc}", file=sys.stderr)
        return EXIT_INPUT
    except OSError as exc:
        print(f"output_error: {exc}", file=sys.stderr)
        return EXIT_OUTPUT


if __name__ == "__main__":
    raise SystemExit(main())
