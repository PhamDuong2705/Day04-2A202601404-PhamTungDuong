from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from tools._shared import domain, err


def _normalized_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def audit_citations(
    items: list[dict[str, Any]] | None = None,
    require_summary: bool = True,
    deduplicate: bool = True,
) -> dict[str, Any]:
    """Validate and normalize research items before digest formatting."""

    try:
        valid_items: list[dict[str, Any]] = []
        rejected_items: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for index, raw_item in enumerate(items or []):
            if not isinstance(raw_item, dict):
                rejected_items.append({
                    "index": index,
                    "item": raw_item,
                    "reasons": ["item_must_be_an_object"],
                })
                continue

            item = dict(raw_item)
            reasons: list[str] = []
            notes: list[str] = []
            url = _normalized_url(str(item.get("url") or ""))
            title = str(item.get("title") or "").strip()
            summary = str(item.get("summary") or "").strip()
            source = str(item.get("source") or "").strip()

            if not url:
                reasons.append("missing_or_invalid_url")
            elif deduplicate and url in seen_urls:
                reasons.append("duplicate_url")

            if not title:
                reasons.append("missing_title")
            if require_summary and not summary:
                reasons.append("missing_summary")

            if url and not source:
                source = domain(url)
                if source:
                    notes.append("source_inferred_from_url")
            if not source:
                reasons.append("missing_source")

            if reasons:
                rejected_items.append({
                    "index": index,
                    "item": item,
                    "reasons": reasons,
                })
                issues.append({"index": index, "status": "rejected", "reasons": reasons})
                continue

            seen_urls.add(url)
            item.update({
                "title": title,
                "summary": summary,
                "url": url,
                "source": source,
            })
            valid_items.append(item)
            if notes:
                issues.append({"index": index, "status": "accepted", "notes": notes})

        return {
            "tool": "citation_audit",
            "items": valid_items,
            "rejected_items": rejected_items,
            "issues": issues,
            "input_count": len(items or []),
            "valid_count": len(valid_items),
            "rejected_count": len(rejected_items),
            "all_cited": bool(valid_items) and not rejected_items,
        }
    except Exception as exc:
        return err("citation_audit", exc)
