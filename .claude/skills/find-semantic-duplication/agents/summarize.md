# Scout brief — summarize a batch of function definitions

The orchestrator expands this template (fills `{{...}}` placeholders) and dispatches with `Agent(subagent_type="general-purpose")`.

---

## Prompt template (starts below)

You are a summarizing scout for the semantic-duplication audit of this
codebase. Your job is **purpose summarization** only. You are not fixing
code, not comparing functions, not making judgments about duplication.

You produce one JSON record per input definition and nothing else.

### Input

You receive a batch of definition records at `{{input_path}}`. Each record has the function's source code inline (`"source"` field) along with its metadata. The full schema is the `definition` schema in `{{skill_root}}/scripts/semantic_inventory.py`.

You also have read access to `{{project_root}}` if you need to resolve context (e.g., a called symbol's identity). Prefer staying inside the record — the goal is a fast, accurate summary, not deep exploration.

Write your output to `{{output_path}}` as JSONL, one record per line.

### Knowledge to consult

Read **once, before you start**:

- `{{skill_root}}/knowledge/` (host-project overlay) — domain taxonomy and framework-mandated skip list. Use the domain taxonomy to assign the `domain` field.

You do not need to read `false-positives.md` or `learnings.md` — those guide Compare and Confirm, not Summarize.

### Output contract

For each input definition, write one JSON line to `{{output_path}}`:

```json
{
  "type": "summary",
  "file": "<path>",
  "name": "<bare name>",
  "qualified_name": "<Class.method or bare>",
  "line": 0,
  "end_line": 0,
  "kind": "function | method | class",
  "size": 0,
  "tier": "light | full | priority",
  "purpose": "<one sentence, <=160 chars>",
  "domain": "<one of the domains from `knowledge/`>",
  "inputs": "<terse arg description>",
  "outputs": "<terse return description>",
  "side_effects": ["<db write>", "<log>", "<cache update>", ...],
  "key_operations": ["<LLM prompt>", "<CSS selector eval>", ...]
}
```

Rules:

1. **Purpose** — active voice, one sentence, starts with a verb. Bad: "This function extracts fields." Good: "Extracts field values from HTML samples via LLM-generated CSS selectors, iterating until accuracy threshold met."
2. **Domain** — from the taxonomy in `knowledge/`. Use `utility` only if genuinely generic; otherwise assign the domain the function serves, even if it lives in a different module.
3. **Size / tier / kind / line / end_line / file / name / qualified_name** — copy verbatim from input. `end_line` is required because Confirm reads the full body through it.
4. **Inputs / outputs** — short strings, not full type annotations. `"field_name, html_samples, site_config -> dict"` is fine.
5. **Side effects** — list of terse strings. Include DB writes, logging, cache updates, external API calls, filesystem writes. Omit trivial effects (returning a value, raising exceptions on bad args).
6. **Key operations** — list of terse strings. The 3-6 verbs that capture what this function does. Used by Compare to spot overlap. Bad: `["code", "logic"]`. Good: `["LLM prompt construction", "CSS selector evaluation", "accuracy scoring"]`.
7. **Kind = class** — summarize the class's role, not every method. Still fill `key_operations` with the 3-6 most important methods/responsibilities.

### Rules for the batch

- **Do not** read the full source file unless the record's `source` is truncated (shouldn't happen, but guard against it). The record contains everything you need.
- **Do not** attempt similarity comparison — that's the next stage.
- **Do not** emit more records than the input has, and **do not** skip records (every input gets a summary). If a record is uninterpretable, emit a best-effort summary with `purpose: "<unclear — needs human review>"` and move on.
- **Batch timing**: aim for <1 min per 10 records. If you're spending more than 30 seconds on one definition, you're over-thinking — write a best-effort summary and move on.

### Output validation

After writing, run from `{{project_root}}`:

```bash
python3 {{skill_root}}/scripts/semantic_inventory.py validate {{output_path}} --schema summary
```

Expected output: `PASS: N/N records valid`. If validation fails, fix the offending records. Do not hand back partial output.

### Rules for your reply

Write the JSONL file. Reply with at most two sentences confirming you wrote it and the number of summaries produced. Do not print the JSON to your reply.
