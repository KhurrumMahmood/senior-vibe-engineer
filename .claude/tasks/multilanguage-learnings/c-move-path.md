# C move-path learning packet

Status: accepted implementation at `e95f222`; publication pending the complete
C cohort

## Final value proved

One conventional authored C17 source file can move within one Make project
without guessing symbol identity. The standalone adapter:

- validates one current compile-database entry for the source;
- previews exact relative-include and Makefile path edits;
- binds apply to content-addressed source, plan, tool, edit, and after-tree
  evidence;
- regenerates `compile_commands.json`, runs the native Make target and exact
  smoke output, and verifies the source after-tree; and
- restores the complete pre-apply tree after a failed postflight.

The copied adapter runs without repository imports. Focused verification is
`9 passed`.

## Honest boundary

The accepted shape moves one `.c` file inside one C17/Clang/Make project. It
refuses multiple or directory moves, generated/vendor/build destinations,
symlink boundaries, macro-computed includes, excluded-role old-path residue,
missing or wrong-mode compile database facts, stale approval, old tools, and
native failure. It does not rename C symbols, move public headers, infer ABI
compatibility, resolve inactive macro variants, support arbitrary build
systems, or claim external-consumer completeness.

## Reusable lesson

C source location is not symbol identity. A useful bounded mover therefore
needs less semantic machinery than a rename: exact include lineage, build-file
path ownership, a current compile command, and native verification are enough
for one static shape. Reuse the preview/approval/rollback transaction pattern
for other languages, but keep include resolution and build regeneration local
to the selected language/build profile.
