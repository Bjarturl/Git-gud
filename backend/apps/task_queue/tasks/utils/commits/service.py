from typing import List, Tuple

import requests as requests_lib
from django.db import reset_queries
from django.utils import timezone

from apps.search.services import ElasticsearchService
from apps.git_data.models import Commit
from apps.task_queue.tasks.utils.gists.helpers import is_binary_filename
from apps.task_queue.tasks.utils.jobs import (
    COMMIT_CLAIM_LOCK,
    claim_lock,
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
    commit_ids = []
    with claim_lock(COMMIT_CLAIM_LOCK):
        claimed_ids = get_active_claimed_ids("commit", exclude_worker_id=worker.id)
        queryset = Commit._base_manager.order_by("id").filter(processed_at__isnull=True)
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


GITHUB_FILE_CAP = 300
MAX_CONTENT_BYTES = 8_000_000  # skip files whose diff content exceeds 8 MB


def _parse_raw_diff_files(diff_text: str) -> list:
    """Split a raw unified diff into per-file dicts with filename + patch."""
    files = []
    current_filename = None
    patch_lines = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current_filename is not None:
                files.append({"filename": current_filename, "patch": "\n".join(patch_lines)})
            parts = line.split(" b/", 1)
            current_filename = parts[1] if len(parts) == 2 else None
            patch_lines = []
        elif current_filename is not None:
            patch_lines.append(line)

    if current_filename is not None:
        files.append({"filename": current_filename, "patch": "\n".join(patch_lines)})

    return files


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

    if len(additions) + len(deletions) > MAX_CONTENT_BYTES:
        return None, None

    doc_id = f"commit:{commit.repo_id}:{commit.sha}:{filename}"
    doc_data = {
        "user": commit.repo.owner.username,
        "user_company": commit.repo.owner.company or "",
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
        repo_owner, repo_name = commit.repo.full_name.split("/", 1)
        commit_details = client.get_commit_details(repo_owner, repo_name, commit.sha)
        if not commit_details:
            logger.warning(f"Could not fetch details for commit {commit.sha}")
            return None

        files = commit_details.get("files", [])

        null_patch_count = sum(
            1 for f in files
            if f.get("patch") is None
            and not is_binary_filename(f.get("filename", ""))
            and (f.get("additions", 0) or f.get("deletions", 0))
        )
        needs_raw_diff = len(files) >= GITHUB_FILE_CAP or null_patch_count
        if needs_raw_diff:
            raw_diff = client.get_commit_diff(repo_owner, repo_name, commit.sha)
            if raw_diff:
                files = _parse_raw_diff_files(raw_diff)
                if null_patch_count:
                    logger.info(
                        f"Commit {commit.sha[:8]} had {null_patch_count} null patches — "
                        f"re-fetched raw diff ({len(files)} files)"
                    )
                else:
                    logger.info(
                        f"Commit {commit.sha[:8]} hit {GITHUB_FILE_CAP}-file cap — "
                        f"re-fetched raw diff ({len(files)} files)"
                    )
            else:
                logger.warning(
                    f"Commit {commit.sha[:8]} needs raw diff but fetch failed — will retry"
                )
                return None

        docs = []
        for file_data in files:
            doc_id, doc_data = _build_commit_file_doc(commit, file_data)
            if doc_id:
                docs.append((doc_id, doc_data))

        return es_service.bulk_index_documents(docs)

    except requests_lib.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 404:
            logger.warning(f"Commit {commit.sha[:8]} not found (404) — repo likely privated, marking processed")
            return 0
        logger.error(f"HTTP {status} error indexing commit {commit.sha}: {exc}", exc_info=True)
        return None

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

            result = _index_commit_code(commit, client, es_service, logger)
            if result is None:
                continue

            indexed_count += result
            commit.processed_at = timezone.now()
            commit.save(update_fields=["processed_at"])
            processed_count += 1
            processed_since_refresh += 1

            if processed_since_refresh >= CLAIM_REFRESH_EVERY:
                refresh_worker_claims(worker)
                reset_queries()
                processed_since_refresh = 0

    finally:
        clear_worker_model_claims(worker, "commit")

    logger.info(f"Processed: {processed_count}")
    logger.info(f"Indexed files: {indexed_count}")