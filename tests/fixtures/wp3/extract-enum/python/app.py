from dataclasses import dataclass


@dataclass
class Job:
    status: str = "pending"


def is_pending(job: Job) -> bool:
    return job.status == "pending"


def start(job: Job) -> None:
    job.status = "running"


if __name__ == "__main__":
    job = Job()
    assert is_pending(job)
    start(job)
    assert job.status == "running"
