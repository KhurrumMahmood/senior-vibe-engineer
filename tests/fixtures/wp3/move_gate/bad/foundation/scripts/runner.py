"""Run the legacy worker using its pinned prompt."""

from pathlib import Path

ASSET = Path(__file__).resolve().parent / "assets" / "prompt.txt"


def new_worker() -> str:
    return ASSET.read_text(encoding="utf-8").strip()
