# Proposal — extract-enum: Job.status

## Proposed authority

```python
class JobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    DONE = "done", "Done"
```

Update `Job.status` to `choices=JobStatus.choices` and replace every first-party
assignment/comparison in `app/services/jobs.py` with a `JobStatus` member. Keep
the raw vendor comparison only at `app/integrations/vendor.py` with its reasoned
`# noqa: stringly-status:` boundary.

## Reviewed caller changes

| Symbol | Before | After |
|---|---|---|
| `start` | `job.status = "queued"` | `job.status = JobStatus.QUEUED` |
| `can_finish` | `job.status in ("queued", "running")` | `job.status in (JobStatus.QUEUED, JobStatus.RUNNING)` |
| `is_done` | `"done" == job.status` | `JobStatus.DONE == job.status` |

## Stop condition

`stringly-status` is red on the before state and green on the reviewed after
state, while the vendor boundary remains a reasoned exception.
