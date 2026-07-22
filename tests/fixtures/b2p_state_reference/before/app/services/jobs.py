from app.models.jobs import Job


def start(job: Job) -> bool:
    job.status = "queued"
    return job.status == "queued"


def can_finish(job: Job) -> bool:
    return job.status in ("queued", "running")


def is_done(job: Job) -> bool:
    return "done" == job.status
