from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from urllib.parse import urljoin, urlparse
import re
from time import sleep
import httpx

from instant_context.logging import log_event


PROBE_PATHS = ("/llms.txt", "/docs/llms.txt", "/latest/llms.txt")
MAX_PROBE_WORKERS = 8
LLMS_LINK_PATTERN = re.compile(
    r"https?://[^\s)\]>\"']+llms[^\s)\]>\"']*\.txt|(?:\./|/)?[^\s)\]>\"']*llms[^\s)\]>\"']*\.txt",
    re.IGNORECASE,
)


def probe_llms_sources(hosts: list[str], timeout: float = 10.0) -> dict[str, list[dict[str, object]] | list[str]]:
    tasks = [f"https://{host}{path}" for host in hosts for path in PROBE_PATHS]
    probes: list[dict[str, object]] = []
    accepted_sources: list[str] = []
    linked_sources: list[str] = []

    with ThreadPoolExecutor(
        max_workers=min(MAX_PROBE_WORKERS, max(1, len(tasks)))
    ) as executor:
        futures = [executor.submit(_probe_one_url, url, timeout) for url in tasks]

        for future in as_completed(futures):
            row = future.result()
            url = str(row["url"])
            content = str(row["content"])
            probes.append(
                {
                    "url": url,
                    "status_code": row["status_code"],
                    "latency_ms": row["latency_ms"],
                    "error": row["error"],
                }
            )
            if row["status_code"] == 200:
                accepted_sources.append(url)
                linked_sources.extend(_extract_llms_links(content, url))
            log_event(
                "probe_result",
                url=url,
                status_code=row["status_code"],
                latency_ms=row["latency_ms"],
                error=row["error"],
            )
    probes.sort(key=lambda item: str(item["url"]))

    log_event(
        "probe_complete",
        hosts=len(hosts),
        probes=len(probes),
        accepted_sources=len(set(accepted_sources)),
        linked_sources=len(set(linked_sources)),
    )

    return {
        "probes": probes,
        "accepted_sources": sorted(set(accepted_sources)),
        "linked_sources": sorted(set(linked_sources)),
    }


def _extract_llms_links(text: str, base_url: str) -> list[str]:
    matches = LLMS_LINK_PATTERN.findall(text or "")
    resolved = []

    for candidate in matches:
        url = urljoin(base_url, candidate.strip())
        parsed = urlparse(url)

        if parsed.scheme.lower() != "https" or not parsed.netloc:
            continue
        if (not parsed.path.lower().endswith(".txt") or "llms" not in parsed.path.lower()):
            continue

        resolved.append(url)

    return resolved


def _probe_one_url(url: str, timeout: float) -> dict[str, object]:
    started = perf_counter()
    status_code, content, error = _fetch_with_retry(url, timeout)

    return {
        "url": url,
        "status_code": status_code,
        "latency_ms": int((perf_counter() - started) * 1000),
        "error": error,
        "content": content,
    }


def _fetch_with_retry(url: str, timeout: float, retries: int = 2) -> tuple[int | None, str, str | None]:
    delay = 0.2
    for attempt in range(retries + 1):
        try:
            response = httpx.get(url, timeout=timeout, follow_redirects=True)
            return (
                response.status_code,
                response.text if response.status_code == 200 else "",
                None,
            )

        except httpx.RequestError as error:
            if attempt == retries:
                return None, "", str(error)
            sleep(delay)
            delay *= 2
    return None, "", "unknown error"
