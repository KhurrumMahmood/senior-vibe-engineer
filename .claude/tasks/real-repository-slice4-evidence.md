# Real-repository validation — slice 4

Status: pass through product revision `877045b`

## Pinned corpus and preservation

| Language | Repository | Exact revision | License |
|---|---|---|---|
| Swift | `apple/swift-argument-parser` | `2f77f2fccb6e84fecff338c37b199e33e7dfd119` | Apache-2.0 |
| C# | `dotnet-state-machine/stateless` | `588f1a1a08683b452eb7c05562d9f055693cba5d` | Apache-2.0 |

`scripts/real_repo_corpus.py prepare --slice 4` and `verify --slice 4`
accepted both detached, exact, license-bearing checkouts. All discovery and
skill artifacts stayed outside the source repositories. Final Git status was
empty for both repositories.

## Canonical discovery, routing, and execution

Both repositories passed canonical external `adapt-project --no-host-write`
discovery and its evidence gate. Explicit installed `which-skill` routing
selected `find-complexity-hotspots` from the on-demand library without
ambient-installing the task skill.

| Host | Outcome | Useful result | Time |
|---|---|---|---:|
| swift-argument-parser | `partial` / `safe-defer-incomplete` | 14 hash/span-bound Swift leads; top: `parseValue` score 25, `makeErrorMessage` 20, `parse` 17 | 4.20 s baseline replay; 4.72 s final runner replay |
| Stateless | `partial` / `safe-defer-incomplete` | five Roslyn syntax leads across 56 authored files and 384 named methods; scores 13, 11, 10, 10, 8 | 1.78 s |

Swift's package has command-plugin targets outside the clean
library/executable/test contract. The runner therefore retains lexical leads
but makes no compiler-validated whole-package claim. The final replay at
`877045b` uses the contract verdict and maintains a `latest` link for the valid
partial artifact.

Stateless does not contain the fixture-only `csharp-project.json`. Revision
`50e1359` added the narrow real-repository path: Roslyn parses authored sources
without compiling the host, records the missing build-membership/native-test
authority, emits useful external artifacts, and returns zero for the valid
partial result.

## Manual validation

All five C# findings were checked against the exact source spans and analyzer's
frozen branch-node definition:

- `StateMachine.Async.cs:237` `ProcessHandler` — 9 switch sections + 4 `if` = 13;
- `Reflection/StateInfo.cs:38` `AddRelationships` — 7 `foreach` + 4 `if` = 11;
- `Graph/StateGraph.cs:136` `AddTransitions` — 6 `foreach` + 4 `if` = 10;
- `StateMachine.cs:392` `InternalFireOne` — 7 switch sections + 3 `if` = 10;
- `StateRepresentation.Async.cs:204` `TryFindLocalHandlerAsync` — 2 `if`,
  1 `foreach`, 1 ternary, 1 `&&`, and 3 `??` = 8.

The top Swift declarations, spans, and source hashes were independently
checked. Strict recursive `swift-format` and direct `swiftc -frontend -parse`
checks for the top three source files passed. Neither result claims runtime
cost or refactor authority.

## Repairs and verification

- C# now supports external `--output-dir --no-host-write`, retains source-only
  facts when its product manifest is absent, and renders useful report leads.
- Swift partial results now use the declared verdict vocabulary and maintain
  `latest`.
- The generated on-demand closure now names the Swift lexical provider and
  guide that the runner actually requires.
- The pinned public corpus now contains every advertised language.

Verification:

- C# family, conformance, and coverage: `26 passed in 51.68s`.
- Exact Swift partial regression and final real-repository replay: pass.
- Swift family replay reached `39 passed` before the unrelated remainder was
  deliberately interrupted after 17:49; the affected regression had already
  passed and the remaining native copied-closure families were outside this
  change.
- Committed installed-router, corpus, and generated-matrix replay: `15 passed
  in 7.68s`.
- Corpus harness: `11 passed`; matrix reports 76 current skills.
- Ruff, generated-matrix freshness, diff checks, and every commit hook pass.

Minor C# artifact-size and convenience issues are tracked in the language
backlog; they do not block a useful external report or source preservation.
