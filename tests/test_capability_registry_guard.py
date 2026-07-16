from __future__ import annotations

from check_capability_registry_consumers import CONSUMERS, check_consumers


def test_all_load_bearing_consumers_import_one_registry():
    assert len(CONSUMERS) == 7
    assert check_consumers() == []
