# Java filesystem discovery

Read this reference only when `/adapt-project` scans a Java host.

## Accepted boundary

- Count authored `.java` files by filesystem role using the
  `filesystem-source-inventory` analyzer.
- Exclude dependency, vendor, build, generated, test, fixture, symlinked, and
  generated-marker source.
- Recognize Maven (`pom.xml`, optional `mvnw`) and Gradle
  (`build.gradle`/`build.gradle.kts`, optional `gradlew`) markers and emit their
  conventional `test` command.
- Keep `status: complete` atomic with `adapter.yml`, `adapter.json`, `report.md`,
  and `evidence.json` present.

## Native fixture check

Compile the locked fixture separately from discovery:

```bash
javac --release 17 -proc:none -d /tmp/adapt-project-java-j2a-classes \
  $(find tests/fixtures/adapt-project-java-j2a -name '*.java' -type f)
```

Discovery itself does not invoke a JDK. A missing or old JDK therefore does not
create a discovery `partial` state; it only prevents the separate native fixture
check from running. Malformed authored Java remains an objective filesystem fact.

## Non-claims

This adapter does not parse Java, load packages, resolve the build graph,
interpret annotations, infer frameworks, type-check source, execute application
code, assess source health, or classify Kotlin as Java.
