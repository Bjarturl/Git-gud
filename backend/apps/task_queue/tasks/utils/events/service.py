import gzip
import json
import time
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.db import transaction

from apps.events.models import RawEvent
from apps.task_queue.tasks.utils.jobs import is_cancelled


GHARCHIVE_URL = "https://data.gharchive.org/{hour}.json.gz"


def _get_resume_hour():
    last = (
        RawEvent.objects
        .order_by("-observed_at")
        .values_list("observed_at", flat=True)
        .first()
    )

    if not last:
        return datetime(2011, 2, 12, 0, tzinfo=dt_timezone.utc)

    return last.replace(minute=0, second=0, microsecond=0)


def _iter_hours(start: datetime, end: datetime):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(hours=1)


def _fetch_hour_stream(hour: datetime):
    hour_str = f"{hour.year}-{hour.month:02d}-{hour.day:02d}-{hour.hour}"
    url = GHARCHIVE_URL.format(hour=hour_str)

    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()

    with gzip.GzipFile(fileobj=resp.raw) as gz:
        for line in gz:
            yield line


def _extract_rows(line, hour_dt):
    try:
        event = json.loads(line)
    except Exception:
        return []

    if event.get("type") != "PushEvent":
        return []

    repo = event.get("repo") or {}
    payload = event.get("payload") or {}

    repo_id = repo.get("id")
    if not repo_id:
        return []

    shas = set()

    for c in payload.get("commits", []):
        sha = c.get("sha")
        if sha:
            shas.add(sha)

    if payload.get("head"):
        shas.add(payload["head"])

    if payload.get("before"):
        shas.add(payload["before"])

    rows = []
    for sha in shas:
        try:
            rows.append(
                RawEvent(
                    repo_id=repo_id,
                    sha=bytes.fromhex(sha),
                    observed_at=hour_dt,
                )
            )
        except Exception:
            continue

    return rows


def _bulk_insert(rows):
    if not rows:
        return 0

    with transaction.atomic():
        objs = RawEvent.objects.bulk_create(
            rows,
            ignore_conflicts=True,
            batch_size=10000,
        )
    return len(objs)


def process_gharchive(logger, job_id: str):
    if is_cancelled(job_id):
        logger.warning("Task cancelled before starting")
        return

    start_hour = _get_resume_hour()
    end_hour = datetime.now(tz=dt_timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )

    logger.info(f"Processing from {start_hour} to {end_hour}")

    total_inserted = 0

    for hour in _iter_hours(start_hour, end_hour):
        if is_cancelled(job_id):
            logger.warning("Task cancelled during processing")
            break

        hour_str = hour.strftime("%Y-%m-%d-%H")
        logger.info(f"Processing hour {hour_str}")

        batch = []
        inserted_this_hour = 0

        try:
            for line in _fetch_hour_stream(hour):
                rows = _extract_rows(line, hour)
                if not rows:
                    continue

                batch.extend(rows)

                if len(batch) >= 10000:
                    inserted = _bulk_insert(batch)
                    inserted_this_hour += inserted
                    total_inserted += inserted
                    batch.clear()

            if batch:
                inserted = _bulk_insert(batch)
                inserted_this_hour += inserted
                total_inserted += inserted
                batch.clear()

            logger.info(
                f"Hour {hour_str} done. Inserted {inserted_this_hour} rows"
            )

        except Exception as exc:
            logger.error(
                f"Error processing hour {hour_str}: {exc}", exc_info=True)

        time.sleep(0.2)

    logger.info(f"Total inserted: {total_inserted}")
