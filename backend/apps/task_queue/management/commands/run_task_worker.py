import logging
import signal
import threading
import time
import traceback
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.module_loading import import_string

from apps.task_queue.models import TaskJob, TaskJobStatus, TaskWorkerStatus
from apps.task_queue.worker_runtime import (
    heartbeat_worker,
    recover_stale_workers_and_jobs,
    register_worker,
    set_worker_job,
    stop_worker,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a task queue worker to process background tasks."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shutdown = False
        self.worker = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--queues",
            nargs="*",
            default=["default"],
            help="Queue names to process (default: ['default'])",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=1.0,
            help="Seconds to sleep when no work is available (default: 1.0)",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one task and exit",
        )
        parser.add_argument(
            "--worker-id",
            default=None,
            help="Worker identifier (defaults to a random value)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging",
        )
        parser.add_argument(
            "--stale-after",
            type=int,
            default=60,
            help="Seconds after which a worker is considered stale",
        )
        parser.add_argument(
            "--heartbeat-interval",
            type=int,
            default=10,
            help="Seconds between worker heartbeats while idle/running",
        )

    def handle(self, *args, **options):
        if options["verbose"]:
            logging.basicConfig(level=logging.INFO)

        queues = options["queues"]
        sleep_seconds = options["sleep"]
        once = options["once"]
        stale_after = options["stale_after"]
        heartbeat_interval = options["heartbeat_interval"]
        worker_id = options["worker_id"] or f"worker-{get_random_string(8)}"
        primary_queue = queues[0] if queues else "default"

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        recovered = recover_stale_workers_and_jobs(stale_after)
        if recovered:
            logger.warning(f"Recovered {recovered} stale worker(s) on startup")

        self.worker = register_worker(worker_id, primary_queue)

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting task worker {worker_id} for queues: {', '.join(queues)}"
            )
        )

        processed = 0
        last_idle_heartbeat = None

        try:
            while not self.shutdown:
                self.worker.refresh_from_db(
                    fields=["stop_requested", "status"])
                if self.worker.stop_requested:
                    logger.warning(
                        f"Stop requested for worker {self.worker.worker_name}")
                    break

                now = time.monotonic()
                if (
                    last_idle_heartbeat is None
                    or now - last_idle_heartbeat >= heartbeat_interval
                ):
                    heartbeat_worker(self.worker, status=TaskWorkerStatus.IDLE)
                    last_idle_heartbeat = now

                job = self._claim_next_job(worker=self.worker, queues=queues)
                if not job:
                    if once:
                        break
                    time.sleep(sleep_seconds)
                    continue

                try:
                    set_worker_job(self.worker, job, TaskWorkerStatus.RUNNING)
                    self._execute_job(
                        job=job,
                        worker=self.worker,
                        heartbeat_interval=heartbeat_interval,
                    )
                    processed += 1

                    if once:
                        break

                except KeyboardInterrupt:
                    self.stdout.write(
                        self.style.WARNING(
                            "Received interrupt signal, shutting down...")
                    )
                    break

                except Exception as exc:
                    logger.error(
                        f"Unexpected error processing job {job.id}: {exc}")
                    self._mark_job_failed(
                        job, str(exc), traceback.format_exc())

                finally:
                    set_worker_job(self.worker, None, TaskWorkerStatus.IDLE)
                    last_idle_heartbeat = time.monotonic()

        except Exception as exc:
            logger.error(f"Worker {worker_id} crashed: {exc}")
            if self.worker:
                stop_worker(
                    self.worker, status=TaskWorkerStatus.DEAD, error=str(exc))
            raise

        if self.worker:
            stop_worker(self.worker, status=TaskWorkerStatus.STOPPED)

        self.stdout.write(
            self.style.SUCCESS(
                f"Worker {worker_id} processed {processed} task(s)")
        )

    def _signal_handler(self, signum, frame):
        self.stdout.write(
            self.style.WARNING(
                f"Received signal {signum}, shutting down gracefully..."
            )
        )
        self.shutdown = True
        if self.worker:
            self.worker.stop_requested = True
            self.worker.status = TaskWorkerStatus.STOPPING
            self.worker.save(update_fields=["stop_requested", "status"])

    def _claim_next_job(self, *, worker, queues: list) -> Optional[TaskJob]:
        now = timezone.now()

        with transaction.atomic():
            job = (
                TaskJob.objects.filter(
                    status=TaskJobStatus.READY,
                    queue_name__in=queues,
                )
                .filter(
                    models.Q(run_after__isnull=True) | models.Q(
                        run_after__lte=now)
                )
                .select_for_update(skip_locked=True)
                .order_by("-priority", "enqueued_at")
                .first()
            )

            if job:
                job.status = TaskJobStatus.RUNNING
                job.started_at = now
                job.last_attempted_at = now
                job.worker = worker
                job.save(
                    update_fields=[
                        "status",
                        "started_at",
                        "last_attempted_at",
                        "worker",
                        "updated_at",
                    ]
                )
                logger.info(f"Claimed job {job.id}: {job.task_path}")

        return job

    def _execute_job(self, *, job: TaskJob, worker, heartbeat_interval: int):
        logger.info(f"Executing job {job.id}: {job.task_path}")

        stop_event = threading.Event()

        def heartbeat_loop():
            while not stop_event.wait(heartbeat_interval):
                try:
                    worker.refresh_from_db(fields=["stop_requested", "status"])
                    heartbeat_worker(worker, status=TaskWorkerStatus.RUNNING)
                except Exception:
                    logger.exception(
                        f"Failed to heartbeat worker {worker.worker_name} for job {job.id}"
                    )

        heartbeat_worker(worker, status=TaskWorkerStatus.RUNNING)
        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            name=f"task-worker-heartbeat-{worker.id}",
            daemon=True,
        )
        heartbeat_thread.start()

        try:
            task_func = import_string(job.task_path)

            kwargs_with_job_id = (job.kwargs or {}).copy()
            kwargs_with_job_id["job_id"] = str(job.id)

            result = task_func(*(job.args or []), **kwargs_with_job_id)
            self._mark_job_successful(job, result)

        except Exception as exc:
            error_msg = str(exc)
            tb = traceback.format_exc()

            logger.error(f"Job {job.id} failed: {error_msg}")
            logger.debug(f"Job {job.id} traceback:\n{tb}")

            if job.retry_count < job.max_retries:
                self._mark_job_for_retry(job, error_msg, tb)
            else:
                self._mark_job_failed(job, error_msg, tb)

        finally:
            stop_event.set()
            heartbeat_thread.join(timeout=max(1, heartbeat_interval))

    def _mark_job_successful(self, job: TaskJob, result):
        job.status = TaskJobStatus.SUCCESSFUL
        job.finished_at = timezone.now()
        job.result = result
        job.error_message = None
        job.traceback = None
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "result",
                "error_message",
                "traceback",
                "updated_at",
            ]
        )
        logger.info(f"Job {job.id} completed successfully")

    def _mark_job_failed(self, job: TaskJob, error_message: str, traceback_str: str):
        job.status = TaskJobStatus.FAILED
        job.finished_at = timezone.now()
        job.error_message = error_message
        job.traceback = traceback_str
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "error_message",
                "traceback",
                "updated_at",
            ]
        )
        logger.error(
            f"Job {job.id} failed permanently after {job.retry_count} retries"
        )

    def _mark_job_for_retry(
        self, job: TaskJob, error_message: str, traceback_str: str
    ):
        job.status = TaskJobStatus.READY
        job.retry_count += 1
        job.error_message = error_message
        job.traceback = traceback_str
        job.worker = None
        job.started_at = None
        delay_seconds = 2 ** job.retry_count * 60
        job.run_after = timezone.now() + timezone.timedelta(seconds=delay_seconds)
        job.save(
            update_fields=[
                "status",
                "retry_count",
                "error_message",
                "traceback",
                "worker",
                "started_at",
                "run_after",
                "updated_at",
            ]
        )
        logger.warning(
            f"Job {job.id} failed, scheduling retry {job.retry_count}/{job.max_retries} "
            f"in {delay_seconds} seconds"
        )
