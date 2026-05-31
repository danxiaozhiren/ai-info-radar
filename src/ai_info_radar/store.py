from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .models import (
    AlertHistoryEntry,
    EventRecord,
    NormalizedItem,
    Source,
    SourceHealthEntry,
    StoredItem,
    utc_now_iso,
)


ITEM_STATES = {"new", "alerted", "daily", "read", "saved", "ignored", "digested"}
USER_SETTABLE_ITEM_STATES = {"read", "saved", "ignored"}

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

CREATE TABLE IF NOT EXISTS events (
  event_key TEXT PRIMARY KEY,
  canonical_item_id INTEGER NOT NULL,
  canonical_title TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  vendor TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  item_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS event_items (
  event_key TEXT NOT NULL,
  item_id INTEGER NOT NULL UNIQUE,
  relation TEXT NOT NULL,
  matched_by TEXT NOT NULL,
  linked_at TEXT NOT NULL,
  PRIMARY KEY (event_key, item_id)
);

CREATE TABLE IF NOT EXISTS event_match_keys (
  match_key TEXT PRIMARY KEY,
  event_key TEXT NOT NULL,
  match_type TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class InsertSummary:
    inserted: int
    existing: int


@dataclass(frozen=True)
class ItemStateUpdate:
    item: StoredItem
    previous_state: str
    new_state: str


class ItemStateError(ValueError):
    pass


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

    def list_items(self, *, state: str | None = None) -> list[StoredItem]:
        if state is not None and state not in ITEM_STATES:
            raise ItemStateError(f"Unsupported item state: {state}")
        where = "WHERE state = ?" if state is not None else ""
        parameters = (state,) if state is not None else ()
        rows = self.connection.execute(
            f"""
            SELECT id, source_id, source_name, vendor, authority_level, content_type,
                   title, url, detected_at, published_at, summary, fingerprint, state, trace_json
            FROM items
            {where}
            ORDER BY id
            """,
            parameters,
        ).fetchall()
        return [_stored_item_from_row(row) for row in rows]

    def list_recent_items(self, *, limit: int = 20) -> list[StoredItem]:
        if limit < 1:
            raise ItemStateError("Recent item limit must be positive.")
        rows = self.connection.execute(
            """
            SELECT id, source_id, source_name, vendor, authority_level, content_type,
                   title, url, detected_at, published_at, summary, fingerprint, state, trace_json
            FROM items
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
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

    def item_alert_exists(self, item_id: int) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM alert_history WHERE item_id = ?",
            (item_id,),
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
        self.connection.execute(
            """
            UPDATE items
            SET state = 'alerted'
            WHERE id = ? AND state NOT IN ('read', 'saved', 'ignored')
            """,
            (item_id,),
        )
        self.connection.commit()

    def supporting_sources_for(
        self,
        *,
        title: str,
        exclude_item_id: int,
        target_url: str | None = None,
    ) -> tuple[str, ...]:
        supporting_sources: set[str] = set()
        for item in self.list_items():
            if item.id == exclude_item_id:
                continue
            if item.title == title:
                supporting_sources.add(item.source_name)
                continue
            if target_url and item.trace.get("target_url") == target_url:
                supporting_sources.add(item.source_name)
        return tuple(sorted(supporting_sources))

    def find_event_by_match_keys(self, match_keys: list[tuple[str, str]]) -> str | None:
        for match_key, _match_type in match_keys:
            row = self.connection.execute(
                "SELECT event_key FROM event_match_keys WHERE match_key = ?",
                (match_key,),
            ).fetchone()
            if row is not None:
                return row["event_key"]
        return None

    def upsert_event_item(
        self,
        *,
        event_key: str,
        item: StoredItem,
        relation: str,
        matched_by: str,
    ) -> None:
        seen_at = item.published_at or item.detected_at
        self.connection.execute(
            """
            INSERT OR IGNORE INTO events (
              event_key, canonical_item_id, canonical_title, canonical_url, vendor,
              first_seen_at, last_seen_at, item_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                event_key,
                item.id,
                item.title,
                item.url,
                item.vendor,
                seen_at,
                seen_at,
            ),
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO event_items (event_key, item_id, relation, matched_by, linked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_key, item.id, relation, matched_by, utc_now_iso()),
        )
        self.connection.execute(
            """
            UPDATE events
            SET last_seen_at = CASE WHEN last_seen_at > ? THEN last_seen_at ELSE ? END,
                item_count = (
                  SELECT COUNT(*) FROM event_items WHERE event_items.event_key = events.event_key
                )
            WHERE event_key = ?
            """,
            (seen_at, seen_at, event_key),
        )
        self.connection.commit()

    def register_event_match_keys(
        self,
        *,
        event_key: str,
        match_keys: list[tuple[str, str]],
    ) -> None:
        for match_key, match_type in match_keys:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO event_match_keys (match_key, event_key, match_type)
                VALUES (?, ?, ?)
                """,
                (match_key, event_key, match_type),
            )
        self.connection.commit()

    def event_key_for_item(self, item_id: int) -> str | None:
        row = self.connection.execute(
            "SELECT event_key FROM event_items WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        return row["event_key"] if row is not None else None

    def event_items(self, event_key: str) -> list[StoredItem]:
        rows = self.connection.execute(
            """
            SELECT i.id, i.source_id, i.source_name, i.vendor, i.authority_level,
                   i.content_type, i.title, i.url, i.detected_at, i.published_at,
                   i.summary, i.fingerprint, i.state, i.trace_json
            FROM event_items ei
            JOIN items i ON i.id = ei.item_id
            WHERE ei.event_key = ?
            ORDER BY i.id
            """,
            (event_key,),
        ).fetchall()
        return [_stored_item_from_row(row) for row in rows]

    def list_events(self) -> list[EventRecord]:
        rows = self.connection.execute(
            """
            SELECT event_key, canonical_item_id, canonical_title, canonical_url, vendor,
                   first_seen_at, last_seen_at, item_count
            FROM events
            ORDER BY first_seen_at, event_key
            """
        ).fetchall()
        return [
            EventRecord(
                event_key=row["event_key"],
                canonical_item_id=int(row["canonical_item_id"]),
                canonical_title=row["canonical_title"],
                canonical_url=row["canonical_url"],
                vendor=row["vendor"],
                first_seen_at=row["first_seen_at"],
                last_seen_at=row["last_seen_at"],
                item_count=int(row["item_count"]),
                supporting_sources=self.event_supporting_sources(
                    row["event_key"],
                    exclude_item_id=int(row["canonical_item_id"]),
                ),
            )
            for row in rows
        ]

    def event_supporting_sources(self, event_key: str, *, exclude_item_id: int) -> tuple[str, ...]:
        rows = self.connection.execute(
            """
            SELECT DISTINCT i.source_name
            FROM event_items ei
            JOIN items i ON i.id = ei.item_id
            WHERE ei.event_key = ? AND i.id != ?
            ORDER BY i.source_name
            """,
            (event_key, exclude_item_id),
        ).fetchall()
        return tuple(row["source_name"] for row in rows)

    def list_alert_history(self, *, exclude_item_states: set[str] | None = None) -> list[AlertHistoryEntry]:
        excluded = tuple(sorted(exclude_item_states or ()))
        where = ""
        parameters: tuple[str, ...] = ()
        if excluded:
            unsupported = sorted(set(excluded) - ITEM_STATES)
            if unsupported:
                raise ItemStateError(f"Unsupported item state: {', '.join(unsupported)}")
            placeholders = ", ".join("?" for _ in excluded)
            where = f"WHERE i.state NOT IN ({placeholders})"
            parameters = excluded
        rows = self.connection.execute(
            f"""
            SELECT a.alert_key, a.item_id, a.fingerprint, a.notifier, a.status,
                   a.message, a.alerted_at, i.title, i.url, i.source_name
            FROM alert_history a
            JOIN items i ON i.id = a.item_id
            {where}
            ORDER BY a.alerted_at DESC, a.item_id DESC
            """,
            parameters,
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
                supporting_sources=self._supporting_sources_for_alert(
                    row["alert_key"],
                    int(row["item_id"]),
                ),
            )
            for row in rows
        ]

    def _supporting_sources_for_alert(self, alert_key: str, item_id: int) -> tuple[str, ...]:
        event_key = alert_key.removeprefix("event:") if alert_key.startswith("event:") else None
        if event_key is None:
            event_key = self.event_key_for_item(item_id)
        if event_key is None:
            return ()
        return self.event_supporting_sources(event_key, exclude_item_id=item_id)

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
        return self.mark_new_items_daily(item_ids)

    def mark_new_items_daily(self, item_ids: list[int]) -> int:
        if not item_ids:
            return 0
        placeholders = ", ".join("?" for _ in item_ids)
        cursor = self.connection.execute(
            f"""
            UPDATE items
            SET state = 'daily'
            WHERE state = 'new' AND id IN ({placeholders})
            """,
            tuple(item_ids),
        )
        self.connection.commit()
        return int(cursor.rowcount)

    def resolve_item_identifier(self, identifier: str) -> StoredItem:
        cleaned = identifier.strip()
        if not cleaned:
            raise ItemStateError("Empty item identifier.")

        if cleaned.isdecimal():
            item = self._item_by_id(int(cleaned))
            if item is not None:
                return item

        if len(cleaned) < 6:
            raise ItemStateError(f"Item fingerprint prefix is too short: {cleaned}")

        matches = self._items_by_fingerprint_prefix(cleaned)
        if not matches:
            raise ItemStateError(f"Unknown item identifier: {cleaned}")
        if len(matches) > 1:
            matching_ids = ", ".join(str(item.id) for item in matches)
            raise ItemStateError(f"Ambiguous item identifier {cleaned}; matches item ids: {matching_ids}")
        return matches[0]

    def set_item_state_by_identifiers(
        self,
        identifiers: list[str],
        state: str,
    ) -> list[ItemStateUpdate]:
        if state not in USER_SETTABLE_ITEM_STATES:
            raise ItemStateError(f"State is not user-settable: {state}")
        if not identifiers:
            raise ItemStateError("At least one item identifier is required.")

        resolved: dict[int, StoredItem] = {}
        for identifier in identifiers:
            item = self.resolve_item_identifier(identifier)
            resolved.setdefault(item.id, item)

        updates = [
            ItemStateUpdate(item=item, previous_state=item.state, new_state=state)
            for item in resolved.values()
        ]
        for update in updates:
            self.connection.execute(
                "UPDATE items SET state = ? WHERE id = ?",
                (state, update.item.id),
            )
        self.connection.commit()
        return updates

    def set_item_state_by_id(self, item_id: int, state: str) -> None:
        if state not in ITEM_STATES:
            raise ItemStateError(f"Unsupported item state: {state}")
        self.connection.execute(
            "UPDATE items SET state = ? WHERE id = ?",
            (state, item_id),
        )
        self.connection.commit()

    def _item_by_id(self, item_id: int) -> StoredItem | None:
        row = self.connection.execute(
            """
            SELECT id, source_id, source_name, vendor, authority_level, content_type,
                   title, url, detected_at, published_at, summary, fingerprint, state, trace_json
            FROM items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
        return _stored_item_from_row(row) if row is not None else None

    def _items_by_fingerprint_prefix(self, prefix: str) -> list[StoredItem]:
        rows = self.connection.execute(
            """
            SELECT id, source_id, source_name, vendor, authority_level, content_type,
                   title, url, detected_at, published_at, summary, fingerprint, state, trace_json
            FROM items
            WHERE fingerprint LIKE ?
            ORDER BY id
            """,
            (f"{prefix}%",),
        ).fetchall()
        return [_stored_item_from_row(row) for row in rows]


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
