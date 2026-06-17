# Structural Design Principles

Use this shared reference when a skill proposes, evaluates, or executes
a *structural* choice — folder topology, module placement, naming,
top-level organization, skill grouping, or any architectural decision
that constrains where humans (and agents) look to find things. It is
project-agnostic and language-agnostic; project-specific instances
belong in each project's ADRs and skill `knowledge/` files.

## The two-layer rule

> Norms for the language and frameworks you're using are a **floor**.
> Above that floor, maximally prioritize **intuitiveness and ease of
> skimming** to find what you need.

Two layers, in this order:

1. **Floor — framework and language norms.** Hard constraints: things
   break if you violate them. Examples:
   - Django: an app is a package with `models.py` / `views.py` /
     `urls.py` / `apps.py` / `migrations/`. The app's package name is
     consistent with `INSTALLED_APPS` and imports.
   - Python: top-level repo layout, `__init__.py` semantics,
     relative-import resolution.
   - Test runner conventions (py.test discovery, Django test runner).
   - Build tools and deployment conventions (where `setup.py`,
     `pyproject.toml`, `Dockerfile` live).
   - JS framework conventions (Next.js `app/` directory, Vite root,
     framework-mandated config files).

2. **Above the floor — human-skim intuitiveness.** Soft criteria:
   things don't break if you ignore them, but the codebase becomes
   harder to navigate. The objective is: a human (or AI agent) walks
   into the directory listing for the first time, scans the names,
   and locates the thing they're looking for **without already knowing
   the codebase**.

## Why the order matters

The floor is a *constraint*, not a *ceiling*. A common failure mode is
treating framework convention as the answer ("it's a Django app, so
everything goes in `core/`") when the framework only mandates *that*
the package exist, not *what to call it* or *how to organize content
inside it*. The floor tells you what you can't do; intuitiveness
tells you what you should do with the freedom you have.

The opposite failure mode is ignoring the floor in pursuit of
intuitiveness — splitting a Django app along workflow lines without
realizing the framework needs the package boundary to stay coherent
(or that the split is itself a multi-app refactor with real
migration cost).

## Tests for "intuitive"

When evaluating a structural choice above the floor, apply these:

1. **Skim test.** A reader who has never seen this codebase opens the
   top-level directory listing. Can they form a working mental model
   of what each folder owns from names alone? If you have to explain
   what `core/` means, the name is failing the test.
2. **Find test.** A reader knows what they want (e.g., "the code that
   handles site-config"). They scan the listing. Do they reach the
   right folder in one or two hops? If they have to grep file names
   to recover the cluster, the layout is failing the test.
3. **Cluster test.** A reader who finds *one* relevant file looks
   at its siblings. Do the siblings reveal a coherent cluster, or do
   they look like an unrelated grab bag? Same domain near same
   domain.
4. **Stranger test (the strongest).** Show the directory listing to
   someone who knows the *domain* but not this codebase (e.g., another
   pricing-tool engineer for a pricing project). Can they predict
   what's in each folder? If yes, the layout is carrying its weight
   intuitively.

## The navigation-key principle

Different surfaces in the same project legitimately use different
navigation keys. Above the floor, before picking a topology for a
surface, ask: *what's the navigation key for this surface?* — when a
reader asks for a file, what term do they use?

- **URL routes** are the navigation key for HTTP views and API
  endpoints. A reader asks "where's the discovery page?" →
  `pages/sites/discovery/`. Mirror the route tree.
- **Domain concepts** are the navigation key for services, models,
  and domain objects. A reader asks "where's brand_name extraction?"
  → `services/extraction/brand_name/`. Mirror the domain.
- **Subsystem internals** are the navigation key for substrate code
  (the AI runtime, the crawler infrastructure). A reader asks
  "where's the provider stack?" → `ai/providers/`. Mirror the
  internals.

The mistake is forcing one navigation key on every surface
(always-routes, always-DDD, always-layered). The right answer is to
*match each surface to its key*. A single project legitimately mixes
route-aligned `pages/`, domain-aligned `services/`, and
subsystem-internal `ai/` at the same level.

**The `_*` prefix convention.** Inside a folder that mirrors an
external structure, non-mirrored children carry an underscore prefix.
`pages/sites/discovery/` is a route segment; `pages/_components/` is
meta. The `_` differentiates "structurally mirrored" from
"conceptually grouped." Apply this consistently wherever a folder
mirrors something — `api/_common/`, `services/_common/`,
`ai/_common/`.

## Structural rules above the floor

The intuitiveness goal collapses into five sub-rules. They apply at
every nesting depth — repo root, package root, any folder — and are
an ongoing test, not a one-time top-level redesign.

1. **Purpose-aligned top level.** A folder's name reveals *what
   kinds of things live in it*. MVC's `models/views/controllers/` is
   one example of the principle, not a mandate — name folders for
   the categories of work they own, not for opaque project history.
   "Why is this called `core/`?" is the diagnostic question; if the
   answer is "because the project started that way," the name is
   failing rule 1.

2. **Depth = specificity.** Each level deeper narrows scope.
   `services/ai_sidecar/extraction_runtime.py` is more specific
   than `services/ai_sidecar/`, which is more specific than
   `services/`. Folders that don't narrow scope are noise; folders
   that broaden scope are violating the rule. Pure-grouping folders
   ("util/", "misc/", "common/", "helpers/") almost always fail this
   test — they aggregate unrelated content under a single roof.
   **Default to scoped helpers under each subsystem
   (`<subsystem>/_common/`); admit a top-level junk-drawer folder
   only when something genuinely crosses ≥3 subsystems and has no
   natural home in any.** Top-level "things-that-don't-fit" folders
   are guaranteed rule-2/rule-5 violation accumulators over time.

3. **Cohesion = colocation.** Related code groups together — same
   file when small, same folder when large enough to merit splitting.
   Don't fragment a coherent concept across siblings just because
   each piece is "clean in isolation." A single 600-LOC cohesive
   module is fine; six 100-LOC modules with the same prefix are
   usually a folder waiting to be born (rule 5).

   **Parallel hierarchies fail this rule.** When two folders mirror
   the same external structure but split content by *kind* — e.g., a
   route-mirrored `pages/sites/discovery/` for Python alongside a
   parallel `templates/sites/discovery/` for HTML — every change
   touches both. Prefer single-hierarchy colocation
   (`pages/sites/discovery/{view.py, template.html, ...}`) over
   parallel hierarchies, even when framework defaults push toward
   the parallel shape. The cost of breaking the framework default is
   usually a one-line config; the cost of recurring two-folder edits
   is permanent.

4. **Per-folder README is the signpost.** Folders large enough to
   navigate to should self-describe with a `README.md` (or
   equivalent index) that tells the reader what lives there and how
   the contents relate. The README is the folder's interface;
   without it, a reader has to skim every file to recover the
   cluster's purpose. The README answers: "what is this folder for,
   what's in it, and what *isn't* in it that you might expect."

5. **No prefix-as-fake-folder.** A file named `<prefix>_<thing>.ext`
   whose prefix names a folder-worth of work should *be* a folder.
   When the prefix is a category and the suffix is the specific
   thing, the category should be a real directory. The threshold for
   "folder-worth" is project-specific (this project: ≥3 siblings, per
   ADR 0006), but the principle stands at any depth: prefix sprawl
   is a folder asking to be born.

   Generalize this beyond literal prefixes: when the same name is acting
   as a tag across several siblings, and those siblings naturally change
   together or answer the same reader question, prefer a real container.
   Four renaming-related skills usually belong under a `renaming/`
   boundary unless a discovery mechanism or framework requires a flat
   registry.

These rules compose. A purpose-aligned top level (rule 1) is
depth-zero. A folder for a prefix cluster (rule 5) only makes sense
if it narrows scope (rule 2). A folder's README (rule 4) explains
the cohesion (rule 3) of its contents. Failing one rule often means
failing another — junk-drawer flatness fails 1, 2, and 5 at once.

## When the two layers conflict

The floor wins on hard constraints (you literally cannot ship code
that violates the framework's import rules). But many apparent
conflicts are actually false: framework norms usually constrain the
*existence* of a structure (a Django app must be a package), not the
*name* (you can name the app anything) or the *internal organization*
(the app can have whatever subpackages it wants).

When you face a real conflict (e.g., promoting workflow folders out
of an app to surface them at the top level requires a real Django
multi-app refactor), the cost of breaking the floor is the
migration cost — usually high. The cost of leaving intuitiveness on
the table is recurring navigation friction — accumulates per agent,
per developer, per refactor. Weigh both before choosing.

**AI changes the cost calculus.** When the floor cost is "manual
update of N references," weigh whether that cost is *actually
manual* in an AI-grown codebase. With agentic move-tools — build
the tool, write characterization tests for each move shape, run
the tool against a typed plan — what looks like a multi-week
migration can become a one-week build + one-day execute. Before
deferring an "expensive" structural choice on cost grounds, ask:
*is the cost manual, or tooling-buildable?* The tool itself often
becomes a reusable artifact; the second restructure pays for the
first.

## How to use this in a skill

- **SUSPECT skills** that detect structural drift cite this rule
  when explaining *why* the smell costs anything ("the layout fails
  the skim test").
- **EXPLAIN/proposal skills** evaluate options against both layers:
  state which framework norms constrain the choice (the floor), then
  evaluate intuitiveness above the floor.
- **DECIDE / ADR-authoring skills** name both layers explicitly in
  the design-space section of an ADR — what the framework requires,
  and what intuitiveness gain motivates the choice above that.
- **REFACTOR skills** preserve the floor invariants under
  characterization tests; the intuitiveness gain is the target
  outcome, but it doesn't excuse breaking framework correctness.

## Substrate vs. feature

When a subsystem mixes infrastructure code (the substrate something
else uses) with feature code (something that uses the substrate), the
two often want different homes. Test:

> *"Would this code still exist if we replaced the
> [provider/library/runtime] tomorrow?"*

- **No** → it's substrate; lives at the substrate level (e.g.,
  `ai/`, `crawler/`).
- **Yes** → it's feature code; lives in the feature's home (e.g.,
  `services/extraction/`).

The split forces a clean dependency direction: features depend on
substrate, never the reverse. It also lets substrate evolve
independently of any specific feature, and lets feature code stay
agnostic of substrate replacement (the "what if we swap providers"
hypothetical isn't a future-proofing fantasy; it's a clarifying
test for *today's* placement).

The same test resolves a recurring confusion in AI-using codebases:
*is this an `ai/` thing or a `services/` thing?* The answer is
almost always: substrate (provider stack, prompt context, agent
harness, benchmark infrastructure) goes in `ai/`; features that
*use* AI (extraction pipeline, classifier, recommender) go in
`services/`.

## Companion: Interface Depth

Where this doc covers *where things go* (placement and topology),
`interface-depth.md` covers *how things expose themselves to callers*
(public surface, leverage, locality). Both are structural, both are
project-agnostic, both belong at the start of any proposal that
reshapes structure.
