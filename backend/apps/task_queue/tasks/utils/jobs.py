import logging
import os
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from apps.task_queue.models import TaskJobStatus, TaskJob, TaskWorker, TaskWorkerStatus


CLAIM_TTL_MINUTES = 30
ACTIVE_WORKER_STATUSES = [
    TaskWorkerStatus.STARTING,
    TaskWorkerStatus.IDLE,
    TaskWorkerStatus.RUNNING,
    TaskWorkerStatus.STOPPING,
]


def setup_job_logger(job_id: str, task_name: str | None = None) -> tuple[logging.Logger, logging.FileHandler, str]:
    log_dir = os.path.join(settings.BASE_DIR, 'apps', 'task_queue', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    if task_name:
        clean_name = task_name.replace(
            'apps.task_queue.tasks.', '').replace('_task', '')
        filename = f"{clean_name}_{job_id}.log"
    else:
        filename = f"task_{job_id}.log"

    log_file = os.path.join(log_dir, filename)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'))

    job_logger = logging.getLogger(f"job_{job_id}")
    job_logger.setLevel(logging.INFO)
    job_logger.addHandler(file_handler)
    job_logger.propagate = False

    github_logger = logging.getLogger('clients.github')
    github_logger.addHandler(file_handler)

    return job_logger, file_handler


def close_job_logger(job_logger: logging.Logger, file_handler: logging.FileHandler):
    github_logger = logging.getLogger('clients.github')
    github_logger.handlers = [
        h for h in github_logger.handlers if h is not file_handler]

    job_logger.handlers = [
        h for h in job_logger.handlers if h is not file_handler]
    file_handler.close()


def is_cancelled(job_id: str):
    return TaskJob.objects.get(id=job_id).status == TaskJobStatus.CANCELLED


def get_job_worker(job_id: str) -> TaskWorker:
    return TaskJob.objects.select_related("worker").get(id=job_id).worker


def reset_worker_claims(worker: TaskWorker):
    worker.model_claims = {}
    worker.claim_expires_at = None
    worker.save(update_fields=["model_claims", "claim_expires_at"])


def get_active_claimed_ids(model_name: str, exclude_worker_id=None) -> set[int]:
    now = timezone.now()

    workers = TaskWorker.objects.filter(
        status__in=ACTIVE_WORKER_STATUSES,
        claim_expires_at__gt=now,
    )

    if exclude_worker_id:
        workers = workers.exclude(id=exclude_worker_id)

    claimed_ids = set()

    for worker in workers.only("id", "model_claims"):
        ids = (worker.model_claims or {}).get(model_name, [])
        claimed_ids.update(ids)

    return claimed_ids


def set_worker_model_claims(
    worker: TaskWorker,
    model_name: str,
    ids: list[int],
    ttl_minutes: int = CLAIM_TTL_MINUTES,
):
    claims = worker.model_claims or {}
    claims[model_name] = ids
    worker.model_claims = claims
    worker.claim_expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
    worker.save(update_fields=["model_claims", "claim_expires_at"])


def refresh_worker_claims(
    worker: TaskWorker,
    ttl_minutes: int = CLAIM_TTL_MINUTES,
):
    worker.claim_expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
    worker.save(update_fields=["claim_expires_at"])


def clear_worker_model_claims(worker: TaskWorker, model_name: str):
    claims = worker.model_claims or {}
    claims.pop(model_name, None)
    worker.model_claims = claims

    if claims:
        worker.save(update_fields=["model_claims"])
    else:
        worker.claim_expires_at = None
        worker.save(update_fields=["model_claims", "claim_expires_at"])
