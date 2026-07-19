# Quality perimeter — quality-maintenance-host

Suspect detectors inventoried: 1; cells: 2; min LOC for gap-flagging: 10

| root | language | LOC | files | covered by |
|---|---|---:|---:|---|
| src | typescript | 31 | 3 | **NONE** |

## PERIMETER GAPS (1)

- `src` / typescript: 31 LOC across 3 files with **no covering detector**

## Classification

`src` is product TypeScript, not generated data. The installed
`find-perimeter-gaps` skill declares `language: any`; that declares a portable
implementation but does not claim a scanner surface. Do not claim coverage
from language: any. The useful next decision is whether an existing structural
detector earns a TypeScript adapter, not whether this perimeter report should
hide the gap.
