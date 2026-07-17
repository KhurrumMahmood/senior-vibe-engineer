"""Renderer tests (spec IM-7, plan §2 criterion 4).

The static tests run everywhere; the browser smoke activates when
playwright is installed (the CI renderer step) and skips locally.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render_mod = _load("render_status_mod", "scripts/render_status.py")
status_mod = _load("status_mod_r", "scripts/status.py")


@pytest.fixture
def fixture_doc(tmp_path):
    """A status doc with a mix of available and absent sections."""
    (tmp_path / "ai-docs" / "plans").mkdir(parents=True)
    (tmp_path / "ai-docs" / "plans" / "x.md").write_text(
        "---\nname: x\nstatus: scoped\n---\n\n# x\n"
    )
    qdir = tmp_path / ".engineering" / "local" / "queue"
    qdir.mkdir(parents=True)
    (qdir / "item-1.json").write_text(json.dumps(
        {"status": "staged", "staged_at": "2026-06-12T00:00:00+00:00",
         "recipe": "r", "scope": ["a.py"]}))
    d = tmp_path / "reports" / "unify-shadows" / "SC-9"
    d.mkdir(parents=True)
    (d / "proposal.md").write_text("p")
    return status_mod.build_status(tmp_path)


def test_html_is_self_contained(fixture_doc):
    html = render_mod.render(fixture_doc)
    # zero network: no external URLs, scripts, stylesheets, imports
    assert "http://" not in html and "https://" not in html
    assert not re.search(r"<(script|img|link)[^>]*\b(src|href)=", html)
    assert "@import" not in html and "fetch(" not in html
    # the data is inlined and every section name renders from it
    assert 'id="status-data"' in html
    for name in ("lifecycle", "pending_approvals", "queue", "goals"):
        assert name in html


def test_inline_json_script_escape(fixture_doc):
    fixture_doc["sections"]["goals"]["reason"] = "contains </script> attack"
    html = render_mod.render(fixture_doc)
    payload = html.split('id="status-data">', 1)[1].split("</script>", 1)[0]
    assert "</script>" not in payload  # escaped to <\/script>
    assert json.loads(payload)["sections"]["goals"]["reason"] == "contains </script> attack"


def test_cli_roundtrip(tmp_path, fixture_doc):
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(fixture_doc))
    rc = render_mod.main(["--status", str(status_path)])
    assert rc == 0
    assert (tmp_path / "status.html").is_file()


# spec:status-projection-and-presentation::IM-10
def test_browser_smoke_zero_console_errors_zero_network(tmp_path, fixture_doc):
    """Plan §2 criterion 4 — file://, headless Chromium, every section rendered."""
    sync_api = pytest.importorskip("playwright.sync_api")
    out = tmp_path / "status.html"
    out.write_text(render_mod.render(fixture_doc), encoding="utf-8")

    errors: list[str] = []
    requests: list[str] = []
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url))
        page.goto(out.as_uri())
        page.wait_for_load_state("networkidle")
        cards = page.locator("status-card").count()
        browser.close()

    assert errors == []
    assert [u for u in requests if not u.startswith("file://")] == []
    assert cards == len(fixture_doc["sections"])
