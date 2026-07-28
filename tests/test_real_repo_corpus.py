from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts import real_repo_corpus as corpus


def _git(args: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _source_repo(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    _git(["init", "--quiet"], cwd=source)
    _git(["config", "user.name", "Corpus Test"], cwd=source)
    _git(["config", "user.email", "corpus@example.invalid"], cwd=source)
    (source / "license").write_text("MIT\n", encoding="utf-8")
    (source / "main.py").write_text("def useful():\n    return True\n", encoding="utf-8")
    _git(["add", "license", "main.py"], cwd=source)
    _git(["commit", "--quiet", "-m", "fixture"], cwd=source)
    return source, _git(["rev-parse", "HEAD"], cwd=source)


def _entry(source: Path, revision: str) -> corpus.CorpusEntry:
    return corpus.CorpusEntry(
        name="fixture-repo",
        source=str(source),
        revision=revision,
        language="python",
        license="MIT",
        slice=1,
    )


def test_manifest_requires_exact_https_revisions(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repositories": [
                    {
                        "name": "moving",
                        "source": "https://github.com/example/moving.git",
                        "revision": "main",
                        "language": "python",
                        "license": "MIT",
                        "slice": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(corpus.CorpusError, match="40 lowercase hex"):
        corpus.load_manifest(manifest)


@pytest.mark.parametrize(
    "source",
    (
        "http://github.com/example/repository.git",
        "git@github.com:example/repository.git",
        "https://example.com/example/repository.git",
    ),
)
def test_manifest_refuses_non_https_github_sources(
    tmp_path: Path, source: str
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repositories": [
                    {
                        "name": "unsafe-source",
                        "source": source,
                        "revision": "0" * 40,
                        "language": "python",
                        "license": "MIT",
                        "slice": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(corpus.CorpusError, match="HTTPS GitHub"):
        corpus.load_manifest(manifest)


@pytest.mark.parametrize("cache", (Path("/"), corpus.REPO_ROOT, Path.home()))
def test_cache_root_refuses_destructive_scope(cache: Path) -> None:
    with pytest.raises(corpus.CorpusError, match="unsafe cache root"):
        corpus._safe_cache_root(cache)


def test_prepare_is_exact_idempotent_and_read_only(tmp_path: Path) -> None:
    source, revision = _source_repo(tmp_path)
    cache = tmp_path / "cache"
    entry = _entry(source, revision)

    first = corpus.prepare_entry(entry, cache, allow_local_source=True)
    second = corpus.prepare_entry(entry, cache, allow_local_source=True)

    assert first["status"] == "prepared"
    assert second["status"] == "reused"
    assert first["revision"] == revision
    assert first["license_files"] == ["license"]
    assert _git(["status", "--porcelain"], cwd=cache / entry.name) == ""


def test_verify_refuses_revision_mismatch(tmp_path: Path) -> None:
    source, revision = _source_repo(tmp_path)
    cache = tmp_path / "cache"
    entry = _entry(source, revision)
    corpus.prepare_entry(entry, cache, allow_local_source=True)

    wrong = corpus.CorpusEntry(
        **{**entry.to_dict(), "revision": "0" * 40}  # type: ignore[arg-type]
    )
    with pytest.raises(corpus.CorpusError, match="revision mismatch"):
        corpus.verify_entry(wrong, cache)


def test_verify_refuses_dirty_checkout(tmp_path: Path) -> None:
    source, revision = _source_repo(tmp_path)
    cache = tmp_path / "cache"
    entry = _entry(source, revision)
    corpus.prepare_entry(entry, cache, allow_local_source=True)
    (cache / entry.name / "unexpected.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(corpus.CorpusError, match="is dirty"):
        corpus.verify_entry(entry, cache)


def test_public_manifest_is_valid_and_names_are_unique() -> None:
    entries = corpus.load_manifest(corpus.DEFAULT_MANIFEST)
    assert {entry.language for entry in entries} == {
        "python",
        "typescript",
        "go",
        "java",
        "javascript",
        "c",
        "cpp",
        "kotlin",
        "php",
        "ruby",
        "rust",
        "dart",
        "swift",
        "csharp",
    }
    assert {entry.slice for entry in entries} == {1, 2, 3, 4}
    assert {
        slice_id: sum(entry.slice == slice_id for entry in entries)
        for slice_id in (1, 2, 3, 4)
    } == {1: 4, 2: 4, 3: 4, 4: 2}
    assert len(entries) == len({entry.name for entry in entries})
