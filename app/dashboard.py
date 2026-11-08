import os
import sys

# Suppress harmless Windows asyncio Proactor [WinError 10054] connection reset exceptions
if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost
        def _silent_call_connection_lost(self, exc=None):
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError):
                pass
        _ProactorBasePipeTransport._call_connection_lost = _silent_call_connection_lost
    except Exception:
        pass

import time
import sqlite3
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import cv2
from PIL import Image

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.face_engine import face_engine, DEFAULT_VERIFICATION_THRESHOLD, DEFAULT_MIN_MARGIN
from app.attendance import record_attendance, has_attended_today, create_database
from app.enrollment import enroll_student
from app.attendance_runner import load_enrolled_students, LiveAttendanceTracker
from database.punctuality import classify_punctuality, get_punctuality_summary, get_student_punctuality
from database.attendance_queries import get_today_attendance_count, get_total_students
from app.auth import (
    render_login_screen,
    logout,
    init_auth_db,
    check_session_timeout,
    AuthenticationConfigurationError,
)

DATABASE_PATH = os.path.join(PROJECT_ROOT, "database", "attendance.db")
EXPORTS_DIR = os.path.join(PROJECT_ROOT, "data", "exports")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
LOGO_PATH = os.path.join(PROJECT_ROOT, "assets", "kprit_logo.png")

# --------------------------------------------------
# Streamlit Page Config & Enterprise Design System
# --------------------------------------------------
st.set_page_config(
    page_title="KPRIT - Smart Face Verification Attendance",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Design System (CSS)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ========================================================
       1. GLOBAL BASELINE & TYPOGRAPHY SYSTEM
       ======================================================== */
    html, body, .stApp {
        background-color: #f8fafc !important;
        color: #111827 !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }

    /* All text elements default to high-contrast dark text on light canvas */
    .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6, label {
        color: #111827;
    }

    .stCaption, small, .kpi-sub {
        color: #475569 !important;
    }

    /* Preserve Material Icon Fonts */
    .material-symbols-rounded, .material-symbols-outlined, .material-icons, [class*="material-symbols"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    }

    /* ========================================================
       2. STREAMLIT HEADER & SIDEBAR TOGGLE SYSTEM (EXPAND & COLLAPSE)
       ======================================================== */
    /* Keep header container present and transparent so stExpandSidebarButton is accessible */
    header[data-testid="stHeader"],
    header {
        background: transparent !important;
        visibility: visible !important;
        display: flex !important;
        align-items: center !important;
        height: 3.2rem !important;
        z-index: 999990 !important;
        pointer-events: none !important; /* Prevents transparent header from blocking clicks */
    }

    /* Allow pointer events on interactive children in header */
    header[data-testid="stHeader"] *,
    header * {
        pointer-events: auto !important;
    }

    /* Hide only unwanted top-right chrome (hamburger, deploy, status widget, footer) */
    #MainMenu,
    footer,
    [data-testid="stToolbarActions"],
    [data-testid="stStatusWidget"],
    [data-testid="stDecoration"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
    }

    /* Fluid Responsive Container (Auto-adjusts width when sidebar opens/closes) */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
        max-width: 100% !important;
        width: 100% !important;
        box-sizing: border-box !important;
        transition: padding 0.2s ease !important;
    }

    /* Sidebar Expand / Reopen Button (In Header when Collapsed) */
    [data-testid="stExpandSidebarButton"],
    [data-testid="stExpandSidebarButton"] button,
    [data-testid="collapsedControl"],
    [data-testid="collapsedControl"] button {
        visibility: visible !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        opacity: 1 !important;
        background: #0f172a !important;
        color: #ffffff !important;
        border: 1.5px solid #2563eb !important;
        border-radius: 8px !important;
        padding: 6px 10px !important;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.3) !important;
        cursor: pointer !important;
        z-index: 999999 !important;
        pointer-events: auto !important;
        transition: all 0.2s ease !important;
        margin-left: 0.75rem !important;
        margin-top: 0.35rem !important;
    }

    [data-testid="stExpandSidebarButton"]:hover,
    [data-testid="stExpandSidebarButton"] button:hover,
    [data-testid="collapsedControl"]:hover,
    [data-testid="collapsedControl"] button:hover {
        background: #2563eb !important;
        border-color: #60a5fa !important;
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.5) !important;
        transform: scale(1.05) !important;
    }

    [data-testid="stExpandSidebarButton"] svg,
    [data-testid="stExpandSidebarButton"] span,
    [data-testid="collapsedControl"] svg,
    [data-testid="collapsedControl"] span {
        color: #ffffff !important;
        fill: #ffffff !important;
    }

    /* Sidebar Collapse Button (Inside Sidebar Header) */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] button {
        visibility: visible !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        opacity: 1 !important;
        background: #1e293b !important;
        color: #ffffff !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        padding: 6px !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
    }

    [data-testid="stSidebarCollapseButton"]:hover,
    [data-testid="stSidebarCollapseButton"] button:hover {
        background: #2563eb !important;
        border-color: #3b82f6 !important;
        color: #ffffff !important;
    }

    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarCollapseButton"] span {
        color: #ffffff !important;
        fill: #ffffff !important;
    }

    /* Responsive Adjustments for 1366x768 and Laptops */
    @media (max-width: 1366px) {
        .block-container {
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
        .kpi-container {
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)) !important;
        }
    }

    /* ========================================================
       3. FORM INSTRUCTIONS TOOLTIP SUPPRESSION
       Hides 'Press Enter to submit form' without breaking Enter submission
       ======================================================== */
    [data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
        overflow: hidden !important;
    }

    /* ========================================================
       4. GLOBAL BUTTON COLOR SYSTEM (100% CONTRAST IN ALL STATES)
       ======================================================== */
    .stButton > button,
    [data-testid="stFormSubmitButton"] > button,
    [data-testid="stDownloadButton"] > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 0.6rem 1.15rem !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
        text-align: center !important;
    }

    /* Primary Buttons (Start Camera, Commit Enrollment, Download CSV) */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"],
    [data-testid="stFormSubmitButton"] > button,
    [data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border: 1px solid #1d4ed8 !important;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.25) !important;
    }
    .stButton > button[kind="primary"] *,
    .stButton > button[data-testid="stBaseButton-primary"] *,
    [data-testid="stFormSubmitButton"] > button *,
    [data-testid="stDownloadButton"] > button * {
        color: #ffffff !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover,
    [data-testid="stFormSubmitButton"] > button:hover,
    [data-testid="stDownloadButton"] > button:hover {
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
        color: #ffffff !important;
        border-color: #1e40af !important;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.4) !important;
        transform: translateY(-1px);
    }
    .stButton > button[kind="primary"]:focus,
    [data-testid="stFormSubmitButton"] > button:focus,
    [data-testid="stDownloadButton"] > button:focus {
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.35) !important;
        outline: none !important;
    }

    /* Secondary / Default Buttons (Sync Live Data, Stop Camera, Attendance Actions) */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"],
    .stButton > button:not([kind="primary"]) {
        background: #ffffff !important;
        color: #1e293b !important;
        border: 1.5px solid #cbd5e1 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06) !important;
    }
    .stButton > button[kind="secondary"] *,
    .stButton > button[data-testid="stBaseButton-secondary"] *,
    .stButton > button:not([kind="primary"]) * {
        color: #1e293b !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover,
    .stButton > button:not([kind="primary"]):hover {
        background: #f1f5f9 !important;
        color: #0f172a !important;
        border-color: #94a3b8 !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1) !important;
        transform: translateY(-1px);
    }
    .stButton > button[kind="secondary"]:hover *,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover *,
    .stButton > button:not([kind="primary"]):hover * {
        color: #0f172a !important;
    }
    .stButton > button[kind="secondary"]:focus,
    .stButton > button:not([kind="primary"]):focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2) !important;
        outline: none !important;
    }

    /* Disabled State for Buttons */
    .stButton > button:disabled,
    .stButton > button[disabled] {
        background: #f1f5f9 !important;
        color: #94a3b8 !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: none !important;
        cursor: not-allowed !important;
        opacity: 0.8 !important;
        transform: none !important;
    }
    .stButton > button:disabled *,
    .stButton > button[disabled] * {
        color: #94a3b8 !important;
    }

    /* ========================================================
       5. SIDEBAR NAVIGATION & PROFILE SYSTEM
       ======================================================== */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b !important;
    }

    /* Sidebar Headings and Labels (No destructive universal wildcard) */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        color: #f1f5f9;
    }

    [data-testid="stSidebar"] hr {
        border-color: #1e293b !important;
    }

    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] small {
        color: #94a3b8 !important;
    }

    /* Administrator Role Badge (Active Session Card in Sidebar) */
    [data-testid="stSidebar"] .admin-role-badge,
    .admin-role-badge {
        background-color: #1D4ED8 !important;
        color: #FFFFFF !important;
        border: 1px solid #3B82F6 !important;
        font-weight: 700 !important;
        border-radius: 9999px !important;
        padding: 4px 12px !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 5px !important;
        font-size: 0.72rem !important;
        letter-spacing: 0.03em !important;
        white-space: nowrap !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25) !important;
        line-height: 1.2 !important;
        transition: none !important;
    }

    [data-testid="stSidebar"] .admin-role-badge:hover,
    [data-testid="stSidebar"] .admin-role-badge:focus,
    .admin-role-badge:hover,
    .admin-role-badge:focus {
        background-color: #1D4ED8 !important;
        color: #FFFFFF !important;
        border-color: #3B82F6 !important;
    }

    /* Sidebar Sign Out Button */
    [data-testid="stSidebar"] .stButton button {
        background: #1e293b !important;
        color: #ffffff !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25) !important;
        font-weight: 600 !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] .stButton button * {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%) !important;
        border-color: #ef4444 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 10px rgba(220, 38, 38, 0.4) !important;
        transform: translateY(-1px);
    }
    [data-testid="stSidebar"] .stButton button:hover * {
        color: #ffffff !important;
    }

    /* Sidebar Navigation Radio Buttons */
    [data-testid="stSidebar"] .stRadio > div {
        background: transparent !important;
        gap: 6px !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        padding: 0.65rem 0.95rem !important;
        margin-bottom: 2px !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        color: #f8fafc !important;
    }
    [data-testid="stSidebar"] .stRadio label p {
        color: #f8fafc !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: #2563eb !important;
        border-color: #3b82f6 !important;
        color: #ffffff !important;
        transform: translateX(2px);
    }
    [data-testid="stSidebar"] .stRadio label:hover p {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stRadio label[data-checked="true"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        border-color: #60a5fa !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 8px -1px rgba(37, 99, 235, 0.4) !important;
    }
    [data-testid="stSidebar"] .stRadio label[data-checked="true"] p {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Sidebar Expander & Configuration Controls */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
        fill: #94a3b8 !important;
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stNumberInput label {
        color: #cbd5e1 !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] {
        background-color: #0f172a !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] input {
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] button {
        background-color: #334155 !important;
        color: #ffffff !important;
        border: none !important;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] button svg {
        fill: #ffffff !important;
    }

    /* ========================================================
       5. MAIN PAGE INPUTS, SELECTBOXES, DROPDOWNS & CHECKBOXES
       ======================================================== */
    [data-testid="stTextInput"] label,
    [data-testid="stSelectbox"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stFileUploader"] label,
    [data-testid="stCameraInput"] label {
        color: #0f172a !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
        margin-bottom: 4px !important;
    }

    /* Light Surface Inputs (Search & Forms) */
    [data-testid="stAppViewContainer"] [data-baseweb="input"] {
        background-color: #ffffff !important;
        border: 1.5px solid #cbd5e1 !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stAppViewContainer"] [data-baseweb="input"]:focus-within {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2) !important;
    }
    [data-testid="stAppViewContainer"] [data-baseweb="input"] input {
        color: #0f172a !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
    }
    [data-testid="stAppViewContainer"] [data-baseweb="input"] input::placeholder {
        color: #64748b !important;
        font-weight: 400 !important;
    }

    /* Selectboxes */
    [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border: 1.5px solid #cbd5e1 !important;
        border-radius: 8px !important;
        color: #0f172a !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within > div {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2) !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] * {
        color: #0f172a !important;
    }
    [data-testid="stSelectbox"] svg {
        fill: #475569 !important;
    }

    /* Dropdown Menus (Portal Popovers) */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    ul[role="listbox"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15) !important;
    }
    li[role="option"] {
        color: #0f172a !important;
        font-weight: 500 !important;
        font-size: 0.88rem !important;
        padding: 8px 12px !important;
    }
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {
        background-color: #eff6ff !important;
        color: #1d4ed8 !important;
        font-weight: 600 !important;
    }

    /* Checkbox Labels */
    [data-testid="stCheckbox"] label {
        color: #1e293b !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        cursor: pointer !important;
    }
    [data-testid="stCheckbox"] label p {
        color: #1e293b !important;
        font-weight: 600 !important;
    }

    /* ========================================================
       6. HORIZONTAL RADIOS & TAB BARS (MAIN PAGE)
       ======================================================== */
    [data-testid="stAppViewContainer"] .stRadio > div[role="radiogroup"] {
        background: #f1f5f9 !important;
        padding: 4px !important;
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        gap: 4px !important;
    }
    [data-testid="stAppViewContainer"] .stRadio > div[role="radiogroup"] label {
        background: transparent !important;
        border-radius: 7px !important;
        padding: 6px 14px !important;
        color: #334155 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        border: none !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
    }
    [data-testid="stAppViewContainer"] .stRadio > div[role="radiogroup"] label p {
        color: #334155 !important;
        font-weight: 600 !important;
    }
    [data-testid="stAppViewContainer"] .stRadio > div[role="radiogroup"] label:hover {
        background: #e2e8f0 !important;
        color: #0f172a !important;
    }
    [data-testid="stAppViewContainer"] .stRadio > div[role="radiogroup"] label:hover p {
        color: #0f172a !important;
    }
    [data-testid="stAppViewContainer"] .stRadio > div[role="radiogroup"] label[data-checked="true"] {
        background: #ffffff !important;
        color: #2563eb !important;
        font-weight: 700 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
    }
    [data-testid="stAppViewContainer"] .stRadio > div[role="radiogroup"] label[data-checked="true"] p {
        color: #2563eb !important;
        font-weight: 700 !important;
    }

    /* Tabs as Elevated Pills */
    [data-baseweb="tab-list"] {
        background: #f1f5f9 !important;
        padding: 4px !important;
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        gap: 4px !important;
        margin-bottom: 1.25rem !important;
    }
    [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 7px !important;
        padding: 8px 16px !important;
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        border: none !important;
        transition: all 0.15s ease !important;
    }
    [data-baseweb="tab"] * {
        color: #475569 !important;
        font-weight: 600 !important;
    }
    [data-baseweb="tab"]:hover {
        background: #e2e8f0 !important;
        color: #0f172a !important;
    }
    [data-baseweb="tab"]:hover * {
        color: #0f172a !important;
    }
    [data-baseweb="tab"][aria-selected="true"] {
        background: #ffffff !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
    }
    [data-baseweb="tab"][aria-selected="true"] * {
        color: #2563eb !important;
        font-weight: 700 !important;
    }
    [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* ========================================================
       7. CARDS, KPI METRICS, BADGES & TABLES
       ======================================================== */
    /* KPI Cards */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .kpi-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem 1rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        text-align: left;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px -2px rgba(0, 0, 0, 0.08);
    }
    .kpi-title {
        font-size: 0.74rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #475569;
        margin-bottom: 0.35rem;
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.1;
        margin-bottom: 0.25rem;
    }
    .kpi-sub {
        font-size: 0.78rem;
        color: #64748b;
        font-weight: 500;
    }

    /* Badges & Pills */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .status-pill-green {
        background: #ecfdf5;
        color: #065f46;
        border: 1px solid #a7f3d0;
    }
    .status-pill-amber {
        background: #fffbeb;
        color: #92400e;
        border: 1px solid #fde68a;
    }
    .status-pill-cyan {
        background: #ecfeff;
        color: #155e75;
        border: 1px solid #a5f3fc;
    }
    .status-pill-orange {
        background: #fff7ed;
        color: #9a3412;
        border: 1px solid #fed7aa;
    }
    .status-pill-red {
        background: #fef2f2;
        color: #991b1b;
        border: 1px solid #fecaca;
    }
    .status-pill-blue {
        background: #eff6ff;
        color: #1e40af;
        border: 1px solid #bfdbfe;
    }

    /* Video Viewport Frame */
    .video-viewport-box {
        background: #020617;
        border-radius: 12px;
        padding: 8px;
        border: 1px solid #1e293b;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }

    /* Dataframe Tables */
    [data-testid="stDataFrame"] {
        border-radius: 10px !important;
        border: 1px solid #cbd5e1 !important;
        background: #ffffff !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        overflow: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize databases
create_database()
try:
    init_auth_db()
except AuthenticationConfigurationError as e:
    st.error(f"🚨 **Authentication Configuration Error:** {e}")
    st.info("💡 **Resolution:** Please configure `ADMIN_PASSWORD` and `KIOSK_PASSWORD` in your `.env` file or environment variables before running the application.")
    st.stop()

# --------------------------------------------------
# Security Gateway (Authentication Check & Inactivity Timeout)
# --------------------------------------------------
if not st.session_state.get("authenticated", False):
    render_login_screen()
    st.stop()

# Validate Session Inactivity Timeout Guard
if not check_session_timeout():
    st.stop()


# --------------------------------------------------
# Database Utilities & Live Data Loaders
# --------------------------------------------------
def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def load_students_df():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT student_id, name, department, year, consent_status, created_at
        FROM students
        ORDER BY student_id ASC
    """, conn)
    conn.close()
    return df


def load_attendance_df():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT id, student_id, name, department, attendance_date, entry_time, similarity_score, verification_status
        FROM attendance
        ORDER BY attendance_date DESC, entry_time DESC
    """, conn)
    conn.close()
    if not df.empty:
        df["punctuality"] = df["entry_time"].apply(classify_punctuality)
    return df


def load_today_attendance_df():
    """Fetch all attendance records logged today."""
    conn = get_connection()
    today_str = datetime.now().strftime("%Y-%m-%d")
    df = pd.read_sql_query("""
        SELECT id, student_id, name, department, attendance_date, entry_time, similarity_score, verification_status
        FROM attendance
        WHERE attendance_date = ?
        ORDER BY entry_time DESC
    """, conn, params=(today_str,))
    conn.close()
    if not df.empty:
        df["punctuality"] = df["entry_time"].apply(classify_punctuality)
    return df


students_df = load_students_df()
attendance_df = load_attendance_df()
user_role = st.session_state.get("role", "admin")
user_full_name = st.session_state.get("full_name", "User")
username = st.session_state.get("username", "user")

# --------------------------------------------------
# Sidebar: Navigation, Profile & Settings
# --------------------------------------------------
with st.sidebar:
    # Institution Brand Banner
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=160)
    st.markdown("### **KPRIT Biometrics**")
    st.caption("Kommuri Pratap Reddy Institute of Technology\nDept. of CSE (DS / AI & ML) • UGC Autonomous")
    st.divider()

    # User Profile Card
    st.markdown(f"""
    <div style="background: #1e293b; border-radius: 8px; padding: 12px 14px; border: 1px solid #334155; margin-bottom: 12px;">
        <div style="font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">Active Session</div>
        <div style="font-weight: 700; font-size: 0.95rem; color: #ffffff; margin-top: 2px;">{user_full_name}</div>
        <div style="margin-top: 6px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span class="{'admin-role-badge' if user_role == 'admin' else 'status-pill status-pill-blue'}">
                {'👑 ADMINISTRATOR' if user_role == 'admin' else '🖥️ KIOSK TERMINAL'} ({username})
            </span>
            <span class="status-pill" style="background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.45); font-size: 0.72rem; padding: 2px 8px;">
                🔒 HTTPS / TLS
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Sign Out", use_container_width=True):
        logout()

    st.divider()

    # Sidebar Navigation Menu
    st.markdown("<div style='font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-bottom: 8px;'>Navigation Menu</div>", unsafe_allow_html=True)

    if user_role == "kiosk":
        nav_options = ["📸 Live Attendance & Verification"]
    else:
        nav_options = [
            "📊 Dashboard",
            "📸 Live Attendance & Verification",
            "👥 Student Management",
            "📋 Attendance History",
            "⏰ Punctuality Analytics",
            "ℹ️ System Information"
        ]

    selected_nav = st.radio("Navigation", nav_options, label_visibility="collapsed")

    st.divider()

    # Verification Engine Settings Expander
    with st.expander("⚙️ Biometric Engine Config", expanded=False):
        st.caption("Fine-tune ArcFace 512-D parameters and camera hardware.")

        active_threshold = st.slider(
            "Decision Threshold (t)",
            min_value=0.40,
            max_value=0.75,
            value=DEFAULT_VERIFICATION_THRESHOLD,
            step=0.01,
            help="Optimal calibrated threshold: 0.58"
        )
        active_margin = st.slider(
            "Ambiguity Margin (m)",
            min_value=0.01,
            max_value=0.20,
            value=DEFAULT_MIN_MARGIN,
            step=0.01,
            help="Minimum separation between best and second-best matches (default: 0.05)"
        )
        active_consecutive = st.slider(
            "Consecutive Frames (N)",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
            help="Consecutive verified frames required before committing attendance (default: 3)"
        )
        active_cam_index = st.number_input(
            "Webcam Index",
            min_value=0,
            max_value=4,
            value=0,
            step=1,
            help="Index 0 = Default Laptop Camera | Index 1/2 = Iriun Webcam or USB camera"
        )
        st.caption("💡 For Iriun Webcam, select Device Index 1 or 2.")

    st.caption("KPRIT Smart Attendance v3.0 • Enterprise Edition")


# --------------------------------------------------
# Top Institutional Header
# --------------------------------------------------
head_col1, head_col2 = st.columns([1, 8], vertical_alignment="center")
with head_col1:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=95)
with head_col2:
    st.markdown("""
    <div style="display: flex; flex-direction: column; justify-content: center;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px; flex-wrap: wrap;">
            <span class="status-pill status-pill-blue">UGC AUTONOMOUS</span>
            <span class="status-pill status-pill-green">AICTE APPROVED</span>
            <span class="status-pill status-pill-cyan">NAAC ACCREDITED</span>
            <span class="status-pill" style="background: #ecfdf5; color: #047857; border: 1.5px solid #10b981; font-weight: 700; box-shadow: 0 1px 2px rgba(16,185,129,0.15);">
                🔒 HTTPS SECURED (TLS 1.3)
            </span>
        </div>
        <h3 style="margin: 0; color: #0f172a; font-weight: 700; font-size: 1.35rem;">KOMMURI PRATAP REDDY INSTITUTE OF TECHNOLOGY</h3>
        <p style="margin: 0; color: #64748b; font-size: 0.85rem; font-weight: 500;">
            Department of Computer Science & Engineering (Data Science / AI & ML) • Face Verification Smart Attendance
        </p>
    </div>
    """, unsafe_allow_html=True)

st.write("")


# ==================================================
# VIEW 1: 📊 MAIN DASHBOARD
# ==================================================
def render_main_dashboard():
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
            <h2 style="margin:0; font-weight: 700; color: #0f172a; font-size: 1.5rem;">System Overview & Analytics</h2>
            <p style="margin:0; color: #64748b; font-size: 0.88rem;">Real-time biometric attendance metrics, punctuality breakdown, and department distribution.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Filter Toolbar
    f_col1, f_col2, f_col3 = st.columns([1.5, 1.5, 1], vertical_alignment="bottom")
    with f_col1:
        dates_list = sorted(attendance_df["attendance_date"].unique(), reverse=True) if not attendance_df.empty else []
        today_str = datetime.now().strftime("%Y-%m-%d")
        default_idx = dates_list.index(today_str) if today_str in dates_list else 0
        selected_date = st.selectbox("📅 Select Date Scope:", dates_list if dates_list else [today_str], index=default_idx)

    with f_col2:
        dept_list = ["All Departments"] + (sorted(students_df["department"].unique().tolist()) if not students_df.empty else [])
        selected_dept = st.selectbox("🏫 Filter Department:", dept_list)

    with f_col3:
        if st.button("🔄 Sync Live Data", use_container_width=True):
            st.rerun()

    # Filtered dataframe
    filtered_df = attendance_df.copy()
    if not filtered_df.empty and selected_date:
        filtered_df = filtered_df[filtered_df["attendance_date"] == selected_date]
    if selected_dept != "All Departments" and not filtered_df.empty:
        filtered_df = filtered_df[filtered_df["department"] == selected_dept]

    # Metrics Calculation
    scoped_students = students_df if selected_dept == "All Departments" else students_df[students_df["department"] == selected_dept]
    total_reg = len(scoped_students)
    verified_entries = filtered_df[filtered_df["verification_status"] == "VERIFIED"] if not filtered_df.empty else pd.DataFrame()
    present_today = len(verified_entries["student_id"].unique()) if not verified_entries.empty else 0
    absent_today = max(0, total_reg - present_today)
    att_rate = (present_today / total_reg * 100) if total_reg > 0 else 0.0

    on_time_count = len(verified_entries[verified_entries["punctuality"] == "ON TIME"]) if not verified_entries.empty else 0
    late_count = len(verified_entries[verified_entries["punctuality"] == "LATE"]) if not verified_entries.empty else 0
    very_late_count = len(verified_entries[verified_entries["punctuality"] == "VERY LATE"]) if not verified_entries.empty else 0
    on_time_rate = (on_time_count / present_today * 100) if present_today > 0 else 0.0

    # High-impact Uniform KPI Cards
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <div class="kpi-title">👥 Registered Students</div>
            <div class="kpi-value">{total_reg}</div>
            <div class="kpi-sub">Active enrolled profiles</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title" style="color: #059669;">✅ Present on Date</div>
            <div class="kpi-value" style="color: #059669;">{present_today}</div>
            <div class="kpi-sub">Verified attendees</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title" style="color: #dc2626;">❌ Absent on Date</div>
            <div class="kpi-value" style="color: #dc2626;">{absent_today}</div>
            <div class="kpi-sub">Pending verification</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title" style="color: #2563eb;">📈 Attendance Rate</div>
            <div class="kpi-value" style="color: #2563eb;">{att_rate:.1f}%</div>
            <div class="kpi-sub">Target: &ge; 85.0%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title" style="color: #0d9488;">⏰ On-Time Arrivals</div>
            <div class="kpi-value" style="color: #0d9488;">{on_time_count}</div>
            <div class="kpi-sub">{on_time_rate:.1f}% punctuality rate</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title" style="color: #7c3aed;">🔒 Verified Logs</div>
            <div class="kpi-value" style="color: #7c3aed;">{len(attendance_df)}</div>
            <div class="kpi-sub">Total database events</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Visualizations Row
    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        st.markdown("<h4 style='color: #0f172a; font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;'>⏰ Punctuality Classification</h4>", unsafe_allow_html=True)
        punc_data = pd.DataFrame({
            "Classification": ["ON TIME (≤09:30)", "LATE (09:30-09:40)", "VERY LATE (≥09:40)"],
            "Students": [on_time_count, late_count, very_late_count]
        }).set_index("Classification")
        st.bar_chart(punc_data, color="#2563eb", use_container_width=True)

    with c_chart2:
        st.markdown("<h4 style='color: #0f172a; font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;'>🏫 Department-wise Attendance</h4>", unsafe_allow_html=True)
        if not attendance_df.empty:
            dept_chart = attendance_df.groupby("department").size().reset_index(name="Attendees").set_index("department")
            st.bar_chart(dept_chart, color="#06b6d4", use_container_width=True)
        else:
            st.info("No attendance records logged yet.")

    # Historical Attendance Trend
    st.markdown("<h4 style='color: #0f172a; font-size: 1.1rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem;'>📅 Attendance Trend Across Dates</h4>", unsafe_allow_html=True)
    if not attendance_df.empty:
        trend = attendance_df[attendance_df["verification_status"] == "VERIFIED"].groupby("attendance_date").size().reset_index(name="Verified Attendees").set_index("attendance_date")
        st.line_chart(trend, color="#7c3aed", use_container_width=True)
    else:
        st.info("No trend data available.")


# ==================================================
# VIEW 2: 📸 LIVE ATTENDANCE & VERIFICATION
# ==================================================
def render_live_attendance_view():
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
            <h2 style="margin:0; font-weight: 700; color: #0f172a; font-size: 1.5rem;">Live Attendance & Face Verification</h2>
            <p style="margin:0; color: #64748b; font-size: 0.88rem;">Real-time continuous biometric recognition via laptop webcam or Iriun Webcam with auto-attendance logging.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Sub-mode selection tabs
    live_subtab = st.radio(
        "Mode:",
        ["🎥 Live Camera Stream (Real-Time Auto-Attendance)", "📸 Snapshot Capture (1:1 / 1:N)", "📁 Image File Upload"],
        horizontal=True,
        label_visibility="collapsed"
    )

    if live_subtab == "🎥 Live Camera Stream (Real-Time Auto-Attendance)":
        render_live_stream_terminal()
    elif live_subtab == "📸 Snapshot Capture (1:1 / 1:N)":
        render_snapshot_verification()
    else:
        render_file_upload_verification()


def render_live_stream_terminal():
    if "camera_active" not in st.session_state:
        st.session_state.camera_active = False

    # Top Toolbar Card
    st.markdown('<div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">', unsafe_allow_html=True)
    t_col1, t_col2, t_col3, t_col4 = st.columns([1.2, 1.2, 1.8, 1.8], vertical_alignment="center")

    with t_col1:
        if st.button("▶️ Start Camera", type="primary", disabled=st.session_state.camera_active, use_container_width=True):
            st.session_state.camera_active = True
            st.rerun()

    with t_col2:
        if st.button("⏹️ Stop Camera", type="secondary", disabled=not st.session_state.camera_active, use_container_width=True):
            st.session_state.camera_active = False
            st.rerun()

    with t_col3:
        auto_record_toggle = st.checkbox("⚡ Auto-Record to SQLite", value=True, help="Automatically write attendance entry on stable consecutive verification.")

    with t_col4:
        if st.session_state.camera_active:
            st.markdown("<div style='text-align: right;'><span class='status-pill status-pill-green'>🟢 LIVE FEED ACTIVE</span></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align: right;'><span class='status-pill status-pill-red'>🔴 CAMERA IDLE</span></div>", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Real-Time Main Stage: Left = Video Stream, Right = Biometric Feedback
    col_video, col_info = st.columns([1.35, 1])

    with col_video:
        st.markdown("<h4 style='color: #0f172a; font-weight: 600; font-size: 1.05rem; margin-bottom: 0.5rem;'>📹 Live Video Viewport</h4>", unsafe_allow_html=True)
        frame_placeholder = st.empty()
        status_alert_placeholder = st.empty()

    with col_info:
        st.markdown("<h4 style='color: #0f172a; font-weight: 600; font-size: 1.05rem; margin-bottom: 0.5rem;'>🎯 Live Biometric Analysis</h4>", unsafe_allow_html=True)
        info_card_placeholder = st.empty()
        log_feedback_placeholder = st.empty()

    st.divider()

    # Real-Time Live Today Roster
    st.markdown("<h4 style='color: #0f172a; font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem;'>📋 Today's Live Attendance Roster</h4>", unsafe_allow_html=True)
    roster_placeholder = st.empty()

    today_df = load_today_attendance_df()
    def display_roster(df):
        if df.empty:
            roster_placeholder.info("No attendance entries recorded today yet.")
        else:
            roster_placeholder.dataframe(
                df[["student_id", "name", "department", "entry_time", "similarity_score", "verification_status", "punctuality"]],
                use_container_width=True,
                hide_index=True
            )
    display_roster(today_df)

    # Inactive Camera Placeholder
    if not st.session_state.camera_active:
        frame_placeholder.markdown("""
        <div style="background: #020617; border-radius: 12px; height: 380px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #94a3b8; border: 1px solid #1e293b;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">📷</div>
            <div style="font-weight: 600; color: #f1f5f9; font-size: 1.1rem;">Camera Viewport Standby</div>
            <div style="font-size: 0.85rem; margin-top: 4px;">Click <b>▶️ Start Camera</b> above to begin real-time verification.</div>
            <div style="font-size: 0.78rem; color: #64748b; margin-top: 8px;">Supports Primary Laptop Webcam or Iriun Webcam (USB / Wi-Fi)</div>
        </div>
        """, unsafe_allow_html=True)

        info_card_placeholder.markdown(f"""
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="font-weight: 700; color: #0f172a; margin-bottom: 0.5rem; font-size: 0.95rem;">⚡ Biometric Engine Operational</div>
            <div style="font-size: 0.82rem; color: #475569; line-height: 1.6;">
                • Model: <b>InsightFace ArcFace buffalo_l (512-D)</b><br>
                • Operating Threshold (t): <code>{active_threshold}</code><br>
                • Ambiguity Margin (m): <code>{active_margin}</code><br>
                • Required Stability: <code>{active_consecutive} frames</code><br>
                • Anti-Duplicate Rule: <b>1 verified entry per student / day</b><br>
                • Camera Index: <code>{active_cam_index}</code>
            </div>
            <div style="margin-top: 1rem; padding: 0.75rem; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 0.75rem; color: #64748b;">
                💡 <b>Status Indicator Guide:</b><br>
                <span class="status-pill status-pill-green" style="margin-top:4px;">GREEN: VERIFIED & MARKED</span><br>
                <span class="status-pill status-pill-amber" style="margin-top:4px;">AMBER: ALREADY LOGGED TODAY</span><br>
                <span class="status-pill status-pill-cyan" style="margin-top:4px;">CYAN: VERIFYING</span><br>
                <span class="status-pill status-pill-orange" style="margin-top:4px;">ORANGE: UNKNOWN / UNCERTAIN</span><br>
                <span class="status-pill status-pill-red" style="margin-top:4px;">RED: UNKNOWN / REJECTED</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # CAMERA ACTIVE STREAMING LOOP
    cap = cv2.VideoCapture(active_cam_index)
    if not cap.isOpened():
        st.session_state.camera_active = False
        frame_placeholder.error(
            f"❌ Unable to connect to camera device at index {active_cam_index}.\n\n"
            "Troubleshooting Steps:\n"
            "1. If using Iriun Webcam, ensure the Iriun app is running on both phone and laptop, and try index 1 or 2.\n"
            "2. If using integrated webcam, ensure no other program (Teams, Zoom, Camera app) is using it.\n"
            "3. Verify OS Camera Privacy Settings allow desktop app access."
        )
        return

    tracker = LiveAttendanceTracker(consecutive_required=active_consecutive)
    tracker.refresh_enrolled_students()

    try:
        while st.session_state.camera_active:
            ret, frame = cap.read()
            if not ret:
                status_alert_placeholder.warning("⚠️ Frame dropped from camera stream. Re-reading...")
                break

            annotated_frame, face_evals, newly_recorded = tracker.process_frame(
                frame=frame,
                threshold=active_threshold,
                min_margin=active_margin,
                auto_record=auto_record_toggle
            )

            # Display video frame
            rgb_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(rgb_frame, channels="RGB", use_container_width=True)

            # Update Biometric Analysis Panel
            if len(face_evals) == 0:
                info_card_placeholder.markdown("""
                <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 12px; padding: 1.25rem;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="status-pill status-pill-amber">SCANNING</span>
                        <b style="color: #92400e; font-size: 0.95rem;">Searching for Faces...</b>
                    </div>
                    <p style="margin-top: 0.5rem; margin-bottom: 0; color: #78350f; font-size: 0.85rem;">
                        Position face directly in front of camera with adequate lighting.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            elif len(face_evals) > 1:
                # Multiple faces in frame
                multi_html = f"""
                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 1.25rem;">
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                        <span class="status-pill status-pill-blue">MULTI-FACE</span>
                        <b style="color: #1e40af; font-size: 0.95rem;">{len(face_evals)} Faces Detected Simultaneously</b>
                    </div>
                    <div style="font-size: 0.82rem; color: #1e3a8a; margin-bottom: 8px;">Independent facial evaluation:</div>
                    <ul style="margin: 0; padding-left: 18px; font-size: 0.82rem; color: #1e3a8a;">
                """
                for fe in face_evals:
                    if fe["verified"]:
                        badge = "ALREADY RECORDED" if fe["already_marked"] else ("VERIFIED" if fe["status"] == "VERIFIED" else "STABILIZING")
                        multi_html += f"<li><b>{fe['name']}</b> ({fe['student_id']}) — Score: <code>{fe['score']:.2f}</code> [{badge}]</li>"
                    elif fe["is_ambiguous"]:
                        multi_html += f"<li><b>Ambiguous Match</b> — Margin: <code>{fe['score_margin']:.2f} < {active_margin}</code> [UNCERTAIN]</li>"
                    else:
                        multi_html += f"<li><b>Unknown Person</b> — Score: <code>{fe['score']:.2f}</code> [REJECTED]</li>"
                multi_html += "</ul></div>"
                info_card_placeholder.markdown(multi_html, unsafe_allow_html=True)
            else:
                fe = face_evals[0]
                if fe["verified"]:
                    if fe["already_marked"]:
                        pill_class = "status-pill-amber"
                        badge_text = "ALREADY LOGGED TODAY"
                        card_border = "#f59e0b"
                        card_bg = "#fffbeb"
                        card_text = "#92400e"
                    elif fe["status"] == "VERIFIED":
                        pill_class = "status-pill-green"
                        badge_text = "VERIFIED & MARKED"
                        card_border = "#10b981"
                        card_bg = "#ecfdf5"
                        card_text = "#065f46"
                    else:
                        pill_class = "status-pill-cyan"
                        badge_text = f"VERIFYING ({fe['consecutive_count']}/{fe['consecutive_required']})"
                        card_border = "#06b6d4"
                        card_bg = "#ecfeff"
                        card_text = "#155e75"

                    punc_color = "#059669" if fe["punctuality"] == "ON TIME" else ("#d97706" if fe["punctuality"] == "LATE" else "#dc2626")

                    info_card_placeholder.markdown(f"""
                    <div style="background: {card_bg}; border: 1.5px solid {card_border}; border-radius: 12px; padding: 1.25rem;">
                        <span class="status-pill {pill_class}">{badge_text}</span>
                        <h3 style="color: {card_text}; margin: 8px 0 2px 0; font-size: 1.25rem; font-weight: 700;">{fe['name']}</h3>
                        <div style="font-size: 0.85rem; color: #475569; margin-bottom: 8px;">
                            <b>ID:</b> <code>{fe['student_id']}</code> &nbsp;|&nbsp; <b>Dept:</b> {fe['department']}
                        </div>
                        <div style="border-top: 1px solid rgba(0,0,0,0.06); padding-top: 8px; font-size: 0.82rem; color: #334155; line-height: 1.6;">
                            • Cosine Similarity: <b>{fe['score']:.4f}</b> (Threshold: {active_threshold})<br>
                            • Decision Margin: <b>+{fe['score_margin']:.4f}</b> (Margin: {active_margin})<br>
                            • Punctuality: <b style="color: {punc_color};">{fe['punctuality']}</b><br>
                            • Frame Stability: <b>{fe['consecutive_count']}/{fe['consecutive_required']} frames</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                elif fe["is_ambiguous"]:
                    info_card_placeholder.markdown(f"""
                    <div style="background: #fff7ed; border: 1.5px solid #f97316; border-radius: 12px; padding: 1.25rem;">
                        <span class="status-pill status-pill-orange">UNKNOWN / UNCERTAIN</span>
                        <h4 style="color: #9a3412; margin: 8px 0 4px 0; font-weight: 700;">Ambiguous Biometric Match</h4>
                        <p style="margin: 0; font-size: 0.82rem; color: #7c2d12; line-height: 1.5;">
                            Score meets threshold (<code>{fe['score']:.4f}</code>), but margin to second-best candidate (<code>{fe['score_margin']:.4f}</code>) is below required margin <code>{active_margin}</code>.
                        </p>
                        <div style="margin-top: 6px; font-size: 0.78rem; font-weight: 600; color: #9a3412;">
                            ⛔ Attendance rejected to prevent false identification.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    info_card_placeholder.markdown(f"""
                    <div style="background: #fef2f2; border: 1.5px solid #ef4444; border-radius: 12px; padding: 1.25rem;">
                        <span class="status-pill status-pill-red">UNKNOWN / REJECTED</span>
                        <h4 style="color: #991b1b; margin: 8px 0 4px 0; font-weight: 700;">Face Not Recognized</h4>
                        <p style="margin: 0; font-size: 0.82rem; color: #7f1d1d; line-height: 1.5;">
                            Highest match score is <code>{fe['score']:.4f}</code> (Below threshold <code>{active_threshold}</code>).
                        </p>
                        <div style="margin-top: 6px; font-size: 0.78rem; font-weight: 600; color: #991b1b;">
                            ⛔ No attendance logged.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            if newly_recorded:
                for rec in newly_recorded:
                    log_feedback_placeholder.success(f"🎉 **Attendance Recorded!** {rec['name']} ({rec['student_id']}) logged at {rec['time']} [{classify_punctuality(rec['time'])}].")
                today_df = load_today_attendance_df()
                display_roster(today_df)

            time.sleep(0.03)

    except Exception as e:
        status_alert_placeholder.error(f"❌ Camera stream exception: {e}")
    finally:
        cap.release()
        status_alert_placeholder.info("🔒 Camera session released.")


def render_snapshot_verification():
    """Manual single-frame camera snapshot verification mode."""
    v_col1, v_col2 = st.columns([1, 1])

    with v_col1:
        mode = st.radio("Verification Type:", ["1:N Identification (Auto-Match Face)", "1:1 Claimed Verification (ID Check)"], horizontal=True, key="snap_mode")
        claimed_id = None
        if mode == "1:1 Claimed Verification (ID Check)":
            student_choices = students_df["student_id"].tolist() if not students_df.empty else ["DS001"]
            claimed_id = st.selectbox("Select Claimed Student ID:", student_choices, key="snap_claimed_id")

        camera_photo = st.camera_input("Position face in center and capture snapshot:")
        query_image = None
        if camera_photo is not None:
            img_pil = Image.open(camera_photo)
            query_image = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    with v_col2:
        st.markdown("<h4 style='color: #0f172a; font-weight: 600;'>🎯 Snapshot Verification Result</h4>", unsafe_allow_html=True)
        if query_image is not None:
            st.image(cv2.cvtColor(query_image, cv2.COLOR_BGR2RGB), caption="Captured Snapshot", width=380)
            run_single_image_evaluation(query_image, mode, claimed_id, active_threshold, active_margin)
        else:
            st.info("👈 Capture a snapshot with the camera above to begin.")


def render_file_upload_verification():
    """Manual image file upload verification mode."""
    v_col1, v_col2 = st.columns([1, 1])

    with v_col1:
        mode = st.radio("Verification Type:", ["1:N Identification (Auto-Match Face)", "1:1 Claimed Verification (ID Check)"], horizontal=True, key="upload_mode")
        claimed_id = None
        if mode == "1:1 Claimed Verification (ID Check)":
            student_choices = students_df["student_id"].tolist() if not students_df.empty else ["DS001"]
            claimed_id = st.selectbox("Select Claimed Student ID:", student_choices, key="upload_claimed_id")

        uploaded_file = st.file_uploader("Choose an image (JPEG/PNG):", type=["jpg", "jpeg", "png"], key="upload_file")
        query_image = None
        if uploaded_file is not None:
            img_pil = Image.open(uploaded_file)
            query_image = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    with v_col2:
        st.markdown("<h4 style='color: #0f172a; font-weight: 600;'>🎯 Image Verification Result</h4>", unsafe_allow_html=True)
        if query_image is not None:
            st.image(cv2.cvtColor(query_image, cv2.COLOR_BGR2RGB), caption="Uploaded Query Image", width=380)
            run_single_image_evaluation(query_image, mode, claimed_id, active_threshold, active_margin)
        else:
            st.info("👈 Upload an image file to begin.")


def run_single_image_evaluation(query_image, mode, claimed_id, threshold, min_margin):
    """Processes a single captured or uploaded image for verification."""
    with st.spinner("Analyzing face biometrics..."):
        enrolled_students = load_enrolled_students()
        faces = face_engine.detect_faces(query_image)

        if len(faces) == 0:
            st.error("❌ No face detected in the image. Please ensure good lighting and clear face alignment.")
            return

        face = faces[0]
        q_emb = getattr(face, "embedding", None)
        if q_emb is None:
            st.error("❌ Could not extract 512-D face embedding.")
            return

        if mode == "1:1 Claimed Verification (ID Check)" and claimed_id:
            target_s = next((s for s in enrolled_students if s["student_id"] == claimed_id), None)
            if not target_s:
                st.error(f"Enrolled embedding for {claimed_id} not found in database.")
                return

            sim = face_engine.compute_similarity(q_emb, target_s["embedding"])
            st.progress(float(min(1.0, max(0.0, sim))))
            st.write(f"**Similarity Score:** `{sim:.4f}` (Threshold: `{threshold}`)")

            if sim >= threshold:
                st.success(f"✅ **VERIFIED! Identity Confirmed:** {target_s['name']} ({target_s['student_id']})")
                curr_time = datetime.now().strftime("%H:%M:%S")
                punc = classify_punctuality(curr_time)
                st.info(f"⏰ Arrival Time: **{curr_time}** | Punctuality: **{punc}**")

                if st.button("📝 Confirm & Record Attendance", key="rec_snap_1_1"):
                    res = record_attendance(
                        student_id=target_s["student_id"],
                        name=target_s["name"],
                        department=target_s["department"],
                        similarity_score=sim,
                        verification_status="VERIFIED"
                    )
                    if res["status"] == "DUPLICATE":
                        st.warning(f"⚠️ {target_s['name']} is ALREADY marked present today.")
                    else:
                        st.balloons()
                        st.success(f"🎉 Attendance successfully logged for {target_s['name']}!")
            else:
                st.error(f"⛔ **REJECTED! Identity mismatch or score ({sim:.4f}) below threshold ({threshold}).**")

        else:
            # 1:N Identification
            match_info = face_engine.identify_1_to_n(
                query_embedding=q_emb,
                enrolled_students=enrolled_students,
                threshold=threshold,
                min_margin=min_margin
            )

            if match_info["verified"] and match_info["best_student"]:
                student = match_info["best_student"]
                score = match_info["best_score"]
                margin = match_info["score_margin"]

                st.progress(float(min(1.0, max(0.0, score))))
                st.success(f"✅ **MATCH FOUND: {student['name']}**")

                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Student ID:** `{student['student_id']}`")
                    st.write(f"**Department:** {student['department']}")
                with c2:
                    st.write(f"**Match Confidence:** `{score:.4f}`")
                    st.write(f"**Margin:** `+{margin:.4f}`")
                    curr_time = datetime.now().strftime("%H:%M:%S")
                    punc = classify_punctuality(curr_time)
                    st.write(f"**Punctuality:** `{punc}`")

                if st.button("📝 Log Attendance Now", key="rec_snap_1_n"):
                    res = record_attendance(
                        student_id=student["student_id"],
                        name=student["name"],
                        department=student["department"],
                        similarity_score=score,
                        verification_status="VERIFIED"
                    )
                    if res["status"] == "DUPLICATE":
                        st.warning(f"⚠️ {student['name']} is ALREADY marked present today.")
                    else:
                        st.balloons()
                        st.success(f"🎉 Attendance successfully logged for {student['name']}!")
            elif match_info["is_ambiguous"]:
                st.warning(f"⚠️ **UNCERTAIN IDENTITY: Ambiguous Match!** Top score {match_info['best_score']:.4f} but margin ({match_info['score_margin']:.4f}) < {min_margin}. Attendance not recorded.")
            else:
                st.error(f"⛔ **UNKNOWN FACE! Highest score: {match_info['best_score']:.4f} < Threshold {threshold}**")


# ==================================================
# VIEW 3: 👥 STUDENT MANAGEMENT
# ==================================================
def render_student_management_view():
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
            <h2 style="margin:0; font-weight: 700; color: #0f172a; font-size: 1.5rem;">Student Management & Biometric Directory</h2>
            <p style="margin:0; color: #64748b; font-size: 0.88rem;">Manage enrolled student profiles, register new faces, and view biometric ArcFace templates.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    sm_tabs = st.tabs(["📋 Registered Students Directory", "✍️ Enroll New Student", "🔍 Biometric Templates"])

    with sm_tabs[0]:
        st.markdown("<h4 style='color: #0f172a; font-weight: 600; font-size: 1.1rem;'>Active Enrolled Student Registry</h4>", unsafe_allow_html=True)
        if students_df.empty:
            st.info("No students registered in database.")
        else:
            s_filter_col1, s_filter_col2 = st.columns([2, 1])
            with s_filter_col1:
                search_student = st.text_input("🔍 Search Student by Name or ID:", "", placeholder="Type name or student ID...")
            with s_filter_col2:
                dept_filter = st.selectbox("Department:", ["All"] + sorted(students_df["department"].unique().tolist()), key="sm_dept_filter")

            view_df = students_df.copy()
            if search_student:
                view_df = view_df[
                    view_df["name"].str.contains(search_student, case=False, na=False) |
                    view_df["student_id"].str.contains(search_student, case=False, na=False)
                ]
            if dept_filter != "All":
                view_df = view_df[view_df["department"] == dept_filter]

            # Re-label columns for presentation
            display_df = view_df.rename(columns={
                "student_id": "Student ID",
                "name": "Full Name",
                "department": "Department",
                "year": "Academic Year",
                "consent_status": "Consent Given",
                "created_at": "Enrolled Date"
            })
            display_df["Enrollment Status"] = "✅ Active & Enrolled"

            st.dataframe(
                display_df[["Student ID", "Full Name", "Department", "Academic Year", "Enrollment Status", "Consent Given", "Enrolled Date"]],
                use_container_width=True,
                hide_index=True
            )

    with sm_tabs[1]:
        st.markdown("<h4 style='color: #0f172a; font-weight: 600; font-size: 1.1rem;'>Biometric Student Enrollment Wizard</h4>", unsafe_allow_html=True)
        e_col1, e_col2 = st.columns([1, 1])

        with e_col1:
            with st.form("enrollment_form"):
                new_id = st.text_input("Student ID (e.g. DS003):").strip()
                new_name = st.text_input("Full Name:").strip()
                new_dept = st.selectbox("Department:", ["CSE-DS", "CSE-AIML", "CSE", "IT", "ECE", "EEE", "MECH", "CIVIL"])
                new_year = st.selectbox("Year of Study:", ["1", "2", "3", "4"])
                consent_check = st.checkbox("Student provides informed consent for facial feature embedding storage.")

                enroll_image_source = st.radio("Photo Capture Mode:", ["Webcam Capture", "Upload Image File"], horizontal=True)
                enroll_submit = st.form_submit_button("🚀 Commit Student Enrollment", use_container_width=True)

        with e_col2:
            st.markdown("<h5 style='color: #0f172a; font-weight: 600;'>📷 Student Portrait Preview</h5>", unsafe_allow_html=True)
            enroll_image = None
            if enroll_image_source == "Webcam Capture":
                enroll_cam = st.camera_input("Capture official portrait:")
                if enroll_cam is not None:
                    img_pil = Image.open(enroll_cam)
                    enroll_image = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            else:
                enroll_file = st.file_uploader("Upload portrait photo:", type=["jpg", "jpeg", "png"], key="enroll_upload")
                if enroll_file is not None:
                    img_pil = Image.open(enroll_file)
                    enroll_image = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

            if enroll_image is not None:
                st.image(cv2.cvtColor(enroll_image, cv2.COLOR_BGR2RGB), caption="Portrait Preview", width=280)

        if enroll_submit:
            if not new_id or not new_name:
                st.error("Please provide both Student ID and Full Name.")
            elif not consent_check:
                st.error("Student informed consent is required to register biometrics.")
            elif enroll_image is None:
                st.error("Please capture or upload a student portrait.")
            else:
                with st.spinner("Analyzing face biometrics and generating 512-D template..."):
                    res = enroll_student(
                        student_id=new_id,
                        name=new_name,
                        department=new_dept,
                        year=new_year,
                        image_or_path=enroll_image,
                        consent="yes"
                    )

                    if res["success"]:
                        st.balloons()
                        st.success(f"🎉 **{res['message']}**")
                        st.json({
                            "Student ID": res["student_id"],
                            "Name": res["name"],
                            "Department": res["department"],
                            "Embedding Dimensions": "512-D ArcFace Vector",
                            "Template File": res["embedding_path"]
                        })
                    else:
                        st.error(f"❌ {res['message']}")

    with sm_tabs[2]:
        st.markdown("<h4 style='color: #0f172a; font-weight: 600; font-size: 1.1rem;'>Biometric Template Verification</h4>", unsafe_allow_html=True)
        enrolled_list = load_enrolled_students()
        st.write(f"Total Active Facial Templates: **{len(enrolled_list)}**")

        for s in enrolled_list:
            st.markdown(f"""
            <div style="background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <b style="font-size: 1.05rem; color: #0f172a;">{s['name']}</b> &nbsp;
                        <span class="status-pill status-pill-blue">{s['student_id']}</span>
                        <div style="font-size: 0.85rem; color: #64748b; margin-top: 2px;">
                            Department: {s['department']} &nbsp;|&nbsp; Academic Year: {s['year']}
                        </div>
                    </div>
                    <div>
                        <span class="status-pill status-pill-green">512-D TENSOR LOADED</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ==================================================
# VIEW 4: 📋 ATTENDANCE HISTORY
# ==================================================
def render_attendance_history_view():
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
            <h2 style="margin:0; font-weight: 700; color: #0f172a; font-size: 1.5rem;">Attendance History & Records</h2>
            <p style="margin:0; color: #64748b; font-size: 0.88rem;">Search, filter, inspect and export complete institutional attendance logs.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if attendance_df.empty:
        st.info("No attendance records found in database.")
        return

    # Multi-Filter Toolbar
    col_s1, col_s2, col_s3, col_s4 = st.columns([2, 1.2, 1.2, 1.2])

    with col_s1:
        search_kw = st.text_input("🔍 Search Student:", placeholder="Search by student ID or name...")

    with col_s2:
        dates = ["All Dates"] + sorted(attendance_df["attendance_date"].unique().tolist(), reverse=True)
        sel_date = st.selectbox("Date:", dates)

    with col_s3:
        depts = ["All Departments"] + sorted(attendance_df["department"].unique().tolist())
        sel_dept = st.selectbox("Department:", depts, key="hist_dept")

    with col_s4:
        puncs = ["All Punctuality", "ON TIME", "LATE", "VERY LATE"]
        sel_punc = st.selectbox("Punctuality:", puncs)

    # Filter logic
    hist_df = attendance_df.copy()
    if search_kw:
        hist_df = hist_df[
            hist_df["name"].str.contains(search_kw, case=False, na=False) |
            hist_df["student_id"].str.contains(search_kw, case=False, na=False)
        ]
    if sel_date != "All Dates":
        hist_df = hist_df[hist_df["attendance_date"] == sel_date]
    if sel_dept != "All Departments":
        hist_df = hist_df[hist_df["department"] == sel_dept]
    if sel_punc != "All Punctuality":
        hist_df = hist_df[hist_df["punctuality"] == sel_punc]

    st.write(f"Showing **{len(hist_df)}** matching attendance event(s):")

    st.dataframe(
        hist_df[[
            "id", "student_id", "name", "department",
            "attendance_date", "entry_time", "similarity_score",
            "verification_status", "punctuality"
        ]].rename(columns={
            "id": "Log ID",
            "student_id": "Student ID",
            "name": "Full Name",
            "department": "Department",
            "attendance_date": "Date",
            "entry_time": "Entry Time",
            "similarity_score": "Confidence",
            "verification_status": "Status",
            "punctuality": "Punctuality"
        }),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # Export Section
    st.markdown("<h4 style='color: #0f172a; font-weight: 600;'>📥 Export Filtered Attendance Report</h4>", unsafe_allow_html=True)
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    csv_data = hist_df.to_csv(index=False).encode('utf-8')
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_filename = f"kprit_attendance_{timestamp_str}.csv"

    st.download_button(
        label="⬇️ Download Attendance CSV",
        data=csv_data,
        file_name=export_filename,
        mime="text/csv",
        type="primary"
    )


# ==================================================
# VIEW 5: ⏰ PUNCTUALITY ANALYTICS
# ==================================================
def render_punctuality_view():
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
            <h2 style="margin:0; font-weight: 700; color: #0f172a; font-size: 1.5rem;">Punctuality Analytics & Policy Audit</h2>
            <p style="margin:0; color: #64748b; font-size: 0.88rem;">Punctuality schedule policy tracking, arrival distribution, and student-level compliance breakdown.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Schedule Rules Card
    st.markdown("""
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
        <div style="font-weight: 700; color: #0f172a; margin-bottom: 0.5rem; font-size: 1rem;">🏛️ KPRIT Institutional Punctuality Timetable Policy</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-top: 0.75rem;">
            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 0.75rem 1rem;">
                <span class="status-pill status-pill-green">ON TIME</span>
                <div style="font-weight: 700; color: #065f46; font-size: 1.1rem; margin-top: 4px;">09:00:00 – 09:30:00</div>
                <div style="font-size: 0.78rem; color: #047857; margin-top: 2px;">Includes early arrivals prior to 09:00 AM</div>
            </div>
            <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 0.75rem 1rem;">
                <span class="status-pill status-pill-amber">LATE</span>
                <div style="font-weight: 700; color: #92400e; font-size: 1.1rem; margin-top: 4px;">09:30:01 – 09:39:59</div>
                <div style="font-size: 0.78rem; color: #b45309; margin-top: 2px;">Grace period buffer window</div>
            </div>
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 0.75rem 1rem;">
                <span class="status-pill status-pill-red">VERY LATE</span>
                <div style="font-weight: 700; color: #991b1b; font-size: 1.1rem; margin-top: 4px;">&ge; 09:40:00</div>
                <div style="font-size: 0.78rem; color: #b91c1c; margin-top: 2px;">Subject to administrative review</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Summary
    punc_summary = get_punctuality_summary()
    total_events = sum(punc_summary.values())
    on_time_pct = (punc_summary["ON TIME"] / total_events * 100) if total_events > 0 else 0.0

    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <div class="kpi-title" style="color: #059669;">✅ Total On-Time</div>
            <div class="kpi-value" style="color: #059669;">{punc_summary['ON TIME']}</div>
            <div class="kpi-sub">{on_time_pct:.1f}% punctuality compliance</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title" style="color: #d97706;">⚠️ Total Late</div>
            <div class="kpi-value" style="color: #d97706;">{punc_summary['LATE']}</div>
            <div class="kpi-sub">Inside grace buffer</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title" style="color: #dc2626;">🚨 Total Very Late</div>
            <div class="kpi-value" style="color: #dc2626;">{punc_summary['VERY LATE']}</div>
            <div class="kpi-sub">Critical delayed arrivals</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Student-Level Breakdown Leaderboard
    st.markdown("<h4 style='color: #0f172a; font-weight: 600; margin-top: 1.5rem;'>🧑‍🎓 Student Punctuality Breakdown Leaderboard</h4>", unsafe_allow_html=True)
    student_stats = get_student_punctuality()
    if not student_stats:
        st.info("No verified student attendance records available yet.")
    else:
        stats_df = pd.DataFrame(student_stats).rename(columns={
            "student_id": "Student ID",
            "name": "Full Name",
            "department": "Department",
            "total_attendance": "Total Attendance",
            "on_time": "On Time",
            "late": "Late",
            "very_late": "Very Late",
            "punctuality_percentage": "Punctuality %"
        })
        st.dataframe(stats_df, use_container_width=True, hide_index=True)


# ==================================================
# VIEW 6: ℹ️ SYSTEM INFORMATION & EVALUATION
# ==================================================
def render_system_info_view():
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
            <h2 style="margin:0; font-weight: 700; color: #0f172a; font-size: 1.5rem;">System Architecture & Biometric Evaluation</h2>
            <p style="margin:0; color: #64748b; font-size: 0.88rem;">InsightFace model specifications, ArcFace embedding pipeline, and ROC / FAR-FRR performance metrics.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Architecture Specifications Card
    st.markdown(r"""
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
        <h4 style="color: #0f172a; margin-top: 0; font-weight: 700;">🔬 Deep Biometric Architecture Overview</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; margin-top: 1rem;">
            <div>
                <b>• Face Detection Backbone:</b><br>
                <span style="color: #475569; font-size: 0.9em;">RetinaFace (det_10g.onnx, ResNet-50 Feature Pyramid Network)</span>
            </div>
            <div>
                <b>• Feature Representation:</b><br>
                <span style="color: #475569; font-size: 0.9em;">ArcFace 512-Dimensional normalized angular embedding vector</span>
            </div>
            <div>
                <b>• Distance Metric:</b><br>
                <span style="color: #475569; font-size: 0.9em;">Normalized Cosine Similarity: \(\cos(\theta) = \frac{A \cdot B}{\|A\| \|B\|}\)</span>
            </div>
            <div>
                <b>• Calibrated Operating Threshold:</b><br>
                <span style="color: #475569; font-size: 0.9em;">\(t = 0.58\) (Determined via empirical FAR/FRR trade-off curve)</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Charts
    c1, c2 = st.columns(2)
    plot1 = os.path.join(REPORTS_DIR, "far_frr_tradeoff.png")
    plot2 = os.path.join(REPORTS_DIR, "similarity_distribution.png")
    plot3 = os.path.join(REPORTS_DIR, "confusion_matrix.png")

    with c1:
        st.markdown("<h5 style='color: #0f172a; font-weight: 600;'>📈 FAR vs. FRR Trade-off Curve</h5>", unsafe_allow_html=True)
        if os.path.exists(plot1):
            st.image(plot1, use_container_width=True)
        else:
            st.info("Evaluation chart pending.")

    with c2:
        st.markdown("<h5 style='color: #0f172a; font-weight: 600;'>📊 Cosine Score Distribution</h5>", unsafe_allow_html=True)
        if os.path.exists(plot2):
            st.image(plot2, use_container_width=True)
        else:
            st.info("Distribution chart pending.")

    st.divider()

    cm_col, text_col = st.columns([1, 1.2])
    with cm_col:
        st.markdown("<h5 style='color: #0f172a; font-weight: 600;'>🎯 Confusion Matrix (t = 0.58)</h5>", unsafe_allow_html=True)
        if os.path.exists(plot3):
            st.image(plot3, use_container_width=True)

    with text_col:
        st.markdown("""
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem;">
            <h5 style="color: #0f172a; margin-top:0; font-weight: 700;">Biometric Security Assessment</h5>
            <div style="font-size: 0.88rem; color: #334155; line-height: 1.6;">
                • <b>False Acceptance Rate (FAR):</b> <code>0.00%</code> (Zero unauthorized bypass detected)<br>
                • <b>False Rejection Rate (FRR):</b> <code>0.00%</code> (Zero legitimate student rejections)<br>
                • <b>Decision Margin Separation:</b> <code>~0.4351</code> separation between highest impostor score (0.1459) and lowest genuine score (0.5809)<br>
                • <b>Informed Consent Compliance:</b> 100% of enrolled students have consent recorded<br>
                • <b>Security Architecture:</b> 100,000 PBKDF2 iterations for credential hashing
            </div>
        </div>
        """, unsafe_allow_html=True)


# --------------------------------------------------
# Main Navigation Router
# --------------------------------------------------
if selected_nav == "📊 Dashboard":
    render_main_dashboard()
elif selected_nav == "📸 Live Attendance & Verification":
    render_live_attendance_view()
elif selected_nav == "👥 Student Management":
    render_student_management_view()
elif selected_nav == "📋 Attendance History":
    render_attendance_history_view()
elif selected_nav == "⏰ Punctuality Analytics":
    render_punctuality_view()
elif selected_nav == "ℹ️ System Information":
    render_system_info_view()

st.divider()
st.markdown("""
<div style="text-align: center; color: #64748b; font-size: 0.8rem; padding: 0.5rem 0;">
    🏛️ <b>Kommuri Pratap Reddy Institute of Technology (KPRIT)</b> • UGC Autonomous • Affiliated to JNTUH • Hyderabad<br>
    Face Verification Based Smart Attendance Management System • InsightFace ArcFace 512-D
</div>
""", unsafe_allow_html=True)
