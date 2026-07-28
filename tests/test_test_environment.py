"""Tests for repository-wide test-runner hygiene."""

from __future__ import annotations

import os
import sys


def test_pytest_disables_source_tree_bytecode_writes():
    assert os.environ["PYTHONDONTWRITEBYTECODE"] == "1"
    assert sys.dont_write_bytecode is True
