from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse
from uuid import uuid4

from instant_context.db import connect, init_db


class SourceUrlRow(TypedDict):
    url: str
    host: str
    tier: int


class SourceDocumentRow(TypedDict):
    url: str
    fetched_at: str
    status_code: int | None
    content: str | None


def create_source_set(source_name: str | None, urls: list[SourceUrlRow], db_path: str | Path | None = None) -> str:
    now = datetime.now(timezone.utc).isoformat()
    source_id = str(uuid4())
    source_rows: list[tuple[str, str, str, int, str]] = [
        (source_id, url["url"], url["host"], url["tier"], now) for url in urls
    ]
    with connect(db_path) as connection:
        init_db(connection)
        connection.execute(
            """
            insert into source_sets (source_id, source_name, created_at, updated_at, status)
            values (?, ?, ?, ?, ?)
            """,
            (source_id, source_name, now, now, "active"),
        )
        connection.executemany(
            """
            insert into source_urls (source_id, url, host, tier, created_at)
            values (?, ?, ?, ?, ?)
            """,
            source_rows,
        )
        connection.commit()

    return source_id


def list_source_sets(db_path: str | Path | None = None) -> list[dict[str, object]]:
    with connect(db_path) as connection:
        init_db(connection)
        rows = connection.execute(
            """
            select s.source_id, s.source_name, s.status, s.created_at, s.updated_at,
                   count(u.source_url_id) as url_count,
                   (
                       select cs.indexed_at
                       from cache_snapshots cs
                       where cs.source_id = s.source_id
                       order by cs.indexed_at desc
                       limit 1
                   ) as indexed_at,
                   (
                       select cs.stale
                       from cache_snapshots cs
                       where cs.source_id = s.source_id
                       order by cs.indexed_at desc
                       limit 1
                   ) as stale
            from source_sets s
            left join source_urls u on u.source_id = s.source_id
            group by s.source_id
            order by s.created_at asc
            """
        ).fetchall()

    return [dict(row) for row in rows]


def touch_source_set(source_id: str, db_path: str | Path | None = None) -> bool:
    with connect(db_path) as connection:
        init_db(connection)
        updated_at = datetime.now(timezone.utc).isoformat()
        cursor = connection.execute(
            """
            update source_sets
            set updated_at = ?, status = ?
            where source_id = ?
            """,
            (updated_at, "active", source_id),
        )
        connection.commit()

    return cursor.rowcount > 0


def list_source_docs(source_id: str | None = None, framework: str | None = None, db_path: str | Path | None = None) -> list[dict[str, object]]:
    with connect(db_path) as connection:
        init_db(connection)
        rows = connection.execute(
            """
            select s.source_id, s.source_name, s.status, u.url, u.host, u.tier
            from source_sets s
            join source_urls u on u.source_id = s.source_id
            where (? is null or s.source_id = ?)
              and (? is null or lower(ifnull(s.source_name, '')) like '%' || lower(?) || '%')
            order by s.created_at asc, u.tier asc, u.url asc
            """,
            (source_id, source_id, framework, framework),
        ).fetchall()

    return [dict(row) for row in rows]


def get_source_urls(source_id: str, db_path: str | Path | None = None) -> list[SourceUrlRow]:
    with connect(db_path) as connection:
        init_db(connection)
        rows = connection.execute(
            """
            select url, host, tier
            from source_urls
            where source_id = ?
            order by tier asc, url asc
            """,
            (source_id,),
        ).fetchall()

    return [
        SourceUrlRow(url=row["url"], host=row["host"], tier=row["tier"]) for row in rows
    ]


def replace_source_documents(source_id: str, documents: list[SourceDocumentRow], db_path: str | Path | None = None) -> None:
    with connect(db_path) as connection:
        init_db(connection)
        connection.execute(
            "delete from source_documents where source_id = ?",
            (source_id,),
        )
        connection.executemany(
            """
            insert into source_documents (source_id, url, fetched_at, status_code, content)
            values (?, ?, ?, ?, ?)
            """,
            [
                (
                    source_id,
                    document["url"],
                    document["fetched_at"],
                    document["status_code"],
                    document["content"],
                )
                for document in documents
            ],
        )
        connection.commit()


def list_cached_documents(source_id: str | None = None, framework: str | None = None, db_path: str | Path | None = None) -> list[dict[str, object]]:
    with connect(db_path) as connection:
        init_db(connection)
        rows = connection.execute(
            """
            select d.source_id, d.url, d.fetched_at, d.status_code, d.content, s.source_name, ifnull(u.tier, 2) as tier
            from source_documents d
            join source_sets s on s.source_id = d.source_id
            left join source_urls u on u.source_id = d.source_id and u.url = d.url
            where (? is null or d.source_id = ?)
              and (? is null or lower(ifnull(s.source_name, '')) like '%' || lower(?) || '%')
            order by s.created_at asc, d.url asc
            """,
            (source_id, source_id, framework, framework),
        ).fetchall()

    return [dict(row) for row in rows]


def get_cached_document(source_id: str, path_or_slug: str, db_path: str | Path | None = None) -> dict[str, object] | None:
    with connect(db_path) as connection:
        init_db(connection)
        rows = connection.execute(
            """
            select d.source_id, d.url, d.fetched_at, d.status_code, d.content, s.source_name
            from source_documents d
            join source_sets s on s.source_id = d.source_id
            where d.source_id = ?
            order by d.url asc
            """,
            (source_id,),
        ).fetchall()

    keys = _document_lookup_keys(path_or_slug)

    if not keys:
        return None

    exact_full_url, exact_path, exact_tail = keys
    best_rank = 9
    best_match: dict[str, object] | None = None

    for row in rows:
        url = str(row["url"]).strip().lower()

        if url == exact_full_url:
            return dict(row)

        path = urlparse(url).path.strip("/")
        rank = (
            1
            if path == exact_path
            else 2
            if path.endswith(f"/{exact_tail}") or path == exact_tail
            else 3
            if exact_tail and exact_tail in url
            else 9
        )
        if rank < best_rank:
            best_rank = rank
            best_match = dict(row)
    return best_match


def _document_lookup_keys(path_or_slug: str) -> tuple[str, str, str] | None:
    raw = path_or_slug.strip().lower()

    if not raw:
        return None
    full_url = raw.rstrip("/")

    if full_url.startswith("http://") or full_url.startswith("https://"):
        parsed = urlparse(full_url)
        path = parsed.path.strip("/")
        tail = path.split("/")[-1] if path else ""
        return full_url, path, tail
    path = raw.strip("/")
    tail = path.split("/")[-1] if path else ""

    return full_url, path, tail


def save_cache_snapshot(source_id: str, indexed_at: str, expires_at: str, stale: bool = False, db_path: str | Path | None = None) -> None:
    with connect(db_path) as connection:
        init_db(connection)
        connection.execute(
            """
            insert into cache_snapshots (source_id, indexed_at, expires_at, stale)
            values (?, ?, ?, ?)
            """,
            (source_id, indexed_at, expires_at, 1 if stale else 0),
        )
        connection.commit()


def latest_cache_snapshot(source_id: str, db_path: str | Path | None = None) -> dict[str, object] | None:
    with connect(db_path) as connection:
        init_db(connection)
        row = connection.execute(
            """
            select source_id, indexed_at, expires_at, stale
            from cache_snapshots
            where source_id = ?
            order by indexed_at desc
            limit 1
            """,
            (source_id,),
        ).fetchone()

    return dict(row) if row else None
