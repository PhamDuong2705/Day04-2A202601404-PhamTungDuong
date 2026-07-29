from __future__ import annotations

from typing import Any

from tools._shared import err
from tools._tavily_social import search_social_web


def search_tweets(query: str = "", search_type: str = "Latest", limit: int = 5) -> dict[str, Any]:
    """Tìm bài đăng X/Twitter công khai theo từ khóa.

    Đây là hàm đứng sau tool `social_search`. Dùng khi người dùng muốn biết
    "mọi người đang nói gì về X". Nếu họ chỉ đích danh một tài khoản thì phải
    dùng `timeline`, còn nếu cần nguồn tin chính thống thì dùng `lookup`.

    Args:
        query: Từ khóa cần tìm. Bắt buộc, để rỗng bị coi là lỗi.
        search_type: `"Latest"` ưu tiên bài mới, `"Top"` ưu tiên bài nổi bật.
            Giá trị khác bị từ chối thay vì âm thầm quay về mặc định, để lỗi
            routing của model hiện ra trong log chứ không bị che đi.
        limit: Số bài muốn lấy.

    Returns:
        Dict gồm `tool`, `query`, `search_type` đã chuẩn hoá, `provider` và
        `items`. Trả lại `search_type` để khi đọc run JSON biết nhánh nào đã
        chạy. Khi có lỗi, trả dict lỗi chuẩn `err()`.

    Raises:
        Không raise ra ngoài; mọi ngoại lệ được `err()` bọc lại thành dict.

    Ghi chú thiết kế:
        - `search_type` được chuẩn hoá bằng `.title()` nên `"latest"`, `"LATEST"`
          hay `"Latest"` đều nhận. Model không phải lúc nào cũng giữ đúng chữ hoa
          như khai báo trong `tools.yaml`.
        - Tavily không có khái niệm sắp xếp theo mới hay theo nổi bật, nên ý định
          đó được diễn đạt lại theo hai cách:
          thứ nhất, chèn từ `latest` hoặc `popular` vào câu truy vấn để tác động
          tới việc khớp ngữ nghĩa;
          thứ hai, đổi cửa sổ thời gian — `Latest` lấy trong một tháng để ưu tiên
          bài mới, `Top` mở rộng một năm vì bài nổi bật cần thời gian tích lũy độ
          phổ biến, bó hẹp một tháng sẽ loại mất chúng.
        - Riêng nhánh `Top` sắp xếp lại theo điểm liên quan của Tavily. Đây là
          xấp xỉ gần nhất cho khái niệm "nổi bật", vì dữ liệu không có lượt like
          hay retweet.
        - `float(... or 0)` xử lý trường hợp Tavily thiếu trường `score`, tránh
          làm hỏng cả lượt sắp xếp chỉ vì một item khuyết dữ liệu.
    """

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

