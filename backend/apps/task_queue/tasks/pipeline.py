from django.utils import timezone

from apps.git_data.models import AccountType, Commit, Gist, Repo, User, UserStatus
from apps.search.services import ElasticsearchService
from clients.github import GitHubAPIClient

from .utils.commits.processing import process_repository_commits, process_repository_pull_requests
from .utils.commits.service import _index_commit_code
from .utils.gists.processing import process_all_user_gists
from .utils.gists.service import _index_gist_code
from .utils.jobs import close_job_logger, is_cancelled, setup_job_logger
from .utils.matches.service import find_matches
from .utils.repositories.processing import process_all_user_repositories
from .utils.users.processing import (
    create_or_update_discovered_user,
    process_organization_members,
    process_user_followers,
    process_user_following,
)


def _run_pipeline_for_user(username: str, client, es_service, logger, job_id: str):
    check_cancel = lambda: is_cancelled(job_id)

    logger.info("Step 1/7: Resolving user")
    user = User.objects.filter(username=username).first()
    if user:
        logger.info(f"User already exists (id={user.id}), skipping discovery")
    else:
        logger.info("User not found in DB, fetching from GitHub")
        user_data = client.get_user_info(username)
        if not user_data:
            raise Exception(f"GitHub returned no data for '{username}'")
        user, _, _ = create_or_update_discovered_user(
            full_user_data=user_data,
            set_user_status=UserStatus.CONFIRMED,
            logger=logger,
        )
        if not user:
            raise Exception(f"Failed to create user record for '{username}'")

    if user.status != UserStatus.CONFIRMED:
        User.objects.filter(id=user.id).update(status=UserStatus.CONFIRMED)
        user.status = UserStatus.CONFIRMED
        logger.info("User status updated to CONFIRMED")

    if is_cancelled(job_id):
        return

    logger.info("Step 2/7: Processing social graph (followers / following)")
    process_user_followers(client, user, logger, check_cancel)
    if is_cancelled(job_id):
        return
    process_user_following(client, user, logger, check_cancel)
    if is_cancelled(job_id):
        return
    if user.account_type == AccountType.ORGANIZATION:
        process_organization_members(client, user, logger, check_cancel)
        if is_cancelled(job_id):
            return

    logger.info("Step 3/7: Discovering repos and gists")
    process_all_user_repositories(client, user, logger, check_cancel)
    if is_cancelled(job_id):
        return
    process_all_user_gists(client, user, logger, check_cancel)
    if is_cancelled(job_id):
        return

    logger.info("Step 4/7: Processing repositories (fetching commits)")
    repos = list(Repo.objects.filter(owner=user, is_fork=False, processed_at__isnull=True))
    logger.info(f"Found {len(repos)} unprocessed repos")
    for repo in repos:
        if is_cancelled(job_id):
            return
        try:
            commit_count, _ = process_repository_commits(client, repo, logger, check_cancel)
            pr_count, _ = process_repository_pull_requests(client, repo, logger, check_cancel)
            repo.processed_at = timezone.now()
            repo.save(update_fields=["processed_at"])
            logger.info(f"{repo.full_name}: {commit_count} commits, {pr_count} PRs")
        except Exception as exc:
            logger.error(f"Error processing repo {repo.full_name}: {exc}", exc_info=True)

    logger.info("Step 5/7: Indexing commits to Elasticsearch")
    commits = list(
        Commit.objects
        .filter(repo__owner=user, processed_at__isnull=True)
        .select_related("author", "repo", "repo__owner")
    )
    logger.info(f"Found {len(commits)} unprocessed commits")
    for commit in commits:
        if is_cancelled(job_id):
            return
        indexed = _index_commit_code(commit, client, es_service, logger)
        if indexed is not None:
            commit.processed_at = timezone.now()
            commit.save(update_fields=["processed_at"])

    logger.info("Step 6/7: Indexing gists to Elasticsearch")
    gists = list(
        Gist.objects
        .filter(author=user, processed_at__isnull=True, is_fork=False)
        .select_related("author")
    )
    logger.info(f"Found {len(gists)} unprocessed gists")
    for gist in gists:
        if is_cancelled(job_id):
            return
        indexed = _index_gist_code(gist, client, es_service, logger)
        if indexed is not None:
            gist.processed_at = timezone.now()
            gist.save(update_fields=["processed_at"])

    logger.info("Step 7/7: Finding matches")
    if not es_service.is_available():
        logger.warning("Elasticsearch not available, skipping match scan")
    else:
        find_matches(logger=logger, job_id=job_id, username=username)

    User.objects.filter(id=user.id).update(scanned_at=timezone.now())
    logger.info(f"Marked {username} as scanned")


def pipeline_task(username: str, job_id: str = None):
    job_logger, file_handler = setup_job_logger(job_id, "pipeline")
    job_logger.info(f"Starting pipeline for username: {username}")
    try:
        client = GitHubAPIClient()
        es_service = ElasticsearchService()
        _run_pipeline_for_user(username, client, es_service, job_logger, job_id)
        job_logger.info("TASK COMPLETED")
    except Exception as exc:
        job_logger.error(f"Pipeline task failed: {exc}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)


def multi_pipeline_task(usernames: list, job_id: str = None):
    job_logger, file_handler = setup_job_logger(job_id, "pipeline")
    job_logger.info(f"Starting multi-user pipeline for: {', '.join(usernames)}")
    try:
        client = GitHubAPIClient()
        es_service = ElasticsearchService()
        for i, username in enumerate(usernames, 1):
            if is_cancelled(job_id):
                job_logger.warning("Pipeline cancelled")
                break
            job_logger.info(f"")
            job_logger.info(f"=== User {i}/{len(usernames)}: {username} ===")
            _run_pipeline_for_user(username, client, es_service, job_logger, job_id)
        job_logger.info("TASK COMPLETED")
    except Exception as exc:
        job_logger.error(f"Multi-pipeline task failed: {exc}")
        job_logger.exception("Full traceback:")
    finally:
        close_job_logger(job_logger, file_handler)
