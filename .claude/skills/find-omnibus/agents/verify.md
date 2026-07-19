# Scout brief — verify one omnibus-module candidate

This file is a **prompt template** the orchestrator expands and sends through
the host's standard sub-agent capability. Placeholders are double-brace
`{{name}}`.

Fresh sub-agent, no prior context. Everything the scout needs is either
inline below or in the knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are verifying **one** candidate flagged as a possible omnibus
module in this codebase. Your job is to decide
whether the detected clusters are genuine independent domains (the
file really is omnibus), facets of one job (a false positive), or
coordination for one product workflow that should be mapped before
file decomposition.

You are **not** editing or splitting code. You produce a single
classification JSON file and nothing else.

### Candidate to verify

```json
{{candidate_json}}
```

Project root (absolute): `{{project_root}}`
Skill root: `{{skill_root}}`
Write your output here: `{{output_path}}`

### Knowledge you MUST consult

Read in this order:

1. `{{skill_root}}/knowledge/verification.md` — bucket definitions,
   the refactor-subsystem §1.2.5 "facets vs domains" evaluation rule,
   false-positive hints, the deletion test, locality guidance, and output
   schema. This bundled file is the complete knowledge dependency.

### Verification procedure (follow in order — do not skip)

#### V1. Read the candidate file

Open `{{project_root}}/<candidate.file>` and scan it end-to-end.
Summarize in your head: "This file contains X, Y, Z." Do NOT copy the
auto-generated SRP sentence — write your own one-sentence summary
from what you actually read.

#### V2. Classify each cluster

For each cluster in `candidate.clusters`, decide:

- **Domain** — an independently-understandable concept you could
  explain to a new hire without mentioning the others.
- **Facet** — a different execution path, pipeline step, or lifecycle
  phase of a single concept (e.g., "bulk vs single-URL crawling",
  "pivot assembly vs Excel formatting", "create/pause/resume/cancel
  job lifecycle"). Facets count as **0 "and"s** per refactor-subsystem
  §1.2.5.

Record `domains_confirmed` (list of cluster names that are genuine
domains) and `facets_collapsed` (list of cluster names that are
facets, with a short note on which domain they belong to).

#### V3. Count confirmed domains

Count confirmed domains after collapsing facets.

Also note whether the candidate combines security-sensitive or
side-effect-heavy authority (credentials, admin/staff APIs, CSRF
mutation, diagnostics, command/network calls, persistence, raw SQL,
task dispatch, imports/exports, or filesystem writes). The detector's
`risk_signals` are hints, not proof; confirm them from the file.

#### V4. Bucket the candidate

| Confirmed domain count | Bucket |
|---|---|
| 3 or more | `confirmed_omnibus` |
| 2 | `borderline` (human call — could decompose, could leave) |
| 0 or 1 | `facets_not_domains` |

If there are 3+ domains but they are mainly workflow coordination
(routes, template selection, sidebar/dashboard status, redirects, boot
payload context) rather than domain logic, use
`coordination_omnibus`.

If you catch a **known false-positive shape** (see the bundled
`knowledge/verification.md` list — thin re-export `__init__.py`, directory-package shims,
migrations aggregator, urls.py), bucket as `facets_not_domains` with
`false_positive_reason` naming the shape.

#### V5. Sketch a decomposition (only for `confirmed_omnibus`)

Propose 3–8 new files (directory-package layout). For each, list the
candidate symbols that would move. Format:

```json
[
  {"new_file": "core/views/sitemaps/discovery.py",
   "symbols": ["RunDiscoveryView", "DiscoverySamplesView", ...]},
  ...
]
```

This is a sketch for the human to refine — don't try to be exhaustive
about every helper. Focus on the obvious top-level groupings.

Then write `decomposition_depth_note`: one sentence explaining whether
the sketch improves locality and passes the deletion test. If the
bucket is not `confirmed_omnibus`, set it to `null`.

For `coordination_omnibus`, keep `decomposition_sketch` to registry /
context / status ownership targets rather than moved domain symbols,
and set `recommendation` to `map_workflow`.

### Rules you MUST respect

1. **Read the file before classifying.** The detector's SRP sentence
   is auto-generated from symbol names; it can be misleading. Your
   verdict must come from reading the actual code.
2. **Facets collapse aggressively.** When in doubt between "domain"
   and "facet," prefer facet. The refactor-subsystem §1.2.5 worked
   examples all err toward "facet" — only split when the domains are
   genuinely unrelated.
2a. **Risk can raise priority but not invent domains.** A settings/admin
   file with credentials and command diagnostics deserves earlier human
   attention than its LOC suggests, but it is still only omnibus when it
   has independently-understandable domains after facet collapse.
3. **Do not estimate LOC savings.** The report stage does not need
   that and scouts regularly over-estimate.
4. **Flag directory-package shims.** An `__init__.py` whose body is
   just `from .foo import *` is never omnibus regardless of symbol
   count. Same for `urls.py` and migrations aggregators.
5. **Keep `notes` tight** — 1 to 3 sentences.

### Output contract

Write a single JSON file at `{{output_path}}` matching the schema in
`verification.md`:

```json
{
  "candidate_id": "{{candidate_id}}",
  "file": "<candidate file>",
  "bucket": "confirmed_omnibus | borderline | coordination_omnibus | facets_not_domains",
  "domains_confirmed": ["discovery", "crud", "import", "filter_state"],
  "facets_collapsed": [
    {"cluster": "control", "belongs_to": "crawl_lifecycle"}
  ],
  "srp_rewrite": "This file handles sitemap discovery and sitemap CRUD and URL import and filter state.",
  "decomposition_sketch": [
    {"new_file": "core/views/sitemaps/discovery.py",
     "symbols": ["..."]}
  ],
  "decomposition_depth_note": "Deletion test passes because each file owns one independently-understandable domain and avoids private-helper calls into sibling domains.",
  "false_positive_reason": null,
  "notes": "1-3 sentence scout summary",
  "recommendation": "decompose | map_workflow | keep | borderline"
}
```

`decomposition_sketch` is `[]` for non-`confirmed_omnibus` buckets
except `coordination_omnibus`, where it may list workflow ownership
targets.
`false_positive_reason` is `null` unless the bucket is
`facets_not_domains`.

Do not print the JSON to your reply. Write it to `{{output_path}}` and
respond with at most two sentences confirming you wrote the file (and,
if relevant, one sentence flagging anything surprising the
orchestrator should know).
