from urllib.parse import urlparse


def build_allowlist_hosts(authority: dict[str, object], repository_metadata: object = None) -> list[str]:
    hosts: set[str] = set()
    _collect_hosts(hosts, authority.get("registry_fields", {}))
    if repository_metadata:
        _collect_hosts(hosts, repository_metadata)
    return sorted(hosts)


def is_allowed_source_url(url: str, allowlist_hosts: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    return any(
        host == allowed or host.endswith(f".{allowed}") for allowed in allowlist_hosts
    )


def _collect_hosts(hosts: set[str], fields: object) -> None:
    if not isinstance(fields, dict):
        return
    for value in fields.values():
        if isinstance(value, str):
            _add_host(hosts, value)
            continue
        if not isinstance(value, dict):
            continue
        for nested_value in value.values():
            if isinstance(nested_value, str):
                _add_host(hosts, nested_value)


def _add_host(hosts: set[str], url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return
    hosts.add(parsed.netloc.lower())
