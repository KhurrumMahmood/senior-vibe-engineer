# find-duplication TypeScript v1 learning report

Current implementation revision: `8e4a585e20bcf8a3ae47cdef51e413673b99eb2c`
on `codex/ts-duplication`; D6 clean-room replay and post-D6 rerun hardening
completed 2026-07-19 UTC.

## Outcome and scope

`find-duplication` now has a narrow TypeScript v1: it reports substantial
lexical/near-lexical `.ts` and `.tsx` clone clusters with the jscpd line spans
and enclosing function/arrow names that a conservative mapper can prove. The
final `triage.md` and `findings.json` repeat the key boundary: this is evidence
for a human to investigate, never proof of semantic equivalence or safe
consolidation.

The supported outcome excludes TypeScript type facts, module resolution, call
graphs, frameworks, React/Node conventions, class-method mapping that the
mapper cannot prove, and refactoring/codemod execution. The installed router
must therefore advertise this revision as `typescript/any`; the retained Python
replay is a frozen reference oracle, not a broader routing claim.

## Reference repair

The existing Python `collapse.py` resolved symbols through the repository
language-adapter registry. That made a source-tree run look portable even though
a copied skill could not import it. The reference path now uses only Python's
stdlib `ast`, and the locked oracle contains one real clone pair plus a
behaviorally different clean file. It produces one stable finding whose symbols
are `summarize_queued_entries` and `summarize_pending_entries`.

The TypeScript report also previously inherited an execution-oriented triage
shape. The renderer now marks TypeScript findings as lexical evidence whose
semantic/refactor safety is unknown, removes the direct execution instruction,
and asks for body/caller review before a proposal.

## TypeScript model and tool decision

The accepted TypeScript outcome is lexical cloning, so `jscpd@4.0.5` is the
least tool that supplies mature token-level clone detection. The selected
family-local wrapper stages only eligible source then runs stock
`npx --offline` with `NPM_CONFIG_OFFLINE=true` and a caller-selected cache.
It never makes a network attempt. Cache/tool absence is an explicit status-3
preflight failure, not an empty clean result.

The mapper masks strings and comments, identifies ordinary function declarations
and block-bodied arrows, and discards a raw clone pair unless the complete
start-to-end range at each site fits one real enclosing symbol. It also drops
generated/test/declaration/vendor paths and overload signatures. This strictness
is intentional: a false negative is better than an invented source owner. It is
not a TypeScript parser platform.

The collapse stage retains exact clone occurrences (`file`, `symbol`, start,
end), rather than collapsing all pairs that merely name the same symbol. Raw
pairs form one cluster only when those occurrences overlap, so separate repeated
blocks in one long function remain separate leads. The offline wrapper validates
the pinned jscpd report shape before adding its completed metadata; malformed
zero-exit JSON is a status-3 failure and the unusable report is removed.

Rejected alternatives were the TypeScript Compiler API, tree-sitter/ts-morph,
a handwritten token-clone detector, runtime network fallback, and a shared
TypeScript parser/executor. None improves the narrow accepted outcome enough to
justify a new runtime or abstraction; there is no second accepted consumer.

## Fixture and verification evidence

The locked TypeScript host includes:

- A real typed clone cluster: `src/queue_one.ts` and `src/queue_two.ts`.
- A behaviorally different source pair that contains no substantial lexical
  clone: `src/behaviorally_different.ts`.
- TSX syntax: `src/Panel.tsx`.
- Must-not-fire boundary shapes: generated source, a test clone, `.d.ts`, and
  function overload signatures.

The final-outcome test uses a locked jscpd report containing all boundary pairs,
runs `collapse_typescript.py -> rank.py -> report.py`, checks the final
`triage.md`/JSON for exactly the two typed clone symbols and their spans, checks
all filter reasons, and snapshots the complete source tree before/after. This
is a final artifact assertion rather than a parser-helper test.

Initial red evidence, before the TypeScript scripts/reports existed:

```bash
.venv/bin/python \
  -m pytest tests/test_find_duplication_typescript.py -q
# 4 failed
```

After production work:

```bash
.venv/bin/python \
  -m pytest tests/test_find_duplication_typescript.py -q
# 10 passed

.venv/bin/ruff check \
  .claude/skills/find-duplication tests/test_find_duplication_typescript.py
# All checks passed

NPM_CONFIG_CACHE=/tmp/find-duplication-npm-cache \
  npx --offline --yes -p typescript@5.9.3 tsc --noEmit \
  -p tests/fixtures/find-duplication-typescript/typescript-host/tsconfig.json
# 0
```

A copied directory at `/tmp/find-duplication-final-install.mEW5CW` ran with
`python3 -I -S` outside the checkout against
`/tmp/find-duplication-final-host.JRyLma`. Its real offline jscpd run wrote
`reports/jscpd/jscpd-report.json`, one `ts-jscpd-0001` cluster in
`collapsed.json`, `ranked.json`, `triage.md`, and `findings.json`; direct
source hashes were unchanged. A fresh forward task then received the installed
directory and raw host at `/tmp/find-duplication-forward.VwLoi4`, but no
expected diagnosis. It ran all four installed `python3 -I -S` commands against
the pre-provisioned offline cache with status 0 and wrote
`reports/duplication/scan-20260719-080641` plus `latest`. It independently
reported the one P2 `ts-jscpd-0001` cluster with 13 shared lines between
`summarizeQueuedEntries` and `summarizePendingEntries`, interpreted it as
evidence rather than safe consolidation, and found no excluded boundary path.
One raw detector pair was deliberately omitted as `unmapped_symbol`; the source
fingerprint before/after was exactly
`f506d3fe7ab415e6aced3cd93237e3c18bcc654881e737fec87e96927e3b81f6`.

The preceding forward replay predates the adversarial repair and does not count
as D6 evidence. D6 was rerun from implementation commit
`5d5394f9290fb521799157f4730528e5970ae0e0` as a genuinely fresh, no-context
clean-room journey. The preserved task was: “Audit this TypeScript project for
meaningful duplicated implementation, produce the skill’s final report
artifacts, and tell me which findings deserve engineering review. Do not edit
source files.” Its SHA-256 is
`a027d91e56b9333d6f6604133ae498ffa24ed8c9f46a47d6f8af4e0811b8c370`.

The pinned stock installer (`skills@1.5.19`) copied only `find-duplication` to
`/private/tmp/find-duplication-ts-journey.KpDQtl/host/.agents/skills/find-duplication`.
The full evidence handoff is
`/private/tmp/find-duplication-ts-journey.KpDQtl/evidence`; its command record
and pipeline transcript have SHA-256 hashes
`bb0a50fbc700278c56d69ce181b47913d950e1a63f75b226b1e9ff06fcb4f514`
and `5df7844322d195bf8cf78a07a360880b58e0218a68be7b4d5d3090d337e6da75`.
The four installed stages completed with raw=2, filtered=1, findings=1 and
P0/P1/P2=0/0/1. The one conservative `ts-jscpd-0001` finding covers 13 lines
between `summarizeQueuedEntries` and `summarizePendingEntries`; the other raw
pair was correctly filtered as `span_crosses_symbol_boundary`. The independent
interpretation recommends routine P2 review and explicitly rejects automatic
consolidation.

The final report directory is
`/private/tmp/find-duplication-ts-journey.KpDQtl/host/reports/duplication/scan-20260719-083525`.
Artifact SHA-256 hashes are:

- `jscpd/jscpd-report.json` — `03dc2b397d6e9ef98e44c92a47ee5b9e4f5351f95c639d7fb7057f1aba246819`
- `jscpd/run.json` — `2630546c2fb959b18da992948a64cf632080f97f1a4e557508a6ffb744f1a5ad`
- `collapsed.json` — `23070a4f2de201072f66161d3819ddcc3801ba55cca83f4741e5927bd0096561`
- `ranked.json` — `fe3784ae16ccc080091813e8449dde590a55d46741bcb275cd6e334a00870820`
- `triage.md` — `a178dff9d49cbdeaf82bc30a03479f96fadec903286b505d925d27e5d2d67c20`
- `findings.json` — `9b42507e3ba508ac51501a06a3a0680f1377bfee76a143da38dfbd5095c3bc35`

The pre- and post-audit source manifests are byte-identical and each hashes to
`f506d3fe7ab415e6aced3cd93237e3c18bcc654881e737fec87e96927e3b81f6`.
The preserved verification says `IDENTICAL: source SHA-256 manifests match
before and after the audit.` D6 therefore closes with the installed final
output, task handoff, command output, artifact hashes, and read-only source
proof intact.

## Post-D6 rerun hardening

Final adversarial review reproduced a P1 rerun defect at
`/private/tmp/find-duplication-rerun.pbamNy`: when `--target` named the host
root and report output lived below it, a second run rediscovered the first
run’s `.jscpd-input` source copies and reported false sites below `reports/`.
The repair now enumerates source before staging, excludes the current output
root, skips every `.jscpd-input` and conventional `reports` tree, and applies
the report/staging boundary again while collapsing hand-supplied evidence.
Invalid or empty zero-exit detector JSON is also deleted, matching the skill’s
failure contract rather than leaving an unusable `jscpd-report.json` behind.

The exact regression copies only the selected skill, runs it twice with
`python -I -S`, uses the host root as target, and puts each output under an
arbitrary nested `arbitrary-audit-output/` path. The second collapsed artifact
must contain exactly one finding whose sites remain `src/queue_one.ts` and
`src/queue_two.ts`; its `run.json` must list no nested output source. Separate
coverage feeds both empty and syntactically invalid JSON from a zero-exit fake
detector and asserts that neither `jscpd-report.json` nor `run.json` survives.

A real copied-skill/offline replay is preserved at
`/private/tmp/find-duplication-rerun-repair.XqTK05`. Both full four-stage runs
used `python3 -I -S`, targeted the host root, and wrote beneath the arbitrary
nested output directory. The second run retained only `ts-jscpd-0001` with
original sites `src/queue_one.ts` and `src/queue_two.ts`; its five eligible
sources contain no output or staging path. Second-run artifact SHA-256 hashes
are:

- `jscpd/jscpd-report.json` — `b836450ca4f6705d04b66b77fbe779f04e67db93c37d811577c2cf858fe20d19`
- `collapsed.json` — `52c2c41cafb97ce21e1b46fe0bfaae15c6b83d950d082761ed894db3c30279ae`
- `ranked.json` — `fe99fa981b919ad460cabc484d6ac3fa5691b4df334c13d3f09d737dc949e3ab`
- `triage.md` — `50c0ea39d2173ac2928e8b3a2b8edda15b854827abbfa2b113dbab6945d06560`
- `findings.json` — `2aaea49f89c640535e920502967d70a91de7eff1ee583081ed305d94ca0038a6`

The pre/post `src` manifests are byte-identical and both hash to
`219b3169f4b8261f265e66d667fa851830f230f6852ce5c4e0531d394713b47e`.
This post-D6 evidence is tied to implementation revision
`8e4a585e20bcf8a3ae47cdef51e413673b99eb2c`.

## False-positive boundary

Generated, tests, declarations, vendor/dependency/build trees, and overload
signatures are all excluded both before and after jscpd. The behaviorally
different fixture stays clean. These are not semantic guarantees: a textually
identical behaviorally different implementation can still be a lexical clone,
and any semantically duplicated but lexically different implementation remains
out of scope. The mapper also deliberately omits class methods, decorators,
namespaces, expression-bodied arrows, and unfamiliar constructs when it cannot
prove a source span/symbol relationship.

It also omits a pair whose reported start/end range crosses a symbol boundary;
same-symbol pair records remain distinct unless their actual clone occurrences
overlap.

## What generalized—and what did not

The demonstrated reusable ideas are outcome-first fixtures, source immutability
checks, copied-skill `python -I -S` closure replay, and explicit external-tool
preflight. The implementations do not generalize: Python AST handling,
TypeScript lexical mapping, npm cache provisioning, overload syntax, and all
semantic/refactor judgments stay variant/family specific.

No shared abstraction is proposed. There is no actual second consumer of the
jscpd-plus-span-mapper contract, and sharing it now would turn this one useful
pipeline into an unproven parser/executor platform.

## Translation prerequisites

Rust needs a pinned clone detector plus fixtures for free functions, impls,
macros, generated output, tests, and trait default methods; rust-analyzer is
needed before symbol claims. Go needs the equivalent package/method/build-tag
fixtures and `go/packages` before package identity claims. Java/Kotlin and C#
need compiler-aware overload/generated/partial-source fixtures. Ruby needs a
parser or runtime/language-service facts for reopened classes and metaprogrammed
methods. The JSON companion names the exact native tools, representations,
fixtures, and unresolved semantic gaps per language.

## User experience, residual risk, and next decision

The installed path is one selected skill directory, a deliberately provisioned
cache, and four host-Python commands. The main friction is explicit Node cache
provisioning, but that is preferable to an undeclared network dependency. A
small later UX improvement would be a router/catalog handoff that prints the
exact cache preflight and four commands; do not add a wrapper runtime before
measuring that friction.

Residual risks are intentional mapper false negatives, jscpd report-format
drift on a future version bump, and the Node/npm cache prerequisite. The
forward replay was fresh for this task but reused an agent with unrelated
explain-code context because no new agent slot was available; it received no
find-duplication diagnosis or expected result. Accept or extend this family
only after independent adversarial review; semantic duplication remains a
separate Compiler API family, not an extension of this lexical v1.
