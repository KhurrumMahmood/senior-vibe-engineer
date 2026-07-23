# Dart D3 declaration/body consumer family

Status: accepted implementation candidate; this packet publishes no Dart
support and changes no central skill prose, coverage, routing, profile, plan,
installer, provider, or framework surface

Base revision: `a3e6ff9fcaabfc129ba2481fd94b4bc106f8a3ef`

## Outcome and dispositions

The accepted additive D2 provider contract is sufficient for all four bounded
D3 outcomes. One content-addressed union snapshot invokes that unchanged
provider once and each consumer independently validates the snapshot, its
source lineage, the accepted tool-package manifest, target coverage, and its
required public fact groups. Interpretation and final artifacts remain local
to the consumer.

| Skill | Worker disposition | Final value |
|---|---|---|
| `explain-code` | `dart-complete-implementation-candidate` | Direct public class, enum, extension, mixin, typedef, and top-level-function declarations reach bounded annotations, target inventory, final explanation, and explicit re-export/unexplained sidecars. A private-only target is a successful explicit empty outcome. |
| `find-complexity-hotspots` | `dart-complete-implementation-candidate` | A named direct body with the frozen score of 18 reaches `detections.jsonl`, `findings.json`, `report.md`, `scan.json`, and `latest`, with exact event/body/declaration lineage. |
| `find-duplication` | `dart-complete-implementation-candidate` | One at-least-five-line exact public-analyzer token clone pair reaches `collapsed.json`, `ranked.json`, `triage.md`, `findings.json`, and `scan.json`. |
| `find-omnibus` | `dart-complete-implementation-candidate` | Two syntax candidates reach complete human-scout accounting; the four-domain library is `confirmed_omnibus`, the cohesive control library is `facets_not_domains`, and only the confirmed candidate becomes a decomposition finding. |

Root may promote these rows only after serial integration and publication. The
worker changed no `SKILL.md`, matrix, generated projection, router, catalog,
profile, plan, installer, backlog, `_common`, Dart analyzer provider/tool, or
Flutter surface.

## Accepted fact boundary and union snapshot

The existing provider and locked tool remain byte-for-byte unchanged:

- `.claude/skills/_dart/scripts/dart_syntax_facts.py` SHA-256
  `c162ad0393237ef9f5a1541768f24f14303ba9e66ee24762d21ddb1261bbf6e0`;
- locked tool-package manifest SHA-256
  `77486420178671884b4b0e409e44ad0d58080d6a29eaef41bd2bab56314acb6e`;
- Dart executable SHA-256
  `db03bb4f7a2b4914f8242641d44a7f29d3abb22324d576fc5a69f07fc1aab560`;
- analyzer 14.1.0 and SDK range `>=3.12.0 <3.13.0`; and
- only public `package:analyzer` imports, with no `package:analyzer/src/...`.

The new `dart_d3_snapshot.py` is a D3 batching/provenance wrapper, not another
syntax provider. It calls `dart_syntax_facts.produce()` exactly once and adds:

```text
schema_version, analyzer, status, failure_kind, consumer_union,
snapshot_key, snapshot_key_sha256, snapshot_sha256, provider
```

The key contains the provider source manifest, selected-source manifest,
accepted tool-package SHA, analyzer package version, Dart SDK version, target,
and native options. Consumers reject a corrupt key/hash, an unaccepted
producer manifest, a target mismatch, source mutation, stale current source,
or missing required arrays. Missing provider/companion evidence is terminal
partial; malformed or stale evidence is failed. No consumer calls Dart, Pub,
the analyzer provider, a regex lexer, or a second parser.

The consumer fact sets are exact:

| Consumer | Required public fact arrays | Consumer-local decisions |
|---|---|---|
| `explain-code` | `directives`, `declarations` | public direct-declaration kinds, annotation format, 15-target cap, re-export explanation boundary, final prose/sidecars |
| `find-complexity-hotspots` | `named_bodies`, `direct_body_branches` | eligible body kinds, score = direct event count, frozen threshold 18, ranking/report schema |
| `find-duplication` | `named_bodies`, `body_tokens` | top-level-function/method eligibility, five-line minimum, exact `(token_kind, lexeme)` normalization, grouping/ranking/triage |
| `find-omnibus` | `declarations` | direct top-level-function eligibility, generic-verb removal, four paired head-noun threshold, stable candidate hashes, scout schema/verdicts/final findings |

The wrapper publishes no explanation prose, score, normalized clone hash,
clone group, rank, head-noun cluster, candidate, scout verdict, or final report
schema.

## Final consumer evidence

### Explanation

`lib/public_surface.dart` produces five selected public declarations:
`InvoiceMapper`, `PaymentState`, `InvoiceService`, `InvoiceFormatting`, and
`calculateInvoice`. Every target has exact declaration offsets/lines,
`source_sha256`, `spelling_sha256`, a stable symbol key, and one annotation.
Private members/functions, imports, declaration-shaped strings, generated
source, and the declaration behind a syntax-only re-export are not explained
as direct exports. The export remains visibly unresolved in `targets.json`,
`unexplained.txt`, and the final Markdown. The clean private-only fixture
finishes complete with zero targets and empty sidecars.

### Complexity

`routeInvoice` emits exactly 18 direct events: `logical_and`, `logical_or`, ten
`if` events, `for`, `while`, `do`, two non-default `switch_case` events, and
`catch`. The consumer freezes the threshold at 18 and reports that one body.
The branch-heavy nested closure and local function each publish zero direct
events for their enclosing owner and never become findings. Every finding
carries declaration/body spans and hashes plus exact event spans and spelling
hashes. A clean host retains a complete empty report and `latest`; failed or
partial evidence removes `latest`.

### Duplication

`normalizeInvoice` and `normalizePayment` have six-line bodies with identical
ordered public-analyzer `(token_kind, lexeme)` sequences. One stable clone
finding cites both exact declaration/body spans, source/body/spelling hashes,
line counts, token counts, and a consumer-owned normalized hash/rank. A
behaviorally similar but token-different function, one-line trivial bodies,
constructor/accessor bodies, nested closures, and excluded source roles do not
fire. `triage.md` explicitly refuses automatic consolidation or behavioral
equivalence.

### Omnibus and human scout accounting

Syntax nominates exactly two files:

- `lib/omnibus.dart`: four paired invoice/payment/shipping/audit domains;
- `lib/cohesive_control.dart`: four paired header/body/footer/checksum facets.

Every candidate has a stable candidate ID/SHA bound to the file source hash,
cluster membership, exact declaration spans, and spelling hashes. With no
scout files the run is `partial/human_scout_required`, reports both candidates
as ungraded, and emits zero confirmed findings. Fixed SHA-bound human inputs
use `human_verdict: accepted`; the first becomes `confirmed_omnibus`, the
second `facets_not_domains`. Final accounting is exactly two candidates, two
graded, zero ungraded, while only the confirmed row appears in
`omnibus.jsonl`/final findings. Accepted scout artifacts are retained under
`scout/*.json`. Extensions, mixins, strings, barrels, file size alone, and
excluded roles cannot become candidates or confirmed findings.

## Fixture, exclusions, lifecycle, and closure proof

The frozen D3 fixture contains 24 files / 7,740 bytes with manifest SHA-256
`6cde43b318e7231e54f67df9ff319bcd3b63b6dec838fdf15955bd8736f0a5fc`.
It has positive and clean pubspec-only hosts, `lib`, `bin`, and `tool` native
entrypoints, generated suffix/header cases, `test`, `example`, `build`,
`vendor`, build-directory semantics, an external symlink target, strings,
private declarations, nested closure/local function, trivial/constructor/
accessor bodies, a barrel, extension/mixin decoys, and a large non-omnibus
file.

The focused contract proves:

- one complete union snapshot drives all four actual final artifact sets;
- positive, clean/private-only, and ungraded-refusal outcomes;
- exact roles for source, test, example, generated, vendor, build, and symlink
  inventory, with only eligible source becoming facts/findings;
- current-source staleness is rejected independently by every consumer;
- complete -> failed parse -> complete at the same destinations, with stale
  findings/annotations/`latest` removed;
- complete -> partial missing copied provider -> complete from an installed
  selected-skill plus sibling `_dart` closure;
- execution from an unrelated working directory with product Python, no
  ambient repository imports, network fetch, install, host Pub write,
  `.dart_tool`, host `pubspec.lock`, or source mutation; and
- native `dart analyze --fatal-infos --fatal-warnings`, check-only Dart format,
  dependency-free direct test, and exact smoke stdout.

The four extended selected-skill plus `_dart` closures are descriptive
base-without-capability measurements, not the ML-025 sharing comparison:

| Closure | Base files/bytes | Extended files/bytes | Capability delta | Extended SHA-256 |
|---|---:|---:|---:|---|
| `explain-code` + `_dart` | 13 / 197,016 | 15 / 217,977 | +10.64% | `2d672f358487023deadc623e1a9c8447132ef488195f6eac2b999cffc1ddc0bf` |
| `find-complexity-hotspots` + `_dart` | 17 / 165,129 | 19 / 185,299 | +12.21% | `57ba34169f62ffd5192831c06860f1c5ade544fe92c6ee7d49fbb55e2761166a` |
| `find-duplication` + `_dart` | 24 / 246,665 | 26 / 268,382 | +8.80% | `1f97e928500f29334dea50069a7107c8035d21fbae5d3ec0ea07f1cd693f3427` |
| `find-omnibus` + `_dart` | 16 / 196,117 | 18 / 219,060 | +11.70% | `2115fd46638ca461c9a7bc19f724fcfd9a7c5dbbd9d937d229c777e11c5ca6a8` |

## Batching and maintained-LOC economics

One warmed-cache union run and four independent starts used the same clean
fixture, product Python, Dart 3.12.2, locked offline analyzer setup, native
matrix, target, and options. This is a local observation, not a threshold.

| Shape | Wall observations | Total wall | Analyzer observations | Total analyzer |
|---|---|---:|---|---:|
| One union snapshot | 4.2909 s | 4.2909 s | 3.4408 s | 3.4408 s |
| Four independent starts | 4.2893, 4.4127, 4.3244, 4.2979 s | 17.3241 s | 3.4368, 3.5343, 3.4672, 3.4486 s | 13.8869 s |
| Avoided | — | 13.0332 s (75.23%) | — | 10.4461 s (75.22%) |

The analyzer/Pub process startup dominates each independent run, so one union
snapshot removes three starts without a daemon or provider change.

Using physical LOC and the accepted ML-025 convention:

- `H = 1,454`: accepted provider Python + Dart analyzer executable + pubspec +
  D3 snapshot/provenance wrapper;
- `C = 1,689`: four consumer adapters + the final-outcome contract test;
- shared design `C + H = 3,143` lines;
- equivalent per-consumer provider copies `C + 4H = 7,505` lines; and
- maintained-LOC reduction is 58.12%.

The honest aggregate installed-family byte comparison counts all four selected
skills. One shared `_dart` closure is 673,593 bytes / 60 files; four equivalent
consumer-local `_dart` copies are 890,718 bytes / 78 files. Sharing is 217,125
bytes (24.38%) smaller and does not grow the equivalent copied closure. Runtime
is also lower by 75.23%, so the sharing shape clears ML-025; the descriptive
base-without-Dart deltas above are not that gate.

## Verification and preserved-language state

Passing candidate verification:

- `tests/test_dart_d3_declaration_body_family.py`: 11 passed;
- `tests/test_dart_d2_provider_extension.py`: 3 passed;
- `tests/test_dart_d2_syntax_family.py`: 16 passed;
- preserved explain implementations: 20 passed after removing local ignored
  `__pycache__` created by a compile probe;
- preserved complexity implementations all passed; the broader group had 38
  passes plus two untouched router failures described below;
- preserved duplication implementations had 37 passes plus two stale
  publication assertions described below; and
- preserved omnibus implementations had 56 passes plus one stale publication
  assertion described below;
- `tests/test_skill_comply.py`: 4 passed; and
- the explicit staged-file pre-commit run passed every applicable Ruff,
  whitespace, YAML, conflict, size, project-lint, host-reference, and drift
  hook (ADR- and `SKILL.md`-only hooks skipped because this lane owns neither).

Five pre-existing assertions fail against exact base metadata and were not
changed in this forbidden shared-publication lane:

1. `tests/test_find_duplication_python.py::test_copied_python_pipeline_preserves_legacy_scout_triage`
   and
   `tests/test_find_duplication_go.py::test_go_contract_declares_bounded_evidence`
   expect `scans: [python, javascript, typescript, go, java]`; exact base
   `a3e6ff9` already has `[..., rust]`.
2. `tests/test_omnibus_typescript.py::test_frontmatter_truthfully_declares_all_supported_scanners`
   expects `[..., go, java, swift]`; exact base already has
   `[..., go, java, rust, swift]`.
3. `tests/test_code_health_family.py::test_router_selects_bounded_health_family_without_ambient_members`
   routes to `which-shape` rather than the stale expected complexity member.
4. `tests/test_code_health_family.py::test_all_benchmark_user_prompts_activate_the_family`
   has one exact-base prompt stop at an unavailable Django-only stronger match
   rather than activating the family.

No `SKILL.md`, router, family, or central metadata differs from `HEAD` in this
worker. These failures reproduce without D3 consumer execution; repairing them
belongs to root/shared publication ownership.

The generic skill-creator `quick_validate.py` also rejects the repository's
pre-existing extended frontmatter keys (`job`, `tier`, `language`, routing
metadata). Shared `SKILL.md` is explicitly out of scope, so repository Ruff,
focused tests, preserved implementation tests, Dart format/native gates, and
hooks are the applicable validators.

## Limitations

- D3 is syntax-only. It resolves no symbols, imports/exports, aliases, callers,
  types, flow, runtime behavior, generated semantics, framework behavior, or
  Flutter widgets/routes/state.
- Conditional directives and parsed augmentations remain provider partial;
  parse diagnostics and native-gate failures remain failed.
- Explanation records direct syntax surface, not contracts or behavior.
- Complexity counts frozen direct branch/operator events and excludes nested
  closure/local-function ownership; it is not cognitive or runtime cost.
- Duplication is exact analyzer-token evidence for direct top-level functions
  and methods only. Constructors/accessors/operators, semantic equivalence,
  ownership, and consolidation safety remain outside the claim.
- Omnibus uses head-noun nomination only. SHA-bound human scout judgment is
  mandatory, and even `confirmed_omnibus` proves no safe split.
- The SDK/analyzer pins, offline cache availability, core-Dart role policy,
  package-workspace boundary, and no-Flutter boundary remain unchanged.

## Root integration steps

1. Cherry-pick the D3 consumer commit after exact accepted base `a3e6ff9`; do
   not resolve it by changing the D2 provider/tool.
2. Replay the 11 focused D3 tests, 3 D2 extension tests, and all 16 preserved
   D2 syntax-family tests with the frozen product Python and Dart path.
3. Copy each selected skill plus the single sibling `_dart` closure outside the
   repository/host and replay the documented fact-pack + consumer commands;
   preserve explicit omnibus scout input and accounting.
4. Confirm `git diff` contains no provider/tool, shared `SKILL.md`, matrix,
   router, catalog, profile, plan, installer, `_common`, framework, or other
   batch changes.
5. From root ownership only, publish each of the four bounded Dart dispositions
   independently, regenerate coverage/projections, and update routing/catalog/
   plan/installer surfaces serially.
6. Repair or consciously baseline the five stale shared-suite assertions in a
   separate root-owned change; do not mix that publication maintenance into
   this D3 consumer commit.
