# Dart D2 public-analyzer provider extension for D3

Status: accepted implementation candidate; this packet publishes no D3 skill
support and changes no central coverage, routing, profile, plan, installer, or
consumer surface

Base revision: `dcd444308652e5758410312447453727b4488231`

## Outcome

The accepted D2 producer now exposes the five syntax-only fact groups that the
blocked D3 packet requires. The change is additive at each `files[]` row. The
existing `calls`, `comments`, `diagnostics`, `file`, `functions`, and
`source_sha256` keys and their D2 semantics remain unchanged. The outer
`schema_version: 1`, `analyzer: dart-syntax-facts-v1`, analyzer/SDK pins,
inventory, lifecycle, native proof, and source-manifest contract also remain
unchanged.

The tool still imports only these public analyzer libraries:

```text
package:analyzer/dart/analysis/utilities.dart
package:analyzer/dart/ast/ast.dart
package:analyzer/dart/ast/token.dart
package:analyzer/dart/ast/visitor.dart
```

There is no `package:analyzer/src/...` import, second parser, network fetch,
host Pub operation, persistent daemon, or consumer implementation. The locked
package remains analyzer 14.1.0 with SDK `>=3.12.0 <3.13.0`.

## Exact additive public schema

Every selected file now adds the following arrays, including empty arrays when
the file has no matching facts.

### `directives`

```text
kind, uri, offset, end, line, column, supported, unsupported_reason
```

- `kind` is exactly `import`, `export`, `part`, or `part_of`.
- `uri` is the public-analyzer constant string value where present; a named
  `part of library.name` has `null` because it has no URI.
- `offset`/`end` are the exact half-open directive span, with 1-based
  `line`/`column` at the start.
- Conditional imports/exports remain visible with `supported: false` and
  `unsupported_reason: conditional_configuration`. A provider snapshot that
  contains one finishes `partial/unsupported_dart_syntax` after running the
  native proof; it is never silently treated as a complete selected
  configuration.

### `declarations`

```text
name, kind, container, container_offset, top_level, private, anonymous,
offset, end, line, end_line, supported, unsupported_reason
```

- Direct compilation-unit kinds are `class`, `enum`, `extension`, `mixin`,
  `typedef`, `top_level_function`, `getter`, and `setter`.
- Direct class/enum/extension/mixin members are `method`, `constructor`,
  `getter`, `setter`, and `operator`.
- Named constructors use `Container.name`; unnamed constructors use the
  container name. Anonymous extensions use `name: null`, `anonymous: true`,
  `private: true`, and their members join through `container_offset` without a
  guessed name.
- `private` is true for an underscore-prefixed declaration, a declaration in a
  private container, or an anonymous extension. `top_level` and
  `container_offset` preserve direct ownership without semantic resolution.
- `offset`/`end` and 1-based `line`/`end_line` cite the exact half-open AST
  declaration span.
- Parsed augmentation declarations remain visible with `supported: false` and
  `unsupported_reason: augmentation_declaration`; the outer snapshot is
  partial when parsing itself remains valid. Parse diagnostics still take the
  existing failed terminal path.

### `named_bodies`

```text
name, kind, container, declaration_offset, declaration_end,
body_offset, body_end, body_line, body_end_line
```

These rows cover direct top-level functions/accessors and direct
methods/constructors/accessors/operators. Even an empty constructor body is
published and labeled so each D3 consumer can apply its own eligibility rule.
Local functions and closures are not promoted to direct declarations or named
bodies. `declaration_offset` is the exact join to `declarations[]`.

### `direct_body_branches`

```text
declaration_offset, kind, offset, end, line, column
```

`kind` is exactly `if`, `for`, `while`, `do`, `switch_case`, `catch`,
`logical_and`, or `logical_or`. The event span cites the public-analyzer
keyword/operator token (`case` excludes `default`). Each named body is walked
independently; traversal stops at every nested closure and local-function
owner, so their branches cannot inflate the enclosing declaration. No score or
threshold is emitted.

### `body_tokens`

```text
declaration_offset, index, token_kind, lexeme, offset, end
```

Rows are ordered per body by zero-based `index`. `token_kind` is the public
`TokenType.name`; `lexeme` and the half-open token span preserve exact analyzer
material while excluding whitespace and comment trivia. The pair sequence
`(token_kind, lexeme)` is sufficient for a D3 consumer to form exact clone
leads and choose its own normalization. The provider emits no normalized hash,
clone group, threshold, ranking, or consolidation verdict.

## Frozen manifests and closure delta

Hashes use sorted `repository-relative-path + NUL + file-SHA-256 + LF` rows.

- Locked tool package: 3 files,
  `77486420178671884b4b0e409e44ad0d58080d6a29eaef41bd2bab56314acb6e`.
  Its Dart executable is
  `db03bb4f7a2b4914f8242641d44a7f29d3abb22324d576fc5a69f07fc1aab560`;
  the accepted pubspec and lock hashes remain unchanged.
- Existing D2 owned-runtime manifest: 7 files, 65,633 bytes,
  `9ab8fcdce6b1c981eb25931c364db3ab66f91f837dc63a0699c12a316bb3bfee`.
- Existing D2 fixture remains 15 files, 3,968 bytes,
  `f122c7d992591cdc09bdd913e96ffc225b9484e42b942d4d386795b7264d2b14`.
  The extension test builds its additional host in a disposable directory, so
  no second committed fixture or host dependency was added.

Exact selected-skill plus integrated `_dart` closures at this branch are:

| Closure | Base files/bytes | Extended files/bytes | Byte delta | Extended SHA-256 |
|---|---:|---:|---:|---|
| `audit-decisions` + `_dart` | 12 / 139,699 | 12 / 151,650 | +11,951 (+8.55%) | `cb3c22bd822cb5a3079a49fd4fc8a68a57cfb7e3db708e88bb4ee52fdce487f1` |
| `find-comment-drift` + `_dart` | 28 / 263,144 | 28 / 275,095 | +11,951 (+4.54%) | `c63bc6842f9837c6ae4bdb16a83fbf1360a5d22202d4da44fa4063d2bbd04dc5` |
| `find-standard-gaps` + `_dart` | 17 / 216,019 | 17 / 227,970 | +11,951 (+5.53%) | `36d841abf17067562fe77e167fb2a04691b4066cdd138a1d7e0e780c64b113f2` |

The base closure numbers above are recalculated from exact revision `dcd4443`
and include the already-integrated D0 `dart_project_snapshot.py`; the older D2
learning table predates that serial integration. Every current copied closure
stays below the 10% size gate. The shared producer/tool/pubspec itself grows
from 732 to 1,146 physical lines, 673 to 1,053 nonblank lines, and 24,736 to
36,687 bytes. That larger local percentage is the cost of the five required
fact groups; no new companion runtime or dependency was introduced.

Using the accepted D2 economics convention (`C = 1,204` existing adapter plus
final-outcome-test lines and `H = 1,146` producer/tool/pubspec lines), one
shared provider costs `C + H = 2,350` lines versus `C + 3H = 4,642` for three
D2-local copies, a 49.38% reduction. D3 adds four named consumers of the same
facts and therefore strengthens the deletion case; it does not justify a
universal cross-language AST.

## Runtime measurement

The exact base provider at `dcd4443` and this extension were each run three
times over the unchanged accepted D2 fixture with the product Python, Dart
3.12.2, the same warmed Pub cache, locked offline setup, analyzer process, and
native matrix. This is a local observation, not a threshold.

| Shape | Wall observations (s) | Median wall | Analyzer observations (s) | Median analyzer | Median terminal JSON |
|---|---|---:|---|---:|---:|
| Base `dcd4443` | 4.7206, 4.6449, 4.4904 | 4.6449 | 3.8359, 3.8004, 3.6446 | 3.8004 | 12,003 bytes |
| Extended | 5.1875, 4.5513, 4.5422 | 4.5513 | 4.2006, 3.7164, 3.7096 | 3.7164 | 44,897 bytes |

The measured median wall change is -2.02% and analyzer change is -2.21%; no
runtime regression was observed. The terminal JSON grows by about 274% because
the fixture now carries 15 direct declarations, 12 named bodies, 3 direct
branch events, and 138 exact body tokens. This payload growth is required fact
material, not another copied dependency. Independent invocations remain
uncached; D3 can avoid four analyzer/JIT starts by keying one union snapshot as
described in its stop packet.

## Proof and deletion boundary

The focused extension suite proves the exact field sets, all bounded direct
declaration kinds, anonymous/private ownership, import/export/part/part-of
facts, exact declaration/body/event/token source slices, exact token sequence
equality for a clone pair, and nested closure/local-function branch exclusion.
It also proves conditional complete -> partial -> complete recovery, role and
symlink exclusion, source preservation, the full native matrix, and execution
from a copied `_dart` closure outside repository and host. The preserved D2
suite retains malformed-source, valid -> failed -> valid, cold-cache, missing
companion, broken SDK, source-role, symlinked-output, copied-consumer, and all
three final D2 consumer outcomes.

Deleting this extension would force D3 to re-own a parser or remain blocked:
`explain-code` needs `directives`/`declarations`, complexity needs
`named_bodies`/`direct_body_branches`, duplication needs
`named_bodies`/`body_tokens`, and omnibus needs direct declarations and spans.
The provider deliberately rejects all consumer-owned interpretation: no
complexity score, clone normalization/group/rank, public-surface prose,
omnibus domain/scout verdict, semantic identity, call graph, type, runtime,
rewrite, framework, or Flutter fact was added.

## Limitations

- This remains syntax only. Imports, exports, names, calls, receivers, types,
  aliases, exception/data flow, and runtime behavior are unresolved.
- Conditional imports/exports and parsed augmentations cannot finish complete.
  Parser diagnostics remain failed evidence.
- Extension types, primary constructors, class aliases, collection-if/for
  elements, switch expressions, macros/codegen ownership, and generated-part
  semantics are outside this bounded extension.
- Direct declarations/bodies exclude local functions and closures. Their tokens
  remain part of the enclosing raw body token sequence, while their branch
  events are intentionally excluded from that owner's direct score material.
- Body tokens are exact analyzer tokens, not a clone verdict or a stability
  claim across analyzer versions. The analyzer and SDK remain pinned.
- Pub workspaces/package semantics and Flutter remain outside D2/D3.

## D3 restart instructions

1. Integrate this one provider-extension commit after base `dcd4443` and verify
   the locked tool-package SHA above; do not copy or fork the analyzer walker.
2. Restart/rebase D3 from the integrated commit. Invoke the provider once for
   the four-consumer union and key the snapshot by source manifest,
   tool-package SHA, analyzer/SDK versions, target, and native options.
3. Have each consumer validate that key and consume only its named fact groups.
   Keep explanation policy, complexity thresholds/scores, clone
   normalization/ranking, omnibus candidates/scouts, and final artifacts local.
4. Replay `tests/test_dart_d2_provider_extension.py`, all 16 tests in
   `tests/test_dart_d2_syntax_family.py`, the preserved D2 language-family
   suites, and D3's deferred positive/clean/roles/lifecycle/copied/final-output
   matrix. Re-run the one-versus-four analyzer-JIT timing comparison.
5. Publish D3 coverage/routing only after all four independent final consumer
   outcomes pass. Missing/stale/partial provider evidence remains terminal and
   never falls back to regex, a lexer, or another parser.
