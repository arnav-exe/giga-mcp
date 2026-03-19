from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from giga_mcp.logging import log_event
from giga_mcp.models import AcceptedSource, AuthorityEvidence, DiscoveryResult, ProbeResult, RejectedCandidate

from .allowlist import build_allowlist_hosts, is_allowed_source_url
from .authority import fetch_npm_authority, fetch_pypi_authority
from .github import fetch_github_repository_metadata
from .probe import probe_llms_sources


def discover_official_sources(name: str, ecosystem: str, timeout: float = 10.0) -> DiscoveryResult:
    log_event("discovery_start", name=name, ecosystem=ecosystem)
    authority = _authority_for(ecosystem, name, timeout)
    repository = (
        authority.get("repository")
        if isinstance(authority.get("repository"), str)
        else None
    )
    repository_metadata = (
        fetch_github_repository_metadata(repository, timeout=timeout)
        if isinstance(repository, str) and repository
        else None
    )

    allowlist_hosts = build_allowlist_hosts(authority, repository_metadata)
    probed = probe_llms_sources(_probe_hosts(allowlist_hosts), timeout=timeout)
    accepted_probe_urls = [
        url for url in probed.get("accepted_sources", []) if isinstance(url, str)
    ]
    linked_probe_urls = [
        url for url in probed.get("linked_sources", []) if isinstance(url, str)
    ]
    discovered_links = [
        url for url in linked_probe_urls if is_allowed_source_url(url, allowlist_hosts)
    ]
    accepted_urls = sorted(set(accepted_probe_urls) | set(discovered_links))
    accepted_sources = [
        AcceptedSource(
            url=url,
            host=url.split("/")[2],
            tier=tier,
            reason="linked official llms source"
            if url in discovered_links
            else "strict probe success on allowlisted host",
            confidence=_confidence_for(tier=tier, linked=(url in discovered_links)),
        )
        for url in accepted_urls
        for tier in [_tier_for(url)]
    ]
    registry_fields = authority.get("registry_fields")
    registry_fields = registry_fields if isinstance(registry_fields, dict) else {}
    probes, rejected_candidates = _normalize_probes_and_rejections(
        probed.get("probes", []), linked_probe_urls, allowlist_hosts
    )

    result = DiscoveryResult(
        discovery_id=str(uuid4()),
        name=name,
        ecosystem=ecosystem,
        accepted_sources=accepted_sources,
        rejected_candidates=rejected_candidates,
        authority_evidence=AuthorityEvidence(
            registry_fields=cast(dict[str, object], registry_fields),
            repository_fields=(repository_metadata or {}),
            allowlist_hosts=allowlist_hosts,
        ),
        probes=probes,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    log_event(
        "discovery_end",
        name=name,
        ecosystem=ecosystem,
        accepted_sources=len(result.accepted_sources),
        rejected_candidates=len(result.rejected_candidates),
        probes=len(result.probes),
    )
    return result


def _authority_for(ecosystem: str, name: str, timeout: float) -> dict[str, object]:
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


def _confidence_for(tier: int, linked: bool) -> float:
    base, tier_penalty, linked_penalty = 1.0, 0.1, 0.05
    return round(
        max(
            0.0,
            base - ((tier - 1) * tier_penalty) - (linked_penalty if linked else 0.0),
        ),
        2,
    )


def _normalize_probes_and_rejections(raw_probes: object, linked_probe_urls: list[str], allowlist_hosts: list[str]) -> tuple[list[ProbeResult], list[RejectedCandidate]]:
    probes: list[ProbeResult] = []
    rejections: list[RejectedCandidate] = []

    if isinstance(raw_probes, list):
        for row in raw_probes:
            if not isinstance(row, dict):
                continue
            raw_url = row.get("url")
            raw_status = row.get("status_code")
            raw_latency = row.get("latency_ms")
            raw_error = row.get("error")
            url = raw_url if isinstance(raw_url, str) else ""
            status_code = raw_status if isinstance(raw_status, int) else None
            latency_ms = raw_latency if isinstance(raw_latency, int) else None
            error = raw_error if isinstance(raw_error, str) else None
            probes.append(
                ProbeResult(
                    url=cast(str, url),
                    status_code=status_code,
                    latency_ms=latency_ms,
                    error=error,
                )
            )

            if status_code != 200:
                rejections.append(
                    RejectedCandidate(
                        url=cast(str, url),
                        reason=_probe_rejection_reason(
                            {"status_code": status_code, "error": error}
                        ),
                    )
                )

    rejections.extend(
        RejectedCandidate(
            url=url, reason="linked llms source host not in strict allowlist"
        )
        for url in linked_probe_urls
        if not is_allowed_source_url(url, allowlist_hosts)
    )
    return probes, rejections
