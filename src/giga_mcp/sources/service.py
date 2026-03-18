from datetime import datetime, timedelta, timezone
from time import sleep
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
    latest_cache_snapshot,
    list_cached_documents,
    list_source_docs,
    list_source_sets,
    save_cache_snapshot,
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

    snapshot = latest_cache_snapshot(source_id=source_id)
    if snapshot and not force and not _snapshot_is_stale(snapshot):
        return {
            "status": "ok",
            "tool": "refresh_source",
            "source_id": source_id,
            "force": force,
            "refreshed": False,
            "fetched_docs": 0,
            "skipped": True,
            "indexed_at": str(snapshot.get("indexed_at", "")),
        }

    source_urls = get_source_urls(source_id)
    fetched_docs = _fetch_source_documents(source_urls)
    indexed_at = datetime.now(timezone.utc).isoformat()
    successful_fetches = [
        document
        for document in fetched_docs
        if document["status_code"] == 200 and document["content"]
    ]

    if not successful_fetches:
        expires_at = indexed_at
        save_cache_snapshot(
            source_id=source_id,
            indexed_at=indexed_at,
            expires_at=expires_at,
            stale=True,
        )
        cached_docs = list_cached_documents(source_id=source_id)
        return {
            "status": "ok",
            "tool": "refresh_source",
            "source_id": source_id,
            "force": force,
            "refreshed": False,
            "fetched_docs": 0,
            "skipped": False,
            "indexed_at": indexed_at,
            "stale_fallback": True,
            "cached_docs": len(cached_docs),
        }

    replace_source_documents(source_id=source_id, documents=fetched_docs)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    save_cache_snapshot(
        source_id=source_id, indexed_at=indexed_at, expires_at=expires_at, stale=False
    )

    return {
        "status": "ok",
        "tool": "refresh_source",
        "source_id": source_id,
        "force": force,
        "refreshed": True,
        "fetched_docs": len(fetched_docs),
        "skipped": False,
        "indexed_at": indexed_at,
        "stale_fallback": False,
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


def search_docs(query: str, source_id: str | None = None, framework: str | None = None, section: str | None = None, top_k: int = 8, ) -> dict[str, object]:
    tokens = _expanded_tokens(query)

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
    indexed_at, stale = _search_index_metadata(source_id=source_id, documents=documents)

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
        "stale": stale,
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
    indexed_at, stale = _snapshot_metadata(source_id)
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
            "indexed_at": indexed_at,
            "stale": stale,
        },
    }


def get_excerpt(query: str, source_id: str | None = None, top_k: int = 5, max_chars: int = 4000) -> dict[str, object]:
    searched = search_docs(
        query=query,
        source_id=source_id,
        framework=None,
        section=None,
        top_k=top_k,
    )
    results = searched.get("results")
    if not isinstance(results, list):
        results = []
    snippets = [
        str(result.get("snippet", "")) for result in results if isinstance(result, dict)
    ]
    content = "\n\n".join(snippets)
    if len(content) > max_chars:
        content = content[:max_chars]
    citations = [
        {
            "source_url": str(result.get("source_url", "")),
            "title": str(result.get("title", "untitled")),
            "section": str(result.get("section", "general")),
            "chunk_id": str(result.get("chunk_id", "")),
        }
        for result in results
        if isinstance(result, dict)
    ]
    return {
        "status": "ok",
        "tool": "get_excerpt",
        "query": query,
        "source_id": source_id,
        "top_k": top_k,
        "max_chars": max_chars,
        "content": content,
        "citations": citations,
        "index_metadata": {
            "source_id": source_id or "",
            "indexed_at": str(searched.get("indexed_at", "")),
            "stale": bool(searched.get("stale", False)),
        },
    }


def _fetch_source_documents(source_urls: list[SourceUrlRow]) -> list[SourceDocumentRow]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    documents: list[SourceDocumentRow] = []

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for source in source_urls:
            url = str(source["url"])
            status_code, content = _fetch_with_retry(client=client, url=url)

            documents.append(
                {
                    "url": url,
                    "fetched_at": fetched_at,
                    "status_code": status_code,
                    "content": content,
                }
            )

    return documents


def _fetch_with_retry(client: httpx.Client, url: str, retries: int = 2) -> tuple[int | None, str | None]:
    delay = 0.25
    for attempt in range(retries + 1):
        try:
            response = client.get(url)
            return (
                response.status_code,
                response.text if response.status_code == 200 else None,
            )
        except httpx.RequestError:
            if attempt == retries:
                return None, None
            sleep(delay)
            delay *= 2
    return None, None


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


def _expanded_tokens(query: str) -> list[str]:
    base = _tokens(query)
    aliases = {
        "js": ["javascript"],
        "ts": ["typescript"],
        "py": ["python"],
        "llm": ["llms", "language", "model"],
    }
    expanded = [token for token in base]
    for token in base:
        expanded.extend(aliases.get(token, []))
    # keep deterministic order but remove dupes
    return list(dict.fromkeys(expanded))


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


def _snapshot_metadata(source_id: str) -> tuple[str, bool]:
    snapshot = latest_cache_snapshot(source_id=source_id)
    if not snapshot:
        return "", False
    return str(snapshot.get("indexed_at", "")), _snapshot_is_stale(snapshot)


def _search_index_metadata(source_id: str | None, documents: list[dict[str, object]]) -> tuple[str, bool]:
    if source_id:
        return _snapshot_metadata(source_id)
    source_ids = list(
        dict.fromkeys(
            str(document["source_id"])
            for document in documents
            if document.get("source_id")
        )
    )
    if not source_ids:
        return "", False
    indexed_values = []
    stale_values = []
    for sid in source_ids:
        indexed_at, stale = _snapshot_metadata(sid)
        indexed_values.append(indexed_at)
        stale_values.append(stale)
    return max(indexed_values, default=""), any(stale_values)


def _snapshot_is_stale(snapshot: dict[str, object]) -> bool:
    if snapshot.get("stale", 0) in (1, "1", True):
        return True
    expires_at = str(snapshot.get("expires_at", ""))
    if not expires_at:
        return False
    return expires_at < datetime.now(timezone.utc).isoformat()
