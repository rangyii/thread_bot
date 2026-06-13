from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any
from urllib.error import HTTPError

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

    def keyword_search(self, keyword: str, search_type: str | None = None) -> list[ThreadPost]:
        last_error: Exception | None = None
        for query_param in self.config["threads"].get("keyword_query_params", ["query", "q"]):
            try:
                return self._keyword_search_with_param(keyword, query_param, search_type)
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Keyword search failed for {keyword!r}: {last_error}") from last_error

    def me(self) -> dict[str, Any]:
        fields = self.config["threads"].get("me_fields", ["id", "username", "name"])
        return self._get_json(
            f"{self.base_url}/me",
            {
                "fields": ",".join(fields),
                "access_token": self.access_token,
            },
        )

    def my_threads(self, limit: int = 10) -> list[ThreadPost]:
        fields = self.config["threads"].get("fields", ["id", "text", "timestamp"])
        data = self._get_json(
            f"{self.base_url}/me/threads",
            {
                "fields": ",".join(fields),
                "limit": str(limit),
                "access_token": self.access_token,
            },
        )
        return [self._parse_post(row, "me/threads") for row in data.get("data", []) if row.get("id")]

    def _keyword_search_with_param(
        self,
        keyword: str,
        query_param: str,
        search_type: str | None = None,
    ) -> list[ThreadPost]:
        threads = self.config["threads"]
        params: dict[str, str] = {
            query_param: keyword,
            "access_token": self.access_token,
            "fields": ",".join(threads.get("fields", [])),
            "limit": str(threads.get("max_results_per_keyword", 25)),
        }
        effective_search_type = search_type or threads.get("search_type")
        if effective_search_type:
            params["search_type"] = effective_search_type
        data = self._get_json(f"{self.base_url}/keyword_search", params)
        rows = data.get("data", [])
        return [self._parse_post(row, keyword) for row in rows if row.get("id") and row.get("text")]

    def publish_text(self, text: str) -> str:
        create = self._post_json(
            f"{self.base_url}/me/threads",
            {"media_type": "TEXT", "text": text, "access_token": self.access_token},
        )
        creation_id = create.get("id")
        if not creation_id:
            raise RuntimeError(f"Threads create container did not return id: {create}")
        published = self._post_json(
            f"{self.base_url}/me/threads_publish",
            {"creation_id": creation_id, "access_token": self.access_token},
        )
        return str(published.get("id", creation_id))

    def resolve_user_id(self) -> str:
        if self.user_id and self.user_id.isdigit():
            return self.user_id
        me = self.me()
        resolved = str(me.get("id", ""))
        if not resolved:
            raise RuntimeError(f"Could not resolve Threads user id from /me response: {me}")
        if self.user_id and not self.user_id.isdigit():
            print(
                f"THREADS_USER_ID looks like a username ({self.user_id!r}); "
                f"using numeric /me id {resolved!r} for publishing."
            )
        return resolved

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            message = diagnose_threads_error(body)
            if message:
                raise RuntimeError(f"{message}\nHTTP {exc.code} from {redact_access_token(full_url)}: {body}") from exc
            raise RuntimeError(f"HTTP {exc.code} from {redact_access_token(full_url)}: {body}") from exc

    def _post_json(self, url: str, form: dict[str, str]) -> dict[str, Any]:
        body = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc

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


def redact_access_token(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [(key, "***" if key == "access_token" else value) for key, value in pairs]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment)
    )


def diagnose_threads_error(body: str) -> str | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    error = payload.get("error", {})
    if error.get("code") == 10 and "permission" in str(error.get("message", "")).lower():
        return "Threads API permission error: 현재 앱/토큰에 이 작업 권한이 없습니다."
    return None
