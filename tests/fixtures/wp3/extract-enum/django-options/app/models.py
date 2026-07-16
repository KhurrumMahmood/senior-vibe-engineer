from django.db import models


STATE_CHOICES = (
    ("pending", "Awaiting triage"),
    ("running", "In progress"),
)


class Ticket(models.Model):
    state = models.CharField(
        max_length=32,
        default="pending",
        choices=STATE_CHOICES,
        null=True,
        blank=True,
        db_index=True,
        help_text="Workflow state",
    )
