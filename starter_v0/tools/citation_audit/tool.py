"""Tool `citation_audit` — kiểm tra và làm sạch danh sách nguồn trước khi format.

Vị trí trong workflow AI News Digest::

    lookup / social_search / timeline / fetch   (thu thập)
                    |
                    v
              citation_audit                    (làm sạch)  <-- file này
                    |
                    v
                  format                        (trình bày)

Tool này chạy hoàn toàn cục bộ: không gọi mạng, không đọc biến môi trường,
không cần API key. Nhờ vậy nó không có đường làm rò rỉ credential ra output,
run JSON hay transcript.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from tools._shared import domain, err


def _normalized_url(value: str) -> str:
    """Chuẩn hoá một URL để vừa kiểm tra tính hợp lệ, vừa so sánh trùng lặp.

    Hai URL viết khác nhau nhưng trỏ tới cùng một trang cần cho ra cùng một
    chuỗi, nếu không bước khử trùng lặp ở `audit_citations` sẽ bỏ sót.

    Args:
        value: URL thô lấy từ item, có thể rỗng hoặc sai định dạng.

    Returns:
        URL đã chuẩn hoá, hoặc chuỗi rỗng `""` nếu URL không dùng được.
        Trả `""` thay vì raise để hàm gọi tự phân loại lý do loại bỏ, giữ cho
        một item hỏng không làm hỏng cả lô.

    Quy tắc chuẩn hoá đang áp dụng:
        - Chỉ chấp nhận scheme `http` / `https`; thiếu host cũng bị loại.
          Chặn luôn các scheme nguy hiểm như `javascript:` hay `file:`.
        - Hạ thấp scheme và host, vì tên miền không phân biệt hoa thường.
        - Bỏ dấu `/` ở cuối path, để `/tin-ai` và `/tin-ai/` là một.
        - Bỏ fragment `#...`, vì nó chỉ là vị trí cuộn trang, không đổi nội dung.

    Giới hạn đã biết:
        Query string được giữ nguyên. Do đó hai link chỉ khác tham số theo dõi
        (`?utm_source=newsletter`) vẫn bị coi là hai nguồn khác nhau và lọt qua
        bước khử trùng lặp. Nguồn tin tức thường gắn sẵn `utm_*`, nên đây là
        điểm cần cân nhắc mở rộng.
    """

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
    """Lọc danh sách item đã thu thập, tách phần dùng được khỏi phần lỗi.

    Model gọi tool này sau khi đã có item từ các tool thu thập, và trước khi gọi
    `format`. Khoá `items` trong giá trị trả về được thiết kế để đưa thẳng sang
    `format` mà không cần biến đổi thêm.

    Args:
        items: Danh sách item cần kiểm tra. Mỗi item là dict với các khoá quen
            thuộc `title`, `url`, `source`, `summary`, `section`. Nhận `None`
            hoặc danh sách rỗng mà không lỗi, để lượt gọi đầu tiên của model
            không bị crash khi chưa có dữ liệu.
        require_summary: Bật thì item thiếu `summary` bị loại. Tắt khi người
            dùng chỉ cần danh sách link, chưa cần nội dung tóm tắt.
        deduplicate: Bật thì item có URL trùng với item hợp lệ trước đó bị loại.
            Tắt khi người dùng muốn giữ nguyên toàn bộ danh sách gốc.

    Returns:
        Dict gồm:
            - `tool`: tên tool, để đọc log biết ai tạo ra kết quả này.
            - `items`: các item đã hợp lệ và chuẩn hoá, dùng cho `format`.
            - `rejected_items`: item bị loại, mỗi phần tử giữ `index` gốc,
              `item` nguyên bản và `reasons`. Giữ lại thay vì vứt đi để model
              biết cần bổ sung gì, ví dụ thiếu URL thì đi `fetch` thêm.
            - `issues`: nhật ký theo từng item, gồm cả trường hợp được nhận
              nhưng có chỉnh sửa, ví dụ `source` được suy ra từ URL.
            - `input_count`, `valid_count`, `rejected_count`: số liệu để đối
              chiếu nhanh, khỏi phải đếm lại danh sách.
            - `all_cited`: True khi có ít nhất một item và không item nào bị
              loại. Dùng như tín hiệu một chạm cho câu hỏi "bản tin này đã đủ
              trích dẫn chưa".
        Nếu có ngoại lệ, trả về dict lỗi theo đúng chuẩn của `err()` để agent
        loop xử lý giống mọi tool khác.

    Các lý do loại bỏ có thể xuất hiện trong `reasons`:
        - `item_must_be_an_object`: phần tử không phải dict. Model đôi khi trả
          thẳng một chuỗi, cần chặn trước khi gọi `.get()` lên nó.
        - `missing_or_invalid_url`: URL rỗng, sai scheme hoặc thiếu host.
        - `duplicate_url`: URL trùng item hợp lệ đã gặp trước đó.
        - `missing_title`: thiếu tiêu đề.
        - `missing_summary`: thiếu tóm tắt, chỉ áp dụng khi `require_summary`.
        - `missing_source`: không có tên nguồn và cũng không suy ra được từ URL.

    Ghi chú thiết kế:
        - Item bị loại không dừng vòng lặp. Một lô 10 tin có 2 tin hỏng vẫn trả
          về 8 tin dùng được, thay vì hỏng cả lô.
        - Mỗi item được thu thập đủ mọi lý do lỗi rồi mới loại, không thoát ở
          lỗi đầu tiên. Người dùng thấy một lần toàn bộ vấn đề của item đó.
        - Chỉ URL của item hợp lệ mới được ghi vào tập đã gặp. Nhờ vậy một item
          hỏng không vô tình chiếm chỗ, khiến bản sao hợp lệ sau đó bị loại oan.
        - Hàm không sửa dict gốc mà làm việc trên bản sao, tránh tác dụng phụ
          lên dữ liệu mà tool trước đó đang giữ.
    """

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
