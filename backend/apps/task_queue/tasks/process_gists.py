from .utils.jobs import close_job_logger, setup_job_logger
from .utils.gists.service import process_gists


def process_gists_task(
    job_id: str = None,
):
    job_logger, file_handler = setup_job_logger(job_id, "process_gists")

    job_logger.info("Starting gist indexing task")

    try:
        process_gists(
            logger=job_logger,
            job_id=job_id,
        )

        job_logger.info("TASK COMPLETED")

    except Exception as e:
        job_logger.error(f"Gist processing task failed: {e}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
