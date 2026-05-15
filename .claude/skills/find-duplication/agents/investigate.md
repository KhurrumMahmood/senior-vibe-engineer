# Scout brief — investigate a duplication finding

This file is a **prompt template** the orchestrator expands and sends to a
sub-agent. Placeholders are double-brace `{{name}}`. The orchestrator fills
them in and calls `Agent(subagent_type="general-purpose", prompt=<expanded>)`.

Fresh sub-agent, no prior context. Everything the scout needs to act on the
finding is either inline below or in three knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are investigating **one** code-duplication finding in this codebase
so the main orchestrator can decide whether to dispatch a fix.
You are not fixing anything. You are not touching code. You produce a
classification JSON file and nothing else.

### Finding to investigate

```json
{{finding_json}}
```

Project root (absolute): `{{project_root}}`
Write your output here: `{{output_path}}`

### Knowledge you MUST consult

In this order:

1. `{{skill_root}}/knowledge/false-positives.md` — the dispatch-registry
   check is **mandatory** for class-like or module-level callables. Do not
   claim "dead" or "single caller" for a class until you have run the
   registry-dispatch check from this file.
2. `{{skill_root}}/knowledge/` (host-project overlay) — known dispatch registries,
   intentional boilerplate, shadow-helper names, which test suites guard
   which subsystems.
3. `{{skill_root}}/knowledge/learnings.md` — read only when you hit
   ambiguity. Cluster 2, 3, 10 are the most frequently cited precedents.

### Investigation steps (in order)

**4a. Read both/all sites with context.** For every site in the finding,
Read the enclosing function, a few definitions above it, and the imports.
Line ranges from jscpd are approximate; confirm the real clone span.

**4b. Grep upward in each file.** Read the top-of-file area for each site:
imports, module-level helpers, "shadow" definitions hiding above the clone
pair. The top of the file is where dead helpers hide.

**4c. Verify call sites exist.** For every function, method, or class
involved in the finding, grep across the project for callers:
- `core/` — the main application
- `templates/` — URL-name references (`{% url '<name>' %}`)
- static / JS bundles — client-side references
- `urls.py`, `admin.py`, `management/commands/` — alternative entry points

If a function has **zero** inbound references → add it to
`dormant_candidates` in your output; do **not** call it a duplication
finding.

**4c-bis. Dispatch-dict / registry check (MANDATORY).** Before flagging any
class or module-level callable as "dead" or "low-reference," run the
registry-dispatch check from `knowledge/false-positives.md`. Skipping this
step has historically produced wrong-by-95% confidence scores.

**4d. Diff the bodies.** For each pair that survives the dead-code check,
classify each differing line:

- *truly identical* (same tokens, same semantics) → liftable into a helper
- *superficially similar* (log format, error message, exception policy
  differs) → keep in the caller; lift only the truly-identical middle
- *load-bearing divergence* (e.g. `reclassify=True` vs `False`) → express
  as a keyword-only flag on the helper

**4e. Silent-catch grep.** Grep near each clone for this pattern:

```
except\s+Exception.*:\s*(#[^\n]*)?\n\s*(pass|return|continue)
```

A silent catch adjacent to the clone is a **latent bug risk**. Flag it so
`/fix-workflow` writes a test against the catch before refactoring.

**4f. Decide the fix shape.** Pick exactly one from the table below and
record it as `fix_shape`:

| fix_shape | When |
|---|---|
| `extract_helper` | 2+ methods, 90%+ identical bodies |
| `three_way_helper` | 3+ methods near-identical (higher confidence) |
| `policy_flag_helper` | 2 methods differ on one branch — helper with `*, policy_flag` kwarg |
| `delete_shadow` | Shadow helper strictly mirrors a canonical one |
| `promote_canonical` | Shadow fills a real gap — promote it and retire the others |
| `skip_module_local` | The "shadow" is a legitimate module-local concept |
| `universal_adapter` | Template triplication (N>=3) with minor renames — helper that returns `None` on failure |
| `investigate_cross_file` | Cross-file clone that needs semantic analysis before lifting |
| `apply_canonical_pattern` | Canonical-pattern violation (e.g. `safe_int` adoption) — one concentrated fix |
| `skip_intentional` | Registry/framework dispatch or known-intentional repeat |
| `skip_false_positive` | Superficial match only — bodies are not the same concept |

### Output contract

Write a single JSON file at `{{output_path}}` with this shape:

```json
{
  "finding_id": "{{finding_id}}",
  "investigation_status": "reviewed | false_positive | dormant_suspected | intentional",
  "fix_shape": "<one of the values from the table>",
  "confidence": "low | medium | high",
  "latent_bug_risk": "none | <short description citing file:line>",
  "notes": "2-5 sentence explanation: what you read, what you concluded, anything /fix-workflow needs to know",
  "tests_that_guard_this_area": ["tests.test_X", "tests.test_Y"],
  "dormant_candidates": [
    {
      "file": "<path>",
      "line": <int>,
      "name": "<symbol>",
      "evidence": "zero inbound references in <scopes searched>",
      "reachable_via": "<url pattern / registry / none>",
      "last_touched": "<git sha, date> or null"
    }
  ]
}
```

`dormant_candidates` is a list — leave it empty if you found none.
Do not add keys beyond this schema. Do not wrap the JSON in markdown.

### Rules for your output

1. **Effort estimates** — do not include one. The orchestrator's heuristic
   already produced an `effort_hint`; only override if you have specific
   evidence (e.g. "test fixture needed for X adds ~30 min").
2. **Log format is behavior.** Do not recommend lifting a log line into a
   helper.
3. **Read both bodies** before classifying a shadow helper.
4. **Silent `except Exception`** adjacent to the clone → flag as latent bug
   risk.
5. **Dormant findings go in `dormant_candidates`**, never in `fix_shape`.
6. **Keep `notes` tight.** 2-5 sentences, not a blow-by-blow.

Do not print the JSON to your reply. Write it to `{{output_path}}` and
respond with at most two sentences confirming you wrote the file.
