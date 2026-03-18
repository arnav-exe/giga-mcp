from datetime import datetime, timezone
from typing import cast
from urllib.parse import urlparse
import httpx

from giga_mcp.discovery import load_discovery_result

from .store import (
    SourceDocumentRow,
    SourceUrlRow,
    create_source_set,
    get_cached_document,
    get_source_urls,
    list_cached_documents,
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


def list_docs(source_id: str | None = None, framework: str | None = None) -> dict[str, object]:
    docs = list_source_docs(source_id=source_id, framework=framework)

    return {
        "status": "ok",
        "tool": "list_docs",
        "source_id": source_id,
        "framework": framework,
        "docs": docs,
    }


def search_docs(query: str, source_id: str | None = None, framework: str | None = None, section: str | None = None, top_k: int = 8) -> dict[str, object]:
    tokens = _tokens(query)

    if not tokens:
        return {
            "status": "ok",
            "tool": "search_docs",
            "query": query,
            "source_id": source_id,
            "framework": framework,
            "section": section,
            "top_k": top_k,
            "results": [],
            "stale": False,
        }

    documents = list_cached_documents(source_id=source_id, framework=framework)

    results = [
        result
        for document in documents
        for result in _search_document(
            document=document, tokens=tokens, section=section
        )
    ]
    results.sort(key=_search_sort_key)

    limited = results[: max(1, top_k)]
    indexed_at = max(
        (str(document["fetched_at"]) for document in documents), default=""
    )

    return {
        "status": "ok",
        "tool": "search_docs",
        "query": query,
        "source_id": source_id,
        "framework": framework,
        "section": section,
        "top_k": top_k,
        "results": limited,
        "indexed_at": indexed_at,
        "stale": False,
    }


def get_doc(source_id: str, path_or_slug: str) -> dict[str, object]:
    document = get_cached_document(source_id=source_id, path_or_slug=path_or_slug)
    if not document:
        return {
            "status": "error",
            "tool": "get_doc",
            "message": "document not found in cached source set",
            "source_id": source_id,
            "path_or_slug": path_or_slug,
        }

    content = document.get("content")
    if not isinstance(content, str):
        content = ""

    title = _title([line.strip() for line in content.splitlines() if line.strip()])
    return {
        "status": "ok",
        "tool": "get_doc",
        "source_id": source_id,
        "path_or_slug": path_or_slug,
        "content": content,
        "citations": [
            {
                "source_url": str(document["url"]),
                "title": title,
                "section": "general",
                "chunk_id": f"{source_id}:0",
            }
        ],
        "index_metadata": {
            "source_id": source_id,
            "indexed_at": str(document.get("fetched_at") or ""),
            "stale": False,
        },
    }


def _fetch_source_documents(source_urls: list[SourceUrlRow]) -> list[SourceDocumentRow]:
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


def _search_document(document: dict[str, object], tokens: list[str], section: str | None) -> list[dict[str, object]]:
    content = document.get("content")
    status_code = document.get("status_code")

    if status_code != 200 or not isinstance(content, str) or not content.strip():
        return []

    lowered_section = section.lower() if section else None
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    title = _title(lines)
    matches: list[dict[str, object]] = []

    for index, line in enumerate(lines):
        line_lower = line.lower()
        score = sum(line_lower.count(token) for token in tokens)

        if score == 0:
            continue
        section_name = _nearest_heading(lines, index)

        if lowered_section and lowered_section not in section_name.lower():
            continue

        matches.append(
            {
                "snippet": line[:400],
                "source_url": str(document["url"]),
                "title": title,
                "section": section_name,
                "chunk_id": f"{document['source_id']}:{index}",
                "score": float(score),
            }
        )

    return matches


def _tokens(query: str) -> list[str]:
    return [part for part in query.lower().split() if part]


def _title(lines: list[str]) -> str:
    for line in lines:
        if line.startswith("#"):
            return line.lstrip("# ") or "untitled"

    return lines[0][:120] if lines else "untitled"


def _nearest_heading(lines: list[str], index: int) -> str:
    for pointer in range(index, -1, -1):
        candidate = lines[pointer]

        if candidate.startswith("#"):
            return candidate.lstrip("# ") or "general"

    return "general"


def _search_sort_key(item: dict[str, object]) -> tuple[float, str, str]:
    return (
        -float(str(item["score"])),
        cast(str, item["source_url"]),
        cast(str, item["chunk_id"]),
    )
