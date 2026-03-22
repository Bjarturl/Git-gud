from .utils.jobs import close_job_logger, setup_job_logger

from .utils.events.service import process_gharchive


def get_raw_events_task(job_id: str = None):
    job_logger, file_handler = setup_job_logger(job_id, "process_gharchive")

    job_logger.info("Starting GH Archive ingestion task")

    try:
        process_gharchive(
            logger=job_logger,
            job_id=job_id,
        )

        job_logger.info("TASK COMPLETED")

    except Exception as e:
        job_logger.error(f"GH Archive task failed: {e}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
