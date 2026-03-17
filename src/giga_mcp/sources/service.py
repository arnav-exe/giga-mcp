from urllib.parse import urlparse

from giga_mcp.discovery import load_discovery_result

from .store import create_source_set


def register_source_url(
    llms_url: str, source_name: str | None = None
) -> dict[str, object]:
    parsed = urlparse(llms_url)
    if parsed.scheme.lower() != "https":
        return {
            "status": "error",
            "tool": "register_source",
            "message": "only https llms urls are allowed",
            "llms_url": llms_url,
        }
    if not parsed.netloc:
        return {
            "status": "error",
            "tool": "register_source",
            "message": "url must include host",
            "llms_url": llms_url,
        }
    if not parsed.path.endswith(".txt") or "llms" not in parsed.path.lower():
        return {
            "status": "error",
            "tool": "register_source",
            "message": "url must point to llms*.txt source",
            "llms_url": llms_url,
        }
    tier = 1 if parsed.path.lower() in {"/llms.txt", "/llms-full.txt"} else 2

    source_id = create_source_set(
        source_name=source_name,
        urls=[{"url": llms_url, "host": parsed.netloc.lower(), "tier": tier}],
    )

    return {
        "status": "ok",
        "tool": "register_source",
        "source_id": source_id,
        "source_name": source_name,
        "accepted_sources": [
            {
                "url": llms_url,
                "host": parsed.netloc.lower(),
                "tier": tier,
            }
        ],
    }


def register_discovered_sources(discovery_id: str) -> dict[str, object]:
    discovery = load_discovery_result(discovery_id)
    if not discovery:
        return {
            "status": "error",
            "tool": "register_discovered_sources",
            "message": "discovery_id not found",
            "discovery_id": discovery_id,
            "source_ids": [],
        }
    if not discovery.accepted_sources:
        return {
            "status": "ok",
            "tool": "register_discovered_sources",
            "message": "no accepted sources to register",
            "discovery_id": discovery_id,
            "source_ids": [],
        }
    source_id = create_source_set(
        source_name=discovery.name,
        urls=[
            {"url": source.url, "host": source.host, "tier": source.tier}
            for source in discovery.accepted_sources
        ],
    )
    return {
        "status": "ok",
        "tool": "register_discovered_sources",
        "discovery_id": discovery_id,
        "source_ids": [source_id],
    }
