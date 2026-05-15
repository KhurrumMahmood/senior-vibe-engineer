# Verification procedure + bucket taxonomy — transaction-overreach

This file is loaded by **scouts**, not by the orchestrator. It tells a
verifier exactly what to check for one candidate and how to classify
the result.

## The smell

A Django `transaction.atomic()` block (or `@transaction.atomic`
function) holds a database connection from the pool for as long as its
body runs. If the body does any of the following, the connection is
pinned for seconds-to-minutes while waiting on something the database
doesn't care about:

- HTTP request (`requests.get`, `httpx.post`, `urllib.urlopen`)
- AI/SDK call (Anthropic, OpenAI, `ai_runtime` sidecar)
- Cloud upload (`boto3.put_object`, `s3.upload_file`)
- Subprocess (`subprocess.run`, `os.system`)
- Blocking sleep (`time.sleep`)
- Celery dispatch without `transaction.on_commit` — even with
  `safe_dispatch`, the task can run before commit and read a row that
  doesn't exist yet

Three failure modes follow:

1. **Connection pool starvation.** Under load, every request waiting
   for a free connection blocks. The article that motivated this
   skill describes a fintech payment incident: one `@Transactional`
   method called 8 external APIs, each holding the connection ~22s.
   Five concurrent users blocked the entire pool.
2. **Lost work on rollback.** External work isn't transactional. If
   the DB rollback fires after the HTTP request returns, the side
   effect already happened and can't be undone.
3. **Read-your-own-writes failure.** A Celery task dispatched inside
   a transaction can run before the transaction commits, fail to find
   the row it was given the ID of, and either retry forever or no-op.
   `transaction.on_commit(lambda: task.delay(...))` is the canonical
   fix.

This skill surfaces pre-existing instances of the smell. There is no
matching diff-scoped lint yet — if recurrence justifies one, file a
`/decide` to spec it.

## Bucket definitions

Write exactly one of these into ``bucket`` on your JSON output:

| Bucket | Criteria | Recommendation |
|---|---|---|
| **narrow_transaction** | The slow op happens before any DB write, OR after all DB writes and only consumes (not produces) the locked rows. | `/fix-workflow cluster:<symbol>` — move the slow op outside the `transaction.atomic()` block. |
| **split_transaction** | The block has DB writes both before and after the slow op, but they don't need to be atomic with each other. | `/fix-workflow cluster:<symbol>` — split into two atomic blocks. |
| **defer_via_on_commit** | The slow op is a side-effect-only call (Celery dispatch, audit event, notification, cache invalidation) that could run after commit. | `/fix-workflow cluster:<symbol>` — wrap in `transaction.on_commit(lambda: …)`. |
| **legitimate_long_transaction** | The block must be one atomic transaction AND the slow op genuinely belongs inside (e.g. a transactional outbox row that captures the payload to send, where rollback should also un-queue the send). | Add `# atomic-overreach: <reason>` allow-list marker on the `with` / `def` line. |
| **false_positive** | The flagged helper does not actually do external I/O, OR the Celery dispatch IS wrapped in `transaction.on_commit` (the detector should have caught it but missed a less common shape). | Drop from candidates. Recommend no action. |

### When to choose narrow vs split vs defer

- **Narrow** is the default — most cases are "DB writes don't depend
  on the slow op's return value, just move the slow op to the
  caller". Cheapest refactor; should always be tried first.
- **Split** is for cases where part of the DB write must happen
  before the slow op (e.g. claim a row by setting `status='in_progress'`)
  and another part after (e.g. record the result). Two atomic blocks
  with the slow op between.
- **Defer** is specifically for fire-and-forget side effects: Celery
  dispatch, log writes to an external system, webhook notifications.
  The DB block stays atomic; the side effect runs after commit.

Default to `narrow_transaction` when the choice is unclear — it's the
simplest refactor and can be revisited if it turns out the DB writes
genuinely need to be atomic with the slow op.

## Verification checklist (apply in order)

### 1. Read the enclosing block.

Open the candidate's `file` and read from `block_lineno` through
`block_endline`. For `block_kind: "decorator"`, this is the whole
function body; for `block_kind: "with"`, this is the
`with transaction.atomic():` block.

### 2. Confirm each slow-op hit is genuinely slow.

For each entry in the candidate's `hits` list:

- **`category: http` / `ai` / `cloud` / `subprocess` / `sleep`** —
  these are guaranteed-slow. Proceed to step 3.
- **`category: celery`** — check whether the dispatch is wrapped in
  `transaction.on_commit(lambda: ...)` (the canonical safe pattern).
  If wrapped, this hit is a false positive (the detector should have
  caught it but may have missed a less common shape — e.g. the
  `on_commit` is on a separate line via a callable assigned to a
  variable). Note in `notes` and bucket as `false_positive`.
- **`category: network_helper`** — open the helper's definition and
  read it. Does it do HTTP/AI work internally?
  - **Yes** → treat as a real `http`/`ai` hit and proceed.
  - **No** (the helper just builds URLs, computes hashes, etc.) →
    bucket as `false_positive` with
    `false_positive_reason: "helper_does_not_do_io"` and the helper
    name in `notes`.

### 3. Check for the `# atomic-overreach:` allow-list marker.

The detector honors `# atomic-overreach: <reason>` and drops marked
hits before writing `hits.jsonl`. **A hit surfacing in the candidate
means no marker was found** anywhere in the block range. If the scout
spots a marker the detector missed (e.g. on a continuation line above
the block start), bucket as `legitimate_long_transaction` with
`false_positive_reason: "atomic_overreach_marker_missed"`.

### 4. Classify the candidate's role.

For genuine overreach:

- **Narrow test.** Could the slow op move outside the `with` block
  and the DB writes still work? Specifically: do the DB writes
  consume the slow op's *return value*, or do they just happen to
  be in the same function?
  - DB writes don't depend on the slow op's return → `narrow_transaction`.
  - DB writes consume the return → check Split test.
- **Split test.** Are the DB writes naturally divisible? Specifically:
  is there a "claim" write before the slow op (`status='processing'`)
  and a "record result" write after (`result=..., status='complete'`)?
  - Yes → `split_transaction`.
- **Defer test.** Is the slow op a side effect that could run after
  the transaction commits? Specifically: a Celery dispatch, an
  external notification, a cache invalidation?
  - Yes → `defer_via_on_commit`.
- **Legitimate test.** Must the DB block stay atomic AND must the
  slow op happen inside it? This is rare. The canonical example is a
  transactional outbox: a row capturing "we will send this payload"
  must be atomic with the business writes that justify it. The actual
  send happens later (typically via `on_commit` or a separate
  dispatcher), but the *capture* row is inside the transaction.
  - Yes → `legitimate_long_transaction`.

### 5. Pick `recommendation_hint_symbol`.

For bucketed candidates that need a refactor, the report's next-action
section needs a symbol to pass to `/fix-workflow cluster:<symbol>`.
This is almost always the candidate's own `enclosing_symbol`.

## Output schema

Write a JSON file at `{{output_path}}`:

```json
{
  "candidate_id": "transaction-overreach-0001",
  "file": "core/views/scrape_testing.py",
  "enclosing_symbol": "scrape_test_view",
  "block_kind": "with",
  "block_lineno": 222,
  "bucket": "narrow_transaction",
  "confidence": "high",
  "hit_count": 1,
  "categories": ["http"],
  "recommendation_hint_symbol": "scrape_test_view",
  "notes": "1-3 sentence scout summary: which slow op, which bucket, why.",
  "false_positive_reason": null
}
```

`false_positive_reason` is set when `bucket` is `false_positive` or
`legitimate_long_transaction`. One of:

- `helper_does_not_do_io` — the flagged helper builds URLs / computes
  data, no real I/O.
- `on_commit_wrapped` — the dispatch is inside
  `transaction.on_commit(lambda: ...)`; detector missed it.
- `atomic_overreach_marker_missed` — scout spotted the allow-list
  marker but the detector missed it.
- `transactional_outbox` — the slow op (or its capture row) genuinely
  needs to be atomic with the DB writes.

## Rules for your output

1. **Default conservatively.** When the scout cannot resolve whether
   a helper is doing real external work, bucket as `false_positive`
   with the helper name in `notes`. Better to under-report than to
   recommend a refactor that breaks correctness. If the helper later
   gets refactored to do HTTP, the next scan will catch it.
2. **Keep `notes` tight.** 1 to 3 sentences. The hit evidence carries
   the detail.
3. **Never propose the refactor yourself.** Your job is to bucket.
   The `/fix-workflow cluster:<symbol>` skill owns the
   narrow / split / defer proposal.
4. **Respect the `# atomic-overreach:` allow-list.** It is a deliberate
   decision; `legitimate_long_transaction` is not a failure state.
5. **Recognize the row-locking pattern.** A block that opens with
   `<Model>.objects.select_for_update().get(...)` and only mutates
   the locked row + adjacent rows is the canonical "I need atomicity
   for a small critical section" pattern. If the only "slow" hit is
   a Celery dispatch wrapped in `transaction.on_commit`, that's
   `false_positive`, not a real finding.
