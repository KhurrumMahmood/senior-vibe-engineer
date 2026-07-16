from dataclasses import dataclass


@dataclass
class Job:
    STATUS_VALUES = ("pending", "running")
    status: str = "pending"


def is_pending(job: Job) -> bool:
    return job.status == "pending"


def start(job: Job) -> None:
    job.status = "running"


def vendor_bridge(job: Job) -> bool:
    return job.status == "vendor_queued"


if __name__ == "__main__":
    job = Job()
    assert is_pending(job)
    start(job)
    assert job.status == "running"
