"""Lớp truy vấn bài đăng X/Twitter qua Tavily, thay cho RapidAPI.

Vì sao có file này:
    Hai tool `timeline` và `social_search` trong starter gọi RapidAPI
    (`twitter-api45`). API đó trả 403 nếu tài khoản chưa đăng ký gói, nên tool
    không chạy được. Thay vì để hai tool hỏng, ta lấy bài đăng công khai qua
    chỉ mục web của Tavily — dịch vụ mà tool `lookup` vốn đã dùng, nên không
    phát sinh thêm key.

Đánh đổi cần biết khi đọc kết quả:
    - Đây là dữ liệu chỉ mục web, không phải luồng thời gian thực. Bài mới đăng
      vài phút có thể chưa xuất hiện.
    - Không có số like, retweet, view. RapidAPI có, Tavily thì không.
    - Mọi item trả về đều gắn `provider: "tavily_social_fallback"` để khi đọc
      run JSON hay transcript, người chấm phân biệt được ngay đây là dữ liệu
      thay thế chứ không phải từ API mạng xã hội gốc.

Module này là chi tiết nội bộ, không đăng ký trong `TOOL_FUNCTIONS`. Model
không gọi trực tiếp; nó chỉ phục vụ hai tool nói trên.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, domain


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
SOCIAL_DOMAINS = ["x.com", "twitter.com"]


def _positive_limit(value: int, default: int = 5) -> int:
    """Ép `limit` do model truyền vào về một số nguyên an toàn.

    Model có thể truyền `0`, số âm, chuỗi, `None`, hoặc một số rất lớn. Bất kỳ
    giá trị nào trong số đó đưa thẳng sang Tavily đều gây lỗi hoặc tốn quota vô ích.

    Args:
        value: Giá trị `limit` thô, không đảm bảo kiểu.
        default: Giá trị dùng khi không ép kiểu được.

    Returns:
        Số nguyên trong khoảng 1 đến 20. Chặn dưới ở 1 vì gọi API mà xin 0 kết
        quả là vô nghĩa; chặn trên ở 20 để một lần gọi sai không đốt quota.
    """

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
    """Gọi Tavily đúng một lần và trả về mảng kết quả thô.

    Tách riêng thành hàm vì `search_social_web` cần gọi tối đa hai lần với tham
    số khác nhau. Hàm này cố tình không bắt ngoại lệ và không biến đổi dữ liệu,
    để phần quyết định thử lại và phần chuẩn hoá nằm gọn ở hàm gọi.

    Tham số dùng dạng keyword-only để chỗ gọi luôn đọc rõ nghĩa, tránh nhầm thứ
    tự giữa `limit` và `time_range`.

    Args:
        key: Tavily API key. Truyền vào thay vì tự đọc biến môi trường, để hàm
            gọi kiểm tra key thiếu một lần duy nhất.
        query: Câu truy vấn đã dựng sẵn.
        limit: Số kết quả tối đa, đã được `_positive_limit` làm sạch.
        time_range: Cửa sổ thời gian của Tavily, hoặc `None` để bỏ giới hạn.
        constrain_domains: Bật thì chỉ lấy kết quả thuộc `SOCIAL_DOMAINS`.

    Returns:
        Danh sách dict thô theo đúng định dạng Tavily trả về, chưa chuẩn hoá.

    Raises:
        requests.HTTPError: Khi Tavily trả mã lỗi. Để nguyên cho hàm gọi, cuối
            cùng sẽ được `err()` ở tầng tool bọc lại thành dict lỗi chuẩn.
    """

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
    """Tìm bài đăng X/Twitter công khai và trả về theo contract chung của tool.

    Đây là điểm vào duy nhất mà `timeline` và `social_search` sử dụng.

    Args:
        query: Câu truy vấn đã được tool gọi dựng sẵn, thường kèm `site:x.com`
            để thu hẹp phạm vi.
        limit: Số item mong muốn. Được làm sạch qua `_positive_limit`.
        time_range: Cửa sổ thời gian ban đầu. `None` nghĩa là không giới hạn.

    Returns:
        Danh sách item đã chuẩn hoá, mỗi item có `title`, `summary`, `url`,
        `source`, `date`, `score`, `provider`. Bộ khoá này khớp với thứ mà
        `format` và `citation_audit` mong đợi, nên kết quả đi thẳng vào workflow
        digest được.

    Raises:
        RuntimeError: Khi thiếu `TAVILY_API_KEY`. Báo lỗi sớm và rõ ràng thay vì
            để Tavily trả 401 khó đọc.

    Ghi chú thiết kế:
        - Có một lần thử lại: nếu lượt đầu bị bó cả theo domain lẫn theo thời
          gian mà không ra kết quả, hàm bỏ giới hạn thời gian và giữ nguyên
          giới hạn domain. Lý do là chỉ mục của Tavily với bài trên X thường
          thưa; bỏ cửa sổ thời gian đổi lấy độ phủ, nhưng vẫn không cho kết quả
          ngoài mạng xã hội lọt vào.
        - Khử trùng lặp theo URL nguyên văn ngay tại đây, vì Tavily có thể trả
          cùng một bài ở cả hai lượt gọi.
        - `title` rỗng thì lấy 120 ký tự đầu của nội dung. Bài đăng mạng xã hội
          thường không có tiêu đề, mà `format` lại cần một dòng để hiển thị.
        - Cắt danh sách ở `safe_limit` lần cuối, vì lượt thử lại có thể trả về
          nhiều hơn số item đã xin.
    """

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
