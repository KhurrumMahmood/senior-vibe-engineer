# Initial real-repository journey evidence

Status: pass at product revision `1179fa135008d289d8f23065433c2db9ebb5cdca`

## Installed boundary

The Got disposable clone was the lifecycle host:

- stock `skills@1.5.19` installed exactly `which-shape`, `which-skill`, and
  `which-cleanup`; `skills list --json` showed exactly those three;
- the local committed revision was cloned into an external project-scoped
  library and its pinned runtime was created in 24.25 seconds;
- initial status honestly reported schema `1 -> 3`; the explicit migration
  plan contained only two manifest updates, apply completed, and status then
  reported router/library/schema compatibility `match`;
- `which-shape` selected `health-audit` with medium confidence for all four
  natural prompts;
- `which-skill` selected `find-complexity-hotspots`, returned the exact
  on-demand skill root/runtime, and reported TypeScript, Go, and Java capability
  evidence without ambiently installing the selected skill; and
- after execution, explicit uninstall removed the three routers and
  `skills list --json` returned `[]`.

The same installed router copies routed against the other three disposable
hosts with each host passed as `--project-root`. All hosts used the same exact
external-library revision.

## Final selected-skill outcomes

| Host | Routed outcome | Sample result | Time | Artifacts |
|---|---|---|---:|---:|
| Requests/Python | `complete`, 24 findings: 8 high-branch, 9 membership-in-loop, 6 nested-loop, 1 repeated-scan | the first five nested-loop locations were inspected; all five contain the named enclosing scope and actual nested loops | 0.18 s | 44 KiB |
| Got/TypeScript | `complete`, 4 high-branch functions | all four symbols begin and end at the reported lines with exact 501/346/95/78-line spans | 4.85 s | 12 KiB |
| Chi/Go | `partial`, 1 high-branch function | `(*node).findRoute` is the reported 144-line branching traversal; `middleware/profiler.go` is correctly disclosed as build-constraint ambiguous | 6.09 s | 16 KiB |
| Spring PetClinic/Java | `complete`, 0 findings | the report states the JDK analyzer/toolchain and 30 analyzed, 0 excluded, 0 unsupported files | 1.33 s | 8 KiB |

Every final directory contains `detections.jsonl`, `findings.json`, and
`report.md`; every referenced path exists. Clean results and partial analysis
are explicit rather than inferred from exit zero.

## Source preservation

Tracked-file digests for each disposable journey clone exactly match its
pristine pinned corpus checkout, and `git status --porcelain
--untracked-files=no` is empty:

| Host | Tracked-byte digest |
|---|---|
| Requests | `1566d7b8146fb7f27e4558f7364fdfeed79fa5c1f5b1374125da790880dc4f29` |
| Got | `5617e130fe383879c689a9062e5a7a61483ae635ffa2bb7400e2408c20d4e2f6` |
| Chi | `f89b76949c025a5615c5b6dc4dc737a0207c3198264f96154109e4c92bfd6037` |
| Spring PetClinic | `c211e6c3b8539fd4de82fc9d341e087a28f6a586329a54019aaf35b921291f56` |

Expected untracked journey state includes router copies before uninstall,
toolkit-owned `.engineering/` state, reports, and Got's analyzer dependency.
No production/tracked source byte changed.

## Friction and limitations

- Got did not carry `node_modules`, so the TypeScript analyzer correctly
  refused to pretend it ran. A direct `npm install --ignore-scripts` was
  stopped when the repository agent policy required user approval. The
  disposable host instead received an untracked link to an already-local
  TypeScript `5.9.3`, exactly matching Got's declared `^5.9.3`. A normal user
  journey must approve/run the adapter's setup command or already have project
  dependencies installed.
- Go took 6.09 seconds and returned `partial` because a real build-tagged file
  cannot be interpreted without a selected build context. This is the intended
  honest boundary, not a failure.
- Python capability remains implicit as the original contract rather than an
  explicit `python_disposition` field in router capability metadata. Routing
  and execution succeeded, but explicit publication is tracked as ML-032.
- No native project test suite was run; this was a read-only syntax-lens
  journey. The findings recommend measurement/native verification before any
  mutation, and no mutation was attempted.
