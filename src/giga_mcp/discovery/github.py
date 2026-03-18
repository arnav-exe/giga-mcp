import httpx
from time import sleep


def fetch_github_repository_metadata(repository: str, timeout: float = 10.0) -> dict[str, str | None]:
    payload = _get_json_retry(f"https://api.github.com/repos/{repository}", timeout)
    return {
        "repository": repository,
        "homepage": payload.get("homepage"),
        "html_url": payload.get("html_url"),
        "default_branch": payload.get("default_branch"),
    }


def _get_json_retry(url: str, timeout: float, retries: int = 2) -> dict[str, str | None]:
    delay = 0.2
    for attempt in range(retries + 1):
        try:
            response = httpx.get(url, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return {
                    "homepage": payload.get("homepage"),
                    "html_url": payload.get("html_url"),
                    "default_branch": payload.get("default_branch"),
                }
            return {}
        except httpx.HTTPError:
            if attempt == retries:
                raise
            sleep(delay)
            delay *= 2
    return {}
