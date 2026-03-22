from .utils.jobs import close_job_logger, setup_job_logger

from .utils.events.commit_sync_service import sync_event_commits


def sync_event_commits_task(job_id: str = None):
    job_logger, file_handler = setup_job_logger(job_id, "sync_event_commits")

    job_logger.info("Starting event commit sync task")

    try:
        sync_event_commits(
            logger=job_logger,
            job_id=job_id
        )

        job_logger.info("TASK COMPLETED")

    except Exception as e:
        job_logger.error(f"Event commit sync task failed: {e}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
