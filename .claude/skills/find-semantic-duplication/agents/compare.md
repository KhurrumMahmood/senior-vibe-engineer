# Scout brief — compare summaries in one domain group

The orchestrator expands this template (fills `{{...}}` placeholders) and dispatches with `Agent(subagent_type="general-purpose")`.

---

## Prompt template (starts below)

You are a comparator scout for the semantic-duplication audit of this
codebase. Your job is **pairwise nomination** within a domain group:
read summaries, find pairs that plausibly solve the same problem, and
write a candidate file.

You are not confirming; you are nominating. Lower bar. Better to over-nominate than to miss — the Confirm stage has full source code and will filter.

### Input

The orchestrator writes a prompt file at `{{prompt_path}}`. It conforms to the `comparison_prompt` schema in `scripts/semantic_inventory.py` and contains:

- `domain` — the domain group you're scoring (e.g., `"extraction"`)
- `items` — array of summary records (from `summaries.jsonl`, filtered to this domain)
- `output_schema` — the exact schema your candidates must follow

Write your output to `{{output_path}}` as JSON (not JSONL — a single `{ "candidates": [...] }` object).

### Knowledge to consult

In this order:

1. `{{skill_root}}/knowledge/` (host-project overlay) — framework-mandated patterns to skip, known semantic-duplication suspects, split-by-design exclusions.
2. `{{skill_root}}/knowledge/false-positives.md` — the **seven rejection classes**. Apply classes 1 (caller-callee), 2 (framework pattern), 4 (test mock), 5 (token-similar — belongs in find-duplication) **in this stage**; leave 3, 6, 7 for Confirm (they need source).
3. `{{skill_root}}/knowledge/learnings.md` — Rules R1 (workflow-first), R2 (summary ≠ body), R7 (cross-domain pairs), R9 (union-find), R10 (nominate liberally).

### Investigation steps

**C1. Load the prompt.** Read `{{prompt_path}}`. Note the domain and how many items are in the group. If items > 40, you'll need a two-pass scan (step C4).

**C2. Skim-filter.** Before scoring pairs, drop items that match a cheap rejection:

- Named `get`/`post`/`put`/`delete`/`patch`/`dispatch`/`handle`/`form_valid` etc. (framework-mandated; `knowledge/` lists the full set).
- Tier = `skip` (<11 lines — excluded from full summaries anyway, but guard against stragglers).
- `kind = "class"` when the purpose reads "Django model", "form", "admin", or "migration".
- Test-mock signals in purpose/name (`Mock`, `Fake`, `stub_`, `fixture_`).

Record a count of filtered items; you'll report it in output metadata.

**C3. Pairwise scoring (≤40 items).** For every pair of surviving items, read both summaries and score 0-5 using the rubric below. Record every pair that scores ≥3. A pair is `(a_index, b_index)` — indices into the `items` array (0-based).

**C4. Two-pass for large groups (>40 items).** First pass: quick `purpose`-text scan — flag any pair with ≥2 shared content words (excluding domain stop-words like "extract", "parse", "HTML"). Second pass: full 0-5 scoring on flagged pairs.

**C5. Cross-workflow check.** If an item's `key_operations` include terms like "orchestrate", "entry", or "workflow", and its purpose describes an end-to-end pipeline, mark the candidate as `"level": "workflow"` instead of `"level": "function"`. Workflow-level candidates get higher priority.

**C6. Write candidates.** One candidate per pair with score ≥3. If 0 pairs qualify, write `{"candidates": []}` — an empty result is still a valid result.

### Scoring rubric (0-5)

- **0** — Unrelated. Different end products entirely.
- **1** — Same domain, different end products (e.g., "export to Excel" vs "export to CSV" — related but distinct).
- **2** — Same end product, substantially different approaches (sync vs async pipeline for the same result).
- **3** — Same end product, similar high-level steps, different internal logic. **Nomination threshold.**
- **4** — Same end product, same step sequence, different implementations at some steps. One could plausibly be refactored to share code with the other.
- **5** — Near-identical purpose, same shape, different code.

Light-tier items (11-30 lines) require ≥4 to be nominated. Full/Priority tier requires ≥3.

### Output contract

Write `{{output_path}}` as a JSON object:

```json
{
  "domain": "<domain>",
  "items_input": 0,
  "items_after_skim_filter": 0,
  "candidates": [
    {
      "id": "<domain>-C<n>",
      "source": "function",
      "level": "function | workflow",
      "a": {"file": "<path>", "name": "<name>", "qualified_name": "<Class.method>", "line": 0, "end_line": 0, "size": 0},
      "b": {"file": "<path>", "name": "<name>", "qualified_name": "<Class.method>", "line": 0, "end_line": 0, "size": 0},
      "similarity": 3,
      "rationale": "<1-2 sentences citing shared key_operations or purpose terms>"
    }
  ]
}
```

IDs are local to your domain group (`extraction-C1`, `extraction-C2`, …). The collapse stage re-numbers globally.

### Rules for your reply

- Write the JSON file. Reply with at most two sentences: number of candidates nominated, and one-sentence impression of the group ("dense cluster around JSON-LD parsing" / "sparse, mostly unrelated utilities" / etc.).
- Do not print candidate JSON in your reply.
- Do not explore source files — the Confirm stage does that. Your job is fast nomination from summaries.
