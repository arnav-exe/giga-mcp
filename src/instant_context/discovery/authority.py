from urllib.parse import urlparse
from time import sleep
import httpx

from instant_context.logging import log_event


def fetch_npm_authority(name: str, timeout: float = 10.0) -> dict[str, object]:
    payload = _get_json_retry(f"https://registry.npmjs.org/{name}/latest", timeout)
    repository_url = _repository_url(payload.get("repository"))
    result = {
        "ecosystem": "npm",
        "name": name,
        "registry_fields": {
            "homepage": _normalize_url(payload.get("homepage")),
            "repository": repository_url,
            "bugs": _bugs_url(payload.get("bugs")),
        },
        "repository": _github_repo(repository_url),
    }
    log_event(
        "authority_resolved",
        ecosystem="npm",
        name=name,
        has_repository=bool(result["repository"]),
    )
    return result


def fetch_pypi_authority(name: str, timeout: float = 10.0) -> dict[str, object]:
    info = _get_json_retry(f"https://pypi.org/pypi/{name}/json", timeout).get(
        "info", {}
    )
    repository_url = _pypi_repository_url(
        info.get("project_urls"), info.get("home_page")
    )
    result = {
        "ecosystem": "pypi",
        "name": name,
        "registry_fields": {
            "home_page": _normalize_url(info.get("home_page")),
            "project_urls": _normalize_project_urls(info.get("project_urls")),
        },
        "repository": _github_repo(repository_url),
    }
    log_event(
        "authority_resolved",
        ecosystem="pypi",
        name=name,
        has_repository=bool(result["repository"]),
    )
    return result


def _repository_url(repository: object) -> str | None:
    if isinstance(repository, str):
        return _normalize_url(repository)
    if not isinstance(repository, dict):
        return None
    return _normalize_url(repository.get("url"))


def _bugs_url(bugs: object) -> str | None:
    if isinstance(bugs, str):
        return _normalize_url(bugs)
    if not isinstance(bugs, dict):
        return None
    return _normalize_url(bugs.get("url"))


def _normalize_url(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = raw.strip()
    if value.startswith("git+"):
        value = value[4:]
    if value.endswith(".git"):
        value = value[:-4]
    return value


def _normalize_project_urls(project_urls: object) -> dict[str, str]:
    if not isinstance(project_urls, dict):
        return {}
    normalized = {}
    for key, value in project_urls.items():
        if not key:
            continue
        url = _normalize_url(value)
        if url:
            normalized[key] = url
    return normalized


def _pypi_repository_url(project_urls: object, home_page: object) -> str | None:
    urls = _normalize_project_urls(project_urls)
    for key in urls:
        if "repo" in key.lower() or "source" in key.lower() or "code" in key.lower():
            return urls[key]
    for value in urls.values():
        if "github.com" in value.lower():
            return value
    return _normalize_url(home_page)


def _github_repo(repository_url: str | None) -> str | None:
    if not repository_url:
        return None
    parsed = urlparse(repository_url)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def _get_json_retry(url: str, timeout: float, retries: int = 2) -> dict[str, object]:
    delay = 0.2
    for attempt in range(retries + 1):
        try:
            response = httpx.get(url, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except httpx.HTTPError:
            if attempt == retries:
                raise
            sleep(delay)
            delay *= 2
    return {}
