from clients.github import GitHubAPIClient

from .utils.jobs import close_job_logger, setup_job_logger
from .utils.repositories.service import process_repositories


def process_repositories_task(
    job_id: str = None,
):
    job_logger, file_handler = setup_job_logger(job_id, "process_repositories")

    job_logger.info("Starting repository processing task")

    try:
        client = GitHubAPIClient()

        process_repositories(
            client=client,
            logger=job_logger,
            job_id=job_id,
        )

        job_logger.info("TASK COMPLETED")

    except Exception as e:
        job_logger.error(f"Repository processing task failed: {e}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
