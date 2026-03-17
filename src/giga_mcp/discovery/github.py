import httpx


def fetch_github_repository_metadata(repository: str, timeout: float = 10.0):
    response = httpx.get(f"https://api.github.com/repos/{repository}", timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return {
        "repository": repository,
        "homepage": payload.get("homepage"),
        "html_url": payload.get("html_url"),
        "default_branch": payload.get("default_branch"),
    }
