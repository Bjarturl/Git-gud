from typing import Any, Dict

from django.utils import timezone

from apps.git_data.models import AccountType, User, UserStatus
from apps.task_queue.tasks.utils.gists.processing import process_all_user_gists
from apps.task_queue.tasks.utils.jobs import (
    clear_worker_model_claims,
    get_active_claimed_ids,
    get_job_worker,
    is_cancelled,
    refresh_worker_claims,
    reset_worker_claims,
    set_worker_model_claims,
)
from apps.task_queue.tasks.utils.repositories.processing import process_all_user_repositories
from .processing import (
    process_organization_members,
    process_user_followers,
    process_user_following,
)


CLAIM_BATCH_SIZE = 1000
CLAIM_REFRESH_EVERY = 100


def _get_user_queryset(user_filter: str):
    queryset = User.objects.all()

    if user_filter == "confirmed":
        return queryset.filter(status=UserStatus.CONFIRMED)

    if user_filter == "all":
        return queryset

    return queryset.filter(status=user_filter)


def _claim_next_user_batch(worker, user_filter: str, logger, batch_size: int = CLAIM_BATCH_SIZE) -> list[int]:
    claimed_ids = get_active_claimed_ids("user", exclude_worker_id=worker.id)

    queryset = _get_user_queryset(user_filter)

    if claimed_ids:
        queryset = queryset.exclude(id__in=claimed_ids)

    ids = list(
        queryset.order_by("id").values_list("id", flat=True)[:batch_size]
    )

    set_worker_model_claims(worker, "user", ids)

    if ids:
        logger.info(f"Claimed {len(ids)} users")

    return ids


def _process_user(client, user: User, logger, job_id: str) -> Dict[str, int | bool]:
    new_users_created = 0
    repos_created = 0
    gists_created = 0

    try:
        _, new_followers = process_user_followers(
            client, user, logger, lambda: is_cancelled(job_id)
        )
        new_users_created += new_followers
        if is_cancelled(job_id):
            return {
                "completed": False,
                "new_users_created": new_users_created,
                "repos_created": repos_created,
                "gists_created": gists_created,
            }

        _, new_following = process_user_following(
            client, user, logger, lambda: is_cancelled(job_id)
        )
        new_users_created += new_following
        if is_cancelled(job_id):
            return {
                "completed": False,
                "new_users_created": new_users_created,
                "repos_created": repos_created,
                "gists_created": gists_created,
            }

        if user.account_type == AccountType.ORGANIZATION:
            _, new_members = process_organization_members(
                client, user, logger, lambda: is_cancelled(job_id)
            )
            new_users_created += new_members
            if is_cancelled(job_id):
                return {
                    "completed": False,
                    "new_users_created": new_users_created,
                    "repos_created": repos_created,
                    "gists_created": gists_created,
                }

        repo_count, new_repo_owners = process_all_user_repositories(
            client, user, logger, lambda: is_cancelled(job_id)
        )
        repos_created += repo_count
        new_users_created += new_repo_owners
        if is_cancelled(job_id):
            return {
                "completed": False,
                "new_users_created": new_users_created,
                "repos_created": repos_created,
                "gists_created": gists_created,
            }

        gist_count = process_all_user_gists(
            client, user, logger, lambda: is_cancelled(job_id)
        )
        gists_created += gist_count
        if is_cancelled(job_id):
            return {
                "completed": False,
                "new_users_created": new_users_created,
                "repos_created": repos_created,
                "gists_created": gists_created,
            }

        user.processed_at = timezone.now()
        user.save(update_fields=["processed_at"])

        logger.info(
            f"Processed user {user.username} ({repo_count} repos, {gist_count} gists)"
        )

        return {
            "completed": True,
            "new_users_created": new_users_created,
            "repos_created": repos_created,
            "gists_created": gists_created,
        }

    except Exception as exc:
        logger.error(
            f"Error processing user {user.username}: {exc}", exc_info=True
        )
        return {
            "completed": False,
            "new_users_created": new_users_created,
            "repos_created": repos_created,
            "gists_created": gists_created,
        }


def process_users(
    client,
    user_filter: str,
    logger,
    job_id: str,
) -> Dict[str, Any]:
    worker = get_job_worker(job_id)
    reset_worker_claims(worker)

    total_available = _get_user_queryset(user_filter).count()

    logger.info(f"Found {total_available} users available")

    processed = 0
    new_users_created = 0
    repos_created = 0
    gists_created = 0
    errors = 0
    processed_since_refresh = 0

    claimed_user_ids: list[int] = []

    try:
        while True:
            if is_cancelled(job_id):
                logger.warning(
                    f"Task cancelled after processing {processed} users")
                break

            if not claimed_user_ids:
                claimed_user_ids = _claim_next_user_batch(
                    worker, user_filter, logger)

                if not claimed_user_ids:
                    logger.info("No more users available to process")
                    break

            user_id = claimed_user_ids.pop(0)

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                continue

            if user.processed_at is not None:
                continue

            logger.info(
                f"Processing user {processed + 1}/{total_available}: {user.username}"
            )

            result = _process_user(client, user, logger, job_id)

            new_users_created += result["new_users_created"]
            repos_created += result["repos_created"]
            gists_created += result["gists_created"]

            if not result["completed"]:
                if is_cancelled(job_id):
                    break

                errors += 1
                logger.warning(
                    f"Skipping processed_at update for user {user.username}"
                )
                continue

            processed += 1
            processed_since_refresh += 1

            if processed_since_refresh >= CLAIM_REFRESH_EVERY:
                refresh_worker_claims(worker)
                processed_since_refresh = 0

            logger.info(f"New users created: {new_users_created}")
            logger.info(f"Repositories created: {repos_created}")
            logger.info(f"Gists created: {gists_created}")

    finally:
        clear_worker_model_claims(worker, "user")

    return {
        "processed": processed,
        "new_users_created": new_users_created,
        "repos_created": repos_created,
        "gists_created": gists_created,
        "errors": errors,
    }
