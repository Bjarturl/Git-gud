import os
import signal
import socket

from django.utils import timezone

from apps.task_queue.models import TaskJob, TaskJobStatus, TaskWorker, TaskWorkerStatus


def register_worker(worker_name: str, queue_name: str) -> TaskWorker:
    worker, _ = TaskWorker.objects.update_or_create(
        worker_name=worker_name,
        defaults={
            "queue_name": queue_name,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "status": TaskWorkerStatus.STARTING,
            "current_job": None,
            "stop_requested": False,
            "heartbeat_at": timezone.now(),
            "started_at": timezone.now(),
            "stopped_at": None,
            "last_seen_error": "",
        },
    )
    return worker


def heartbeat_worker(worker: TaskWorker, *, status: str | None = None):
    worker.heartbeat_at = timezone.now()
    if status is not None:
        worker.status = status
        worker.save(update_fields=["heartbeat_at", "status", "updated_at"] if hasattr(worker, "updated_at") else ["heartbeat_at", "status"])
    else:
        worker.save(update_fields=["heartbeat_at"])


def set_worker_job(worker: TaskWorker, job: TaskJob | None, status: str):
    worker.current_job = job
    worker.status = status
    worker.heartbeat_at = timezone.now()
    worker.save(update_fields=["current_job", "status", "heartbeat_at"])


def stop_worker(worker: TaskWorker, *, status: str, error: str = ""):
    worker.status = status
    worker.current_job = None
    worker.stopped_at = timezone.now()
    worker.heartbeat_at = timezone.now()
    worker.last_seen_error = error
    worker.save(update_fields=["status", "current_job", "stopped_at", "heartbeat_at", "last_seen_error"])


def request_worker_stop(worker: TaskWorker):
    worker.stop_requested = True
    worker.status = TaskWorkerStatus.STOPPING
    worker.save(update_fields=["stop_requested", "status"])


def kill_worker_process(worker: TaskWorker, sig=signal.SIGTERM):
    os.kill(worker.pid, sig)


def recover_stale_workers_and_jobs(stale_after_seconds: int = 60) -> int:
    threshold = timezone.now() - timezone.timedelta(seconds=stale_after_seconds)

    stale_workers = list(
        TaskWorker.objects.filter(
            status__in=[
                TaskWorkerStatus.STARTING,
                TaskWorkerStatus.IDLE,
                TaskWorkerStatus.RUNNING,
                TaskWorkerStatus.STOPPING,
            ],
            heartbeat_at__lt=threshold,
        )
    )

    if not stale_workers:
        return 0

    stale_ids = [worker.id for worker in stale_workers]

    TaskJob.objects.filter(
        status=TaskJobStatus.RUNNING,
        worker_id__in=[str(worker_id) for worker_id in stale_ids],
    ).update(
        status=TaskJobStatus.READY,
        started_at=None,
        last_attempted_at=None,
        worker=None,
    )

    TaskWorker.objects.filter(id__in=stale_ids).update(
        status=TaskWorkerStatus.DEAD,
        current_job=None,
        stopped_at=timezone.now(),
    )

    return len(stale_workers)