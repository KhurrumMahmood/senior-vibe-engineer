from __future__ import annotations

import tempfile
from pathlib import Path

import move_path


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docs").mkdir()
        (root / "specs").mkdir()
        (root / "docs" / "index.md").write_text("[Old](old.md)\n", encoding="utf-8")
        (root / "docs" / "old.md").write_text("# Old\n", encoding="utf-8")
        plan = root / "moves.yml"
        plan.write_text(
            """
moves:
  - from: docs/old.md
    to: specs/new.md
reference_scope:
  include: ["**/*.md"]
rewrite:
  markdown_links: update
""".lstrip(),
            encoding="utf-8",
        )
        report = move_path.run_plan(
            plan_path=plan,
            project_root=root,
            mode="dry-run",
            report_dir=root / ".engineering" / "local" / "move-path",
        )
        assert report["summary"]["auto_rewrites"] == 1
        assert not report["blocked"]
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
