from urllib.parse import urlparse


def build_allowlist_hosts(authority, repository_metadata=None):
    hosts = set()
    _collect_hosts(hosts, authority.get("registry_fields", {}))
    if repository_metadata:
        _collect_hosts(hosts, repository_metadata)
    return sorted(hosts)


def is_allowed_source_url(url, allowlist_hosts):
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        return False
    host = parsed.netloc.lower()
    return any(
        host == allowed or host.endswith(f".{allowed}") for allowed in allowlist_hosts
    )


def _collect_hosts(hosts, fields):
    for value in fields.values():
        if isinstance(value, str):
            _add_host(hosts, value)
            continue
        if not isinstance(value, dict):
            continue
        for nested_value in value.values():
            if isinstance(nested_value, str):
                _add_host(hosts, nested_value)


def _add_host(hosts, url):
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return
    hosts.add(parsed.netloc.lower())
