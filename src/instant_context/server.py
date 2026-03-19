from fastmcp import FastMCP

from instant_context.discovery import discover_official_sources as run_discovery
from instant_context.discovery import save_discovery_result
from instant_context.sources import get_doc as run_get_doc
from instant_context.sources import get_excerpt as run_get_excerpt
from instant_context.sources import list_docs as run_list_docs
from instant_context.sources import list_sources as run_list_sources
from instant_context.sources import refresh_source as run_refresh_source
from instant_context.sources import register_discovered_sources as run_register_discovered_sources
from instant_context.sources import register_source_url
from instant_context.sources import search_docs as run_search_docs


def create_server() -> FastMCP:
    app = FastMCP("instant-context")

    @app.tool()
    def discover_official_sources(name: str, ecosystem: str, timeout: float = 10.0) -> dict[str, object]:
        try:
            result = run_discovery(name=name, ecosystem=ecosystem, timeout=timeout)
            save_discovery_result(result)
            return result.model_dump()
        except ValueError as error:
            return {
                "status": "error",
                "tool": "discover_official_sources",
                "message": str(error),
                "name": name,
                "ecosystem": ecosystem,
            }

    @app.tool()
    def register_source(llms_url: str, source_name: str | None = None) -> dict[str, object]:
        return register_source_url(llms_url=llms_url, source_name=source_name)

    @app.tool()
    def register_discovered_sources(discovery_id: str) -> dict[str, object]:
        return run_register_discovered_sources(discovery_id=discovery_id)

    @app.tool()
    def list_sources() -> dict[str, object]:
        return run_list_sources()

    @app.tool()
    def refresh_source(source_id: str, force: bool = False) -> dict[str, object]:
        return run_refresh_source(source_id=source_id, force=force)

    @app.tool()
    def list_docs(source_id: str | None = None, framework: str | None = None) -> dict[str, object]:
        return run_list_docs(source_id=source_id, framework=framework)

    @app.tool()
    def search_docs(query: str, source_id: str | None = None, framework: str | None = None, section: str | None = None, top_k: int = 8) -> dict[str, object]:
        return run_search_docs(
            query=query,
            source_id=source_id,
            framework=framework,
            section=section,
            top_k=top_k,
        )

    @app.tool()
    def get_doc(source_id: str, path_or_slug: str) -> dict[str, object]:
        return run_get_doc(source_id=source_id, path_or_slug=path_or_slug)

    @app.tool()
    def get_excerpt(query: str, source_id: str | None = None, top_k: int = 5, max_chars: int = 4000) -> dict[str, object]:
        return run_get_excerpt(
            query=query, source_id=source_id, top_k=top_k, max_chars=max_chars
        )

    return app


app = create_server()
