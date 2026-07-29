from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, domain


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
SOCIAL_DOMAINS = ["x.com", "twitter.com"]


def _positive_limit(value: int, default: int = 5) -> int:
    try:
        return max(1, min(int(value or default), 20))
    except (TypeError, ValueError):
        return default


def _search_once(
    *,
    key: str,
    query: str,
    limit: int,
    time_range: str | None,
    constrain_domains: bool,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {
        "query": query,
        "topic": "general",
        "max_results": limit,
        "search_depth": "basic",
    }
    if time_range:
        body["time_range"] = time_range
    if constrain_domains:
        body["include_domains"] = SOCIAL_DOMAINS

    response = requests.post(
        TAVILY_SEARCH_URL,
        json=body,
        headers={"Authorization": f"Bearer {key}"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("results", [])


def search_social_web(
    *,
    query: str,
    limit: int = 5,
    time_range: str | None = "month",
) -> list[dict[str, Any]]:
    """Search Tavily's live web index for public X/Twitter posts."""

    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("Missing TAVILY_API_KEY env var")

    safe_limit = _positive_limit(limit)
    raw_items = _search_once(
        key=key,
        query=query,
        limit=safe_limit,
        time_range=time_range,
        constrain_domains=True,
    )

    # Some Tavily indexes do not return constrained X results for a narrow
    # recency window. Retry once without the window, while keeping the domains.
    if not raw_items and time_range:
        raw_items = _search_once(
            key=key,
            query=query,
            limit=safe_limit,
            time_range=None,
            constrain_domains=True,
        )

    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for raw in raw_items:
        url = str(raw.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title = str(raw.get("title") or "").strip()
        summary = str(raw.get("content") or "").strip()
        items.append({
            "title": title or summary[:120],
            "summary": summary,
            "url": url,
            "source": domain(url) or "x.com",
            "date": raw.get("published_date"),
            "score": raw.get("score"),
            "provider": "tavily_social_fallback",
        })
    return items[:safe_limit]
