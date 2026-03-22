import time
from typing import Dict, List, Optional, Tuple

from dateutil import parser

from apps.git_data.models import (
    Repo,
    User,
    RelationshipType,
    DiscoveryMethod,
)
from clients.github import RepositoryAccessBlockedException

from ..users.processing import (
    create_detailed_user,
    create_lightweight_user,
    create_user_relationship,
)


def _get_repo_owner(repo_data: Dict, fallback_username: str) -> str:
    full_name = repo_data.get("full_name", "")
    return full_name.split("/")[0] if "/" in full_name else fallback_username


def _parse_created_at(value: Optional[str], logger, label: str):
    if not value:
        return None

    try:
        return parser.parse(value)
    except Exception as exc:
        logger.warning(f"Could not parse created_at for {label}: {exc}")
        return None


def _repo_defaults(
    repo_data: Dict,
    repo_info: Dict,
    owner: User,
    languages: List[str],
    source_created_at,
    tags: Optional[List[str]] = None,
) -> Dict:
    return {
        "name": repo_data.get("name"),
        "full_name": repo_data.get("full_name"),
        "owner": owner,
        "description": repo_info.get("description", ""),
        "default_branch": repo_info.get("default_branch", "main"),
        "url": repo_info.get("html_url", ""),
        "stars": repo_info.get("stargazers_count", 0),
        "size": repo_info.get("size", 0),
        "is_fork": repo_info.get("fork", False),
        "homepage": repo_info.get("homepage") or None,
        "languages": languages,
        "source_created_at": source_created_at,
        "tags": tags or [],
    }


def fetch_all_user_repositories(client, username: str, logger, check_cancellation_func) -> List[Dict]:
    logger.info("Fetching repositories")
    all_repos: List[Dict] = []
    page = 1

    while True:
        if check_cancellation_func():
            logger.warning("Task cancelled during repository fetching")
            break

        try:
            repos = client.get_user_repos(username, page=page)
            if not repos:
                break

            all_repos.extend(repos)

            if len(repos) < 100:
                break

            page += 1
            time.sleep(0.1)

        except Exception as exc:
            if "404" in str(exc):
                logger.info(f"No repositories accessible for {username}")
            else:
                logger.error(f"Error fetching repositories page {page}: {exc}")
            break

    return all_repos


def categorize_repositories_by_ownership(repos: List[Dict], username: str) -> Tuple[List[Dict], List[Dict]]:
    owned_repos = []
    collaborative_repos = []

    for repo_data in repos:
        repo_owner = _get_repo_owner(repo_data, username)
        if repo_owner == username:
            owned_repos.append(repo_data)
        else:
            collaborative_repos.append(repo_data)

    return owned_repos, collaborative_repos


def create_detailed_repository_record(client, repo_owner: User, repo_data: Dict, logger) -> Repo:
    repo_name = repo_data.get("name")
    repo_full_name = repo_data.get("full_name")

    try:
        repo_info = client.get_repo_info(repo_owner.username, repo_name)
        time.sleep(0.1)

        languages_data = client.get_repo_languages(
            repo_owner.username, repo_name)
        languages = list(languages_data.keys()) if languages_data else []
        time.sleep(0.1)
        block_reason = None

    except RepositoryAccessBlockedException as exc:
        logger.warning(
            f"Repository {repo_full_name} access blocked ({exc.block_reason}), creating minimal record"
        )
        repo_info = repo_data
        languages = []
        block_reason = exc.block_reason

    repo, created = Repo.objects.get_or_create(
        source_repo_id=repo_info.get("id"),
        defaults=_repo_defaults(
            repo_data=repo_data,
            repo_info=repo_info,
            owner=repo_owner,
            languages=languages,
            source_created_at=_parse_created_at(
                repo_info.get("created_at"),
                logger,
                repo_full_name,
            ),
            tags=[f"block:{block_reason}"] if block_reason else [],
        ),
    )

    if not created:
        logger.info(f"Repository {repo_full_name} already exists")

    return repo


def create_lightweight_repository_record(repo_data: Dict, owner: User, logger) -> Repo:
    repo_full_name = repo_data.get("full_name")

    repo, created = Repo.objects.get_or_create(
        source_repo_id=repo_data.get("id"),
        defaults=_repo_defaults(
            repo_data=repo_data,
            repo_info=repo_data,
            owner=owner,
            languages=[],
            source_created_at=_parse_created_at(
                repo_data.get("created_at"),
                logger,
                repo_full_name,
            ),
        ),
    )

    if not created:
        logger.info(f"Repository {repo_full_name} already exists")

    return repo


def process_collaborative_repository(client, user: User, repo_data: Dict, logger) -> Tuple[Optional[Repo], bool]:
    repo_full_name = repo_data.get("full_name")
    repo_owner = _get_repo_owner(repo_data, user.username)

    repo_owner_user, owner_created = create_detailed_user(
        client,
        repo_owner,
        DiscoveryMethod.COLLABORATOR,
        logger,
    )

    if repo_owner_user is None:
        logger.warning(
            f"GitHub API failed for {repo_owner}, creating lightweight user record")
        repo_owner_user, owner_created = create_lightweight_user(
            client,
            repo_owner,
            DiscoveryMethod.COLLABORATOR,
            logger,
        )

    if repo_owner_user is None:
        return None, False

    try:
        repo_record = create_detailed_repository_record(
            client,
            repo_owner_user,
            repo_data,
            logger,
        )
    except Exception as exc:
        if "404" in str(exc):
            logger.info(
                f"Repo {repo_full_name} not accessible for detailed processing, creating lightweight record"
            )
        else:
            logger.error(
                f"Error creating detailed record for collaborative repo {repo_full_name}: {exc}")

        repo_record = create_lightweight_repository_record(
            repo_data, repo_owner_user, logger)

    create_user_relationship(
        from_user=user,
        to_user=repo_owner_user,
        relationship_type=RelationshipType.COLLABORATOR,
        repo=repo_record,
    )

    return repo_record, owner_created


def process_all_user_repositories(client, user: User, logger, check_cancellation_func) -> Tuple[int, int]:
    all_repos = fetch_all_user_repositories(
        client,
        user.username,
        logger,
        check_cancellation_func,
    )
    if not all_repos:
        return 0, 0

    owned_repos, collaborative_repos = categorize_repositories_by_ownership(
        all_repos,
        user.username,
    )

    owned_forks = sum(
        1 for repo_data in owned_repos if repo_data.get("fork", False))
    owned_originals = len(owned_repos) - owned_forks

    logger.info(
        f"Found {len(owned_repos)} owned repos ({owned_originals} original, {owned_forks} forks)"
    )
    logger.info(f"Found {len(collaborative_repos)} collaborative repos")

    prioritized_repos = owned_repos + collaborative_repos
    repos_processed = 0
    new_users_created = 0

    for index, repo_data in enumerate(prioritized_repos, start=1):
        if check_cancellation_func():
            logger.warning("Task cancelled during repository processing")
            break

        repo_name = repo_data.get("name")
        repo_full_name = repo_data.get("full_name")
        if not repo_name or not repo_full_name:
            continue

        logger.info(
            f"Processing repository {index}/{len(prioritized_repos)}: {repo_full_name}")

        repo_owner = _get_repo_owner(repo_data, user.username)
        is_owned_by_user = repo_owner == user.username

        try:
            if not is_owned_by_user:
                repo_record, owner_created = process_collaborative_repository(
                    client,
                    user,
                    repo_data,
                    logger,
                )
                if repo_record is None:
                    continue

                repos_processed += 1
                if owner_created:
                    new_users_created += 1
                continue

            if repo_data.get("fork", False):
                create_lightweight_repository_record(repo_data, user, logger)
            else:
                create_detailed_repository_record(
                    client, user, repo_data, logger)

            repos_processed += 1

        except Exception as exc:
            if "404" in str(exc):
                logger.info(f"Skipping {repo_full_name} (not accessible)")
            else:
                logger.error(f"Error processing repo {repo_full_name}: {exc}")

    if repos_processed > 0:
        logger.info(f"Processed {repos_processed} repositories")

    return repos_processed, new_users_created
