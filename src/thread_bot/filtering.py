from __future__ import annotations

import re

from .models import FilteredPost, ThreadPost


GATE_ALIASES = {
    "1-1": ["1-1", "1학년 1반"],
    "1-2": ["1-2", "1학년 2반"],
    "1-3": ["1-3", "1학년 3반"],
    "1-4": ["1-4", "1학년 4반"],
    "1-5": ["1-5", "1학년 5반"],
    "2-1": ["2-1", "2학년 1반"],
    "2-2": ["2-2", "2학년 2반"],
    "2-3": ["2-3", "2학년 3반"],
    "2-4": ["2-4", "2학년 4반"],
    "2-5": ["2-5", "2학년 5반"],
}


def flatten_keyword_groups(groups: list[list[str]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for keyword in group:
            normalized = keyword.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                out.append(normalized)
    return out


def flatten_blacklist_groups(groups: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for keyword in group.get("keywords", []):
            normalized = str(keyword).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                out.append(normalized)
    return out


def blacklist_keywords(config: dict) -> list[str]:
    keywords = config["keywords"]
    blacklist = flatten_blacklist_groups(keywords.get("blacklist_groups", []))
    legacy_exclude = [str(item) for item in keywords.get("exclude", [])]
    return flatten_keyword_groups([blacklist, legacy_exclude])


def has_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def contains_personal_info(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def detect_gate(text: str) -> str | None:
    for gate, aliases in GATE_ALIASES.items():
        if has_any(text, aliases):
            return gate
    return None


def classify_post(post: ThreadPost, config: dict) -> FilteredPost | None:
    text = post.text or ""
    keywords = config["keywords"]
    if has_any(text, blacklist_keywords(config)):
        return None
    if contains_personal_info(text, keywords.get("personal_info_patterns", [])):
        return None

    gate = detect_gate(text)
    lowered = text.lower()

    shortage_words = ["부족", "증원", "지원요청", "지원 요청", "선수교체", "교체"]
    safety_words = ["위험", "안전", "압박", "혼잡", "밀집", "사고", "부상", "충돌"]
    status_words = ["현황", "인원", "상황 공유", "대기", "줄", "입장"]
    incident_words = ["경찰", "특이", "제보", "이동", "통제", "막힘"]

    if any(word in lowered for word in shortage_words):
        return FilteredPost(post, "증원 요청", gate, "인원 부족 또는 지원 요청 표현 포함")
    if any(word in lowered for word in safety_words):
        return FilteredPost(post, "안전/혼잡", gate, "안전 문제 표현 포함")
    if gate and any(word in lowered for word in status_words):
        return FilteredPost(post, "게이트별 현황", gate, "게이트와 인원/상황 표현 포함")
    if any(word in lowered for word in incident_words):
        return FilteredPost(post, "특이사항", gate, "현장 특이사항 표현 포함")
    return None
