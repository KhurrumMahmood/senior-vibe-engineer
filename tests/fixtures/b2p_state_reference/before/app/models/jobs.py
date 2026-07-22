from django.db import models


class Job(models.Model):
    status = models.CharField(max_length=16, default="queued")
