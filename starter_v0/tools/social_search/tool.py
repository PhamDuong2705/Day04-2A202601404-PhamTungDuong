from __future__ import annotations

from typing import Any

from tools._shared import err
from tools._tavily_social import search_social_web


def search_tweets(query: str = "", search_type: str = "Latest", limit: int = 5) -> dict[str, Any]:
    try:
        normalized_query = (query or "").strip()
        if not normalized_query:
            raise ValueError("query is required")
        normalized_type = (search_type or "Latest").strip().title()
        if normalized_type not in {"Latest", "Top"}:
            raise ValueError("search_type must be Latest or Top")

        intent = "latest" if normalized_type == "Latest" else "popular"
        social_query = f'{intent} public X posts about "{normalized_query}" site:x.com'
        items = search_social_web(
            query=social_query,
            limit=limit,
            time_range="month" if normalized_type == "Latest" else "year",
        )
        if normalized_type == "Top":
            items.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return {
            "tool": "search_tweets",
            "query": normalized_query,
            "search_type": normalized_type,
            "provider": "tavily_social_fallback",
            "items": items,
        }
    except Exception as exc:
        return err("search_tweets", exc)

