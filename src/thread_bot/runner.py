from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .ai import summarize_posts
from .config import AppConfig
from .filtering import classify_post, flatten_keyword_groups
from .storage import Storage
from .threads_api import ThreadsApi


def run_once(app_config: AppConfig) -> int:
    config = app_config.raw
    app_config.draft_dir.mkdir(parents=True, exist_ok=True)
    storage = Storage(app_config.db_path)
    try:
        api = ThreadsApi(config)
        keywords = flatten_keyword_groups(config["keywords"]["include_groups"])
        seen: set[str] = set()
        filtered = []
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=config["schedule"].get("lookback_minutes", 45))

        for keyword in keywords:
            for post in api.keyword_search(keyword):
                if post.id in seen:
                    continue
                seen.add(post.id)
                if post.timestamp and post.timestamp < cutoff:
                    continue
                storage.save_post(post)
                item = classify_post(post, config)
                if item:
                    storage.save_filtered(item)
                    filtered.append(item)

        tz = ZoneInfo(config["output"].get("timezone", "Asia/Seoul"))
        now_label = datetime.now(tz).strftime("%H:%M")
        content = summarize_posts(config, filtered, now_label)
        source_ids = [item.post.id for item in filtered]
        draft_id = storage.create_draft(content, source_ids)
        draft_path = app_config.draft_dir / f"draft_{draft_id:04d}.txt"
        draft_path.write_text(content, encoding="utf-8")
        return draft_id
    finally:
        storage.close()


def watch(app_config: AppConfig) -> None:
    interval = int(app_config.raw["schedule"]["interval_minutes"]) * 60
    while True:
        try:
            draft_id = run_once(app_config)
            print(f"created draft #{draft_id}")
        except Exception as exc:
            print(f"run failed: {exc}")
        time.sleep(interval)


def publish_draft(app_config: AppConfig, draft_id: int) -> str:
    storage = Storage(app_config.db_path)
    try:
        content = storage.get_draft(draft_id)
        api = ThreadsApi(app_config.raw)
        post_id = api.publish_text(content)
        storage.mark_posted(draft_id)
        return post_id
    finally:
        storage.close()
