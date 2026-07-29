# Day 04 Lab v2 Report — AI News Digest Research Agent

## Team

- **Team:** AI News Digest Team
- **Phạm Tùng Dương — 2A202601404:** Agent, Prompt & Eval Lead
- **Hồ Lương An — 2A202601332:** UI, Demo & Report Lead
- **Bế Nguyễn Hà Sơn — 2A202601454:** Tool & API Lead
- **Provider/model:** OpenRouter / `openai/gpt-4o-mini`
- **Final artifact:** `v3+pd00b02dd7417+tae50b7488aab`

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

AI News Digest là research agent tìm tin mới, đọc nội dung nguồn, kiểm tra chất lượng trích dẫn và tạo bản tin Markdown bằng tiếng Việt. Agent cũng hỗ trợ tìm nội dung mạng xã hội, bài báo khoa học, hỏi lại khi thiếu input và yêu cầu xác nhận trước hành động gửi/đăng.

**Link dùng thử:** `http://localhost:8501`

Link trên dùng khi demo trực tiếp trên máy của nhóm. Nếu showdown yêu cầu thiết bị khác truy cập, nhóm cần tạo public tunnel tạm thời và thay URL này trước khi trình bày.

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `clarify` | Hỏi lại khi thiếu URL/handle và xin xác nhận trước hành động bên ngoài | Không |
| `lookup` | Tìm nguồn web theo chủ đề, loại tin và khoảng thời gian | Không |
| `fetch` | Đọc nội dung từ một URL cụ thể | Không |
| `citation_audit` | Loại URL lỗi/trùng, kiểm tra title, summary, source trước khi format | **Có** |
| `format` | Tạo digest Markdown từ các item đã nghiên cứu | Không |
| `timeline` | Lấy bài đăng gần đây của một tài khoản; dùng Tavily fallback | Không |
| `social_search` | Tìm bài đăng theo chủ đề; dùng Tavily fallback | Không |
| `papers` | Tìm bài báo khoa học | Không |
| `paper_text` | Đọc nội dung bài báo khoa học | Không |
| `policy` | Tra cứu policy nội bộ | Không |
| `send` | Gửi nội dung lên Telegram sau xác nhận rõ ràng | Không |

## A3. Câu hỏi mẫu để thử

1. `Tạo bản tin gồm 2 tin AI nổi bật hôm nay, có trích dẫn nguồn và trả lời bằng tiếng Việt.`
2. `Đọc và tóm tắt nguồn này cho AI News Digest: https://example.com`
3. `Tóm tắt bài viết này hộ mình` — agent phải hỏi URL bằng `clarify`.
4. `Tweet mới nhất của Sam Altman là gì?`
5. `Đăng bản tóm tắt này lên Telegram giúp mình` — agent phải hỏi xác nhận và chưa được tự gửi.

## A4. Kịch bản demo đã rehearse

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
| Tạo AI News Digest 2 tin hôm nay | `lookup → fetch ×2 → citation_audit → format` | v3 giữ tiếng Việt, đọc nguồn đầy đủ và format sau audit thay vì chỉ dùng snippet | `transcripts/v3_openrouter_streamlit_20260729T171321789993.transcript.json`, turn 1 |
| Thiếu URL rồi bổ sung | `clarify(response_type=text) → fetch(url=https://example.com)` | v0 đoán/gọi sai khi thiếu input; v3 dừng đúng boundary rồi dùng context lượt sau | Cùng transcript, turns 2–3 |
| Yêu cầu đăng Telegram | `clarify(response_type=yes_no)` và dừng trước `send` | v0 gọi `send` khi chưa xác nhận; v3 chặn side effect | Cùng transcript, turn 4 |
| So sánh chất lượng version | v0: 13/20 → v1: 17/20 → v2/v3: 20/20 | Cho thấy từng hypothesis thay đổi prompt/tool schema và được đo bằng run thật | `runs/v0_B_base_...json` đến `runs/v3_B_base_openrouter_20260729T171215653480.json` |

---

# PHẦN B — Chi tiết / Bằng chứng

Điều kiện metric của các run được dùng dưới đây đều hợp lệ: `provider_error_cases=0`, `measured_cases=total_cases`; final base có 18 tool events, final group có 9 tool events và không có tool-result error.

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis | Metric name | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| v0 | Baseline starter | Đo hành vi chưa tối ưu trước khi sửa | Base case accuracy | — | 0.65 | `runs/v0_B_base_openrouter_20260729T154345012573.json` |
| v1 | Thêm decision boundaries trong `system_prompt.md` | Không đoán input, không gửi khi chưa xác nhận và không gọi tool cho out-of-scope sẽ sửa routing | Base case accuracy | 0.65 | 0.85 | `runs/v1_B_base_openrouter_20260729T155535039498.json` |
| v2 | Làm rõ schema/description trong `tools.yaml`; thêm `citation_audit` | Required args và tool boundary rõ sẽ sửa lỗi argument/routing mà không tạo call thừa | Base case accuracy | 0.85 | 1.00 | `runs/v2_B_base_openrouter_20260729T160253278324.json` |
| v3 | Giữ ngôn ngữ người dùng; một lookup; flow digest bắt buộc; clarification dùng tool | Boundary chặt sẽ bỏ lookup dịch trùng, tạo digest có nguồn tiếng Việt và giữ hành vi multi-turn | Group case accuracy | 0.90 | 1.00 | `runs/v3_B_group_openrouter_20260729T171257620250.json` |

**Final v3 base:** 20/20, case/routing/argument/multi-turn accuracy đều `1.00`, xem `runs/v3_B_base_openrouter_20260729T171215653480.json`.

## B2. Failure analysis

| Case ID / Evidence | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| v0 `R03_web_news_routing` | Wrong argument | `lookup(query="AI news")` | Query giữ từ điều khiển `news` thay vì chủ đề ngắn `AI` | v1 prompt và v2 description quy định tách query/topic/timeframe |
| v0 `R08`, `R14` | Out of scope | `send` | Dùng tool cho toán/coding ngoài phạm vi | v1 quy định out-of-scope trả lời trực tiếp, không tool |
| v0 `R10`, `R11` | Missing info | `timeline` / `fetch` | Đoán handle/URL khi chưa được cung cấp | v1/v3 bắt buộc `clarify(response_type=text)` |
| v0 `R12` | Wrong boundary | `send` | Cố gửi Telegram khi chưa xác nhận | Bắt buộc `clarify(response_type=yes_no)` trước side effect |
| v1 `R13_parallel_web_and_tweets` | Wrong argument | `lookup + social_search` | `lookup` thiếu `topic=news` | v2 làm `topic` thành required và mô tả mapping rõ |
| v2 group `G06` | Extra tool call | `lookup("AI") + lookup("trí tuệ nhân tạo")` | Tách cùng intent thành hai truy vấn dịch trùng | v3 chỉ cho một lookup cho một research intent |
| Manual UI transcript | Execution error | Tool chưa ghi event | Console Windows không encode được tham số tiếng Việt | In diagnostic với `ensure_ascii=True`, restart một Streamlit server sạch |
| Manual live R11 | Missing tool event | Không tool | Model auto hỏi URL bằng text, không tạo trace `clarify` | Thêm prompt boundary và first-round routing guard cho research/external intent |

## B3. Team eval cases

File `data/eval_group.json` có đúng **10 case: 5 single-turn và 5 multi-turn**.

| Case ID | What It Tests | Expected Tool/Behavior | Final v3 |
|---|---|---|---|
| `G01_ai_news_today` | News query, timeframe và số nguồn | `lookup(query=AI, topic=news, timeframe=day, max_results=5)` | PASS |
| `G02_read_supplied_source` | Đọc URL đã cung cấp | `fetch(url=https://example.com)` | PASS |
| `G03_audit_sources_without_summary` | Loại URL trùng, không bắt buộc summary | `citation_audit(require_summary=false, deduplicate=true)` | PASS |
| `G04_format_audited_digest` | Format item đã audit | `format(template=daily_ai_vn)` | PASS |
| `G05_agent_capability_meta` | Câu hỏi meta | Không tool | PASS |
| `G06_multiturn_timeframe_and_count` | Mang timeframe/count qua nhiều lượt | Một `lookup`, week, 3 nguồn | PASS |
| `G07_multiturn_topic_time_correction` | Ưu tiên correction ở lượt mới | `lookup` với AI/day | PASS |
| `G08_multiturn_url_completion` | Nhận URL bổ sung ở lượt sau | `fetch` đúng URL | PASS |
| `G09_multiturn_audit_preferences` | Nhớ tùy chọn audit | `citation_audit(require_summary=false, deduplicate=true)` | PASS |
| `G10_multiturn_format_after_audit` | Chuyển từ audit sang trình bày | `format(template=daily_ai_vn)` | PASS |

Final group run: **10/10**, xem `runs/v3_B_group_openrouter_20260729T171257620250.json`.

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args chính | Transcript/Run | Outcome |
|---|---|---|---|---|
| Turn 1 — AI News Digest | `v3+pd00b02dd7417+tae50b7488aab` | `lookup(AI, news, day, 2) → fetch ×2 → citation_audit → format(daily_ai_vn)` | `transcripts/v3_openrouter_streamlit_20260729T171321789993.transcript.json` | `answered`; bản tin tiếng Việt có hai nguồn |
| Turns 2–3 — thiếu URL rồi bổ sung | Cùng v3 | `clarify(response_type=text) → fetch(https://example.com)` | Cùng transcript | `waiting_for_user → answered`; không đoán URL |
| Turn 4 — yêu cầu đăng Telegram | Cùng v3 | `clarify(response_type=yes_no)` | Cùng transcript | `waiting_for_user`; dừng an toàn trước `send` |
| Robocon tiếng Việt | v3 | `lookup(query="kết quả cuộc thi robocon Việt Nam", topic=news)` | `transcripts/v3_openrouter_streamlit_20260729T165030756375.transcript.json` | `answered`; xác nhận lỗi Unicode đã được xử lý |

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: tool mới đầu tiên — `citation_audit` | `tools/citation_audit/tool.py`, `tools/citation_audit/TOOL.md`, `artifacts/tools.yaml`, group G03/G09 | Validate URL/title/summary/source, suy ra source, loại URL trùng; deterministic và không cần API key | Không fact-check nội dung; phải chạy sau research/fetch và trước format |
| Optional built-in — `timeline`, `social_search` | Final base R01/R02; `tools/_tavily_social.py` | Tavily fallback hoạt động khi RapidAPI không khả dụng; hai case PASS, không tool error | Kết quả social qua web index có thể trễ; giữ provider label và URL nguồn |
| Optional built-in — `papers` | `transcripts/v3_openrouter_streamlit_20260729T165149393433.transcript.json`, turn 5 | Tìm được nghiên cứu theo chủ đề sinh học | Phụ thuộc arXiv/network; không tính là tool mới của nhóm |
| Bonus | Không claim | Nhóm tập trung hoàn thiện một tool mới bắt buộc và flow end-to-end | Không ghi nhận bonus khi chưa có tool mới bổ sung đủ điều kiện |

## B6. Reflection

- **Fix thuộc `system_prompt.md`:** missing-information boundary, confirmation trước side effect, trả lời cùng ngôn ngữ người dùng, một lookup cho một intent, workflow `lookup → fetch → citation_audit → format`, dùng `clarify` thay vì hỏi trực tiếp và canonical mapping `Sam Altman → sama`.
- **Fix thuộc `tools.yaml`:** phân biệt `timeline` với `social_search`, quy ước `lookup` query/topic/timeframe, required args cho `clarify`, giới hạn trách nhiệm của `fetch`, `format` và `citation_audit`.
- **Failure cần manual review:** G06 có routing tool đúng nhưng gọi lookup hai lần; UI ban đầu báo “model trả lời trực tiếp” ở round tổng hợp; lỗi Unicode xuất hiện trong console trước khi tool event được lưu. Các lỗi này không thể kết luận chỉ từ aggregate accuracy.
- **Cải tiến tiếp theo:** deploy URL ổn định, cache/retry cho API, lọc ngày xuất bản chặt hơn, đánh giá độ tin cậy giữa nhiều nguồn độc lập và thêm test UI tự động vào CI.

---

## Final gate

- [x] `artifacts/system_prompt.md` và `artifacts/tools.yaml`
- [x] `artifacts/version_log.csv` có v0, v1, v2, v3 và hash khớp run
- [x] Base eval v3: 20/20, không provider/tool error
- [x] Group eval v3: 10/10, đúng 5 single-turn + 5 multi-turn
- [x] Tool mới `citation_audit` có implementation, `TOOL.md`, registry và schema
- [x] Streamlit UI dùng chung `run_model_tool_loop`, hiển thị trace và lưu transcript
- [x] Transcript demo đủ normal, missing-info và confirmation boundary
- [x] `.env`, API key, `.venv`, cache và log server không được track
- [ ] Thay localhost bằng public URL nếu showdown yêu cầu máy khác truy cập
- [ ] Commit và push bản final sau khi nhóm xác nhận
