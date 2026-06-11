"""Characterization tests for scripts/_lib/yaml_frontmatter.py.

The highest-ROI target in the suite: pure functions shared by decisions /
plans / specs / skill_meta. Pins frontmatter presence detection, the
malformed-YAML and non-mapping guards, BOM / CRLF normalization, and the
PyYAML 1.1 octal gotcha the parser deliberately does not paper over.
"""
from __future__ import annotations

import dataclasses

import pytest

from _lib.yaml_frontmatter import FrontmatterDoc, FrontmatterError, parse, read


def test_parse_basic_frontmatter():
    doc = parse("---\ntitle: Hello\nn: 3\n---\nbody text\n")
    assert isinstance(doc, FrontmatterDoc)
    assert doc.has_frontmatter is True
    assert doc.metadata == {"title": "Hello", "n": 3}
    assert doc.body == "body text\n"
    assert doc.raw_frontmatter is not None


def test_parse_no_frontmatter():
    doc = parse("a plain document with no frontmatter\n")
    assert doc.has_frontmatter is False
    assert doc.metadata == {}
    assert doc.body == "a plain document with no frontmatter\n"
    assert doc.raw_frontmatter is None


def test_parse_empty_frontmatter_block():
    doc = parse("---\n---\nbody\n")
    assert doc.has_frontmatter is True
    assert doc.metadata == {}
    assert doc.body == "body\n"


def test_parse_invalid_yaml_raises():
    with pytest.raises(FrontmatterError) as exc:
        parse("---\nkey: [unclosed\n---\n", path="bad.md")
    assert exc.value.path == "bad.md"
    assert "bad.md" in str(exc.value)


def test_parse_non_mapping_top_level_raises():
    with pytest.raises(FrontmatterError):
        parse("---\n- a\n- b\n---\n")


def test_parse_strips_utf8_bom():
    doc = parse("﻿---\ntitle: X\n---\nbody\n")
    assert doc.has_frontmatter is True
    assert doc.metadata == {"title": "X"}


def test_parse_normalizes_crlf():
    doc = parse("---\r\ntitle: X\r\n---\r\nbody\r\n")
    assert doc.has_frontmatter is True
    assert doc.metadata == {"title": "X"}
    assert "\r" not in doc.body


def test_parse_unquoted_leading_zero_is_octal():
    # PyYAML SafeLoader is YAML 1.1: `id: 0010` parses as octal int 8.
    # decisions.py / plans.py warn + renormalize; the parser does not.
    doc = parse("---\nid: 0010\n---\n")
    assert doc.metadata["id"] == 8


def test_parse_quoted_id_stays_string():
    doc = parse('---\nid: "0010"\n---\n')
    assert doc.metadata["id"] == "0010"


def test_read_from_file(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("---\nk: v\n---\nbody\n", encoding="utf-8")
    doc = read(p)
    assert doc.metadata == {"k": "v"}
    assert doc.body == "body\n"


def test_frontmatter_doc_is_frozen():
    doc = parse("---\nk: v\n---\n")
    with pytest.raises(dataclasses.FrozenInstanceError):
        doc.metadata = {}
