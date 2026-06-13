from __future__ import annotations

import argparse
import json
import os
import sys

from .config import load_config, save_config
from .keyword_manager import (
    add_blacklist_keyword,
    add_include_keyword,
    list_blacklist_keywords,
    list_include_keywords,
    remove_blacklist_keyword,
    remove_include_keyword,
)
from .oauth import (
    build_authorization_url,
    debug_access_token,
    exchange_code_for_short_lived_token,
    exchange_for_long_lived_token,
)
from .runner import publish_draft, run_once, watch
from .storage import Storage
from .threads_api import ThreadsApi


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="thread-bot")
    parser.add_argument("--config", default="config.json")
    sub = parser.add_subparsers(dest="command", required=True)

    run_once_parser = sub.add_parser("run-once")
    run_once_parser.add_argument("--verbose", action="store_true")
    run_once_parser.add_argument("--lookback-minutes", type=int)

    sub.add_parser("watch")

    list_parser = sub.add_parser("list-drafts")
    list_parser.add_argument("--limit", type=int, default=10)

    show_draft_parser = sub.add_parser("show-draft")
    show_draft_parser.add_argument("--draft-id", type=int, required=True)

    recent_posts_parser = sub.add_parser("recent-posts")
    recent_posts_parser.add_argument("--limit", type=int, default=20)

    search_test_parser = sub.add_parser("search-test")
    search_test_parser.add_argument("keyword")
    search_test_parser.add_argument("--search-type", choices=["TOP", "RECENT"])

    sub.add_parser("me-test")
    my_threads_parser = sub.add_parser("my-threads")
    my_threads_parser.add_argument("--limit", type=int, default=10)

    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("--draft-id", type=int, required=True)

    auth_url_parser = sub.add_parser("auth-url")
    auth_url_parser.add_argument("--redirect-uri", required=True)

    sub.add_parser("token-debug")

    token_parser = sub.add_parser("exchange-code")
    token_parser.add_argument("--code", required=True)
    token_parser.add_argument("--redirect-uri", required=True)
    token_parser.add_argument("--short-lived-only", action="store_true")

    keyword_parser = sub.add_parser("keywords")
    keyword_sub = keyword_parser.add_subparsers(dest="keyword_command", required=True)
    keyword_sub.add_parser("list")
    add_search = keyword_sub.add_parser("add-search")
    add_search.add_argument("keyword")
    add_search.add_argument("--group", type=int, default=1)
    remove_search = keyword_sub.add_parser("remove-search")
    remove_search.add_argument("keyword")
    add_blacklist = keyword_sub.add_parser("add-blacklist")
    add_blacklist.add_argument("keyword")
    add_blacklist.add_argument("--group-name", default="추가 블랙리스트")
    remove_blacklist = keyword_sub.add_parser("remove-blacklist")
    remove_blacklist.add_argument("keyword")

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "auth-url":
        return handle_auth_url(config.raw, args)
    if args.command == "token-debug":
        return handle_token_debug(config.raw)
    if args.command == "exchange-code":
        return handle_exchange_code(args)
    if args.command == "run-once":
        draft_id = run_once(config, verbose=args.verbose, lookback_minutes=args.lookback_minutes)
        print(f"created draft #{draft_id}: {config.draft_dir / f'draft_{draft_id:04d}.txt'}")
        return 0
    if args.command == "watch":
        watch(config)
        return 0
    if args.command == "list-drafts":
        return handle_list_drafts(config, args.limit)
    if args.command == "show-draft":
        return handle_show_draft(config, args.draft_id)
    if args.command == "recent-posts":
        return handle_recent_posts(config, args.limit)
    if args.command == "search-test":
        return handle_search_test(config.raw, args.keyword, args.search_type)
    if args.command == "me-test":
        api = ThreadsApi(config.raw)
        print(json_dumps(api.me()))
        return 0
    if args.command == "my-threads":
        return handle_my_threads(config.raw, args.limit)
    if args.command == "publish":
        post_id = publish_draft(config, args.draft_id)
        print(f"published Threads post: {post_id}")
        return 0
    if args.command == "keywords":
        return handle_keywords(config, args)
    return 1


def handle_auth_url(config: dict, args: argparse.Namespace) -> int:
    app_id_env = config["threads"].get("app_id_env", "THREADS_APP_ID")
    app_id = os.environ.get(app_id_env, "").strip()
    if not app_id:
        raise RuntimeError(f"Missing environment variable: {app_id_env}")
    scopes = config["threads"].get("scopes", [])
    print(build_authorization_url(app_id, args.redirect_uri, scopes))
    print("")
    print("requested scopes: " + ", ".join(scopes))
    return 0


def handle_token_debug(config: dict) -> int:
    token_env = config["threads"].get("access_token_env", "THREADS_ACCESS_TOKEN")
    token = os.environ.get(token_env, "").strip()
    if not token:
        raise RuntimeError(f"Missing environment variable: {token_env}")
    data = debug_access_token(token)
    payload = data.get("data", data)
    print(json_dumps(payload))
    scopes = payload.get("scopes") or payload.get("granular_scopes") or []
    print("")
    print("scopes:")
    if isinstance(scopes, list):
        for scope in scopes:
            print(f"- {scope}")
    else:
        print(scopes)
    return 0


def handle_exchange_code(args: argparse.Namespace) -> int:
    short_lived = exchange_code_for_short_lived_token(args.code, args.redirect_uri)
    result = short_lived if args.short_lived_only else exchange_for_long_lived_token(short_lived.access_token)
    print("THREADS_ACCESS_TOKEN=" + result.access_token)
    if result.user_id:
        print("THREADS_USER_ID=" + result.user_id)
    if result.expires_in:
        print(f"EXPIRES_IN_SECONDS={result.expires_in}")
    return 0


def handle_list_drafts(config, limit: int) -> int:
    storage = Storage(config.db_path)
    try:
        for draft_id, status, created_at in storage.list_drafts(limit):
            print(f"#{draft_id} {status} {created_at}")
    finally:
        storage.close()
    return 0


def handle_show_draft(config, draft_id: int) -> int:
    storage = Storage(config.db_path)
    try:
        print(storage.get_draft(draft_id))
    finally:
        storage.close()
    return 0


def handle_recent_posts(config, limit: int) -> int:
    storage = Storage(config.db_path)
    try:
        for post in storage.list_recent_posts(limit):
            print(
                f"- {post['timestamp'] or '-'} @{post['username'] or '-'} "
                f"keyword={post['source_keyword'] or '-'}"
            )
            print(f"  {post['permalink'] or post['id']}")
            print(f"  {post['text'][:180]}")
    finally:
        storage.close()
    return 0


def handle_search_test(config: dict, keyword: str, search_type: str | None) -> int:
    api = ThreadsApi(config)
    posts = api.keyword_search(keyword, search_type=search_type)
    print(f"found {len(posts)} posts")
    usernames = sorted({post.username for post in posts if post.username})
    if usernames:
        print("usernames: " + ", ".join(usernames[:20]))
    for post in posts[:5]:
        timestamp = post.timestamp.isoformat() if post.timestamp else "-"
        print(f"- {timestamp} {post.username or '-'} {post.permalink or post.id}")
        print(f"  {post.text[:140]}")
    return 0


def handle_my_threads(config: dict, limit: int) -> int:
    api = ThreadsApi(config)
    posts = api.my_threads(limit=limit)
    print(f"found {len(posts)} posts")
    for post in posts:
        timestamp = post.timestamp.isoformat() if post.timestamp else "-"
        print(f"- {timestamp} {post.permalink or post.id}")
        print(f"  {post.text[:180]}")
    return 0


def handle_keywords(config, args: argparse.Namespace) -> int:
    if args.keyword_command == "list":
        print("[search keywords]")
        for group_index, keyword in list_include_keywords(config.raw):
            print(f"group {group_index}: {keyword}")
        print("")
        print("[blacklist keywords]")
        for group_name, keyword in list_blacklist_keywords(config.raw):
            print(f"{group_name}: {keyword}")
        return 0
    if args.keyword_command == "add-search":
        changed = add_include_keyword(config.raw, args.keyword, args.group)
        save_config(config)
        print("added" if changed else "already exists")
        return 0
    if args.keyword_command == "remove-search":
        changed = remove_include_keyword(config.raw, args.keyword)
        save_config(config)
        print("removed" if changed else "not found")
        return 0
    if args.keyword_command == "add-blacklist":
        changed = add_blacklist_keyword(config.raw, args.keyword, args.group_name)
        save_config(config)
        print("added" if changed else "already exists")
        return 0
    if args.keyword_command == "remove-blacklist":
        changed = remove_blacklist_keyword(config.raw, args.keyword)
        save_config(config)
        print("removed" if changed else "not found")
        return 0
    return 1


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
