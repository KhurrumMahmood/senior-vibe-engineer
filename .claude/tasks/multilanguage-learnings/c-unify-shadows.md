# C `unify-shadows` learning packet

## Outcome

The C consumer now turns one accepted `c-semantic-duplication-v1` static
review lead into exactly `proposal.md`, `evidence.json`, and `scope.json`.
The artifact remains read-only and explicitly does not establish behavioral
equivalence. `keep_separate_document_why` is a complete useful result; the
other three shapes remain proposals requiring separate source-mutation
approval.

## Accepted evidence boundary

The consumer does not launch Clang or repeat semantic detection. It verifies:

- the current analysis bytes and self-hashed `c-semantic-facts-v1` pack;
- the complete current C17 compile database and source manifest;
- one deterministic `C-SD-NNNN` lead and its canonical hash;
- exact external definitions and every accepted direct-caller citation,
  including the source-file SHA-256 for each;
- a self-hashed human acceptance selecting one of the four proposal shapes;
- exact host-owned Make, native-test, executable-smoke, and stdout
  obligations.

Pending/missing authority is `partial`; tampered or stale accepted evidence is
`failed`. Either path atomically replaces any earlier ready bundle with a
three-artifact refusal, preventing stale success from surviving.

## C-specific stop boundary

The proposal stops on ABI or exported-symbol drift, unknown external
consumers/build variants/function pointers, uncharacterized side effects, or
possible undefined behavior. The accepted direct-call graph is not promoted
to whole-program authority. Native Make and exact smoke success are necessary
implementation checks, not proof that those boundaries are absent.

## Reuse and closure decision

The implementation reuses the accepted Ruby/Dart three-artifact and refusal
shape and the Rust exact citation/hash discipline. Validation stays in one
C-local stdlib-only script because there is one consumer and no second use
that would justify shared proposal infrastructure. The copied replay installs
only `unify-shadows/scripts/propose_c.py`; it imports no repository helper,
runs no analyzer, and preserves source bytes.

## Replay

```bash
<product-root>/.venv/bin/python \
  -m pytest -q tests/test_c_unify_shadows_proposal.py
<product-root>/.venv/bin/python \
  -m ruff check \
  .claude/skills/unify-shadows/scripts/propose_c.py \
  tests/test_c_unify_shadows_proposal.py
```

The focused replay covers all four shapes, exact source/caller hashes and
citations, actual analysis-byte tampering, stale source, pending and missing
authority, ready/refusal replacement, copied standalone closure, source
preservation, Make test, and exact executable smoke.
