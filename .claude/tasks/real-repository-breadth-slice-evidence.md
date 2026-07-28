# Specialized-language real-repository journey evidence

Status: pass at product revision `62559f1659ae9b122deb93a6367284de1c8b425f`

## Pinned corpus

| Language | Repository | Exact revision | License |
|---|---|---|---|
| PHP | `slimphp/Slim` | `80900fb39cafce3ae53b18a2c4f642a122f03095` | MIT |
| Ruby | `sinatra/sinatra` | `cb22afd7902b566b6eaba6c4ea89739494a65d12` | MIT |
| Rust | `BurntSushi/ripgrep` | `f9c05a949d1a0dc8e16dee28ca9605d38611faeb` | Unlicense OR MIT |
| Dart | `dart-lang/path` | `7e3d5d87220133ad9cc99f82e85a826011a62859` | BSD-3-Clause |

`scripts/real_repo_corpus.py prepare --slice 2` produced exact detached
checkouts. The subsequent `verify --slice 2` accepted all four repositories
with their declared license files and no dirty or revision-mismatched host.

## Installed boundary

A disposable PHP host proved the full router lifecycle using stock
`skills@1.5.19`:

- exactly `which-cleanup`, `which-shape`, and `which-skill` were installed;
- an external project-scoped library was bootstrapped at the exact revision
  above, and installed router bytes matched that library;
- the explicit schema `1 -> 3` migration plan contained only its two expected
  manifest updates, after which status reported compatibility `match`;
- router `--help` returned documentation without initiating work;
- for every language, `which-skill` selected `find-complexity-hotspots` and
  returned an `on_demand_library` handoff with the correct supported capability;
- for every missing-context host, `which-shape` selected project intake and
  handed off first to the external `adapt-project` closure; and
- the selected skills were never ambient-installed. Explicit uninstall removed
  all three routers and `skills list --json` returned `[]`.

## Canonical project discovery

All artifacts were written outside the pinned repositories with
`--no-host-write`.

| Host | Discovered stack | Authored source evidence | Declared commands | Time |
|---|---|---|---|---:|
| Slim | PHP / Composer | `Slim`: 72 PHP files | `composer test`; validate; install | 0.11 s |
| Sinatra | Ruby / Bundler | `lib`: 7 Ruby files; two real bundled subprojects retained; examples excluded | `bundle exec rake test`; install | 0.14 s |
| ripgrep | Rust / Cargo | `crates`: 86 Rust files; fuzz/package support roots disclosed | locked test, Clippy, and fetch | 0.15 s |
| path | Dart / Pub | `lib`: 13 Dart files; benchmark excluded | `dart test`; analyze; pub get | 0.08 s |

Every adapter reached terminal `complete`, named the expected language and
package manager, and produced `adapter.json`, `adapter.yml`, `evidence.json`,
and a human report through the same canonical entrypoint.

## Routed final outcomes

| Host | Final outcome | Source-grounded result | Time | Artifact bytes |
|---|---|---|---:|---:|
| Slim/PHP | `complete`, `measure-first` | 2 high-branch functions; both spans inspected | 5.73 s | 925,742 |
| Sinatra/Ruby | `partial`, `safe-defer-incomplete` | 9 Prism method leads retained; first 5 declarations inspected | 1.20 s | 962,747 |
| ripgrep/Rust | `partial`, `safe-defer-incomplete` | 51 syntax leads retained; first 5 declarations inspected | 3.07 s | 6,172,216 |
| path/Dart | `partial`, `incomplete` | 4 frozen, hash-bound method leads; all 4 declarations inspected | 5.58 s | 1,902,807 |

The PHP report names `MiddlewareDispatcher::handle` (score 17) and
`ResponseEmitter::emitBody` (score 8). Ruby's leading methods are
`handle_exception!` (22), `render` (19), and `process_route` (13). Rust's
leading functions are `from_low_args` (28), `matched_ignore` (26), and
`indexing_unsupported_flag` (19). Dart's four leads score 35, 22, 20, and 19.
All sampled files exist, every reported span contains the named declaration,
and no duplicate or materially misleading sampled finding was found.

The partial results are intentionally not clean conclusions:

- Sinatra has no committed `Gemfile.lock`; Prism syntax facts remain useful,
  but native project completeness is not claimed.
- ripgrep's locked offline Cargo check could not resolve `aho-corasick` from
  the existing local cache; syntax leads remain visible and the report names
  `cargo_dependency_cache_unavailable`.
- Dart's public-analyzer native contract was unavailable without prepared
  package state; the accepted hash-bound syntax snapshot remains visible and
  the report names `native_contract_unavailable`.

No tool fetched dependencies or used the network during these selected-skill
runs.

## Source preservation

After both discovery and selected-skill execution, `git status --porcelain`
was empty, corpus verification still matched every pinned revision, and the
sorted Git-index digests were:

| Host | Tracked-object digest |
|---|---|
| Slim | `efaac1dd6491f1cf9da8ca154329de39aae113769b5d92726a1c0f169ba9c941` |
| Sinatra | `a65f1c7ca546054def0c4765cc1566690832e0236360413695c65404d42db447` |
| ripgrep | `befe0c781d52d6b9e9ef2af1f699be662673f15308a8c80b8e129908561059af` |
| path | `93e46ee5e39a36f3ee0beea341d1d1439c8471586268113c84e3126591777bdf` |

## Regression and release evidence

- Focused corpus manifest suite: `11 passed`.
- Ruby, Rust, and Dart regression families plus breadth discovery and the
  affected router/release boundaries: `204 passed in 397.51s`.
- Skill conformance: `4 passed`.
- Commit hooks passed for both repair commits.

## Remaining product friction

- Ruby's native runner contract is currently too restrictive for some real
  gem test commands; this is tracked separately rather than hidden by syntax
  success.
- Rust's read-only policy will honestly return partial until the selected
  locked dependencies already exist locally or the user approves setup.
- Dart needs prepared package state for the native analyzer contract; the
  syntax fallback is useful but not semantic completion.
- Specialized task wrappers still have language-specific command shapes.
  The canonical `adapt-project` path and the external-output hotspot paths
  prove a reusable pattern, but do not yet close uniform dispatch for every
  advertised language.
