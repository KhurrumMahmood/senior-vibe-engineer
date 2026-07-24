# /plan-feature — tier discipline and escalation criteria

Reference for the orchestrator and scout sub-agents. The `/plan-feature`
SKILL.md keeps its own pipeline rules; this file defines the *judgment*
rules — when to use the skill, when to escalate, when to bail.

---

## Tier discipline — the four scope tests

`/plan-feature` is the **Feature-tier** entry point. Use it when **all
four** tests pass:

1. **One workflow.** The feature lands in (or extends) a single
   user-visible workflow. If two workflows are touched, escalate to
   the System-tier chain (`/scope-feature` → `/impact-feature` →
   `/architecture-fit` → `/plan-spec` once it ships).
2. **1-3 day scope.** A senior engineer who already knows the codebase
   could implement it in a week or less. Multi-week work is
   System-tier; spending a week on the spec for a 1-day feature is the
   inverse problem (over-planning).
3. **Impact assessment helps.** The implementation will touch enough
   files that grep alone won't catch every call site. If the change is
   localized to one file or has obvious blast radius (rename a method,
   add a field), skip `/plan-feature` and `/decide` if a real choice is
   being made — proceed directly.
4. **No new subsystem.** The feature extends an existing subsystem; it
   does NOT create a new top-level domain (new package, new
   `core/services/<name>/` directory, new top-level workflow doc). If
   it does, escalate.

If any test fails:
- **Test 1 fails (multiple workflows)** → System-tier chain.
- **Test 2 fails (>1 week)** → System-tier chain.
- **Test 3 fails (trivial)** → proceed directly; `/decide` if a choice
  is being made.
- **Test 4 fails (new subsystem)** → System-tier chain (specifically:
  the System-tier `/scope-feature` step is built to bound new
  subsystems).

---

## The four-stage shape — why these four, in this order

Stage 1 (Read context) → Stage 2 (Impact map) → Stage 3 (Synthesize +
decision stubs) → Stage 4 (Spec scaffold).

The shape mirrors `/find-omnibus` (orchestrator-scout, three-output
discipline) but at planning time rather than audit time:

- **Stage 1 first** because every subsequent step needs to know what
  the codebase already constrains. Skipping Stage 1 lets the spec
  re-litigate decisions that were already made (a "phantom-supersede"
  smell).
- **Stage 2 next** because the impact map is the substrate for
  decision stubs in Stage 3. Decisions made in the abstract — "we
  should use FK" — are weaker than decisions made against a real list
  of touched call sites — "introducing this FK forces these 4 callers
  to change; the alternative (enum + signal) leaves them untouched."
- **Stage 3 third** because decisions are the load-bearing artifact —
  the spec is downstream of them. A spec that doesn't surface its
  forks ("we just picked X because it felt right") leaves no audit
  trail for future-engineers asking "why was Y rejected?"
- **Stage 4 last** because the spec scaffold is the deliverable; it's
  populated *from* Stages 1-3, never *parallel to* them.

Don't reorder. The shape is intentionally test-first-flavored — write
the constraints (Stage 1) before the design (Stage 4), as the canonical
patterns doc requires for implementation work.

---

## Behaviors-to-preserve heuristics

The scout's `## Extracted behaviors` section is the most easily-skipped
and most easily-regretted. Heuristics for what to capture:

| Shape | Why it's load-bearing | Concrete example |
|---|---|---|
| Ordering invariant | Race condition risk | `crawl_job.status = 'running'` save MUST precede Celery dispatch (stale-detection logic) |
| Queue pinning | Wrong queue corrupts state | Discovery uses `--pool=solo -Q browser` (Playwright single-threaded) |
| Mixin requirement | Auth / permission contract | `LoginRequiredMixin` on every internal view |
| Compiled state | Wrong source-of-truth | Exports read `SiteConfig.extraction_recipe`, NOT `ExtractionConfig` rows directly |
| Atomic write | Windows file-system contract | `os.replace()` retry loop in `ExportCacheService` |
| Reverse-shape API | Caller chaining | `apply_product_url_filter` returns a queryset via `pk__in`, not a list |
| Singleton access | Shared state coordination | `GlobalSettings.get_settings()` only — never `.objects.get()` |
| Signal-based coupling | Hidden side-effect | `post_save` on `SiteConfig` triggers extraction-code recompile |

If a behavior fits one of these shapes, it goes in `## Extracted
behaviors`. If it doesn't fit but the scout senses "this would break
something subtle if changed," capture it anyway with a `# subtle:`
prefix and a one-sentence explanation of the risk. Better to over-
capture at this stage; the orchestrator filters during Stage 3.

---

## When to invoke `/decide` inline vs stub

Stage 3 has to decide for each material fork: invoke `/decide` now, or
leave a stub in the spec's `motivating_decision` slot for later.

**Invoke `/decide` inline when:**
- The fork has a clear winner (one alternative is materially better
  given current constraints).
- The Decision sentence can be written without speculation — you can
  finish "We will X because Y" in one sentence.
- The choice is cross-file or supersedes an existing pattern.

**Stub it (leave for later) when:**
- The choice depends on data the scout didn't have (benchmarks,
  user feedback, a separate prototype).
- Two or more alternatives are equally defensible and the spec author
  + reviewer should debate it.
- The choice is local to one file and doesn't supersede a pattern —
  it's a code-level preference, not a decision.

Default to **stub**. Premature decisions are harder to undo than
deferred decisions; the spec carries forward as `proposed`, and the
implementer can promote the stub to a real `/decide` when they reach
the choice point.

---

## Anti-patterns this skill is designed to prevent

### "Spec as wishlist"

Bad: a spec that lists every feature improvement the engineer might
want to ship in the next year, with no constraint on which lands now.

Rule: a `/plan-feature` spec covers ONE feature, named in the
`<feature-name>` argument. Other features get their own specs (or get
deferred to a `## Future work` section in the doc).

### "Decision-free spec"

Bad: a spec whose Architecture section is six paragraphs of
implementation prose with zero forks named or alternatives considered.

Rule: every spec must list its material forks (Stage 3) — even if all
of them are "no real fork; only one defensible shape, here it is."
Future-engineers reading the spec need to see what was considered, not
just what was chosen.

### "Re-discovering already-decided territory"

Bad: a spec that proposes a stringly-typed status field for a new
model, when ADR 0001 already established TextChoices as the standard.

Rule: Stage 1 reads `decisions.py audit --json`. If the feature would
violate an existing decision, Stage 3 EITHER (a) conforms to the
existing decision (and notes that explicitly), OR (b) proposes a
supersession via `/decide --supersede`. The supersession path requires
explicit user approval — never silent.

### "Bypassing the System tier"

Bad: a `/plan-feature` invocation for a feature that obviously spans
two workflows, just because the user asked for it directly.

Rule: if Stage 1 or Stage 2 surfaces 2+ subsystems with non-trivial
work in each, STOP and recommend the System-tier chain. The cost of
escalating is one extra `/scope-feature` call; the cost of forcing
2-workflow work through `/plan-feature` is a spec that misses the
boundary-of-responsibility decisions only `/architecture-fit`
surfaces.

### "Scout dispatched without a doc"

Bad: dispatching `agents/impact-scout.md` for a subsystem that has no
`.engineering/docs/subsystems/<name>.md` file. The scout will form opinions
from raw code reads alone and may misclassify the subsystem's
responsibility.

Compatibility exception: a schema-2 host may still have the map at
`.claude/docs/subsystems/<name>.md`. Use it with an explicit migration warning;
if both homes exist, stop rather than choosing or merging them silently.

Rule: if a subsystem doc is missing, the orchestrator either (a)
recommends running `/map-subsystem <name>` first, or (b) proceeds with
explicit acknowledgement in the spec's `## Architecture` section that
the impact map is doc-less and may be incomplete. Default to (a)
unless time pressure forces (b).

---

## Cross-references

- `.claude/skills/plan-feature/SKILL.md` — orchestrator pipeline.
- `.claude/skills/plan-feature/agents/impact-scout.md` — Stage 2 brief.
- `.claude/skills/plan-feature/knowledge/` (host-project overlay) —
  project-flavored subsystem map and integration hot spots.
- `.claude/skills/_common/skill-frontmatter.md` — the agent decision
  contract this skill complies with.
- `.claude/docs/skill-catalog.md` — where this skill sits in the
  Tier × Job grid.
- `.claude/docs/canonical-patterns.md` — the law every spec must
  respect.
- `.claude/docs/architectural-smells.md` — what to avoid.
- `ai-docs/decisions/README.md` — ADR registry conventions.
- `scripts/specs.py` / `scripts/decisions.py` — the CLIs Stage 4 and
  Stage 3 invoke.
