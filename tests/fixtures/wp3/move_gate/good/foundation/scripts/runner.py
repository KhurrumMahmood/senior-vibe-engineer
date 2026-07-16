"""Run the new worker using its pinned portable prompt."""

from pathlib import Path

ASSET = Path(__file__).resolve().parents[1] / "assets" / "prompt.txt"


def new_worker() -> str:
    return ASSET.read_text(encoding="utf-8").strip()
