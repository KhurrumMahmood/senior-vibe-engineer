# Java `find-complexity-hotspots` learning packet

The Java J0 detector is a read-only, syntax-only pilot. Its bundled
`detect_java_complexity.java` uses the public JDK compiler tree API through a
host JDK >= 17 discovered from `PATH`. One source-launcher process batches all
eligible `.java` files. It invokes neither Maven nor Gradle, downloads no JAR,
and imports no repository analysis runtime.

It emits `high-branch-function` only for declared methods and constructors. The
score counts direct `if`, classic/enhanced `for`, `while`, `do`, switch
statements/expressions, `catch`, ternaries, `&&`, and `||`. Nested lambdas and
class bodies do not inflate the enclosing method. The unchanged threshold
remains a `measure-first` structural lead; it establishes no type, framework,
call-graph, build, reachability, or runtime-cost fact.

The standalone Java 17 fixture proves two score-18 shapes, a clean negative,
nested-lambda exclusion, conventional/Gradle test-source, vendor, generated,
and symlink-ancestor exclusions, malformed source,
missing/old JDK, source immutability, native `javac --release 17`, and an
isolated copied skill run. Eligible `.kt`/`.kts` files are inventoried as
`kotlin_source_present`, make the final result `partial`, and are not analyzed.
This is deliberately Java support, not JVM or Kotlin support.

The product review exposed two reporting/tool-boundary lessons that should
transfer: an exclusion-only target must be visibly `partial` in the human
report, and version parsing must select the tool's actual banner line rather
than the first number because `JAVA_TOOL_OPTIONS` warnings may precede it.

What transferred from TypeScript and Go: final-artifact tests, native-tool
preflight, analyzer provenance, direct-target exclusion tests, copied closure,
source fingerprints, and explicit non-clean incomplete evidence. What did not
transfer: either earlier AST walker, build-tag behavior, receiver formatting,
or a shared parser/fact runtime. Keep the Java helper family-local until a
second Java consumer demonstrates the same compiler invocation and output
contract; the next proposal pilot may need symbol/package facts that this
syntax-only batch intentionally does not produce.
