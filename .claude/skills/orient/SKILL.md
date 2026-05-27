---
name: orient
description: Establish (or re-confirm) a project's lifecycle state on two independent axes — maturity (prototype → first-users → production) and stakes/exposure (internal → external → public-adversarial) — by asking orientation questions, showing the resulting classification and which standard rungs it activates, then writing the declared state to `.engineering/project-state.json` (the cross-agent state home, ADR 0021). This is the human-in-the-loop "pull" mechanism of ADR 0020 — automatic inference proposes a transition, /orient lets the human dispose. Stakes/exposure are NOT reliably inferable from code, which is why the questions matter. Idempotent — re-running re-confirms and overwrites.
argument-hint: "[--project-root <path>] [--show] [--dry-run]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Declaring or re-confirming where a project sits on the maturity ×
  stakes grid so standard-activation skills (find-standard-gaps and the
  review lanes) enforce the right rungs — not too few, not gold-plated.
  The trigger: starting work in a project with no .engineering/project-state.json,
  or being prompted by inference that the project "looks past its
  declared state" (a new unauthenticated write endpoint, first real-user
  data, a public deploy). Stakes/exposure can only be set by a human, so
  this is the surface that does it.
not_for: |
  Capturing project purpose, critical workflows, intentional tradeoffs,
  or known-bad legacy patterns (use /project-interview — the broad
  human-intent profile). Discovering objective repo facts like stack,
  CI, source roots (use /adapt-project). Authoring an architectural
  decision (use /decide). Running the coverage scan that consumes this
  state (use /find-standard-gaps). Editing the activation thresholds on
  individual standards — those live in the standards file, not here.
escalate_to: |
  /project-interview when the orientation conversation surfaces broader
  intent, risk posture, or do-not-break surfaces worth a durable
  profile. /decide when re-classifying reveals a durable architectural
  choice (e.g. "we are committing to public exposure").
language: any
framework: any
lanes: [project-adaptation]
stage: frame
entrypoint: true
produces: [project_state]
---

# /orient

You are the **orienteer**. Your one job is to establish a project's
lifecycle state on two independent axes and write it to a fixed-schema
state file the standard-activation ecosystem reads. You are the **pull**
half of ADR 0020 (lifecycle- and stakes-gated standard activation):
automatic inference may *propose* that a project has crossed a
threshold, but only a human, through these orientation questions, can
*dispose* — confirm the new classification and commit it.

The work is the conversation plus the write. There is no scout fan-out
and no timestamped report. The deliverable is one file:
`<project-root>/.engineering/project-state.json`.

## Core beliefs

1. **Activation, not knowledge.** General training already covers
   production standards. What suppresses them is the operating mode —
   "hit the goal somehow." This skill exists to *activate* the right bar
   at the right moment, not to teach standards. The state file is the
   switch.
2. **Stakes are not inferable from code; ask.** Maturity leaves
   footprints (a deploy config, real user tables, uptime alerting).
   Stakes/exposure — blast radius, regulated data, uptime commitments,
   adversarial exposure — are a human judgment. The orientation
   questions are the only reliable source. Never silently guess stakes.
3. **Two axes, independent.** Maturity (how real is the reliance) and
   stakes (how much a failure costs / how exposed it is) are
   orthogonal. A quasi-live internal tool is high-maturity, low-stakes;
   an early public payments prototype is low-maturity, high-stakes.
   Collapsing them to one ladder mis-ranks both.
4. **Guard both failure modes.** Under-defending (a prototype-grade
   control shipped into a relied-upon, exposed context) and
   over-defending (gold-plating a low-stakes internal tool like a public
   adversarial service) are both failures. The declared state raises the
   bar on the way up *and caps it* on the way down.
5. **Idempotent and overwritable.** Re-running /orient re-confirms.
   State drifts — projects mature, exposure changes — so the file is
   meant to be rewritten, not appended to. Show the prior state (if any)
   before asking, so the conversation is "is this still true?" not "from
   scratch."

## The axes

### Maturity — ordinal ladder

| Value | Ordinal | Meaning |
|---|---|---|
| `prototype` | 0 | No real users / no real data yet. Spike, experiment, or pre-launch build. Nobody is relying on it. |
| `first-users` | 1 | Real users or real data have arrived, but reliance is light / early. Deployed, but not yet load-bearing for anyone's day. |
| `production` | 2 | Relied upon. Real users / real data in steady use; an outage or bad write is felt. |

### Stakes / exposure — ordinal ladder

| Value | Ordinal | Meaning |
|---|---|---|
| `internal` | 0 | Internal, trusted operators only. Small blast radius. No PII / payments / regulated data of consequence. Modest or no uptime commitment. |
| `external` | 1 | Externally exposed to non-trusted callers, OR handles PII / payments / regulated data, OR carries a real uptime commitment. A bad write or outage reaches people outside the team. |
| `public-adversarial` | 2 | Public and adversarially exposed (untrusted callers can reach side-effectful surfaces), high-uptime, and/or regulated. Must assume hostile input and sustained pressure. |

The two ladders are **independent**. A standard "rung" activates only
when **both** declared axes meet its `{min_maturity, min_stakes}`
thresholds — so a heavy adversarial rung does not fire on a quasi-live
internal tool, and a data-safety rung does fire as soon as maturity
crosses its bar regardless of stakes.

## Orientation questions

Ask these in the conversation. Adapt wording to what you already know
about the project; skip a question only if the answer is unambiguous
from a prior answer. **Do not infer stakes silently** — even if the repo
looks internal, confirm it.

**Maturity:**

1. Is this serving real users or real data yet, or is it still a
   prototype / spike?
2. Is anyone relying on it for their work today? What breaks for them if
   it goes down or writes garbage?
3. Is it deployed somewhere persistent, or does it only run locally / in
   CI?

**Stakes / exposure:**

4. Who can reach it — internal trusted operators only, or external /
   untrusted callers?
5. What is the blast radius of a bad write or an outage? Who feels it,
   and how badly?
6. Does it handle PII, payments, credentials, or regulated data?
7. Is there an uptime commitment (an SLA, an on-call, a "this must not
   go down")?
8. Is it adversarially exposed — public endpoints reachable by untrusted
   callers, especially side-effectful ones?

## Answer → classification mapping

Map the answers to exactly one `maturity` value and one `stakes` value.

**Maturity** (take the highest rung any answer supports):

- Any "real users / real data in steady, relied-upon use" (Q1–Q2) →
  `production`.
- Real users or real data exist but reliance is early / light, or it is
  deployed-but-not-yet-load-bearing (Q1–Q3) → `first-users`.
- No real users, no real data, local/CI only → `prototype`.

**Stakes** (take the highest rung any answer triggers — stakes is a
max over independent risk sources):

- Any of: untrusted/public callers can reach side-effectful surfaces
  (Q8), regulated data under a compliance regime, or a hard high-uptime
  commitment with adversarial pressure → `public-adversarial`.
- Any of: external/non-trusted exposure (Q4), PII / payments /
  credentials / regulated data handled (Q6), or a real uptime
  commitment (Q7) — but not the adversarial ceiling above → `external`.
- Internal trusted operators only, small blast radius, no
  consequential PII/payments/regulated data, modest uptime needs →
  `internal`.

When two answers point at different rungs, **take the higher** — stakes
and maturity are both "highest applicable rung," because a single
high-stakes surface (one payments endpoint) raises the project's bar.
If a single surface is the *only* high-stakes part of an otherwise
low-stakes project, note it in `notes` and consider whether a per-area
exception (ADR 0020 defers these as an override) is warranted — but the
project-level declared value still takes the higher rung.

## Pipeline

### Stage 0 — Resolve project root and read prior state

```bash
PROJECT_ROOT="${ARG_PROJECT_ROOT:-$(pwd)}"
ENGINEERING_DIR="${PROJECT_ROOT}/.engineering"
STATE_FILE="${ENGINEERING_DIR}/project-state.json"
# Transitional read fallback (ADR 0021): prefer the .engineering/ home, but
# read a legacy root-level .project-state.json if the host has not migrated.
LEGACY_STATE_FILE="${PROJECT_ROOT}/.project-state.json"
[ ! -f "$STATE_FILE" ] && [ -f "$LEGACY_STATE_FILE" ] && STATE_FILE="$LEGACY_STATE_FILE"
```

If a project-state file already exists, **read it and show the user
the current classification first.** Re-orientation is a confirmation
conversation, not a blank slate. If `--show` was passed, print the
current state (or "no state declared yet") and stop — no questions, no
write.

### Stage 1 — Ask the orientation questions

Walk the maturity and stakes questions above. Keep it tight — this is a
short conversation, not the full `/project-interview`. If the user is
non-interactive (batch/agent context) and you cannot get answers, **do
not write a guessed file** — report that orientation needs a human and
stop. (Maturity may be partly inferable; stakes is not.)

### Stage 2 — Show the classification and what it implies, THEN confirm

Before writing, show the user:

```
Proposed project state:
  maturity: <value>   (prototype | first-users | production)
  stakes:   <value>   (internal | external | public-adversarial)

What this activates:
  - Baseline ("Sanity"): always on — DRY/SOLID/consistency, input
    hygiene, no hardcoded secrets, no unauthenticated side-effectful
    endpoints, parse-and-validate before fetching a URL.
  - Maturity-gated rungs that now fire: <e.g. reversible migrations,
    backups — if maturity ≥ first-users/production>
  - Stakes-gated rungs that now fire: <e.g. rate-limiting/DDoS, threat
    modeling, second-model input screening — only if stakes is high>
  - Capped (NOT required at this state): <name the heavy rungs the
    declared state deliberately leaves off, so over-defending is
    visibly out of scope>
```

The "capped" line matters as much as the "activates" line — naming what
is deliberately *out* of scope is how /orient prevents gold-plating.
Confirm with the user that the classification is right before writing.
If they correct an axis, re-map and re-show.

### Stage 3 — Write the state file

On confirmation, write `<project-root>/.engineering/project-state.json`
(run `mkdir -p "${ENGINEERING_DIR}"` first) with **exactly** this schema
(the sibling scanner relies on it — do not add, rename, or reorder
semantic keys). If a legacy `<project-root>/.project-state.json` exists,
remove it after writing the canonical file — the loaders prefer
`.engineering/`, but a stale duplicate invites drift:

```json
{
  "maturity": "prototype | first-users | production",
  "stakes": "internal | external | public-adversarial",
  "declared_by": "orient",
  "declared_at": "<ISO8601 timestamp, e.g. 2026-05-21T19:30:00Z>",
  "notes": "<optional 1-2 lines on why this classification>"
}
```

- `maturity` ∈ `{prototype, first-users, production}` — exactly one.
- `stakes` ∈ `{internal, external, public-adversarial}` — exactly one.
- `declared_by` is always the literal string `"orient"`.
- `declared_at` is an ISO 8601 timestamp (UTC, `Z` suffix is fine).
- `notes` is optional freeform; use it for the one fact that drove the
  call (e.g. "internal ops tool, trusted operators, modest uptime" or
  "one payments endpoint forces external despite mostly-internal use").

Write it deterministically (stdlib `json`, sorted-or-fixed key order,
trailing newline). If `--dry-run` was passed, print the JSON you *would*
write and stop — do not touch disk. Re-running overwrites the existing
file (idempotent re-confirm); the new `declared_at` records the
re-confirmation time.

Then confirm to the user in ≤3 lines: the path written, the
`(maturity, stakes)` pair, and a one-line "re-run /orient when the
project crosses a threshold."

> **Convention divergence (intentional):** unlike the `find-*` /
> `map-*` skills, /orient does **not** write a timestamped
> `reports/<skill>/scan-<TS>/` artifact. Its output is the durable,
> single-instance `.engineering/project-state.json` — a declared
> state surface analogous to `environment=dev/production` in `.env`,
> not an audit report. There is one current state, and re-running
> overwrites it.

## Push inference — proposing re-orientation (the other half of ADR 0020)

`/orient` is **pull**: a human runs it on demand. The **push** half is
inference — read-only heuristics that watch for signals the project
looks *more* mature or *more* exposed than its declared state, and
*ask* the user to re-run `/orient`. **Inference only proposes; it never
rewrites the state file.** The agent cannot read stakes from code, so a
flagged signal is a prompt for a human decision, not an auto-transition.

A thin, read-only helper ships with this skill:

```bash
python3 .claude/skills/orient/scripts/infer_state_signals.py \
  --project-root "${PROJECT_ROOT}"
```

It greps for a small set of high-signal transition markers and prints
candidate-transition flags (with the declared state, if any, for
contrast). It **writes nothing**. The signal taxonomy and how to read
the output live in `knowledge/inference-heuristics.md`.

**Point `--project-root` at the source root, not a data-lake monorepo.**
The helper auto-skips vendored/build/cache/worktree dirs and files over
512 KB, and has a `--max-files` backstop — but a repo with tens of
thousands of cached-page or data-dump fixtures (a crawler, an ML data
lake) will still produce a noisy, high-count scan dominated by fixtures.
On such a repo, pass the application source directory (e.g.
`--project-root path/to/app`) so the signals reflect hand-written code,
not captured data. A budget-truncated run is reported as PARTIAL, never
a clean bill of health. The signals it
looks for:

| Signal | Suggests | Axis |
|---|---|---|
| New unauthenticated, side-effectful endpoint (POST/PUT/DELETE/mutation handler with no auth decorator/guard) | Exposure crossing into untrusted territory | stakes ↑ |
| Public deploy / ingress config appears (Dockerfile EXPOSE on a public port, k8s Ingress, `vercel.json`, `netlify.toml`, nginx server block, a `*.tf` with a public LB) | First real public exposure | stakes ↑ (and often maturity ↑) |
| Payment / PII / credential handling introduced (stripe/braintree SDK, `card_number`, `ssn`, `passport`, secret-vault clients) | Regulated / high-blast-radius data | stakes ↑ |
| Auth / login system added (a new `login`, `session`, `oauth`, `jwt` surface where there was none) | Real users arriving / exposure | maturity ↑ and/or stakes ↑ |
| First real-user-data markers (a `users`/`accounts`/`customers` model or migration, a production DB config) | First real users / data | maturity ↑ |

When the helper flags a signal whose suggested rung is **above** the
declared state, surface it to the user as:

> "This looks past your declared state — `<signal>` suggests
> `<axis> ≥ <rung>`, but `.engineering/project-state.json` says `<axis>=<current>`.
> Re-run `/orient` to re-confirm?"

If there is no declared state at all, the prompt is simply "no project
state declared yet — run `/orient` to set it." Either way, the next
action is a human running `/orient` — never an automatic write.

## Non-goals

- Editing production code — this skill reads code only (for the optional
  inference pass) and writes one state file.
- Inferring stakes without asking — stakes/exposure is a human call;
  the questions are mandatory for it.
- Capturing project purpose / critical workflows / tradeoffs — that's
  `/project-interview`. /orient is the narrow two-axis state, not the
  full profile.
- Authoring the activation thresholds on standards — those live in the
  standards file consumed by `/find-standard-gaps`.
- Auto-advancing the declared state from inference — inference proposes;
  the human disposes via a fresh `/orient` run.
- Writing a timestamped report — the durable single-instance
  `.engineering/project-state.json` is the artifact.

## When things go sideways

| Symptom | Action |
|---|---|
| Non-interactive run, can't get answers | Do not write a guessed file. Report "orientation needs a human (stakes is not inferable)" and stop. |
| User unsure about an axis | Ask the discriminating question for that ladder (Q8 for the stakes ceiling; Q1–Q2 for production). Default *down* a rung when genuinely ambiguous and note it — but flag that under-defending is the worse failure if the project is actually exposed. |
| One high-stakes surface in an otherwise low-stakes app | Take the higher project-level rung, record the surface in `notes`, and mention ADR 0020 defers per-area exceptions as a future override. |
| `.engineering/project-state.json` exists but is malformed / hand-edited | Show what you can parse, treat unparseable fields as "undeclared," and re-orient from the questions. |
| Inference flags a signal but the user says it's intentional / out of scope | Not a tool failure — leave the state file unchanged. Inference proposes; the human disposed by declining. |
| Asked to set state for a different repo | Honor `--project-root`; write `.engineering/project-state.json` at THAT root, never the engineering-skills repo's own. |

## Repository layout

```
.claude/skills/orient/
├── SKILL.md                       # this file — orchestrator
├── scripts/
│   └── infer_state_signals.py     # read-only push-inference pass (stdlib-only)
└── knowledge/
    └── inference-heuristics.md     # the signal taxonomy + how to read output
```

The schema written to `.engineering/project-state.json` is a **fixed contract**
shared with the standard-activation scanner. Changing it is a
coordinated change across both surfaces, not a local edit.
