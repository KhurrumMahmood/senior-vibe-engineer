# Profile — job__status

## Location

- Field: `Job.status`
- File: `app/models/jobs.py`
- Current kwargs: `max_length=16`, default `"queued"`
- Status: found

## Enum proposal

- Class name: `JobStatus`
- Canonical vs reusable: `new`
- Default member: `JobStatus.QUEUED`

## Caller classification

- confirmed_state_compare: 4
- third_party_bridge: 1 (kept at the named vendor boundary)

## Caller migration table

| File | Symbol | Before | After |
|---|---|---|---|
| `app/services/jobs.py` | `start` | `job.status = "queued"` | `job.status = JobStatus.QUEUED` |
| `app/services/jobs.py` | `can_finish` | `job.status in ("queued", "running")` | `job.status in (JobStatus.QUEUED, JobStatus.RUNNING)` |
| `app/services/jobs.py` | `is_done` | `"done" == job.status` | `JobStatus.DONE == job.status` |
