# generic official llms source discovery + mcp retrieval spec

## 1) purpose

This document is a handoff spec for building a **generic** MCP server that can discover and retrieve documentation from official `llms*.txt` sources across technologies.

The target audience is another LLM or engineer implementing the system.

This spec includes both:

- intuitive explanation of why each part exists
- technical contracts, architecture, constraints, and acceptance criteria

---

## 2) what was decided in discussion (locked)

These are fixed project decisions from user + assistant discussion.

- output file location: `DISCOVERY_SPEC.md`
- scope: **full generic MCP flow** (discovery + source registration + indexing + retrieval)
- style: **hybrid** (explanatory + prescriptive)
- trust mode: **official-only strict mode**
- source policy when multiple official sources are found: **index all official sources**
- source precedence: **tiered precedence** (higher-confidence sources preferred in ranking/ties)
- fallback probe paths (when root `/llms.txt` is missing):
  - `/docs/llms.txt`
  - `/latest/llms.txt`
- ecosystems for v1 strict discovery: **npm + PyPI**
- retrieval approach: **local lexical search** (no embedding/vector dependency)

---

## 3) problem statement

Current implementation is Skeleton-specific and source-fixed.

Target state:

- user (or LLM) can provide a technology/package/domain
- MCP discovers official `llms*.txt` source(s)
- MCP indexes docs locally with cache + refresh
- LLM queries docs through MCP tools and gets cited snippets

Key constraints:

- official sources only
- deterministic behavior
- transparent evidence for discovery decisions

---

## 4) non-goals (v1)

- no broad mode (no community mirrors, no arbitrary search engine scraping for source selection)
- no semantic embedding retrieval
- no dynamic spawning of separate MCP servers per technology
- no guaranteed 100% discovery completeness claim

---

## 5) high-level workflow (how LLM uses this MCP)

### path A: user provides `llms.txt` URL

1. LLM calls `register_source(url)`
2. MCP validates strict official policy (if metadata context provided)
3. MCP fetches root source, expands linked official `llms*.txt` URLs
4. MCP indexes cache
5. LLM queries via `search_docs` / `get_excerpt` / `get_doc`

### path B: user provides technology/package name

1. LLM calls `discover_official_sources(name, ecosystem)`
2. MCP resolves authority chain (registry -> repository -> official docs host)
3. MCP probes allowed `llms` paths on official hosts
4. MCP returns accepted sources + evidence + rejected candidates
5. LLM calls `register_source` or `register_discovered_sources`
6. LLM queries retrieval tools

---

## 6) architecture

## 6.1 components

- `discovery` module
  - authority chain resolution (npm/PyPI, GitHub repo metadata)
  - strict host allowlist construction
  - `llms` candidate probing + validation
- `source registry` module
  - stores discovered/registered source sets
  - source status, precedence tier, timestamps
- `fetch` module
  - http fetch with retries/backoff/timeout
- `parse` module
  - parse markdown/text source indexes and docs
- `index` module
  - chunking + lexical ranking + dedupe
- `cache` module
  - persisted snapshots per source/workspace
- `mcp tool layer`
  - discovery tools + retrieval tools

## 6.2 runtime model

- single MCP server process
- multiple registered source sets
- each source set has its own indexed snapshot
- retrieval can target one source set or all registered sets

---

## 7) strict official discovery model

## 7.1 authority chain

Discovery must rely on authority links, not name guessing.

### npm route

1. fetch package metadata from npm registry
2. extract `homepage`, `repository.url`, `bugs.url`
3. if repository is GitHub, fetch GitHub repo metadata
4. extract repo `homepage`
5. construct allowed hosts from these authoritative fields

### PyPI route

1. fetch package metadata from PyPI JSON
2. extract `project_urls` and `home_page`
3. if repository is GitHub, fetch repo metadata
4. construct allowed hosts from authoritative links

## 7.2 allowed-host policy

Accepted source URL host must satisfy one of:

- exact host from authoritative homepage/docs URLs
- subdomain of authoritative host (ex: `docs.example.com`)
- host directly linked by authoritative source metadata and categorized as docs/homepage/repository context

Reject if:

- host not in strict allowlist
- protocol is not HTTPS

## 7.3 probing policy

For each allowed host, probe in this order:

1. `/llms.txt`
2. `/docs/llms.txt`
3. `/latest/llms.txt`

If a probed file is found, parse it and extract linked `llms*.txt` URLs.

Follow-up linked URLs are accepted only if host remains in allowlist.

## 7.4 precedence tiers

When indexing multiple official sources, assign precedence tier:

- tier 1: root canonical files (`/llms.txt`, `/llms-full.txt`)
- tier 2: official docs-subpath files (`/docs/.../llms.txt`, `/latest/llms.txt`, versioned doc indexes)

Ranking behavior:

- tier boosts used only as tie-breaker or slight score adjustment
- lexical relevance remains primary signal

---

## 8) real authority-chain examples (validated during discussion)

## 8.1 react

- npm: `https://registry.npmjs.org/react/latest`
  - homepage -> `https://react.dev/`
  - repository -> `https://github.com/facebook/react`
- github: `https://api.github.com/repos/facebook/react`
  - homepage -> `https://react.dev`
- discovered source: `https://react.dev/llms.txt` (found)

## 8.2 next.js

- npm: `https://registry.npmjs.org/next/latest`
  - homepage -> `https://nextjs.org`
- github: `https://api.github.com/repos/vercel/next.js`
  - homepage -> `https://nextjs.org`
- discovered root source: `https://nextjs.org/llms.txt` (found)
- discovered linked variants from root:
  - `https://nextjs.org/docs/llms.txt`
  - `https://nextjs.org/docs/llms-full.txt`
  - versioned docs `.../docs/15/llms.txt`, `.../docs/14/llms.txt`

## 8.3 svelte

- npm: `https://registry.npmjs.org/svelte/latest`
  - homepage -> `https://svelte.dev`
- github: `https://api.github.com/repos/sveltejs/svelte`
  - homepage -> `https://svelte.dev`
- discovered root source: `https://svelte.dev/llms.txt` (found)
- discovered linked variants from root:
  - `https://svelte.dev/llms-medium.txt`
  - `https://svelte.dev/llms-small.txt`
  - `https://svelte.dev/llms-full.txt`
  - package-specific docs indexes under `/docs/.../llms.txt`

## 8.4 vue

- npm `vue` homepage points to repo readme path (not docs domain)
- github `vuejs/core` homepage resolves canonical docs host:
  - `https://vuejs.org/`
- discovered source: `https://vuejs.org/llms.txt` (found)

## 8.5 typescript (name-domain mismatch case)

- npm `typescript` homepage -> `https://www.typescriptlang.org/`
- github `microsoft/TypeScript` homepage -> same domain
- strict probes:
  - `/llms.txt` -> 404
  - `/docs/llms.txt` -> 404
  - `/latest/llms.txt` -> no official file observed
- outcome: official domain resolved correctly, no official llms source currently found

## 8.6 pydantic (docs-subpath case)

- PyPI project URLs include docs host `https://docs.pydantic.dev`
- probes:
  - `/llms.txt` -> 404
  - `/latest/llms.txt` -> found
- outcome: fallback probe path is necessary and valid in strict mode

---

## 9) mcp tool contracts (v1)

All tools return structured JSON-compatible objects.

## discovery + source lifecycle

- `discover_official_sources(name: str, ecosystem: "npm" | "pypi")`
  - resolves authority chain
  - probes strict paths
  - returns accepted + rejected + evidence

- `register_source(llms_url: str, source_name: str | None = None)`
  - validates URL
  - validates strict host policy where possible
  - indexes source set

- `register_discovered_sources(discovery_id: str)`
  - bulk register all accepted discovered sources

- `list_sources()`
  - list registered source sets and health

- `refresh_source(source_id: str, force: bool = False)`
  - refresh one source set

## retrieval

- `list_docs(source_id: str | None = None, framework: str | None = None)`
- `search_docs(query: str, source_id: str | None = None, framework: str | None = None, section: str | None = None, top_k: int = 8)`
- `get_doc(source_id: str, path_or_slug: str)`
- `get_excerpt(query: str, source_id: str | None = None, top_k: int = 5, max_chars: int = 4000)`

---

## 10) response schema requirements

## discovery result must include

- `accepted_sources[]`
  - url
  - host
  - tier
  - reason
  - confidence
- `rejected_candidates[]`
  - url
  - reason
- `authority_evidence`
  - registry fields used
  - repository fields used
  - final allowlist hosts
- `probes[]`
  - url
  - status_code
  - latency_ms

## retrieval result must include

- snippet/content payload
- citations:
  - source_url
  - doc title
  - section
  - chunk_id
- index metadata:
  - source_id
  - indexed_at
  - stale flag

---

## 11) indexing + retrieval behavior

- parse markdown/text and preserve heading structure
- chunk primarily by heading boundaries
- lexical ranking weights:
  - title > section > body
- query alias expansion allowed (local dictionary)
- dedupe across multi-source ingestion by:
  - canonical URL
  - normalized heading/title + text hash
- cap outputs for token safety
- deterministic sort order for reproducibility

---

## 12) caching and refresh

- cache persisted locally (per source set)
- TTL-based freshness
- startup behavior:
  - use existing cache immediately
  - background refresh when stale
- on network failure:
  - serve stale snapshot
  - return stale indicator in response

---

## 13) reliability + security requirements

- HTTPS-only source acceptance
- strict host allowlist enforcement
- request timeout + retry + exponential backoff
- bounded concurrency for probes and fetches
- no execution of remote content
- no trust of non-authoritative links

---

## 14) observability requirements

Emit structured logs for:

- discovery start/end
- authority fields extracted
- probe attempts and status codes
- acceptance/rejection reasons
- indexing counts (docs/chunks)
- stale-cache fallback events

---

## 15) practical limits and guarantees

- official-source precision should be high under strict mode
- full completeness cannot be guaranteed due to:
  - nonstandard pathing
  - robots/rate limits/network failures
  - undocumented/private source locations
- system must report evidence of what was checked

---

## 16) phased implementation plan

## phase 1: strict discovery core

- add `discover_official_sources` for npm + PyPI
- add authority extraction + host allowlist
- add strict probing + evidence return

## phase 2: source registry integration

- support bulk registration from discovery result
- assign precedence tiers
- persist source set metadata

## phase 3: multi-source indexing/retrieval

- index all accepted official sources
- dedupe and tier-aware ranking
- retrieval filters by source/framework/section

## phase 4: hardening

- logging, retry/backoff tuning
- stale-cache behavior verification
- edge-case tests for name-domain mismatch and docs-subpath hosts

---

## 17) test and acceptance criteria

## discovery tests

- npm packages: react, next, svelte, vue, typescript
- PyPI package: pydantic
- expected:
  - discover official sources for react/next/svelte/vue/pydantic
  - return no source for typescript but clear evidence/probe logs

## strictness tests

- reject non-allowlisted `llms.txt` URL even if reachable
- accept docs subdomain/path only when authority-linked

## retrieval tests

- deterministic top-k ordering
- citation fields present on every result
- dedupe works across multiple official sources

---

## 18) migration from current codebase

Current implementation is Skeleton-specific.

Migration direction:

- keep existing cache/index/search architecture
- replace source-specific fetch assumptions with source registry + discovery pipeline
- maintain stdio MCP transport and existing retrieval tools while adding discovery tools

---

## 19) final implementation guidance for builder llm

- prioritize correctness of authority chain over breadth
- make discovery explainable (evidence-first responses)
- keep retrieval deterministic and citation-rich
- preserve strict mode defaults and avoid broad-mode behavior



## 20) text-based sequence diagram

```text
user
  |
  | asks coding llm for docs-aware help
  v
coding llm client
  |
  | 1) discover_official_sources(name, ecosystem)
  v
generic docs mcp server
  |
  | -> resolve authority chain (registry + repo metadata)
  | -> probe official llms paths
  | <- return accepted_sources + evidence
  |
  | 2) register_discovered_sources(discovery_id)
  |
  | -> fetch llms sources
  | -> parse/chunk/index
  | -> save cache snapshot
  | <- return source_ids + indexed counts
  |
  | 3) search_docs(query, source_id?, top_k?)
  |    or get_excerpt(...) / get_doc(...)
  |
  | -> query local lexical index
  | <- return structured results + citations
  v
coding llm client
  |
  | grounded answer to user
  v
user
```

## 21) mcp-first retrieval shape

retrieval should come back as structured json-like payloads, for example:

- `query`
- `results[]`
  - `snippet`
  - `source_url`
  - `title`
  - `section`
  - `chunk_id`
  - `score`
- `source_id`
- `indexed_at`
- `stale`

this is what keeps the workflow aligned with traditional mcp usage.

