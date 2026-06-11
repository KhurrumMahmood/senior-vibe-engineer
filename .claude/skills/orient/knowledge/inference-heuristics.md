# Push-inference heuristics for /orient

This is the reference for `scripts/infer_state_signals.py` — the
read-only "push" pass of ADR 0020. It explains what each signal means,
why it is recall-tuned (deliberately noisy), and how to read the output.

`/orient` itself is **pull** (a human runs it). This pass is **push**:
it watches for code that suggests the project has crossed a maturity or
stakes threshold and *prompts* a human to re-run `/orient`. It never
writes the state file — inference proposes, the human disposes.

## How to run

```bash
python3 .claude/skills/orient/scripts/infer_state_signals.py \
  --project-root /path/to/project        # default: cwd
python3 .claude/skills/orient/scripts/infer_state_signals.py --json
```

The scan is read-only. Its last line always confirms nothing was
written. Exit code is `0` for any scan outcome (signals or none); `2`
only on a usage error (bad `--project-root`).

## The signals

| Key | Looks for | Suggests | Axis |
|---|---|---|---|
| `unauth_side_effect` | POST/PUT/PATCH/DELETE route decorators and mutating handlers (Flask/FastAPI/Django/Express/Rails-ish) | A write surface exists — confirm whether it is reachable by untrusted callers without auth | stakes ↑ |
| `public_deploy` | Dockerfile `EXPOSE`, k8s `Ingress`/`LoadBalancer`, terraform LBs, nginx `server`/`listen`, and deploy-config *filenames* (`Dockerfile`, `vercel.json`, `netlify.toml`, `Procfile`, `fly.toml`, …) | First real public exposure / a persistent deploy | stakes ↑ (often maturity ↑) |
| `payment_pii` | Payment SDKs (stripe/braintree/paypal/plaid), PII tokens (`card_number`, `cvv`, `ssn`, `passport_number`), secret-vault clients | Regulated / high-blast-radius data is now handled | stakes ↑ |
| `auth_added` | OAuth/OpenID, `login_required`, session creation, JWT encode/decode, password verification, passport.js | Real users arriving and/or an exposed surface to protect | maturity ↑ and/or stakes ↑ |
| `real_user_data` | `User`/`Account`/`Customer` model classes, `CREATE TABLE users/accounts`, a Postgres/RDS/CloudSQL/Atlas production DB URL | Real users / real data are present | maturity ↑ |

## Why recall over precision

A false positive costs a human one glance ("no, that endpoint is
internal — dismiss"). A false negative costs the stated biggest hole in
ADR 0020: a prototype-grade control shipped into a relied-upon, exposed
context because nobody re-raised the bar at the transition. So the
patterns are intentionally broad. **A hit is a prompt for a human
decision, never a verdict.**

Concretely, expect noise:

- `unauth_side_effect` flags *every* write route; it cannot see whether
  an auth decorator/middleware guards it. It is "you have writes —
  confirm exposure," not "this is unauthenticated."
- `auth_added` and `real_user_data` fire on test fixtures and example
  code as readily as on production surfaces.
- `payment_pii` matches a variable named `card_number` even in a
  validation unit test.

This is acceptable by design. Do not tighten these into low-recall
precision detectors — that would defeat the purpose. If a project
generates persistent noise from a known-safe directory, add it to
`SKIP_DIRS` in the script rather than narrowing a pattern.

## Reading the output

Each signal with hits prints as `[FLAG]` or `[info]`:

- **`[FLAG]`** — the signal suggests a rung *above* the project's
  declared state (or there is no declared state). This is the "re-run
  /orient?" prompt.
- **`[info]`** — the signal fired but is at or below the declared state
  (e.g. a payments SDK in a project already declared `external`). No
  re-orientation prompted; shown for transparency.

The comparison is coarse on purpose: any stakes-bearing signal flags
when declared `stakes < external`; any maturity-bearing signal flags
when declared `maturity < first-users`. The precise human framing (which
exact rung, whether a single surface warrants a per-area exception) is
the `/orient` conversation's job, not the script's.

## What this pass does NOT do

- It does not write `.project-state.json` (or anything else).
- It does not auto-advance the declared state — only a human running
  `/orient` changes state.
- It does not judge whether a flagged write route is actually
  unauthenticated, or whether flagged PII handling is actually in a
  production path — it surfaces the situation for a human to judge.
- It is not a security scanner. Closing an unauthenticated
  side-effectful endpoint is a **baseline** standard enforced elsewhere
  (find-standard-gaps / review lanes); this pass only uses such signals
  as evidence that the *project's stakes classification* may be stale.

## Tuning

- **Add a skip directory:** extend `SKIP_DIRS` in the script (vendored
  SDKs, generated clients, large fixture trees).
- **Add a signal:** append a `Signal(...)` to `SIGNALS`. Keep it cheap
  (a single compiled regex over text lines), set `axis` to `stakes`,
  `maturity`, or `maturity+stakes`, and write a `suggests` phrase a human
  can act on. Recall-first still applies.
- **Add a deploy filename:** extend `DEPLOY_FILENAMES` (case-insensitive
  match on the file's name).
