import json
from pathlib import Path

from giga_mcp.db import connect, init_db
from giga_mcp.models import DiscoveryResult


def save_discovery_result(result: DiscoveryResult, db_path: str | Path | None = None) -> None:
    payload = result.model_dump()
    with connect(db_path) as connection:
        init_db(connection)
        connection.execute(
            """
            insert into discovery_runs (discovery_id, name, ecosystem, created_at, payload_json)
            values (?, ?, ?, ?, ?)
            on conflict(discovery_id) do update set
                name=excluded.name,
                ecosystem=excluded.ecosystem,
                created_at=excluded.created_at,
                payload_json=excluded.payload_json
            """,
            (
                result.discovery_id,
                result.name,
                result.ecosystem,
                result.discovered_at,
                json.dumps(payload, sort_keys=True),
            ),
        )
        connection.commit()


def load_discovery_result(discovery_id: str, db_path: str | Path | None = None,) -> DiscoveryResult | None:
    with connect(db_path) as connection:
        init_db(connection)
        row = connection.execute(
            "select payload_json from discovery_runs where discovery_id = ?",
            (discovery_id,),
        ).fetchone()
    if not row:
        return None
    return DiscoveryResult.model_validate(json.loads(row["payload_json"]))



