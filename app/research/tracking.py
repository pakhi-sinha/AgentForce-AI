from dataclasses import dataclass, field
from datetime import datetime, timezone
import json

from app.db.sqlite import connect, migrate


@dataclass(frozen=True)
class ExperimentRun:
    name: str
    model: str
    dataset: str
    notes: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ExperimentTracker:
    def __init__(self) -> None:
        migrate()
        with connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dataset TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def log(self, run: ExperimentRun, metrics: dict[str, float] | None = None) -> int:
        with connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO experiments (name, model, dataset, metrics, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run.name,
                    run.model,
                    run.dataset,
                    json.dumps(metrics or {}),
                    run.notes,
                    run.created_at.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def list(self) -> list[dict[str, object]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, name, model, dataset, metrics, notes, created_at FROM experiments ORDER BY id DESC"
            ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "model": row["model"],
                "dataset": row["dataset"],
                "metrics": json.loads(row["metrics"]),
                "notes": row["notes"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
