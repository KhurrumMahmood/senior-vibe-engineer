# Real-repository validation — slice 3

Status: pass at product revision `4f3bf41`

## Pinned corpus and preservation

| Language | Repository | Exact revision | License |
|---|---|---|---|
| JavaScript | `expressjs/express` | `a3714473feb3d2908add734d340e7755fd85e0a3` | MIT |
| C | `benhoyt/inih` | `5cc5e2c24642513aaa5b19126aad42d0e4e0923e` | BSD-3-Clause |
| C++ | `fmtlib/fmt` | `40626af88bd7df9a5fb80be7b25ac85b122d6c21` | MIT |
| Kotlin | `detekt/detekt` | `e019e63ee459bd005694ed944af7ad6c8a165c57` | Apache-2.0 |

`scripts/real_repo_corpus.py prepare --slice 3` created exact detached
checkouts under the ignored corpus root. The final `verify --slice 3` accepted
all four revisions, root license files, origins, and empty Git status.
Discovery, build metadata, and result artifacts stayed under the separate
ignored artifact root; none of the four source checkouts changed.

## Canonical discovery and routing

All four repositories passed the same canonical `adapt-project` command with
an external `--artifact-root` and `--no-host-write`; `check_evidence.py` then
accepted each final artifact set.

| Host | Canonical language result | Representative source result |
|---|---|---|
| Express | JavaScript / npm | `lib`, six authored JavaScript files |
| inih | C plus its separate C++ wrapper | root C and `fuzzing`; `cpp` remains separately classified |
| fmt | C++ / CMake | `src` C++ root |
| detekt | Kotlin plus its real website JavaScript / Gradle+npm | Kotlin source roots for `build-logic` and the project modules |

For each explicit language, current `which-skill` returned exit 0, selected
`find-complexity-hotspots`, reported the matching supported disposition, and
handed off the external on-demand closure without ambient-installing it.

## Routed task outcomes

| Host | Final outcome | Source-grounded result | Time |
|---|---|---|---:|
| Express | `complete` | `lib/response.js:126`, `res.send`, branch score 19 | 1.37 s |
| inih | `complete`, `measure-first` | `ini.c:97`, `ini_parse_stream`, score 22 | 0.25 s |
| fmt | `partial`, `safe-defer-incomplete` | 36 compiler-owned syntax leads; `src/fmt.cc` explicitly missing from the normal library build database | 13.57 s |
| detekt | `partial`, `safe-defer-incomplete` | five hash-bound Kotlin leads from the full authored tree | 3.69 s |

The fmt report's leading spans are `format_float` (39/38), `format_dragon`
(34), and `count_code_points::operator()` (26). Duplicate qualified template
spans can represent separate compiler forms and remain advisory. Detekt's
leading spans are `XmlEscape.escapeXml` (11),
`visitDotQualifiedExpression` (10), and
`LibraryCodeMustSpecifyReturnType.check` (9).

The two partial outcomes are useful but not clean conclusions:

- fmt's normal CMake library target compiles `format.cc` and `os.cc`, while the
  optional module unit `fmt.cc` is not in that database. Covered units and
  their compiler-owned headers remain visible; the missing unit is named.
- detekt does not contain the fixture-only `kotlin-project.json` contract.
  Authored lowercase `.kt` syntax is retained with source hashes, while Gradle
  membership, dependencies, native compilation, and runtime behavior remain
  unvalidated.

## Repairs proved by the slice

1. The external library now owns a pinned TypeScript 5.9.3 parser runtime.
   Host-local TypeScript remains preferred, but ordinary JavaScript projects
   no longer need to add TypeScript for the skill. Initial setup installs and
   verifies the lock with Node.js >=20 and npm.
2. JavaScript function expressions assigned through CommonJS, prototypes,
   object properties, and variables are analyzed. This converted Express from
   a misleading zero to the source-valid `res.send` finding.
3. Generic discovery now recognizes C, C++, Kotlin, and C# source roots and
   avoids treating a Kotlin Gradle project as Java merely because Gradle is
   present.
4. C and C++ accept standard `command` or `arguments` compilation databases
   generated in external Meson/CMake build directories. Mixed-language rows
   are filtered by the selected language. Explicit-target coverage can be
   complete; missing target units preserve covered facts as partial.
5. Kotlin and C++ complexity runners accept external artifacts and retain
   useful partial evidence rather than discarding it at fixture-only gates.
6. The coherence hook no longer scans ignored `.engineering/local` reference
   clones as though they were current project source.

## Verification

- C/C++/Kotlin/adaptation focused family replay: `55 passed in 269.83s`.
- Current release/router boundary: `96 passed in 35.17s`.
- Corpus plus TypeScript outcome replay: `20 passed in 19.11s`.
- Coherence regression: `11 passed`; self-audit reports `pass`.
- Router catalog and multi-language matrix are current for all 76 skills.
- Skill metadata: `76/76`; Ruff, diff checks, and every commit hook passed.

The local validation setup installed Homebrew CMake 4.4.0 and Meson 1.11.2;
its transitive Ninja/Python/SQLite state and safe cleanup guidance are recorded
in the execution plan's dependency register.
