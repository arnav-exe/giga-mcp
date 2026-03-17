from urllib.parse import urlparse

import httpx


def fetch_npm_authority(name, timeout=10.0):
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
