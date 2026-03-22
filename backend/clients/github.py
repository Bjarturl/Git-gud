import logging
import time
from typing import Dict, List, Optional

import requests

from apps.core.models import GitHubToken

logger = logging.getLogger(__name__)


class RepositoryAccessBlockedException(Exception):
    def __init__(self, message, block_reason=None):
        super().__init__(message)
        self.block_reason = block_reason


class GitHubAPIClient:
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeCollector-SecurityResearch/1.0",
        })
        self.token_model = GitHubToken
        self.current_token_index = 0
        self.github_logger = logging.getLogger("clients.github")

    def get_active_tokens(self) -> List["GitHubToken"]:
        return list(
            self.token_model.objects
            .filter(is_active=True)
            .only("id", "label", "token", "is_active")
            .order_by("id")
        )

    def get_active_token(self) -> Optional["GitHubToken"]:
        tokens = self.get_active_tokens()
        return tokens[0] if tokens else None

    def get_rate_limit_info(self, token_obj: "GitHubToken") -> Dict:
        headers = {
            "Authorization": f"token {token_obj.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeCollector-SecurityResearch/1.0",
        }

        try:
            response = requests.get(
                f"{self.base_url}/rate_limit", headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()

            logger.warning(
                f"Rate limit check failed for token {token_obj.label}: {response.status_code}")
            return {
                "error": f"API returned status {response.status_code}",
                "status_code": response.status_code,
            }
        except requests.exceptions.RequestException as exc:
            logger.error(
                f"Rate limit request failed for token {token_obj.label}: {exc}")
            return {"error": f"Request failed: {exc}"}

    def _request(self, url: str, method: str, params: Optional[Dict], headers: Dict) -> requests.Response:
        if method.upper() == "GET":
            return self.session.get(url, params=params, headers=headers, timeout=30)
        return self.session.request(method, url, json=params, headers=headers, timeout=30)

    def _parse_json(self, response: requests.Response) -> Dict:
        try:
            return response.json()
        except ValueError:
            return {}

    def _is_rate_limited(self, response: requests.Response, error_data: Dict) -> bool:
        message = error_data.get("message", "")
        if "rate limit" in message.lower():
            return True
        return "rate limit" in response.text.lower()

    def _raise_if_repo_blocked(self, response: requests.Response, error_data: Dict, url: str) -> None:
        if response.status_code not in (403, 451):
            return

        if error_data.get("message") != "Repository access blocked":
            return

        block_reason = (error_data.get("block") or {}).get("reason")
        if block_reason in {"unavailable", "sensitive_data", "dmca"}:
            self.github_logger.warning(
                f"Repository access blocked ({block_reason}): {url}")
            raise RepositoryAccessBlockedException(
                f"Repository access blocked ({block_reason}): {url}",
                block_reason=block_reason,
            )

    def _log_rate_limited(self, token_obj: "GitHubToken", response: requests.Response, remaining_tokens: int) -> None:
        self.github_logger.warning(f"Token '{token_obj.label}' RATE LIMITED")
        self.github_logger.warning(
            f"   Limit: {response.headers.get('X-RateLimit-Limit')}, "
            f"Used: {response.headers.get('X-RateLimit-Used')}"
        )
        if remaining_tokens > 0:
            self.github_logger.info(
                f"Rotating to next token ({remaining_tokens} tokens remaining)")

    def _wait_for_earliest_reset(self, active_tokens: List["GitHubToken"]) -> None:
        earliest_reset_time = float("inf")
        earliest_token = None

        for token in active_tokens:
            rate_info = self.get_rate_limit_info(token)
            reset_time = rate_info.get("rate", {}).get("reset")
            if reset_time is not None and reset_time < earliest_reset_time:
                earliest_reset_time = reset_time
                earliest_token = token

        if earliest_token is None or earliest_reset_time == float("inf"):
            raise Exception(
                "All GitHub tokens are rate limited and no reset time available")

        current_time = int(time.time())
        wait_time = max(1, int(earliest_reset_time) - current_time + 10)

        if wait_time > 3600:
            raise Exception(
                f"Rate limit wait time too long: {wait_time} seconds")

        self.github_logger.warning("ALL TOKENS RATE LIMITED")
        self.github_logger.warning(
            f"   Waiting {wait_time} seconds for token '{earliest_token.label}' to reset"
        )
        self.github_logger.warning(
            f"   Reset time: {time.strftime('%H:%M:%S', time.localtime(int(earliest_reset_time)))}"
        )

        self.current_token_index = active_tokens.index(earliest_token)
        time.sleep(wait_time)

    def make_request(self, endpoint: str, params: Dict = None, method: str = "GET") -> Dict:
        active_tokens = self.get_active_tokens()
        if not active_tokens:
            raise Exception("No active GitHub tokens available")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        tokens_tried = set()

        while len(tokens_tried) < len(active_tokens):
            token = active_tokens[self.current_token_index %
                                  len(active_tokens)]

            if token.id in tokens_tried:
                self.current_token_index += 1
                continue

            headers = {"Authorization": f"token {token.token}"}

            try:
                response = self._request(url, method, params, headers)
                error_data = self._parse_json(response)

                self._raise_if_repo_blocked(response, error_data, url)

                if response.status_code == 404:
                    self.github_logger.warning(
                        f"Resource not found (404): {url}")
                    response.raise_for_status()

                if response.status_code in (403, 451) and self._is_rate_limited(response, error_data):
                    tokens_tried.add(token.id)
                    self.current_token_index += 1
                    self._log_rate_limited(token, response, len(
                        active_tokens) - len(tokens_tried))
                    continue

                response.raise_for_status()
                return response.json()

            except RepositoryAccessBlockedException:
                raise

            except requests.exceptions.RequestException as exc:
                self.github_logger.error(f"REQUEST FAILED: {exc}")

                status_code = getattr(
                    getattr(exc, "response", None), "status_code", None)
                if status_code == 404:
                    self.github_logger.warning(
                        f"404 error - not retrying with other tokens: {exc}")
                    raise

                raise

        self._wait_for_earliest_reset(active_tokens)
        return self.make_request(endpoint, params, method)

    def search_users(self, query: str, per_page: int = 100, page: int = 1) -> Dict:
        params = {"q": query, "per_page": min(per_page, 100), "page": page}
        return self.make_request("/search/users", params)

    def get_user(self, username: str) -> Dict:
        return self.make_request(f"/users/{username}")

    def get_user_followers(self, username: str, per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"per_page": min(per_page, 100), "page": page}
        result = self.make_request(f"/users/{username}/followers", params)
        return result if isinstance(result, list) else []

    def get_user_following(self, username: str, per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"per_page": min(per_page, 100), "page": page}
        result = self.make_request(f"/users/{username}/following", params)
        return result if isinstance(result, list) else []

    def get_user_repos(self, username: str, per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"per_page": min(per_page, 100), "page": page, "type": "all"}
        result = self.make_request(f"/users/{username}/repos", params)
        return result if isinstance(result, list) else []

    def get_user_gists(self, username: str, per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"per_page": min(per_page, 100), "page": page}
        result = self.make_request(f"/users/{username}/gists", params)
        return result if isinstance(result, list) else []

    def get_gist_details(self, gist_id: str) -> Dict:
        return self.make_request(f"/gists/{gist_id}")

    def get_gist_revision_details(self, gist_id: str, revision_id: str) -> Dict:
        return self.make_request(f"/gists/{gist_id}/{revision_id}")

    def get_user_info(self, username: str) -> Dict:
        return self.make_request(f"/users/{username}")

    def get_org_members(self, org_name: str, per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"per_page": min(per_page, 100), "page": page}
        result = self.make_request(f"/orgs/{org_name}/members", params)
        return result if isinstance(result, list) else []

    def get_repo_info(self, owner: str, repo_name: str) -> Dict:
        return self.make_request(f"/repos/{owner}/{repo_name}")

    def get_repo_languages(self, owner: str, repo_name: str) -> Dict:
        return self.make_request(f"/repos/{owner}/{repo_name}/languages")

    def get_repo_branches(self, owner: str, repo_name: str, per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"per_page": min(per_page, 100), "page": page}
        result = self.make_request(
            f"/repos/{owner}/{repo_name}/branches", params)
        return result if isinstance(result, list) else []

    def get_repo_commits(self, owner: str, repo_name: str, sha: str = None, per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"per_page": min(per_page, 100), "page": page}
        if sha:
            params["sha"] = sha
        result = self.make_request(
            f"/repos/{owner}/{repo_name}/commits", params)
        return result if isinstance(result, list) else []

    def get_commit_details(self, owner: str, repo_name: str, sha: str) -> Dict:
        result = self.make_request(f"/repos/{owner}/{repo_name}/commits/{sha}")
        return result if isinstance(result, dict) else {}

    def get_repo_pull_requests(self, owner: str, repo_name: str, state: str = "open", per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"state": state, "per_page": min(per_page, 100), "page": page}
        result = self.make_request(f"/repos/{owner}/{repo_name}/pulls", params)
        return result if isinstance(result, list) else []

    def get_pull_request_reviews(self, owner: str, repo_name: str, pull_number: int) -> List[Dict]:
        result = self.make_request(
            f"/repos/{owner}/{repo_name}/pulls/{pull_number}/reviews")
        return result if isinstance(result, list) else []

    def get_pull_request_commits(self, owner: str, repo_name: str, pull_number: int, per_page: int = 100, page: int = 1) -> List[Dict]:
        params = {"per_page": min(per_page, 100), "page": page}
        result = self.make_request(
            f"/repos/{owner}/{repo_name}/pulls/{pull_number}/commits", params
        )
        return result if isinstance(result, list) else []
