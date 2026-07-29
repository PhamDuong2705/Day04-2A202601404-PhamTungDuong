from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import (
    initial_tool_choice_for,
    now_iso,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
SYSTEM_PROMPT_PATH = ARTIFACTS_DIR / "system_prompt.md"
TOOLS_PATH = ARTIFACTS_DIR / "tools.yaml"
load_lab_env(ROOT)

PROVIDER_ENV = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
SENSITIVE_ENV_NAMES = [
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "RAPIDAPI_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]


st.set_page_config(
    page_title="AI News Digest",
    page_icon="🗞️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp {
        background:
          radial-gradient(circle at 82% 8%, rgba(73, 88, 255, 0.12), transparent 28rem),
          radial-gradient(circle at 12% 18%, rgba(0, 184, 148, 0.10), transparent 24rem),
          #f7f8fc;
      }
      [data-testid="stSidebar"] {
        background: #101426;
      }
      [data-testid="stSidebar"] * {
        color: #eef1ff;
      }
      [data-testid="stSidebar"] .stButton button {
        border: 1px solid rgba(255,255,255,0.18);
        background: rgba(255,255,255,0.07);
      }
      .hero {
        padding: 1.4rem 1.5rem;
        border: 1px solid rgba(33, 41, 89, 0.10);
        border-radius: 1.25rem;
        background: rgba(255, 255, 255, 0.84);
        box-shadow: 0 18px 48px rgba(30, 40, 90, 0.08);
        margin-bottom: 1rem;
      }
      .hero-kicker {
        color: #5360d9;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
      }
      .hero h1 {
        color: #171b35;
        font-size: clamp(2rem, 4vw, 3.4rem);
        line-height: 1.02;
        margin: 0;
      }
      .hero p {
        color: #596079;
        font-size: 1.02rem;
        max-width: 54rem;
        margin: 0.7rem 0 0;
      }
      .status-chip {
        display: inline-block;
        padding: 0.35rem 0.62rem;
        border-radius: 999px;
        background: #e9ecff;
        color: #3e49bd;
        font-size: 0.78rem;
        font-weight: 700;
        margin: 0.15rem 0.2rem 0.15rem 0;
      }
      [data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.78);
        border: 1px solid rgba(33,41,89,0.08);
        border-radius: 1rem;
        padding: 0.35rem 0.65rem;
      }
      [data-testid="stExpander"] {
        border-color: rgba(33,41,89,0.12);
        background: rgba(255,255,255,0.62);
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret_values() -> list[str]:
    return [
        value
        for name in SENSITIVE_ENV_NAMES
        if (value := os.getenv(name)) and len(value) >= 6
    ]


def _redact_text(value: str) -> str:
    redacted = value
    for secret in _secret_values():
        redacted = redacted.replace(secret, "[REDACTED]")
    return re.sub(
        r"(?i)\b(api[_-]?key|authorization|access[_-]?token|bot[_-]?token|password|secret)"
        r"(\s*[=:]\s*)([^\s,;]+)",
        r"\1\2[REDACTED]",
        redacted,
    )


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {
                "api_key",
                "authorization",
                "access_token",
                "bot_token",
                "password",
                "secret",
                "telegram_bot_token",
            } or lowered.endswith("_api_key"):
                output[key] = "[REDACTED]"
            else:
                output[key] = redact(item)
        return output
    return value


def json_text(value: Any, *, max_chars: int = 8000) -> str:
    text = json.dumps(redact(value), ensure_ascii=False, indent=2, default=str)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...<truncated in UI; full result is saved in transcript>"
    return text


def new_transcript(
    *,
    provider_name: str,
    model_name: str | None,
    version_label: str,
    history_window: int,
    max_tool_rounds: int,
    artifact: Any,
) -> tuple[dict[str, Any], Path]:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([
        safe_slug(version_label),
        safe_slug(provider_name),
        "streamlit",
        timestamp,
    ])
    path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    transcript = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact),
        "provider": provider_name,
        "model": model_name,
        "surface": "streamlit",
        "system_prompt": str(SYSTEM_PROMPT_PATH),
        "tools": str(TOOLS_PATH),
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }
    write_transcript(path, transcript)
    return transcript, path


def start_session(
    *,
    config_key: str,
    provider_name: str,
    model_name: str | None,
    version_label: str,
    history_window: int,
    max_tool_rounds: int,
    artifact: Any,
) -> None:
    transcript, transcript_path = new_transcript(
        provider_name=provider_name,
        model_name=model_name,
        version_label=version_label,
        history_window=history_window,
        max_tool_rounds=max_tool_rounds,
        artifact=artifact,
    )
    st.session_state.config_key = config_key
    st.session_state.ui_turns = []
    st.session_state.agent_history = []
    st.session_state.transcript = transcript
    st.session_state.transcript_path = str(transcript_path)


def render_trace(turn: dict[str, Any]) -> None:
    tool_events = turn.get("tool_events") or []
    rounds = turn.get("rounds") or []
    if not rounds:
        return

    label = f"Tool trace · {len(tool_events)} call{'s' if len(tool_events) != 1 else ''}"
    with st.expander(label, expanded=bool(tool_events)):
        for round_record in rounds:
            st.markdown(f"**Round {round_record.get('round', '?')}**")
            assistant_text = round_record.get("assistant_text")
            if assistant_text:
                st.caption(_redact_text(str(assistant_text)))

            calls = round_record.get("tool_calls") or []
            results = round_record.get("tool_results") or []
            if not calls:
                if tool_events:
                    st.success("Round tổng hợp câu trả lời từ kết quả tool; không có tool call mới.")
                else:
                    st.info("Model trả lời trực tiếp; yêu cầu này không cần tool.")
                continue

            for index, call in enumerate(calls):
                tool_name = call.get("name", "unknown")
                st.markdown(f"`{tool_name}`")
                left, right = st.columns(2)
                with left:
                    st.caption("Arguments")
                    st.code(json_text(call.get("args") or {}), language="json")
                with right:
                    st.caption("Result")
                    result = results[index].get("result") if index < len(results) else None
                    if isinstance(result, dict) and result.get("error"):
                        st.error(f"{result.get('error')}: {_redact_text(str(result.get('message') or ''))}")
                    else:
                        st.code(json_text(result), language="json")


def render_turn(turn: dict[str, Any]) -> None:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        if turn.get("status") == "provider_error":
            st.error(turn.get("assistant_text") or "Provider không phản hồi.")
        else:
            st.markdown(turn.get("assistant_text") or "_Không có nội dung trả lời._")
        render_trace(turn)


system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
tool_declarations = load_tool_declarations(TOOLS_PATH)
openai_tools = to_openai_tools(tool_declarations)

with st.sidebar:
    st.markdown("## Cấu hình demo")
    provider_name = st.selectbox(
        "Provider",
        ["openrouter", "openai", "anthropic", "gemini"],
        index=0,
    )
    model_input = st.text_input(
        "Model override",
        value="",
        placeholder="Để trống để dùng model mặc định",
    ).strip()
    version_label = st.text_input("Artifact version", value="v3").strip() or "v3"
    history_window = st.slider("History window", min_value=1, max_value=10, value=5)
    max_tool_rounds = st.slider("Max tool rounds", min_value=1, max_value=8, value=5)

provider = make_provider(provider_name)
selected_model = model_input or getattr(provider, "default_model", None)
artifact = build_artifact_version(version_label, SYSTEM_PROMPT_PATH, TOOLS_PATH)
config_key = json.dumps(
    {
        "provider": provider_name,
        "model": selected_model,
        "version": version_label,
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "artifact_version": artifact.artifact_version,
    },
    sort_keys=True,
)

if st.session_state.get("config_key") != config_key:
    start_session(
        config_key=config_key,
        provider_name=provider_name,
        model_name=selected_model,
        version_label=version_label,
        history_window=history_window,
        max_tool_rounds=max_tool_rounds,
        artifact=artifact,
    )

with st.sidebar:
    key_ready = bool(os.getenv(PROVIDER_ENV[provider_name]))
    st.markdown("---")
    st.markdown("### Runtime")
    st.markdown(
        f"<span class='status-chip'>{'API key ready' if key_ready else 'Missing API key'}</span>"
        f"<span class='status-chip'>{len(tool_declarations)} tools</span>",
        unsafe_allow_html=True,
    )
    st.caption(f"Model: {selected_model or 'provider default'}")
    st.caption(f"Artifact: {artifact.artifact_version}")
    st.caption(f"Transcript: {Path(st.session_state.transcript_path).name}")

    if st.button("Bắt đầu phiên mới", use_container_width=True):
        start_session(
            config_key=config_key,
            provider_name=provider_name,
            model_name=selected_model,
            version_label=version_label,
            history_window=history_window,
            max_tool_rounds=max_tool_rounds,
            artifact=artifact,
        )
        st.rerun()

    transcript_download = json.dumps(
        redact(st.session_state.transcript),
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    st.download_button(
        "Tải transcript JSON",
        data=transcript_download,
        file_name=Path(st.session_state.transcript_path).name,
        mime="application/json",
        use_container_width=True,
    )

    st.markdown("---")
    st.markdown("### Câu thử nhanh")
    st.caption("Tạo bản tin gồm 5 tin AI nổi bật hôm nay, có trích dẫn nguồn.")
    st.caption("Đọc nguồn này và tóm tắt cho digest: https://example.com")
    st.caption("Kiểm tra trùng URL trong danh sách nguồn trước khi format.")

st.markdown(
    """
    <section class="hero">
      <div class="hero-kicker">Research agent · evidence-first</div>
      <h1>AI News Digest</h1>
      <p>Tìm tin, đọc nguồn, kiểm tra trích dẫn và tạo bản tin có thể kiểm chứng.
      Mỗi lượt đều lưu trace và transcript để đối chiếu giữa các artifact version.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

metric_columns = st.columns(4)
metric_columns[0].metric("Provider", provider_name)
metric_columns[1].metric("Version", version_label)
metric_columns[2].metric("Declared tools", len(tool_declarations))
metric_columns[3].metric("Turns", len(st.session_state.ui_turns))

if not key_ready:
    st.warning(f"Thiếu `{PROVIDER_ENV[provider_name]}` trong `.env`; chat sẽ chưa gọi được model.")

for saved_turn in st.session_state.ui_turns:
    render_turn(saved_turn)

user_text = st.chat_input("Bạn muốn tạo AI News Digest về chủ đề nào?")
if user_text:
    turn_index = len(st.session_state.ui_turns) + 1
    with st.chat_message("user"):
        st.markdown(user_text)

    model_messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.agent_history, history_window),
        {"role": "user", "content": user_text},
    ]
    turn_record: dict[str, Any] = {
        "turn_index": turn_index,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    with st.chat_message("assistant"):
        try:
            with st.status("Agent đang nghiên cứu và kiểm tra nguồn…", expanded=False) as status:
                result = run_model_tool_loop(
                    provider=provider,
                    messages=model_messages,
                    tools=openai_tools,
                    model=model_input or None,
                    max_tool_rounds=max_tool_rounds,
                    initial_tool_choice=initial_tool_choice_for(user_text),
                )
                safe_result = redact(result)
                turn_record.update(safe_result)
                status_label = {
                    "answered": "Hoàn tất câu trả lời",
                    "waiting_for_user": "Đang chờ bạn bổ sung thông tin",
                    "max_tool_rounds": "Đã chạm giới hạn tool rounds",
                }.get(result.get("status"), "Hoàn tất lượt chạy")
                status.update(label=status_label, state="complete")

            assistant_text = str(turn_record.get("assistant_text") or "")
            st.markdown(assistant_text or "_Không có nội dung trả lời._")
            render_trace(turn_record)
            st.session_state.agent_history.extend([
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": assistant_text},
            ])
        except Exception as exc:
            error_text = _redact_text(f"{type(exc).__name__}: {exc}")
            turn_record.update({
                "status": "provider_error",
                "assistant_text": f"Không thể gọi provider: {error_text}",
                "error": error_text,
            })
            st.error(turn_record["assistant_text"])

    turn_record["ended_at"] = now_iso()
    safe_turn = redact(turn_record)
    st.session_state.ui_turns.append(safe_turn)
    st.session_state.transcript["turns"].append(safe_turn)
    write_transcript(
        Path(st.session_state.transcript_path),
        st.session_state.transcript,
    )
    st.rerun()
