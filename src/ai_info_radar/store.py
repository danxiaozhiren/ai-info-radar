from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .models import AlertHistoryEntry, NormalizedItem, Source, SourceHealthEntry, StoredItem, utc_now_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  vendor TEXT NOT NULL,
  source_type TEXT NOT NULL,
  authority_level TEXT NOT NULL,
  url TEXT NOT NULL,
  priority INTEGER NOT NULL,
  parsing_strategy TEXT NOT NULL,
  content_type TEXT NOT NULL,
  enabled INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  vendor TEXT NOT NULL,
  authority_level TEXT NOT NULL,
  content_type TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  detected_at TEXT NOT NULL,
  published_at TEXT,
  summary TEXT NOT NULL,
  fingerprint TEXT NOT NULL UNIQUE,
  trace_json TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_health (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  ok INTEGER NOT NULL,
  message TEXT NOT NULL,
  item_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_history (
  alert_key TEXT PRIMARY KEY,
  item_id INTEGER NOT NULL,
  fingerprint TEXT NOT NULL,
  notifier TEXT NOT NULL,
  status TEXT NOT NULL,
  message TEXT NOT NULL,
  alerted_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class InsertSummary:
    inserted: int
    existing: int


class RadarStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "RadarStore":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def upsert_source(self, source: Source) -> None:
        self.connection.execute(
            """
            INSERT INTO sources (
              id, name, vendor, source_type, authority_level, url, priority,
              parsing_strategy, content_type, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              vendor = excluded.vendor,
              source_type = excluded.source_type,
              authority_level = excluded.authority_level,
              url = excluded.url,
              priority = excluded.priority,
              parsing_strategy = excluded.parsing_strategy,
              content_type = excluded.content_type,
              enabled = excluded.enabled
            """,
            (
                source.id,
                source.name,
                source.vendor,
                source.source_type,
                source.authority_level,
                source.url,
                source.priority,
                source.parsing_strategy,
                source.content_type,
                int(source.enabled),
            ),
        )
        self.connection.commit()

    def insert_items(self, items: list[NormalizedItem]) -> InsertSummary:
        inserted = 0
        existing = 0
        for item in items:
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO items (
                  source_id, source_name, vendor, authority_level, content_type,
                  title, url, detected_at, published_at, summary, fingerprint,
                  trace_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.source_id,
                    item.source_name,
                    item.vendor,
                    item.authority_level,
                    item.content_type,
                    item.title,
                    item.url,
                    item.detected_at,
                    item.published_at,
                    item.summary,
                    item.fingerprint,
                    json.dumps(item.trace, ensure_ascii=False, sort_keys=True),
                    utc_now_iso(),
                ),
            )
            if cursor.rowcount == 1:
                inserted += 1
            else:
                existing += 1
        self.connection.commit()
        return InsertSummary(inserted=inserted, existing=existing)

    def record_health(self, source_id: str, ok: bool, message: str, item_count: int) -> None:
        self.connection.execute(
            """
            INSERT INTO source_health (source_id, checked_at, ok, message, item_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_id, utc_now_iso(), int(ok), message, item_count),
        )
        self.connection.commit()

    def list_items(self) -> list[StoredItem]:
        rows = self.connection.execute(
            """
            SELECT id, source_id, source_name, vendor, authority_level, content_type,
                   title, url, detected_at, published_at, summary, fingerprint, state, trace_json
            FROM items
            ORDER BY id
            """
        ).fetchall()
        return [_stored_item_from_row(row) for row in rows]

    def item_state_counts(self) -> dict[str, int]:
        rows = self.connection.execute(
            """
            SELECT state, COUNT(*) AS count
            FROM items
            GROUP BY state
            ORDER BY state
            """
        ).fetchall()
        return {row["state"]: int(row["count"]) for row in rows}

    def alert_exists(self, alert_key: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM alert_history WHERE alert_key = ?",
            (alert_key,),
        ).fetchone()
        return row is not None

    def record_alert(
        self,
        *,
        alert_key: str,
        item_id: int,
        fingerprint: str,
        notifier: str,
        status: str,
        message: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO alert_history (
              alert_key, item_id, fingerprint, notifier, status, message, alerted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (alert_key, item_id, fingerprint, notifier, status, message, utc_now_iso()),
        )
        self.connection.commit()

    def supporting_sources_for(self, *, title: str, exclude_item_id: int) -> tuple[str, ...]:
        rows = self.connection.execute(
            """
            SELECT DISTINCT source_name
            FROM items
            WHERE title = ? AND id != ?
            ORDER BY source_name
            """,
            (title, exclude_item_id),
        ).fetchall()
        return tuple(row["source_name"] for row in rows)

    def list_alert_history(self) -> list[AlertHistoryEntry]:
        rows = self.connection.execute(
            """
            SELECT a.alert_key, a.item_id, a.fingerprint, a.notifier, a.status,
                   a.message, a.alerted_at, i.title, i.url, i.source_name
            FROM alert_history a
            JOIN items i ON i.id = a.item_id
            ORDER BY a.alerted_at DESC, a.item_id DESC
            """
        ).fetchall()
        return [
            AlertHistoryEntry(
                alert_key=row["alert_key"],
                item_id=int(row["item_id"]),
                fingerprint=row["fingerprint"],
                notifier=row["notifier"],
                status=row["status"],
                message=row["message"],
                alerted_at=row["alerted_at"],
                title=row["title"],
                url=row["url"],
                source_name=row["source_name"],
            )
            for row in rows
        ]

    def list_source_failures(self) -> list[SourceHealthEntry]:
        rows = self.connection.execute(
            """
            SELECT source_id, checked_at, ok, message, item_count
            FROM source_health
            WHERE ok = 0
            ORDER BY checked_at DESC, id DESC
            """
        ).fetchall()
        return [
            SourceHealthEntry(
                source_id=row["source_id"],
                checked_at=row["checked_at"],
                ok=bool(row["ok"]),
                message=row["message"],
                item_count=int(row["item_count"]),
            )
            for row in rows
        ]

    def mark_new_items_digested(self, item_ids: list[int]) -> int:
        if not item_ids:
            return 0
        placeholders = ", ".join("?" for _ in item_ids)
        cursor = self.connection.execute(
            f"""
            UPDATE items
            SET state = 'digested'
            WHERE state = 'new' AND id IN ({placeholders})
            """,
            tuple(item_ids),
        )
        self.connection.commit()
        return int(cursor.rowcount)


def _stored_item_from_row(row: sqlite3.Row) -> StoredItem:
    try:
        trace = json.loads(row["trace_json"])
    except json.JSONDecodeError:
        trace = {}
    return StoredItem(
        id=int(row["id"]),
        source_id=row["source_id"],
        source_name=row["source_name"],
        vendor=row["vendor"],
        authority_level=row["authority_level"],
        content_type=row["content_type"],
        title=row["title"],
        url=row["url"],
        detected_at=row["detected_at"],
        published_at=row["published_at"],
        summary=row["summary"],
        fingerprint=row["fingerprint"],
        state=row["state"],
        trace=trace,
    )
