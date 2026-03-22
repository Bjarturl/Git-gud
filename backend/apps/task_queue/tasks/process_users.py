from clients.github import GitHubAPIClient

from .utils.jobs import close_job_logger, setup_job_logger
from .utils.users.service import process_users


def process_users_task(
    user_filter: str = "confirmed",
    job_id: str = None,
):
    job_logger, file_handler = setup_job_logger(job_id, "process_users")

    job_logger.info("Starting user processing task")
    job_logger.info(f"User filter: {user_filter}")

    try:
        client = GitHubAPIClient()

        process_users(
            client=client,
            user_filter=user_filter,
            logger=job_logger,
            job_id=job_id,
        )

        job_logger.info("TASK COMPLETED")

    except Exception as e:
        job_logger.error(f"User processing task failed: {e}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
