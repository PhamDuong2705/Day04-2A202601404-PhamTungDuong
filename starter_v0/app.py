"""
AI News Digest — Streamlit UI
Reuses run_model_tool_loop from chat.py for the agent loop.
Displays: user request, final response, tool trace (name, args, result/error, round),
provider/model/version. Saves transcripts.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

# ── Project imports ──────────────────────────────────────────────────────────
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import build_artifact_version, artifact_version_dict
from chat import run_model_tool_loop, trim_history, write_transcript

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
RUNS_DIR = ROOT / "runs"

load_lab_env(ROOT)

# ── Helpers ──────────────────────────────────────────────────────────────────

PROVIDER_CHOICES = ["openrouter", "openai", "anthropic", "gemini"]
VERSION_CHOICES = ["v0", "v1", "v2", "v3"]

TOOL_ICONS = {
    "clarify": "❓",
    "timeline": "📋",
    "social_search": "🐦",
    "lookup": "🔍",
    "fetch": "🌐",
    "format": "📝",
    "send": "📤",
    "policy": "📑",
    "papers": "🎓",
    "paper_text": "📄",
    "citation_audit": "✅",
}

STATUS_COLORS = {
    "answered": "#4ade80",
    "waiting_for_user": "#facc15",
    "max_tool_rounds": "#f87171",
    "provider_error": "#ef4444",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return slug.strip("_") or "run"


def json_pretty(obj: Any, max_chars: int | None = None) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n...<truncated>"
    return text


def list_run_files() -> list[Path]:
    if not RUNS_DIR.exists():
        return []
    return sorted(RUNS_DIR.glob("*.json"), reverse=True)


def list_transcript_files() -> list[Path]:
    if not TRANSCRIPTS_DIR.exists():
        return []
    return sorted(TRANSCRIPTS_DIR.glob("*.transcript.json"), reverse=True)


# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI News Digest Agent",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Global ─────────────────────────────────── */
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f4f6f8;
    --bg-card: rgba(255, 255, 255, 0.95);
    --bg-glass: rgba(0, 0, 0, 0.03);
    --border-glass: rgba(0, 0, 0, 0.08);
    --accent-primary: #6c63ff;
    --accent-secondary: #00d4aa;
    --accent-warning: #f59e0b;
    --accent-error: #ef4444;
    --accent-success: #10b981;
    --text-primary: #111111;
    --text-secondary: #4b5563;
    --text-muted: #6b7280;
    --gradient-primary: linear-gradient(135deg, #6c63ff 0%, #00d4aa 100%);
    --gradient-card: linear-gradient(145deg, rgba(108,99,255,0.05) 0%, rgba(0,212,170,0.03) 100%);
    --shadow-glow: 0 4px 20px rgba(0, 0, 0, 0.06);
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    font-family: 'Inter', sans-serif !important;
    background-color: var(--bg-secondary) !important;
    color: var(--text-primary) !important;
}

[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid var(--border-glass) !important;
}

/* ── Global Text Colors (Sidebar + Main) ──── */
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stAppViewContainer"] .stMarkdown h1,
[data-testid="stAppViewContainer"] .stMarkdown h2,
[data-testid="stAppViewContainer"] .stMarkdown h3,
[data-testid="stAppViewContainer"] .stMarkdown p,
[data-testid="stAppViewContainer"] .stMarkdown li,
[data-testid="stAppViewContainer"] .stMarkdown strong {
    color: var(--text-primary) !important;
}

[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown li,
[data-testid="stSidebar"] .stMarkdown span,
[data-testid="stSidebar"] .stMarkdown code,
[data-testid="stSidebar"] .stMarkdown strong {
    color: var(--text-secondary) !important;
}

label,
.stSelectbox label,
.stSlider label,
.stTextInput label,
.stRadio label,
[data-testid="stWidgetLabel"] {
    color: var(--text-primary) !important;
}

.stRadio div[role="radiogroup"] label span,
.stRadio div[role="radiogroup"] label p {
    color: var(--text-secondary) !important;
}

.stSelectbox div[data-baseweb="select"] span,
.stSelectbox div[data-baseweb="select"] div {
    color: var(--text-primary) !important;
}

.stTextInput input,
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input {
    color: var(--text-primary) !important;
    background: #ffffff !important;
    border-color: rgba(0,0,0,0.15) !important;
    caret-color: var(--accent-primary) !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: var(--text-muted) !important;
}

[data-testid="stChatInput"] {
    border-color: rgba(108,99,255,0.3) !important;
    background: #ffffff !important;
}

.stSlider div[data-baseweb="slider"] div {
    color: var(--text-primary) !important;
}

.stAlert p,
.stSuccess p {
    color: inherit !important;
}

p strong {
    color: var(--text-primary) !important;
}

code {
    color: var(--accent-primary) !important;
    background: rgba(108,99,255,0.08) !important;
}

/* Dropdown menu items */
div[data-baseweb="popover"] li,
div[data-baseweb="popover"] div[role="option"] {
    color: var(--text-primary) !important;
}

/* Expander headers */
.streamlit-expanderHeader p,
.streamlit-expanderHeader span,
details summary span {
    color: var(--text-primary) !important;
}


/* ── Hero header ────────────────────────────── */
.hero-header {
    background: var(--gradient-card);
    border: 1px solid var(--border-glass);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
    backdrop-filter: blur(12px);
    box-shadow: var(--shadow-glow);
}
.hero-header h1 {
    background: var(--gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    font-size: 2rem;
    margin: 0 0 6px 0;
    letter-spacing: -0.5px;
}
.hero-header p {
    color: var(--text-primary);
    margin: 0;
    font-size: 0.95rem;
}

/* ── Info bar ────────────────────────────────── */
.info-bar {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 20px;
}
.info-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-card);
    border: 1px solid var(--border-glass);
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 0.8rem;
    color: var(--text-secondary);
    box-shadow: 0 2px 10px rgba(0,0,0,0.02);
}
.info-chip .chip-icon {
    font-size: 0.9rem;
}
.info-chip .chip-value {
    color: var(--accent-primary);
    font-weight: 600;
}

/* ── Chat bubbles ────────────────────────────── */
.chat-user {
    background: #ffffff;
    border: 1px solid rgba(108,99,255,0.2);
    border-radius: 16px 16px 4px 16px;
    padding: 16px 20px;
    margin: 8px 0;
    max-width: 85%;
    margin-left: auto;
    box-shadow: 0 2px 15px rgba(108,99,255,0.05);
}
.chat-user .chat-label {
    font-size: 0.7rem;
    color: var(--accent-primary);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}
.chat-user .chat-text {
    color: var(--text-primary);
    font-size: 0.95rem;
    line-height: 1.6;
}

.chat-agent {
    background: var(--bg-card);
    border: 1px solid var(--border-glass);
    border-radius: 16px 16px 16px 4px;
    padding: 16px 20px;
    margin: 8px 0;
    max-width: 85%;
    box-shadow: var(--shadow-glow);
}
.chat-agent .chat-label {
    font-size: 0.7rem;
    color: var(--accent-secondary);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}
.chat-agent .chat-text {
    color: var(--text-primary);
    font-size: 0.95rem;
    line-height: 1.6;
}

/* ── Tool trace card ─────────────────────────── */
.tool-card {
    background: #ffffff;
    border: 1px solid var(--border-glass);
    border-radius: 12px;
    padding: 14px 18px;
    margin: 6px 0;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}
.tool-card:hover {
    border-color: rgba(108,99,255,0.4);
    box-shadow: 0 4px 15px rgba(108,99,255,0.1);
}
.tool-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}
.tool-icon {
    font-size: 1.2rem;
}
.tool-name {
    font-weight: 700;
    color: var(--accent-primary);
    font-size: 0.9rem;
    font-family: 'SF Mono', 'Fira Code', monospace;
}
.tool-round {
    background: rgba(108,99,255,0.1);
    color: var(--accent-primary);
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 0.7rem;
    font-weight: 600;
    margin-left: auto;
}
.tool-status-ok {
    background: rgba(16,185,129,0.1);
    color: var(--accent-success);
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 0.7rem;
    font-weight: 600;
}
.tool-status-err {
    background: rgba(239,68,68,0.1);
    color: var(--accent-error);
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 0.7rem;
    font-weight: 600;
}

/* ── Status badge ────────────────────────────── */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.75rem;
    font-weight: 600;
}
.status-answered { background: rgba(16,185,129,0.1); color: var(--accent-success); }
.status-waiting  { background: rgba(245,158,11,0.1); color: var(--accent-warning); }
.status-error    { background: rgba(239,68,68,0.1); color: var(--accent-error); }

/* ── Metric card ─────────────────────────────── */
.metric-card {
    background: #ffffff;
    border: 1px solid var(--border-glass);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 4px 15px rgba(0,0,0,0.03);
}
.metric-value {
    font-size: 1.6rem;
    font-weight: 800;
    background: var(--gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.metric-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Run viewer card ─────────────────────────── */
.run-card {
    background: var(--gradient-card);
    border: 1px solid var(--border-glass);
    border-radius: 12px;
    padding: 16px 20px;
    margin: 8px 0;
    box-shadow: 0 4px 15px rgba(0,0,0,0.03);
}

/* ── Scrollbar ───────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(108,99,255,0.2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(108,99,255,0.4); }

/* ── Expander style ──────────────────────────── */
.streamlit-expanderHeader {
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}

/* ── Sidebar separator ───────────────────────── */
.sidebar-sep {
    border: none;
    border-top: 1px solid var(--border-glass);
    margin: 16px 0;
}
</style>
""", unsafe_allow_html=True)



# ── Session state init ───────────────────────────────────────────────────────

def init_state():
    defaults = {
        "messages": [],            # Chat history [{role, content}]
        "turn_records": [],        # Full turn records for transcript
        "turn_index": 0,
        "transcript_id": None,
        "transcript_path": None,
        "transcript": None,
        "provider_name": "openrouter",
        "model_name": None,
        "version": "v2",
        "agent_ready": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_state()


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Cấu hình Agent")

    provider_name = "openai"
    st.session_state.provider_name = provider_name

    model_override = "gpt-4o-mini"

    version = st.selectbox(
        "Artifact Version",
        VERSION_CHOICES,
        index=VERSION_CHOICES.index(st.session_state.version),
        help="Version của system_prompt + tools.yaml",
    )
    st.session_state.version = version

    max_rounds = st.slider("Max tool rounds", 1, 8, 4, help="Số vòng tool tối đa mỗi turn")
    history_window = st.slider("History window", 1, 10, 5, help="Số cặp user/assistant giữ trong context")

    st.markdown('<hr class="sidebar-sep">', unsafe_allow_html=True)

    # ── Init / reset button ──
    col_init, col_reset = st.columns(2)
    with col_init:
        init_clicked = st.button("🚀 Khởi tạo", use_container_width=True)
    with col_reset:
        reset_clicked = st.button("🔄 Reset", use_container_width=True, type="secondary")

    if reset_clicked:
        for key in ["messages", "turn_records", "turn_index", "transcript_id",
                     "transcript_path", "transcript", "agent_ready"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    if init_clicked:
        try:
            with st.spinner("Đang khởi tạo agent..."):
                provider = make_provider(provider_name)
                system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
                tools_path = ARTIFACTS_DIR / "tools.yaml"
                system_prompt = system_prompt_path.read_text(encoding="utf-8")
                tool_declarations = load_tool_declarations(tools_path)
                openai_tools = to_openai_tools(tool_declarations)
                selected_model = model_override or getattr(provider, "default_model", None)
                artifact_version = build_artifact_version(version, system_prompt_path, tools_path)

                timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
                transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), "ui", timestamp])
                transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"

                transcript = {
                    "transcript_id": transcript_id,
                    **artifact_version_dict(artifact_version),
                    "provider": provider_name,
                    "model": selected_model,
                    "system_prompt": str(system_prompt_path),
                    "tools": str(tools_path),
                    "history_window": history_window,
                    "max_tool_rounds": max_rounds,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "turns": [],
                }

                # Store in session
                st.session_state.provider_obj = provider
                st.session_state.system_prompt = system_prompt
                st.session_state.openai_tools = openai_tools
                st.session_state.selected_model = selected_model
                st.session_state.model_name = selected_model
                st.session_state.artifact_version = artifact_version
                st.session_state.max_rounds = max_rounds
                st.session_state.history_window = history_window
                st.session_state.transcript_id = transcript_id
                st.session_state.transcript_path = transcript_path
                st.session_state.transcript = transcript
                st.session_state.messages = []
                st.session_state.turn_records = []
                st.session_state.turn_index = 0
                st.session_state.agent_ready = True

            st.success(f"✅ Agent sẵn sàng — {artifact_version.artifact_version}")
        except Exception as exc:
            st.error(f"❌ Lỗi khởi tạo: {exc}")

    st.markdown('<hr class="sidebar-sep">', unsafe_allow_html=True)

    # ── Sidebar info ──
    if st.session_state.agent_ready:
        av = st.session_state.artifact_version
        st.markdown(f"""
**Trạng thái:** 🟢 Đang hoạt động
- **Provider:** `{st.session_state.provider_name}`
- **Model:** `{st.session_state.model_name}`
- **Version:** `{av.version}`
- **Artifact:** `{av.artifact_version[:30]}...`
- **Transcript:** `{st.session_state.transcript_id[:25]}...`
""")
    else:
        st.info("Nhấn **🚀 Khởi tạo** để bắt đầu chat.")

    st.markdown('<hr class="sidebar-sep">', unsafe_allow_html=True)

    # ── Sidebar navigation ──
    st.markdown("### 📂 Xem dữ liệu")
    sidebar_page = st.radio(
        "Chuyển trang",
        ["💬 Chat", "📊 Run Viewer", "📜 Transcript Viewer"],
        label_visibility="collapsed",
    )


# ── Main content ─────────────────────────────────────────────────────────────

# Hero header
st.markdown("""
<div class="hero-header">
    <h1>📰 AI News Digest Agent</h1>
    <p>Research Agent — Tìm tin, đọc nguồn và tạo bản tin có trích dẫn (lookup → fetch → format)</p>
</div>
""", unsafe_allow_html=True)


# ── PAGE: Chat ───────────────────────────────────────────────────────────────

if sidebar_page == "💬 Chat":

    # Info bar
    if st.session_state.agent_ready:
        av = st.session_state.artifact_version
        st.markdown(f"""
<div class="info-bar">
    <span class="info-chip"><span class="chip-icon">🤖</span> Provider: <span class="chip-value">{st.session_state.provider_name}</span></span>
    <span class="info-chip"><span class="chip-icon">🧠</span> Model: <span class="chip-value">{st.session_state.model_name or 'default'}</span></span>
    <span class="info-chip"><span class="chip-icon">📌</span> Version: <span class="chip-value">{av.version}</span></span>
    <span class="info-chip"><span class="chip-icon">🔗</span> Rounds: <span class="chip-value">{st.session_state.max_rounds}</span></span>
    <span class="info-chip"><span class="chip-icon">💬</span> Turns: <span class="chip-value">{st.session_state.turn_index}</span></span>
</div>
""", unsafe_allow_html=True)

    # ── Render chat history ──
    for turn in st.session_state.turn_records:
        # User message
        st.markdown(f"""
<div class="chat-user">
    <div class="chat-label">👤 You</div>
    <div class="chat-text">{turn['user']}</div>
</div>
""", unsafe_allow_html=True)

        # Tool trace
        status = turn.get("status", "")
        status_class = "status-answered" if status == "answered" else "status-waiting" if status == "waiting_for_user" else "status-error"
        status_icon = "✅" if status == "answered" else "⏳" if status == "waiting_for_user" else "⚠️"

        for rnd in turn.get("rounds", []):
            round_idx = rnd.get("round", "?")
            for tool_evt in rnd.get("tool_results", []):
                tool_name = tool_evt.get("tool", "unknown")
                tool_args = tool_evt.get("args", {})
                tool_result = tool_evt.get("result", {})
                icon = TOOL_ICONS.get(tool_name, "[T]")
                has_error = isinstance(tool_result, dict) and "error" in tool_result

                status_html = f'<span class="tool-status-err">ERROR</span>' if has_error else f'<span class="tool-status-ok">OK</span>'

                st.markdown(f"""
<div class="tool-card">
    <div class="tool-header">
        <span class="tool-icon">{icon}</span>
        <span class="tool-name">{tool_name}</span>
        {status_html}
        <span class="tool-round">Round {round_idx}</span>
    </div>
</div>
""", unsafe_allow_html=True)

                with st.expander(f"📎 {tool_name} — chi tiết args & result", expanded=False):
                    col_args, col_result = st.columns(2)
                    with col_args:
                        st.markdown("**Arguments:**")
                        st.code(json_pretty(tool_args, max_chars=2000), language="json")
                    with col_result:
                        st.markdown("**Result:**")
                        result_str = json_pretty(tool_result, max_chars=3000)
                        if has_error:
                            st.error(result_str)
                        else:
                            st.code(result_str, language="json")

        # Agent response
        agent_text = turn.get("assistant_text", "")
        if agent_text:
            st.markdown(f"""
<div class="chat-agent">
    <div class="chat-label">🤖 Agent <span class="status-badge {status_class}">{status_icon} {status}</span></div>
    <div class="chat-text">{agent_text}</div>
</div>
""", unsafe_allow_html=True)

    # ── Chat input ──
    if not st.session_state.agent_ready:
        st.info("👈 Vui lòng cấu hình và nhấn **🚀 Khởi tạo** ở sidebar trước khi chat.")
    else:
        user_input = st.chat_input("Nhập yêu cầu nghiên cứu... (ví dụ: Tin AI hôm nay có gì nổi bật?)")

        if user_input:
            st.session_state.turn_index += 1
            turn_idx = st.session_state.turn_index

            # Build messages with history
            history_pairs = []
            for prev_turn in st.session_state.turn_records:
                history_pairs.append({"role": "user", "content": prev_turn["user"]})
                history_pairs.append({"role": "assistant", "content": prev_turn.get("assistant_text", "")})

            trimmed = trim_history(history_pairs, st.session_state.history_window)

            messages = [
                {"role": "system", "content": st.session_state.system_prompt},
                *trimmed,
                {"role": "user", "content": user_input},
            ]

            turn_record = {
                "turn_index": turn_idx,
                "started_at": now_iso(),
                "user": user_input,
                "status": "started",
                "assistant_text": None,
                "rounds": [],
                "tool_events": [],
            }

            with st.spinner(f"🔄 Agent đang xử lý... (turn #{turn_idx})"):
                try:
                    result = run_model_tool_loop(
                        provider=st.session_state.provider_obj,
                        messages=messages,
                        tools=st.session_state.openai_tools,
                        model=st.session_state.selected_model if hasattr(st.session_state, "selected_model") else None,
                        max_tool_rounds=st.session_state.max_rounds,
                    )
                    turn_record.update(result)
                except Exception as exc:
                    turn_record.update({
                        "status": "provider_error",
                        "error": f"{type(exc).__name__}: {str(exc)}",
                        "assistant_text": f"❌ Lỗi: {type(exc).__name__}: {str(exc)}",
                        "rounds": [],
                        "tool_events": [],
                    })

            turn_record["ended_at"] = now_iso()
            st.session_state.turn_records.append(turn_record)

            # Save transcript
            transcript = st.session_state.transcript
            transcript["turns"].append(turn_record)
            write_transcript(st.session_state.transcript_path, transcript)

            st.rerun()


# ── PAGE: Run Viewer ─────────────────────────────────────────────────────────

elif sidebar_page == "📊 Run Viewer":
    st.markdown("### 📊 Run Viewer — Xem kết quả eval")

    run_files = list_run_files()
    if not run_files:
        st.info("Chưa có file run nào trong `runs/`. Hãy chạy `run_eval.py` trước.")
    else:
        selected_run = st.selectbox(
            "Chọn run file",
            run_files,
            format_func=lambda p: p.name,
        )

        if selected_run:
            run_data = json.loads(selected_run.read_text(encoding="utf-8"))

            # Summary metrics
            summary = run_data.get("summary", {})
            cols = st.columns(5)
            metric_items = [
                ("📈", "Case Accuracy", f"{summary.get('case_accuracy', 0):.0%}"),
                ("🎯", "Routing Acc", f"{summary.get('tool_routing_accuracy', 0):.0%}"),
                ("📋", "Arg Accuracy", f"{summary.get('argument_accuracy', 0):.0%}"),
                ("📊", "Measured", f"{summary.get('measured_cases', 0)}/{summary.get('total_cases', 0)}"),
                ("⚠️", "Errors", f"{summary.get('provider_error_cases', 0)}"),
            ]
            for col, (icon, label, value) in zip(cols, metric_items):
                with col:
                    st.markdown(f"""
<div class="metric-card">
    <div class="metric-value">{icon} {value}</div>
    <div class="metric-label">{label}</div>
</div>
""", unsafe_allow_html=True)

            st.markdown("")

            # Run info
            with st.expander("📋 Run metadata", expanded=False):
                info_cols = st.columns(3)
                with info_cols[0]:
                    st.markdown(f"**Version:** `{run_data.get('version', '?')}`")
                    st.markdown(f"**Suite:** `{run_data.get('suite', '?')}`")
                with info_cols[1]:
                    st.markdown(f"**Provider:** `{run_data.get('provider', '?')}`")
                    st.markdown(f"**Model:** `{run_data.get('model', '?')}`")
                with info_cols[2]:
                    st.markdown(f"**Artifact:** `{run_data.get('artifact_version', '?')[:35]}...`")
                    st.markdown(f"**Generated:** `{run_data.get('generated_at', '?')}`")

            # Results table
            st.markdown("#### Kết quả từng case")

            for item in run_data.get("results", []):
                result = item.get("result", {})
                passed = result.get("passed", False)
                case_id = item.get("id", "?")
                failure_type = result.get("failure_type") or ""
                is_multi = item.get("is_multiturn", False)

                icon = "✅" if passed else "❌"
                multi_badge = " 🔄" if is_multi else ""

                with st.expander(f"{icon} {case_id}{multi_badge} — {failure_type}", expanded=not passed):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Expected:**")
                        st.code(json_pretty(item.get("expect", {})), language="json")
                    with c2:
                        st.markdown("**Actual tool calls:**")
                        st.code(json_pretty(result.get("actual_tool_calls", [])), language="json")

                    if result.get("failures"):
                        st.error("**Failures:** " + " | ".join(result["failures"]))

                    if item.get("tool_results"):
                        st.markdown("**Tool results:**")
                        st.code(json_pretty(item["tool_results"], max_chars=3000), language="json")

            # Failure breakdown
            if summary.get("failure_counts"):
                st.markdown("#### Failure Breakdown")
                fc = summary["failure_counts"]
                for ftype, count in sorted(fc.items(), key=lambda x: -x[1]):
                    st.markdown(f"- **{ftype}:** {count}")


# ── PAGE: Transcript Viewer ──────────────────────────────────────────────────

elif sidebar_page == "📜 Transcript Viewer":
    st.markdown("### 📜 Transcript Viewer")

    transcript_files = list_transcript_files()
    if not transcript_files:
        st.info("Chưa có transcript. Hãy chat hoặc chạy `chat.py` trước.")
    else:
        selected_ts = st.selectbox(
            "Chọn transcript",
            transcript_files,
            format_func=lambda p: p.name,
        )

        if selected_ts:
            ts_data = json.loads(selected_ts.read_text(encoding="utf-8"))

            with st.expander("📋 Transcript metadata", expanded=False):
                meta_cols = st.columns(3)
                with meta_cols[0]:
                    st.markdown(f"**ID:** `{ts_data.get('transcript_id', '?')[:30]}...`")
                    st.markdown(f"**Version:** `{ts_data.get('version', '?')}`")
                with meta_cols[1]:
                    st.markdown(f"**Provider:** `{ts_data.get('provider', '?')}`")
                    st.markdown(f"**Model:** `{ts_data.get('model', '?')}`")
                with meta_cols[2]:
                    st.markdown(f"**Created:** `{ts_data.get('created_at', '?')}`")
                    st.markdown(f"**Turns:** `{len(ts_data.get('turns', []))}`")

            for turn in ts_data.get("turns", []):
                user_text = turn.get("user", "")
                agent_text = turn.get("assistant_text", "")
                status = turn.get("status", "")

                st.markdown(f"""
<div class="chat-user">
    <div class="chat-label">👤 You — Turn {turn.get('turn_index', '?')}</div>
    <div class="chat-text">{user_text}</div>
</div>
""", unsafe_allow_html=True)

                for rnd in turn.get("rounds", []):
                    round_idx = rnd.get("round", "?")
                    for tool_evt in rnd.get("tool_results", []):
                        tool_name = tool_evt.get("tool", "unknown")
                        tool_args = tool_evt.get("args", {})
                        tool_result = tool_evt.get("result", {})
                        icon = TOOL_ICONS.get(tool_name, "[T]")
                        has_error = isinstance(tool_result, dict) and "error" in tool_result
                        status_html = f'<span class="tool-status-err">ERROR</span>' if has_error else f'<span class="tool-status-ok">OK</span>'

                        st.markdown(f"""
<div class="tool-card">
    <div class="tool-header">
        <span class="tool-icon">{icon}</span>
        <span class="tool-name">{tool_name}</span>
        {status_html}
        <span class="tool-round">Round {round_idx}</span>
    </div>
</div>
""", unsafe_allow_html=True)

                        with st.expander(f"📎 {tool_name} — args & result"):
                            st.code(json_pretty({"args": tool_args, "result": tool_result}, max_chars=4000), language="json")

                if agent_text:
                    status_class = "status-answered" if status == "answered" else "status-waiting" if status == "waiting_for_user" else "status-error"
                    st.markdown(f"""
<div class="chat-agent">
    <div class="chat-label">🤖 Agent <span class="status-badge {status_class}">{status}</span></div>
    <div class="chat-text">{agent_text}</div>
</div>
""", unsafe_allow_html=True)

            # Raw JSON
            with st.expander("🔍 Raw JSON"):
                st.code(json_pretty(ts_data, max_chars=10000), language="json")
