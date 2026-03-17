from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from giga_mcp.db import connect, init_db


def create_source_set(source_name: str | None, urls: list[dict[str, object]], db_path: str | Path | None = None,) -> str:
    now = datetime.now(timezone.utc).isoformat()
    source_id = str(uuid4())
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
            [
                (
                    source_id,
                    str(url["url"]),
                    str(url["host"]),
                    int(url["tier"]),
                    now,
                )
                for url in urls
            ],
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
