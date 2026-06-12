#!/usr/bin/env python3
"""Lens renderer v0 — status.json → one self-contained dashboard HTML.

Deterministic formatter, zero agents, zero network: the status.json
document is inlined into the page, design-token CSS is inlined, and the
rendering is vanilla web components reading the inlined data. The
renderer never recomputes state (smell 5 — `status.py` is the one
producer); it only formats fields that are present. Actions render as
copy-paste commands (click selects the text), not live controls.

Source decision: `core:status-projection-schema` (ADR 0037).
"""
# spec:status-projection-and-presentation::IM-7
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Project status</title>
<style>
:root {
  --bg: #0f1216; --card: #171c23; --card-edge: #232b36;
  --ink: #e6edf3; --muted: #8b98a9; --accent: #4ea1ff;
  --ok: #3fb950; --warn: #d29922; --bad: #f85149;
  --radius: 10px;
  --font: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
       font: 15px/1.5 var(--font); padding: 24px; }
header h1 { margin: 0 0 4px; font-size: 22px; }
header .meta { color: var(--muted); font-size: 13px; margin: 0 0 20px; }
main { display: grid; gap: 16px;
       grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); }
status-card { display: block; background: var(--card);
              border: 1px solid var(--card-edge); border-radius: var(--radius);
              padding: 16px; }
status-card.absent { opacity: .55; }
status-card h2 { margin: 0 0 10px; font-size: 15px; display: flex;
                 align-items: center; gap: 8px; }
.badge { font-size: 12px; padding: 1px 8px; border-radius: 999px;
         border: 1px solid var(--card-edge); color: var(--muted); }
.badge.ok { color: var(--ok); border-color: var(--ok); }
.badge.warn { color: var(--warn); border-color: var(--warn); }
.badge.bad { color: var(--bad); border-color: var(--bad); }
.reason { color: var(--muted); font-style: italic; font-size: 13px; }
ul.kv { list-style: none; margin: 0; padding: 0; font-size: 13px; }
ul.kv li { display: flex; justify-content: space-between; gap: 12px;
           padding: 3px 0; border-bottom: 1px dotted var(--card-edge); }
ul.kv li:last-child { border-bottom: none; }
ul.kv .k { color: var(--muted); }
ul.kv .v { font-family: var(--mono); text-align: right; word-break: break-all; }
.rows { font-size: 13px; margin-top: 8px; }
.rows .row { padding: 4px 0; border-top: 1px solid var(--card-edge); }
.rows .row .sub { color: var(--muted); font-size: 12px; }
code.action { display: block; margin-top: 10px; padding: 8px 10px;
              background: #0b0e12; border: 1px solid var(--card-edge);
              border-radius: 6px; font: 12px var(--mono); color: var(--accent);
              cursor: pointer; user-select: all; }
code.action::before { content: "copy-paste ▸ "; color: var(--muted);
                      user-select: none; }
</style>
</head>
<body>
<header>
  <h1>Project status</h1>
  <p class="meta" id="meta"></p>
</header>
<main id="sections"></main>
<script type="application/json" id="status-data">__STATUS_JSON__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("status-data").textContent);
const SECTION_ORDER = ["lifecycle", "structural_health", "pending_approvals",
                       "in_flight", "staleness", "queue", "goals"];

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function kvList(pairs) {
  const ul = el("ul", "kv");
  for (const [k, v] of pairs) {
    if (v === undefined || v === null) continue;
    const li = el("li");
    li.appendChild(el("span", "k", k));
    li.appendChild(el("span", "v", v));
    ul.appendChild(li);
  }
  return ul;
}

function action(cmd) {
  const code = el("code", "action", cmd);
  code.title = "Click to select, then copy";
  code.addEventListener("click", () => {
    const range = document.createRange();
    range.selectNodeContents(code);
    const sel = window.getSelection();
    if (sel) { sel.removeAllRanges(); sel.addRange(range); }
  });
  return code;
}

const RENDERERS = {
  lifecycle(sec, body) {
    const state = sec.project_state || {};
    body.appendChild(kvList([
      ["maturity", state.maturity || "undeclared (assumed MAX)"],
      ["stakes", state.stakes || "undeclared (assumed MAX)"],
      ["engineering manifest", "v" + sec.engineering_manifest_version +
        (sec.engineering_manifest_ok ? " (ok)" : " (version mismatch)")],
      ["adapter", sec.adapter_present ? "present" : "absent"],
      ["profile", sec.profile_present ? "present" : "absent"],
      ["open questions", sec.open_questions_present ? "present" : "none"],
    ]));
  },
  structural_health(sec, body) {
    const counts = Object.entries(sec.counts || {})
      .map(([k, v]) => k + ": " + v).join("  ");
    body.appendChild(kvList([
      ["total findings", sec.total],
      ["by detector", counts || "none"],
      ["detector errors", (sec.detector_errors || []).join(", ") || "none"],
      ["manifest", sec.manifest_path],
      ["manifest mtime", sec.manifest_mtime],
    ]));
  },
  pending_approvals(sec, body, card) {
    badge(card, sec.pending_count > 0 ? "warn" : "ok",
          sec.pending_count + " pending");
    const rows = el("div", "rows");
    for (const item of sec.items || []) {
      const row = el("div", "row");
      row.appendChild(el("div", null,
        item.chain + " / " + item.id + " — " + item.status));
      row.appendChild(el("div", "sub",
        item.age_days + "d old" +
        (item.closure_detectable ? "" : " · closure not detectable; dismiss when handled")));
      rows.appendChild(row);
    }
    body.appendChild(rows);
    const pending = (sec.items || []).find(i => i.status === "pending");
    if (pending) {
      body.appendChild(action("touch " + pending.path + "/DISMISSED"));
    }
  },
  in_flight(sec, body) {
    const ideas = sec.ideas && sec.ideas.available ? sec.ideas : null;
    body.appendChild(kvList([
      ["active plans", (sec.active_plans || []).join(", ") || "none"],
      ["specs", (sec.specs || []).map(s => s.id + " (" + s.status + ")").join(", ") || "none"],
      ["ideas", ideas ? ideas.total + " total" : "no ledger"],
      ["ideas by state", ideas
        ? Object.entries(ideas.by_state).map(([k, v]) => k + ": " + v).join("  ")
        : null],
      ["in-flight ideas", ideas ? (ideas.in_flight.join(", ") || "none") : null],
    ]));
  },
  staleness(sec, body, card) {
    badge(card, sec.stale_count > 0 ? "warn" : "ok", sec.stale_count + " stale");
    const rows = el("div", "rows");
    for (const artifact of sec.artifacts || []) {
      const row = el("div", "row");
      row.appendChild(el("div", null, artifact.artifact + " — " + artifact.state));
      row.appendChild(el("div", "sub", "scope written " + artifact.scope_written_at));
      rows.appendChild(row);
    }
    body.appendChild(rows);
    if (!(sec.artifacts || []).length) {
      body.appendChild(el("p", "reason", "no scope-tracked artifacts"));
    }
  },
  queue(sec, body, card) {
    badge(card, sec.count > 0 ? "warn" : "ok", sec.count + " item(s)");
    const rows = el("div", "rows");
    for (const item of sec.items || []) {
      const row = el("div", "row");
      row.appendChild(el("div", null, item.id + " — " + item.status));
      row.appendChild(el("div", "sub", "staged " + (item.staged_at || "?")));
      rows.appendChild(row);
    }
    body.appendChild(rows);
    if (sec.count > 0) {
      body.appendChild(action("python3 scripts/queue_status.py list"));
    }
  },
};

function badge(card, kind, text) {
  card.querySelector("h2").appendChild(el("span", "badge " + kind, text));
}

class StatusCard extends HTMLElement {
  render(name, sec) {
    const title = el("h2", null, name.replace(/_/g, " "));
    this.appendChild(title);
    if (!sec || !sec.available) {
      this.classList.add("absent");
      title.appendChild(el("span", "badge", "absent"));
      this.appendChild(el("p", "reason", (sec && sec.reason) || "no data"));
      return;
    }
    const body = el("div");
    this.appendChild(body);
    const renderer = RENDERERS[name];
    if (renderer) {
      renderer(sec, body, this);
    } else {
      body.appendChild(el("pre", null, JSON.stringify(sec, null, 1)));
    }
  }
}
customElements.define("status-card", StatusCard);

document.getElementById("meta").textContent =
  DATA.root + " · generated " + DATA.generated_at +
  " · schema v" + DATA.schema_version;

const main = document.getElementById("sections");
const names = SECTION_ORDER
  .concat(Object.keys(DATA.sections).filter(n => !SECTION_ORDER.includes(n)).sort());
for (const name of names) {
  if (!(name in DATA.sections)) continue;
  const card = new StatusCard();
  main.appendChild(card);
  card.render(name, DATA.sections[name]);
}
</script>
</body>
</html>
"""


def render(status_doc: dict) -> str:
    # `</` would terminate the inline JSON script block early; escape it.
    payload = json.dumps(status_doc, sort_keys=True).replace("</", "<\\/")
    return TEMPLATE.replace("__STATUS_JSON__", payload)


def main(argv: list[str] | None = None) -> int:
    toolkit_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=toolkit_root)
    parser.add_argument("--status", type=Path, default=None,
                        help="status.json path (default: <root>/.engineering/local/status.json)")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output HTML (default: alongside the status.json)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    status_path = args.status or root / ".engineering" / "local" / "status.json"
    if not status_path.is_file():
        print(f"error: {status_path} not found — run scripts/status.py first", file=sys.stderr)
        return 2
    try:
        doc = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: cannot read {status_path}: {exc}", file=sys.stderr)
        return 2

    out = args.out or status_path.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(doc), encoding="utf-8")
    print(f"dashboard written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
