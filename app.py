import pandas as pd
import plotly.express as px
import streamlit as st

from config import (
    APP_TITLE,
    APP_SUBTITLE,
    RAW_EXCEL_FILE,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    OUTPUTS_DIR,
    CHARTS_DIR,
    REPORTS_DIR,
    EXPORTS_DIR,
    OPENAI_API_KEY,
    DEFAULT_MODEL_NAME,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_USE_TLS,
    MEMORY_PERSIST_PATH,
    MEMORY_MAX_TURNS,
)
from utils import (
    ensure_directories,
    file_exists,
    display_filter_value,
    display_value,
    build_executive_report_pdf,
    report_pdf_filename,
    smtp_configured,
    send_report_email,
)
from data_prep import build_data_model, get_data_overview
from memory import ConversationMemory
from llm_router import LLMRouter
from query_engine import QueryEngine
from llm_narrator import LLMNarrator
from insight_engine import InsightEngine


WEEK_ORDER = {
    "L8W": 0,
    "L7W": 1,
    "L6W": 2,
    "L5W": 3,
    "L4W": 4,
    "L3W": 5,
    "L2W": 6,
    "L1W": 7,
    "L0W": 8,
}


def initialize_project_folders() -> None:
    ensure_directories(
        [
            RAW_DATA_DIR,
            PROCESSED_DATA_DIR,
            OUTPUTS_DIR,
            CHARTS_DIR,
            REPORTS_DIR,
            EXPORTS_DIR,
        ]
    )


def initialize_session_objects(data_model: dict) -> None:
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationMemory(
            persist_path=MEMORY_PERSIST_PATH,
            max_turns=MEMORY_MAX_TURNS,
        )

    # Rebuild code-driven components on every rerun so Streamlit does not keep stale
    # class instances in session_state after code changes.
    st.session_state.router = LLMRouter(
        model_name=DEFAULT_MODEL_NAME,
        api_key=OPENAI_API_KEY,
    )

    st.session_state.query_engine = QueryEngine(
        metrics_df=data_model["metrics_long"],
        orders_df=data_model["orders_long"],
    )

    st.session_state.narrator = LLMNarrator(
        model_name=DEFAULT_MODEL_NAME,
        api_key=OPENAI_API_KEY,
    )

    st.session_state.insight_engine = InsightEngine(
        metrics_df=data_model["metrics_long"],
        orders_df=data_model["orders_long"],
    )

    st.session_state.executive_report = None

    if "last_parsed_intent" not in st.session_state:
        st.session_state.last_parsed_intent = None

    if "last_analytical_result" not in st.session_state:
        st.session_state.last_analytical_result = None

    if "last_executive_answer" not in st.session_state:
        st.session_state.last_executive_answer = None

    if "last_insights" not in st.session_state:
        st.session_state.last_insights = []

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "chat_turns" not in st.session_state:
        st.session_state.chat_turns = []

    if "report_export_filename" not in st.session_state:
        st.session_state.report_export_filename = report_pdf_filename()


def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(circle at top left, #fff1ec 0%, #fff8f5 35%, #f8fafc 100%);
        }

        [data-testid="stHeader"] {
            display: none;
        }

        [data-testid="stToolbar"] {
            display: none;
        }

        .block-container {
            padding-top: 0 !important;
            padding-bottom: 6rem !important;
            max-width: 1240px;
        }

        .main .block-container {
            padding-top: 0 !important;
            padding-bottom: 6rem !important;
        }

        [data-testid="stAppViewBlockContainer"] {
            padding-top: 0 !important;
            padding-bottom: 6rem !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 248, 245, 0.96);
            border: 1px solid #ffd8cf !important;
            border-radius: 22px !important;
            box-shadow: 0 8px 24px rgba(16, 24, 40, 0.04);
        }

        [data-baseweb="tab-list"] {
            margin-top: 0;
            gap: 0.35rem;
            margin-bottom: 0.2rem;
        }

        [data-baseweb="tab"] {
            color: #475467 !important;
        }

        [aria-selected="true"][data-baseweb="tab"] {
            color: #ff441f !important;
        }

        [data-baseweb="tab"] p,
        [data-baseweb="tab"] span,
        [data-baseweb="tab"] div {
            color: inherit !important;
        }

        [data-baseweb="tab-panel"] {
            padding-top: 0 !important;
        }

        [data-testid="stSidebar"] {
            background: #17212f !important;
            min-width: 230px !important;
            max-width: 270px !important;
        }

        [data-testid="stSidebarContent"] {
            padding: 1.2rem 1rem 1.5rem 1rem;
        }

        [data-testid="stSidebar"] .stMarkdown p,
        [data-testid="stSidebar"] .stMarkdown li,
        [data-testid="stSidebar"] .stMarkdown span {
            color: #c9d1da !important;
        }

        .sidebar-title {
            font-size: 0.72rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: rgba(255,255,255,0.38) !important;
            margin-bottom: 1rem;
        }

        .sidebar-category {
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color: #ff7a5c !important;
            margin-top: 1rem;
            margin-bottom: 0.35rem;
        }

        .sidebar-example {
            font-size: 0.87rem;
            color: #c9d1da !important;
            line-height: 1.45;
            padding: 0.42rem 0.6rem;
            border-radius: 9px;
            background: rgba(255,255,255,0.05);
            margin-bottom: 0.35rem;
            border-left: 2px solid rgba(255,122,92,0.35);
            cursor: default;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: rgba(255,255,255,0.05) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-left: 2px solid rgba(255,122,92,0.45) !important;
            color: #c9d1da !important;
            border-radius: 9px !important;
            text-align: left !important;
            padding: 0.42rem 0.6rem !important;
            font-size: 0.85rem !important;
            line-height: 1.45 !important;
            width: 100% !important;
            margin-bottom: 0.3rem !important;
            white-space: normal !important;
            height: auto !important;
            min-height: unset !important;
            box-shadow: none !important;
            font-weight: 400 !important;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(255,122,92,0.12) !important;
            border-left-color: #ff7a5c !important;
            color: white !important;
        }

        .sidebar-divider {
            border: none;
            border-top: 1px solid rgba(255,255,255,0.08);
            margin: 1.2rem 0 1rem 0;
        }

        [data-testid="stSidebar"] .stButton.clear-btn > button {
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            color: rgba(255,255,255,0.4) !important;
            font-size: 0.78rem !important;
            text-align: center !important;
            border-radius: 8px !important;
        }

        [data-testid="stSidebar"] .stButton.clear-btn > button:hover {
            background: rgba(255,60,60,0.12) !important;
            border-color: rgba(255,60,60,0.3) !important;
            color: rgba(255,150,150,0.9) !important;
        }

        .top-shell {
            background: linear-gradient(135deg, #ff5a36 0%, #ff441f 45%, #ff7a5c 100%);
            border-radius: 28px;
            padding: 1.15rem 1.2rem 1.1rem 1.2rem;
            color: white;
            box-shadow: 0 18px 36px rgba(255, 68, 31, 0.20);
            margin-bottom: 1rem;
        }

        .top-title {
            font-size: 2rem;
            font-weight: 900;
            letter-spacing: -0.03em;
            margin-bottom: 0.2rem;
            line-height: 1.1;
        }

        .top-subtitle {
            font-size: 0.97rem;
            opacity: 0.95;
            line-height: 1.45;
            max-width: 860px;
        }

        .metric-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
            margin-top: 0.8rem;
        }

        .metric-pill {
            background: rgba(255,255,255,0.16);
            border: 1px solid rgba(255,255,255,0.22);
            color: white;
            border-radius: 999px;
            padding: 0.48rem 0.78rem;
            font-size: 0.86rem;
            font-weight: 700;
        }

        .chat-hero {
            background: linear-gradient(135deg, #ff5a36 0%, #ff441f 45%, #ff7a5c 100%);
            border-radius: 22px;
            padding: 0.8rem 1rem 0.75rem 1rem;
            color: white;
            box-shadow: 0 14px 28px rgba(255, 68, 31, 0.18);
            margin-bottom: 0.3rem;
        }

        .chat-hero-title {
            font-size: 1.45rem;
            font-weight: 900;
            letter-spacing: -0.03em;
            line-height: 1.1;
            margin-bottom: 0.25rem;
        }

        .chat-hero-copy {
            font-size: 0.94rem;
            opacity: 0.95;
            line-height: 1.45;
            max-width: 760px;
        }

        .empty-state {
            padding: 0.05rem 0.4rem 0.4rem 0.4rem;
            text-align: center;
            color: #667085;
        }

        .assistant-intro {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            justify-content: center;
            margin-bottom: 0.45rem;
        }

        .assistant-avatar {
            width: 44px;
            height: 44px;
            border-radius: 14px;
            background: linear-gradient(135deg, #ff441f 0%, #ff7a5c 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            font-size: 1rem;
            box-shadow: 0 10px 24px rgba(255, 68, 31, 0.22);
        }

        .assistant-name {
            font-weight: 800;
            color: #101828;
            font-size: 1rem;
        }

        .assistant-copy {
            color: #667085;
            font-size: 0.92rem;
        }

        .chat-intro-card {
            background: rgba(255,255,255,0.86);
            border: 1px solid #f1dfd9;
            border-radius: 18px;
            padding: 0.85rem 0.9rem;
            margin-bottom: 0.75rem;
        }

        .composer-hint {
            color: #667085;
            font-size: 0.86rem;
            margin-top: 0.1rem;
            margin-bottom: 0.15rem;
        }

        .chat-row {
            display: flex;
            width: 100%;
            margin-bottom: 0.8rem;
        }

        .chat-row.user {
            justify-content: flex-end;
        }

        .chat-row.assistant {
            justify-content: flex-start;
        }

        .bubble {
            max-width: 78%;
            border-radius: 20px;
            padding: 0.95rem 1rem;
            box-shadow: 0 6px 18px rgba(16,24,40,0.04);
            line-height: 1.6;
        }

        .bubble.user {
            background: linear-gradient(135deg, #ff5a36 0%, #ff441f 100%);
            color: white;
            border-bottom-right-radius: 8px;
        }

        .bubble.assistant {
            background: #fff8f5;
            color: #17212f;
            border: 1px solid #ffd8cf;
            border-bottom-left-radius: 8px;
        }

        .bubble-label {
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.35rem;
            opacity: 0.8;
        }

        .assistant-turn-wrap {
            margin-bottom: 0.75rem;
        }

        .assistant-bubble-label {
            font-size: 0.74rem;
            font-weight: 900;
            color: #9a3412;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.35rem;
        }

        .assistant-answer-text {
            color: #17212f;
            line-height: 1.6;
            font-size: 1rem;
        }

        .assistant-section-title {
            font-size: 0.92rem;
            font-weight: 800;
            color: #101828;
            margin-top: 0.9rem;
            margin-bottom: 0.55rem;
        }

        .insight-box {
            background: #ffffff;
            border: 1px solid #f4e2dc;
            border-radius: 16px;
            padding: 0.85rem 0.9rem;
            margin-bottom: 0.65rem;
            box-shadow: 0 4px 14px rgba(16,24,40,0.03);
            color: #17212f;
        }

        .insight-title {
            font-weight: 800;
            color: #ff441f;
            margin-bottom: 0.2rem;
        }

        .insight-meta {
            font-size: 0.8rem;
            color: #667085;
            margin-bottom: 0.35rem;
        }

        .insight-message {
            color: #17212f;
            line-height: 1.55;
        }

        .insight-recommendation {
            margin-top: 0.45rem;
            color: #475467;
            line-height: 1.55;
        }

        .history-card {
            background: rgba(255,255,255,0.94);
            border: 1px solid #f1dfd9;
            border-radius: 22px;
            padding: 1rem;
            box-shadow: 0 10px 24px rgba(16,24,40,0.04);
            margin-bottom: 1rem;
            position: sticky;
            top: 1rem;
        }

        .history-item {
            background: #fff8f5;
            border: 1px solid #ffe0d6;
            border-radius: 16px;
            padding: 0.8rem 0.85rem;
            margin-bottom: 0.7rem;
        }

        .history-q {
            font-size: 0.78rem;
            color: #9a3412;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }

        .history-a {
            color: #344054;
            font-size: 0.9rem;
            line-height: 1.45;
        }

        .section-card {
            background: rgba(255,255,255,0.94);
            border: 1px solid #f1dfd9;
            border-radius: 22px;
            padding: 1rem 1.05rem;
            box-shadow: 0 10px 24px rgba(16,24,40,0.04);
            margin-bottom: 1rem;
        }

        .section-title {
            font-size: 1rem;
            font-weight: 800;
            color: #101828;
            margin-bottom: 0.75rem;
        }

        .section-subtle {
            color: #667085;
            font-size: 0.9rem;
            margin-bottom: 0.8rem;
        }

        .report-hero {
            background: linear-gradient(135deg, #17212f 0%, #23324a 55%, #32486a 100%);
            border-radius: 24px;
            padding: 1rem 1.05rem;
            color: white;
            box-shadow: 0 16px 34px rgba(23, 33, 47, 0.16);
            margin-bottom: 1rem;
        }

        .report-kicker {
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: rgba(255,255,255,0.72);
            margin-bottom: 0.35rem;
        }

        .report-title {
            font-size: 1.6rem;
            font-weight: 900;
            letter-spacing: -0.03em;
            margin-bottom: 0.3rem;
        }

        .report-copy {
            font-size: 0.95rem;
            line-height: 1.5;
            color: rgba(255,255,255,0.86);
            max-width: 860px;
        }

        .report-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin-top: 0.85rem;
        }

        .report-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.14);
            color: white;
            padding: 0.45rem 0.75rem;
            font-size: 0.84rem;
            font-weight: 700;
        }

        .report-overview-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        .report-stat-card {
            background: rgba(255,255,255,0.94);
            border: 1px solid #f1dfd9;
            border-radius: 18px;
            padding: 0.9rem 0.95rem;
            box-shadow: 0 10px 24px rgba(16,24,40,0.04);
        }

        .report-stat-label {
            font-size: 0.76rem;
            color: #667085;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.22rem;
        }

        .report-stat-value {
            font-size: 1.2rem;
            font-weight: 800;
            color: #101828;
        }

        .report-section-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }

        .report-section-count {
            border-radius: 999px;
            background: #fff3ef;
            border: 1px solid #ffd8cf;
            color: #9a3412;
            padding: 0.32rem 0.65rem;
            font-size: 0.8rem;
            font-weight: 700;
        }

        .summary-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 0.2rem;
        }

        .summary-item {
            background: #fff;
            border: 1px solid #f0e3de;
            border-radius: 16px;
            padding: 0.85rem 0.95rem;
        }

        .summary-label {
            font-size: 0.76rem;
            color: #667085;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }

        .summary-value {
            font-size: 1rem;
            font-weight: 700;
            color: #101828;
            line-height: 1.35;
        }

        .chip-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.2rem;
        }

        .filter-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: #fff3ef;
            border: 1px solid #ffd8cf;
            color: #9a3412;
            border-radius: 999px;
            padding: 0.42rem 0.7rem;
            font-size: 0.86rem;
            font-weight: 600;
        }

        .trace-box {
            background: #ffffff;
            border: 1px solid #f0e3de;
            border-radius: 16px;
            padding: 0.9rem 0.95rem;
        }

        .trace-line {
            font-size: 0.92rem;
            color: #344054;
            margin-bottom: 0.55rem;
            line-height: 1.45;
        }

        .trace-line b {
            color: #101828;
        }

        .footer-note {
            color: #667085;
            font-size: 0.9rem;
            text-align: center;
            margin-top: 0.6rem;
        }

        /* ── Compact app header ── */
        .app-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #ffffff;
            border: 1px solid #ffd8cf;
            border-radius: 18px;
            padding: 0.7rem 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 14px rgba(255,68,31,0.06);
        }

        .app-header-left {
            display: flex;
            align-items: center;
            gap: 0.65rem;
        }

        .app-logo {
            width: 38px;
            height: 38px;
            border-radius: 11px;
            background: linear-gradient(135deg, #ff441f 0%, #ff7a5c 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            font-size: 1rem;
            flex-shrink: 0;
            box-shadow: 0 6px 14px rgba(255,68,31,0.22);
        }

        .app-title {
            font-weight: 900;
            font-size: 1rem;
            color: #101828;
            letter-spacing: -0.02em;
        }

        .app-subtitle {
            font-size: 0.82rem;
            color: #667085;
            margin-top: 0.05rem;
        }

        .app-pills {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .app-pill {
            background: #fff3ef;
            border: 1px solid #ffd8cf;
            color: #9a3412;
            border-radius: 999px;
            padding: 0.32rem 0.65rem;
            font-size: 0.8rem;
            font-weight: 700;
        }

        /* Spinner text */
        [data-testid="stSpinner"] p {
            color: #ff441f !important;
            font-weight: 600;
        }

        /* Chart container clean look */
        [data-testid="stPlotlyChart"] {
            border-radius: 14px;
            overflow: hidden;
        }

        /* ── Floating chat input — centrado con padding calc ── */
        [data-testid="stBottom"] {
            background: transparent !important;
            background-color: transparent !important;
            box-shadow: none !important;
            border-top: none !important;
            padding-top: 0.75rem !important;
            padding-bottom: 1.4rem !important;
            padding-left: max(1rem, calc((100% - 1240px) / 2)) !important;
            padding-right: max(1rem, calc((100% - 1240px) / 2)) !important;
        }
        [data-testid="stBottomBlockContainer"] {
            background: transparent !important;
            background-color: transparent !important;
        }
        /* Wrapper interno — transparente, sin padding extra */
        [data-testid="stBottom"] > div {
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
        }

        /* La pill del input — fondo oscuro Rappi con borde naranja */
        [data-testid="stChatInputContainer"] {
            border-radius: 18px !important;
            border: 1.5px solid #ff441f !important;
            box-shadow: 0 4px 20px rgba(255,68,31,0.15), 0 1px 6px rgba(0,0,0,0.12) !important;
            overflow: hidden !important;
        }

        /* Texto siempre plata/blanco */
        [data-testid="stChatInput"] textarea {
            color: #e5e7eb !important;
            -webkit-text-fill-color: #e5e7eb !important;
            caret-color: #ff441f !important;
        }
        [data-testid="stChatInput"] textarea::placeholder {
            color: #9ca3af !important;
            -webkit-text-fill-color: #9ca3af !important;
        }

        /* Botón enviar — naranja Rappi */
        [data-testid="stChatInputSubmitButton"] button {
            background: #ff441f !important;
            border-radius: 12px !important;
        }
        [data-testid="stChatInputSubmitButton"] button svg path {
            fill: white !important;
        }

        /* Texto visible en expanders (contraste general) */
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span,
        [data-testid="stExpander"] > details > summary p {
            color: #344054 !important;
            font-weight: 600 !important;
        }

        /* ── Rappi-friendly data table ── */
        .rappi-table-wrap {
            overflow-x: auto;
            overflow-y: auto;
            max-height: 360px;
            border-radius: 12px;
            border: 1px solid #ffd8cf;
            margin: 0.5rem 0 0.2rem 0;
            box-shadow: 0 4px 12px rgba(255,68,31,0.06);
        }
        .rappi-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.87rem;
        }
        .rappi-table thead th {
            background: #ff441f;
            color: white;
            padding: 0.55rem 0.8rem;
            text-align: left;
            font-weight: 700;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            white-space: nowrap;
            position: sticky;
            top: 0;
            z-index: 2;
        }
        .rappi-table thead th:first-child { border-radius: 11px 0 0 0; }
        .rappi-table thead th:last-child  { border-radius: 0 11px 0 0; }
        .rappi-table tbody tr:nth-child(even) { background: #fff8f5; }
        .rappi-table tbody tr:nth-child(odd)  { background: #ffffff; }
        .rappi-table tbody td {
            padding: 0.5rem 0.8rem;
            color: #344054;
            border-top: 1px solid #fde8e0;
        }
        .rappi-table tbody tr:hover { background: #fff3ef !important; }

        /* ── Trazabilidad expander styling ── */
        .element-container:has(.trace-expander-before) + .element-container [data-testid="stExpander"] {
            background: #faf5ff !important;
            border: 1px solid #c4b5fd !important;
            border-radius: 12px !important;
        }
        .element-container:has(.trace-expander-before) + .element-container [data-testid="stExpander"] summary p {
            color: #7c3aed !important;
            font-weight: 600 !important;
        }

        /* ── Email Insights expander styling ── */
        .element-container:has(.email-expander-before) + .element-container [data-testid="stExpander"] {
            background: #ecfeff !important;
            border: 1px solid #67e8f9 !important;
            border-radius: 12px !important;
        }
        .element-container:has(.email-expander-before) + .element-container [data-testid="stExpander"] summary p {
            color: #0891b2 !important;
            font-weight: 600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def pretty_label(value) -> str:
    if value is None or value == "":
        return "—"
    return str(display_value(value)).replace("_", " ").title()


def format_time_scope(time_scope: list | None) -> str:
    if not time_scope:
        return "Default window"
    return ", ".join(time_scope)


def format_generated_at(timestamp: str | None) -> str:
    if not timestamp:
        return "Not available"
    return timestamp.replace("T", " ").replace("Z", " UTC")


def pretty_label(value) -> str:
    if value is None or value == "":
        return "-"
    return str(display_value(value)).replace("_", " ").title()


def format_time_scope(time_scope: list | None) -> str:
    if not time_scope:
        return "Ventana por defecto"
    return ", ".join(time_scope)


def format_generated_at(timestamp: str | None) -> str:
    if not timestamp:
        return "No disponible"
    return timestamp.replace("T", " ").replace("Z", " UTC")


def get_active_filters(filters: dict | None) -> dict:
    if not filters:
        return {}
    return {k: v for k, v in filters.items() if v not in [None, "", []]}


def show_active_filters(filters: dict | None) -> None:
    active_filters = get_active_filters(filters)

    if not active_filters:
        st.write("No hay filtros explícitos aplicados.")
        return

    chips_html = "".join(
        [
            f'<div class="filter-chip"><span>{pretty_label(k)}</span>: <span>{display_filter_value(k, v)}</span></div>'
            for k, v in active_filters.items()
        ]
    )
    st.markdown(f'<div class="chip-wrap">{chips_html}</div>', unsafe_allow_html=True)


def show_run_summary(parsed_intent: dict | None, analytical_result: dict | None) -> None:
    if not parsed_intent or not analytical_result:
        st.write("Todavía no hay un resumen analítico disponible.")
        return

    metric = parsed_intent.get("metric")
    intent = parsed_intent.get("intent")
    group_by = parsed_intent.get("group_by")
    time_scope = parsed_intent.get("time_scope")
    router_mode = parsed_intent.get("router_mode")

    dataset_used = analytical_result.get("dataset_used")
    aggregation_method = analytical_result.get("aggregation_method")
    analysis_type = analytical_result.get("analysis_type")
    status = analytical_result.get("status")

    st.markdown(
        f"""
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-label">Métrica</div>
                <div class="summary-value">{pretty_label(metric)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Intent</div>
                <div class="summary-value">{pretty_label(intent)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Tipo de análisis</div>
                <div class="summary-value">{pretty_label(analysis_type)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Estado</div>
                <div class="summary-value">{pretty_label(status)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Dataset usado</div>
                <div class="summary-value">{pretty_label(dataset_used)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Agregación</div>
                <div class="summary-value">{pretty_label(aggregation_method)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Agrupación</div>
                <div class="summary-value">{pretty_label(group_by)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Modo del router</div>
                <div class="summary-value">{pretty_label(router_mode)}</div>
            </div>
            <div class="summary-item" style="grid-column: 1 / -1;">
                <div class="summary-label">Semanas consideradas</div>
                <div class="summary-value">{format_time_scope(time_scope)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_trace_summary(parsed_intent: dict | None, analytical_result: dict | None) -> None:
    if not parsed_intent and not analytical_result:
        st.write("Todavía no hay traza técnica.")
        return

    intent = parsed_intent.get("intent") if parsed_intent else None
    metric = parsed_intent.get("metric") if parsed_intent else None
    group_by = parsed_intent.get("group_by") if parsed_intent else None
    time_scope = parsed_intent.get("time_scope") if parsed_intent else None
    dataset_used = analytical_result.get("dataset_used") if analytical_result else None
    aggregation_method = analytical_result.get("aggregation_method") if analytical_result else None
    status = analytical_result.get("status") if analytical_result else None

    lines = []
    if metric:
        lines.append(f"<div class='trace-line'><b>Métrica resuelta:</b> {metric}</div>")
    if intent:
        lines.append(f"<div class='trace-line'><b>Intent resuelto:</b> {intent}</div>")
    if dataset_used:
        lines.append(f"<div class='trace-line'><b>Dataset seleccionado:</b> {dataset_used}</div>")
    if aggregation_method:
        lines.append(f"<div class='trace-line'><b>Agregación aplicada:</b> {aggregation_method}</div>")
    if group_by:
        lines.append(f"<div class='trace-line'><b>Dimensión de agrupación:</b> {group_by}</div>")
    if time_scope:
        lines.append(f"<div class='trace-line'><b>Ventana temporal:</b> {', '.join(time_scope)}</div>")
    if status:
        lines.append(f"<div class='trace-line'><b>Estado de ejecución:</b> {status}</div>")

    if not lines:
        st.write("Todavía no hay traza técnica.")
        return

    st.markdown(f"<div class='trace-box'>{''.join(lines)}</div>", unsafe_allow_html=True)


_RAPPI_ORANGE = "#ff441f"
_RAPPI_ORANGE_MID = "#ff6b47"
_RAPPI_ORANGE_LIGHT = "#ff7a5c"
_CHART_FONT = dict(family="Inter, system-ui, -apple-system, sans-serif", color="#344054", size=12)
_CHART_TITLE_FONT = dict(family="Inter, system-ui, -apple-system, sans-serif", size=13, color="#101828")
_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,248,245,0.5)",
    font=_CHART_FONT,
    title_font=_CHART_TITLE_FONT,
    margin=dict(l=20, r=20, t=48, b=20),
    xaxis=dict(gridcolor="#f0c4b5", linecolor="#e8906e", linewidth=1, showline=True, tickfont=dict(size=11, color="#475467"), title_font=dict(color="#344054", size=12)),
    yaxis=dict(gridcolor="#f0c4b5", linecolor="#e8906e", linewidth=1, showline=True, tickfont=dict(size=11, color="#475467"), title_font=dict(color="#344054", size=12)),
    hoverlabel=dict(bgcolor="white", bordercolor="#ffd8cf", font=dict(color="#101828", size=12)),
)


def build_chart(analytical_result: dict):
    status = analytical_result.get("status")
    analysis_type = analytical_result.get("analysis_type")
    result_table = analytical_result.get("result_table", [])

    if status != "success" or not result_table:
        return None

    df = pd.DataFrame(result_table)

    if analysis_type == "trend":
        if "week" not in df.columns or "value" not in df.columns:
            return None
        df["week_order"] = df["week"].map(WEEK_ORDER)
        df = df.sort_values("week_order")
        fig = px.line(
            df, x="week", y="value", markers=True, title="Tendencia en el tiempo",
            color_discrete_sequence=[_RAPPI_ORANGE],
        )
        fig.update_traces(
            line=dict(color=_RAPPI_ORANGE, width=2.5),
            marker=dict(size=7, color=_RAPPI_ORANGE, line=dict(color="white", width=1.5)),
        )
        fig.update_layout(**_CHART_LAYOUT, height=360, xaxis_title="Semana", yaxis_title="Valor")
        return fig

    if analysis_type == "comparison":
        group_by = analytical_result.get("group_by")
        if not group_by or group_by not in df.columns or "value" not in df.columns:
            return None
        if "week" in df.columns:
            df["week_order"] = df["week"].map(WEEK_ORDER)
            latest_week_order = df["week_order"].max()
            df = df[df["week_order"] == latest_week_order].copy()
        df = df.sort_values("value", ascending=False)
        fig = px.bar(
            df, x=group_by, y="value", title=f"Comparación por {pretty_label(group_by)}",
            color_discrete_sequence=[_RAPPI_ORANGE],
        )
        fig.update_traces(marker_color=_RAPPI_ORANGE, marker_line_width=0)
        fig.update_layout(
            **_CHART_LAYOUT, height=360,
            xaxis_title=group_by.replace("_", " ").title(), yaxis_title="Valor",
        )
        return fig

    if analysis_type == "ranking":
        group_by = analytical_result.get("group_by")
        if not group_by or group_by not in df.columns or "value" not in df.columns:
            return None
        rank_limit = analytical_result.get("rank_limit") or 10
        df = df.head(rank_limit).sort_values("value", ascending=True)
        fig = px.bar(
            df, x="value", y=group_by, orientation="h",
            title=f"Ranking por {pretty_label(group_by)}",
            color_discrete_sequence=[_RAPPI_ORANGE],
        )
        fig.update_traces(marker_color=_RAPPI_ORANGE, marker_line_width=0)
        fig.update_layout(
            **_CHART_LAYOUT, height=400,
            xaxis_title="Valor", yaxis_title=group_by.replace("_", " ").title(),
        )
        return fig

    if analysis_type == "distribution":
        group_by = analytical_result.get("group_by")
        metric = analytical_result.get("metric", "Métrica principal")
        secondary_metric = analytical_result.get("secondary_metric", "Métrica secundaria")
        if not group_by or group_by not in df.columns:
            return None
        if "primary_value" not in df.columns or "secondary_value" not in df.columns:
            return None
        fig = px.scatter(
            df, x="primary_value", y="secondary_value", hover_name=group_by,
            title=f"{metric} vs {secondary_metric}",
        )
        fig.update_traces(
            marker=dict(size=9, opacity=0.75, color=_RAPPI_ORANGE,
                        line=dict(color="white", width=1.5))
        )
        fig.update_layout(
            **_CHART_LAYOUT, height=380, xaxis_title=metric, yaxis_title=secondary_metric,
        )
        return fig

    if analysis_type == "anomaly":
        group_by = analytical_result.get("group_by")
        metric = analytical_result.get("metric", "Metric")
        if not group_by or group_by not in df.columns or "delta_pct" not in df.columns:
            return None
        chart_df = df.head(10).sort_values("delta_pct", ascending=True).copy()
        colors = [_RAPPI_ORANGE if v < 0 else "#22c55e" for v in chart_df["delta_pct"]]
        fig = px.bar(
            chart_df, x="delta_pct", y=group_by, orientation="h",
            title=f"Mayor movimiento en {metric}",
        )
        fig.update_traces(marker_color=colors, marker_line_width=0)
        fig.update_layout(
            **_CHART_LAYOUT, height=400,
            xaxis_title="Delta %", yaxis_title=group_by.replace("_", " ").title(),
        )
        return fig

    return None



def show_result_table(result_table: list) -> None:
    if not result_table:
        st.write("No hay tabla de resultados disponible.")
        return
    df = pd.DataFrame(result_table)
    total_rows = len(df)
    cols = df.columns.tolist()
    header_html = "".join(f"<th>{col}</th>" for col in cols)
    rows_html = ""
    for _, row in df.iterrows():
        cells = "".join(f"<td>{val}</td>" for val in row)
        rows_html += f"<tr>{cells}</tr>"
    st.markdown(
        f'<div class="rappi-table-wrap"><table class="rappi-table">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True,
    )
    if total_rows > 10:
        st.markdown(
            f'<div style="font-size:0.75rem;color:#9a3412;margin-top:0.25rem;text-align:right;">'
            f'{total_rows} filas · scrolleá para ver todas</div>',
            unsafe_allow_html=True,
        )


def show_insights(insights: list[dict]) -> None:
    if not insights:
        st.write("No se generaron insights automáticos.")
        return
    for insight in insights:
        meta_parts = []
        if insight.get("category"):
            meta_parts.append(insight["category"].replace("_", " ").title())
        if insight.get("severity"):
            meta_parts.append(f"Severity: {insight['severity'].title()}")
        meta_html = " • ".join(meta_parts)
        recommendation_html = ""
        if insight.get("recommendation"):
            recommendation_html = f"<div class='insight-recommendation'><b>Acción recomendada:</b> {insight['recommendation']}</div>"
        st.markdown(
            f"""
            <div class="insight-box">
                <div class="insight-title">{insight['title']}</div>
                <div class="insight-meta">{meta_html}</div>
                <div class="insight-message">{insight['message']}</div>
                {recommendation_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_top_shell(overview: dict) -> None:
    st.markdown(
        f"""
        <div class="top-shell">
            <div class="top-title">Rappi AI Operations Assistant</div>
            <div class="top-subtitle">
                Analítica conversacional para operaciones. Preguntá en lenguaje natural, obtené respuestas determinísticas y revisá la traza técnica solo cuando la necesites.
            </div>
            <div class="metric-pill-row">
                <div class="metric-pill">Modelo: {DEFAULT_MODEL_NAME}</div>
                <div class="metric-pill">Países: {overview['metrics_unique_countries']}</div>
                <div class="metric-pill">Ciudades: {overview['metrics_unique_cities']}</div>
                <div class="metric-pill">Zonas: {overview['metrics_unique_zones']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_compact_header(overview: dict) -> None:
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#ff441f 0%,#ff5a36 55%,#ff7a5c 100%);border-radius:24px;padding:1.35rem 1.5rem 1.2rem 1.5rem;color:white;box-shadow:0 20px 40px rgba(255,68,31,0.22);margin-bottom:1rem;position:relative;overflow:hidden;">
            <div style="position:absolute;right:-50px;top:-50px;width:220px;height:220px;border-radius:50%;background:rgba(255,255,255,0.07);pointer-events:none;"></div>
            <div style="position:absolute;right:90px;top:8px;width:100px;height:100px;border-radius:50%;background:rgba(255,255,255,0.05);pointer-events:none;"></div>
            <div style="position:absolute;left:35%;bottom:-35px;width:160px;height:160px;border-radius:50%;background:rgba(255,255,255,0.04);pointer-events:none;"></div>
            <div style="position:relative;">
                <div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.85rem;">
                    <div style="width:52px;height:52px;border-radius:16px;background:rgba(255,255,255,0.2);border:2px solid rgba(255,255,255,0.3);display:flex;align-items:center;justify-content:center;font-size:1.65rem;font-weight:900;flex-shrink:0;box-shadow:0 8px 20px rgba(0,0,0,0.12);letter-spacing:-0.02em;">R</div>
                    <div>
                        <div style="font-size:1.45rem;font-weight:900;letter-spacing:-0.03em;line-height:1.1;">Rappi AI Ops</div>
                        <div style="font-size:0.84rem;opacity:0.88;margin-top:0.15rem;line-height:1.4;">Sistema de Análisis Inteligente para Operaciones &nbsp;·&nbsp; Technical Challenge Demo</div>
                    </div>
                </div>
                <div style="display:flex;gap:0.55rem;flex-wrap:wrap;">
                    <div style="background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.26);border-radius:999px;padding:0.35rem 0.72rem;font-size:0.8rem;font-weight:700;">🌎 {overview['metrics_unique_countries']} países</div>
                    <div style="background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.26);border-radius:999px;padding:0.35rem 0.72rem;font-size:0.8rem;font-weight:700;">🏙 {overview['metrics_unique_cities']} ciudades</div>
                    <div style="background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.26);border-radius:999px;padding:0.35rem 0.72rem;font-size:0.8rem;font-weight:700;">📍 {overview['metrics_unique_zones']} zonas</div>
                    <div style="background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.26);border-radius:999px;padding:0.35rem 0.72rem;font-size:0.8rem;font-weight:700;">🤖 {DEFAULT_MODEL_NAME}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_bottom_bar() -> None:
    st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
    st.divider()

    if st.session_state.executive_report is None:
        st.session_state.executive_report = st.session_state.insight_engine.generate_executive_report()

    report = st.session_state.executive_report
    pdf_bytes = build_executive_report_pdf(report)
    filename = st.session_state.report_export_filename

    smtp_settings = {
        "host": SMTP_HOST,
        "port": SMTP_PORT,
        "username": SMTP_USERNAME,
        "password": SMTP_PASSWORD,
        "from_email": SMTP_FROM_EMAIL,
        "use_tls": SMTP_USE_TLS,
    }

    col_csv, col_pdf, col_email = st.columns(3)

    with col_csv:
        last_result = st.session_state.last_analytical_result
        result_table = (last_result or {}).get("result_table", [])
        if result_table:
            csv_bytes = pd.DataFrame(result_table).to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar CSV",
                data=csv_bytes,
                file_name="resultado.csv",
                mime="text/csv",
                use_container_width=True,
                key="bottom_bar_csv",
            )
        else:
            st.button("Descargar CSV", disabled=True, use_container_width=True, key="bottom_bar_csv_disabled")

    with col_pdf:
        st.download_button(
            "Descargar Insights PDF",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
            key=f"bottom_bar_pdf_{filename}",
        )

    with col_email:
        st.markdown(
            '<div class="email-expander-before" style="margin-bottom:0.2rem;">'
            '<span style="font-size:0.68rem; font-weight:800; color:#0891b2; text-transform:uppercase; letter-spacing:0.07em; background:#ecfeff; padding:0.1rem 0.45rem; border-radius:4px; border:1px solid #a5f3fc;">✉ Exportar por mail</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Email Insights"):
            if not smtp_configured(smtp_settings):
                st.info("Configurá SMTP en .env para habilitar el envío por mail.")
            else:
                st.markdown(f'<p style="font-size:0.82rem;color:#344054;margin-bottom:0.4rem;">Se enviará desde <b>{SMTP_FROM_EMAIL}</b></p>', unsafe_allow_html=True)
                recipient = st.text_input("Destinatario", key="bar_email_to", placeholder="nombre@empresa.com")
                if st.button("Enviar PDF", key=f"bar_send_{filename}", use_container_width=True):
                    if not recipient.strip():
                        st.error("Ingresá un destinatario.")
                    else:
                        try:
                            send_report_email(
                                smtp_settings=smtp_settings,
                                to_email=recipient.strip(),
                                subject="Reporte Ejecutivo - Rappi AI Operations",
                                body="Adjunto el reporte ejecutivo generado automáticamente.",
                                pdf_bytes=pdf_bytes,
                                filename=filename,
                            )
                            st.success(f"Enviado a {recipient.strip()}")
                        except Exception as exc:
                            st.error(f"Error al enviar: {exc}")


def run_full_query(user_message: str) -> None:
    memory = st.session_state.memory
    router = st.session_state.router
    query_engine = st.session_state.query_engine
    narrator = st.session_state.narrator
    insight_engine = st.session_state.insight_engine

    memory_context = memory.get_context()
    parsed_intent = router.parse(user_message, memory_context)
    analytical_result = query_engine.run(parsed_intent)
    executive_answer = narrator.narrate(
        user_query=user_message,
        parsed_intent=parsed_intent,
        analytical_result=analytical_result,
    )
    insights = insight_engine.generate(analytical_result)
    fig = build_chart(analytical_result)

    memory.add_turn(user_message, executive_answer)
    memory.set_last_intent(parsed_intent)
    memory.set_last_result(analytical_result)

    if parsed_intent.get("metric"):
        memory.set_last_metric(parsed_intent["metric"])

    if parsed_intent.get("filters"):
        memory.set_last_filters(parsed_intent["filters"])
        memory.set_last_entities(parsed_intent["filters"])

    if parsed_intent.get("group_by"):
        memory.set_last_dimension(parsed_intent["group_by"])

    memory.save()

    st.session_state.last_parsed_intent = parsed_intent
    st.session_state.last_analytical_result = analytical_result
    st.session_state.last_executive_answer = executive_answer
    st.session_state.last_insights = insights

    st.session_state.chat_history.append(
        {
            "user": user_message,
            "assistant": executive_answer,
        }
    )

    st.session_state.chat_turns.append(
        {
            "user": user_message,
            "assistant": executive_answer,
            "insights": insights,
            "analytical_result": analytical_result,
            "parsed_intent": parsed_intent,
            "figure": fig,
        }
    )


def render_chat_turn_user(text: str) -> None:
    st.markdown(
        f"""
        <div class="chat-row user">
            <div class="bubble user">
                <div class="bubble-label">Vos</div>
                <div>{text}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chat_turn_assistant(turn: dict, turn_index: int = 0) -> None:
    left_col, right_col = st.columns([0.84, 0.16])
    with left_col:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="assistant-bubble-label">Rappi Ops Assistant</div>
                <div class="assistant-answer-text">{turn['assistant']}</div>
                """,
                unsafe_allow_html=True,
            )

            fig = turn.get("figure")
            if fig is not None:
                st.markdown('<div class="assistant-section-title">Gráfico</div>', unsafe_allow_html=True)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{turn_index}")

            analytical_result = turn.get("analytical_result", {})
            result_table = analytical_result.get("result_table", [])
            if result_table:
                st.markdown('<div class="assistant-section-title">Tabla de resultados</div>', unsafe_allow_html=True)
                show_result_table(result_table)

            insights = turn.get("insights", [])
            if insights:
                with st.expander(f"Insights automáticos ({len(insights)})", expanded=False):
                    show_insights(insights)

            st.markdown(
                '<div class="trace-expander-before" style="border-top:1px solid #e9d8fd; margin-top:0.6rem; padding-top:0.4rem;">'
                '<span style="font-size:0.68rem; font-weight:800; color:#7c3aed; text-transform:uppercase; letter-spacing:0.07em; background:#faf5ff; padding:0.1rem 0.45rem; border-radius:4px;">⚙ Auditoría técnica</span>'
                "</div>",
                unsafe_allow_html=True,
            )
            with st.expander("Ver trazabilidad técnica"):
                show_trace_summary(turn.get("parsed_intent"), turn.get("analytical_result"))
                t1, t2 = st.tabs(["Intent parseado", "Resultado analítico"])
                with t1:
                    if turn.get("parsed_intent"):
                        st.json(turn["parsed_intent"])
                    else:
                        st.write("No disponible.")
                with t2:
                    if turn.get("analytical_result"):
                        st.json({k: v for k, v in turn["analytical_result"].items() if k != "result_table"})
                    else:
                        st.write("No disponible.")



def render_technical_tab() -> None:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Resumen de ejecución</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtle">Vista concisa de lo que entendió el asistente y cómo respondió el motor determinístico.</div>',
        unsafe_allow_html=True,
    )
    show_run_summary(st.session_state.last_parsed_intent, st.session_state.last_analytical_result)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Filtros activos</div>', unsafe_allow_html=True)
    show_active_filters(
        st.session_state.last_parsed_intent.get("filters", {}) if st.session_state.last_parsed_intent else {}
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Traza técnica</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtle">Vista transparente del routing, la analítica determinística y el estado de ejecución.</div>',
        unsafe_allow_html=True,
    )
    show_trace_summary(st.session_state.last_parsed_intent, st.session_state.last_analytical_result)
    st.write("")

    tab1, tab2 = st.tabs(["Intent parseado", "Resultado analítico"])

    with tab1:
        if st.session_state.last_parsed_intent:
            st.json(st.session_state.last_parsed_intent)
        else:
            st.write("Todavía no hay un intent parseado.")

    with tab2:
        if st.session_state.last_analytical_result:
            st.json(
                {
                    k: v
                    for k, v in st.session_state.last_analytical_result.items()
                    if k != "result_table"
                }
            )
        else:
            st.write("Todavía no hay resultado analítico.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_executive_report_overview(report: dict) -> None:
    counts = report.get("counts", {})
    total_findings = sum(counts.values())
    active_categories = sum(1 for value in counts.values() if value > 0)
    generated_at = format_generated_at(report.get("generated_at"))

    st.markdown(
        f"""
        <div class="report-hero">
            <div class="report-kicker">Resumen Operativo</div>
            <div class="report-title">Reporte Ejecutivo</div>
            <div class="report-copy">
                Hallazgos transversales generados automáticamente a partir del dataset actual. Esta vista está pensada para sentirse lista para presentar en una demo corta o en una entrevista.
            </div>
            <div class="report-pill-row">
                <div class="report-pill">Generado: {generated_at}</div>
                <div class="report-pill">Hallazgos totales: {total_findings}</div>
                <div class="report-pill">Categorías activas: {active_categories}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="report-overview-grid">
            <div class="report-stat-card">
                <div class="report-stat-label">Ítems del resumen</div>
                <div class="report-stat-value">{len(report.get('summary', []))}</div>
            </div>
            <div class="report-stat-card">
                <div class="report-stat-label">Categoría con más hallazgos</div>
                <div class="report-stat-value">{pretty_label(max(counts, key=counts.get) if counts else None)}</div>
            </div>
            <div class="report-stat-card">
                <div class="report-stat-label">Categorías vacías</div>
                <div class="report-stat-value">{sum(1 for value in counts.values() if value == 0)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_executive_report_actions(report: dict) -> None:
    pdf_bytes = build_executive_report_pdf(report)
    filename = st.session_state.report_export_filename
    smtp_settings = {
        "host": SMTP_HOST,
        "port": SMTP_PORT,
        "username": SMTP_USERNAME,
        "password": SMTP_PASSWORD,
        "from_email": SMTP_FROM_EMAIL,
        "use_tls": SMTP_USE_TLS,
    }

    col_download, col_save = st.columns([0.7, 0.3])
    with col_download:
        st.download_button(
            "Descargar reporte en PDF",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
            key=f"download_report_{filename}",
        )
    with col_save:
        if st.button("Guardar copia local", use_container_width=True, key=f"save_report_{filename}"):
            output_path = REPORTS_DIR / filename
            output_path.write_bytes(pdf_bytes)
            st.success(f"Reporte guardado en {output_path}")

    with st.expander("Enviar reporte por mail"):
        if not smtp_configured(smtp_settings):
            st.info(
                "Configurá SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD y SMTP_FROM_EMAIL en el entorno para habilitar el envío por mail."
            )
            return

        st.markdown(f'<p style="font-size:0.82rem;color:#344054;margin-bottom:0.4rem;">Se enviará desde <b>{SMTP_FROM_EMAIL}</b> usando {SMTP_HOST}:{SMTP_PORT}.</p>', unsafe_allow_html=True)

        default_subject = "Reporte Ejecutivo - Rappi AI Operations Assistant"
        default_body = (
            "Hola,\n\n"
            "Comparto el reporte ejecutivo generado desde el asistente analítico local.\n\n"
            "Saludos."
        )

        recipient = st.text_input("Destinatario", key="report_email_recipient", placeholder="nombre@empresa.com")
        subject = st.text_input("Asunto", key="report_email_subject", value=default_subject)
        body = st.text_area("Mensaje", key="report_email_body", value=default_body, height=120)

        if st.button("Enviar mail con PDF", key=f"send_report_{filename}", use_container_width=True):
            if not recipient.strip():
                st.error("Ingresá un destinatario antes de enviar.")
            else:
                try:
                    send_report_email(
                        smtp_settings=smtp_settings,
                        to_email=recipient.strip(),
                        subject=subject.strip() or default_subject,
                        body=body.strip() or default_body,
                        pdf_bytes=pdf_bytes,
                        filename=filename,
                    )
                    st.success(f"Reporte enviado a {recipient.strip()}")
                except Exception as exc:
                    st.error(f"No se pudo enviar el mail: {exc}")


def render_executive_report_tab() -> None:
    if st.session_state.executive_report is None:
        st.session_state.executive_report = st.session_state.insight_engine.generate_executive_report()

    report = st.session_state.executive_report
    render_executive_report_overview(report)
    render_executive_report_actions(report)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Resumen ejecutivo</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtle">Hallazgos de mayor prioridad seleccionados entre todas las categorías.</div>',
        unsafe_allow_html=True,
    )
    show_insights(report.get("summary", []))
    st.markdown("</div>", unsafe_allow_html=True)

    section_labels = {
        "anomalies": "Anomalías",
        "trend_deterioration": "Deterioro de tendencia",
        "benchmarking": "Benchmarking",
        "correlations": "Correlaciones",
        "opportunities": "Oportunidades",
    }

    for section_key, section_label in section_labels.items():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        items = report.get("sections", {}).get(section_key, [])
        st.markdown(
            f"""
            <div class="report-section-head">
                <div class="section-title" style="margin-bottom:0;">{section_label}</div>
                <div class="report-section-count">{len(items)} hallazgo{'s' if len(items) != 1 else ''}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if items:
            show_insights(items[:5])
            if len(items) > 5:
                with st.expander(f"Ver {len(items) - 5} hallazgos más"):
                    show_insights(items[5:])
        else:
            st.write("No hay hallazgos en esta categoría para el dataset actual.")
        st.markdown("</div>", unsafe_allow_html=True)


def render_chat_shell_header(overview: dict) -> None:
    st.markdown(
        f"""
        <div class="chat-hero">
            <div class="chat-hero-title">Rappi AI Operations Assistant</div>
            <div class="chat-hero-copy">
                Hacé preguntas de negocio en lenguaje natural y obtené respuestas determinísticas, gráficos e insights operativos dentro de un mismo flujo conversacional.
            </div>
            <div class="metric-pill-row">
                <div class="metric-pill">Modelo: {DEFAULT_MODEL_NAME}</div>
                <div class="metric-pill">Países: {overview['metrics_unique_countries']}</div>
                <div class="metric-pill">Ciudades: {overview['metrics_unique_cities']}</div>
                <div class="metric-pill">Zonas: {overview['metrics_unique_zones']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_history_panel() -> None:
    st.markdown('<div class="history-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Historial</div>', unsafe_allow_html=True)

    if not st.session_state.chat_history:
        st.markdown(
            '<div class="section-subtle">Acá van a aparecer las preguntas y respuestas recientes.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for item in reversed(st.session_state.chat_history[-8:]):
        st.markdown(
            f"""
            <div class="history-item">
                <div class="history-q">Pregunta</div>
                <div class="history-a">{item['user']}</div>
                <div style="height:0.45rem;"></div>
                <div class="history-q">Respuesta</div>
                <div class="history-a">{item['assistant']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_examples_sidebar() -> None:
    _EXAMPLES = [
        ("Búsqueda simple", [
            "Cuál es el Gross Profit UE en Bogotá?",
            "Lead Penetration promedio por país",
        ]),
        ("Tendencia", [
            "Tendencia de Perfect Orders en Argentina últimas 5 semanas",
            "Evolución de Turbo Adoption en Colombia",
        ]),
        ("Comparación", [
            "Compara Perfect Orders entre Wealthy y Non Wealthy en México",
            "Perfect Orders por ciudad en Colombia",
        ]),
        ("Ranking", [
            "Top 5 zonas por órdenes en Argentina",
            "Qué zonas tienen más órdenes en Colombia?",
        ]),
        ("Multivariable", [
            "Qué zonas tienen alto Lead Penetration pero bajo Perfect Orders?",
            "Zonas con alto Gross Profit pero bajas órdenes",
        ]),
        ("Anomalías", [
            "Mostrá las zonas problemáticas en México",
            "Dónde cayó más Perfect Orders esta semana?",
        ]),
    ]

    with st.sidebar:
        st.markdown('<div class="sidebar-title">Ejemplos</div>', unsafe_allow_html=True)
        for category, examples in _EXAMPLES:
            st.markdown(f'<div class="sidebar-category">{category}</div>', unsafe_allow_html=True)
            for i, example in enumerate(examples):
                if st.button(example, key=f"sbex_{category}_{i}", use_container_width=True):
                    st.session_state.sidebar_query = example
                    st.rerun()

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        if not OPENAI_API_KEY:
            st.markdown(
                '<div style="font-size:0.78rem;color:rgba(255,200,100,0.75);'
                'background:rgba(255,180,0,0.07);border:1px solid rgba(255,180,0,0.18);'
                'border-radius:8px;padding:0.5rem 0.6rem;margin-bottom:0.8rem;line-height:1.4;">'
                "⚠️ Sin API key — usando parser heurístico. Configurá OPENAI_API_KEY en .env para máxima precisión."
                "</div>",
                unsafe_allow_html=True,
            )

        if st.button("Limpiar conversación", key="clear_chat", use_container_width=True):
            st.session_state.chat_turns = []
            if "memory" in st.session_state:
                st.session_state.memory.clear()
            st.session_state.last_parsed_intent = None
            st.session_state.last_analytical_result = None
            st.session_state.last_executive_answer = None
            st.session_state.last_insights = []
            st.rerun()


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_custom_css()
    initialize_project_folders()

    file_ready = file_exists(RAW_EXCEL_FILE)
    if not file_ready:
        st.error("No encontré el archivo Excel en data/raw/.")
        st.stop()

    data_model = build_data_model()
    overview = get_data_overview(data_model)
    initialize_session_objects(data_model)

    render_examples_sidebar()

    if st.session_state.get("sidebar_query"):
        query = st.session_state.sidebar_query
        st.session_state.sidebar_query = None
        with st.spinner("Analizando tu pregunta..."):
            run_full_query(query)
        st.rerun()

    render_compact_header(overview)

    if not st.session_state.chat_turns:
        st.markdown(
            """
            <div class="chat-intro-card">
                <div class="empty-state">
                    <div class="assistant-intro">
                        <div class="assistant-avatar">R</div>
                        <div>
                            <div class="assistant-name">Rappi Ops Assistant</div>
                            <div class="assistant-copy">Preguntá por tendencias, comparaciones, rankings, zonas problemáticas u oportunidades de crecimiento.</div>
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for turn_index, turn in enumerate(st.session_state.chat_turns):
            render_chat_turn_user(turn["user"])
            render_chat_turn_assistant(turn, turn_index=turn_index)

    user_prompt = st.chat_input("¿Qué querés saber?")
    if user_prompt:
        with st.spinner("Analizando tu pregunta..."):
            run_full_query(user_prompt)
        st.rerun()

    render_bottom_bar()


if __name__ == "__main__":
    main()
