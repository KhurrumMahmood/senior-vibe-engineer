# find-duplication TypeScript v1 learning report

Revision: adversarial repair in progress on `codex/ts-duplication`, 2026-07-19 UTC

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
# 5 passed

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
as D6 evidence. A new no-context installed forward replay from the repair
commit is pending with the parent task; its handoff must preserve the installed
skill path, raw host/output paths, command transcript, report/source hashes,
and byte-identical source-tree proof.

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
