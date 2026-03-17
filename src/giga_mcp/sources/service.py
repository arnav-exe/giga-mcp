from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from giga_mcp.discovery import load_discovery_result

from .store import (
    SourceDocumentRow,
    SourceUrlRow,
    create_source_set,
    get_source_urls,
    list_source_docs,
    list_source_sets,
    replace_source_documents,
    touch_source_set,
)


def register_source_url(llms_url: str, source_name: str | None = None) -> dict[str, object]:
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


def list_sources() -> dict[str, object]:
    sources = list_source_sets()

    return {
        "status": "ok",
        "tool": "list_sources",
        "sources": sources,
    }


def refresh_source(source_id: str, force: bool = False) -> dict[str, object]:
    refreshed = touch_source_set(source_id)

    if not refreshed:
        return {
            "status": "error",
            "tool": "refresh_source",
            "message": "source_id not found",
            "source_id": source_id,
            "force": force,
        }

    source_urls = get_source_urls(source_id)
    fetched_docs = _fetch_source_documents(source_urls)
    replace_source_documents(source_id=source_id, documents=fetched_docs)

    return {
        "status": "ok",
        "tool": "refresh_source",
        "source_id": source_id,
        "force": force,
        "refreshed": True,
        "fetched_docs": len(fetched_docs),
    }


def list_docs(source_id: str | None = None, framework: str | None = None,) -> dict[str, object]:
    docs = list_source_docs(source_id=source_id, framework=framework)

    return {
        "status": "ok",
        "tool": "list_docs",
        "source_id": source_id,
        "framework": framework,
        "docs": docs,
    }


def _fetch_source_documents(source_urls: list[SourceUrlRow],) -> list[SourceDocumentRow]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    documents: list[SourceDocumentRow] = []

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for source in source_urls:
            url = str(source["url"])
            try:
                response = client.get(url)
                content = response.text if response.status_code == 200 else None
                status_code = response.status_code

            except httpx.RequestError:
                content = None
                status_code = None

            documents.append(
                {
                    "url": url,
                    "fetched_at": fetched_at,
                    "status_code": status_code,
                    "content": content,
                }
            )

    return documents
