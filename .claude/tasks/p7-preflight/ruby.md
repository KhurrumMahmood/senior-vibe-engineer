# Ruby P7 preflight

Captured 2026-07-22 on macOS 26.5.2 arm64. This was a read-only preflight:
no network access, install/update, product implementation, worktree, commit, or
push was attempted. Commands using Python used
`<repo>/.venv/bin/python`.

## Recommendation

**Defer Ruby product implementation until the owner supplies or approves a
healthy modern Ruby toolchain.** The usable PATH runtime is Apple Ruby 2.6.10,
whose parser rejects representative modern syntax. A private rbenv Ruby 3.3.0
and bundled Prism/RBS/TypeProf files exist, but the runtime, its package tools,
rbenv itself, and the rbenv shim all timed out after three seconds with no
output. Treat that installation as present-but-unusable, not as toolchain
readiness.

Once a healthy toolchain is available, pilot exactly three outcomes before any
broad pass:

1. **Lexical — `find-comment-drift`:** Prism comment/source spans plus `ruby -c`;
   final detections/report, malformed and excluded-role cases, copied closure,
   fingerprints, and same-destination lifecycle transitions.
2. **Semantic/project — `map-subsystem`:** Bundler/load-path metadata and Prism
   syntax for explicit `require`/`require_relative` edges. The expected base
   outcome is **partial**: dynamic dispatch and constant resolution remain
   unsupported unless the representative host already owns and configures
   Sorbet or Steep.
3. **Mutation — `move-path`:** one leaf `lib/` path/module move with only
   statically proved constant and `require_relative` edits; verify every file
   with `ruby -c`, run the locked Minitest smoke, prove rollback, and refuse
   dynamic require/autoload/reflection and Rails/Zeitwerk cases.

A reasonable pilot floor is a healthy Ruby 3.3+ because Prism ships with that
runtime line; the final minimum must be checked against upstream support policy
and the representative host's own `required_ruby_version` when implementation
starts. Do not silently fall back to Ruby 2.6 Ripper for modern projects.

## Exact local evidence

### Platform and selected PATH tools

```text
$ uname -m
arm64
$ sw_vers
ProductName: macOS
ProductVersion: 26.5.2
BuildVersion: 25F84
$ which -a ruby gem bundle bundler irb rake rails rubocop standardrb steep srb tc typeprof rbs solargraph prism
/usr/bin/ruby
<user-home>/.rbenv/shims/ruby
/usr/bin/gem
<user-home>/.rbenv/shims/gem
/usr/bin/bundle
<user-home>/.rbenv/shims/bundle
/usr/bin/bundler
<user-home>/.rbenv/shims/bundler
/usr/bin/irb
<user-home>/.rbenv/shims/irb
/usr/bin/rake
<user-home>/.rbenv/shims/rake
/usr/bin/rails
<user-home>/.rbenv/shims/typeprof
<user-home>/.rbenv/shims/rbs
```

No `rubocop`, `standardrb`, `steep`, `srb`, `tc`, `solargraph`, or `prism`
executable was found. This checkout has no `.ruby-version`, `.tool-versions`,
`Gemfile`, `Gemfile.lock`, `gems.rb`, `gems.locked`, `Rakefile`, or `config.ru`.

```text
$ ruby -v
ruby 2.6.10p210 (2022-04-12 revision 67958) [universal.arm64e-darwin25]
$ gem --version
3.0.3.1
$ bundle --version
Bundler version 1.17.2
$ irb --version
irb 1.0.0 (2018-12-18)
$ rake --version
rake, version 12.3.3
```

RubyGems reports `/Library/Ruby/Gems/2.6.0` as its installation directory,
`<user-home>/.gem/ruby/2.6.0` as the user directory, and
`https://rubygems.org/` as the configured remote source. The local gem census
contains only the old system/default set plus a few unrelated gems; notably it
does not contain Prism, parser, RuboCop, RBS, TypeProf, Sorbet, Steep, or
Solargraph. Direct `require` probes returned `LoadError` for all of those.

### Parser and syntax behavior

```text
$ ruby --disable-gems -e 'require "ripper"; puts [Ripper, Ripper.respond_to?(:sexp), Ripper.respond_to?(:lex)].inspect'
[Ripper, true, true]
$ printf '%s\n' 'class A' '  def x' '    1' '  end' 'end' | ruby -c
Syntax OK
$ printf '%s\n' 'def broken(' | ruby -c
-:1: syntax error, unexpected end-of-input, expecting ')'
```

`Ripper.sexp("def broken(")` returned `nil`, while `Ripper.lex` still returned
tokens. More importantly, the Ruby 2.6 parser rejected pattern matching,
endless method definitions, argument forwarding, and rightward assignment:

```text
$ printf '%s\n' 'case x; in [a, *]; a; end' | ruby -c
syntax error, unexpected in, expecting when
$ printf '%s\n' 'def answer = 42' | ruby -c
syntax error, unexpected '=', expecting ';' or '\n'
$ printf '%s\n' 'def f(...); g(...); end' | ruby -c
syntax error, unexpected ..., expecting ')'
$ printf '%s\n' 'value => x' | ruby -c
syntax error, unexpected =>, expecting end-of-input
```

Therefore Ripper is useful only as evidence that a lexical fallback exists; it
cannot establish support for contemporary Ruby syntax on this machine.

### Installed-but-unhealthy rbenv tree

`<user-home>/.rbenv/versions/3.3.0/bin/ruby` is an arm64 Mach-O and
the rbenv version file says `3.3.0`. Its gemspec tree contains Prism 0.19.0,
RBS 3.4.0, and TypeProf 0.21.9. Presence did not equal usability:

```text
$ <explicit product .venv Python timeout harness> <user-home>/.rbenv/versions/3.3.0/bin/ruby -v
TIMEOUT after 3s; stdout=b''; stderr=b''
$ <same harness> <user-home>/.rbenv/versions/3.3.0/bin/gem --version
TIMEOUT after 3s; stdout=b''; stderr=b''
$ <same harness> <user-home>/.rbenv/versions/3.3.0/bin/bundle --version
TIMEOUT after 3s; stdout=b''; stderr=b''
$ <same harness> /opt/homebrew/bin/rbenv root
TIMEOUT after 3s; stdout=b''; stderr=b''
$ <same harness> <user-home>/.rbenv/shims/ruby -v
TIMEOUT after 3s; stdout=b''; stderr=b''
```

The product doctor must preserve the distinction between file presence,
available-and-supported, too old, and present-but-unusable/time-out.

### Offline and framework boundaries

`ruby -c` and stdlib Ripper are offline. Bundler 1.17.2 help documents
`bundle install --local` and `bundle lock --local` as avoiding remote fetches.
With `BUNDLE_DISABLE_VERSION_CHECK=true`, `BUNDLE_FROZEN=true`, and an invalid
`BUNDLE_PATH`, `bundle check` and `bundle list` failed locally with `Could not
locate Gemfile or .bundle/ directory`; no network was needed. Routed execution
should use only `bundle check`/`bundle exec` against an already locked,
satisfied host and must never install or update gems. RubyGems has a remote
source configured, so `gem install`/`gem update` are outside the product path.

`/usr/bin/rails --version` exits **0** while printing `Rails is not currently
installed on this system`; command existence and exit zero are therefore not a
valid Rails capability probe. Rails is a supplementary profile only. Zeitwerk
autoloading, ActiveSupport constantization, callbacks/metaprogramming,
ActiveRecord associations/scopes, engines, migrations/schema, and ERB are
framework facts and must not leak into a base Ruby claim.

## Existing profile/doctor/inventory seams and gaps

- The strict profile can express `.rb` and other suffixes, project markers,
  Ruby/Bundler executable resolution, fact tiers, minimum versions, `ruby -c`,
  explicit limits, and terminal outcomes. The doctor already prefers declared
  project-local executables, times out version commands, and never installs.
- The doctor resolves literal repo executables and then PATH. It does not
  understand `.ruby-version` managers, inspect a library capability such as
  `require "prism"`, or distinguish required from optional tools when computing
  aggregate status. A Ruby lane should first use the current contract and keep
  the Prism require-probe provider-local; shared doctor changes require root
  review and evidence from another consumer.
- Source inventory currently labels `.rb` as unsupported. A Ruby profile would
  enable it, but Ruby project code also lives in `.rake`, `.gemspec`, `.ru`, and
  extensionless `Gemfile`/`Rakefile`. The current suffix-only inventory cannot
  include extensionless DSL files. `spec/` is not currently a test-directory
  convention, and Rails `db/migrate/` does not match the generic `migrations/`
  rule. The first fixture should use `.rb` plus `test/`; root should decide
  whether later shared inventory support is justified.
- `ruby -c` effectively needs one source per invocation; batching must preserve
  per-file status rather than imply that one command validated an entire list.

## Representative fixture

Use a dependency-minimal, locked plain-Ruby Bundler host: `Gemfile` and
`Gemfile.lock`; `lib/billing/invoice_service.rb`; explicit
`require_relative` consumers; `test/` Minitest smoke; generated, vendor, build,
and malformed Ruby sentinels; and modern syntax sentinels. Freeze source and
closure manifests. Native commands are per-file `ruby -c`, `bundle check`, and
`bundle exec ruby -Itest <test-file>` with frozen/version-check-disabled
Bundler settings. Include dynamic `require`, `const_get`, `send`, monkey patch,
and metaprogramming examples as must-not-overclaim cases. Do not make the first
fixture Rails-dependent.

Use version-matched official Ruby syntax/API documentation, Prism
documentation, and Bundler/RubyGems manuals as language/tool authorities.
Treat the host's RuboCop configuration and RuboCop docs as the idiom/style
authority when present; treat RBS+Steep or Sorbet configuration as optional
project-owned semantic authorities. Rails Guides and Zeitwerk documentation
apply only to an explicitly selected Rails profile. These sources were named,
not fetched, because this preflight prohibited network access.

## Initial 22-skill forecast

No Ruby skill has reached a final artifact, so the only honest **current**
disposition for every row is `ruby-unsupported (preflight)`. “Candidate” below
is a work-order forecast, not a published support claim.

| Skill | Forecast and rationale |
|---|---|
| `find-comment-drift` | First lexical pilot; Prism spans make it plausible after a healthy runtime. |
| `map-subsystem` | First semantic/project pilot; expect partial explicit-load edges unless a host analyzer resolves more. |
| `move-path` | First mutation pilot; only a bounded explicit-load/module leaf move is plausible. |
| `adapt-project` | Near-term lexical/filesystem candidate after `.rb` inventory and final adapter artifacts are proved. |
| `find-complexity-hotspots` | Near-term syntax candidate; needs Prism branch/method facts and a final report fixture. |
| `find-concept-divergence` | Near-term lexical candidate; dynamic identities limit findings to declared names/usages. |
| `find-duplication` | Near-term token/syntax candidate; Ruby normalization and heredoc/metaprogramming boundaries need fixtures. |
| `find-folder-topology-drift` | Near-term filesystem candidate, but Bundler layout is not Rails/Zeitwerk topology. |
| `find-omnibus` | Near-term syntax candidate only; syntax size does not prove runtime responsibility. |
| `audit-decisions` | Deferred until Ruby comment/declaration evidence reaches the skill's final audit artifact. |
| `explain-code` | Analyzer-gated; Prism structure alone cannot explain dynamic call targets or runtime reopening. |
| `find-dormant` | Analyzer-gated and likely partial even then because reflection/autoload can hide references. |
| `find-implicit-state` | Analyzer-gated; globals, class variables, constants, callbacks, and monkey patches need Ruby-specific semantics. |
| `find-incomplete-sweep` | Analyzer-gated; requires resolved call targets/trajectory evidence unavailable in base Ruby. |
| `find-semantic-duplication` | Analyzer-gated; no reliable project-owned semantic index is currently available. |
| `find-standard-gaps` | Host-tool-gated; orchestrate an existing RuboCop/Steep/Sorbet setup rather than reimplementing it. |
| `propose-boundary` | Analyzer-gated; explicit requires alone are not a resolved dependency graph. |
| `rename-concept` | Analyzer-gated and high risk because reflection, symbols, strings, DSLs, and runtime reopening evade syntax-only rename. |
| `extract-enum` | Deferred proposal; Ruby has no single native enum model and compatibility/type evidence is missing. |
| `prevent-regression` | Deferred until an accepted Ruby producer artifact can drive a Ruby-native guard and verification. |
| `propose-folder-reorganization` | Deferred until base Ruby layout is separated from Bundler, Zeitwerk, Rails, gem, and monorepo conventions. |
| `unify-shadows` | Deferred until a producer proves identities and compatibility across reopenings, aliases, and dynamic delegation. |

## Bounded resumable worker packet

Do not open a lane until a healthy owner-approved Ruby is executable. Then:

- Record base SHA, macOS arm64, exact Ruby/Bundler paths and versions, the
  explicit product Python path, fixture manifest, offline environment, and
  tool health before branching.
- Spine owns only a Ruby-named profile, Ruby fixture, focused profile/doctor/
  inventory tests, frozen three-pilot contracts, and a Ruby coverage draft.
  It must prove project-local precedence, old/missing/time-out outcomes, modern
  syntax, per-file lint, locked offline Bundler behavior, roles, and all 22
  initial unsupported dispositions.
- Open three disjoint workers from that spine: lexical
  `find-comment-drift`, project/semantic `map-subsystem`, and serial mutation
  `move-path`. Each owns only Ruby-named provider/helper files, its fixture
  projection, focused tests, and a learning fragment.
- Stop rather than weaken claims if Ruby/Prism is unhealthy or too old, the
  lock is unsatisfied offline, the task would install gems, Rails behavior is
  required, dynamic targets cannot be resolved, source roles escape the
  manifest, or mutation cannot prove rollback and native success.
- Root alone integrates shared inventory/doctor changes, skill dispatch/prose,
  router and matrix publication, durable docs, and the execution ledger. Run
  focused final-outcome tests, existing-language regression, exact external-
  library replay, native checks, and adversarial review before any Ruby claim.
