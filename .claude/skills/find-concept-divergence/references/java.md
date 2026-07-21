# Java strict-text contract

Read this reference only for `--language java`.

## Run and artifacts

Invoke the copied skill with Python 3.11+:

```bash
python3 scripts/scan.py --project-root "$PWD" --language java \
  --output reports/find-concept-divergence/scan-java/findings.jsonl \
  --report reports/find-concept-divergence/scan-java/report.md .
```

Grade the final outcome from `findings.jsonl`, `report.md`, and `scan.json`.
The analyzer is `python-strict-text`.

## Accepted boundary

The inventory records every selected `.java` file before excluding test,
generated, vendor, build, symlink, and generated-marker/annotation surfaces.
Eligible UTF-8 text receives the existing exact, case-insensitive term-boundary
scan for avoid terms, competing-term coexistence, and superseded co-occurrence.

Malformed Java syntax remains eligible because the claim is textual, not
syntactic. Invalid UTF-8 or an unreadable file makes the run `partial`; target
errors also prevent a clean result. An explicit selection with no Java files is
`unsupported`.

## Native fixture check

Validate the locked host independently:

```bash
javac --release 17 -proc:none -d /tmp/concept-divergence-java-j2a-classes \
  $(find tests/fixtures/find-concept-divergence-java-j2a/valid -name '*.java' -type f)
```

The scan does not require a JDK, so missing or old `java`/`javac` is not a scan
status. The JDK command validates only the fixture boundary.

## Non-claims

This mode does not parse Java, distinguish identifiers from strings or
comments, resolve packages or types, infer synonymy, perform fuzzy matching,
recommend or apply renames, or classify Kotlin as Java.
