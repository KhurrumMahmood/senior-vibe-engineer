# Java filename-topology contract

Read this reference only when `--java-root` is selected.

## Run and artifacts

Invoke the copied skill with Python 3.11+:

```bash
python3 scripts/detect.py --project-root "$PWD" --java-root src/main/java \
  --output reports/find-folder-topology-drift/scan-java/detections.jsonl
python3 scripts/report.py \
  --detections reports/find-folder-topology-drift/scan-java/detections.jsonl \
  --output-md reports/find-folder-topology-drift/scan-java/report.md \
  --output-json reports/find-folder-topology-drift/scan-java/findings.json \
  --target src/main/java --language java
```

Grade the final outcome from `detections.jsonl`, `scan.json`, `report.md`, and
`findings.json`. The analyzer is `python-filesystem-names`.
A Java rerun clears these same-run artifacts before validating its selected
roots, so a failed or partial rerun cannot leave a prior complete report as the
apparent outcome.

## Accepted boundary

Each explicit root must be a real directory inside `--project-root`, not a
symlink. Inventory records every selected `.java` file before excluding test,
generated, vendor, build, symlink, declared-exclude, and
generated-marker/annotation surfaces.

Within one directory, eligible filenames are grouped by their leading
CamelCase domain token. `BillingParser.java`, `BillingTypes.java`, and
`BillingValidator.java` therefore emit one `billing` `flat_prefix_cluster` at
the default threshold of three. `package-info.java`, `module-info.java`, a
single prefix, mixed prefixes, and below-threshold groups stay clean.

Malformed Java bodies remain eligible because the claim is filename-only.
Invalid UTF-8 or an unreadable file makes the run `partial`; a selection with
no Java files is `unsupported`. Invalid or symlinked roots exit with
`scan-blocked` behavior before artifacts are presented as complete.

## Native fixture check

Validate the locked host independently:

```bash
javac --release 17 -proc:none -d /tmp/folder-topology-java-j2a-classes \
  $(find tests/fixtures/find-folder-topology-java-j2a/valid -name '*.java' -type f)
```

The scan does not require a JDK, so missing or old `java`/`javac` is not a scan
status. The JDK command validates only the fixture boundary.

## Non-claims

This mode does not parse Java, read package declarations, resolve imports or
types, inspect Maven/Gradle, prove cohesion, recommend a move, or classify
Kotlin as Java.
