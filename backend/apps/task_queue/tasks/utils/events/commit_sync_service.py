from datetime import datetime, timedelta, timezone as dt_timezone

from django.db.models import Exists, OuterRef

from apps.events.models import RawEvent
from apps.git_data.models import Repo, UserStatus
from apps.task_queue.tasks.utils.commits.processing import create_commit_record_with_users
from apps.task_queue.tasks.utils.jobs import (
    clear_worker_model_claims,
    get_job_worker,
    is_cancelled,
    refresh_worker_claims,
    reset_worker_claims,
)
from apps.task_queue.tasks.utils.repositories.service import (
    _claim_next_repository_batch,
)
from clients.github import GitHubAPIClient


GHARCHIVE_START = datetime(2011, 2, 12, 0, tzinfo=dt_timezone.utc)
LOOKBACK_WINDOW = timedelta(hours=24)

CLAIM_REFRESH_EVERY = 100
REPO_PROGRESS_EVERY = 100
RAW_EVENT_PROGRESS_EVERY = 100


def _get_event_repository_queryset():
    raw_events_for_repo = RawEvent.objects.filter(
        repo_id=OuterRef("source_repo_id")
    )

    return (
        Repo.objects.filter(
            owner__status=UserStatus.CONFIRMED,
            is_fork=False,
            source_repo_id__isnull=False,
        )
        .annotate(has_raw_events=Exists(raw_events_for_repo))
        .filter(has_raw_events=True)
        .select_related("owner")
    )


def _claim_next_event_repository_batch(worker, logger=None, batch_size: int = 1000):
    original_get_queryset = _claim_next_repository_batch.__globals__[
        "_get_repository_queryset"
    ]
    _claim_next_repository_batch.__globals__[
        "_get_repository_queryset"
    ] = _get_event_repository_queryset

    try:
        return _claim_next_repository_batch(worker, logger=logger, batch_size=batch_size)
    finally:
        _claim_next_repository_batch.__globals__[
            "_get_repository_queryset"
        ] = original_get_queryset


def _get_global_event_frontier():
    last = (
        RawEvent.objects.order_by("-observed_at")
        .values_list("observed_at", flat=True)
        .first()
    )
    return last or GHARCHIVE_START


def _get_cutoff(repo: Repo):
    if not repo.latest_event_checked:
        return GHARCHIVE_START
    return max(GHARCHIVE_START, repo.latest_event_checked - LOOKBACK_WINDOW)


def _get_repo_raw_events(repo: Repo):
    return (
        RawEvent.objects.filter(
            repo_id=repo.source_repo_id,
            observed_at__gt=_get_cutoff(repo),
        )
        .order_by("observed_at")
        .only("sha", "observed_at")
        .iterator(chunk_size=1000)
    )


def _build_commit_payload(commit_details: dict, repo: Repo) -> dict:
    payload = dict(commit_details)
    payload["branch_name"] = repo.default_branch or "event"
    return payload


def _advance_repo_checkpoint(repo: Repo, frontier):
    if repo.latest_event_checked != frontier:
        repo.latest_event_checked = frontier
        repo.save(update_fields=["latest_event_checked"])


def _sync_repo_events(client, repo: Repo, logger, check_cancellation_func, frontier) -> bool:
    created_count = 0
    existing_count = 0
    missing_count = 0
    failed_count = 0
    saw_raw_events = False

    for index, raw_event in enumerate(_get_repo_raw_events(repo), start=1):
        saw_raw_events = True

        if check_cancellation_func():
            logger.warning("Task cancelled during repo event sync")
            return False

        if index % RAW_EVENT_PROGRESS_EVERY == 0:
            logger.info(f"{repo.full_name}: processed {index} raw events")

        sha = raw_event.sha.hex()

        try:
            commit_details = client.get_commit_details(
                repo.owner.username,
                repo.name,
                sha,
            )
        except Exception as exc:
            failed_count += 1
            logger.warning(f"[FETCH FAILED] {repo.full_name} {sha}: {exc}")
            continue

        if not commit_details:
            missing_count += 1
            continue

        try:
            commit_record, users_discovered = create_commit_record_with_users(
                client=client,
                repo=repo,
                commit_data=_build_commit_payload(commit_details, repo),
                logger=logger,
            )

            if not commit_record:
                existing_count += 1
                continue

            if not commit_record.from_event:
                commit_record.from_event = True
                commit_record.save(update_fields=["from_event"])

            created_count += 1
            logger.info(
                f"[CREATED] {repo.full_name} {sha} users_discovered={users_discovered}"
            )

        except Exception as exc:
            failed_count += 1
            logger.error(
                f"[CREATE FAILED] {repo.full_name} {sha}: {exc}",
                exc_info=True,
            )

    _advance_repo_checkpoint(repo, frontier)

    if saw_raw_events or created_count or existing_count or missing_count or failed_count:
        logger.info(
            f"Repository completed: {repo.full_name} | "
            f"created={created_count}, existing={existing_count}, "
            f"missing={missing_count}, failed={failed_count}, "
            f"latest_event_checked={repo.latest_event_checked}"
        )

    return True


def sync_event_commits(logger, job_id: str):
    if is_cancelled(job_id):
        logger.warning("Task cancelled before starting")
        return

    frontier = _get_global_event_frontier()
    client = GitHubAPIClient()
    worker = get_job_worker(job_id)
    reset_worker_claims(worker)

    total_available = _get_event_repository_queryset().count()
    logger.info(
        f"Found {total_available} repositories with raw events available")

    if total_available == 0:
        logger.warning("No repositories found matching criteria")
        return

    repositories_processed = 0
    repositories_claimed = 0
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
                repositories_batch = _claim_next_event_repository_batch(
                    worker,
                    logger=logger,
                )

                if not repositories_batch:
                    logger.info("No more repositories available to process")
                    break

            repo = repositories_batch.pop(0)
            repositories_claimed += 1

            if repositories_claimed % REPO_PROGRESS_EVERY == 0:
                logger.info(
                    f"Claimed {repositories_claimed}/{total_available} repositories "
                    f"(processed={repositories_processed})"
                )

            completed = _sync_repo_events(
                client=client,
                repo=repo,
                logger=logger,
                check_cancellation_func=lambda: is_cancelled(job_id),
                frontier=frontier,
            )

            if not completed:
                if is_cancelled(job_id):
                    break
                continue

            repositories_processed += 1
            processed_since_refresh += 1

            if processed_since_refresh >= CLAIM_REFRESH_EVERY:
                refresh_worker_claims(worker)
                processed_since_refresh = 0

    finally:
        clear_worker_model_claims(worker, "repo")

    logger.info(
        f"Repositories processed: {repositories_processed}, claimed: {repositories_claimed}"
    )
