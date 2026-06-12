from __future__ import annotations

import argparse
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
from .runner import publish_draft, run_once, watch
from .storage import Storage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="thread-bot")
    parser.add_argument("--config", default="config.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run-once")
    sub.add_parser("watch")
    list_parser = sub.add_parser("list-drafts")
    list_parser.add_argument("--limit", type=int, default=10)
    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("--draft-id", type=int, required=True)
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
    if args.command == "run-once":
        draft_id = run_once(config)
        print(f"created draft #{draft_id}: {config.draft_dir / f'draft_{draft_id:04d}.txt'}")
        return 0
    if args.command == "watch":
        watch(config)
        return 0
    if args.command == "list-drafts":
        storage = Storage(config.db_path)
        try:
            for draft_id, status, created_at in storage.list_drafts(args.limit):
                print(f"#{draft_id} {status} {created_at}")
        finally:
            storage.close()
        return 0
    if args.command == "publish":
        post_id = publish_draft(config, args.draft_id)
        print(f"published Threads post: {post_id}")
        return 0
    if args.command == "keywords":
        return handle_keywords(config, args)
    return 1


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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
