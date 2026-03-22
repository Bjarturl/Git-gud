from clients.github import GitHubAPIClient
from .utils.jobs import (
    close_job_logger,
    setup_job_logger,
)
from .utils.users.processing import (
    process_discovered_users_batch,
    search_users_with_date_splitting,
)


def user_discovery_task(
    search_query: str,
    update_existing: bool = False,
    set_user_status: str = None,
    add_tags: list = None,
    job_id: str = None,
):
    job_logger, file_handler = setup_job_logger(job_id, 'user_discovery')
    job_logger.info(f"Starting user discovery task with query: {search_query}")
    job_logger.info(f"Update existing users: {update_existing}")
    job_logger.info(f"Set user status: {set_user_status}")
    job_logger.info(f"Add tags: {add_tags}")

    try:
        client = GitHubAPIClient()
        user_list = search_users_with_date_splitting(
            client,
            search_query,
            job_logger,
            job_id,
        )
        total_found = len(user_list)

        if total_found == 0:
            job_logger.warning("No users found for this search query")

        process_discovered_users_batch(
            client=client,
            user_list=user_list,
            search_query=search_query,
            set_user_status=set_user_status,
            add_tags=add_tags,
            update_existing=update_existing,
            logger=job_logger,
            job_id=job_id,
        )

        job_logger.info("TASK COMPLETED")

    except Exception as e:
        job_logger.error(f"User discovery task failed: {e}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
