import logging
import regex
import time
from typing import Optional

from dateutil import parser as dateutil_parser
from django.db import IntegrityError, reset_queries, transaction

logger = logging.getLogger(__name__)

from apps.git_data.models import Commit, Gist
from apps.search.models import Match, MatchStatus, Regex
from apps.search.services import ElasticsearchService
from apps.task_queue.tasks.utils.jobs import is_cancelled


PROGRESS_LOG_EVERY = 100
CHECKPOINT_FLUSH_EVERY = 100
MAX_ADDITIONS_BYTES = 500_000
MAX_LINE_LENGTH = 2_000
REGEX_TIMEOUT_SECS = 3.0

_IGNORED_PATH_SEGMENTS = frozenset([
    "node_modules",
    "venv",
    ".venv",
    "virtualenv",
    "site-packages",
    ".tox",
    "vendor",
    "bower_components",
])


def _is_ignored_filename(filename: str) -> bool:
    if not filename:
        return False
    parts = filename.replace("\\", "/").split("/")
    return any(p in _IGNORED_PATH_SEGMENTS for p in parts)


def _get_active_regexes():
    return list(
        Regex.objects
        .filter(is_active=True)
        .only("id", "name", "regex_pattern", "last_processed_at")
        .order_by("id")
    )


def _regex_label(regex: Regex) -> str:
    return f"{regex.id}:{regex.name or '<unnamed>'}"


def _compile_pattern(rx: Regex):
    try:
        return regex.compile(rx.regex_pattern), None
    except regex.error as exc:
        return None, str(exc)


def _get_active_regexes_compiled(logger):
    result = []
    for rx in _get_active_regexes():
        compiled, error = _compile_pattern(rx)
        if compiled is None:
            logger.warning(f"Skipping regex {_regex_label(rx)}: {error}")
            continue
        result.append((rx, compiled))
    return result


def _min_checkpoint(regexes):
    checkpoints = [r.last_processed_at for r in regexes]
    if any(cp is None for cp in checkpoints):
        return None
    return min(checkpoints)


def _flush_checkpoints(latest_ts: dict):
    for regex_id, ts in latest_ts.items():
        Regex.objects.filter(id=regex_id).update(last_processed_at=ts)


def _parse_es_timestamp(value):
    if value is None:
        return None
    if hasattr(value, "year"):
        return value
    try:
        return dateutil_parser.parse(value)
    except Exception:
        return None


def _get_commit_from_source(source: dict) -> Optional[Commit]:
    sha = source.get("source_id")
    repo_name = source.get("repo")

    if not sha or not repo_name:
        return None

    return (
        Commit.objects
        .select_related("repo")
        .filter(
            sha=sha,
            repo__name=repo_name,
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
        return [], False

    deadline = time.monotonic() + REGEX_TIMEOUT_SECS
    results = []
    seen = set()

    for line in content.splitlines():
        if len(line) > MAX_LINE_LENGTH:
            continue

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return results, True

        try:
            for match in compiled_pattern.finditer(line, timeout=remaining):
                value = match.group(0)
                key = (value, line)
                if key in seen:
                    continue
                seen.add(key)
                results.append((value, line))
        except TimeoutError:
            return results, True

    return results, False


def _find_deletions_batch(es_service, values: list) -> dict:
    """Return {value: (commit_or_None, gist_or_None)} for a list of values via msearch."""
    if not values:
        return {}
    body = []
    for value in values:
        body.append({"index": es_service._index_name})
        body.append({
            "query": {"match_phrase": {"deletions": value}},
            "sort": [{"date": "asc"}],
            "size": 1,
            "_source": ["source_id", "repo", "type"],
        })
    try:
        responses = es_service._client.msearch(body=body)
    except Exception:
        return {v: (None, None) for v in values}

    result = {}
    for value, resp in zip(values, responses.get("responses", [])):
        if resp.get("error"):
            result[value] = (None, None)
            continue
        hits = resp.get("hits", {}).get("hits", [])
        result[value] = _resolve_source(hits[0]["_source"]) if hits else (None, None)
    return result


def _create_matches_for_document(compiled_regexes, commit, gist, filename, additions, es_service):
    """
    Process all regexes for one document in a single pass, batching ES and DB lookups.
    compiled_regexes: list of (regex, compiled_pattern)
    """
    if _is_ignored_filename(filename):
        return 0

    if len(additions) > MAX_ADDITIONS_BYTES:
        logger.warning(
            f"Skipping oversized document: {filename!r} ({len(additions)}b > {MAX_ADDITIONS_BYTES}b)"
        )
        return 0

    # Collect all candidates across every regex
    candidates = []
    for rx, compiled_pattern in compiled_regexes:
        line_matches, timed_out = _extract_line_matches(compiled_pattern, additions)
        if timed_out:
            logger.warning(
                f"Regex {_regex_label(rx)} timed out after {REGEX_TIMEOUT_SECS}s "
                f"on {filename!r} ({len(additions)}b)"
            )
        for value, raw_line in line_matches:
            candidates.append((rx, value, raw_line))

    if not candidates:
        return 0

    unique_values = list({v for _, v, _ in candidates})

    # One ES msearch for all deletion lookups
    deletions = _find_deletions_batch(es_service, unique_values)

    # One DB query for all false positive statuses
    fp_values = set(
        Match.objects
        .filter(match__in=unique_values, status=MatchStatus.FALSE_POSITIVE)
        .values_list("match", flat=True)
        .distinct()
    )

    created = 0
    for rx, value, raw_line in candidates:
        status = MatchStatus.FALSE_POSITIVE if value in fp_values else MatchStatus.NONE
        deleted_in_commit, deleted_in_gist = deletions.get(value, (None, None))

        try:
            with transaction.atomic():
                Match.objects.create(
                    regex=rx,
                    commit=commit,
                    gist=gist,
                    repo=commit.repo if commit else None,
                    gist_base_id=gist.gist_id if gist else None,
                    match=value,
                    raw_match=raw_line,
                    filename=filename or "",
                    status=status,
                    deleted_in_commit=deleted_in_commit,
                    deleted_in_gist=deleted_in_gist,
                )
            created += 1
        except IntegrityError:
            pass

    return created


def _scan_global(es_service, compiled_regexes, logger, job_id):
    regexes = [r for r, _ in compiled_regexes]
    min_cp = _min_checkpoint(regexes)

    eligible_total = es_service.count_documents_from_timestamp(timestamp=min_cp)
    logger.info(
        f"Global scan: regexes={len(compiled_regexes)}, "
        f"checkpoint={min_cp or 'beginning'}, eligible={eligible_total}"
    )

    scanned = 0
    created = 0
    skipped = 0
    latest_ts = {}
    cancelled = False

    try:
        for hit in es_service.scan_documents_from_timestamp(timestamp=min_cp):
            if is_cancelled(job_id):
                cancelled = True
                logger.warning(
                    f"Global scan cancelled: scanned={scanned}/{eligible_total}, "
                    f"matches_created={created}, skipped={skipped}"
                )
                break

            source = hit.get("_source", {})
            if not source:
                skipped += 1
                scanned += 1
                continue

            ts = _parse_es_timestamp(source.get("timestamp"))
            if ts is None:
                skipped += 1
                scanned += 1
                continue

            scanned += 1

            eligible = [
                (r, p) for r, p in compiled_regexes
                if r.last_processed_at is None or r.last_processed_at < ts
            ]

            if not eligible:
                continue

            commit, gist = _resolve_source(source)
            if not commit and not gist:
                skipped += 1
                continue

            filename = source.get("filename", "")
            additions = source.get("additions", "") or ""
            source_id = source.get("source_id", "")

            t0 = time.monotonic()
            created += _create_matches_for_document(
                compiled_regexes=eligible,
                commit=commit,
                gist=gist,
                filename=filename,
                additions=additions,
                es_service=es_service,
            )
            elapsed = time.monotonic() - t0
            if elapsed > 2:
                logger.warning(
                    f"Slow document: {filename!r} took {elapsed:.1f}s "
                    f"(source_id={source_id!r}, additions={len(additions)}b)"
                )

            for regex, _ in eligible:
                if regex.id not in latest_ts or latest_ts[regex.id] < ts:
                    latest_ts[regex.id] = ts

            if scanned % CHECKPOINT_FLUSH_EVERY == 0:
                _flush_checkpoints(latest_ts)
                reset_queries()
                logger.info(
                    f"Global scan progress: scanned={scanned}/{eligible_total}, "
                    f"matches_created={created}, skipped={skipped}"
                )

    finally:
        _flush_checkpoints(latest_ts)

    logger.info(
        f"Global scan complete: scanned={scanned}/{eligible_total}, "
        f"matches_created={created}, skipped={skipped}"
    )


def _scan_for_user(es_service, compiled_regexes, username, logger, job_id):
    eligible_total = es_service.count_documents_from_timestamp(username=username)
    logger.info(
        f"User scan: user={username}, regexes={len(compiled_regexes)}, eligible={eligible_total}"
    )

    scanned = 0
    created = 0
    skipped = 0

    for hit in es_service.scan_documents_from_timestamp(username=username):
        if is_cancelled(job_id):
            logger.warning(
                f"User scan cancelled: scanned={scanned}/{eligible_total}, "
                f"matches_created={created}, skipped={skipped}"
            )
            break

        source = hit.get("_source", {})
        if not source:
            skipped += 1
            scanned += 1
            continue

        scanned += 1

        commit, gist = _resolve_source(source)
        if not commit and not gist:
            skipped += 1
            continue

        filename = source.get("filename", "")
        additions = source.get("additions", "") or ""
        source_id = source.get("source_id", "")

        t0 = time.monotonic()
        created += _create_matches_for_document(
            compiled_regexes=compiled_regexes,
            commit=commit,
            gist=gist,
            filename=filename,
            additions=additions,
            es_service=es_service,
        )
        elapsed = time.monotonic() - t0
        if elapsed > 2:
            logger.warning(
                f"Slow document: {filename!r} took {elapsed:.1f}s "
                f"(source_id={source_id!r}, additions={len(additions)}b)"
            )

        if scanned % PROGRESS_LOG_EVERY == 0:
            reset_queries()
            logger.info(
                f"User scan progress: scanned={scanned}/{eligible_total}, "
                f"matches_created={created}, skipped={skipped}"
            )

    logger.info(
        f"User scan complete: user={username}, scanned={scanned}/{eligible_total}, "
        f"matches_created={created}, skipped={skipped}"
    )


def find_matches(logger, job_id: Optional[str], username: Optional[str] = None):
    es_service = ElasticsearchService()
    if not es_service.is_available():
        raise Exception("Elasticsearch is not available")

    compiled_regexes = _get_active_regexes_compiled(logger)
    if not compiled_regexes:
        logger.warning("No active regexes found (or all failed to compile)")
        return

    if username:
        _scan_for_user(es_service, compiled_regexes, username, logger, job_id)
    else:
        _scan_global(es_service, compiled_regexes, logger, job_id)
