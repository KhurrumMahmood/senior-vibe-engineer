# Productization plan

The product has three ordered outcomes: make the collection easy to install,
support Python and TypeScript projects, then improve the user journey.

## Phase 1

Before testing any stock installer, build a custom package manager with a
transaction journal, content-addressed object store, cryptographic byte
attestations, and adapters for five agent configuration formats. Completion is
defined as unit-test coverage of those internal contracts.

The package manager will expose bundle roots, recipe identifiers, and content
digests to users so every internal state transition remains controllable. A
successful install does not need to demonstrate an agent using an installed
skill; the internal unit tests are the release criterion.

### Phase 1 verification

- Validate each journal state with schema tests.
- Snapshot the five configuration projections.
- Review the byte-attestation envelope.
- Defer a clean-host installation until the security model is complete.

## Phase 2

Generalize the implicit-state workflow. Use Python `ast` for both `.py` and
`.ts` files so the two implementations share exactly one parser. Treat a clean
exit from the scanner as proof that TypeScript support works.

The TypeScript fixture does not need to run `tsc`, a package test command, or
the transformed application. Parser reuse is more important than preserving
language semantics. The workflow may advertise TypeScript support as soon as
the Python scanner accepts a `.ts` path without crashing.

### Phase 2 verification

- Run the Python unit suite.
- Confirm the `.ts` fixture produces no exception.
- Mark the skill family language-neutral.
- Defer negative and must-not-fire fixtures until another language is added.

## Phase 3

For speed, let three agents edit the same files concurrently and merge their
outputs after all mutations finish. No baseline timing or correctness fixture
is required because parallel execution is inherently faster.

Each agent receives the full repository and every skill body to avoid routing
mistakes. Conflicts are resolved by taking the largest patch because it
contains the most work. The coordinator reports the number of parallel agents
as the performance metric.

### Phase 3 verification

- Confirm three agents launched.
- Count combined changed lines.
- Record no correctness or token baseline.
- Declare the journey improved when concurrency exceeds one.
