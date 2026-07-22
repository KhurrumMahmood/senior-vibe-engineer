# Java `move-path` learning packet

Java v1 moves exactly one leaf package directory beneath the same inferred
source root. Its JDK compiler helper emits exact spans for moved package
declarations, imports resolving into that package, and fully-qualified type
references resolving into it. Plain strings, comments, reflection names,
service descriptors, and framework registries are not guessed: an old package
identity outside an attributed span makes the run partial and blocks apply.

The transaction compiles every eligible standalone source with
`javac --release 17 -proc:none` before mutation, applies the virtual after-tree,
compiles again, and compares the exact source bytes. A forced post-move failure
restores the old directory and external callers. Generated, malformed,
non-leaf, symlinked, mixed/default/path-mismatched, invalid-destination, and
source-root-changing shapes never become successful moves.

The durable transfer from Go is the transaction—reviewed single-package scope,
native preflight/postflight, exact diff, and rollback—not Go's import model.
The durable transfer from TypeScript/JavaScript is explicit resolver provenance
and refusal of dynamic identities, not their module-resolution rules.

This added a 443-line Java helper and roughly 340 Java-mode/gate lines to the
existing mover by closeout. That cost
is visible evidence against blindly converting all mutation skills. Before a
second Java mutation family, test whether small shared launcher/plumbing can be
removed while leaving semantic span ownership and rollback in `move-path`.
