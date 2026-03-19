# sqlite bootstrap for giga mcp
from pathlib import Path
import sqlite3


def default_db_path() -> Path:
    return Path.cwd() / ".instant-context" / "instant_context.sqlite3"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row

    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        create table if not exists schema_meta (
            key text primary key,
            value text not null
        );

        create table if not exists source_sets (
            source_id text primary key,
            source_name text,
            created_at text not null,
            updated_at text not null,
            status text not null
        );

        create table if not exists source_urls (
            source_url_id integer primary key autoincrement,
            source_id text not null,
            url text not null,
            host text not null,
            tier integer not null,
            created_at text not null,
            unique(source_id, url),
            foreign key(source_id) references source_sets(source_id)
        );

        create table if not exists cache_snapshots (
            snapshot_id integer primary key autoincrement,
            source_id text not null,
            indexed_at text not null,
            expires_at text not null,
            stale integer not null default 0,
            unique(source_id, indexed_at),
            foreign key(source_id) references source_sets(source_id)
        );

        create table if not exists discovery_runs (
            discovery_id text primary key,
            name text not null,
            ecosystem text not null,
            created_at text not null,
            payload_json text not null
        );

        create table if not exists source_documents (
            source_id text not null,
            url text not null,
            fetched_at text not null,
            status_code integer,
            content text,
            primary key(source_id, url),
            foreign key(source_id) references source_sets(source_id)
        );
        """
    )

    connection.commit()
