from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError


TOKEN_URL = "https://graph.threads.net/oauth/access_token"
LONG_LIVED_TOKEN_URL = "https://graph.threads.net/access_token"
AUTHORIZE_URL = "https://threads.net/oauth/authorize"
DEBUG_TOKEN_URLS = [
    "https://graph.facebook.com/debug_token",
    "https://graph.threads.net/debug_token",
]


@dataclass(frozen=True)
class TokenResult:
    access_token: str
    user_id: str | None
    expires_in: int | None
    raw: dict[str, Any]


def build_authorization_url(client_id: str, redirect_uri: str, scopes: list[str]) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": ",".join(scopes),
            "response_type": "code",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def debug_access_token(input_token: str) -> dict[str, Any]:
    app_id = require_env("THREADS_APP_ID")
    app_secret = require_env("THREADS_APP_SECRET")
    last_error: Exception | None = None
    for url in DEBUG_TOKEN_URLS:
        try:
            return get_json(
                url,
                {
                    "input_token": input_token,
                    "access_token": f"{app_id}|{app_secret}",
                },
            )
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not debug token with Meta debug_token endpoints: {last_error}") from last_error


def exchange_code_for_short_lived_token(code: str, redirect_uri: str) -> TokenResult:
    client_id = require_env("THREADS_APP_ID")
    client_secret = require_env("THREADS_APP_SECRET")
    data = post_form(
        TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        },
    )
    return parse_token_result(data)


def exchange_for_long_lived_token(short_lived_access_token: str) -> TokenResult:
    client_secret = require_env("THREADS_APP_SECRET")
    data = get_json(
        LONG_LIVED_TOKEN_URL,
        {
            "grant_type": "th_exchange_token",
            "client_secret": client_secret,
            "access_token": short_lived_access_token,
        },
    )
    return parse_token_result(data)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def post_form(url: str, form: dict[str, str]) -> dict[str, Any]:
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


def get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc


def parse_token_result(data: dict[str, Any]) -> TokenResult:
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"Token response did not include access_token: {data}")
    user_id = data.get("user_id")
    expires_in = data.get("expires_in")
    return TokenResult(
        access_token=str(token),
        user_id=str(user_id) if user_id is not None else None,
        expires_in=int(expires_in) if expires_in is not None else None,
        raw=data,
    )
