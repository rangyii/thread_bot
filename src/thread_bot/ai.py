from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .models import FilteredPost


def summarize_posts(config: dict, posts: list[FilteredPost], now_label: str) -> str:
    if not posts:
        return build_empty_summary(config, now_label)

    provider = select_provider(config)
    prompt = build_prompt(config, posts, now_label)
    try:
        if provider == "openai":
            return call_openai(config, prompt)
        if provider == "gemini":
            return call_gemini(config, prompt)
    except Exception as exc:
        return build_heuristic_summary(config, posts, now_label, warning=f"AI 요약 실패: {exc}")
    return build_heuristic_summary(config, posts, now_label)


def select_provider(config: dict) -> str:
    provider = config["ai"].get("provider", "auto").lower()
    if provider != "auto":
        if provider == "openai" and not os.environ.get(config["ai"]["openai_api_key_env"]):
            if os.environ.get(config["ai"]["gemini_api_key_env"]):
                return "gemini"
        return provider
    if os.environ.get(config["ai"]["openai_api_key_env"]):
        return "openai"
    if os.environ.get(config["ai"]["gemini_api_key_env"]):
        return "gemini"
    return "none"


def build_prompt(config: dict, posts: list[FilteredPost], now_label: str) -> str:
    rows = []
    for idx, filtered in enumerate(posts, start=1):
        post = filtered.post
        rows.append(
            {
                "n": idx,
                "category": filtered.category,
                "gate": filtered.gate,
                "text": post.text,
                "time": post.timestamp.isoformat() if post.timestamp else None,
                "link": post.permalink,
                "media_type": post.media_type,
                "media_url": post.media_url,
            }
        )
    return f"""
너는 집회 현장 상황 제보를 짧고 보수적으로 정리하는 한국어 운영 보조자다.
출력은 Threads에 게시할 수 있는 완성 문안만 작성한다.

규칙:
- 제목은 "{config['template']['title'].format(time=now_label)}"로 시작한다.
- 섹션은 "증원 요청", "안전/혼잡", "게이트별 현황", "특이사항", "안내" 순서로 작성한다.
- 없는 섹션은 "확인된 제보 없음"이라고 짧게 쓴다.
- 같은 게이트에서 상충 제보가 있으면 "부족 가능성"을 우선 반영한다.
- 개인 신원, 연락처, 특정 개인을 식별할 수 있는 정보는 쓰지 않는다.
- 경찰 위치, 규모, 이동 제보는 현장 정보로 요약해도 된다.
- 확실하지 않은 내용을 단정하지 말고 "제보"라고 표현한다.
- 전체는 900자 이내로 쓴다.
- 마지막 안내에 다음 문구를 자연스럽게 포함한다:
  "{config['template']['notice']}"
  "{config['template']['special_note']}"

제보 목록 JSON:
{json.dumps(rows, ensure_ascii=False)}
""".strip()


def call_openai(config: dict, prompt: str) -> str:
    api_key = os.environ.get(config["ai"]["openai_api_key_env"], "")
    if not api_key:
        raise RuntimeError(f"Missing environment variable: {config['ai']['openai_api_key_env']}")
    body = json.dumps(
        {
            "model": config["ai"]["model"],
            "input": prompt,
            "max_output_tokens": 900,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("output_text"):
        return str(data["output_text"]).strip()
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("text"):
                chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks).strip()
    raise RuntimeError(f"Unexpected OpenAI response: {data}")


def call_gemini(config: dict, prompt: str) -> str:
    api_key = os.environ.get(config["ai"]["gemini_api_key_env"], "")
    if not api_key:
        raise RuntimeError(f"Missing environment variable: {config['ai']['gemini_api_key_env']}")
    model = config["ai"]["model"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(api_key)}"
    )
    body = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 900}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response: {data}") from exc


def build_empty_summary(config: dict, now_label: str) -> str:
    return "\n".join(
        [
            config["template"]["title"].format(time=now_label),
            "",
            "증원 요청: 확인된 제보 없음",
            "안전/혼잡: 확인된 제보 없음",
            "게이트별 현황: 확인된 제보 없음",
            "특이사항: 확인된 제보 없음",
            "",
            f"안내: {config['template']['notice']} {config['template']['special_note']}",
        ]
    )


def build_heuristic_summary(
    config: dict,
    posts: list[FilteredPost],
    now_label: str,
    warning: str | None = None,
) -> str:
    buckets = {"증원 요청": [], "안전/혼잡": [], "게이트별 현황": [], "특이사항": []}
    for filtered in posts:
        gate = f"{filtered.gate}: " if filtered.gate else ""
        text = " ".join(filtered.post.text.split())
        buckets.setdefault(filtered.category, []).append(f"- {gate}{text[:80]}")
    lines = [config["template"]["title"].format(time=now_label), ""]
    for section in ["증원 요청", "안전/혼잡", "게이트별 현황", "특이사항"]:
        lines.append(section)
        lines.extend(buckets.get(section)[:5] or ["- 확인된 제보 없음"])
        lines.append("")
    lines.append(f"안내: {config['template']['notice']} {config['template']['special_note']}")
    if warning:
        lines.append(f"운영 참고: {warning}")
    return "\n".join(lines).strip()
