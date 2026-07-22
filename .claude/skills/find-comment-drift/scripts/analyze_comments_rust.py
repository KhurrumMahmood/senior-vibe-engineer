#!/usr/bin/env python3
"""Produce bounded Rust comment-drift artifacts from exact source bytes.

The copied helper combines a Rust-aware byte lexer with host-owned native
gates. ``cargo check`` validates the locked workspace snapshot and ``rustfmt``
parses each eligible source without writing it. The only behavior claim is a
deliberately narrow adjacent-item rule: a comment says a function calculates a
percentage from an amount, while that complete function body returns one fixed
numeric literal. Macro expansion, build-script output, cfg variants without
selection evidence, name resolution, traits, and runtime dispatch are not
inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_RUST = (1, 85, 0)
MINIMUM_RUST_TEXT = "1.85.0"
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen"})
BUILD_DIRS = frozenset({"target", "build", "dist", "out"})
AUXILIARY_DIRS = frozenset({"examples", "benches"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
STALE_TERM_RE = re.compile(r"\b(?:SiteConfig|Site Configuration|site configuration|site config)\b")
DOC_REF_RE = re.compile(r"\b(?:L\d{2,}|line\s+\d{2,}|[A-Za-z0-9_./-]+\.rs:\d{1,5})\b", re.I)
SECTION_BANNER_RE = re.compile(r"^section\s+\d+.*$", re.I)
UPPER_BANNER_RE = re.compile(r"^[A-Z][A-Z0-9 _/:-]{5,}$")
PERCENT_CLAIM_RE = re.compile(
    r"\b(?:calculates?|computes?|derives?)\b.*\b(?:percentage|percent(?:age)?\s+fee|rate)\b"
    r".*\b(?:from|of|based\s+on)\b.*\b(?:amount|subtotal|total)\b",
    re.I,
)
FN_RE = re.compile(
    rb"(?P<leading>[ \t\r\n]*)"
    rb"(?P<attrs>(?:\#\[[^\]\n]*\][ \t\r\n]*)*)"
    rb"(?P<prefix>(?:pub(?:\([^\n)]*\))?\s+)?(?:(?:const|async|unsafe)\s+)*"
    rb"(?:extern\s+\"[^\n\"]+\"\s+)?fn\s+)"
    rb"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*",
)
FIXED_RETURN_RE = re.compile(
    rb"(?:return\s+)?(?P<literal>-?\d(?:[\d_]*\d)?(?:\.\d(?:[\d_]*\d)?)?"
    rb"(?:u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize|f32|f64)?)\s*;?"
)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _run(
    argv: list[str], cwd: Path, *, env: dict[str, str] | None = None, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _which(command: str) -> Path | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory or ".") / command
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def _exclusion(path: Path, root: Path, text: str) -> str | None:
    relative = path.relative_to(root)
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if "vendor" in parts:
        return "vendor"
    if parts & BUILD_DIRS:
        return "build-tree"
    if parts & TEST_DIRS or name.endswith("_test.rs"):
        return "test"
    if parts & AUXILIARY_DIRS:
        return "auxiliary-target"
    if parts & GENERATED_DIRS:
        return "generated-tree"
    if name == "build.rs":
        return "configuration"
    if GENERATED_RE.search(text[:4096]):
        return "generated-marker"
    return None


def _discover(targets: Iterable[str], root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    paths: dict[str, Path] = {}
    errors: list[str] = []
    for raw in targets:
        logical = Path(raw)
        logical = logical if logical.is_absolute() else root / logical
        logical = Path(os.path.abspath(logical))
        try:
            logical.relative_to(root)
        except ValueError:
            errors.append(f"target-outside-project:{raw}")
            continue
        if not logical.exists() and not logical.is_symlink():
            errors.append(f"target-missing:{raw}")
            continue
        if logical.is_symlink():
            paths[_relative(logical, root)] = logical
            continue
        if logical.is_file():
            if logical.suffix.casefold() == ".rs":
                paths[_relative(logical, root)] = logical
            continue
        for directory, dirnames, filenames in os.walk(logical, followlinks=False):
            current = Path(directory)
            symlink_dirs = [name for name in dirnames if (current / name).is_symlink()]
            for name in symlink_dirs:
                path = current / name
                paths[_relative(path, root)] = path
            dirnames[:] = sorted(name for name in dirnames if name not in symlink_dirs)
            for name in sorted(filenames):
                path = current / name
                if path.suffix.casefold() == ".rs":
                    paths[_relative(path, root)] = path

    inventory: list[dict[str, Any]] = []
    for relative, path in sorted(paths.items()):
        if path.is_symlink():
            inventory.append(
                {"file": relative, "path": path, "role": "excluded", "reason": "symlink"}
            )
            continue
        try:
            content = path.read_bytes()
            text = content.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            inventory.append(
                {
                    "file": relative,
                    "path": path,
                    "role": "failed",
                    "reason": "read-error",
                    "detail": str(exc),
                }
            )
            continue
        reason = _exclusion(path, root, text)
        inventory.append(
            {
                "file": relative,
                "path": path,
                "role": "excluded" if reason else "candidate",
                **({"reason": reason} if reason else {}),
                "source_sha256": _hash_bytes(content),
                "source_bytes": len(content),
            }
        )
    return inventory, errors


def _version_tuple(text: str, tool: str) -> tuple[int, int, int] | None:
    match = re.search(rf"\b{re.escape(tool)}\s+(\d+)\.(\d+)\.(\d+)", text)
    return tuple(map(int, match.groups())) if match else None


def _probe_tool(path: Path | None, name: str, root: Path) -> dict[str, Any]:
    if path is None or not path.is_file() or not os.access(path, os.X_OK):
        return {"state": "missing", "failure_kind": f"{name}-tool-missing"}
    args = [str(path), "--version"]
    if name == "rustc":
        args.append("--verbose")
    result = _run(args, root)
    if result.returncode != 0:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-failed",
            "detail": (result.stderr or result.stdout).strip(),
        }
    version = _version_tuple(result.stdout, name)
    if version is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-unrecognized",
            "detail": result.stdout.strip(),
        }
    meets_minimum = name == "rustfmt" or version >= MINIMUM_RUST
    return {
        "state": "ready" if meets_minimum else "too-old",
        "path": str(path),
        "version": ".".join(map(str, version)),
        **({"minimum_version": MINIMUM_RUST_TEXT} if name != "rustfmt" else {}),
        **({"failure_kind": f"{name}-version-too-old"} if not meets_minimum else {}),
    }


def _blank(mask: bytearray, start: int, end: int) -> None:
    for index in range(start, end):
        if mask[index] not in (10, 13):
            mask[index] = 32


def _raw_string_end(source: bytes, start: int) -> int | None:
    if start and (source[start - 1 : start].isalnum() or source[start - 1] == 95):
        return None
    prefix = None
    for candidate in (b"br", b"cr", b"r"):
        if source.startswith(candidate, start):
            prefix = candidate
            break
    if prefix is None:
        return None
    cursor = start + len(prefix)
    hashes = 0
    while cursor < len(source) and source[cursor] == 35:
        hashes += 1
        cursor += 1
    if cursor >= len(source) or source[cursor] != 34:
        return None
    terminator = b'"' + b"#" * hashes
    found = source.find(terminator, cursor + 1)
    return len(source) if found < 0 else found + len(terminator)


def _quoted_end(source: bytes, quote: int, *, escaped: bool = True) -> int:
    cursor = quote + 1
    while cursor < len(source):
        if escaped and source[cursor] == 92:
            cursor += 2
            continue
        if source[cursor] == source[quote]:
            return cursor + 1
        cursor += 1
    return len(source)


def _looks_like_char(source: bytes, start: int) -> bool:
    if start + 2 >= len(source):
        return False
    if source[start + 1] == 92:
        return source.find(b"'", start + 2, min(len(source), start + 12)) >= 0
    return source[start + 2] == 39


def _comment_kind(spelling: bytes, block: bool = False) -> str:
    if block:
        if spelling.startswith(b"/**") and not spelling.startswith(b"/***"):
            return "outer-doc-block"
        if spelling.startswith(b"/*!"):
            return "inner-doc-block"
        return "block"
    if spelling.startswith(b"///") and not spelling.startswith(b"////"):
        return "outer-doc-line"
    if spelling.startswith(b"//!"):
        return "inner-doc-line"
    return "line"


def _lex(source: bytes) -> tuple[bytearray, list[dict[str, Any]], list[str]]:
    mask = bytearray(source)
    comments: list[dict[str, Any]] = []
    errors: list[str] = []
    cursor = 0
    while cursor < len(source):
        if source.startswith(b"//", cursor):
            end = source.find(b"\n", cursor + 2)
            end = len(source) if end < 0 else end
            spelling = source[cursor:end]
            comments.append({"start": cursor, "end": end, "kind": _comment_kind(spelling)})
            _blank(mask, cursor, end)
            cursor = end
            continue
        if source.startswith(b"/*", cursor):
            depth = 1
            end = cursor + 2
            while end < len(source) and depth:
                if source.startswith(b"/*", end):
                    depth += 1
                    end += 2
                elif source.startswith(b"*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
            if depth:
                errors.append(f"unterminated-block-comment@{cursor}")
                end = len(source)
            spelling = source[cursor:end]
            comments.append(
                {"start": cursor, "end": end, "kind": _comment_kind(spelling, block=True)}
            )
            _blank(mask, cursor, end)
            cursor = end
            continue
        raw_end = _raw_string_end(source, cursor)
        if raw_end is not None:
            if raw_end == len(source) and not source.endswith(b'"'):
                errors.append(f"unterminated-raw-string@{cursor}")
            _blank(mask, cursor, raw_end)
            cursor = raw_end
            continue
        quote = cursor
        if source.startswith((b'b"', b'c"'), cursor):
            quote = cursor + 1
        if source[quote : quote + 1] == b'"':
            end = _quoted_end(source, quote)
            if end == len(source) and (not source or source[-1] != 34):
                errors.append(f"unterminated-string@{cursor}")
            _blank(mask, cursor, end)
            cursor = end
            continue
        if source[cursor] == 39 and _looks_like_char(source, cursor):
            end = _quoted_end(source, cursor)
            _blank(mask, cursor, end)
            cursor = end
            continue
        cursor += 1
    return mask, comments, errors


def _line_offsets(source: bytes) -> list[int]:
    return [0, *(match.end() for match in re.finditer(b"\n", source))]


def _position(offset: int, lines: list[int]) -> dict[str, int]:
    import bisect

    index = bisect.bisect_right(lines, offset) - 1
    return {"line": index + 1, "column": offset - lines[index] + 1}


def _span(start: int, end: int, lines: list[int]) -> dict[str, Any]:
    return {
        "start_byte": start,
        "end_byte": end,
        "start": _position(start, lines),
        "end": _position(end, lines),
    }


def _comment_text(spelling: bytes) -> str:
    text = spelling.decode("utf-8")
    if text.startswith("//"):
        return text[2:].lstrip("!/").strip()
    if text.startswith("/*"):
        text = text[2:-2] if text.endswith("*/") else text[2:]
        return " ".join(line.strip(" !*\t") for line in text.splitlines()).strip()
    return text.strip()


def _matching(mask: bytes | bytearray, start: int, opening: int, closing: int) -> int | None:
    depth = 0
    for cursor in range(start, len(mask)):
        if mask[cursor] == opening:
            depth += 1
        elif mask[cursor] == closing:
            depth -= 1
            if depth == 0:
                return cursor
    return None


def _parameters(mask: bytes | bytearray, open_paren: int, close_paren: int) -> list[str]:
    raw = bytes(mask[open_paren + 1 : close_paren]).decode("utf-8", errors="replace")
    results: list[str] = []
    for part in raw.split(","):
        left = part.split(":", 1)[0].strip()
        left = re.sub(r"^(?:&\s*(?:'\w+\s*)?|mut\s+)+", "", left)
        if left and left not in {"self", "&self", "&mut self"}:
            results.append(left)
    return results


def _adjacent_fixed_function(
    source: bytes, mask: bytearray, comment_end: int, lines: list[int]
) -> dict[str, Any] | None:
    match = FN_RE.match(mask, comment_end)
    if match is None:
        return None
    attrs = bytes(mask[match.start("attrs") : match.end("attrs")])
    if re.search(rb"#\s*\[\s*cfg(?:_attr)?\b", attrs):
        return None
    open_paren = bytes(mask).find(b"(", match.end("name"))
    if open_paren < 0:
        return None
    close_paren = _matching(mask, open_paren, 40, 41)
    if close_paren is None:
        return None
    open_brace = bytes(mask).find(b"{", close_paren + 1)
    semicolon = bytes(mask).find(b";", close_paren + 1, open_brace if open_brace >= 0 else None)
    if open_brace < 0 or semicolon >= 0:
        return None
    close_brace = _matching(mask, open_brace, 123, 125)
    if close_brace is None:
        return None
    body = bytes(mask[open_brace + 1 : close_brace]).strip()
    fixed = FIXED_RETURN_RE.fullmatch(body)
    if fixed is None:
        return None
    start = match.start("prefix")
    end = close_brace + 1
    spelling = source[start:end]
    return {
        "function_name": match.group("name").decode("ascii"),
        "parameters": _parameters(mask, open_paren, close_paren),
        "returned_literal": fixed.group("literal").decode("ascii"),
        "span": _span(start, end, lines),
        "spelling_sha256": _hash_bytes(spelling),
    }


def _preceded_by_cfg(mask: bytearray, comment_start: int) -> bool:
    """Conservatively reject a doc comment whose immediately preceding attrs select cfg."""
    prefix = bytes(mask[:comment_start]).splitlines()
    for raw_line in reversed(prefix):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(b"#["):
            if re.match(rb"#\[\s*cfg(?:_attr)?\b", line):
                return True
            continue
        break
    return False


def _findings(
    path: Path, root: Path, comments: list[dict[str, Any]], mask: bytearray
) -> list[dict[str, Any]]:
    source = path.read_bytes()
    lines = _line_offsets(source)
    source_hash = _hash_bytes(source)
    results: list[dict[str, Any]] = []
    for token in comments:
        start, end = token["start"], token["end"]
        spelling = source[start:end]
        comment = _comment_text(spelling)
        comment_span = _span(start, end, lines)
        pattern: str | None = None
        recommendation: str | None = None
        evidence: dict[str, Any] = {
            "comment_kind": token["kind"],
            "comment_span": comment_span,
            "comment_spelling_sha256": _hash_bytes(spelling),
        }
        if PERCENT_CLAIM_RE.search(comment) and not _preceded_by_cfg(mask, start):
            function = _adjacent_fixed_function(source, mask, end, lines)
            if function is not None:
                pattern = "behavior_drift_comment"
                recommendation = "Reconcile the percentage-from-amount claim with the adjacent fixed-literal function."
                evidence.update(
                    claim_kind="parameter-derived-percentage",
                    code_fact="fixed-numeric-literal-return",
                    function=function,
                )
        if pattern is None and STALE_TERM_RE.search(comment):
            pattern = "stale_comment_term"
            recommendation = "Update the comment to current terminology."
        if pattern is None and DOC_REF_RE.search(comment):
            pattern = "malformed_doc_reference"
            recommendation = "Replace line-number references with a durable symbol or path."
        stripped = comment.strip().strip("#*-= ")
        if (
            pattern is None
            and stripped
            and (SECTION_BANNER_RE.fullmatch(stripped) or UPPER_BANNER_RE.fullmatch(stripped))
        ):
            pattern = "detached_section_banner"
            recommendation = "Delete the banner or attach durable rationale to adjacent code."
        if pattern is None:
            continue
        results.append(
            {
                "pattern": pattern,
                "file": _relative(path, root),
                "lineno": comment_span["start"]["line"],
                "summary": comment[:180],
                "recommendation": recommendation,
                "language": "rust",
                "source_sha256": source_hash,
                "source_span": comment_span,
                "evidence": evidence,
            }
        )
    return results


def _manifest(inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    rows = [
        {
            "file": row["file"],
            "source_sha256": row["source_sha256"],
            "source_bytes": row["source_bytes"],
        }
        for row in inventory
        if "source_sha256" in row
    ]
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["file"].encode("utf-8") + b"\0")
        digest.update(row["source_sha256"].encode("ascii") + b"\n")
    return rows, digest.hexdigest()


def _publish(output: Path, analysis: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    jsonl = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    detections_sha256 = _hash_bytes(jsonl.encode("utf-8"))
    analysis["detections_sha256"] = detections_sha256
    payload = {
        "schema_version": 1,
        "status": analysis["status"],
        "outcome": analysis["outcome"],
        "total_findings": len(findings),
        "source_manifest_sha256": analysis["source_manifest_sha256"],
        "detections_sha256": detections_sha256,
        "analysis": {"rust": analysis},
        "findings": findings,
    }
    counts: dict[str, int] = {}
    for row in findings:
        counts[row["pattern"]] = counts.get(row["pattern"], 0) + 1
    markdown = (
        "# Rust comment-drift audit\n\n"
        f"**Status:** `{analysis['status']}`  \n"
        f"**Outcome:** `{analysis['outcome']}`  \n"
        f"**Findings:** {len(findings)}  \n"
        f"**Source manifest:** `{analysis['source_manifest_sha256']}`\n\n"
        "Rust-aware lexical comments plus bounded adjacent syntax; see `findings.json` "
        "for exact spans, hashes, native gates, inventory, and non-claims.\n"
    )
    if counts:
        markdown += (
            "\n" + "\n".join(f"- `{key}`: {value}" for key, value in sorted(counts.items())) + "\n"
        )
    _atomic_text(output, jsonl)
    _json(output.with_name("scan.json"), analysis)
    _json(output.with_name("findings.json"), payload)
    _atomic_text(output.with_name("report.md"), markdown)


def _base_analysis(
    inventory: list[dict[str, Any]], errors: list[str], manifest: list[dict[str, Any]], digest: str
) -> dict[str, Any]:
    return {
        "language": "rust",
        "analyzer": "rust-byte-lexer+cargo+rustfmt",
        "lexical_only": True,
        "limits": [
            "bounded adjacent fixed-literal behavior rule only",
            "no macro_rules or procedural-macro expansion or hygiene claims",
            "no build.rs output, OUT_DIR, include!, or environment claims",
            "cfg-gated adjacent items are skipped without explicit selection evidence",
            "no name, type, trait, generic, unsafe, FFI, or runtime-dispatch resolution",
            "Cargo all-target/all-feature check does not prove unenumerated target triples or profiles",
        ],
        "inventory": [
            {key: value for key, value in row.items() if key != "path"} for row in inventory
        ],
        "errors": errors,
        "source_manifest": manifest,
        "source_manifest_sha256": digest,
        "source_preserved": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Rust comments with native gates.")
    parser.add_argument("targets", nargs="*", default=["."])
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--rustc", type=Path, default=Path("rustc"))
    parser.add_argument("--cargo", type=Path, default=Path("cargo"))
    parser.add_argument("--rustfmt", type=Path, default=Path("rustfmt"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output.resolve()
    if output.suffix.casefold() != ".jsonl":
        parser.error("--output must be a .jsonl artifact path")
    try:
        output.relative_to(root)
    except ValueError:
        parser.error("--output must be inside --project-root")
    artifacts = (
        output,
        output.with_name("scan.json"),
        output.with_name("findings.json"),
        output.with_name("report.md"),
    )
    for artifact in artifacts:
        artifact.unlink(missing_ok=True)

    inventory, target_errors = _discover(args.targets or ["."], root)
    manifest, manifest_digest = _manifest(inventory)
    base = _base_analysis(inventory, list(target_errors), manifest, manifest_digest)

    selected: dict[str, Path | None] = {}
    for name in ("rustc", "cargo", "rustfmt"):
        configured = getattr(args, name)
        selected[name] = (
            configured.resolve() if configured.is_absolute() else _which(str(configured))
        )
    tools = {name: _probe_tool(path, name, root) for name, path in selected.items()}
    base["tools"] = tools
    bad_tools = [tool for tool in tools.values() if tool["state"] != "ready"]
    if bad_tools:
        first = bad_tools[0]
        status = "failed" if first["state"] == "failed" else "partial"
        base.update(
            status=status,
            outcome="failed" if status == "failed" else "incomplete",
            failure_kind=first["failure_kind"],
            summary={
                "discovered": len(inventory),
                "eligible": 0,
                "excluded": 0,
                "failed": len(bad_tools),
            },
        )
        _publish(output, base, [])
        return 1 if status == "failed" else 2

    eligible = [row for row in inventory if row["role"] == "candidate"]
    if not eligible:
        base.update(
            status="partial",
            outcome="incomplete",
            failure_kind="no-eligible-rust-files",
            summary={
                "discovered": len(inventory),
                "eligible": 0,
                "excluded": sum(row["role"] == "excluded" for row in inventory),
                "failed": len(target_errors),
            },
        )
        _publish(output, base, [])
        return 2

    if not (root / "Cargo.toml").is_file():
        base.update(
            status="partial",
            outcome="incomplete",
            failure_kind="cargo-project-missing",
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        _publish(output, base, [])
        return 2

    cargo_command = [
        str(selected["cargo"]),
        "check",
        "--locked",
        "--offline",
        "--workspace",
        "--all-targets",
        "--all-features",
    ]
    with tempfile.TemporaryDirectory(prefix="rust-comment-drift-") as state:
        state_path = Path(state)
        env = os.environ.copy()
        env.update(
            CARGO_NET_OFFLINE="true",
            CARGO_TARGET_DIR=str(state_path / "target"),
            CARGO_HOME=str(state_path / "cargo-home"),
        )
        cargo_check = _run(cargo_command, root, env=env, timeout=120)
    base["cargo_check"] = {
        "command": cargo_command[1:],
        "returncode": cargo_check.returncode,
        "locked": True,
        "offline": True,
        "workspace": True,
        "all_targets": True,
        "all_features": True,
        **(
            {"detail": (cargo_check.stderr or cargo_check.stdout).strip()[-4000:]}
            if cargo_check.returncode
            else {}
        ),
    }
    if cargo_check.returncode:
        base.update(
            status="failed",
            outcome="failed",
            failure_kind="cargo-check-failed",
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        _publish(output, base, [])
        return 1

    findings: list[dict[str, Any]] = []
    syntax_failures = 0
    provider_failures = 0
    for row in eligible:
        path = row["path"]
        syntax = _run(
            [
                str(selected["rustfmt"]),
                "--edition",
                "2024",
                "--emit",
                "stdout",
                "--config",
                "skip_children=true",
                str(path),
            ],
            root,
        )
        if syntax.returncode:
            detail = (syntax.stderr or syntax.stdout).strip()
            reason = "syntax-error" if "error:" in detail.casefold() else "rustfmt-provider-failed"
            row.update(role="failed", reason=reason, detail=detail)
            base["errors"].append(f"{row['file']}:{reason}")
            syntax_failures += reason == "syntax-error"
            provider_failures += reason != "syntax-error"
            continue
        source = path.read_bytes()
        mask, comments, lexer_errors = _lex(source)
        if lexer_errors:
            row.update(role="failed", reason="lexical-error", detail="; ".join(lexer_errors))
            base["errors"].append(f"{row['file']}:lexical-error")
            syntax_failures += 1
            continue
        row.update(role="eligible", comment_count=len(comments), native_syntax="rustfmt-parse")
        findings.extend(_findings(path, root, comments, mask))

    for row in inventory:
        path = row["path"]
        if row.get("source_sha256") and path.is_file() and _hash_file(path) != row["source_sha256"]:
            base["source_preserved"] = False
            base["errors"].append(f"{row['file']}:source-mutated")
    completed = sum(row["role"] == "eligible" for row in inventory)
    failed = sum(row["role"] == "failed" for row in inventory) + len(target_errors)
    excluded = sum(row["role"] == "excluded" for row in inventory)
    if not base["source_preserved"]:
        status, outcome, rc = "failed", "failed", 1
        base["failure_kind"] = "unexpected-source-mutation"
        findings = []
    elif provider_failures and completed == 0:
        status, outcome, rc = "failed", "failed", 1
        base["failure_kind"] = "rustfmt-provider-failed"
        findings = []
    elif failed or syntax_failures:
        status, outcome, rc = "partial", "incomplete", 0
    else:
        status, rc = "complete", 0
        outcome = "advisory-findings" if findings else "clean-within-complete"
    findings.sort(key=lambda row: (row["file"], row["lineno"], row["pattern"]))
    base.update(
        status=status,
        outcome=outcome,
        inventory=[
            {key: value for key, value in row.items() if key != "path"} for row in inventory
        ],
        summary={
            "discovered": len(inventory),
            "eligible": completed,
            "excluded": excluded,
            "failed": failed,
        },
    )
    _publish(output, base, findings)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
