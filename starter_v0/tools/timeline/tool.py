from __future__ import annotations

from typing import Any

from tools._shared import err
from tools._tavily_social import search_social_web


def get_user_tweets(screenname: str = "", limit: int = 5) -> dict[str, Any]:
    """Lấy các bài đăng gần đây của một tài khoản X/Twitter cụ thể.

    Đây là hàm đứng sau tool `timeline`. Điểm khác biệt với `social_search` là
    tool này đi theo **một tài khoản đã biết**, còn tool kia tìm theo từ khóa.
    Nếu người dùng không nói rõ tài khoản nào, model phải hỏi lại bằng `clarify`
    chứ không được đoán bừa một tên nổi tiếng.

    Args:
        screenname: Tên tài khoản, chấp nhận cả dạng có `@` lẫn không. Bắt buộc
            phải có; để rỗng sẽ bị coi là lỗi thay vì đoán thay người dùng.
        limit: Số bài muốn lấy.

    Returns:
        Dict gồm `tool`, `screenname` đã chuẩn hoá, `provider` và `items`.
        Trả lại `screenname` sau khi chuẩn hoá để khi đọc log biết chính xác
        tài khoản nào đã được truy vấn. Khi có lỗi, trả dict lỗi chuẩn `err()`.

    Raises:
        Không raise ra ngoài. Mọi ngoại lệ được `err()` bọc thành dict, vì agent
        loop trong `chat.py` mong tool luôn trả về dict chứ không ném lỗi.

    Ghi chú thiết kế:
        - Dữ liệu lấy qua Tavily thay cho RapidAPI; xem `tools/_tavily_social.py`
          để biết lý do và các đánh đổi.
        - Bỏ ký tự `@` đầu vì model có lúc truyền `@sama`, có lúc truyền `sama`,
          trong khi URL của X không chứa ký tự này.
        - Xin gấp đôi số item cần, tối thiểu 10, rồi mới lọc. Truy vấn theo từ
          khóa luôn kéo về cả bài của người khác nhắc tới tài khoản đó, nên phải
          dự phòng số dư trước khi lọc.
        - Bước lọc kiểm tra URL có đúng dạng `x.com/<tên>/status/` hay không.
          Đây là chỗ bảo đảm ta trả về bài **do tài khoản đó đăng**, chứ không
          phải bài nhắc đến họ — đúng ngữ nghĩa mà tên tool hứa hẹn.
        - So khớp ở dạng chữ thường vì tên tài khoản trên X không phân biệt
          hoa thường.
    """

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

