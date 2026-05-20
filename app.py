"""
PMS Execution Semi-Automation Tool — Guardian Capital
Step-based single-page Streamlit app with modern UI.
"""
import io
import pathlib
import base64

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils.isin import load_isin_database, add_isin_entry
from utils.reader import (
    read_research_file, read_bank_book, read_scrip_wise_report,
    read_session_file,
)
from utils.writer import to_excel_bytes, write_allocation_file
from part1.validator import validate_orders
from part1.session import build_session_file
from part1.broker_file import build_broker_file
from part2.parser import parse_ambit_reply, parse_incred_reply, get_incred_cp_codes
from part2.matcher import match_session_to_broker
from part2.allocator import allocate_costs

# ── Page config ──────────────────────────────────────────────────────────────

LOGO_PATH = pathlib.Path(__file__).parent / "assets" / "logo_transparent.png"

st.set_page_config(
    page_title="PMS Execution Tool — Guardian Capital",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap');

/* ── Base ────────────────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', system-ui, sans-serif !important;
    font-weight: 400;
    background-color: #FFFFFF;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none !important; }
[data-testid="collapsedControl"] { display: none; }
.stAppDeployButton { display: none; }

/* Block container — full width, generous padding */
.block-container {
    padding-top: 0.25rem !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
    max-width: 100% !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #F9F7F4; }
::-webkit-scrollbar-thumb { background: rgba(217,178,68,0.55); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #B8922E; }

/* ── Typography ────────────────────────────────── */
h1, h2, h3, h4, .section-title {
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-weight: 600;
    color: #1C1714;
}

/* ── Stepper ─────────────────────────────────── */
.stepper {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.75rem 0 1.1rem 0;
    gap: 0;
}
.step-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 22px;
    border-radius: 100px;
    font-size: 0.73rem;
    font-weight: 400;
    color: #B0A89E;
    background: #FAFAF8;
    border: 1px solid #EAE3D8;
    white-space: nowrap;
    font-family: 'DM Sans', sans-serif;
    letter-spacing: 0.15px;
}
/* Active step — dark fill with gold text: visually dominant */
.step-pill.active {
    background: #1C1714;
    border-color: #1C1714;
    color: #D9B244;
    font-weight: 500;
}
.step-pill.done {
    background: #FAFAF8;
    border-color: #EAE3D8;
    color: #C8BF9A;
}
.step-line {
    width: 52px;
    height: 1px;
    background: #EAE3D8;
    flex-shrink: 0;
}
.step-line.done { background: rgba(217,178,68,0.4); }

/* ── Section header ──────────────────────────── */
.section-header { margin: 0.3rem 0 1.5rem 0; }
.section-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 2.1rem;
    font-weight: 600;
    color: #1C1714;
    margin: 0 0 5px 0;
    line-height: 1.1;
}
.section-sub {
    font-size: 0.84rem;
    color: #958F87;
    font-family: 'DM Sans', sans-serif;
    font-weight: 300;
}

/* ── Field labels — uppercase, muted, tracked ── */
.upload-label {
    font-size: 0.67rem;
    font-weight: 400;
    color: #B0A89E;
    letter-spacing: 0.65px;
    text-transform: uppercase;
    margin-bottom: 7px;
    font-family: 'DM Sans', sans-serif;
}
.upload-required { color: #D9B244; margin-left: 2px; }

/* ── Fade-in animation ───────────────────────── */
@keyframes fadeSlide {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
.fade-in { animation: fadeSlide 0.3s cubic-bezier(0.16,1,0.3,1) both; }

/* ── Metric cards ────────────────────────────── */
.metric-card {
    background: #FFFFFF;
    border: 1px solid #EAE3D8;
    border-radius: 10px;
    padding: 1.6rem 1.8rem;
    text-align: center;
}
.metric-card.green {
    border-color: rgba(22,163,74,0.2);
    background: rgba(22,163,74,0.035);
}
.metric-card.red {
    border-color: rgba(220,38,38,0.18);
    background: rgba(220,38,38,0.035);
}
.metric-val {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 2.8rem;
    font-weight: 600;
    line-height: 1;
    color: #1C1714;
}
.metric-val.green { color: #16a34a; }
.metric-val.red   { color: #dc2626; }
.metric-lbl {
    font-size: 0.67rem;
    color: #958F87;
    margin-top: 8px;
    text-transform: uppercase;
    letter-spacing: 0.65px;
    font-family: 'DM Sans', sans-serif;
    font-weight: 300;
}

/* ── Info banner ─────────────────────────────── */
.info-banner {
    background: #FBF5E3;
    border: 1px solid rgba(217,178,68,0.2);
    border-left: 3px solid #D9B244;
    border-radius: 6px;
    padding: 0.8rem 1rem;
    font-size: 0.83rem;
    color: #6B5718;
    margin-bottom: 1.2rem;
    font-family: 'DM Sans', sans-serif;
    font-weight: 300;
}

/* ── Divider ─────────────────────────────────── */
.gc-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, #EAE3D8 30%, #EAE3D8 70%, transparent);
    margin: 2rem 0;
}

/* ── Buttons ─────────────────────────────────── */
.stButton > button {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 400 !important;
    font-size: 0.85rem !important;
    border-radius: 6px !important;
    letter-spacing: 0.1px !important;
    height: 38px !important;
    transition: all 0.18s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08) !important;
}
/* Primary — gold fill */
[data-testid="baseButton-primary"] {
    background-color: #D9B244 !important;
    border-color: #D9B244 !important;
    color: #FFFFFF !important;
}
[data-testid="baseButton-primary"]:hover {
    background-color: #C4A03C !important;
    border-color: #C4A03C !important;
    box-shadow: 0 4px 18px rgba(217,178,68,0.3) !important;
}
[data-testid="baseButton-primary"]:disabled {
    background-color: #EAE3D8 !important;
    border-color: #EAE3D8 !important;
    color: #B0A89E !important;
    transform: none !important;
    box-shadow: none !important;
}
/* Secondary — outlined */
[data-testid="baseButton-secondary"] {
    background-color: #FFFFFF !important;
    border-color: #D9B244 !important;
    color: #1C1714 !important;
}
[data-testid="baseButton-secondary"]:hover {
    background-color: #FBF5E3 !important;
}

/* ── Download button ──────────────────────────── */
.stDownloadButton > button {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.85rem !important;
    font-weight: 400 !important;
    border-radius: 6px !important;
    height: 38px !important;
    letter-spacing: 0.1px !important;
    transition: all 0.18s ease !important;
}
.stDownloadButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 18px rgba(217,178,68,0.28) !important;
}

/* ── File uploader ────────────────────────────── */
[data-testid="stFileUploader"] { border-radius: 10px; }
[data-testid="stFileUploadDropzone"] {
    border: 1.5px dashed rgba(217,178,68,0.48) !important;
    background: #FAFAF8 !important;
    border-radius: 10px !important;
    min-height: 140px !important;
    padding: 1rem 1.2rem 0.85rem !important;
    cursor: pointer;
    transition: border-color 0.18s ease, background 0.18s ease !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: #D9B244 !important;
    background: linear-gradient(160deg, #FEFCF5 0%, #FAF2DC 100%) !important;
}
/* Uploaded state — solid border, slightly cooler bg */
[data-testid="stFileUploadDropzone"]:has([data-testid="stFileUploadDeleteBtn"]) {
    border: 1px solid #EAE3D8 !important;
    background: #F9F7F4 !important;
}
[data-testid="stFileUploadDropzone"]:has([data-testid="stFileUploadDeleteBtn"]):hover {
    border-color: #D0C8BC !important;
    background: #F5F1EA !important;
}
/* Cloud icon — injected via ::before */
[data-testid="stFileUploaderDropzoneInstructions"] {
    font-family: 'DM Sans', sans-serif !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
}
[data-testid="stFileUploaderDropzoneInstructions"]::before {
    content: '';
    display: block;
    width: 28px;
    height: 28px;
    margin: 0 auto 8px;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='28' viewBox='0 0 24 24' fill='none' stroke='%23D9B244' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='16 16 12 12 8 16'/%3E%3Cline x1='12' y1='12' x2='12' y2='21'/%3E%3Cpath d='M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3'/%3E%3C/svg%3E");
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;
    opacity: 0.75;
}
[data-testid="stFileUploaderDropzoneInstructions"] svg {
    color: rgba(217,178,68,0.7) !important;
    fill: rgba(217,178,68,0.7) !important;
    width: 26px !important;
    height: 26px !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.77rem !important;
    color: #958F87 !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] > div > span:first-child {
    font-size: 0.82rem !important;
    color: #4A4540 !important;
    font-weight: 400 !important;
}
/* Force vertical stacking inside dropzone at any column width */
[data-testid="stFileUploaderDropzoneInstructions"] > div {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    width: 100% !important;
}

/* Browse files */
[data-testid="stFileUploaderDropzoneInstructions"] button,
[data-testid="stFileUploadDropzone"] button {
    border: 1.5px solid #D9B244 !important;
    color: #8A6E1A !important;
    background: transparent !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.75rem !important;
    border-radius: 5px !important;
    padding: 3px 14px !important;
    margin: 7px auto 0 !important;
    cursor: pointer !important;
    transition: background 0.15s ease !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover {
    background: #FBF5E3 !important;
    border-color: #C4A03C !important;
}

/* ── Text / number inputs ────────────────────── */
.stTextInput input, .stNumberInput input {
    border-radius: 6px !important;
    border-color: #EAE3D8 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.87rem !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #D9B244 !important;
    box-shadow: 0 0 0 2px rgba(217,178,68,0.1) !important;
}

/* ── Dataframe / editor ──────────────────────── */
[data-testid="stDataFrame"] iframe,
[data-testid="stDataEditor"] iframe {
    border: 1px solid #EAE3D8 !important;
    border-radius: 8px !important;
}

/* ── Checkbox — warm pill so it reads on white ── */
[data-testid="stCheckbox"] > label {
    background: #F9F7F4 !important;
    border: 1px solid #EAE3D8 !important;
    border-radius: 6px !important;
    padding: 7px 12px 7px 8px !important;
    transition: border-color 0.15s ease, background 0.15s ease !important;
}
[data-testid="stCheckbox"] > label:hover {
    border-color: rgba(217,178,68,0.45) !important;
    background: #FBF5E3 !important;
}
.stCheckbox label span {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.87rem !important;
    color: #4A4540 !important;
}

/* ── Radio ───────────────────────────────────── */
.stRadio label span {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.87rem !important;
}

/* ── Streamlit alerts ────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 6px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.84rem !important;
}
</style>
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data
def get_isin_db():
    return load_isin_database()


def _logo_b64() -> str | None:
    if LOGO_PATH.exists():
        return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return None


def stepper(steps: list[str], current: int):
    """Render a pill-based step indicator. current is 1-indexed."""
    parts = []
    for i, label in enumerate(steps, 1):
        cls = "active" if i == current else ("done" if i < current else "step-pill")
        if i > 1:
            line_cls = "step-line done" if i <= current else "step-line"
            parts.append(f'<div class="{line_cls}"></div>')
        state_cls = "active" if i == current else ("done" if i < current else "")
        dot = '<div class="step-dot"></div>' if i == current else (
              '✓ ' if i < current else f'{i}. ')
        num = "✓" if i < current else str(i)
        parts.append(
            f'<div class="step-pill {state_cls}">'
            f'<span style="font-size:0.75rem;margin-right:4px">{num}</span>'
            f'{label}</div>'
        )
    st.markdown(f'<div class="stepper">{"".join(parts)}</div>', unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    html = f'<div class="section-header fade-in"><div class="section-title">{title}</div>'
    if subtitle:
        html += f'<div class="section-sub">{subtitle}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def divider():
    st.markdown('<div class="gc-divider"></div>', unsafe_allow_html=True)


def nav():
    """Top navigation bar: [Brand: logo + title] ——— [Part 1] [Part 2] [ISIN DB]"""
    logo_b64 = _logo_b64()
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="height:82px;width:auto;flex-shrink:0;display:block;" />'
        if logo_b64 else ""
    )

    section = st.session_state.get("section", "part1")

    # Layout: [brand] [Part 1] [Part 2] [——spacer——] [ISIN DB]
    # Part 1 & Part 2 stay LEFT (grouped with brand); ISIN Database at far RIGHT
    col_brand, col_p1, col_p2, col_spacer, col_isin = st.columns(
        [2.8, 0.65, 0.65, 5.5, 1.1]
    )

    # Brand: logo + title fused in one flex row
    with col_brand:
        brand_html = (
            f'<div style="display:flex;align-items:center;gap:14px;'
            f'padding:3px 0 6px 0">'
            f'{logo_html}'
            f'<div>'
            f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
            f'font-size:1.85rem;font-weight:600;color:#1C1714;line-height:1;'
            f'letter-spacing:-0.25px;white-space:nowrap">PMS Execution Tool</div>'
            f'<div style="font-family:\'DM Sans\',sans-serif;font-size:0.65rem;'
            f'color:#B0A89E;letter-spacing:1px;text-transform:uppercase;'
            f'font-weight:300;margin-top:5px">Guardian Capital</div>'
            f'</div></div>'
        )
        st.markdown(brand_html, unsafe_allow_html=True)

    # Nav buttons — vertically centred against the 88px brand block
    _btn_pad = '<div style="padding-top:26px">'
    _btn_end = '</div>'

    with col_p1:
        st.markdown(_btn_pad, unsafe_allow_html=True)
        p1_style = "primary" if section == "part1" else "secondary"
        if st.button("Part 1", type=p1_style, use_container_width=True, key="nav_p1"):
            st.session_state.section = "part1"
            st.rerun()
        st.markdown(_btn_end, unsafe_allow_html=True)

    with col_p2:
        st.markdown(_btn_pad, unsafe_allow_html=True)
        p2_style = "primary" if section == "part2" else "secondary"
        if st.button("Part 2", type=p2_style, use_container_width=True, key="nav_p2"):
            st.session_state.section = "part2"
            st.rerun()
        st.markdown(_btn_end, unsafe_allow_html=True)

    with col_spacer:
        pass  # intentional — pushes ISIN Database to far right

    with col_isin:
        st.markdown(_btn_pad, unsafe_allow_html=True)
        isin_style = "primary" if section == "isin" else "secondary"
        if st.button("ISIN Database", type=isin_style, use_container_width=True, key="nav_isin"):
            st.session_state.section = "isin"
            st.rerun()
        st.markdown(_btn_end, unsafe_allow_html=True)

    # Separator pulled hard against the nav — aggressive negative margin collapses
    # the ~1rem Streamlit adds between every element pair
    st.markdown(
        '<div style="height:1px;background:linear-gradient(90deg,'
        'transparent,#EAE3D8 15%,#EAE3D8 85%,transparent);'
        'margin:-0.6rem 0 1.4rem 0"></div>',
        unsafe_allow_html=True,
    )


# ── Part 1 — Step 1: Upload ───────────────────────────────────────────────────

def p1_upload():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)

    # Read batch state from session_state so layout (3 vs 4 cards) is decided
    # BEFORE rendering widgets — avoids chicken-and-egg ordering problem.
    batch_mode = st.session_state.get("p1_second_batch", False)

    # ── Page title ─────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="margin:0.3rem 0 1.4rem 0;text-align:center">'
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;'
        'margin-bottom:5px">Upload Files</div>'
        '<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
        'font-weight:300">Provide the three mandatory Orbis reports and configure batch settings.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Upload cards (3 or 4 depending on batch_mode) ─────────────────────────
    existing_file = None

    if not batch_mode:
        _CARD_COLS = [1, 2, 0.4, 2, 0.4, 2, 1]
        _, col1, _, col2, _, col3, _ = st.columns(_CARD_COLS)
        with col1:
            st.markdown('<div class="upload-label">Research Team File <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            research_file = st.file_uploader("Research Team File", type=["xlsx"], key="p1_research", label_visibility="collapsed")
        with col2:
            st.markdown('<div class="upload-label">Orbis Bank Book <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            bank_file = st.file_uploader("Orbis Bank Book", type=["xlsx"], key="p1_bank", label_visibility="collapsed")
        with col3:
            st.markdown('<div class="upload-label">Scrip-wise Report <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            scrip_file = st.file_uploader("Scrip-wise Report", type=["xls"], key="p1_scrip", label_visibility="collapsed")
    else:
        _CARD_COLS = [0.5, 2, 0.32, 2, 0.32, 2, 0.32, 2, 0.5]
        _, col1, _, col2, _, col3, _, col4, _ = st.columns(_CARD_COLS)
        with col1:
            st.markdown('<div class="upload-label">Research Team File <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            research_file = st.file_uploader("Research Team File", type=["xlsx"], key="p1_research", label_visibility="collapsed")
        with col2:
            st.markdown('<div class="upload-label">Orbis Bank Book <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            bank_file = st.file_uploader("Orbis Bank Book", type=["xlsx"], key="p1_bank", label_visibility="collapsed")
        with col3:
            st.markdown('<div class="upload-label">Scrip-wise Report <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            scrip_file = st.file_uploader("Scrip-wise Report", type=["xls"], key="p1_scrip", label_visibility="collapsed")
        with col4:
            st.markdown('<div class="upload-label">Existing Session File <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            existing_file = st.file_uploader("Existing Session File", type=["xlsx"], key="p1_existing", label_visibility="collapsed")

    # ── Settings row 1 — Multiple Batches + Price Tolerance, centered together
    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)

    _, col_cb, _, col_tol, _ = st.columns([2.2, 2, 0.4, 2, 2.2])

    with col_cb:
        st.markdown('<div style="padding-top:18px">', unsafe_allow_html=True)
        second_batch = st.checkbox(
            "Multiple Batches of the Day",
            help="Check if orders were already sent earlier today. Committed cash will be deducted.",
            key="p1_second_batch",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with col_tol:
        st.markdown('<div class="upload-label">Price Tolerance %</div>', unsafe_allow_html=True)
        tolerance = st.number_input(
            "Tolerance", min_value=0.0, max_value=100.0, value=0.0, step=0.5,
            key="p1_tolerance", label_visibility="collapsed",
        )
        if tolerance > 5.0:
            st.markdown(
                f'<div style="font-size:0.72rem;color:#92400e;background:#FEF3C7;'
                f'border:1px solid rgba(217,178,68,0.35);border-radius:4px;'
                f'padding:4px 9px;margin-top:5px;font-family:\'DM Sans\',sans-serif;">'
                f'⚠ High tolerance — {tolerance:.1f}%</div>',
                unsafe_allow_html=True,
            )

    all_uploaded = bool(research_file and bank_file and scrip_file)
    if batch_mode and not existing_file:
        all_uploaded = False

    # ── Settings row 2 — Validate Orders button, right-aligned (under card 3)
    st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)
    _, col_btn, _ = st.columns([5.8, 2, 1])

    with col_btn:
        validate_clicked = st.button(
            "Validate Orders →",
            type="primary",
            disabled=not all_uploaded,
            key="p1_validate_btn",
            use_container_width=True,
        )
        if not all_uploaded:
            st.markdown(
                '<div style="font-size:0.72rem;color:#B0A89E;text-align:center;'
                'margin-top:5px;font-family:\'DM Sans\',sans-serif;font-weight:300">'
                'Upload all required files to continue</div>',
                unsafe_allow_html=True,
            )

    if validate_clicked:
        with st.spinner("Parsing files and validating orders..."):
            try:
                isin_db = get_isin_db()
                research_df = read_research_file(research_file)
                bank_book = read_bank_book(bank_file)
                scrip_df = read_scrip_wise_report(scrip_file)
                existing_session_df = read_session_file(existing_file) if existing_file else None
                validation_df = validate_orders(
                    research_df=research_df,
                    bank_book=bank_book,
                    scrip_df=scrip_df,
                    isin_db=isin_db,
                    existing_session_df=existing_session_df,
                    tolerance=tolerance,
                )
                st.session_state["validation_df"] = validation_df
                st.session_state["existing_session_df"] = existing_session_df
                st.session_state["p1_step"] = 2
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.markdown('</div>', unsafe_allow_html=True)


# ── Part 1 — Step 2: Validate ─────────────────────────────────────────────────

def p1_validate():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    vdf = st.session_state["validation_df"].copy()
    n_green = int((vdf["Status"] == "GREEN").sum())
    n_red   = int((vdf["Status"] == "RED").sum())
    n_total = len(vdf)
    n_tickers = vdf["Ticker"].nunique()

    # ── Header + inline status pills ──────────────────────────────────────────
    st.markdown(
        f'<div style="margin:0.3rem 0 1.4rem 0;display:flex;align-items:flex-end;'
        f'gap:20px;flex-wrap:wrap">'
        f'<div>'
        f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;margin-bottom:5px">'
        f'Validate Orders</div>'
        f'<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
        f'font-weight:300">{n_total} orders across {n_tickers} stocks — '
        f'review and confirm before generating files.</div>'
        f'</div>'
        f'<div style="display:flex;gap:8px;padding-bottom:4px">'
        f'<div style="background:rgba(22,163,74,0.07);border:1px solid rgba(22,163,74,0.22);'
        f'border-radius:20px;padding:4px 14px;font-size:0.78rem;color:#16a34a;'
        f'font-family:\'DM Sans\',sans-serif;font-weight:500;white-space:nowrap">'
        f'✓ {n_green} ready</div>'
        f'<div style="background:rgba(220,38,38,0.05);border:1px solid rgba(220,38,38,0.18);'
        f'border-radius:20px;padding:4px 14px;font-size:0.78rem;color:#dc2626;'
        f'font-family:\'DM Sans\',sans-serif;font-weight:500;white-space:nowrap">'
        f'✕ {n_red} blocked</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── Resolve button override BEFORE building editor_df ─────────────────────
    override = st.session_state.pop("_include_override", None)

    # Build editor DataFrame — includes Context (units held / available cash)
    context_col = "Context" if "Context" in vdf.columns else None
    base_cols = ["S.No", "Client", "Ticker", "Direction", "Qty", "Ref Price", "Status", "Reason"]
    if context_col:
        base_cols.append(context_col)
    editor_df = vdf[base_cols].copy()
    if context_col:
        editor_df.rename(columns={"Context": "Units Held / Cash"}, inplace=True)
    editor_df.insert(0, "Include", vdf["Status"] == "GREEN")

    if override == "red_out":
        editor_df["Include"] = vdf["Status"] == "GREEN"
    elif override == "all_out":
        editor_df["Include"] = False

    # ── Action buttons (above table) ──────────────────────────────────────────
    ab1, ab2, ab_space = st.columns([1.3, 1.6, 6])
    with ab1:
        if st.button("Exclude all red", key="p1_excl_red", use_container_width=True):
            st.session_state["_include_override"] = "red_out"
            st.rerun()
    with ab2:
        if st.button("Exclude entire batch", key="p1_excl_all", use_container_width=True):
            st.session_state["_include_override"] = "all_out"
            st.rerun()

    st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

    # ── Editable table ────────────────────────────────────────────────────────
    col_cfg = {
        "Include":        st.column_config.CheckboxColumn("✓", default=True, width="small"),
        "S.No":           st.column_config.NumberColumn("No.", width="small"),
        "Client":         st.column_config.TextColumn("Client", width="medium"),
        "Ticker":         st.column_config.TextColumn("Ticker", width="small"),
        "Direction":      st.column_config.TextColumn("Dir", width="small"),
        "Qty":            st.column_config.NumberColumn("Qty", width="small"),
        "Ref Price":      st.column_config.NumberColumn("Ref Price", format="%.2f", width="small"),
        "Status":         st.column_config.TextColumn("Status", disabled=True, width="small"),
        "Reason":         st.column_config.TextColumn("Reason", disabled=True, width="large"),
        "Units Held / Cash": st.column_config.TextColumn("Context", disabled=True, width="medium"),
    }
    disabled_cols = [c for c in editor_df.columns if c != "Include"]

    edited = st.data_editor(
        editor_df,
        column_config=col_cfg,
        disabled=disabled_cols,
        hide_index=True,
        use_container_width=True,
        key="p1_editor",
    )

    red_included = int(((edited["Include"] == True) & (vdf["Status"] == "RED")).sum())
    n_included   = int(edited["Include"].sum())

    # Inline error if red rows are still checked
    if red_included > 0:
        st.markdown(
            f'<div style="background:rgba(220,38,38,0.05);'
            f'border:1px solid rgba(220,38,38,0.18);border-left:3px solid #dc2626;'
            f'border-radius:6px;padding:0.7rem 1rem;font-size:0.82rem;color:#b91c1c;'
            f'margin-top:0.6rem;font-family:\'DM Sans\',sans-serif;font-weight:400">'
            f'⚠  {red_included} blocked row(s) still marked as included — '
            f'uncheck or click "Exclude all red" above.</div>',
            unsafe_allow_html=True,
        )

    # Caption: red rows cannot be fixed here
    if n_red > 0:
        st.caption("Red rows cannot be included — fix the underlying issue and re-upload the research file.")

    # ── Bottom action row ─────────────────────────────────────────────────────
    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    col_back, _, col_gen = st.columns([1, 4.5, 2])

    with col_back:
        if st.button("← Back", key="p1_back_2", use_container_width=True):
            st.session_state["p1_step"] = 1
            st.rerun()

    with col_gen:
        can_generate = (red_included == 0) and (n_included > 0)
        gen_label = (
            f"Generate files ({n_included} orders) →"
            if n_included > 0 else "Select at least one order"
        )
        if st.button(gen_label, type="primary", disabled=not can_generate,
                     key="p1_gen_btn", use_container_width=True):
            with st.spinner("Building session file and broker file..."):
                included_idx = edited[edited["Include"] == True].index
                included_df  = vdf.loc[included_idx].copy()

                session_df = build_session_file(
                    included_df=included_df,
                    existing_session_df=st.session_state.get("existing_session_df"),
                )
                broker_df = build_broker_file(included_df)

                st.session_state["session_df"]       = session_df
                st.session_state["broker_file_df"]   = broker_df
                st.session_state["n_included"]       = n_included

                blank_cp = (
                    (session_df["CP Code"].astype(str).str.strip() == "")
                    | (session_df["CP Code"].astype(str).str.lower() == "nan")
                )
                st.session_state["blank_cp_count"] = int(blank_cp.sum())
                st.session_state["p1_step"] = 3
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ── Part 1 — Step 3: Download ─────────────────────────────────────────────────

def p1_export():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    session_df     = st.session_state["session_df"]
    broker_file_df = st.session_state["broker_file_df"]
    n_included     = st.session_state["n_included"]
    blank_cp       = st.session_state.get("blank_cp_count", 0)
    n_stocks       = broker_file_df["Ticker"].nunique()
    batch_num      = int(session_df["Batch"].max())

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="margin:0.3rem 0 1.4rem 0">'
        f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;margin-bottom:5px">'
        f'Files Ready</div>'
        f'<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
        f'font-weight:300">{n_included} orders · {n_stocks} stocks · Batch {batch_num}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # CP Code warning banner
    if blank_cp > 0:
        st.markdown(
            f'<div class="info-banner">⚠  {blank_cp} row(s) in the session file have a blank CP Code. '
            f'Fill these in Orbis before uploading to Part 2.</div>',
            unsafe_allow_html=True,
        )

    session_bytes = to_excel_bytes(session_df, "Session")
    broker_bytes  = to_excel_bytes(broker_file_df, "Broker File")

    # ── Download cards ────────────────────────────────────────────────────────
    _, dl1, _, dl2, _ = st.columns([1, 2, 0.4, 2, 3])

    with dl1:
        st.markdown(
            '<div style="background:#FAFAF8;border:1px solid #EAE3D8;'
            'border-left:3px solid #D9B244;border-radius:10px;'
            'padding:1.2rem 1.4rem 1rem">'
            '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:1.1rem;'
            'font-weight:600;color:#1C1714;margin-bottom:3px">Session File</div>'
            f'<div style="font-size:0.72rem;color:#B0A89E;font-family:\'DM Sans\',sans-serif;'
            f'letter-spacing:0.4px;text-transform:uppercase;margin-bottom:1rem">'
            f'{len(session_df)} rows · Batch {batch_num}</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇  Download session_file.xlsx",
            data=session_bytes,
            file_name="session_file.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
            key="dl_session",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with dl2:
        st.markdown(
            '<div style="background:#FAFAF8;border:1px solid #EAE3D8;'
            'border-left:3px solid #D9B244;border-radius:10px;'
            'padding:1.2rem 1.4rem 1rem">'
            '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:1.1rem;'
            'font-weight:600;color:#1C1714;margin-bottom:3px">Broker File</div>'
            f'<div style="font-size:0.72rem;color:#B0A89E;font-family:\'DM Sans\',sans-serif;'
            f'letter-spacing:0.4px;text-transform:uppercase;margin-bottom:1rem">'
            f'{n_stocks} stocks · send to broker</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇  Download broker_file.xlsx",
            data=broker_bytes,
            file_name="broker_file.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
            key="dl_broker",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Broker file preview ───────────────────────────────────────────────────
    st.markdown('<div style="height:1.6rem"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.67rem;color:#B0A89E;font-family:\'DM Sans\',sans-serif;'
        'font-weight:400;letter-spacing:0.65px;text-transform:uppercase;margin-bottom:8px">'
        'Broker File Preview</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(broker_file_df, use_container_width=True, hide_index=True)

    # ── Bottom action row ─────────────────────────────────────────────────────
    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    col_back, _, col_new = st.columns([1, 4.5, 2])
    with col_back:
        if st.button("← Back", key="p1_back_3", use_container_width=True):
            st.session_state["p1_step"] = 2
            st.rerun()
    with col_new:
        if st.button("↺  New validation", key="p1_restart", use_container_width=True):
            for k in ["validation_df", "session_df", "broker_file_df",
                      "existing_session_df", "n_included", "blank_cp_count"]:
                st.session_state.pop(k, None)
            st.session_state["p1_step"] = 1
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ── Part 2 — Step 1: Upload ───────────────────────────────────────────────────

def p2_upload():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="margin:0.3rem 0 1.4rem 0">'
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;margin-bottom:5px">'
        'Upload & Configure</div>'
        '<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
        'font-weight:300">Provide the session file and the broker execution reply.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Two upload cards — margin cols sized so each card ≈ same px as Part 1 ──
    # Part 1 uses [1,2,0.4,2,0.4,2,1]=8.8 total; card=2/8.8≈22.7% of page.
    # Here: [2.2,2,0.4,2,2.2]=8.8 total → same 22.7% per card, stays vertical.
    _, col1, _, col2, _ = st.columns([2.2, 2, 0.4, 2, 2.2])
    with col1:
        st.markdown(
            '<div class="upload-label">Session File <span class="upload-required">*</span></div>',
            unsafe_allow_html=True,
        )
        session_file = st.file_uploader(
            "Session File", type=["xlsx"], key="p2_session", label_visibility="collapsed",
        )
    with col2:
        st.markdown(
            '<div class="upload-label">Broker Reply <span class="upload-required">*</span></div>',
            unsafe_allow_html=True,
        )
        broker_file = st.file_uploader(
            "Broker Reply", type=["xlsx"], key="p2_broker", label_visibility="collapsed",
        )

    # ── Settings row — broker selector + process button ───────────────────────
    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)

    _, col_broker, _, col_btn, _ = st.columns([2.2, 2, 0.4, 2, 2.2])

    with col_broker:
        st.markdown('<div class="upload-label">Broker</div>', unsafe_allow_html=True)
        broker_choice = st.radio(
            "Broker", ["Ambit", "InCred"], horizontal=True,
            key="p2_broker_choice", label_visibility="collapsed",
        )

    can_process = bool(session_file and broker_file)

    with col_btn:
        st.markdown('<div style="padding-top:18px">', unsafe_allow_html=True)
        process_clicked = st.button(
            "Process Allocation →",
            type="primary",
            disabled=not can_process,
            key="p2_process_btn",
            use_container_width=True,
        )
        if not can_process:
            st.markdown(
                '<div style="font-size:0.72rem;color:#B0A89E;text-align:center;'
                'margin-top:5px;font-family:\'DM Sans\',sans-serif;font-weight:300">'
                'Upload both files to continue</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    if process_clicked:
        with st.spinner("Matching executions and allocating costs..."):
            try:
                session_df = read_session_file(session_file)

                incred_cp_codes = None
                if broker_choice == "Ambit":
                    broker_df = parse_ambit_reply(broker_file)
                else:
                    broker_df = parse_incred_reply(broker_file)
                    broker_file.seek(0)
                    incred_cp_codes = get_incred_cp_codes(broker_file)

                matched_df, not_executed, unexpected = match_session_to_broker(session_df, broker_df)

                allocation_df = allocate_costs(
                    matched_session_df=matched_df,
                    broker_df=broker_df,
                    incred_cp_codes=incred_cp_codes,
                )

                st.session_state["allocation_df"]  = allocation_df
                st.session_state["p2_not_exec"]    = not_executed
                st.session_state["p2_unexpected"]  = unexpected
                st.session_state["p2_step"]        = 2
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.markdown('</div>', unsafe_allow_html=True)


# ── Part 2 — Step 2: Results ──────────────────────────────────────────────────

def p2_results():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    allocation_df = st.session_state["allocation_df"]
    not_executed  = st.session_state.get("p2_not_exec", [])
    unexpected    = st.session_state.get("p2_unexpected", [])

    n_clients = len(allocation_df)
    n_stocks  = allocation_df["ISIN No"].nunique()

    # ── Header + inline pills ─────────────────────────────────────────────────
    st.markdown(
        f'<div style="margin:0.3rem 0 1.4rem 0;display:flex;align-items:flex-end;'
        f'gap:20px;flex-wrap:wrap">'
        f'<div>'
        f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;margin-bottom:5px">'
        f'Allocation Complete</div>'
        f'<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
        f'font-weight:300">Cost allocation ready for Orbis upload.</div>'
        f'</div>'
        f'<div style="display:flex;gap:8px;padding-bottom:4px">'
        f'<div style="background:rgba(22,163,74,0.07);border:1px solid rgba(22,163,74,0.22);'
        f'border-radius:20px;padding:4px 14px;font-size:0.78rem;color:#16a34a;'
        f'font-family:\'DM Sans\',sans-serif;font-weight:500;white-space:nowrap">'
        f'{n_stocks} stocks</div>'
        f'<div style="background:#F9F7F4;border:1px solid #EAE3D8;'
        f'border-radius:20px;padding:4px 14px;font-size:0.78rem;color:#4A4540;'
        f'font-family:\'DM Sans\',sans-serif;font-weight:400;white-space:nowrap">'
        f'{n_clients} client rows</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── Warnings ─────────────────────────────────────────────────────────────
    if not_executed:
        isins = "  ·  ".join(not_executed)
        st.markdown(
            f'<div style="background:#FBF5E3;border:1px solid rgba(217,178,68,0.3);'
            f'border-left:3px solid #D9B244;border-radius:6px;padding:0.75rem 1rem;'
            f'font-size:0.82rem;color:#6B5718;margin-bottom:0.6rem;'
            f'font-family:\'DM Sans\',sans-serif;font-weight:400">'
            f'⚠  {len(not_executed)} ISIN(s) in the session file were <strong>not executed</strong> '
            f'by the broker and are excluded from allocation:<br>'
            f'<span style="font-family:monospace;font-size:0.78rem">{isins}</span></div>',
            unsafe_allow_html=True,
        )
    if unexpected:
        isins = "  ·  ".join(unexpected)
        st.markdown(
            f'<div style="background:rgba(220,38,38,0.04);border:1px solid rgba(220,38,38,0.18);'
            f'border-left:3px solid #dc2626;border-radius:6px;padding:0.75rem 1rem;'
            f'font-size:0.82rem;color:#b91c1c;margin-bottom:0.6rem;'
            f'font-family:\'DM Sans\',sans-serif;font-weight:400">'
            f'⚠  {len(unexpected)} ISIN(s) appeared in the broker reply but were <strong>not in the '
            f'session file</strong>:<br>'
            f'<span style="font-family:monospace;font-size:0.78rem">{isins}</span></div>',
            unsafe_allow_html=True,
        )

    # ── Allocation summary table ──────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.67rem;color:#B0A89E;font-family:\'DM Sans\',sans-serif;'
        'font-weight:400;letter-spacing:0.65px;text-transform:uppercase;margin-bottom:8px">'
        'Allocation Summary</div>',
        unsafe_allow_html=True,
    )
    summary = (
        allocation_df
        .groupby(["ISIN No", "Buy/ Sell"])
        .agg(
            Clients=("CustomerNo", "count"),
            Total_Qty=("Input Quantity", "sum"),
            Total_Net=("InputNetAmount", "sum"),
        )
        .reset_index()
        .rename(columns={"ISIN No": "ISIN", "Buy/ Sell": "Direction",
                         "Total_Qty": "Total Qty", "Total_Net": "Total Net (₹)"})
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)

    # ── Download card ─────────────────────────────────────────────────────────
    st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)
    alloc_bytes = write_allocation_file(allocation_df)

    _, dl_col, _ = st.columns([1.5, 2, 4])
    with dl_col:
        st.markdown(
            '<div style="background:#FAFAF8;border:1px solid #EAE3D8;'
            'border-left:3px solid #D9B244;border-radius:10px;'
            'padding:1.2rem 1.4rem 1rem">'
            '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:1.1rem;'
            'font-weight:600;color:#1C1714;margin-bottom:3px">Orbis Allocation File</div>'
            f'<div style="font-size:0.72rem;color:#B0A89E;font-family:\'DM Sans\',sans-serif;'
            f'letter-spacing:0.4px;text-transform:uppercase;margin-bottom:1rem">'
            f'{n_clients} rows · 19 columns · ready for upload</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇  Download orbis_allocation.xlsx",
            data=alloc_bytes,
            file_name="orbis_allocation.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
            key="dl_alloc",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Bottom action row ─────────────────────────────────────────────────────
    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    col_back, _, col_new = st.columns([1, 4.5, 2])
    with col_back:
        if st.button("← Back", key="p2_back", use_container_width=True):
            st.session_state["p2_step"] = 1
            st.rerun()
    with col_new:
        if st.button("↺  Process another", key="p2_restart", use_container_width=True):
            for k in ["allocation_df", "p2_not_exec", "p2_unexpected"]:
                st.session_state.pop(k, None)
            st.session_state["p2_step"] = 1
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ── ISIN Database ─────────────────────────────────────────────────────────────

def isin_page():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    isin_db = get_isin_db()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="margin:0.3rem 0 1.4rem 0">'
        f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;margin-bottom:5px">'
        f'ISIN Database</div>'
        f'<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
        f'font-weight:300">{len(isin_db):,} listed companies · NSE + BSE universe</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Search bar ────────────────────────────────────────────────────────────
    search_col, count_col = st.columns([4, 1])
    with search_col:
        search = st.text_input(
            "Search",
            placeholder="Company name, NSE code, BSE code, or ISIN…",
            key="isin_search",
            label_visibility="collapsed",
        )
    # Live-search JS debounce — triggers Enter after 350 ms of inactivity
    components.html(
        """
        <script>
        (function() {
            var timer;
            function setup() {
                try {
                    var parent = window.parent.document;
                    var inputs = parent.querySelectorAll('input[type=text], input:not([type])');
                    var inp = null;
                    for (var i = 0; i < inputs.length; i++) {
                        if (inputs[i].placeholder && inputs[i].placeholder.indexOf('Company name') !== -1) {
                            inp = inputs[i];
                            break;
                        }
                    }
                    if (!inp) { setTimeout(setup, 250); return; }
                    if (inp._liveSearch) return;
                    inp._liveSearch = true;
                    inp.addEventListener('input', function() {
                        clearTimeout(timer);
                        timer = setTimeout(function() {
                            ['keydown','keypress','keyup'].forEach(function(t) {
                                inp.dispatchEvent(new KeyboardEvent(t, {
                                    key: 'Enter', code: 'Enter', keyCode: 13,
                                    which: 13, bubbles: true, cancelable: true
                                }));
                            });
                        }, 350);
                    });
                } catch(e) { /* cross-origin guard */ }
            }
            setup();
        })();
        </script>
        """,
        height=0,
    )

    if search.strip():
        q = search.strip()
        mask = (
            isin_db["Name"].str.contains(q, case=False, na=False)
            | isin_db["NSE Code"].str.contains(q, case=False, na=False)
            | isin_db["BSE Code"].str.contains(q, case=False, na=False)
            | isin_db["ISIN Code"].str.contains(q, case=False, na=False)
        )
        display_db = isin_db[mask]
    else:
        display_db = isin_db

    with count_col:
        st.markdown(
            f'<div style="padding-top:8px;font-size:0.76rem;color:#B0A89E;'
            f'text-align:right;font-family:\'DM Sans\',sans-serif;font-weight:300">'
            f'{len(display_db):,} result(s)</div>',
            unsafe_allow_html=True,
        )

    st.dataframe(display_db, use_container_width=True, hide_index=True, height=400)

    # ── Add New Entry ─────────────────────────────────────────────────────────
    st.markdown(
        '<div style="height:1px;background:linear-gradient(90deg,transparent,'
        '#EAE3D8 20%,#EAE3D8 80%,transparent);margin:1.8rem 0 1.5rem 0"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:1.4rem;'
        'font-weight:600;color:#1C1714;margin-bottom:3px">Add New Listing</div>'
        '<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
        'font-weight:300;margin-bottom:1rem">For newly listed companies not yet in the database.</div>',
        unsafe_allow_html=True,
    )

    with st.form("add_isin_form", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns([2.2, 1.2, 1.2, 1.6, 1.2])
        new_name = c1.text_input("Company Name")
        new_nse  = c2.text_input("NSE Code")
        new_bse  = c3.text_input("BSE Code")
        new_isin = c4.text_input("ISIN Code *")
        c5.markdown('<div style="padding-top:26px"></div>', unsafe_allow_html=True)
        submitted = c5.form_submit_button("+ Add Entry", type="primary", use_container_width=True)

    if submitted:
        if not new_isin.strip():
            st.error("ISIN Code is required.")
        else:
            try:
                add_isin_entry(new_name, new_nse, new_bse, new_isin)
                st.cache_data.clear()
                st.success(f"✓  Added: {new_name or '—'}  ({new_isin.strip()})")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.markdown('</div>', unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.markdown(CSS, unsafe_allow_html=True)

    # Initialise state
    if "section" not in st.session_state:
        st.session_state.section = "part1"
    if "p1_step" not in st.session_state:
        st.session_state.p1_step = 1
    if "p2_step" not in st.session_state:
        st.session_state.p2_step = 1

    nav()

    section = st.session_state.section

    if section == "part1":
        step = st.session_state.p1_step
        stepper(["Upload Files", "Validate Orders", "Download"], step)
        if step == 1:
            p1_upload()
        elif step == 2:
            p1_validate()
        elif step == 3:
            p1_export()

    elif section == "part2":
        step = st.session_state.p2_step
        stepper(["Upload & Configure", "Review & Download"], step)
        if step == 1:
            p2_upload()
        elif step == 2:
            p2_results()

    elif section == "isin":
        isin_page()


main()
