from django.db import models


class RawEvent(models.Model):
    id = None
    repo_id = models.BigIntegerField()
    sha = models.BinaryField(max_length=20)
    observed_at = models.DateTimeField()

    class Meta:
        db_table = "raw_events"
        constraints = [
            models.UniqueConstraint(
                fields=["repo_id", "sha"],
                name="uniq_repo_sha",
            ),
        ]
        indexes = [
            models.Index(fields=["repo_id"]),
        ]
