"""
PMS Execution Semi-Automation Tool - Guardian Capital
Step-based single-page Streamlit app with modern UI.
"""
import io
import pathlib
import base64

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils.isin import load_isin_database, add_isin_entry, bulk_update_isin_database
from utils.reader import (
    read_research_file, read_bank_book, read_scrip_wise_report,
    read_session_file,
)
from utils.writer import to_excel_bytes, write_session_file, write_allocation_file
from part1.validator import validate_orders
from part1.session import build_session_file
from part1.broker_file import build_broker_file
from part2.parser import parse_ambit_reply, parse_incred_reply, get_incred_cp_codes
from part2.matcher import match_session_to_broker
from part2.allocator import allocate_costs

# ── Page config ──────────────────────────────────────────────────────────────

LOGO_PATH = pathlib.Path(__file__).parent / "assets" / "logo_transparent.png"

st.set_page_config(
    page_title="PMS Execution Tool - Guardian Capital",
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

/* Block container - full width, generous padding */
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
/* Active step - dark fill with gold text: visually dominant */
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

/* ── Field labels - uppercase, muted, tracked ── */
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
/* Primary - gold fill */
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
/* Secondary - warm gold-outlined so it reads as a clickable button */
[data-testid="baseButton-secondary"] {
    background: linear-gradient(180deg, #FEFCF6 0%, #F9F3E3 100%) !important;
    border: 1.5px solid #D9B244 !important;
    color: #7A5F1A !important;
}
[data-testid="baseButton-secondary"]:hover {
    background: linear-gradient(180deg, #FBF5E3 0%, #F3EAD0 100%) !important;
    border-color: #C4A03C !important;
    color: #5C4812 !important;
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

/* ── Empty state ─── */
[data-testid="stFileUploaderDropzone"] {
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
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #D9B244 !important;
    background: linear-gradient(160deg, #FEFCF5 0%, #FAF2DC 100%) !important;
}
/* Browse button span - always centered */
[data-testid="stFileUploaderDropzone"] > span {
    width: 100% !important;
    display: flex !important;
    justify-content: center !important;
}

/* ── Uploaded state: dropzone keeps its card shape; file list overlays top ─── */
/* Wrapper is a relative container so the file list can be absolute-positioned */
[data-testid="stFileUploader"]:has([data-testid="stFileUploaderFile"]) {
    position: relative !important;
}
/* Dropzone retains all card dimensions - only border + bg change on upload */
[data-testid="stFileUploader"]:has([data-testid="stFileUploaderFile"]) [data-testid="stFileUploaderDropzone"] {
    border: 1px solid #EAE3D8 !important;
    background: #F9F7F4 !important;
    justify-content: flex-end !important;
    cursor: default !important;
    transition: none !important;
}
/* Suppress hover glow when a file is already loaded */
[data-testid="stFileUploader"]:has([data-testid="stFileUploaderFile"]) [data-testid="stFileUploaderDropzone"]:hover {
    border-color: #EAE3D8 !important;
    background: #F9F7F4 !important;
}
/* Hide drag-drop instructions - Browse files button stays in dropzone */
[data-testid="stFileUploader"]:has([data-testid="stFileUploaderFile"]) [data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}
/* File list overlay: covers card from top down to just above Browse files button */
[data-testid="stFileUploader"]:has([data-testid="stFileUploaderFile"]) > div:last-of-type {
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 2.6rem !important;  /* clears the Browse files button at card bottom */
    padding: 0 !important;
    z-index: 2 !important;
    display: flex !important;
    align-items: center !important;      /* center file info vertically */
    justify-content: center !important;
}
/* Delete × - pinned to top-right of the overlay (= top-right of card) */
[data-testid="stFileUploaderDeleteBtn"] {
    position: absolute !important;
    top: 0.75rem !important;
    right: 0.85rem !important;
    z-index: 3 !important;
}
/* File row - icon + name centered; × is out of flow so it doesn't offset centering */
[data-testid="stFileUploaderFile"] {
    display: flex !important;
    align-items: flex-start !important;
    justify-content: center !important;
    gap: 8px !important;
    padding: 0 1.2rem !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.82rem !important;
    color: #4A4540 !important;
    min-width: 0 !important;
    width: 100% !important;
}
/* File name + size block - wraps long names inside the card */
[data-testid="stFileUploaderFileName"] {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 400 !important;
    color: #1C1714 !important;
    white-space: normal !important;
    word-break: break-word !important;
    text-align: left !important;
    min-width: 0 !important;
    flex: 1 !important;
}
[data-testid="stFileUploaderFileSize"] {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.72rem !important;
    color: #958F87 !important;
}
/* Delete × button styling */
[data-testid="stFileUploaderDeleteBtn"] button {
    color: #B0A89E !important;
    background: transparent !important;
    border: none !important;
    padding: 2px 4px !important;
    cursor: pointer !important;
}
[data-testid="stFileUploaderDeleteBtn"] button:hover {
    color: #dc2626 !important;
}
/* ── Update ISIN Database - file uploader disguised as a muted button ─── */
/* Class stamped by JS directly onto the stFileUploader element */
[data-testid="stFileUploader"].isin-uploader-btn {
    min-height: unset !important;
}
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderDropzone"] {
    min-height: 42px !important;
    max-height: 42px !important;
    padding: 0 !important;
    border: 1.5px solid #D5CFC7 !important;
    background: #F0EDE8 !important;
    border-radius: 6px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: background 0.18s ease, border-color 0.18s ease !important;
    cursor: pointer !important;
}
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderDropzone"]:hover {
    background: linear-gradient(180deg, #FEFCF6 0%, #F9F3E3 100%) !important;
    border-color: #D9B244 !important;
}
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderDropzone"] > span {
    width: 100% !important;
    display: flex !important;
    justify-content: center !important;
}
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderDropzone"] button {
    font-size: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    width: 100% !important;
    height: 42px !important;
    cursor: pointer !important;
    position: relative !important;
}
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderDropzone"] button::after {
    content: "Update ISIN Database" !important;
    font-size: 0.8rem !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 400 !important;
    color: #958F87 !important;
    position: absolute !important;
    left: 50% !important;
    top: calc(50% - 2px) !important;
    transform: translate(-50%, -50%) !important;
    white-space: nowrap !important;
}
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderDropzone"]:hover button::after {
    color: #7A5F1A !important;
}
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderFile"],
[data-testid="stFileUploader"].isin-uploader-btn [data-testid="stFileUploaderDeleteBtn"],
[data-testid="stFileUploader"].isin-uploader-btn > div:last-of-type {
    display: none !important;
}

/* Cloud icon - injected via ::before */
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

/* Browse files - targets button inside the dropzone's sibling <span> */
[data-testid="stFileUploaderDropzone"] button {
    display: block !important;
    width: fit-content !important;
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
[data-testid="stFileUploaderDropzone"] button:hover {
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
/* Darker column headers - target the header row overlay that sits above the canvas */
[data-testid="stDataFrame"] [role="columnheader"],
[data-testid="stDataEditor"] [role="columnheader"] {
    background: #E8E0D2 !important;
    color: #1C1714 !important;
    font-weight: 500 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.2px !important;
}
[data-testid="stDataFrame"] [role="columnheader"] span,
[data-testid="stDataEditor"] [role="columnheader"] span {
    color: #1C1714 !important;
    font-weight: 500 !important;
}

/* ── Checkbox - warm pill so it reads on white ── */
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

/* ── Hide "Press Enter to apply" hint on all text inputs ── */
[data-testid="InputInstructions"] { display: none !important; }
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
    """Top navigation bar: [Brand: logo + title] --- [Part 1] [Part 2] [ISIN DB]"""
    logo_b64 = _logo_b64()
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="height:82px;width:auto;flex-shrink:0;display:block;" />'
        if logo_b64 else ""
    )

    section = st.session_state.get("section", "part1")

    # Layout: [brand] [Part 1] [Part 2] [--spacer--] [ISIN DB]
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

    # Nav buttons - vertically centred against the 88px brand block
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
        pass  # intentional - pushes ISIN Database to far right

    with col_isin:
        st.markdown(_btn_pad, unsafe_allow_html=True)
        isin_style = "primary" if section == "isin" else "secondary"
        if st.button("ISIN Database", type=isin_style, use_container_width=True, key="nav_isin"):
            st.session_state.section = "isin"
            st.rerun()
        st.markdown(_btn_end, unsafe_allow_html=True)

    # Separator pulled hard against the nav - aggressive negative margin collapses
    # the ~1rem Streamlit adds between every element pair
    st.markdown(
        '<div style="height:1px;background:linear-gradient(90deg,'
        'transparent,#EAE3D8 15%,#EAE3D8 85%,transparent);'
        'margin:-0.6rem 0 1.4rem 0"></div>',
        unsafe_allow_html=True,
    )


# ── Part 1 - Step 1: Upload ───────────────────────────────────────────────────

def p1_upload():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)

    # Read batch state from session_state so layout (3 vs 4 cards) is decided
    # BEFORE rendering widgets - avoids chicken-and-egg ordering problem.
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
            research_file = st.file_uploader("Research Team File", type=["xlsx", "xls"], key="p1_research", label_visibility="collapsed")
        with col2:
            st.markdown('<div class="upload-label">Orbis Bank Book <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            bank_file = st.file_uploader("Orbis Bank Book", type=["xlsx", "xls"], key="p1_bank", label_visibility="collapsed")
        with col3:
            st.markdown('<div class="upload-label">Scrip-wise Report <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            scrip_file = st.file_uploader("Scrip-wise Report", type=["xlsx", "xls"], key="p1_scrip", label_visibility="collapsed")
    else:
        _CARD_COLS = [0.5, 2, 0.32, 2, 0.32, 2, 0.32, 2, 0.5]
        _, col1, _, col2, _, col3, _, col4, _ = st.columns(_CARD_COLS)
        with col1:
            st.markdown('<div class="upload-label">Research Team File <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            research_file = st.file_uploader("Research Team File", type=["xlsx", "xls"], key="p1_research", label_visibility="collapsed")
        with col2:
            st.markdown('<div class="upload-label">Orbis Bank Book <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            bank_file = st.file_uploader("Orbis Bank Book", type=["xlsx", "xls"], key="p1_bank", label_visibility="collapsed")
        with col3:
            st.markdown('<div class="upload-label">Scrip-wise Report <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            scrip_file = st.file_uploader("Scrip-wise Report", type=["xlsx", "xls"], key="p1_scrip", label_visibility="collapsed")
        with col4:
            st.markdown('<div class="upload-label">Existing Session File <span class="upload-required">*</span></div>', unsafe_allow_html=True)
            existing_file = st.file_uploader("Existing Session File", type=["xlsx", "xls"], key="p1_existing", label_visibility="collapsed")

    # ── Settings row 1 - Multiple Batches + Price Tolerance, centered together
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
                f'⚠ High tolerance - {tolerance:.1f}%</div>',
                unsafe_allow_html=True,
            )

    all_uploaded = bool(research_file and bank_file and scrip_file)
    if batch_mode and not existing_file:
        all_uploaded = False

    # ── Settings row 2 - Validate Orders button, right-aligned (under card 3)
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


# ── Part 1 - Step 2: Validate ─────────────────────────────────────────────────

def p1_validate():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    vdf = st.session_state["validation_df"].copy()
    n_green = int((vdf["Status"] == "GREEN").sum())
    n_red   = int((vdf["Status"] == "RED").sum())

    # ── Centred title ──────────────────────────────────────────────────────────
    st.markdown(
        '<div style="margin:0.3rem 0 1.2rem 0;text-align:center">'
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        'font-size:2rem;font-weight:600;color:#1C1714;line-height:1">'
        'Validate Orders</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Resolve override BEFORE building editor_df ────────────────────────────
    override = st.session_state.pop("_include_override", None)

    # ── Status bar: split-badge metrics (left) + Exclude buttons (right) ──────
    col_status, col_actions = st.columns([5.5, 3.5])

    with col_status:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;padding-top:2px">'
            # ── Orders Ready ──────────────────────────────────────────────────
            f'<div style="display:flex;border:1px solid rgba(22,163,74,0.28);'
            f'border-radius:8px;overflow:hidden;height:38px">'
            f'<div style="padding:0 14px;display:flex;align-items:center;'
            f'background:rgba(22,163,74,0.05);font-size:0.67rem;color:#16a34a;'
            f'letter-spacing:0.65px;text-transform:uppercase;font-weight:400;'
            f'font-family:\'DM Sans\',sans-serif;white-space:nowrap">Orders Ready</div>'
            f'<div style="padding:0 18px;display:flex;align-items:center;'
            f'background:rgba(22,163,74,0.1);font-size:1rem;font-weight:600;'
            f'color:#16a34a;font-family:\'DM Sans\',sans-serif;'
            f'border-left:1px solid rgba(22,163,74,0.2)">{n_green}</div>'
            f'</div>'
            # ── Orders Blocked ────────────────────────────────────────────────
            f'<div style="display:flex;border:1px solid rgba(220,38,38,0.22);'
            f'border-radius:8px;overflow:hidden;height:38px">'
            f'<div style="padding:0 14px;display:flex;align-items:center;'
            f'background:rgba(220,38,38,0.04);font-size:0.67rem;color:#dc2626;'
            f'letter-spacing:0.65px;text-transform:uppercase;font-weight:400;'
            f'font-family:\'DM Sans\',sans-serif;white-space:nowrap">Orders Blocked</div>'
            f'<div style="padding:0 18px;display:flex;align-items:center;'
            f'background:rgba(220,38,38,0.09);font-size:1rem;font-weight:600;'
            f'color:#dc2626;font-family:\'DM Sans\',sans-serif;'
            f'border-left:1px solid rgba(220,38,38,0.15)">{n_red}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_actions:
        btn1, btn2 = st.columns(2)
        with btn1:
            if st.button("Exclude all red", key="p1_excl_red", use_container_width=True):
                st.session_state["_include_override"] = "red_out"
                st.rerun()
        with btn2:
            if st.button("Exclude entire batch", key="p1_excl_all", use_container_width=True):
                st.session_state["_include_override"] = "all_out"
                st.rerun()

    st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

    # ── Build editor DataFrame - Context before Reason ────────────────────────
    context_col = "Context" if "Context" in vdf.columns else None
    base_cols = ["S.No", "Client", "Ticker", "Direction", "Qty"]
    if context_col:
        base_cols.append(context_col)   # Context sits immediately right of Qty
    base_cols += ["Ref Price", "Status", "Reason"]
    editor_df = vdf[base_cols].copy()
    if context_col:
        editor_df.rename(columns={"Context": "Units Held / Cash"}, inplace=True)
    editor_df.insert(0, "Include", vdf["Status"] == "GREEN")

    if override == "red_out":
        editor_df["Include"] = vdf["Status"] == "GREEN"
    elif override == "all_out":
        editor_df["Include"] = False

    # ── Split table: narrow checkbox editor (left) + colour-styled display (right)
    # Both use auto-height (no cap) so the PAGE scrolls - keeps rows in visual sync.
    col_check, col_table = st.columns([0.7, 8.3])

    with col_check:
        check_df = editor_df[["Include"]].copy()
        edited_check = st.data_editor(
            check_df,
            column_config={
                "Include": st.column_config.CheckboxColumn("", default=True, width="small"),
            },
            hide_index=True,
            use_container_width=True,
            key="p1_editor_check",
        )

    with col_table:
        display_df = editor_df.drop(columns=["Include"])

        def _row_style(row):
            colour = (
                "rgba(22,163,74,0.07)" if row["Status"] == "GREEN"
                else "rgba(220,38,38,0.06)"
            )
            return [f"background-color: {colour}"] * len(row)

        styled_df = (
            display_df.style
            .apply(_row_style, axis=1)
            .format({"Status": lambda v: "READY" if v == "GREEN" else "BLOCKED"})
            .set_properties(**{"white-space": "normal"})
        )

        st.dataframe(
            styled_df,
            column_config={
                "S.No":              st.column_config.NumberColumn("No.", width="small"),
                "Client":            st.column_config.TextColumn("Client", width="medium"),
                "Ticker":            st.column_config.TextColumn("Ticker", width="small"),
                "Direction":         st.column_config.TextColumn("Dir", width="small"),
                "Qty":               st.column_config.NumberColumn("Qty", width="small"),
                "Ref Price":         st.column_config.NumberColumn("Ref Price", format="%.2f", width="small"),
                "Status":            st.column_config.TextColumn("Status", width="small"),
                "Units Held / Cash": st.column_config.TextColumn("Available / Held", width="medium"),
                "Reason":            st.column_config.TextColumn("Reason", width="large"),
            },
            hide_index=True,
            use_container_width=True,
        )

    red_included = int(((edited_check["Include"] == True) & (vdf["Status"] == "RED")).sum())
    n_included   = int(edited_check["Include"].sum())

    # Inline warning if blocked rows are still checked
    if red_included > 0:
        st.markdown(
            f'<div style="background:rgba(220,38,38,0.05);'
            f'border:1px solid rgba(220,38,38,0.18);border-left:3px solid #dc2626;'
            f'border-radius:6px;padding:0.7rem 1rem;font-size:0.82rem;color:#b91c1c;'
            f'margin-top:0.6rem;font-family:\'DM Sans\',sans-serif;font-weight:400">'
            f'⚠  {red_included} blocked row(s) still marked as included - '
            f'uncheck or click "Exclude all red" above.</div>',
            unsafe_allow_html=True,
        )

    # ── JS: semantic Exclude button colours + sticky action bar ──────────────
    components.html("""
    <script>
    (function() {
        function applyValidateStyles() {
            try {
                var doc = window.parent.document;

                // 1. Semantic colours for the two Exclude buttons
                doc.querySelectorAll('button').forEach(function(btn) {
                    var t = btn.textContent.trim();
                    if (t === 'Exclude all red') {
                        btn.style.setProperty('background', 'rgba(220,38,38,0.08)', 'important');
                        btn.style.setProperty('border', '1.5px solid rgba(220,38,38,0.38)', 'important');
                        btn.style.setProperty('color', '#b91c1c', 'important');
                    } else if (t === 'Exclude entire batch') {
                        btn.style.setProperty('background', 'rgba(28,23,20,0.07)', 'important');
                        btn.style.setProperty('border', '1.5px solid rgba(28,23,20,0.3)', 'important');
                        btn.style.setProperty('color', '#1C1714', 'important');
                    }
                });

                // 2. Sticky bottom action bar (only when styled dataframe is present)
                if (!doc.querySelector('[data-testid="stDataFrame"]')) return;
                var backBtn = null;
                doc.querySelectorAll('button').forEach(function(btn) {
                    if (btn.textContent.trim() === '← Back') backBtn = btn;
                });
                if (!backBtn) return;
                var hBlock = backBtn.closest('[data-testid="stHorizontalBlock"]');
                if (!hBlock) return;
                var wrap = hBlock.parentElement;
                if (!wrap || wrap.dataset.stickyDone) return;
                wrap.dataset.stickyDone = '1';
                wrap.style.setProperty('position', 'sticky', 'important');
                wrap.style.setProperty('bottom', '0', 'important');
                wrap.style.setProperty('background', '#FFFFFF', 'important');
                wrap.style.setProperty('z-index', '200', 'important');
                wrap.style.setProperty('border-top', '1px solid #EAE3D8', 'important');
                wrap.style.setProperty('padding-top', '10px', 'important');
                wrap.style.setProperty('padding-bottom', '6px', 'important');
                wrap.style.setProperty('box-shadow', '0 -4px 16px rgba(0,0,0,0.05)', 'important');
            } catch(e) {}
        }
        try {
            new MutationObserver(function() {
                setTimeout(applyValidateStyles, 80);
            }).observe(window.parent.document.body, {childList: true, subtree: true});
        } catch(e) {}
        setInterval(applyValidateStyles, 600);
        setTimeout(applyValidateStyles, 300);
    })();
    </script>
    """, height=0)

    # ── Bottom action row (becomes sticky via JS above) ───────────────────────
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
                included_idx = edited_check[edited_check["Include"] == True].index
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


# ── Part 1 - Step 3: Download ─────────────────────────────────────────────────

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

    session_bytes = write_session_file(session_df)
    broker_bytes  = to_excel_bytes(broker_file_df, "Broker File")
    session_b64   = base64.b64encode(session_bytes).decode()
    broker_b64    = base64.b64encode(broker_bytes).decode()

    # ── Download badges - split-badge row: [Session File | ⬇ xlsx]  [Broker File | ⬇ xlsx]  [Download Both] ──
    _dl_icon = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M12 3v13"/><polyline points="7 11 12 16 17 11"/><line x1="5" y1="21" x2="19" y2="21"/></svg>'
    components.html(f"""
    <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: transparent; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }}
    .dl-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        padding: 10px 0 8px 0;
        flex-wrap: nowrap;
    }}
    /* Split badge: grey label + gold action */
    .dl-badge {{
        display: inline-flex;
        height: 42px;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #EAE3D8;
        text-decoration: none;
        flex-shrink: 0;
    }}
    .dl-badge-label {{
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 16px;
        background: #F0EBE3;
        color: #4A4540;
        font-size: 11px;
        letter-spacing: 0.65px;
        text-transform: uppercase;
        font-weight: 500;
        white-space: nowrap;
        border-right: 1px solid #EAE3D8;
    }}
    .dl-badge-action {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 0 20px;
        background: #D9B244;
        color: #fff;
        font-size: 13px;
        font-weight: 400;
        white-space: nowrap;
        transition: background 0.15s;
    }}
    .dl-badge:hover .dl-badge-action {{ background: #C4A03C; }}
    /* Full-gold Download Both button */
    .dl-both {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        height: 42px;
        border-radius: 8px;
        padding: 0 24px;
        background: #D9B244;
        border: 1.5px solid #D9B244;
        color: #fff;
        font-size: 13px;
        font-weight: 400;
        white-space: nowrap;
        cursor: pointer;
        flex-shrink: 0;
        font-family: inherit;
        transition: background 0.15s;
    }}
    .dl-both:hover {{ background: #C4A03C; border-color: #C4A03C; }}
    </style>
    <div class="dl-row">
      <a class="dl-badge"
         href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{session_b64}"
         download="session_file.xlsx">
        <span class="dl-badge-label">Session File</span>
        <span class="dl-badge-action">{_dl_icon} Download session_file.xlsx</span>
      </a>
      <a class="dl-badge"
         href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{broker_b64}"
         download="broker_file.xlsx">
        <span class="dl-badge-label">Broker File</span>
        <span class="dl-badge-action">{_dl_icon} Download broker_file.xlsx</span>
      </a>
      <button class="dl-both" onclick="
        var badges = document.querySelectorAll('a.dl-badge');
        try {{ if (badges[0]) badges[0].click(); }} catch(e) {{}}
        setTimeout(function() {{ try {{ if (badges[1]) badges[1].click(); }} catch(e) {{}} }}, 400);
      ">{_dl_icon} Download Both Files</button>
    </div>
    """, height=72)

    # ── Broker file preview ───────────────────────────────────────────────────
    st.markdown('<div style="height:1.6rem"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.67rem;color:#B0A89E;font-family:\'DM Sans\',sans-serif;'
        'font-weight:400;letter-spacing:0.65px;text-transform:uppercase;margin-bottom:8px">'
        'Broker File Preview</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(broker_file_df.style.set_properties(**{"white-space": "normal"}), use_container_width=True, hide_index=True)

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


# ── Part 2 - Step 1: Upload ───────────────────────────────────────────────────

def p2_upload():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="margin:0.3rem 0 1.4rem 0;text-align:center">'
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;margin-bottom:5px">'
        'Upload & Configure</div>'
        '<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
        'font-weight:300">Provide the session file and the broker execution reply.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Two upload cards - margin cols sized so each card ≈ same px as Part 1 ──
    # Part 1 uses [1,2,0.4,2,0.4,2,1]=8.8 total; card=2/8.8≈22.7% of page.
    # Here: [2.2,2,0.4,2,2.2]=8.8 total → same 22.7% per card, stays vertical.
    _, col1, _, col2, _ = st.columns([2.2, 2, 0.4, 2, 2.2])
    with col1:
        st.markdown(
            '<div class="upload-label">Session File <span class="upload-required">*</span></div>',
            unsafe_allow_html=True,
        )
        session_file = st.file_uploader(
            "Session File", type=["xlsx", "xls"], key="p2_session", label_visibility="collapsed",
        )
    with col2:
        st.markdown(
            '<div class="upload-label">Broker Reply <span class="upload-required">*</span></div>',
            unsafe_allow_html=True,
        )
        broker_file = st.file_uploader(
            "Broker Reply", type=["xlsx", "xls"], key="p2_broker", label_visibility="collapsed",
        )

    # ── Settings row - broker selector + process button ───────────────────────
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


# ── Part 2 - Step 2: Results ──────────────────────────────────────────────────

def p2_results():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    allocation_df = st.session_state["allocation_df"]
    not_executed  = st.session_state.get("p2_not_exec", [])
    unexpected    = st.session_state.get("p2_unexpected", [])

    n_clients = len(allocation_df)
    n_stocks  = allocation_df["ISIN No"].nunique()

    # ── Header + split-badge blocks ───────────────────────────────────────────
    st.markdown(
        f'<div style="margin:0.3rem 0 1.4rem 0;text-align:center">'
        f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;margin-bottom:16px">'
        f'Allocation Complete</div>'
        f'<div style="display:inline-flex;align-items:center;gap:12px">'
        # ── Stocks block ──────────────────────────────────────────────────────
        f'<div style="display:flex;border:1px solid rgba(22,163,74,0.28);'
        f'border-radius:8px;overflow:hidden;height:38px">'
        f'<div style="padding:0 14px;display:flex;align-items:center;'
        f'background:rgba(22,163,74,0.05);font-size:0.67rem;color:#16a34a;'
        f'letter-spacing:0.65px;text-transform:uppercase;font-weight:400;'
        f'font-family:\'DM Sans\',sans-serif;white-space:nowrap">Stocks</div>'
        f'<div style="padding:0 18px;display:flex;align-items:center;'
        f'background:rgba(22,163,74,0.1);font-size:1rem;font-weight:600;'
        f'color:#16a34a;font-family:\'DM Sans\',sans-serif;'
        f'border-left:1px solid rgba(22,163,74,0.2)">{n_stocks}</div>'
        f'</div>'
        # ── Clients block ─────────────────────────────────────────────────────
        f'<div style="display:flex;border:1px solid rgba(22,163,74,0.28);'
        f'border-radius:8px;overflow:hidden;height:38px">'
        f'<div style="padding:0 14px;display:flex;align-items:center;'
        f'background:rgba(22,163,74,0.05);font-size:0.67rem;color:#16a34a;'
        f'letter-spacing:0.65px;text-transform:uppercase;font-weight:400;'
        f'font-family:\'DM Sans\',sans-serif;white-space:nowrap">Clients</div>'
        f'<div style="padding:0 18px;display:flex;align-items:center;'
        f'background:rgba(22,163,74,0.1);font-size:1rem;font-weight:600;'
        f'color:#16a34a;font-family:\'DM Sans\',sans-serif;'
        f'border-left:1px solid rgba(22,163,74,0.2)">{n_clients}</div>'
        f'</div>'
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
    st.dataframe(summary.style.set_properties(**{"white-space": "normal"}), use_container_width=True, hide_index=True)

    # ── Download badge - centered split badge ─────────────────────────────────
    st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)
    alloc_bytes = write_allocation_file(allocation_df)
    alloc_b64   = base64.b64encode(alloc_bytes).decode()
    _dl_icon = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M12 3v13"/><polyline points="7 11 12 16 17 11"/><line x1="5" y1="21" x2="19" y2="21"/></svg>'
    components.html(f"""
    <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: transparent; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }}
    .dl-row {{
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        padding: 10px 0 8px 0;
    }}
    .dl-badge {{
        display: inline-flex;
        height: 42px;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #EAE3D8;
        text-decoration: none;
        flex-shrink: 0;
    }}
    .dl-badge-label {{
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 16px;
        background: #F0EBE3;
        color: #4A4540;
        font-size: 11px;
        letter-spacing: 0.65px;
        text-transform: uppercase;
        font-weight: 500;
        white-space: nowrap;
        border-right: 1px solid #EAE3D8;
    }}
    .dl-badge-action {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 0 20px;
        background: #D9B244;
        color: #fff;
        font-size: 13px;
        font-weight: 400;
        white-space: nowrap;
        transition: background 0.15s;
    }}
    .dl-badge:hover .dl-badge-action {{ background: #C4A03C; }}
    </style>
    <div class="dl-row">
      <a class="dl-badge"
         href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{alloc_b64}"
         download="orbis_allocation.xlsx">
        <span class="dl-badge-label">Orbis Allocation File</span>
        <span class="dl-badge-action">{_dl_icon} Download orbis_allocation.xlsx</span>
      </a>
    </div>
    """, height=72)

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
    hdr_col, btn_col = st.columns([5, 1])
    with hdr_col:
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
    with btn_col:
        st.markdown('<div style="padding-top:0.4rem"></div>', unsafe_allow_html=True)
        bulk_file = st.file_uploader(
            "Update ISIN Database",
            type=["csv"],
            key=f"isin_bulk_{st.session_state.get('isin_bulk_key', 0)}",
            label_visibility="collapsed",
        )
    # JS: stamp isin-uploader-btn class directly onto the uploader element so
    # CSS can target it (wrapper divs don't work — Streamlit renders siblings)
    components.html(
        """
        <script>
        (function() {
            function stamp() {
                try {
                    var doc = window.parent.document;
                    var uploaders = doc.querySelectorAll('[data-testid="stFileUploader"]');
                    if (!uploaders.length) { setTimeout(stamp, 150); return; }
                    var last = uploaders[uploaders.length - 1];
                    if (!last.classList.contains('isin-uploader-btn')) {
                        last.classList.add('isin-uploader-btn');
                    }
                } catch(e) {}
            }
            stamp();
            // Re-stamp after Streamlit reruns (MutationObserver on body)
            try {
                var obs = new MutationObserver(stamp);
                obs.observe(window.parent.document.body, { childList: true, subtree: true });
            } catch(e) {}
        })();
        </script>
        """,
        height=0,
    )

    if bulk_file is not None:
        try:
            added, skipped = bulk_update_isin_database(bulk_file)
            get_isin_db.clear()
            st.session_state.isin_bulk_key = st.session_state.get("isin_bulk_key", 0) + 1
            if added > 0:
                st.toast(f"✓ {added:,} new entries added. {skipped:,} already existed.")
            else:
                st.toast(f"All {skipped:,} entries already exist. Nothing added.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    # ── Search bar ────────────────────────────────────────────────────────────
    search_col, count_col = st.columns([4, 1])
    with search_col:
        search = st.text_input(
            "Search",
            placeholder="Company name, NSE code, BSE code, or ISIN…",
            key="isin_search",
            label_visibility="collapsed",
        )
    # Live-search JS debounce - triggers Enter after 350 ms of inactivity
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

    st.dataframe(display_db.style.set_properties(**{"white-space": "normal"}), use_container_width=True, hide_index=True, height=400)

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
                get_isin_db.clear()  # scoped clear - only evicts ISIN cache, not all caches
                st.success(f"✓  Added: {new_name or '-'}  ({new_isin.strip()})")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.markdown('</div>', unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.markdown(CSS, unsafe_allow_html=True)

    # JS: (1) stamp data-uploaded on dropzones, (2) equalize card heights by
    # measuring empty-state dropzones and applying that height to uploaded ones.
    components.html("""
    <script>
    (function() {
        function syncDropzones() {
            try {
                var doc = window.parent.document;
                var uploaders = doc.querySelectorAll('[data-testid="stFileUploader"]');
                if (uploaders.length === 0) return;

                // Pass 1 - stamp data-uploaded attribute
                uploaders.forEach(function(uploader) {
                    var dz = uploader.querySelector('[data-testid="stFileUploaderDropzone"]');
                    if (!dz) return;
                    var hasFile = !!uploader.querySelector('[data-testid="stFileUploaderFile"]');
                    dz.setAttribute('data-uploaded', hasFile ? 'true' : 'false');
                });

                // Pass 2 - find the tallest EMPTY-state dropzone
                var maxH = 0;
                uploaders.forEach(function(uploader) {
                    var hasFile = !!uploader.querySelector('[data-testid="stFileUploaderFile"]');
                    if (!hasFile) {
                        var dz = uploader.querySelector('[data-testid="stFileUploaderDropzone"]');
                        if (dz) {
                            // Clear any previously forced height so we read natural height
                            dz.style.removeProperty('min-height');
                            var h = dz.getBoundingClientRect().height;
                            if (h > maxH) maxH = h;
                        }
                    }
                });

                // Pass 3 - force ALL dropzones to that height (uploaded ones won't
                // naturally reach it; empty ones already meet it via content)
                if (maxH > 0) {
                    uploaders.forEach(function(uploader) {
                        var dz = uploader.querySelector('[data-testid="stFileUploaderDropzone"]');
                        if (dz) {
                            dz.style.setProperty('min-height', maxH + 'px', 'important');
                        }
                    });
                }
            } catch(e) {}
        }

        // Re-run on every DOM mutation (file add/remove triggers Streamlit rerender)
        try {
            var obs = new MutationObserver(function() {
                setTimeout(syncDropzones, 120);
            });
            obs.observe(window.parent.document.body, { childList: true, subtree: true });
        } catch(e) {}

        // Polling fallback
        setInterval(syncDropzones, 500);
        setTimeout(syncDropzones, 300);

        // Logo → home: click the logo image to navigate to Part 1
        function wireLogoClick() {
            try {
                var doc = window.parent.document;
                var logo = doc.querySelector('img[src*="data:image/png"]');
                if (!logo || logo._logoWired) return;
                logo._logoWired = true;
                logo.style.cursor = 'pointer';
                logo.title = 'Go to home';
                logo.addEventListener('click', function() {
                    doc.querySelectorAll('button').forEach(function(btn) {
                        if (btn.textContent.trim() === 'Part 1') btn.click();
                    });
                });
            } catch(e) {}
        }
        setTimeout(wireLogoClick, 400);
        try {
            new MutationObserver(function() {
                setTimeout(wireLogoClick, 150);
            }).observe(window.parent.document.body, { childList: true, subtree: true });
        } catch(e) {}
    })();
    </script>
    """, height=0)

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
