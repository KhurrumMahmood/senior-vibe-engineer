# Java v1: compiler-attributed package map

This branch maps one conventional Java package directory without changing host
source. It is deliberately not a Maven/Gradle or whole-JVM project model.

## Evidence model

- A JDK 17+ source launcher infers the source root from the selected package
  declaration and path, then attributes every eligible Java source below it
  with `JavacTask.parse()` and `analyze()`, `--release 17`, `-proc:none`, and
  an empty explicit classpath.
- Only after error-free attribution may it use `Trees.getElement` to report
  public declarations and compiler-resolved first-party normal/static imports
  or fully-qualified type references.
- The durable outputs are `.claude/docs/subsystems/<name>.md` and
  `reports/map/<name>/java-map.json`. The map includes source inventory,
  public surface, inbound/outbound first-party type edges, and explicit
  unavailable fields.

## Boundaries and terminal states

- Generated/test/vendor/build source and symlinks are excluded or rejected;
  generated files remain visible in inventory. Source and artifact paths must
  remain under the project root and must not traverse a symbolic link.
- A parser failure writes `failed` artifacts and exits 2. Unresolved Java
  attribution writes `partial` artifacts with no semantic map facts. Kotlin
  source makes otherwise attributed Java facts `partial`.
- Missing/excluded targets, no eligible source, default or mismatched package
  paths, unsafe source, old JDK, or missing compiler are explicit
  `unsupported` states when the source launcher can run.
- Maven/Gradle dependency resolution, external classpaths, module paths,
  annotation processors, Kotlin attribution, runtime dispatch, and all build
  variants are unavailable rather than guessed.

Native host verification remains separate: compile eligible production sources
with `javac --release 17 -proc:none` and run the host's normal tests.
