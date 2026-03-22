import uuid

from django.db import models
from django.utils import timezone


class TaskJobStatus(models.TextChoices):
    READY = "READY"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    SUCCESSFUL = "SUCCESSFUL"


class TaskWorkerStatus(models.TextChoices):
    STARTING = "STARTING"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    DEAD = "DEAD"


class TaskWorker(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    worker_name = models.CharField(max_length=100, unique=True)
    queue_name = models.CharField(
        max_length=100, default="default", db_index=True)
    hostname = models.CharField(max_length=255)
    pid = models.IntegerField(db_index=True)
    status = models.CharField(
        max_length=16,
        choices=TaskWorkerStatus.choices,
        default=TaskWorkerStatus.STARTING,
        db_index=True,
    )
    current_job = models.ForeignKey(
        "task_queue.TaskJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_workers",
    )
    stop_requested = models.BooleanField(default=False)
    heartbeat_at = models.DateTimeField(default=timezone.now, db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    stopped_at = models.DateTimeField(null=True, blank=True)
    last_seen_error = models.TextField(blank=True, default="")
    model_claims = models.JSONField(default=dict, blank=True)
    claim_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["queue_name", "status"]),
            models.Index(fields=["heartbeat_at"]),
        ]
        ordering = ["worker_name"]

    def __str__(self):
        return f"{self.worker_name} ({self.status})"


class TaskJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    task_path = models.CharField(max_length=255, db_index=True)

    queue_name = models.CharField(
        max_length=100, default="default", db_index=True)
    priority = models.IntegerField(default=0, db_index=True)

    run_after = models.DateTimeField(null=True, blank=True, db_index=True)
    max_retries = models.IntegerField(default=3)
    retry_count = models.IntegerField(default=0)

    status = models.CharField(
        max_length=12,
        choices=TaskJobStatus.choices,
        default=TaskJobStatus.READY,
        db_index=True,
    )
    enqueued_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)

    args = models.JSONField(default=list, blank=True)
    kwargs = models.JSONField(default=dict, blank=True)

    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)

    worker = models.ForeignKey(
        TaskWorker,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "queue_name",
                         "-priority", "enqueued_at"]),
            models.Index(fields=["queue_name", "run_after"]),
            models.Index(fields=["status", "run_after"]),
        ]
        ordering = ["-priority", "enqueued_at"]

    def __str__(self):
        return f"TaskJob({self.task_path}, {self.status})"
