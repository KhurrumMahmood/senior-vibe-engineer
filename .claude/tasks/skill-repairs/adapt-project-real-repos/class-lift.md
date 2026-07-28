# Class-lift sweep

The repaired defect classes and cheapest catalog-wide detectors were run on
2026-07-27 from the repository root.

| Defect class | Detector | Hits | Disposition |
|---|---|---:|---|
| Fixed candidate-root vocabulary omits a common layout | `rg -l 'SOURCE_ROOT_CANDIDATES' .claude/skills --glob '*.py'` | 1 | Only canonical `adapt-project`; `source/` regression covers it |
| Go package inventory assumes only `cmd/internal/pkg` | `rg -l 'GO_SOURCE_ROOT_CANDIDATES|\\("cmd", "internal", "pkg"\\)' .claude/skills --glob '*.py'` | 1 | Only canonical `adapt-project`; arbitrary-package regression covers it |
| Pytest inference relies on text rather than structured config | `rg -l '\\[tool\\.pytest|pytest.ini' .claude/skills --glob '*.py'` | 1 | Only canonical `adapt-project`; positive/malformed/dependency-only regressions cover it |
| Lexical sensitive-name output scans documentation as code risk | `rg -l 'SENSITIVE_NAME_RE|sensitive-looking name' .claude/skills --glob '*.py'` | 1 | Only canonical `adapt-project`; real Got false-positive regression covers it |
| One language inherits another language's directory policy | `rg -n 'JAVA_NON_SOURCE_PARTS\\s*=\\s*GO_NON_SOURCE_PARTS' .claude/skills --glob '*.py'` | 0 | No remaining catalog hit; Java `example` regression protects the observed leak |

No sibling batch is warranted from these detectors. The broader repeated need
for file-role classification remains ML-001; it is not converted into a new
platform by this repair.
