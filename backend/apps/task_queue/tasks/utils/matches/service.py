import re
from typing import Optional

from django.db import IntegrityError

from apps.git_data.models import Commit, Gist
from apps.search.models import Match, MatchType, Regex
from apps.search.services import ElasticsearchService
from apps.task_queue.tasks.utils.jobs import is_cancelled


PROGRESS_LOG_EVERY = 100


def _get_active_regexes():
    return list(
        Regex.objects
        .filter(is_active=True)
        .only("id", "name", "regex_pattern", "last_processed_at")
        .order_by("id")
    )


def _regex_label(regex: Regex) -> str:
    return f"{regex.id}:{regex.name or '<unnamed>'}"


def _compile_pattern(regex: Regex):
    try:
        return re.compile(regex.regex_pattern), None
    except re.error as exc:
        return None, str(exc)


def _get_commit_from_source(source: dict) -> Optional[Commit]:
    sha = source.get("source_id")
    repo_full_name = source.get("repo")

    if not sha or not repo_full_name:
        return None

    return (
        Commit.objects
        .select_related("repo")
        .filter(
            sha=sha,
            repo__full_name=repo_full_name,
        )
        .first()
    )


def _get_gist_from_source(source: dict) -> Optional[Gist]:
    source_id = source.get("source_id")
    if not source_id or ":" not in source_id:
        return None

    gist_id, revision_id = source_id.split(":", 1)

    return (
        Gist.objects
        .filter(
            gist_id=gist_id,
            revision_id=revision_id,
        )
        .first()
    )


def _resolve_source(source: dict):
    doc_type = source.get("type")

    if doc_type == "commit":
        return _get_commit_from_source(source), None

    if doc_type == "gist":
        return None, _get_gist_from_source(source)

    return None, None


def _extract_line_matches(compiled_pattern, content: str):
    if not content or compiled_pattern is None:
        return []

    results = []
    seen = set()

    for line in content.splitlines():
        for match in compiled_pattern.finditer(line):
            value = match.group(0)
            key = (value, line)
            if key in seen:
                continue
            seen.add(key)
            results.append((value, line))

    return results


def _create_match(regex, commit, gist, match_type, value, raw_line, filename):
    try:
        Match.objects.create(
            regex=regex,
            commit=commit,
            gist=gist,
            match_type=match_type,
            match=value,
            raw_match=raw_line,
            filename=filename or "",
        )
        return 1
    except IntegrityError:
        return 0


def _create_matches_for_document(regex, compiled_pattern, commit, gist, filename, additions, deletions):
    created = 0

    for value, raw_line in _extract_line_matches(compiled_pattern, additions):
        created += _create_match(
            regex=regex,
            commit=commit,
            gist=gist,
            match_type=MatchType.ADDITION,
            value=value,
            raw_line=raw_line,
            filename=filename,
        )

    for value, raw_line in _extract_line_matches(compiled_pattern, deletions):
        created += _create_match(
            regex=regex,
            commit=commit,
            gist=gist,
            match_type=MatchType.DELETION,
            value=value,
            raw_line=raw_line,
            filename=filename,
        )

    return created


def _get_document_timestamp(source: dict):
    return source.get("timestamp")


def _advance_regex_checkpoint(regex_id: int, timestamp):
    Regex.objects.filter(id=regex_id).update(last_processed_at=timestamp)


def _process_regex(
    es_service,
    regex: Regex,
    regex_number: int,
    regex_total: int,
    logger,
    job_id: Optional[str],
):
    compiled_pattern, compile_error = _compile_pattern(regex)
    regex_name = _regex_label(regex)

    if compiled_pattern is None:
        logger.warning(
            f"Skipping regex {regex_number}/{regex_total} [{regex_name}] due to invalid pattern: {compile_error}"
        )
        return {
            "scanned": 0,
            "created": 0,
            "skipped": 0,
            "eligible_total": 0,
            "cancelled": False,
        }

    eligible_total = es_service.count_documents_from_timestamp(
        timestamp=regex.last_processed_at,
    )

    logger.info(
        f"Regex {regex_number}/{regex_total} [{regex_name}] starting: "
        f"checkpoint={regex.last_processed_at or 'beginning'}, "
        f"eligible={eligible_total}, "
    )

    scanned_count = 0
    created_count = 0
    skipped_count = 0
    cancelled = False
    last_processed_at = regex.last_processed_at

    hits = es_service.scan_documents_from_timestamp(
        timestamp=regex.last_processed_at,
    )

    for hit in hits:

        if is_cancelled(job_id):
            cancelled = True
            logger.warning(
                f"Regex {regex_number}/{regex_total} [{regex_name}] cancelled: "
                f"scanned={scanned_count}/{eligible_total}, "
                f"matches_created={created_count}, skipped={skipped_count}"
            )
            break

        source = hit.get("_source", {})
        if not source:
            skipped_count += 1
            scanned_count += 1
            continue

        timestamp = _get_document_timestamp(source)
        if timestamp is None:
            skipped_count += 1
            scanned_count += 1
            continue

        filename = source.get("filename", "")
        additions = source.get("additions", "") or ""
        deletions = source.get("deletions", "") or ""

        commit, gist = _resolve_source(source)
        if not commit and not gist:
            skipped_count += 1
            scanned_count += 1
            continue

        created_count += _create_matches_for_document(
            regex=regex,
            compiled_pattern=compiled_pattern,
            commit=commit,
            gist=gist,
            filename=filename,
            additions=additions,
            deletions=deletions,
        )

        _advance_regex_checkpoint(
            regex_id=regex.id,
            timestamp=timestamp,
        )
        last_processed_at = timestamp
        scanned_count += 1

        if scanned_count % PROGRESS_LOG_EVERY == 0:
            logger.info(
                f"Regex {regex_number}/{regex_total} [{regex_name}] progress: "
                f"scanned={scanned_count}/{eligible_total}, "
                f"matches_created={created_count}, skipped={skipped_count}, "
                f"last_processed_at={last_processed_at}"
            )

    logger.info(
        f"Regex {regex_number}/{regex_total} [{regex_name}] finished: "
        f"scanned={scanned_count}/{eligible_total}, "
        f"matches_created={created_count}, skipped={skipped_count}, "
        f"last_processed_at={last_processed_at or 'unchanged'}"
    )

    return {
        "scanned": scanned_count,
        "created": created_count,
        "skipped": skipped_count,
        "eligible_total": eligible_total,
        "cancelled": cancelled,
    }


def find_matches(
    logger,
    job_id: Optional[str],
):
    es_service = ElasticsearchService()
    if not es_service.is_available():
        raise Exception("Elasticsearch is not available")

    regexes = _get_active_regexes()
    if not regexes:
        logger.warning("No active regexes found")
        return

    total_scanned = 0
    total_created = 0
    total_skipped = 0
    total_eligible = 0

    logger.info(
        f"Starting match scan: regexes={len(regexes)}"
    )

    for index, regex in enumerate(regexes, start=1):
        if is_cancelled(job_id):
            logger.warning(
                f"Match scan cancelled before regex {index}/{len(regexes)}: "
                f"scanned={total_scanned}, eligible={total_eligible}, "
                f"matches_created={total_created}, skipped={total_skipped}"
            )
            break

        result = _process_regex(
            es_service=es_service,
            regex=regex,
            regex_number=index,
            regex_total=len(regexes),
            logger=logger,
            job_id=job_id,
        )

        total_scanned += result["scanned"]
        total_created += result["created"]
        total_skipped += result["skipped"]
        total_eligible += result["eligible_total"]

        logger.info(
            f"Overall progress after regex {index}/{len(regexes)}: "
            f"scanned={total_scanned}/{total_eligible}, "
            f"matches_created={total_created}, skipped={total_skipped}"
        )

        if result["cancelled"]:
            break

    logger.info(
        f"Match scan complete: scanned={total_scanned}/{total_eligible}, "
        f"matches_created={total_created}, skipped={total_skipped}, "
        f"regexes={len(regexes)}"
    )
