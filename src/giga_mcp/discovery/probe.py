from time import perf_counter
import httpx
from pprint import pprint


PROBE_PATHS = ("/llms.txt", "/docs/llms.txt", "/latest/llms.txt")


def probe_llms_sources(hosts, timeout=10.0):
    probes = []
    accepted_sources = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for host in hosts:
            for path in PROBE_PATHS:
                url = f"https://{host}{path}"
                started = perf_counter()
                try:
                    response = client.get(url)
                except httpx.RequestError as error:
                    probes.append(
                        {
                            "url": url,
                            "status_code": None,
                            "latency_ms": int((perf_counter() - started) * 1000),
                            "error": str(error),
                        }
                    )
                    continue

                probes.append(
                    {
                        "url": url,
                        "status_code": response.status_code,
                        "latency_ms": int((perf_counter() - started) * 1000),
                        "error": None,
                    }
                )
                if response.status_code == 200:
                    accepted_sources.append(url)
    return {"probes": probes, "accepted_sources": accepted_sources}


if __name__ == "__main__":
    hosts = ["react.dev", "skeleton.dev", "fastht.ml"]

    pprint(probe_llms_sources(hosts))
