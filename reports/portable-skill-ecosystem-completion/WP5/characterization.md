# WP5 characterization — portable batch sweep

Date: 2026-07-16

Scope: AR-1 through AR-12 from `ai-docs/specs/portable-batch-sweep.md`

Repository revision: `29352227a54428c3c574be9514ccbcc9ade67895`

Characterization lane: read-only except this report and ephemeral files under `/tmp`

Model: GPT-5 (Codex); model variant and effort setting were not visible to this lane.

## Result

All twelve ARs were exercised. The current repository supplies useful behavior
to freeze for AR-1, AR-3, AR-4, AR-5, AR-6, and AR-12, but it does not yet
satisfy the productized contracts. The most important implementation gaps are:

1. A failed prototype provider is published as an exit-0, zero-finding scan.
2. Malformed detector/JSON and Python parse failures are silently converted to
   zero findings.
3. The activation manifest and prototype sweep manifest can overwrite one
   another, and `scripts/manifest.py validate` accepts the resulting sweep
   document as an activation manifest.
4. `scripts/status.py` projects raw, unjudged manifest counts and IDs.
5. `scripts/queue_status.py` accepts packets with absent required fields and
   accepts a hand-authored `done`/`PASS` item without harness manifest/diff
   evidence.
6. The five final host fixtures, native-provider fixtures, productized sweep
   package, typed failure contract, judgment contract, and harness do not yet
   exist.

WP4 is still `in_progress` in the master tracker. This characterization did not
start parser-backed Slice 5 or claim any parser-backed WP5 support. Existing
detector behavior was run only to freeze the AR-5 before-state.

## Environment and workspace state

```text
Darwin Khurrums-MacBook-Air.local 25.5.0 arm64
macOS 26.5.1 (25F80)
Python 3.11.10
Ruff 0.6.9
Node v22.21.1
npm 11.12.1
```

At characterization start, the dirty paths were unrelated shared-workspace
files and were not edited by this lane:

```text
 M logs/agent_policy/test_runs.jsonl
?? logs/agent_policy/friction.jsonl
```

Native tool discovery on this machine:

```text
.venv/bin/ruff: present
node, npm: present
eslint, tsc, cargo, rustc, clippy-driver, go, staticcheck: missing
```

The combined version probe therefore exited `127` after reporting the missing
commands. This is environment evidence only; missing local tools do not weaken
the required WP5 live-provider matrix.

## AR-by-AR disposition

| AR | Disposition | Evidence-backed conclusion | Implementation consequence |
|---|---|---|---|
| AR-1 | **CHARACTERIZED — preserve selected semantics** | Two scans of the same fixture were byte-identical. The prototype battery families are `cx`, `omnibus`, `ruff`, and `strdisp`; the selected fixture emitted six `cx` findings. `--top 1` emitted one row plus `… 5 more`. Synthetic before/after manifests proved `1 fixed / 1 new / 1 persisting`; ratchet growth failed, a fix plus metric improvement tightened, and explicit accepts absorbed a growth and a new ID. | Copy these semantics into ordinary fixtures/tests; do not retain a runtime dependency on `.claude/tasks/sweep-prototype/`. Preserve set arithmetic, bounded digest behavior, fail-on-growth, tighten-on-improvement, and explicit accept while replacing the schema/identity/failure contract. |
| AR-2 | **CHARACTERIZED — reverse defects** | Prototype IDs are 12-character SHA1 values. `_jsonl` silently dropped malformed JSON; malformed Ruff JSON became `[]`; an injected broken provider yielded `errors={"broken":"boom"}`, zero findings, and `cmd_scan` exit `0`. Paths to the venv, Ruff, complexity detector, and omnibus detector are hard-coded relative to the prototype. Status consumes raw counts; queue verification is executor-adjacent prose rather than a harness. | Treat all named behavior as a defect, not compatibility: v2 identity, registry providers, typed loud failures, judgment-gated consumers, and harness-owned verification are required. |
| AR-3 | **PARTIAL — preserve implemented v2 identity; add missing manifest oracles** | `tests/test_finding_identity.py`: `6 passed`. It pins line/tool-version stability, anonymous multiplicity, provider/language namespaces, explicit case, path escape/absolute normalization, and move plus `legacy_ids`. Direct probe produced distinct `f2_` IDs and stable line/tool IDs. | Add manifest-level collision rejection and alias validation. Current `finding_record()` merely sorts/deduplicates alias strings; no writer rejects unequal-payload collisions, ambiguous/cyclic/cross-payload aliases, or assigns anonymous occurrences after stable source ordering. |
| AR-4 | **PRESERVE** | `tests/test_capability_consumers.py`: `5 passed`; `scripts/check_capability_registry_consumers.py`: `OK — 7 consumers`; the shim CLI resolved TypeScript from `typescript-syntax`, Rust from `cargo`, Go from `go-toolchain`, CSS unsupported, and rejected an unknown language with exit `2`. Static inspection shows only the canonical registry import and no activation-manifest import or local language/framework enum. | Keep `sweep_shims.py` thin and registry-driven. WP5 must refine registry/provider contracts to the selected concrete native portfolio without adding local enums or activation-manifest coupling. |
| AR-5 | **PARTIAL — preserve fixture behavior; reverse silent parse failure** | Complexity smoke: `OK - 6 bad fixture findings, good fixture clean`. Omnibus adapter suite: `4 passed`, covering Python bad/cohesive behavior, JS bad/cohesive behavior, minified/test skips, and language filter. An invalid Python file produced empty output and exit `0` from both complexity and omnibus detectors. | Freeze the current good/bad/cohesive/skip outputs through provider wiring, but convert unreadable/invalid/parser-failure paths into typed provider failures. Do not publish them as successful zero. |
| AR-6 | **PARTIAL — preserve read/list compatibility; add judgment gates** | Status/queue/render suite: `21 passed`. The status projection remains derived/read-only and does not include raw paths/summaries; queue stage/hook/list compatibility works. However a raw manifest with no judgments projected `available=true`, `counts={"ruff":1}`, and `finding_ids=["raw-unjudged"]`. Queue staging accepted empty scope and null verification/expected delta/budget. | Preserve projection read-only behavior and legacy listing. Require a fresh judged digest for structural health/dashboard data, and require the new sweep packet schema and judgment hash for packet/execution paths. |
| AR-7 | **GAP — current behavior violates the oracle** | In a temp host, `scripts/manifest.py validate` returned `manifest OK`; prototype `scan --out <host>/.engineering/manifest.json` overwrote it; activation validation still returned `manifest OK`. `scripts/sweep/` is absent and the prototype output has no schema version. | Give the activation and sweep artifacts separate paths, schemas, writers, validators, and commands. Strengthen activation validation so a sweep document cannot validate as activation state. |
| AR-8 | **GAP — oracle specified, fixtures absent** | All required `tests/fixtures/sweep/hosts/{python,typescript,rust,go,mixed}` directories are absent. A clean empty prototype scan and an injected failed-provider scan both returned `0` and published empty findings; only the optional `errors` map distinguished them. | Add five completed-clean zero fixtures and an otherwise identical failed-scan fixture. Only the completed scan may be classified clean or publish/tighten a success manifest. |
| AR-9 | **PARTIAL — Ruff before-state captured; native matrix absent** | Direct Ruff output for `tests/fixtures/analysis_facts/python-small.py` retained `F401`, exact row/column, message, and absolute path. Raw stdout SHA256 was `750dea77a33dd12b94f5fec8814f2eacb91efa038cd33781d730d41ff7f650a4`; empty stderr SHA256 was `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The prototype normalized it to file + rule + count, fixed severity `1`, and dropped location, version, raw hash, and original message. Other required native tools/fixtures are absent locally. | Add saved exact outputs and live fixtures for Ruff, ESLint, TypeScript compiler diagnostics, Clippy, and Go vet, retaining rule/location/severity/version and stdout/stderr hashes with repository-relative POSIX paths. |
| AR-10 | **PARTIAL — current ecosystem detectors are agent-free; full instrumentation absent** | Static scan found no socket/HTTP/model imports in the prototype or the two ecosystem detectors. With `socket.socket`, DNS, and `urllib.request.urlopen` replaced by failing functions, complexity still emitted six findings and omnibus completed. | Add explicit deny instrumentation around every native and ecosystem provider plus model-facade traps. The current probe does not cover absent native providers, subprocess children, or a model facade (none is wired here), so it is not AC-5.7 proof. |
| AR-11 | **GAP — no harness ownership enforcement exists** | A hand-authored queue item with `verification: "PASS (executor says so)"` and `status: "done"`, but no post-change manifest/diff, was read and listed with exit `0`. No `scripts/sweep` harness or queue verification validator exists; the queue contract only instructs a drainer to re-run checks. | Implement harness-produced manifest/diff evidence, independent rescan, scope and expected-delta enforcement, and rejection of executor self-attestation/stale evidence. |
| AR-12 | **PRESERVE** | `scripts/decisions.py audit`: `OK — 34 decisions, no drift`. ADR 0036 and ADR 0040 are accepted and explicitly pending WP5 productization work. ADR 0003 remains `proposed` with `embodied_by: pending:portable-skill-ecosystem-completion AC-8.9 formal disposition`. The plan retains `0026 → 0027 → 0028 → 0029/0030 → 0003`. | WP5 may update only ADR 0036/0040 productized embodiment when true. It must not change ADR 0003 status/embodiment or take AC-8.9 ownership. |

## Selected executable evidence

### AR-1 deterministic scan and bounded digest

Command (exit `0` for both scans; both `cmp` checks exit `0`):

```bash
TMP=$(mktemp -d /tmp/wp5-characterization.XXXXXX)
.venv/bin/python .claude/tasks/sweep-prototype/sweep.py scan \
  --root . \
  --scope .claude/skills/find-complexity-hotspots/fixtures \
  --top 1 --out "$TMP/scan-a.json"
.venv/bin/python .claude/tasks/sweep-prototype/sweep.py scan \
  --root . \
  --scope .claude/skills/find-complexity-hotspots/fixtures \
  --top 1 --out "$TMP/scan-b.json"
shasum -a 256 "$TMP"/scan-{a,b}.json "$TMP"/scan-{a,b}.digest.md
cmp -s "$TMP/scan-a.json" "$TMP/scan-b.json"
cmp -s "$TMP/scan-a.digest.md" "$TMP/scan-b.digest.md"
```

Output:

```text
[cx] 6 findings
[omnibus] 0 findings
[ruff] 0 findings
[strdisp] 0 findings
c89752953b3d8a8d37ae3553e8e9c11ba9a8a31effd18f382beb0b2659d7dfe9  scan-a.json
c89752953b3d8a8d37ae3553e8e9c11ba9a8a31effd18f382beb0b2659d7dfe9  scan-b.json
0332e783c419099db5b721cb74f139ac90d2f7ee2161bd62609224b31ae189ea  scan-a.digest.md
0332e783c419099db5b721cb74f139ac90d2f7ee2161bd62609224b31ae189ea  scan-b.digest.md
scan_rc=0,0 manifest_cmp=0 digest_cmp=0

## cx — 6
- `011a6cd88c34` s3 ...::query_inside_loop — ...
- … 5 more (see manifest)
```

The prototype battery declaration inspected was:

```python
BATTERY = {"cx": run_cx, "omnibus": run_omnibus,
           "ruff": run_ruff, "strdisp": run_strdisp}
```

### AR-1 diff and ratchet semantics

Command: a `.venv/bin/python` characterization probe loaded the prototype,
wrote synthetic manifests under `/tmp/wp5-characterization.DsaTLk`, invoked
`cmd_diff`, and monkeypatched only `build_manifest` to provide deterministic
current states to `cmd_ratchet`. Probe exit: `0`.

Output:

```text
fixed: 1   new: 1   persisting: 1
diff_rc= 1

RATCHET FAILED — 1 regression(s):
  GREW ... loc 10 -> 11  [persist-id]
ratchet_rc= 1

RATCHET OK — tightened baseline: 1 finding(s) removed, 1 metric(s) improved
ratchet_rc= 0 baseline_ids= ['persist-id']

RATCHET OK — tightened baseline: ... 2 deliberate increase(s) absorbed
ratchet_rc= 0 baseline_ids= ['persist-id', 'fixed-id', 'new-id']
```

### AR-2 loud-failure reversal

Command: a `.venv/bin/python` probe invoked `fid`, `_jsonl`, `run_ruff`,
`build_manifest`, and `cmd_scan` with deterministic malformed/broken inputs.
Probe exit: `0`.

Output:

```text
fid= 87454c967f8b length= 12
_jsonl_rows= [{'ok': 1}]
ruff_malformed_rows= []
failed_battery_manifest= {"counts": {}, "errors": {"broken": "boom"},
                          "findings": [], "total": 0, ...}
failed_battery_scan_rc= 0 manifest_exists= True
```

### AR-3 identity

```bash
.venv/bin/python -m pytest -q tests/test_finding_identity.py
```

Exit `0`:

```text
...... [100%]
6 passed in 0.03s
```

An initial direct probe without `PYTHONPATH=scripts` exited `1` with
`ModuleNotFoundError: No module named '_lib'`. The corrected exact invocation
was:

```bash
PYTHONPATH=scripts .venv/bin/python - <<'PY'
from _lib.finding_identity import FindingIdentity, finding_record
base = dict(provider='ruff', rule='E501:v1', language='python',
            path='src/A.py', semantic_anchor='anonymous:line-too-long')
a = FindingIdentity(**base, occurrence=0, case_sensitive=True)
b = FindingIdentity(**base, occurrence=1, case_sensitive=True)
print('anonymous_distinct=', a.identifier() != b.identifier(),
      a.identifier(), b.identifier())
print('line_tool_stable=',
      finding_record(a, tool_version='1', line=1)['id'] ==
      finding_record(a, tool_version='2', line=999)['id'])
PY
```

Exit `0`:

```text
anonymous_distinct= True f2_956e4bfa4c08048f4e308e72 f2_4a13c9cda3a9be06d341f2f2
line_tool_stable= True
```

### AR-4 canonical registry resolution

```bash
.venv/bin/python -m pytest -q tests/test_capability_consumers.py
.venv/bin/python scripts/check_capability_registry_consumers.py
.venv/bin/python scripts/sweep_shims.py typescript rust go css
.venv/bin/python scripts/sweep_shims.py made-up-language
```

Exit/output summary:

```text
5 passed in 0.30s                                      # exit 0
OK — 7 consumers use the canonical capability registry # exit 0
typescript -> adapter/typescript-syntax/experimental
rust       -> native-shim/cargo/unsupported
go         -> native-shim/go-toolchain/unsupported
css        -> unsupported                              # exit 0
error: unregistered languages: ['made-up-language']    # exit 2
```

### AR-5 detector behavior and parse failure

```bash
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/smoke.py
.venv/bin/python -m pytest -q tests/test_omnibus_language_adapters.py
```

Both exited `0`:

```text
OK - 6 bad fixture findings, good fixture clean
.... [100%]
4 passed in 0.05s
```

A first dynamic-import probe exited `1` because it did not register the loaded
module in `sys.modules` before evaluating a dataclass. The corrected probe did
so, wrote an invalid Python file in a temporary directory, and called both
detectors. Corrected probe exit `0`:

```text
wrote 0 findings to .../cx.jsonl
[detect_omnibus] wrote .../om.jsonl (0 omnibus candidates across 1 files)
invalid_python: {'cx_rc': 0, 'cx_output': '', 'om_rc': 0, 'om_output': ''}
```

### AR-6 projection and queue before-state

```bash
.venv/bin/python -m pytest -q \
  tests/test_status.py tests/test_queue_status.py tests/test_render_status.py
```

Exit `0`: `21 passed in 4.02s`.

Direct probes (exit `0`) produced:

```text
raw_unjudged_status= {"available": true, "counts": {"ruff": 1},
  "finding_ids": ["raw-unjudged"], "total": 1, ...}
nullable_packet= {
 "expected_delta": null, "scope": [], "token_budget": null,
 "verification": null, ...
}
```

### AR-7 schema/path collision

```bash
TMP=$(mktemp -d /tmp/wp5-ar7.XXXXXX)
# Seed $TMP/.engineering/manifest.json with a valid activation document.
.venv/bin/python scripts/manifest.py --project-root "$TMP" validate
.venv/bin/python .claude/tasks/sweep-prototype/sweep.py scan \
  --root "$TMP" --scope . --out "$TMP/.engineering/manifest.json"
.venv/bin/python scripts/manifest.py --project-root "$TMP" validate
```

All three commands exited `0`:

```text
manifest OK
wrote .../.engineering/manifest.json + .../.engineering/manifest.digest.md
manifest OK
```

The overwritten document was the unversioned sweep shape:

```json
{"target":"/private/tmp/...","scope":["."],"counts":{},"total":0,
 "errors":{},"findings":[]}
```

`scripts/manifest.py --help` exposes activation commands
`show/resolve/validate/is-active/deactivate/activate`; prototype `sweep.py
--help` exposes `scan/diff/ratchet`; `scripts/sweep/` is absent.

### AR-8 host fixtures and zero/failure distinction

```bash
for host in python typescript rust go mixed; do
  test -d "tests/fixtures/sweep/hosts/$host" && echo PRESENT || echo ABSENT
done
```

Exit `0`; all five printed `ABSENT`.

The AR-7 empty scan returned `0`, `errors={}`, `findings=[]`. The AR-2 injected
failed scan also returned `0`, with `errors={"broken":"boom"}` and
`findings=[]`. Thus current callers can distinguish them only by inspecting an
optional field; process status and publication behavior do not enforce the
distinction.

### AR-9 Ruff raw-output before-state

```bash
.venv/bin/ruff check --output-format json --exit-zero \
  tests/fixtures/analysis_facts/python-small.py \
  >/tmp/wp5-characterization.DsaTLk/ruff-raw.json \
  2>/tmp/wp5-characterization.DsaTLk/ruff-stderr.txt
shasum -a 256 /tmp/wp5-characterization.DsaTLk/ruff-{raw.json,stderr.txt}
.venv/bin/python .claude/tasks/sweep-prototype/sweep.py scan \
  --root . --scope tests/fixtures/analysis_facts/python-small.py --top 10 \
  --out /tmp/wp5-characterization.DsaTLk/ruff-prototype.json
```

Both tools exited `0`. The raw output contained `F401`, row `1`, columns
`21..25`, and `` `pathlib.Path` imported but unused ``. The prototype emitted:

```json
{"id":"52d57310bc22","rule":"ruff:F401",
 "path":"tests/fixtures/analysis_facts/python-small.py","symbol":"",
 "severity":1,"summary":"1 instance(s) of F401","count":1}
```

### AR-10 network/model boundary

Static command:

```bash
rg -n "OpenAI|Anthropic|model|agent|requests|httpx|urllib|socket|getaddrinfo|urlopen" \
  .claude/tasks/sweep-prototype/sweep.py \
  .claude/skills/find-complexity-hotspots/scripts \
  .claude/skills/find-omnibus/scripts scripts/sweep_shims.py
```

Exit `0` only because descriptive occurrences of `agent`/network-risk terms
exist; no detection-time socket/HTTP/model import or call was found.

A `.venv/bin/python` probe replaced `socket.socket`, `socket.getaddrinfo`, and
`urllib.request.urlopen` with functions that raise, then invoked the two
ecosystem detectors. Exit `0`:

```text
network_denied_ecosystem= {'cx_findings': 6, 'omnibus_rc': 0,
                           'omnibus_bytes': 0}
```

### AR-11 self-attestation

A `.venv/bin/python` temp-host probe hand-authored a queue item containing
`verification: "PASS (executor says so)"` and `status: "done"` with no
manifest/diff, then called `read_items` and `cmd_list`. Exit `0`:

```text
fake-pass  [done]  change code  (1 file(s); staged 2026-07-16T00:00:00+00:00)
0 staged of 1 total.
list_rc= 0
```

### AR-12 predecessor order

```bash
.venv/bin/python scripts/decisions.py audit
```

Exit `0`: `OK — 34 decisions, no drift`.

Frontmatter inspection with `.venv/bin/python` + PyYAML produced:

```text
0003 status=proposed
     embodied_by=['pending:portable-skill-ecosystem-completion AC-8.9 formal disposition']
0036 status=accepted
     embodied_by=['script:.claude/tasks/sweep-prototype/sweep.py',
                  'pending:productization ... WP5']
0040 status=accepted
     embodied_by=['script:scripts/_lib/finding_identity.py',
                  'contract:tests/test_finding_identity.py',
                  'pending:WP5 migrates ...']
```

## Command ledger

All repository Python commands used `.venv/bin/python` explicitly. Inspection
commands (`sed`, `rg`, `find`, `git`, `uname`, `sw_vers`, `shasum`, `cmp`, and
`command -v`) were read-only. The substantive executable commands and statuses
are recorded above. Additional governing/source inventory commands all exited
`0`, except:

- `rg` over a list containing nonexistent `docs/` exited `0` because matching
  results were still found, while also printing `rg: docs: No such file or
  directory`.
- The first direct identity probe exited `1` due to missing
  `PYTHONPATH=scripts`; the corrected probe exited `0`.
- The first direct detector-import probe exited `1` due to the probe's
  `sys.modules` omission; the corrected probe exited `0`.
- The combined native version command exited `127` because ESLint, TypeScript,
  Rust/Clippy, Go, and staticcheck binaries are not installed on this machine.

No project runtime/code, master plan, WP5 spec, WP3/WP4 file, or decision was
modified by this lane.
