from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import FilteredPost, ThreadPost


SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  username TEXT,
  timestamp TEXT,
  permalink TEXT,
  media_type TEXT,
  media_url TEXT,
  source_keyword TEXT,
  raw_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS filtered_posts (
  post_id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  gate TEXT,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content TEXT NOT NULL,
  source_post_ids TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL,
  posted_at TEXT
);
"""


class Storage:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def save_post(self, post: ThreadPost) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO posts
            (id, text, username, timestamp, permalink, media_type, media_url, source_keyword, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post.id,
                post.text,
                post.username,
                post.timestamp.isoformat() if post.timestamp else None,
                post.permalink,
                post.media_type,
                post.media_url,
                post.source_keyword,
                None,
                now,
            ),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def save_filtered(self, filtered: FilteredPost) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT OR REPLACE INTO filtered_posts
            (post_id, category, gate, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (filtered.post.id, filtered.category, filtered.gate, filtered.reason, now),
        )
        self.conn.commit()

    def create_draft(self, content: str, source_post_ids: list[str]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            """
            INSERT INTO drafts (content, source_post_ids, status, created_at)
            VALUES (?, ?, 'draft', ?)
            """,
            (content, ",".join(source_post_ids), now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_drafts(self, limit: int = 10) -> list[tuple[int, str, str]]:
        cur = self.conn.execute(
            """
            SELECT id, status, created_at FROM drafts
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
        return [(int(row[0]), str(row[1]), str(row[2])) for row in cur.fetchall()]

    def get_draft(self, draft_id: int) -> str:
        cur = self.conn.execute("SELECT content FROM drafts WHERE id = ?", (draft_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Draft not found: {draft_id}")
        return str(row[0])

    def mark_posted(self, draft_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE drafts SET status = 'posted', posted_at = ? WHERE id = ?",
            (now, draft_id),
        )
        self.conn.commit()
