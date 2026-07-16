# WP1 implementation evidence

Implementation revision: `e80456a` (clean worktree after removing automatic
test-run telemetry). Platform: macOS 26.5.1 / Darwin 25.5.0 / arm64.

Toolchain: Python 3.11.10, pytest 9.0.3, PyYAML 6.0.3, Ruff 0.6.9,
Node 22.21.1, npm 11.12.1. D3 candidates: tree-sitter 0.26.0,
tree-sitter-language-pack 1.12.5, ast-grep 0.44.1, TypeScript compiler API
5.9.3, and native TypeScript compiler 7.0.2.

## Acceptance evidence

| AC | Result | Evidence |
|---|---|---|
| AC-1.1 | implemented | `.claude/skills/_common/capability-registry.yml` contains versioned skill, stack, completion, and finding schemas plus separate runtime/language/framework/tool/root/layer/binding/scan/capability/support/evidence fields. `tests/test_capability_registry.py::test_future_language_is_registered_by_data_not_validator_code` proves registry-only extension. |
| AC-1.2 | implemented | `scripts/check_capability_registry_consumers.py` reports `OK — 7 consumers use the canonical capability registry`; its AST guard covers literal, nested, and simple statically computed collections, including `.split()`, `zip()`, `dict(...)`, constructors, and concatenation, plus retired assignment names and composite identifiers. Planted arbitrary-name/nested/constructor/split/zip variants all fail. |
| AC-1.3 | implemented | Strict contracts reject unknown capabilities, layer/binding mismatch, fabricated or shared `language: any` evidence, unexecuted per-subject evidence, unregistered/unproved scan targets, empty/unrelated scan scripts, scan support above its registered ceiling, and framework/tool confusion. Every portable subject has a distinct directly executed integration test and canonical observation. Every scan maps its registered mechanism to an exact contained script path/hash; that script is identically attested as a support artifact and is itself the target test executed by the fixture. Legacy frontmatter cannot acquire strict support. |
| AC-1.4 | implemented | Registry states are `unsupported`, `experimental`, and `verified`; one-step promotion and immediate demotion are mechanical. Evidence is canonically hashed/bound; fixtures emit claim+subject canonical JSON, paths/hashes are contained and fresh, execution is timeout-bounded, and tool probes use registry-owned arguments/version ranges and the actually discovered executable path. Tests cover stale files, generic/cross-claim reuse, symlink escape, false/timeout commands, fake Python/native tools, bad hashes, platforms, tool drift, and ceilings. Self-authored fixtures can reach `experimental`; `verified` is deliberately unavailable until WP8 pins the cross-stack conformance issuer path/hash. |
| AC-1.5 | implemented | Accepted ADRs 0038–0042 resolve D4, D3, D5, D2, and D1 respectively. Every ADR records alternatives, compatibility/migration, costs, and revisit triggers. Decision audit and link check exit 0. |
| AC-1.6 | implemented | `completion_floor.matrix_version: 1` defines every target stack, required outcome/WP owner, and five pinned agent surfaces. Each eventual cell/surface must carry AC-1.4 evidence, a unique test digest, an exact canonical observation, and (for surfaces) a compatible pinned version. The registry-pinned verification issuer is honestly `unavailable`/WP8-owned, so the gate currently rejects even well-shaped or relabeled/rehashed full-floor claims instead of self-certifying future work. Omission, labels, reuse, stale evidence, old versions, generic print scripts, and structural-only runs all fail. Floor changes require an ADR amendment plus migration review. |
| AC-1.7 | implemented | `analysis-portfolio-spike.json` records the pinned corpus/hash, candidates, precision/recall, unsupported facts, cold/warm runtime, install size, licenses, platform limits, deterministic setup, owners, selection, and WP4 budgets. The exact rerun below passed all declared budgets. |

## Commands and results

All commands ran from the repository root.

```text
.venv/bin/python -m pytest -q
445 passed, 1 skipped in 14.70s

.venv/bin/python scripts/check_capability_registry_consumers.py
OK — 7 consumers use the canonical capability registry

.venv/bin/python scripts/skill_meta.py lint --quiet
OK — 76 skills, 76 declaring new contract

.venv/bin/python scripts/decisions.py audit
OK — 34 decisions, no drift

.venv/bin/python scripts/decisions.py link-check
OK — 34 decisions, all links resolve, 22 host-scoped

.venv/bin/ruff check <all WP1 Python/test consumers>
All checks passed!
```

The one pytest skip is the pre-existing history-shape branch in
`tests/scripts/test_which_cleanup.py`; it is unrelated to WP1.

D3 deterministic setup and rerun:

```text
.venv/bin/python -m pip install --target /tmp/.../python \
  tree-sitter==0.26.0 tree-sitter-language-pack==1.12.5
npm install --prefix /tmp/.../node \
  @ast-grep/cli@0.44.1 typescript@7.0.2 \
  typescript-api@npm:typescript@5.9.3
.venv/bin/python scripts/analysis_portfolio_spike.py \
  --python-site /tmp/.../python \
  --node-modules /tmp/.../node/node_modules \
  --output /tmp/wp1-analysis-portfolio-a40d478.json
```

The rerun returned precision/recall 1.0 for every supported fact family.
Warm runtime/install size were: Tree-sitter 0.039996 s / 5,089,280 bytes;
ast-grep 0.067538 s / 154,339,105 bytes; TypeScript compiler API 0.645308 s /
23,625,066 bytes. The rerun JSON SHA-256 was
`a79eb2e269058b6cf96f5cebcb527bd66d45b439005fb33c8ff43523a91fcc25`.

D1 surface-projection probe:

```text
.venv/bin/python scripts/distribution_probe.py \
  .claude/skills/which-skill/SKILL.md /tmp/engineering-skills-distribution-probe
python3 <codex-home>/skills/.system/plugin-creator/scripts/validate_plugin.py \
  /tmp/engineering-skills-distribution-probe/codex
Plugin validation passed
```

Observed runnable versions were Claude Code 2.1.211, Codex CLI 0.144.1, and
Gemini 0.45.0. Augment and Cursor use pinned project-rule contract versions in
the matrix because no local CLI was available. WP3 owns cold-host runtime
discovery, transactional install/update/uninstall, and aliases; WP1 proves the
decision and generated projection contract, not those later acceptance claims.

## Evidence hashes

- `.claude/skills/_common/capability-registry.yml`:
  `87efcec9402cb5c17fcc41c305a035d2e3166cc5fea11ad0d2ea5cbf99372508`
- `reports/portable-skill-ecosystem-completion/WP1/analysis-portfolio-spike.json`:
  `eaec37c970c564483f8d0ca02325d6b570593b9b627c18865767d862ab922de1`
- `tests/fixtures/analysis_portfolio_spike/oracle.json`:
  `bd6c74f03c2397ef5453a6756b3c40456454aced4f444f446869970ecd67a1e3`

## Honest limitations and unsupported claims

- SCIP and LSP are explicitly unsupported pending named cross-project or
  interactive consumers.
- Rust and Go native sweep shims remain `unsupported`; WP5 must execute their
  fixtures before promotion.
- The D3 package/platform execution evidence is macOS arm64. Other published
  wheels/binaries remain unverified until the conformance matrix runs them.
- Existing catalog skills without `capability_contract: 1` remain legacy
  compatibility entries. WP8 must supply per-subject executable evidence before
  any of them receives a strict support claim.
- No target stack or agent surface is claimed complete in WP1; the matrix is a
  non-gameable final floor consumed by later gates.

## Failed-gate correction record

The first and second fresh-context verifiers failed AC-1.2, AC-1.3, AC-1.4,
and AC-1.6 at revisions `e20e521` and `4519e6a`; their full findings remain in
`verification-attempt-1.md` and `verification-attempt-2.md`. Revision `e80456a`
addresses both attack sets: computed registries; distinct subject fixtures;
exact executed scan implementations; canonical claim observations; discovered
native executables; unique floor evidence; and a registry-pinned conformance
issuer that prevents WP1 from certifying work owned by WP8. WP1 remains
`in_progress` until a third zero-context verifier reruns all seven criteria.
