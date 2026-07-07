"""Fixture for lang_adapter tests — deliberately exercises every code path."""


def load_invoice():
    return 1


async def fetch_shipment():
    return 2


def __ignored_dunder__():
    return 0


class SmallThing:
    """A small class — under the god-class threshold, emits one class symbol."""

    def only_method(self):
        return 1


class BigService:
    """A god-class — >= 3 non-dunder methods, expands per-method."""

    def __init__(self):
        self.x = 0

    def get_samples(self):
        return []

    def save_samples(self):
        return None

    async def parse_html(self):
        return ""
