from __future__ import annotations

from check_capability_registry_consumers import CONSUMERS, REPO_ROOT, check_consumers


def _copy_guard_surface(root):
    for relative in CONSUMERS:
        source = REPO_ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return root


def test_all_load_bearing_consumers_import_one_registry():
    assert len(CONSUMERS) == 7
    assert check_consumers() == []


def test_guard_rejects_arbitrarily_named_dictionary_registry(tmp_path):
    _copy_guard_surface(tmp_path)
    target = tmp_path / CONSUMERS[0]
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\nSTACK_CATALOG = {'python': {}, 'typescript': {}, 'rust': {}, 'go': {}}\n",
        encoding="utf-8",
    )

    errors = check_consumers(tmp_path)

    assert any("stack identifier dictionary" in error for error in errors)


def test_guard_rejects_nested_and_constructor_dictionary_registries(tmp_path):
    _copy_guard_surface(tmp_path)
    consumer = tmp_path / "scripts" / "manifest.py"
    consumer.write_text(
        consumer.read_text(encoding="utf-8")
        + "\nSTACK_CATALOG = {'group': {'python': {}}, **{'typescript': {}}}\n"
        + "ANOTHER_CATALOG = dict(rust={}, go={})\n",
        encoding="utf-8",
    )

    errors = check_consumers(tmp_path)

    dictionary_errors = [
        error for error in errors if "stack identifier dictionary" in error
    ]
    assert any("python" in error and "typescript" in error for error in dictionary_errors)
    assert any("rust" in error and "go" in error for error in dictionary_errors)


def test_guard_rejects_split_and_zip_computed_registries(tmp_path):
    _copy_guard_surface(tmp_path)
    consumer = tmp_path / "scripts" / "manifest.py"
    consumer.write_text(
        consumer.read_text(encoding="utf-8")
        + '\nMY_CATALOG = "python typescript rust go".split()\n'
        + '\nOTHER_CATALOG = dict(zip("python typescript".split(), ({}, {})))\n',
        encoding="utf-8",
    )

    errors = check_consumers(tmp_path)

    computed = [error for error in errors if "computed stack identifier" in error]
    assert any("python" in error and "go" in error for error in computed)
    assert any("python" in error and "typescript" in error for error in computed)
