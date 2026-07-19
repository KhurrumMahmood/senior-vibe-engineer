from app.models.jobs import Job, JobStatus


def start(job: Job) -> bool:
    job.status = JobStatus.QUEUED
    return job.status == JobStatus.QUEUED


def can_finish(job: Job) -> bool:
    return job.status in (JobStatus.QUEUED, JobStatus.RUNNING)


def is_done(job: Job) -> bool:
    return JobStatus.DONE == job.status
