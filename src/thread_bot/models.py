from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ThreadPost:
    id: str
    text: str
    username: str | None = None
    timestamp: datetime | None = None
    permalink: str | None = None
    media_type: str | None = None
    media_url: str | None = None
    source_keyword: str | None = None
    raw: dict | None = field(default=None, repr=False)


@dataclass
class FilteredPost:
    post: ThreadPost
    category: str
    gate: str | None
    reason: str
