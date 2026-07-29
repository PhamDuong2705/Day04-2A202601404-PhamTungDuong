from __future__ import annotations

from typing import Any

from tools._shared import err
from tools._tavily_social import search_social_web


def get_user_tweets(screenname: str = "", limit: int = 5) -> dict[str, Any]:
    try:
        normalized = (screenname or "").strip().lstrip("@")
        if not normalized:
            raise ValueError("screenname is required")
        requested_limit = max(1, int(limit or 5))
        query = (
            f'public X posts from the official @{normalized} account '
            f'site:x.com/{normalized}/status'
        )
        candidates = search_social_web(
            query=query,
            limit=max(10, requested_limit * 2),
            time_range=None,
        )
        expected_paths = (
            f"x.com/{normalized.lower()}/status/",
            f"twitter.com/{normalized.lower()}/status/",
        )
        items = [
            item
            for item in candidates
            if any(path in str(item.get("url") or "").lower() for path in expected_paths)
        ][:requested_limit]
        return {
            "tool": "get_user_tweets",
            "screenname": normalized,
            "provider": "tavily_social_fallback",
            "items": items,
        }
    except Exception as exc:
        return err("get_user_tweets", exc)

