from __future__ import annotations


def list_include_keywords(config: dict) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for index, group in enumerate(config["keywords"].get("include_groups", []), start=1):
        rows.extend((index, keyword) for keyword in group)
    return rows


def list_blacklist_keywords(config: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for group in config["keywords"].setdefault("blacklist_groups", []):
        name = str(group.get("name", "미분류"))
        rows.extend((name, keyword) for keyword in group.get("keywords", []))
    return rows


def add_include_keyword(config: dict, keyword: str, group_index: int = 1) -> bool:
    groups = config["keywords"].setdefault("include_groups", [])
    while len(groups) < group_index:
        groups.append([])
    group = groups[group_index - 1]
    return add_unique(group, keyword)


def remove_include_keyword(config: dict, keyword: str) -> bool:
    removed = False
    for group in config["keywords"].get("include_groups", []):
        removed = remove_all(group, keyword) or removed
    return removed


def add_blacklist_keyword(config: dict, keyword: str, group_name: str = "추가 블랙리스트") -> bool:
    groups = config["keywords"].setdefault("blacklist_groups", [])
    group = find_or_create_blacklist_group(groups, group_name)
    return add_unique(group.setdefault("keywords", []), keyword)


def remove_blacklist_keyword(config: dict, keyword: str) -> bool:
    removed = False
    for group in config["keywords"].get("blacklist_groups", []):
        removed = remove_all(group.get("keywords", []), keyword) or removed
    return removed


def find_or_create_blacklist_group(groups: list[dict], name: str) -> dict:
    for group in groups:
        if group.get("name") == name:
            return group
    group = {"name": name, "keywords": []}
    groups.append(group)
    return group


def add_unique(items: list[str], keyword: str) -> bool:
    normalized = keyword.strip()
    if not normalized or normalized in items:
        return False
    items.append(normalized)
    return True


def remove_all(items: list[str], keyword: str) -> bool:
    before = len(items)
    items[:] = [item for item in items if item != keyword]
    return len(items) != before
