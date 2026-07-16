from app.models import Job

def is_pending(job: Job):
    return job.status == "pending"

def has_case_variant(job: Job):
    return job.status == "Pending"

def is_done(job: Job):
    return "done" == job.status

def vendor_bridge(job: Job):
    return job.status == "vendor_pending"

def start(job: Job):
    job.status = "running"
