import time
from typing import Dict, List, Set, Tuple, Optional

from dateutil import parser as date_parser
from django.db import IntegrityError

from apps.git_data.models import (
    Commit,
    Repo,
    User,
    RelationshipType,
    DiscoveryMethod,
)
from ..users.processing import (
    create_detailed_user,
    create_lightweight_user,
    create_user_relationship,
)


def _parse_commit_date(value: Optional[str], logger):
    if not value:
        return None

    try:
        return date_parser.parse(value)
    except Exception as e:
        logger.warning(f"Could not parse commit date: {e}")
        return None


def update_user_profile_from_commit(user: User, commit_author_info: Dict, logger) -> bool:
    updated = False
    commit_name = commit_author_info.get("name")
    commit_email = commit_author_info.get("email")

    if not user.name and commit_name:
        user.name = commit_name
        updated = True
        logger.info(f"Updated {user.username} name: {commit_name}")

    if not user.email and commit_email and "@noreply.github.com" not in commit_email:
        user.email = commit_email
        updated = True
        logger.info(f"Updated {user.username} email: {commit_email}")

    if updated:
        user.save()

    return updated


def _get_contributor_user(
    client,
    username: str,
    discovery_method: DiscoveryMethod,
    logger,
) -> Tuple[Optional[User], bool]:
    user, created = create_detailed_user(
        client, username, discovery_method, logger)
    if user is not None:
        return user, created

    logger.warning(
        f"GitHub API failed for {username}, creating lightweight user record")
    return create_lightweight_user(client, username, discovery_method, logger)


def _create_contributor_relationship(contributor: Optional[User], repo: Repo, logger) -> None:
    if not contributor or contributor == repo.owner:
        return

    try:
        create_user_relationship(
            from_user=contributor,
            to_user=repo.owner,
            relationship_type=RelationshipType.CONTRIBUTOR,
            repo=repo,
        )
    except Exception as e:
        logger.warning(f"Error creating contributor relationship: {e}")


def _link_pull_request_commits(client, repo: Repo, pull_number: int, logger) -> int:
    page = 1
    linked = 0

    while True:
        pr_commits = client.get_pull_request_commits(
            repo.owner.username,
            repo.name,
            pull_number,
            page=page,
            per_page=100,
        )

        if not pr_commits:
            break

        shas = [item.get("sha") for item in pr_commits if item.get("sha")]
        if shas:
            updated = (
                Commit.objects
                .filter(repo=repo, sha__in=shas, pr_number__isnull=True)
                .update(pr_number=pull_number)
            )
            linked += updated

        if len(pr_commits) < 100:
            break

        page += 1
        time.sleep(0.1)

    return linked


def fetch_repository_branches(client, repo_owner: str, repo_name: str, logger) -> List[Dict]:
    logger.info("Fetching branches")
    all_branches: List[Dict] = []
    page = 1

    while True:
        try:
            branches = client.get_repo_branches(
                repo_owner, repo_name, page=page)
            if not branches:
                break

            all_branches.extend(branches)

            if len(branches) < 100:
                break

            page += 1
            time.sleep(0.1)

        except Exception as e:
            if "404" in str(e):
                logger.info("No more branches accessible")
            else:
                logger.error(f"Error fetching branches page {page}: {e}")
            break

    logger.info(f"Found {len(all_branches)} branches")
    return all_branches


def fetch_commits_from_branch(
    client,
    repo_owner: str,
    repo_name: str,
    branch_name: str,
    existing_shas: Set[str],
    logger,
    check_cancellation_func,
) -> Tuple[List[Dict], bool]:
    logger.info(f"Processing branch: {branch_name}")
    new_commits: List[Dict] = []
    page = 1
    pages_without_new_commits = 0

    while True:
        if check_cancellation_func():
            logger.warning("Task cancelled during branch processing")
            return new_commits, False

        try:
            commits = client.get_repo_commits(
                repo_owner,
                repo_name,
                sha=branch_name,
                page=page,
                per_page=100,
            )
            if not commits:
                break

            new_commits_in_page = 0

            for commit_data in commits:
                if not commit_data:
                    raise ValueError(f"Got empty commit data on page {page}")

                commit_sha = commit_data.get("sha")
                if not commit_sha:
                    raise ValueError(f"Commit missing SHA on page {page}")

                if commit_sha not in existing_shas:
                    commit_data["branch_name"] = branch_name
                    new_commits.append(commit_data)
                    existing_shas.add(commit_sha)
                    new_commits_in_page += 1

            if new_commits_in_page == 0:
                pages_without_new_commits += 1
                logger.info(
                    f"Page {page}: 0 new commits (consecutive empty pages: {pages_without_new_commits})"
                )
                if pages_without_new_commits >= 3:
                    logger.info(f"Skipping rest of branch {branch_name}")
                    break
            else:
                pages_without_new_commits = 0
                logger.info(f"Page {page}: {new_commits_in_page} new commits")

            if len(commits) < 100:
                break

            page += 1
            time.sleep(0.1)

        except Exception as e:
            if "404" in str(e):
                logger.info(f"Branch {branch_name} not accessible")
            else:
                logger.error(
                    f"Error fetching commits from {branch_name} page {page}: {e}")
            break

    logger.info(f"Branch {branch_name}: {len(new_commits)} unique commits")
    return new_commits, True


def _create_minimal_commit_record(repo: Repo, commit_sha: str, commit_info: Dict, branch_name: str, logger) -> Optional[Commit]:
    try:
        commit_record = Commit.objects.create(
            sha=commit_sha,
            repo=repo,
            message=commit_info.get("message", "Error retrieving message"),
            branch_name=branch_name or "unknown",
        )
        logger.info(f"Created minimal commit record for {commit_sha}")
        return commit_record

    except IntegrityError as e:
        if "duplicate key value violates unique constraint" in str(e) and "git_commit_sha_repo_id" in str(e):
            logger.debug(
                f"Minimal commit {commit_sha} already exists - skipping")
            return None

        logger.error(
            f"Failed to create minimal commit record for {commit_sha}: {e}")
        return None

    except Exception as e:
        logger.error(
            f"Failed to create minimal commit record for {commit_sha}: {e}")
        return None


def create_commit_record_with_users(client, repo: Repo, commit_data: Dict, logger) -> Tuple[Optional[Commit], int]:
    if not commit_data:
        raise ValueError("Received empty commit_data")

    commit_sha = commit_data.get("sha")
    if not commit_sha:
        raise ValueError("Missing SHA in commit data")

    commit_info = commit_data.get("commit", {})
    branch_name = commit_data.get("branch_name", "unknown")

    stats = commit_data.get("stats") or {}
    additions = stats.get("additions", 0)
    deletions = stats.get("deletions", 0)

    if not stats:
        try:
            detailed_commit = client.get_commit_details(
                repo.owner.username, repo.name, commit_sha)
            if detailed_commit:
                detailed_stats = detailed_commit.get("stats") or {}
                additions = detailed_stats.get("additions", 0)
                deletions = detailed_stats.get("deletions", 0)
                if detailed_commit.get("commit"):
                    commit_info = detailed_commit["commit"]
        except Exception as e:
            logger.warning(
                f"Could not fetch detailed stats for commit {commit_sha}: {e}")

    author_info = commit_info.get("author", {})
    committer_info = commit_info.get("committer", {})

    author_user_data = commit_data.get("author")
    committer_user_data = commit_data.get("committer")

    new_users_count = 0
    author_user = None
    committer_user = None

    if author_user_data and author_user_data.get("login"):
        author_username = author_user_data["login"]
        author_user, created = _get_contributor_user(
            client,
            author_username,
            DiscoveryMethod.CONTRIBUTOR,
            logger,
        )
        if created and author_user:
            new_users_count += 1

        if author_user and author_info:
            update_user_profile_from_commit(author_user, author_info, logger)

    if committer_user_data and committer_user_data.get("login"):
        committer_username = committer_user_data["login"]
        if not author_user_data or committer_username != author_user_data.get("login"):
            committer_user, created = _get_contributor_user(
                client,
                committer_username,
                DiscoveryMethod.CONTRIBUTOR,
                logger,
            )
            if created and committer_user:
                new_users_count += 1

            if committer_user and committer_info:
                update_user_profile_from_commit(
                    committer_user, committer_info, logger)

    commit_record = None
    commit_date = _parse_commit_date(author_info.get("date"), logger)

    try:
        commit_record = Commit.objects.create(
            sha=commit_sha,
            repo=repo,
            author=author_user,
            committer=committer_user,
            message=commit_info.get("message", ""),
            url=commit_data.get("html_url", ""),
            commit_date=commit_date,
            branch_name=branch_name,
            additions=additions,
            deletions=deletions,
        )

    except IntegrityError as e:
        if "duplicate key value violates unique constraint" in str(e) and "git_commit_sha_repo_id" in str(e):
            logger.debug(f"Commit {commit_sha} already exists - skipping")
            return None, new_users_count

        logger.error(
            f"Database integrity error creating commit record for {commit_sha}: {e}")
        commit_record = _create_minimal_commit_record(
            repo, commit_sha, commit_info, branch_name, logger)

    except Exception as e:
        logger.error(f"Error creating commit record for {commit_sha}: {e}")
        commit_record = _create_minimal_commit_record(
            repo, commit_sha, commit_info, branch_name, logger)

    if commit_record is None:
        return None, new_users_count

    _create_contributor_relationship(author_user, repo, logger)

    if committer_user and committer_user != author_user:
        _create_contributor_relationship(committer_user, repo, logger)

    return commit_record, new_users_count


def process_repository_commits(client, repo: Repo, logger, check_cancellation_func) -> Tuple[int, int]:
    repo_owner = repo.owner.username
    repo_name = repo.name
    default_branch = repo.default_branch

    logger.info(f"Processing commits for repository: {repo.full_name}")
    logger.info(f"Default branch: {default_branch}")

    existing_shas: Set[str] = set()
    all_commits: List[Dict] = []
    new_users_discovered = 0

    try:
        default_commits, _ = fetch_commits_from_branch(
            client,
            repo_owner,
            repo_name,
            default_branch,
            existing_shas,
            logger,
            check_cancellation_func,
        )
        all_commits.extend(default_commits)
        logger.info(f"Default branch: {len(default_commits)} commits")
    except Exception as e:
        logger.error(f"Error processing default branch: {e}")
        return 0, 0

    if check_cancellation_func():
        return len(all_commits), new_users_discovered

    branches = fetch_repository_branches(client, repo_owner, repo_name, logger)
    other_branches = [branch for branch in branches if branch.get(
        "name") != default_branch]

    for index, branch_data in enumerate(other_branches, start=1):
        if check_cancellation_func():
            logger.warning("Task cancelled during branch processing")
            break

        branch_name = branch_data.get("name")
        logger.info(f"Branch {index}/{len(other_branches)}: {branch_name}")

        branch_commits, should_continue = fetch_commits_from_branch(
            client,
            repo_owner,
            repo_name,
            branch_name,
            existing_shas,
            logger,
            check_cancellation_func,
        )
        all_commits.extend(branch_commits)

        if not should_continue:
            break

    logger.info(f"Total unique commits found: {len(all_commits)}")

    commits_created = 0

    for index, commit_data in enumerate(all_commits, start=1):
        if check_cancellation_func():
            logger.warning("Task cancelled during commit creation")
            break

        if index % 100 == 0:
            logger.info(
                f"Progress: {index}/{len(all_commits)} commits processed")

        try:
            commit_record, users_discovered = create_commit_record_with_users(
                client,
                repo,
                commit_data,
                logger,
            )
            if commit_record:
                commits_created += 1
                new_users_discovered += users_discovered

            time.sleep(0.02)

        except Exception as e:
            logger.error(
                f"Error creating commit record {commit_data.get('sha', 'unknown')}: {e}")
            raise Exception(
                f"Failed to process commit {commit_data.get('sha', 'unknown')}: {e}")

    logger.info(f"Created {commits_created} commit records")
    logger.info(f"Discovered {new_users_discovered} new users")
    return commits_created, new_users_discovered


def process_single_pull_request(client, repo: Repo, pr_data: Dict, logger) -> int:
    new_users_count = 0
    pr_number = pr_data.get("number")
    pr_author_data = pr_data.get("user")

    if pr_author_data and pr_author_data.get("login"):
        author_username = pr_author_data["login"]
        author_user, created = _get_contributor_user(
            client,
            author_username,
            DiscoveryMethod.CONTRIBUTOR,
            logger,
        )

        if created and author_user:
            new_users_count += 1

        _create_contributor_relationship(author_user, repo, logger)

    try:
        reviews = client.get_pull_request_reviews(
            repo.owner.username, repo.name, pr_number)

        for review_data in reviews or []:
            reviewer_data = review_data.get("user")
            if not reviewer_data or not reviewer_data.get("login"):
                continue

            reviewer_username = reviewer_data["login"]
            reviewer_user, created = _get_contributor_user(
                client,
                reviewer_username,
                DiscoveryMethod.CONTRIBUTOR,
                logger,
            )

            if created and reviewer_user:
                new_users_count += 1
                logger.info(f"Discovered PR reviewer: {reviewer_username}")

            _create_contributor_relationship(reviewer_user, repo, logger)

    except Exception as e:
        logger.warning(f"Could not fetch reviews for PR #{pr_number}: {e}")

    try:
        linked_commits = _link_pull_request_commits(
            client, repo, pr_number, logger)
        logger.info(f"Linked {linked_commits} commits to PR #{pr_number}")
    except Exception as e:
        logger.warning(f"Could not link commits for PR #{pr_number}: {e}")

    time.sleep(0.1)
    return new_users_count


def process_repository_pull_requests(client, repo: Repo, logger, check_cancellation_func) -> Tuple[int, int]:
    repo_owner = repo.owner.username
    repo_name = repo.name

    logger.info(f"Processing pull requests for repository: {repo.full_name}")

    all_prs: List[Dict] = []
    page = 1
    new_users_discovered = 0

    while True:
        if check_cancellation_func():
            logger.warning("Task cancelled during PR fetching")
            break

        try:
            prs = client.get_repo_pull_requests(
                repo_owner,
                repo_name,
                state="all",
                page=page,
                per_page=100,
            )
            if not prs:
                break

            all_prs.extend(prs)

            if len(prs) < 100:
                break

            page += 1
            time.sleep(0.1)

        except Exception as e:
            if "404" in str(e):
                logger.info("No pull requests accessible")
            else:
                logger.error(f"Error fetching pull requests page {page}: {e}")
            break

    logger.info(f"Found {len(all_prs)} pull requests to process")

    for index, pr_data in enumerate(all_prs, start=1):
        if check_cancellation_func():
            logger.warning("Task cancelled during PR processing")
            break

        if index % 25 == 0:
            logger.info(f"Progress: {index}/{len(all_prs)} PRs processed")

        try:
            users_discovered = process_single_pull_request(
                client, repo, pr_data, logger)
            new_users_discovered += users_discovered
            time.sleep(0.05)

        except Exception as e:
            logger.error(
                f"Error processing PR #{pr_data.get('number', 'unknown')}: {e}")

            pr_author_data = pr_data.get("user") if pr_data else None
            if pr_author_data and pr_author_data.get("login"):
                author_username = pr_author_data["login"]
                author_user, created = _get_contributor_user(
                    client,
                    author_username,
                    DiscoveryMethod.CONTRIBUTOR,
                    logger,
                )
                if created and author_user:
                    new_users_discovered += 1
                    logger.info(f"Salvaged PR author: {author_username}")

    logger.info(f"Processed {len(all_prs)} pull requests")
    logger.info(f"Discovered {new_users_discovered} new users from PRs")
    return len(all_prs), new_users_discovered
