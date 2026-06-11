# Class B/C de-baking recon

Read-only recon for removing hardcoded host-specific paths/assumptions.
All paths absolute. IMPORTANT location correction: the `_common` module
that scripts import lives at **`.claude/skills/_common/`** (the
`sys.path.insert(... parents[2] / "_common")` idiom resolves there). There
is NO top-level `_common/`. `product_health.py`, `workflows.py`,
`product_topology.py`, and `scope.py` are all under `.claude/skills/_common/`.

Two layers already exist and matter:
- **scope.py** (`.claude/skills/_common/scope.py`): ignore-first repo-walk.
  Public API: `class Scope`, `load_scope(repo_root, skill_name)`,
  `iter_paths(repo_root, scope, *, extensions=..., repo_ignore=...)` (line 281),
  `scan(...)` (line 334), `parse_scope`, `parse_sections`, `load_repo_ignore`,
  `path_matches`, `descriptor_text`. This is the canonical "scan from repo
  root, narrow only via ignore/allow files, filter by extension" primitive.
- **workflows.py** (`.claude/skills/_common/workflows.py`): host-authored
  product-workflow descriptor at **`.engineering/docs/product-workflows.md`**
  (see item 6). Already de-host-a'd: ships no workflow; empty descriptor =
  empty results.

The descriptor home (`.engineering/docs/`) EXISTS in this repo, and
descriptor files exist as skill fixtures (e.g.
`.claude/skills/find-contract-drift/fixtures/{good,bad}/.engineering/docs/product-workflows.md`).

---

## 1. find-folder-topology-drift (CLASS C)
File: `~/Projects/engineering-skills-2/.claude/skills/find-folder-topology-drift/scripts/detect.py`

**Scan-root default (lines 529-534):**
```python
parser.add_argument(
    "--root",
    type=Path,
    default=Path("app"),          # <-- hardcoded host dir
    help="Package root to scan (default: app)",
)
```
Resolution (line 558): `scan_root = args.root if absolute else (project_root / args.root)`.

**How the root is consumed — `Path.rglob`, NOT scope.** In `detect()` (lines 384-391):
```python
if not scan_root.is_dir():
    return findings
directories: list[Path] = [scan_root]
for path in scan_root.rglob("*"):
    if path.is_dir() and not _is_excluded(path, exclude_globs):
        directories.append(path)
```
Exclusion is a *parallel* mechanism: its own `DEFAULT_EXCLUDE_DIR_NAMES` set
(lines 46-56) + `--exclude` globs (`_is_excluded`, 90-97). NOT the shared
scope ignore.

**Does it import scope?** **NO.** `grep -c "_common|import scope"` = 0. No
`sys.path.insert` idiom. It is the only one of the three Class-C scripts that
never touches `_common` (imports: argparse, fnmatch, json, sys, collections,
pathlib — lines 37-42).

**Single-top-dir assumptions if scanned from repo root:**
- Band 4 `pages_route_mirror` is hardcoded to `scan_root / "pages"` (line 520)
  — expects `app/pages/`. From repo root it would look at `<root>/pages`.
- `_PAGES_PARENT_TO_TOKEN` (lines 295-303) is a fixed host-a singularization
  map (`sites→site`, `runs→run`, …).
- `sparse_folder_package` band explicitly skips `directory != scan_root`
  (line 414): "skip the scan root itself (its cluster size is the whole
  project)". If `scan_root` becomes repo root, the repo root itself is the
  skipped node (fine) — but every top-level dir (`docs/`, `tests/`,
  `scripts/`, `experiments/`, vendored trees) becomes a candidate for
  flat-prefix / sparse-folder findings.
- `DEFAULT_EXCLUDE_DIR_NAMES` does NOT exclude `docs`, `scripts`, `reports`,
  `experiments`, etc. → repo-root scanning would flood noise unless the
  exclude set is widened OR (better) this is rewired onto scope's ignore.
- `FRAMEWORK_FOLDER_NAMES` / `PREFIX_NOISE_TOKENS` (lines 61-87) are
  Django-flavored (`commands`, `management`, `templatetags`, `wsgi`, `asgi`,
  `settings`). Noise filters, not breakage.

Net: analysis is **per-directory** (topology computed relative to each dir,
not relative to `scan_root`), so it *can* structurally analyze the whole
repo's folder tree — the one band tied to a named top dir is
`pages_route_mirror`, and exclude-coverage is the practical blocker. De-bake
path: default `--root` to repo root + replace `rglob`+`_is_excluded` with
scope's `iter_paths`/ignore (parents[2]/_common import like the others), and
make the pages-mirror band either descriptor-driven (`page-dir` from
workflows.py) or graceful-skip when absent.

---

## 2. find-frontend-contract-drift (CLASS C)
File: `~/Projects/engineering-skills-2/.claude/skills/find-frontend-contract-drift/scripts/detect.py`

**Roots defaults (lines 686-688):**
```python
parser.add_argument("--template-root", type=Path, default=Path("templates"))
parser.add_argument("--js-root", type=Path, default=Path("static/js"))
```
Resolution lines 694-695 (rel→project_root).

**How consumed — rooted directory walk filtered by extension, via `iter_files`.**
It DOES import `_common` (lines 11-12):
```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import extract_window_accesses, iter_files, write_jsonl  # noqa: E402
```
Collection (`detect`, lines 537-538):
```python
template_paths = iter_files(template_root, (".html",))
js_paths = iter_files(js_root, (".js",))
```
So it **already filters by extension** (`.html` / `.js`) — but only *within*
the two hardcoded dir roots. `iter_files(root, exts)` (defined in
product_topology.py) is a plain rooted walk; it is NOT scope-based and has NO
ignore awareness. It does NOT call `load_scope`/`iter_paths`. Note
`product_topology` itself imports `scope` and `workflows`, and `workflows.py`
already exposes `workflow_ui_template_globs()` / `workflow_ui_script_globs()`
(item 6) — i.e. the descriptor already has slots meant to feed exactly these
two roots, but this detect.py does not consume them yet (still hardcoded
argparse dirs).

**Other hardcoded host assumptions baked into detection (would NOT auto-fix
by just changing roots):**
- `_workflow_scope` (lines 101-107): `templates/core/site_config`,
  `static/js/site-config`, `external_source` → host-a `/sites` literals.
- `_is_shared_template` (413-419): matches `site_config_base.html`,
  `/includes/`, `base`.
- `STATIC_JS_RE = {% static 'js/...' %}` (line 40) — Django `{% static %}`
  template-tag assumption.
- `CANONICAL_BOOT_GLOBAL = "SITES_CONFIG"` + `COMPAT_BOOT_GLOBALS`
  (lines 79-88) — host-a-specific window globals.

**What breaks if scanned whole-repo-by-extension instead of by the two dirs:**
collection-wise nothing (already extension-filtered); more `.html`/`.js` are
simply considered. Real risk is **volume / false-positives**: the
`_workflow_scope`/`_is_shared_template`/boot-global literals are tuned to
`templates/` + `static/js`. Scanning vendored JS (node_modules, staticfiles,
Django admin JS) would flood `undeclared_window_read` / auto-init findings
because `iter_files` has no ignore layer. De-bake path: route collection
through scope `iter_paths(extensions=(".html",))` / `(".js",)` from repo root
(scope ignore replaces the implicit narrowing the two dirs provided), and/or
seed roots from `workflow_ui_template_globs`/`workflow_ui_script_globs`.

---

## 3. find-route-sprawl (CLASS C EXEMPLAR — path-agnostic)
File: `~/Projects/engineering-skills-2/.claude/skills/find-route-sprawl/scripts/detect.py`
SKILL.md: `~/Projects/engineering-skills-2/.claude/skills/find-route-sprawl/SKILL.md`

**Argparse default is `None` (lines 125-130):**
```python
parser.add_argument(
    "--root-urls",
    type=Path,
    default=None,
    help="Root URLconf to scan; auto-discovered via scope when omitted.",
)
```

**Code path when arg is None (lines 137-145):**
```python
root_urls = args.root_urls
if root_urls is None:
    root_urls = discover_root_urlconf(project_root, "find-route-sprawl")
    if root_urls is None:
        write_jsonl([], args.output)
        print(f"wrote {args.output}: 0 findings (no urls.py found)")
        return 0
elif not root_urls.is_absolute():
    root_urls = project_root / root_urls
```
It imports `_common` via the same idiom (lines 10-17):
`from product_topology import discover_root_urlconf, extract_routes, relpath, route_shape_for, write_jsonl`.

**What "auto-discover" means — repo-root + ignore via scope (GOOD, not
app-root guessing).** `discover_root_urlconf` lives in
`~/Projects/engineering-skills-2/.claude/skills/_common/product_topology.py`
(def at **line 346**, full body confirmed). Exact mechanism (lines 358-378):
```python
if skill_name:
    candidates = [p for p in _scope.scan(project_root, skill_name,
                  extensions=frozenset({".py"})) if p.name == "urls.py"]
else:
    candidates = [p for p in _scope.iter_paths(project_root, _scope.Scope(),
                  extensions=frozenset({".py"})) if p.name == "urls.py"]
if not candidates: return None
project_markers = {"settings.py", "settings", "wsgi.py", "asgi.py"}
for path in candidates:                       # prefer the project urlconf
    if {s.name for s in path.parent.iterdir()} & project_markers:
        return path
return min(candidates, key=lambda p: (len(p.relative_to(project_root).parts), str(p)))  # else shallowest
```
So with a skill name it enumerates `urls.py` files **ignore-first through the
per-skill scope universe** (`_scope.scan(project_root, skill_name,
extensions={".py"})` — which loads `.engineering/docs/<skill>-scope.md`), then
disambiguates the *real* ROOT_URLCONF by **settings/wsgi/asgi adjacency** (the
`urls.py` whose sibling files include a project marker), falling back to the
shallowest. This is exactly the desired pattern: **scan-from-repo-root +
scope-ignore + extension filter + marker-based selection**, NOT a guess at
"which dir is the app root". The template to port to items 1 and 2. (My
earlier description said it preferred `include(`; the actual disambiguator is
project-marker adjacency — corrected here.)

NOTE: `detect()` itself still consumes `route_shape_for(project_root)`
(product_topology.py line 58), whose values come from the descriptor's
`## Routes` section (`page_prefix`/`api_prefix`/`scoped_id_param`). With no
descriptor the RouteShape `is_empty` and `classify_route` returns `"other"`
for everything → route-sprawl finds nothing rather than assuming `/sites`.
(There are host-a-default literals like `page_prefix="sites"` only inside helper
fns `route_shape_for`-adjacent code, e.g. product_topology lines 607/621/701,
used as *fallback args* in standalone helpers, not in the descriptor path.)

---

## 4. find-frontend-duplication / cotton_inventory.py (CLASS B — Cotton)
File: `~/Projects/engineering-skills-2/.claude/skills/find-frontend-duplication/scripts/cotton_inventory.py`

**Hardcoded Cotton paths:**
- line 142: `cotton_dir = project_root / "app" / "_components" / "cotton"`
- lines 143-144: `if not cotton_dir.exists(): raise SystemExit(f"app/_components/cotton not found under {project_root}")`
  — **hard failure when the Cotton dir is absent.**
- line 167: report literal `"cotton_dir": "app/_components/cotton"`.
- `count_callsites` bases (lines 114-118): `project_root/templates`,
  `project_root/static/js`, `project_root/core` — three hardcoded host dirs.

**How it detects Cotton components:** it does NOT detect "is this a Cotton
repo" — it *assumes* it. `build_inventory` (141-170) globs `cotton_dir/*.html`,
and per file runs `parse_cvars` (63-90, reads `<c-vars …>` via `CVARS_RE`),
`has_default_slot` (`{{ slot }}`), `named_slot_candidates`, and
`count_callsites` (regex `<c-{name}\b`, line 114). Component identity =
filename stem with `_`→`-` (lines 59-60). The whole file is the django-cotton
`<c-vars>` / `<c-name/>` / `{{ slot }}` convention end to end.

**Hard requirement vs optional branch:** **HARD requirement.** This is a
Cotton-only script — there is no generic-duplication branch in it. It produces
a Cotton primitive catalogue; absent `app/_components/cotton/` it
`raise SystemExit`s (line 144). The "plain duplication detection with no
Cotton logic" degradation the design wants does NOT exist in this file. (The
broader `find-frontend-duplication` skill *compares* Tailwind class chains / JS
fn defs against this inventory; this script supplies only the Cotton-inventory
half — so it is the isolatable Cotton-specific *producer* component of that
skill.)

**Configurable component dir/prefix?** **NONE.** `--root` (line 188) is
project root only; `--out` is the output path. The cotton dir, the `c-` prefix
(`<c-{primitive}\b`, line 114), the `<c-vars>` token, and the three callsite
bases are all hardcoded. No declared-preference hook.

De-bake path for Principle B: read a host-declared component dir/prefix from
the descriptor (no such field exists yet — see item 6e), and when absent,
**degrade gracefully** — the caller should treat a missing/undeclared cotton
dir as an empty inventory (return `{"primitive_count": 0, "primitives": []}`)
instead of `raise SystemExit`, so the surrounding duplication scan still runs
plain (no Cotton logic).

---

## 5. _common/product_health.py (CLASS B — shared advisory helpers + surface map)
File: `~/Projects/engineering-skills-2/.claude/skills/_common/product_health.py`

This is NOT a "ProductSurface classifier"; it is the shared helper library for
the advisory product-health SUSPECT skills. It imports from `product_topology`
and `workflows` (lines 17-19).

**Public API (signatures, one line each):**
- `load_module(name, path) -> Any` (32-38) — import a module from a file path.
- `line_for_offset(text, offset) -> int` (41-42) — 1-based line of a char offset.
- `read_text(path) -> str` (45-46) — utf-8 read, errors ignored.
- `expand_paths(project_root, raw_paths, suffixes, default_targets=None) -> list[Path]`
  (49-83) — resolve scan targets to files: explicit `raw_paths` win, else
  caller `default_targets`, else **`workflows.workflow_targets(project_root)`**
  (empty when no descriptor); globs/dirs expanded, `SKIP_DIRS` pruned, filtered
  by `suffixes`.
- `infer_surface(file) -> str` (86-101) — classify a repo-rel path string to a
  surface label (see hardcoded map below).
- `finding(pattern, path, lineno, summary, recommendation, project_root, *, confidence="medium", surface=None, next_skill="triage-debt", guard_candidate=False, **extra) -> dict`
  (104-131) — build a normalized finding record (calls `infer_surface` when
  `surface` is None, line 126).
- `normalize_record(record, project_root, *, default_confidence="medium", next_skill="triage-debt", guard_candidate=False) -> dict`
  (134-152) — coerce a raw record to the finding schema (also calls
  `infer_surface`, line 149).
- `render_report_file(title, detections, output, target) -> None` (155-164) —
  read detections.jsonl → markdown + findings.json.
- `write_scan_outputs(skill_name, title, records, target, project_root, *, skip_effectiveness_log=False) -> Path`
  (167-215) — write reports/<skill>/<scan>/ {detections.jsonl, report.md,
  findings.json}, update `latest` symlink, log effectiveness.

Also module-level `SKIP_DIRS` (22-29): `.git, .venv, __pycache__,
node_modules, staticfiles, migrations`.

**Hardcoded product-surface map — `infer_surface`, lines 86-101 (exact):**
```python
def infer_surface(file: str) -> str:
    if file.startswith("app/pages/sites") or file.startswith("templates/core/site_config"):
        return "sites_template_or_view"
    if file.startswith("app/site_management") or file.startswith("app/api/"):
        return "sites_backend"
    if file.startswith("app/services/sites"):
        return "sites_service"
    if file.startswith("static/js/"):
        return "sites_frontend"
    if file.startswith(".claude/skills"):
        return "skill"
    if file.startswith(".claude/docs") or file.startswith("docs/"):
        return "docs"
    if file.startswith("tests/") or file.startswith("testing/"):
        return "tests"
    return "sites_surface"
```

**How the map is used / what it returns:** prefix-match, first hit wins;
returns a **surface label string** (`"sites_template_or_view"`,
`"sites_backend"`, `"sites_service"`, `"sites_frontend"`, `"skill"`, `"docs"`,
`"tests"`) else the catch-all `"sites_surface"`. It is the `surface` field of
every finding record (set inside `finding()` line 126 and `normalize_record()`
line 149) — purely a labeling/grouping signal for report output, not a gate.

**De-bake notes (Principle B/C):** two host couplings here —
(i) `infer_surface`'s `app/pages/sites`, `templates/core/site_config`,
`app/site_management`, `app/api/`, `app/services/sites` prefixes plus the
`"sites_*"` label vocabulary are host-a `/sites`-specific (the default
`"sites_surface"` literal is itself a leak); and (ii) the rest of `expand_paths`
is *already* de-baked — it routes through `workflows.workflow_targets`. So the
cleanup is mostly `infer_surface`: drive surface labels from descriptor data
(or collapse to a neutral default like `"surface"`/`None`) when no descriptor.

---

## 6. product-workflows descriptor mechanism (CLASS B)
Parser: `~/Projects/engineering-skills-2/.claude/skills/_common/workflows.py`
Descriptor path: **`.engineering/docs/product-workflows.md`** under the
cross-agent state home (`engineering_home.docs_path(repo_root, DESCRIPTOR_NAME)`,
`DESCRIPTOR_NAME = "product-workflows.md"`, line 73). The `.engineering/docs/`
home EXISTS in this repo; real descriptors ship as skill fixtures (e.g.
`.claude/skills/find-contract-drift/fixtures/{good,bad}/.engineering/docs/product-workflows.md`).
Module docstring (lines 2-15) states the toolkit ships NO workflow — empty
descriptor → empty results (ignore-first contract, mirrors scope.py).

**Public parsing API (signatures, one line each):**
- `workflow_steps(repo_root) -> list[dict[str,str]]` (110-123) — ordered
  `{id,label,route_name,path}` rows from `## Steps` (4-field `|` rows; malformed skipped).
- `workflow_labels(repo_root) -> list[str]` (126-130) — step labels +
  `## Extra labels`, deduped.
- `workflow_tab_ids(repo_root) -> list[str]` (133-137) — step ids +
  `## Extra tab ids`, deduped.
- `workflow_targets(repo_root) -> list[str]` (140-142) — scan-target globs
  from `## Targets`.
- `workflow_template_roots(repo_root) -> list[str]` (145-147) — `## Template roots`.
- `workflow_text_globs(repo_root) -> list[str]` (150-152) — `## Text-file globs`.
- `workflow_ui_template_globs(repo_root) -> list[str]` (155-159) —
  `## UI template globs` (templates that assign boot globals).
- `workflow_ui_script_globs(repo_root) -> list[str]` (162-166) —
  `## UI script globs` (scripts that read boot globals).
- `workflow_route_shape(repo_root) -> dict[str,str]` (169-187) — `## Routes`
  `key | value` rows; recognized keys `page_prefix`, `api_prefix`,
  `scoped_id_param`.
- privates: `_descriptor_text` (91-99), `_sections` (102-107, uses
  `scope.parse_sections`), `_dedupe` (190-191).

**Sections supported — `_SECTION_MAP`, lines 76-86 (exact heading→key):**
```python
_SECTION_MAP: dict[str, set[str]] = {
    "steps":             {"steps", "workflow steps"},
    "extra_labels":      {"extra labels", "labels"},
    "extra_tab_ids":     {"extra tab ids", "tab ids", "extra tabs"},
    "targets":           {"targets", "scan targets"},
    "template_roots":    {"template roots", "templates"},
    "text_globs":        {"text-file globs", "text file globs", "text globs"},
    "ui_template_globs": {"ui template globs", "frontend template globs"},
    "ui_script_globs":   {"ui script globs", "frontend script globs"},
    "routes":            {"routes", "route shape"},
}
```
Grammar: one `##` heading per section; bullets are backtick/text rows; `## Steps`
rows are `id | label | route_name | path`; `## Routes` rows are `key | value`
(docstring lines 17-59). Parsing reuses `scope.parse_sections` (no PyYAML).

**Any component-system / framework / component-preference concept?** **NO.**
`grep -in "cotton|component|framework|preference"` across `workflows.py`,
`product_topology.py`, `product_health.py`, `scope.py`, and
`tests/test_workflows.py` returns nothing relevant. (The only `framework` /
`component` hits in `_common` are in DOCS: `portability-roadmap.md`,
`structural-design-principles.md`, `skill-frontmatter.md` discuss a *future*
`_lib/framework/<fw>/` reorg and the `language`/`framework` frontmatter seam —
none is a runtime descriptor field. `structural-design-principles.md:101`
mentions `pages/_components/` only as a route-segment example.) The descriptor
today is purely route/dir/glob/step topology — there is **no** declared-
preference slot for a component system (Cotton) or host framework. Adding one
(e.g. a `## Components` section with `component-dir` / `component-prefix` keys,
parsed via the same `_SECTION_MAP` + a `workflow_components()` accessor, then
consumed by cotton_inventory.py item 4) would be net-new but fits the existing
mechanism cleanly.

---

## Blast radius (product_health.py consumers)
Every script under `.claude/skills/` that imports `product_health` (grep of
`product_health` across skill scripts). The advisory product-health skills each
import it across their `detect.py` / `report.py` / `run.py` trio:

- `~/Projects/engineering-skills-2/.claude/skills/find-async-lifecycle-drift/scripts/{detect,report,run}.py`
- `~/Projects/engineering-skills-2/.claude/skills/find-complexity-hotspots/scripts/{detect,run}.py`
- `~/Projects/engineering-skills-2/.claude/skills/find-contract-drift/scripts/{detect,report,run}.py`
- `~/Projects/engineering-skills-2/.claude/skills/find-dead-route-surface/scripts/{detect,report,run}.py`
- `~/Projects/engineering-skills-2/.claude/skills/find-doc-route-drift/scripts/detect.py`
- `~/Projects/engineering-skills-2/.claude/skills/find-test-obligation-drift/scripts/{detect,report,run}.py`
- `~/Projects/engineering-skills-2/.claude/skills/find-workflow-state-gaps/scripts/{detect,report,run}.py`
- `~/Projects/engineering-skills-2/.claude/skills/map-product-workflow/scripts/generate.py`
- test: `~/Projects/engineering-skills-2/tests/test_product_health.py` (exists per grep; verify name)

So **8 skills + 1 test module** depend on `product_health.py`. Most consume the
helper API (`expand_paths`, `finding`, `normalize_record`, `write_scan_outputs`,
`render_report_file`, `infer_surface`), so changing `infer_surface`'s
labels/prefixes or `expand_paths`'s defaulting touches all of them. NOTE:
find-route-sprawl and find-frontend-contract-drift (items 2-3) do NOT import
product_health — they go through `product_topology` directly.
(I could not exhaustively confirm the exact imported-symbol list per consumer
because the shell stalled near the end of this recon; the importer FILE list
above is from a completed grep and is reliable. Re-run
`grep -rn "from product_health import" .claude/skills/*/scripts/*.py` to get
per-file symbol lists before editing the API.)

---

## Recon answers
(a) **find-folder-topology-drift uses scope, or os.walk/rglob?** → **rglob**
(`scan_root.rglob("*")`, line 389). Does NOT import scope/_common at all (0
refs); uses its own `DEFAULT_EXCLUDE_DIR_NAMES` + `--exclude`. Default root
`Path("app")` (line 532). The odd one out — needs the most rewiring.

(b) **find-frontend-contract-drift collects by extension, or purely by dir
name?** → **Both**: extension-filtered (`iter_files(root, (".html",))` /
`(".js",)`, lines 537-538) but *within* two hardcoded dir roots (`templates`,
`static/js`, lines 687-688). Uses `product_topology.iter_files` (a rooted walk
with NO ignore awareness), NOT scope/`iter_paths`. The descriptor already has
`workflow_ui_template_globs`/`workflow_ui_script_globs` slots meant for these
roots, unused here.

(c) **find-route-sprawl "auto-discover" = repo-root+ignore-via-scope, or
app-root guessing?** → **repo-root + ignore via scope.** Default `--root-urls
None` → `discover_root_urlconf(project_root, "find-route-sprawl")`
(product_topology.py:346), which enumerates `urls.py` files ignore-first via
`_scope.scan(project_root, skill_name, extensions={".py"})` (honors
`.engineering/docs/find-route-sprawl-scope.md`), then disambiguates the real
ROOT_URLCONF by settings/wsgi/asgi sibling-adjacency, falling back to the
shallowest. The clean exemplar to port. (Its `route_shape_for` classification
is descriptor-driven and empty without a descriptor — no `/sites` assumption.)

(d) **Is Cotton a hard assumption in cotton_inventory.py, or an isolatable
branch?** → **Hard assumption** — Cotton-only script; `raise SystemExit` if
`app/_components/cotton/` is missing (line 144). No generic-duplication branch
in this file; no configurable component dir/prefix. It IS isolatable as a unit
(the Cotton-specific producer half of find-frontend-duplication), so graceful
degrade = caller treats missing/undeclared cotton dir as empty inventory
instead of letting this script hard-exit.

(e) **Does any descriptor/workflows concept for component-system/framework
preference already exist?** → **No.** The descriptor
(`.engineering/docs/product-workflows.md`, parsed by workflows.py) supports
`## Steps`, `## Extra labels`, `## Extra tab ids`, `## Targets`,
`## Template roots`, `## Text-file globs`, `## UI template globs`,
`## UI script globs`, `## Routes` (with keys `page_prefix`/`api_prefix`/
`scoped_id_param`). Zero cotton/component/framework/preference fields anywhere
in the descriptor mechanism (only unrelated `framework`/`component` mentions in
`_common/*.md` design docs about a future portability reorg). A component-
preference slot would be net-new but fits the existing `_SECTION_MAP` pattern.
