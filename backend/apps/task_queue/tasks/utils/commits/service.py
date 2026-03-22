import time
from typing import List, Tuple

from django.utils import timezone

from apps.search.services import ElasticsearchService
from apps.git_data.models import Commit
from apps.task_queue.tasks.utils.gists.helpers import is_binary_filename
from apps.task_queue.tasks.utils.jobs import (
    clear_worker_model_claims,
    get_active_claimed_ids,
    get_job_worker,
    is_cancelled,
    refresh_worker_claims,
    reset_worker_claims,
    set_worker_model_claims,
)
from clients.github import GitHubAPIClient


CLAIM_BATCH_SIZE = 1000
CLAIM_REFRESH_EVERY = 100


def _claim_next_commit_batch(worker, logger, batch_size: int = CLAIM_BATCH_SIZE) -> List[Commit]:
    claimed_ids = get_active_claimed_ids("commit", exclude_worker_id=worker.id)

    queryset = Commit._base_manager.order_by().filter(processed_at__isnull=True)

    if claimed_ids:
        queryset = queryset.exclude(id__in=claimed_ids)

    commit_ids = list(queryset.values_list("id", flat=True)[:batch_size])

    set_worker_model_claims(worker, "commit", commit_ids)

    if not commit_ids:
        return []

    commits = list(
        Commit.objects
        .filter(id__in=commit_ids)
        .select_related("author", "repo", "repo__owner")
        .order_by("id")
    )

    logger.info(f"Claimed {len(commits)} commits")
    return commits


def _extract_patch_changes(patch: str) -> Tuple[str, str]:
    if not patch:
        return "", ""

    additions = []
    deletions = []

    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            additions.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            deletions.append(line[1:])

    return "\n".join(additions), "\n".join(deletions)


def _build_commit_file_doc(commit: Commit, file_data: dict) -> Tuple[str, dict] | Tuple[None, None]:
    filename = file_data.get("filename")
    if not filename:
        return None, None

    is_binary = is_binary_filename(filename)

    if is_binary:
        additions = ""
        deletions = ""
    else:
        additions, deletions = _extract_patch_changes(file_data.get("patch", ""))

    if not additions and not deletions and not is_binary:
        return None, None

    doc_id = f"commit:{commit.repo_id}:{commit.sha}:{filename}"
    doc_data = {
        "user": commit.author.username if commit.author else "unknown",
        "user_company": commit.author.company if commit.author and commit.author.company else "",
        "repo": commit.repo.name,
        "repo_owner": commit.repo.owner.username,
        "repo_owner_company": commit.repo.owner.company,
        "source_id": commit.sha,
        "message": commit.message,
        "date": commit.commit_date or commit.created_at,
        "branch_name": commit.branch_name,
        "filename": filename,
        "url": commit.url,
        "timestamp": timezone.now(),
        "type": "commit",
        "additions": additions,
        "deletions": deletions,
    }

    return doc_id, doc_data


def _index_commit_code(
    commit: Commit,
    client: GitHubAPIClient,
    es_service: ElasticsearchService,
    logger,
) -> int | None:
    try:
        if not es_service.is_available():
            return None

        repo_owner, repo_name = commit.repo.full_name.split("/", 1)
        commit_details = client.get_commit_details(repo_owner, repo_name, commit.sha)
        if not commit_details:
            logger.warning(f"Could not fetch details for commit {commit.sha}")
            return None

        indexed_files = 0

        for file_data in commit_details.get("files", []):
            doc_id, doc_data = _build_commit_file_doc(commit, file_data)
            if not doc_id:
                continue

            if es_service.index_document(doc_data, doc_id):
                indexed_files += 1

        time.sleep(0.1)
        return indexed_files

    except Exception as exc:
        logger.error(f"Error indexing commit {commit.sha}: {exc}", exc_info=True)
        return None


def process_commits(
    logger,
    job_id: str,
):
    es_service = ElasticsearchService()
    if not es_service.is_available():
        raise Exception("Elasticsearch is not available")

    client = GitHubAPIClient()
    worker = get_job_worker(job_id)
    reset_worker_claims(worker)

    processed_count = 0
    indexed_count = 0
    processed_since_refresh = 0

    commits_batch: List[Commit] = []

    try:
        while True:
            if is_cancelled(job_id):
                logger.warning("Task cancelled")
                break

            if not commits_batch:
                commits_batch = _claim_next_commit_batch(worker, logger)

                if not commits_batch:
                    logger.info("No more commits to process")
                    break

            commit = commits_batch.pop(0)

            if commit.processed_at is not None:
                continue

            if is_cancelled(job_id):
                logger.warning("Task cancelled")
                break

            logger.info(f"Processing commit {commit.sha[:8]} in {commit.repo.full_name}")

            indexed_files = _index_commit_code(commit, client, es_service, logger) or 0
            indexed_count += indexed_files

            commit.processed_at = timezone.now()
            commit.save(update_fields=["processed_at"])
            processed_count += 1
            processed_since_refresh += 1

            if processed_since_refresh >= CLAIM_REFRESH_EVERY:
                refresh_worker_claims(worker)
                processed_since_refresh = 0

    finally:
        clear_worker_model_claims(worker, "commit")

    logger.info(f"Processed: {processed_count}")
    logger.info(f"Indexed files: {indexed_count}")