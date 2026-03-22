import difflib
import time
from typing import Optional, Tuple

from django.utils import timezone

from apps.search.services import ElasticsearchService
from apps.git_data.models import Gist
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
from .helpers import is_binary_filename


CLAIM_BATCH_SIZE = 1000
CLAIM_REFRESH_EVERY = 100


def _get_gist_queryset():
    return Gist._base_manager.filter(processed_at__isnull=True)


def _claim_next_gist_batch(worker, logger, batch_size: int = CLAIM_BATCH_SIZE) -> list[Gist]:
    claimed_ids = get_active_claimed_ids("gist", exclude_worker_id=worker.id)

    queryset = _get_gist_queryset()

    if claimed_ids:
        queryset = queryset.exclude(id__in=claimed_ids)

    gist_ids = list(
        queryset.order_by("id").values_list("id", flat=True)[:batch_size]
    )

    set_worker_model_claims(worker, "gist", gist_ids)

    if not gist_ids:
        return []

    gists = list(
        Gist.objects
        .filter(id__in=gist_ids)
        .select_related("author")
        .order_by("id")
    )

    logger.info(f"Claimed {len(gists)} gists")
    return gists


def _get_previous_gist(gist: Gist) -> Optional[Gist]:
    return (
        Gist.objects
        .filter(
            gist_id=gist.gist_id,
            processed_at__isnull=False,
            source_created_at__lt=gist.source_created_at,
        )
        .order_by("-source_created_at")
        .first()
    )


def _get_revision_files(client: GitHubAPIClient, gist_id: str, revision_id: str) -> dict:
    try:
        if revision_id == "current":
            details = client.get_gist_details(gist_id)
        else:
            details = client.get_gist_revision_details(gist_id, revision_id)

        if not details:
            return {}

        return details.get("files", {}) or {}
    except Exception:
        return {}


def _compute_diff(old_content: str, new_content: str) -> Tuple[str, str]:
    old_lines = old_content.split("\n") if old_content else []
    new_lines = new_content.split("\n") if new_content else []

    additions = []
    deletions = []

    for line in difflib.unified_diff(old_lines, new_lines, lineterm=""):
        if line.startswith("+") and not line.startswith("+++"):
            additions.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            deletions.append(line[1:])

    return "\n".join(additions), "\n".join(deletions)


def _index_gist_code(
    gist: Gist,
    client: GitHubAPIClient,
    es_service: ElasticsearchService,
    logger,
) -> bool | None:
    try:
        if not es_service.is_available():
            return None

        current_files = _get_revision_files(
            client, gist.gist_id, gist.revision_id)
        previous_gist = _get_previous_gist(gist)

        previous_files = (
            _get_revision_files(client, previous_gist.gist_id,
                                previous_gist.revision_id)
            if previous_gist
            else {}
        )

        all_filenames = set(previous_files) | set(current_files)
        indexed_files = 0

        for filename in all_filenames:
            is_binary = is_binary_filename(filename)

            previous_content = previous_files.get(
                filename, {}).get("content", "") or ""
            current_content = current_files.get(
                filename, {}).get("content", "") or ""

            if is_binary:
                additions = ""
                deletions = ""
            else:
                additions, deletions = _compute_diff(
                    previous_content, current_content)

            if not additions and not deletions and not is_binary:
                continue

            doc_id = f"gist:{gist.gist_id}:{gist.revision_id}:{filename}"
            doc_data = {
                "user": gist.author.username,
                "user_company": gist.author.company or "",
                "source_id": f"{gist.gist_id}:{gist.revision_id}",
                "message": gist.description or "",
                "date": gist.source_created_at or gist.created_at,
                "filename": filename,
                "url": gist.url,
                "timestamp": timezone.now(),
                "type": "gist",
                "additions": additions,
                "deletions": deletions,
            }

            if es_service.index_document(doc_data, doc_id):
                indexed_files += 1

        time.sleep(0.1)
        return indexed_files > 0

    except Exception as exc:
        logger.error(
            f"Error indexing gist {gist.gist_id}: {exc}", exc_info=True)
        return None


def process_gists(
    logger,
    job_id: Optional[str],
):
    es_service = ElasticsearchService()
    if not es_service.is_available():
        raise Exception("Elasticsearch is not available")

    client = GitHubAPIClient()
    worker = get_job_worker(job_id)
    reset_worker_claims(worker)

    total_available = _get_gist_queryset().count()

    logger.info(f"Found {total_available} gists available")

    if total_available == 0:
        logger.info("No more gists to process")
        return

    processed_count = 0
    indexed_count = 0
    processed_since_refresh = 0
    gists_batch: list[Gist] = []

    try:
        while True:
            if is_cancelled(job_id):
                logger.warning(
                    f"Task cancelled after processing {processed_count} gists")
                break

            if not gists_batch:
                gists_batch = _claim_next_gist_batch(worker, logger)

                if not gists_batch:
                    logger.info("No more gists to process")
                    break

            gist = gists_batch.pop(0)

            if gist.processed_at is not None:
                continue

            logger.info(
                f"Processing gist {processed_count + 1}/{total_available}: "
                f"{gist.gist_id} (rev {gist.revision_id})"
            )

            indexed = _index_gist_code(gist, client, es_service, logger)
            if indexed is None:
                logger.warning(
                    f"Skipping processed_at update for gist {gist.gist_id} "
                    f"(rev {gist.revision_id})"
                )
                continue

            if indexed:
                indexed_count += 1

            gist.processed_at = timezone.now()
            gist.save(update_fields=["processed_at"])

            processed_count += 1
            processed_since_refresh += 1

            if processed_since_refresh >= CLAIM_REFRESH_EVERY:
                refresh_worker_claims(worker)
                processed_since_refresh = 0

            logger.info(f"Progress: {processed_count}/{total_available}")
            logger.info(f"Indexed: {indexed_count}")

    finally:
        clear_worker_model_claims(worker, "gist")

    logger.info(f"Processed: {processed_count}")
    logger.info(f"Indexed: {indexed_count}")
