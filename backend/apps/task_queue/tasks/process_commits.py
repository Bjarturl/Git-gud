from .utils.jobs import close_job_logger, setup_job_logger
from .utils.commits.service import process_commits


def process_commits_task(
    job_id: str = None,
):
    job_logger, file_handler = setup_job_logger(job_id, "process_commits")

    job_logger.info("Starting commit indexing task")

    try:
        process_commits(
            logger=job_logger,
            job_id=job_id,
        )

        job_logger.info("TASK COMPLETED")

    except Exception as e:
        job_logger.error(f"Commit processing task failed: {e}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
