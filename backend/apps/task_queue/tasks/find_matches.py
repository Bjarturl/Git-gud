from .utils.jobs import close_job_logger, setup_job_logger
from .utils.matches.service import find_matches


def find_matches_task(
    job_id: str = None,
):
    job_logger, file_handler = setup_job_logger(job_id, "find_matches")

    job_logger.info("Starting match generation task")

    try:
        find_matches(
            logger=job_logger,
            job_id=job_id,
        )

        job_logger.info("TASK COMPLETED")

    except Exception as e:
        job_logger.error(f"Match generation task failed: {e}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
