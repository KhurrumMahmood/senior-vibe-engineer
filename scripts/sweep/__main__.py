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
)
from .manifest import ManifestIdentityError, build_diff, read_manifest, write_manifest
from .native import ProviderExecutionError
from .schemas import SchemaValidationError
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


def _scan(args: argparse.Namespace) -> int:
    manifest = scan_native(
        root=args.root,
        languages=args.language,
        scopes=args.scope or (".",),
        case_sensitive=args.case_sensitive,
        source=_source(args),
        executables=_tool_map(args.tool),
    )
    written = write_manifest(args.out, manifest)
    sys.stdout.buffer.write(canonical_json_bytes(written))
    return EXIT_OK


def _digest(args: argparse.Namespace) -> int:
    content = render_digest(
        read_manifest(args.manifest),
        finding_limit=args.finding_limit,
        byte_limit=args.byte_limit,
    )
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    return EXIT_OK


def _diff(args: argparse.Namespace) -> int:
    document = build_diff(read_manifest(args.before), read_manifest(args.after))
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
    baseline = read_manifest(args.baseline)
    current = read_manifest(args.current)
    result = apply_ratchet(baseline, current, accepts=_read_accepts(args.accept_file))
    content = canonical_json_bytes(result.diff)
    atomic_write_bytes(args.out, content)
    sys.stdout.buffer.write(content)
    if result.violations:
        for violation in result.violations:
            print(violation, file=sys.stderr)
        return EXIT_CHANGED
    if result.tighten and not args.no_update:
        write_manifest(args.baseline, current)
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sweep", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    scan = subcommands.add_parser("scan", help="run the declared native battery")
    scan.add_argument("--root", type=Path, required=True)
    scan.add_argument("--out", type=Path, required=True)
    scan.add_argument("--language", action="append", required=True)
    scan.add_argument("--scope", action="append")
    case = scan.add_mutually_exclusive_group(required=True)
    case.add_argument("--case-sensitive", action="store_true", dest="case_sensitive")
    case.add_argument("--case-insensitive", action="store_false", dest="case_sensitive")
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

    digest = subcommands.add_parser("digest", help="write a bounded manifest digest")
    digest.add_argument("manifest", type=Path)
    digest.add_argument("--out", type=Path, required=True)
    digest.add_argument("--finding-limit", type=int, default=50)
    digest.add_argument("--byte-limit", type=int, default=65_536)
    digest.set_defaults(handler=_digest)

    diff = subcommands.add_parser("diff", help="compare two complete manifests")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--out", type=Path, required=True)
    diff.set_defaults(handler=_diff)

    ratchet = subcommands.add_parser("ratchet", help="enforce and tighten a manifest baseline")
    ratchet.add_argument("--baseline", type=Path, required=True)
    ratchet.add_argument("--current", type=Path, required=True)
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
