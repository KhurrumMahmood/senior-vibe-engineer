# Ruby v1 static-map boundary

`scripts/map_ruby.py` maps one or more ordinary production `.rb` targets in a
plain, locked gem layout. The host must provide Ruby 3.3+, its bundled Prism,
Bundler 2.6+, `Gemfile`, `Gemfile.lock`, and a root gemspec. The provider is a
single stdlib-only Python file; it installs nothing and does not use a shared
parser, graph, sibling skill, repository runtime, RBS, or TypeProf.

## Command

Run from the host root. Repeat `--target` to distinguish supported and
unsupported selections in one final artifact. `--test` and `--smoke` are
optional, explicit host-owned Ruby files; they are never inferred or executed
without those flags.

```bash
python3 .agents/skills/map-subsystem/scripts/map_ruby.py \
  --name billing \
  --target lib/billing \
  --project-root "$PWD" \
  --output .engineering/docs/subsystems/billing.md \
  --evidence reports/map/billing/ruby-map.json \
  --ruby "$(command -v ruby)" \
  --bundle "$(command -v bundle)" \
  --test test/invoice_service_test.rb \
  --smoke bin/invoice-kit-smoke
```

The provider runs `ruby --disable-gems -c` separately for every eligible
production, test, and Ruby executable input. It runs only frozen `bundle
check`, with Bundler application state isolated below the report directory and
network proxies pointed at a closed local endpoint. It then uses the selected
Ruby's Prism to record syntax declarations and locations. The explicit native
test and smoke use `ruby --disable-gems -I<host>/lib`.

## Facts that the map earns

- source/configuration/signature inventory with roles and SHA-256 hashes;
- selected production `.rb` targets, including mixed-target results;
- module, class, and method syntax declarations with lexical owners;
- duplicate class/module definitions as static reopening evidence;
- literal `require`, `require_relative`, and `load` calls, with conservative
  first-party layout matches under `lib/`;
- syntactically spelled `include`, `extend`, and `prepend` calls;
- syntactic constant-reference candidates, explicitly labeled as not runtime
  identity; and
- test/executable entrypoints plus per-file syntax, frozen Bundler, test, and
  smoke evidence.

Generated, vendor, build, test, signature, and symlink roles remain visible but
do not become selected production nodes. Directory and file symlinks are never
traversed. Artifact paths are contained below `.engineering/docs/subsystems/` and
`reports/map/`, reject symlink traversal, and replace the Markdown/JSON pair
atomically. A caller can supply `--expected-source-sha256` to reject a stale
snapshot, and the provider rehashes source/configuration inputs after analysis
to detect mutation.

## Honest lifecycle

- `partial` is the successful base-Ruby outcome. Its bounded static map is
  complete, while semantic reachability remains partial.
- `unsupported` means the toolchain, plain-gem metadata, target role, or safe
  topology is outside this provider. A mixed request retains complete static
  facts for supported targets and records unsupported target rows.
- `failed` means syntax, Prism, frozen Bundler, an explicit native check,
  source-preservation, or expected-snapshot validation failed. Failed runs
  return exit 2.

Every safe terminal state replaces both final artifacts. Unsafe CLI or
artifact paths return exit 2 without touching an artifact or host source.

## Deliberate non-claims

Prism proves syntax nodes and locations, not runtime identity. Literal load
layout does not prove that a constant or method is reachable. Dynamic
`require`/`load`, `$LOAD_PATH` mutation, `autoload`, Rails/Zeitwerk, `const_get`,
`const_missing`, `send`/`public_send`, `method_missing`, eval variants,
`define_method`, refinements, runtime reopening/monkey patches, callbacks,
native extensions, and framework DSLs remain unresolved. Their presence is
reported where syntax makes it observable and never upgraded into an edge.

RBS and TypeProf are probed only as optional tool-state context. They are not
used without host-owned signatures/configuration and therefore do not broaden
the v1 claim.
