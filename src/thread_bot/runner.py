from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .ai import summarize_posts
from .config import AppConfig
from .filtering import classify_post, flatten_keyword_groups
from .storage import Storage
from .threads_api import ThreadsApi


def run_once(app_config: AppConfig, verbose: bool = False, lookback_minutes: int | None = None) -> int:
    config = app_config.raw
    app_config.draft_dir.mkdir(parents=True, exist_ok=True)
    storage = Storage(app_config.db_path)
    try:
        api = ThreadsApi(config)
        keywords = flatten_keyword_groups(config["keywords"]["include_groups"])
        seen: set[str] = set()
        filtered = []
        lookback = lookback_minutes if lookback_minutes is not None else config["schedule"].get("lookback_minutes", 45)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback)
        total_found = 0
        fresh_saved = 0

        for keyword in keywords:
            try:
                posts = api.keyword_search(keyword)
            except Exception as exc:
                print(f"keyword search skipped for {keyword!r}: {exc}")
                continue
            total_found += len(posts)
            keyword_fresh = 0
            keyword_filtered = 0
            for post in posts:
                if post.id in seen:
                    continue
                seen.add(post.id)
                if post.timestamp and post.timestamp < cutoff:
                    continue
                keyword_fresh += 1
                fresh_saved += 1
                storage.save_post(post)
                item = classify_post(post, config)
                if item:
                    keyword_filtered += 1
                    storage.save_filtered(item)
                    filtered.append(item)
            if verbose:
                print(
                    f"keyword={keyword!r} found={len(posts)} "
                    f"fresh_unique={keyword_fresh} filtered={keyword_filtered}"
                )

        tz = ZoneInfo(config["output"].get("timezone", "Asia/Seoul"))
        now_label = datetime.now(tz).strftime("%H:%M")
        if verbose:
            print(
                f"summary input: found={total_found}, fresh_unique_saved={fresh_saved}, "
                f"filtered_for_ai={len(filtered)}, lookback_minutes={lookback}"
            )
            if not filtered:
                print("AI summary skipped: no posts passed rule filters.")
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
