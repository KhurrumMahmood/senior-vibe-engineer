# Ruby P7 spine learning packet

This spine proves a plain-Ruby foundation without publishing a support claim.
Ruby 3.4.1, RubyGems 3.6.2, and Bundler 2.6.2 resolve through the existing
user-local shims and pass direct probes. Prism 1.2.0 is bundled with Ruby and
loads under `--disable-gems`. No package or dependency was installed or
updated, no network was used, and product Python commands used
`/Users/<user>/Projects/engineering-skills-product/.venv/bin/python` 3.11.10.

The representative copied host is a dependency-free gem layout. Its committed
Gemfile selects a local gemspec, its lock is already satisfied, and its Rakefile
pins the Rake DSL boundary without making Rake part of the native test path.
Every selected `.rb` file is checked in a separate `ruby -c` invocation. Direct
Ruby runs the dependency-free test and smoke executable, while Bundler is used
only for frozen `bundle check` with version checks disabled and application
configuration outside the host. Malformed Ruby and Gemfile inputs fail, and
the copied host remains byte-for-byte unchanged.

The base inventory owns only `.rb`. It correctly classifies first-party source,
test, generated, vendor, build, and symlink boundaries. It intentionally does
not claim that extensionless Gemfile/Rakefile inputs or wildcard `*.gemspec`,
`*.rake`, and `*.ru` DSL files are ordinary Ruby source. The shared inventory
currently needs filename/glob role support to include those inputs honestly;
root should add that only with another consumer rather than teaching `.rb`
semantics to a generic walker.

Prism is a default gem and Ripper is stdlib; both can serve lexical and syntax
facts such as comments, tokens, nodes, errors, and source locations. RBS 3.8.0
and TypeProf 0.30.1 are present non-default gems in the observed toolchain, but
they are optional and availability alone does not establish project semantics.
Steep, Sorbet, RuboCop, Standard Ruby, and Solargraph are optional
project-owned tools and must use the audited project's locked versions and
configuration. Rails, Zeitwerk, ActiveSupport, and ActiveRecord belong to
separate framework profiles.

Ruby's dynamic boundary is material. Non-literal `require`, load-path changes,
autoload, `const_get`, `send`/`public_send`, `method_missing`, eval variants,
`define_method`, refinements, monkey patches, class/module reopening, callbacks,
and runtime DSLs defeat syntax-only identity and reachability claims. The
fixture keeps representative sentinels so later cohorts must return partial or
refuse rather than manufacture resolved facts.

The frozen cohort order is lexical `find-comment-drift`, partial-by-default
semantic `map-subsystem`, then serial `move-path` only after accepted static
lineage. Each contract names a positive final outcome, must-not-fire/refusal
cases, copied-layout and native obligations, source fingerprints, stale-output
transitions, and mutation rollback where applicable. The fixture is 2,811
bytes; the exercised profile/doctor/inventory runtime closure is 44,151 bytes.

No skill final artifact or mutation has run. Exactly 22 language-level rows are
`ruby-pending-implementation`. Missing optional semantics and unfinished work
are not evidence for `ruby-unsupported`.
