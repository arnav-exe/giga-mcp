# fastmcp entrypoint
from fastmcp import FastMCP


def _not_implemented(tool, **payload):
    return {
        "status": "TODO: implement",
        "tool": tool,
        "message": "chill b im working onit",
        **payload,
    }


def create_server():
    app = FastMCP("giga-mcp")

    @app.tool()
    def discover_official_sources(name: str, ecosystem: str):
        return _not_implemented(
            "discover_official_sources",
            name=name,
            ecosystem=ecosystem,
            accepted_sources=[],
            rejected_candidates=[],
            authority_evidence={
                "registry_fields": {},
                "repository_fields": {},
                "allowlist_hosts": [],
            },
            probes=[],
        )

    @app.tool()
    def register_source(llms_url: str, source_name: str | None = None):
        return _not_implemented(
            "register_source",
            llms_url=llms_url,
            source_name=source_name,
        )

    @app.tool()
    def register_discovered_sources(discovery_id: str):
        return _not_implemented(
            "register_discovered_sources",
            discovery_id=discovery_id,
            source_ids=[],
        )

    @app.tool()
    def list_sources():
        return _not_implemented("list_sources", sources=[])

    @app.tool()
    def refresh_source(source_id: str, force: bool = False):
        return _not_implemented(
            "refresh_source",
            source_id=source_id,
            force=force,
        )

    @app.tool()
    def list_docs(source_id: str | None = None, framework: str | None = None):
        return _not_implemented(
            "list_docs",
            source_id=source_id,
            framework=framework,
            docs=[],
        )

    @app.tool()
    def search_docs(
        query: str,
        source_id: str | None = None,
        framework: str | None = None,
        section: str | None = None,
        top_k: int = 8,
    ):
        return _not_implemented(
            "search_docs",
            query=query,
            source_id=source_id,
            framework=framework,
            section=section,
            top_k=top_k,
            results=[],
            stale=False,
        )

    @app.tool()
    def get_doc(source_id: str, path_or_slug: str):
        return _not_implemented(
            "get_doc",
            source_id=source_id,
            path_or_slug=path_or_slug,
        )

    @app.tool()
    def get_excerpt(
        query: str,
        source_id: str | None = None,
        top_k: int = 5,
        max_chars: int = 4000,
    ):
        return _not_implemented(
            "get_excerpt",
            query=query,
            source_id=source_id,
            top_k=top_k,
            max_chars=max_chars,
            content="",
            citations=[],
        )

    return app


app = create_server()
