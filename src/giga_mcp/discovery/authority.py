from urllib.parse import urlparse
from pprint import pprint
import httpx


# (timeout in seconds)
def fetch_npm_authority(name: str, timeout: float = 10.0):
    response = httpx.get(f"https://registry.npmjs.org/{name}/latest", timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    repository_url = _repository_url(payload.get("repository"))
    return {
        "ecosystem": "npm",
        "name": name,
        "registry_fields": {
            "homepage": _normalize_url(payload.get("homepage")),
            "repository": repository_url,
            "bugs": _bugs_url(payload.get("bugs")),
        },
        "repository": _github_repo(repository_url),
    }


# (timeout in seconds)
def fetch_pypi_authority(name: str, timeout: float = 10.0):
    response = httpx.get(f"https://pypi.org/pypi/{name}/json", timeout=timeout)
    response.raise_for_status()
    info = response.json().get("info", {})
    repository_url = _pypi_repository_url(
        info.get("project_urls"), info.get("home_page")
    )
    return {
        "ecosystem": "pypi",
        "name": name,
        "registry_fields": {
            "home_page": _normalize_url(info.get("home_page")),
            "project_urls": _normalize_project_urls(info.get("project_urls")),
        },
        "repository": _github_repo(repository_url),
    }


def _repository_url(repository):
    if isinstance(repository, str):
        return _normalize_url(repository)
    if not isinstance(repository, dict):
        return None
    return _normalize_url(repository.get("url"))


def _bugs_url(bugs):
    if isinstance(bugs, str):
        return _normalize_url(bugs)
    if not isinstance(bugs, dict):
        return None
    return _normalize_url(bugs.get("url"))


def _normalize_url(raw):
    if not raw:
        return None
    value = raw.strip()
    if value.startswith("git+"):
        value = value[4:]
    if value.endswith(".git"):
        value = value[:-4]
    return value


def _normalize_project_urls(project_urls):
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


def _pypi_repository_url(project_urls, home_page):
    urls = _normalize_project_urls(project_urls)
    for key in urls:
        if "repo" in key.lower() or "source" in key.lower() or "code" in key.lower():
            return urls[key]
    for value in urls.values():
        if "github.com" in value.lower():
            return value
    return _normalize_url(home_page)


def _github_repo(repository_url):
    if not repository_url:
        return None
    parsed = urlparse(repository_url)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"



if __name__ == "__main__":
    pprint(fetch_npm_authority("jwt-decode"))

    print()

    pprint(fetch_pypi_authority("metaflow"))
