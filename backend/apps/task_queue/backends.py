import logging
from typing import Callable, Optional
from django.utils import timezone
from .models import TaskJob, TaskJobStatus

logger = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self, queue_name: str = "default"):
        self.queue_name = queue_name

    def enqueue(
        self,
        task_path: str,
        *args,
        queue_name: Optional[str] = None,
        priority: int = 0,
        run_after: Optional[timezone.datetime] = None,
        max_retries: int = 3,
        **kwargs
    ) -> TaskJob:
        job = TaskJob.objects.create(
            task_path=task_path,
            queue_name=queue_name or self.queue_name,
            priority=priority,
            run_after=run_after,
            max_retries=max_retries,
            args=list(args),
            kwargs=dict(kwargs),
            status=TaskJobStatus.READY
        )

        logger.info(f"Enqueued task {task_path} with id {job.id}")
        return job

    def enqueue_func(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> TaskJob:
        task_path = f"{func.__module__}.{func.__name__}"
        return self.enqueue(task_path, *args, **kwargs)

default_queue = TaskQueue()


def enqueue(task_path: str, *args, **kwargs) -> TaskJob:
    return default_queue.enqueue(task_path, *args, **kwargs)


def enqueue_func(func: Callable, *args, **kwargs) -> TaskJob:
    return default_queue.enqueue_func(func, *args, **kwargs)
