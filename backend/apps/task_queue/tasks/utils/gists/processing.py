import time
from typing import Dict, List, Optional

from dateutil import parser

from apps.git_data.models import Gist, User


def _parse_datetime(value: Optional[str], logger, label: str):
    if not value:
        return None

    try:
        return parser.parse(value)
    except Exception as exc:
        logger.warning(f"Could not parse datetime for {label}: {exc}")
        return None


def fetch_all_user_gists(client, username: str, logger, check_cancellation_func) -> List[Dict]:
    logger.info("Fetching gists")
    all_gists: List[Dict] = []
    page = 1

    while True:
        if check_cancellation_func():
            logger.warning("Task cancelled during gist fetching")
            break

        try:
            gists = client.get_user_gists(username, page=page)
            if not gists:
                break

            all_gists.extend(gists)

            if len(gists) < 100:
                break

            page += 1
            time.sleep(0.1)

        except Exception as exc:
            if "404" in str(exc):
                logger.info(f"No gists accessible for {username}")
            else:
                logger.error(f"Error fetching gists page {page}: {exc}")
            break

    return all_gists


def _build_gist_defaults(user: User, gist_details: Dict, revision_data: Dict, logger) -> Dict:
    gist_id = gist_details.get("id")
    revision_id = revision_data.get("version", "current")

    created_at = _parse_datetime(
        gist_details.get("created_at"),
        logger,
        f"gist {gist_id}",
    )
    committed_at = _parse_datetime(
        revision_data.get("committed_at"),
        logger,
        f"gist {gist_id} revision {revision_id}",
    )

    return {
        "author": user,
        "description": gist_details.get("description") or "",
        "url": gist_details.get("html_url") or "",
        "filenames": list((gist_details.get("files") or {}).keys()),
        "source_created_at": committed_at or created_at,
    }


def process_gist_with_revision_history(client, user: User, gist_data: Dict, logger) -> int:
    gist_id = gist_data.get("id")
    if not gist_id:
        return 0

    revisions_created = 0

    try:
        gist_details = client.get_gist_details(gist_id)
        time.sleep(0.1)

        if not gist_details:
            return 0

        history = gist_details.get("history") or [gist_details]

        for revision_data in history:
            revision_id = revision_data.get("version", "current")

            if Gist.objects.filter(gist_id=gist_id, revision_id=revision_id).exists():
                continue

            revision_details = gist_details
            if revision_id != "current":
                try:
                    revision_details = client.get_gist_revision_details(
                        gist_id, revision_id)
                    time.sleep(0.1)
                except Exception as exc:
                    logger.warning(
                        f"Could not fetch revision details for gist {gist_id} revision {revision_id}: {exc}"
                    )

            Gist.objects.create(
                gist_id=gist_id,
                revision_id=revision_id,
                **_build_gist_defaults(user, revision_details, revision_data, logger),
            )
            revisions_created += 1

    except Exception as exc:
        if "404" in str(exc):
            logger.info(f"Gist {gist_id} not accessible")
        else:
            logger.error(f"Error processing gist {gist_id}: {exc}")

    return revisions_created


def get_gist_summary_for_user(user: User) -> Dict[str, int]:
    total_revisions = Gist.objects.filter(author=user).count()
    unique_gists = Gist.objects.filter(
        author=user).values("gist_id").distinct().count()

    return {
        "unique_gists": unique_gists,
        "total_revisions": total_revisions,
        "avg_revisions_per_gist": total_revisions / unique_gists if unique_gists > 0 else 0,
    }


def process_all_user_gists(client, user, logger, check_cancellation_func) -> int:
    all_gists = fetch_all_user_gists(
        client,
        user.username,
        logger,
        check_cancellation_func,
    )
    if not all_gists:
        return 0

    logger.info(f"Processing {len(all_gists)} gists")

    total_revisions = 0

    for index, gist_data in enumerate(all_gists, start=1):
        if check_cancellation_func():
            logger.warning("Task cancelled during gist processing")
            break

        gist_id = gist_data.get("id")
        if not gist_id:
            continue

        logger.info(f"Processing gist {index}/{len(all_gists)}: {gist_id}")

        revisions_created = process_gist_with_revision_history(
            client,
            user,
            gist_data,
            logger,
        )
        total_revisions += revisions_created

        if revisions_created > 0:
            logger.info(
                f"Created {revisions_created} revision(s) for gist {gist_id}")

    if total_revisions > 0:
        logger.info(f"Created {total_revisions} total gist revisions")

    return total_revisions
