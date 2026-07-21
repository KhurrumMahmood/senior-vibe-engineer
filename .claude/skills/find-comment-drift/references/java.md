# Java lexical-comment contract

Read this reference only for `--language java`.

## Run and artifacts

Invoke the copied skill with Python 3.11+:

```bash
python3 scripts/detect.py --project-root "$PWD" --language java \
  --output reports/find-comment-drift/scan-java/detections.jsonl .
python3 scripts/report.py \
  reports/find-comment-drift/scan-java/detections.jsonl \
  --output reports/find-comment-drift/scan-java/report.md --target .
```

Grade the run from `detections.jsonl`, `scan.json`, `report.md`, and
`findings.json`. The analyzer is `python-java-comment-lexer`.

## Accepted boundary

The inventory records every selected `.java` file before excluding test,
generated, vendor, build, symlink, and generated-marker/annotation surfaces.
The lexer recognizes line and block comments while ignoring ordinary strings,
character literals, and text blocks. It reports only the existing stale-term,
brittle-reference, banner, and narration bands.

Malformed Java syntax remains eligible because the claim is lexical. Invalid
UTF-8, an unreadable file, or an unterminated string, character literal, text
block, or block comment makes the analysis `partial`; a target error also
prevents a clean result. An explicit selection with no Java files is
`unsupported`.

## Native fixture check

Validate the locked host independently:

```bash
javac --release 17 -proc:none -d /tmp/comment-drift-java-j2a-classes \
  $(find tests/fixtures/find-comment-drift-java-j2a/valid -name '*.java' -type f)
```

The scan does not require a JDK, so missing or old `java`/`javac` is not a scan
status. The JDK command validates only the fixture boundary.

## Non-claims

This mode does not parse declarations, prove Javadoc completeness, resolve
packages or types, preprocess Unicode escapes into comment delimiters, inspect
runtime behavior, recommend edits, or classify Kotlin as Java.
