from datetime import datetime, timezone
from uuid import uuid4
from pprint import pprint

from giga_mcp.models import (
    AcceptedSource,
    AuthorityEvidence,
    DiscoveryResult,
    ProbeResult,
    RejectedCandidate,
)

from .allowlist import build_allowlist_hosts
from .authority import fetch_npm_authority, fetch_pypi_authority
from .github import fetch_github_repository_metadata
from .probe import probe_llms_sources


# name: package/framework name
# ecosystem: "pypi" or "npm"
# timeout (seconds)
def discover_official_sources(name: str, ecosystem: str, timeout: float = 10.0) -> DiscoveryResult:
    authority = _authority_for(ecosystem, name, timeout)
    repository = authority.get("repository")

    repository_metadata = (
        fetch_github_repository_metadata(repository, timeout=timeout)
        if repository
        else None
    )

    allowlist_hosts = build_allowlist_hosts(authority, repository_metadata)
    probed = probe_llms_sources(_probe_hosts(allowlist_hosts), timeout=timeout)
    accepted_sources = [
        AcceptedSource(
            url=url,
            host=url.split("/")[2],
            tier=tier,
            reason="strict probe success on allowlisted host",
            confidence=0.95 if tier == 1 else 0.85,
        )
        for url in probed["accepted_sources"]
        for tier in [_tier_for(url)]
    ]

    rejected_candidates = [
        RejectedCandidate(
            url=probe["url"],
            reason=_probe_rejection_reason(probe),
        )
        for probe in probed["probes"]
        if probe["status_code"] != 200
    ]

    probes = [ProbeResult(**probe) for probe in probed["probes"]]

    return DiscoveryResult(
        discovery_id=str(uuid4()),
        name=name,
        ecosystem=ecosystem,
        accepted_sources=accepted_sources,
        rejected_candidates=rejected_candidates,
        authority_evidence=AuthorityEvidence(
            registry_fields=authority.get("registry_fields", {}),
            repository_fields=(repository_metadata or {}),
            allowlist_hosts=allowlist_hosts,
        ),
        probes=probes,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )


def _authority_for(ecosystem: str, name: str, timeout: float) -> dict:
    if ecosystem == "npm":
        return fetch_npm_authority(name, timeout=timeout)
    if ecosystem == "pypi":
        return fetch_pypi_authority(name, timeout=timeout)
    raise ValueError("ecosystem must be 'npm' or 'pypi'")


def _tier_for(url: str) -> int:
    if url.endswith("/llms.txt") and "/docs/" not in url and "/latest/" not in url:
        return 1
    return 2


def _probe_rejection_reason(probe: dict[str, object]) -> str:
    if probe["error"]:
        return f"probe error: {probe['error']}"
    status_code = probe["status_code"]
    if status_code is None:
        return "probe failed with unknown error"
    return f"probe status {status_code}"


def _probe_hosts(allowlist_hosts: list[str]) -> list[str]:
    blocked_hosts = {"github.com", "gitlab.com", "bitbucket.org"}
    return [host for host in allowlist_hosts if host not in blocked_hosts]



if __name__ == "__main__":
    pprint(discover_official_sources("metaflow", "pypi"))
    # pprint(discover_official_sources("jwt-decode", "npm"))
    #
    # print()
    #
    # pprint(discover_official_sources("asdf", "npm"))
