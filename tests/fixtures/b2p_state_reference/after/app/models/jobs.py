from django.db import models


class JobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    DONE = "done", "Done"


class Job(models.Model):
    status = models.CharField(
        max_length=16,
        choices=JobStatus.choices,
        default=JobStatus.QUEUED,
    )
