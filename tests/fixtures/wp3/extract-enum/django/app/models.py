from django.db import models

STATUS_CHOICES = (("pending", "Pending"), ("running", "Running"), ("done", "Done"))

class Job(models.Model):
    status = models.CharField(max_length=16, default="pending", choices=STATUS_CHOICES)
