# shared response models for mcp tools
from typing import Any

from pydantic import BaseModel, Field


class AcceptedSource(BaseModel):
    url: str
    host: str
    tier: int
    reason: str
    confidence: float


class RejectedCandidate(BaseModel):
    url: str
    reason: str


class AuthorityEvidence(BaseModel):
    registry_fields: dict[str, Any] = Field(default_factory=dict)
    repository_fields: dict[str, Any] = Field(default_factory=dict)
    allowlist_hosts: list[str] = Field(default_factory=list)


class ProbeResult(BaseModel):
    url: str
    status_code: int | None = None
    latency_ms: int | None = None
    error: str | None = None


class DiscoveryResult(BaseModel):
    discovery_id: str
    name: str
    ecosystem: str
    accepted_sources: list[AcceptedSource] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidate] = Field(default_factory=list)
    authority_evidence: AuthorityEvidence
    probes: list[ProbeResult] = Field(default_factory=list)
    discovered_at: str


class Citation(BaseModel):
    source_url: str
    title: str
    section: str
    chunk_id: str


class SearchResult(BaseModel):
    snippet: str
    source_url: str
    title: str
    section: str
    chunk_id: str
    score: float


class IndexMetadata(BaseModel):
    source_id: str
    indexed_at: str
    stale: bool


class SearchDocsResponse(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    source_id: str | None = None
    indexed_at: str
    stale: bool


class ExcerptResponse(BaseModel):
    query: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    index_metadata: IndexMetadata


class GetDocResponse(BaseModel):
    path_or_slug: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    index_metadata: IndexMetadata
