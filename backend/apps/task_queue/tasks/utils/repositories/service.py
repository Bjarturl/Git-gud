from django.utils import timezone

from apps.git_data.models import Repo, UserStatus
from apps.task_queue.tasks.utils.jobs import (
    clear_worker_model_claims,
    get_active_claimed_ids,
    get_job_worker,
    is_cancelled,
    refresh_worker_claims,
    reset_worker_claims,
    set_worker_model_claims,
)

from ..commits.processing import (
    process_repository_commits,
    process_repository_pull_requests,
)


CLAIM_BATCH_SIZE = 1000
CLAIM_REFRESH_EVERY = 100


def _get_repository_queryset():
    return Repo.objects.filter(
        owner__status=UserStatus.CONFIRMED,
        is_fork=False,
        processed_at__isnull=True,
    ).select_related("owner")


def _claim_next_repository_batch(worker, logger=None, batch_size: int = CLAIM_BATCH_SIZE):
    claimed_ids = get_active_claimed_ids("repo", exclude_worker_id=worker.id)

    queryset = _get_repository_queryset()

    if claimed_ids:
        queryset = queryset.exclude(id__in=claimed_ids)

    repo_ids = list(
        queryset.order_by("id").values_list("id", flat=True)[:batch_size]
    )

    set_worker_model_claims(worker, "repo", repo_ids)

    if not repo_ids:
        return []

    repositories = list(
        Repo.objects.filter(id__in=repo_ids)
        .select_related("owner")
        .order_by("id")
    )

    if logger:
        logger.info(f"Claimed {len(repositories)} repositories")

    return repositories


def _process_repository(client, repo, logger, job_id: str) -> bool:
    start_time = timezone.now()

    try:
        commit_count, commit_users = process_repository_commits(
            client,
            repo,
            logger,
            lambda: is_cancelled(job_id),
        )
        if is_cancelled(job_id):
            return False

        pr_count, pr_users = process_repository_pull_requests(
            client,
            repo,
            logger,
            lambda: is_cancelled(job_id),
        )
        if is_cancelled(job_id):
            return False

        repo.processed_at = timezone.now()
        repo.save(update_fields=["processed_at"])

        processing_time = (timezone.now() - start_time).total_seconds()

        logger.info(f"Repository completed: {repo.full_name}")
        logger.info(f"Commits processed: {commit_count}")
        logger.info(f"Pull requests processed: {pr_count}")
        logger.info(f"Users discovered: {commit_users + pr_users}")
        logger.info(f"Processing time: {processing_time:.1f} seconds")

        return True

    except Exception as exc:
        logger.error(
            f"Error processing repository {repo.full_name}: {exc}", exc_info=True
        )
        return False


def process_repositories(
    client,
    logger,
    job_id: str,
):
    if is_cancelled(job_id):
        logger.warning("Task cancelled before starting")
        return

    worker = get_job_worker(job_id)
    reset_worker_claims(worker)

    total_available = _get_repository_queryset().count()

    logger.info(f"Found {total_available} repositories available")

    if total_available == 0:
        logger.warning("No repositories found matching criteria")
        return

    repositories_processed = 0
    processed_since_refresh = 0
    repositories_batch = []

    try:
        while True:
            if is_cancelled(job_id):
                logger.warning(
                    f"Task cancelled after processing {repositories_processed} repositories"
                )
                break

            if not repositories_batch:
                repositories_batch = _claim_next_repository_batch(worker, logger=logger)

                if not repositories_batch:
                    logger.info("No more repositories available to process")
                    break

            repo = repositories_batch.pop(0)

            if repo.processed_at is not None:
                continue

            logger.info(
                f"Processing repository {repositories_processed + 1}/{total_available}: {repo.full_name}"
            )
            logger.info(f"Owner: {repo.owner.username}")

            completed = _process_repository(client, repo, logger, job_id)
            if not completed:
                if is_cancelled(job_id):
                    break

                logger.warning(
                    f"Skipping processed_at update for repository {repo.full_name}"
                )
                continue

            repositories_processed += 1
            processed_since_refresh += 1

            if processed_since_refresh >= CLAIM_REFRESH_EVERY:
                refresh_worker_claims(worker)
                processed_since_refresh = 0

    finally:
        clear_worker_model_claims(worker, "repo")