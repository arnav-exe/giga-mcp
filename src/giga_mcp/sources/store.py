from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from giga_mcp.db import connect, init_db


class SourceUrlRow(TypedDict):
    url: str
    host: str
    tier: int


def create_source_set(source_name: str | None, urls: list[SourceUrlRow], db_path: str | Path | None = None,) -> str:
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
                   count(u.source_url_id) as url_count
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


def list_source_docs(source_id: str | None = None, framework: str | None = None, db_path: str | Path | None = None,) -> list[dict[str, object]]:
    with connect(db_path) as connection:
        init_db(connection)
        query = """
            select s.source_id, s.source_name, s.status, u.url, u.host, u.tier
            from source_sets s
            join source_urls u on u.source_id = s.source_id
            where (? is null or s.source_id = ?)
              and (? is null or lower(ifnull(s.source_name, '')) like '%' || lower(?) || '%')
            order by s.created_at asc, u.tier asc, u.url asc
            """
        rows = connection.execute(
            query,
            (source_id, source_id, framework, framework),
        ).fetchall()

    return [dict(row) for row in rows]
