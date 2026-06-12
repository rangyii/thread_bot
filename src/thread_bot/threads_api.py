from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from .models import ThreadPost


class ThreadsApi:
    def __init__(self, config: dict):
        self.config = config
        threads = config["threads"]
        self.base_url = threads["base_url"].rstrip("/")
        self.access_token = os.environ.get(threads["access_token_env"], "")
        self.user_id = os.environ.get(threads["user_id_env"], "")
        if not self.access_token:
            raise RuntimeError(f"Missing environment variable: {threads['access_token_env']}")

    def keyword_search(self, keyword: str) -> list[ThreadPost]:
        last_error: Exception | None = None
        for query_param in self.config["threads"].get("keyword_query_params", ["query", "q"]):
            try:
                return self._keyword_search_with_param(keyword, query_param)
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Keyword search failed for {keyword!r}: {last_error}") from last_error

    def _keyword_search_with_param(self, keyword: str, query_param: str) -> list[ThreadPost]:
        threads = self.config["threads"]
        params: dict[str, str] = {
            query_param: keyword,
            "access_token": self.access_token,
            "fields": ",".join(threads.get("fields", [])),
            "limit": str(threads.get("max_results_per_keyword", 25)),
        }
        if threads.get("search_type"):
            params["search_type"] = threads["search_type"]
        data = self._get_json(f"{self.base_url}/keyword_search", params)
        rows = data.get("data", [])
        return [self._parse_post(row, keyword) for row in rows if row.get("id") and row.get("text")]

    def publish_text(self, text: str) -> str:
        if not self.user_id:
            raise RuntimeError(f"Missing environment variable: {self.config['threads']['user_id_env']}")
        create = self._post_json(
            f"{self.base_url}/{self.user_id}/threads",
            {"media_type": "TEXT", "text": text, "access_token": self.access_token},
        )
        creation_id = create.get("id")
        if not creation_id:
            raise RuntimeError(f"Threads create container did not return id: {create}")
        published = self._post_json(
            f"{self.base_url}/{self.user_id}/threads_publish",
            {"creation_id": creation_id, "access_token": self.access_token},
        )
        return str(published.get("id", creation_id))

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post_json(self, url: str, form: dict[str, str]) -> dict[str, Any]:
        body = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _parse_post(self, row: dict[str, Any], keyword: str) -> ThreadPost:
        timestamp = None
        if row.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            except ValueError:
                timestamp = None
        return ThreadPost(
            id=str(row["id"]),
            text=str(row.get("text", "")),
            username=row.get("username"),
            timestamp=timestamp,
            permalink=row.get("permalink"),
            media_type=row.get("media_type"),
            media_url=row.get("media_url"),
            source_keyword=keyword,
            raw=row,
        )
