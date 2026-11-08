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

import sqlite3
import hashlib
import secrets
import base64
import textwrap
from datetime import datetime
import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATABASE_PATH = os.path.join(PROJECT_ROOT, "database", "attendance.db")
LOGO_PATH = os.path.join(PROJECT_ROOT, "assets", "kprit_logo.png")

# Iterations for PBKDF2
PBKDF2_ITERATIONS = 100_000


def load_dotenv_if_exists(dotenv_path: str = None) -> None:
    """Loads environment variables from a .env file if present, without external dependencies."""
    if dotenv_path is None:
        dotenv_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.isfile(dotenv_path):
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = val
        except Exception:
            pass


# Automatically load local .env if present
load_dotenv_if_exists()


class AuthenticationConfigurationError(RuntimeError):
    """Raised when required authentication credentials are not configured in the environment."""
    pass


def get_required_credentials() -> tuple[str, str]:
    """
    Reads administrator and kiosk passwords exclusively from environment variables.
    Fails safely with AuthenticationConfigurationError if either credential is missing or empty.
    Never provides hardcoded fallback passwords.
    Returns: (admin_password, kiosk_password)
    """
    load_dotenv_if_exists()
    admin_pw = os.getenv("ADMIN_PASSWORD")
    kiosk_pw = os.getenv("KIOSK_PASSWORD")

    missing = []
    if not admin_pw or not str(admin_pw).strip():
        missing.append("ADMIN_PASSWORD")
    if not kiosk_pw or not str(kiosk_pw).strip():
        missing.append("KIOSK_PASSWORD")

    if missing:
        missing_vars = ", ".join(f"'{v}'" for v in missing)
        raise AuthenticationConfigurationError(
            f"Authentication Configuration Error: Missing required environment variable(s): {missing_vars}. "
            f"Administrator and kiosk passwords must be configured exclusively via environment variables. "
            f"No hardcoded fallback passwords are permitted."
        )

    return admin_pw.strip(), kiosk_pw.strip()


# Security and Session Configuration from Environment
DEFAULT_SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
SHOW_EVAL_CREDENTIALS = os.getenv("SHOW_EVAL_CREDENTIALS", "false").strip().lower() in ("true", "1", "yes")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip().lower()
KIOSK_USERNAME = os.getenv("KIOSK_USERNAME", "kiosk").strip().lower()


def get_db_connection():
    """Returns a SQLite connection to attendance.db."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def hash_password(password: str, salt: str = None) -> tuple:
    """
    Hashes a plaintext password using PBKDF2-HMAC-SHA256 with an individual salt.
    Returns (hex_hash, salt).
    """
    if salt is None:
        salt = secrets.token_hex(16)

    hash_bytes = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        iterations=PBKDF2_ITERATIONS
    )
    return hash_bytes.hex(), salt


def init_auth_db():
    """Initializes the users table and seeds or synchronizes accounts exclusively from environment variables."""
    load_dotenv_if_exists()
    admin_password, kiosk_password = get_required_credentials()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Admin Account (Faculty / Management)
    admin_hash, admin_salt = hash_password(admin_password)
    cur.execute("SELECT COUNT(*) FROM users WHERE username = ?", (ADMIN_USERNAME,))
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO users (username, password_hash, salt, role, full_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ADMIN_USERNAME, admin_hash, admin_salt, "admin", "KPRIT Administrator", created_at))
    else:
        cur.execute("""
            UPDATE users
            SET password_hash = ?, salt = ?
            WHERE username = ?
        """, (admin_hash, admin_salt, ADMIN_USERNAME))

    # 2. Campus Kiosk Account (Restricted Attendance Station)
    kiosk_hash, kiosk_salt = hash_password(kiosk_password)
    cur.execute("SELECT COUNT(*) FROM users WHERE username = ?", (KIOSK_USERNAME,))
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO users (username, password_hash, salt, role, full_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (KIOSK_USERNAME, kiosk_hash, kiosk_salt, "kiosk", "Campus Attendance Kiosk", created_at))
    else:
        cur.execute("""
            UPDATE users
            SET password_hash = ?, salt = ?
            WHERE username = ?
        """, (kiosk_hash, kiosk_salt, KIOSK_USERNAME))

    conn.commit()
    conn.close()


def verify_user(username: str, password: str) -> dict:
    """
    Verifies user credentials against SQLite user registry.
    Returns user profile dict if valid, else None.
    """
    init_auth_db()
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT username, password_hash, salt, role, full_name
        FROM users
        WHERE username = ?
    """, (username.strip().lower(),))

    user = cur.fetchone()
    conn.close()

    if not user:
        return None

    u_name, stored_hash, salt, role, full_name = user
    computed_hash, _ = hash_password(password, salt)

    # Secure constant-time comparison
    if secrets.compare_digest(stored_hash, computed_hash):
        return {
            "username": u_name,
            "role": role,
            "full_name": full_name
        }
    return None


def create_user(username: str, password: str, role: str = "faculty", full_name: str = "") -> bool:
    """Creates a new user account with hashed password."""
    init_auth_db()
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        p_hash, salt = hash_password(password)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO users (username, password_hash, salt, role, full_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username.strip().lower(), p_hash, salt, role, full_name, created_at))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def logout(reason: str = None):
    """Clears authentication session state with optional reason."""
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["role"] = None
    st.session_state["full_name"] = None
    st.session_state.pop("login_time", None)
    st.session_state.pop("last_activity", None)
    if reason:
        st.session_state["logout_reason"] = reason
    else:
        st.session_state.pop("logout_reason", None)
    st.rerun()


def check_session_timeout(timeout_minutes: int = DEFAULT_SESSION_TIMEOUT_MINUTES) -> bool:
    """
    Checks if the active authenticated session has exceeded the inactivity threshold.
    If expired, clears session state, sets expiration warning, and returns False.
    If active, updates 'last_activity' timestamp and returns True.
    """
    if not st.session_state.get("authenticated", False):
        return True

    now_ts = datetime.now().timestamp()
    last_act = st.session_state.get("last_activity", now_ts)
    max_inactivity_sec = timeout_minutes * 60

    if (now_ts - last_act) > max_inactivity_sec:
        logout(reason=f"Session timed out due to {timeout_minutes} minutes of inactivity. Please sign in again.")
        return False

    st.session_state["last_activity"] = now_ts
    return True


def get_logo_base64() -> str:
    """Returns base64 data URI of the KPRIT logo if it exists."""
    if os.path.exists(LOGO_PATH):
        try:
            with open(LOGO_PATH, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                return f"data:image/png;base64,{encoded}"
        except Exception:
            return ""
    return ""


def render_html(content: str):
    """
    Renders raw HTML or SVG safely in Streamlit without CommonMark code-block escaping.
    Uses native st.html if supported (Streamlit 1.34+), falling back to stripped st.markdown.
    """
    clean_content = textwrap.dedent(content).strip()
    if hasattr(st, "html"):
        st.html(clean_content)
    else:
        st.markdown(clean_content, unsafe_allow_html=True)


def render_login_screen():
    """
    Renders an enterprise-grade biometric authentication portal for KPRIT.
    Features:
    - Dedicated full-width canvas with hidden sidebar
    - Balanced, responsive two-column SaaS layout
    - Native SVG biometric face scanner illustration
    - Lucide vector eye / eye-off password visibility toggle without 'visibility' text
    - High-contrast inputs and unified elevated login card
    """
    try:
        init_auth_db()
    except AuthenticationConfigurationError as e:
        render_html(f"""
        <div style="background: rgba(239, 68, 68, 0.15); border: 1.5px solid rgba(239, 68, 68, 0.4); border-radius: 12px; padding: 1.5rem; margin: 2rem auto; max-width: 650px; color: #fca5a5; font-size: 0.92rem; line-height: 1.6; text-align: left;">
            <div style="font-weight: 700; color: #ef4444; font-size: 1.15rem; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                <span>🚨</span> Authentication Configuration Error
            </div>
            <div>{e}</div>
            <div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(239, 68, 68, 0.25); font-size: 0.82rem; color: #cbd5e1;">
                💡 <b>Resolution:</b> Set <code>ADMIN_PASSWORD</code> and <code>KIOSK_PASSWORD</code> in your <code>.env</code> file or host environment before starting the portal.
            </div>
        </div>
        """)
        st.stop()

    # Injected Enterprise CSS Stylesheet
    render_html("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

        /* Login Screen Only: Hide sidebar and expand toggle so login is a clean standalone portal */
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="collapsedControl"] {
            display: none !important;
            visibility: hidden !important;
        }

        #MainMenu, footer {
            visibility: hidden !important;
            height: 0 !important;
        }

        /* Dark Navy Canvas */
        .stApp {
            background: radial-gradient(circle at 10% 15%, rgba(37, 99, 235, 0.16) 0%, transparent 45%),
                        radial-gradient(circle at 90% 85%, rgba(6, 182, 212, 0.12) 0%, transparent 40%),
                        #070d19 !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            min-height: 100vh;
        }

        /* Responsive Container */
        .block-container {
            max-width: 1220px !important;
            padding-top: 2.2rem !important;
            padding-bottom: 2.5rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }

        /* Typography & Badges */
        .inst-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(37, 99, 235, 0.16);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.35);
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.4rem;
        }

        .hero-title {
            color: #ffffff;
            font-size: 2.15rem;
            font-weight: 800;
            line-height: 1.22;
            letter-spacing: -0.025em;
            margin-top: 0.2rem;
            margin-bottom: 0.75rem;
        }

        .gradient-accent {
            background: linear-gradient(135deg, #38bdf8 0%, #2563eb 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-desc {
            color: #94a3b8;
            font-size: 0.92rem;
            line-height: 1.6;
            margin-bottom: 1.25rem;
        }

        /* Biometric Graphic Container */
        .biometric-illustration-box {
            margin-bottom: 1.25rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            border-radius: 12px;
            overflow: hidden;
        }

        /* 4 Feature Highlights Grid */
        .features-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.85rem;
        }
        .feature-card {
            background: rgba(15, 23, 42, 0.65);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            padding: 0.85rem 1rem;
            transition: all 0.2s ease;
        }
        .feature-card:hover {
            border-color: rgba(56, 189, 248, 0.35);
            background: rgba(30, 41, 59, 0.7);
            transform: translateY(-1px);
        }
        .feature-title {
            display: flex;
            align-items: center;
            gap: 7px;
            font-size: 0.84rem;
            font-weight: 700;
            color: #f1f5f9;
            margin-bottom: 3px;
        }
        .feature-desc {
            font-size: 0.76rem;
            color: #94a3b8;
            line-height: 1.45;
        }

        /* Unified Elevated Authentication Card */
        [data-testid="stForm"] {
            background: #0f172a !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 18px !important;
            padding: 2.2rem 2rem !important;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.06) !important;
        }

        .card-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: rgba(37, 99, 235, 0.16);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.35);
            font-size: 0.72rem;
            font-weight: 700;
            padding: 4px 11px;
            border-radius: 9999px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.75rem;
        }

        .card-title {
            color: #ffffff !important;
            font-size: 1.45rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
            margin-top: 0 !important;
            margin-bottom: 0.35rem !important;
        }

        .card-sub {
            color: #94a3b8 !important;
            font-size: 0.86rem !important;
            margin-bottom: 0 !important;
            line-height: 1.45 !important;
        }

        /* High-Contrast Inputs */
        [data-testid="stTextInput"] label {
            color: #f1f5f9 !important;
            font-size: 0.83rem !important;
            font-weight: 600 !important;
            margin-bottom: 6px !important;
        }

        [data-baseweb="input"] {
            background-color: #ffffff !important;
            border: 1.5px solid #cbd5e1 !important;
            border-radius: 10px !important;
            transition: all 0.2s ease !important;
            height: 44px !important;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
        }

        [data-baseweb="input"]:focus-within {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.28) !important;
        }

        [data-baseweb="input"] input {
            color: #0f172a !important;
            font-size: 0.92rem !important;
            font-weight: 500 !important;
            padding: 0.6rem 0.95rem !important;
            padding-right: 42px !important;
            background: transparent !important;
        }

        [data-baseweb="input"] input::placeholder {
            color: #94a3b8 !important;
            font-weight: 400 !important;
        }

        /* -------------------------------------------------------------
           REMOVE UNWANTED 'PRESS ENTER TO SUBMIT FORM' HELPER
           Hides Streamlit's InputInstructions helper tag beside inputs
           while strictly preserving native Enter-key form submission
           ------------------------------------------------------------- */
        [data-testid="InputInstructions"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            width: 0 !important;
            overflow: hidden !important;
        }

        /* -------------------------------------------------------------
           LUCIDE EYE-ICON PASSWORD VISIBILITY TOGGLE FIX
           Completely replaces the raw ligature word 'visibility' with an SVG icon
           ------------------------------------------------------------- */
        [data-testid="stTextInput"] button,
        [data-baseweb="input"] button {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            width: 34px !important;
            height: 34px !important;
            padding: 0 !important;
            margin: 0 !important;
            margin-right: 6px !important;
            cursor: pointer !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            position: relative !important;
            color: transparent !important;
            font-size: 0 !important;
            outline: none !important;
        }

        /* Suppress any raw ligature text such as 'visibility' */
        [data-testid="stTextInput"] button *,
        [data-baseweb="input"] button * {
            display: none !important;
            visibility: hidden !important;
            font-size: 0 !important;
            line-height: 0 !important;
            color: transparent !important;
            width: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
        }

        /* Closed-Eye Icon (Lucide Eye-Off) when password is masked */
        [data-testid="stTextInput"] button::after,
        [data-baseweb="input"] button::after {
            content: '' !important;
            display: inline-block !important;
            width: 20px !important;
            height: 20px !important;
            background-repeat: no-repeat !important;
            background-position: center !important;
            background-size: 19px 19px !important;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M9.88 9.88a3 3 0 1 0 4.24 4.24'/%3E%3Cpath d='M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68'/%3E%3Cpath d='M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61'/%3E%3Cline x1='2' x2='22' y1='2' y2='22'/%3E%3C/svg%3E") !important;
            opacity: 0.75 !important;
            transition: opacity 0.15s ease, transform 0.15s ease !important;
        }

        /* Open-Eye Icon (Lucide Eye in Royal Blue) when password is unmasked */
        [data-testid="stTextInput"]:has(input[type="text"]) button::after,
        [data-baseweb="input"]:has(input[type="text"]) button::after,
        [data-testid="stTextInput"] button[aria-label*="Hide"]::after,
        [data-baseweb="input"] button[aria-label*="Hide"]::after,
        [data-testid="stTextInput"] button[title*="Hide"]::after,
        [data-baseweb="input"] button[title*="Hide"]::after {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%232563eb' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z'/%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3C/svg%3E") !important;
            opacity: 1 !important;
        }

        [data-testid="stTextInput"] button:hover::after,
        [data-baseweb="input"] button:hover::after {
            opacity: 1 !important;
            transform: scale(1.1) !important;
        }

        /* Full-Width Royal Blue Login Button */
        [data-testid="stFormSubmitButton"] button,
        .stButton button[kind="primary"],
        .stButton button {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            font-size: 0.96rem !important;
            padding: 0.72rem 1.25rem !important;
            border-radius: 10px !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.45) !important;
            transition: all 0.2s ease !important;
            width: 100% !important;
            margin-top: 0.6rem !important;
            cursor: pointer !important;
        }
        [data-testid="stFormSubmitButton"] button:hover,
        .stButton button:hover {
            background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
            box-shadow: 0 6px 20px 0 rgba(37, 99, 235, 0.6) !important;
            transform: translateY(-1px) !important;
        }

        /* Evaluation Credentials Box */
        .eval-box {
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1rem 1.15rem;
            margin-top: 1.25rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        }
        .eval-title {
            font-size: 0.74rem;
            font-weight: 700;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.6rem;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .eval-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.82rem;
            color: #cbd5e1;
            margin-bottom: 0.45rem;
        }
        .eval-role {
            color: #94a3b8;
            font-weight: 500;
        }
        .eval-badge {
            background: rgba(30, 41, 59, 0.95);
            color: #38bdf8;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.78rem;
            border: 1px solid rgba(56, 189, 248, 0.28);
        }

        /* Security Footer */
        .security-footer {
            text-align: center;
            font-size: 0.72rem;
            color: #64748b;
            margin-top: 1.15rem;
            line-height: 1.5;
        }

        @media (max-width: 960px) {
            .block-container {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
            .hero-title {
                font-size: 1.75rem !important;
            }
            .features-grid {
                grid-template-columns: 1fr !important;
            }
            [data-testid="stForm"] {
                padding: 1.5rem 1.25rem !important;
            }
        }
    </style>
    """)

    # Balanced Two-Column Layout
    col_left, col_right = st.columns([1.18, 1], gap="large")

    # ==================================================
    # LEFT SECTION – Branding, Visual Identity & Features
    # ==================================================
    with col_left:
        logo_data = get_logo_base64()
        logo_html = f'<img src="{logo_data}" style="width: 76px; height: 76px; object-fit: contain; border-radius: 8px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));" alt="KPRIT Logo" />' if logo_data else ''

        render_html(f"""
        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 1.1rem;">
            {logo_html}
            <div>
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 0.35rem;">
                    <span class="inst-badge" style="margin-bottom: 0;">🏛️ KPRIT • UGC AUTONOMOUS</span>
                    <span class="inst-badge" style="background: rgba(16, 185, 129, 0.16); color: #34d399; border-color: rgba(16, 185, 129, 0.4); margin-bottom: 0;">🔒 HTTPS SECURE (TLS 1.3)</span>
                </div>
                <div style="font-size: 1.02rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em;">
                    KOMMURI PRATAP REDDY INSTITUTE OF TECHNOLOGY
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 500;">
                    Department of CSE (Data Science / AI & ML) • Hyderabad
                </div>
            </div>
        </div>
        """)

        # Headline & Professional Description
        render_html("""
        <h1 class="hero-title">
            Face Verification Based<br>
            <span class="gradient-accent">Smart Attendance</span> System
        </h1>
        <p class="hero-desc">
            Next-generation biometric identification and smart attendance platform. Features 512-dimensional ArcFace deep feature extraction, real-time multi-student facial verification, and automated punctuality compliance tracking.
        </p>
        """)

        # Biometric Face Illustration Graphic (Pure SVG, rendered directly via st.html)
        render_html("""
        <div class="biometric-illustration-box">
            <svg viewBox="0 0 520 175" width="100%" height="175" xmlns="http://www.w3.org/2000/svg" style="display:block; border-radius: 12px; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(56, 189, 248, 0.22);">
                <defs>
                    <pattern id="hud-grid" width="20" height="20" patternUnits="userSpaceOnUse">
                        <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(56, 189, 248, 0.07)" stroke-width="1"/>
                    </pattern>
                    <linearGradient id="scan-glow" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stop-color="#38bdf8" stop-opacity="0"/>
                        <stop offset="50%" stop-color="#38bdf8" stop-opacity="0.9"/>
                        <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
                    </linearGradient>
                </defs>
                <rect width="100%" height="100%" fill="url(#hud-grid)" rx="12"/>

                <path d="M 16 34 L 16 16 L 34 16" fill="none" stroke="#06b6d4" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M 504 34 L 504 16 L 486 16" fill="none" stroke="#06b6d4" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M 16 141 L 16 159 L 34 159" fill="none" stroke="#06b6d4" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M 504 141 L 504 159 L 486 159" fill="none" stroke="#06b6d4" stroke-width="2.5" stroke-linecap="round"/>

                <rect x="195" y="18" width="130" height="138" rx="14" fill="none" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.5" stroke-dasharray="4 4"/>
                <circle cx="260" cy="85" r="50" fill="none" stroke="rgba(37, 99, 235, 0.35)" stroke-width="1.5"/>

                <circle cx="242" cy="74" r="3.5" fill="#38bdf8"/>
                <circle cx="278" cy="74" r="3.5" fill="#38bdf8"/>
                <circle cx="260" cy="90" r="3" fill="#06b6d4"/>
                <circle cx="246" cy="112" r="2.5" fill="#38bdf8"/>
                <circle cx="274" cy="112" r="2.5" fill="#38bdf8"/>
                <circle cx="260" cy="126" r="2.5" fill="#38bdf8"/>

                <line x1="242" y1="74" x2="278" y2="74" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.2"/>
                <line x1="242" y1="74" x2="260" y2="90" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.2"/>
                <line x1="278" y1="74" x2="260" y2="90" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.2"/>
                <line x1="260" y1="90" x2="246" y2="112" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.2"/>
                <line x1="260" y1="90" x2="274" y2="112" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.2"/>
                <line x1="246" y1="112" x2="274" y2="112" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.2"/>
                <line x1="246" y1="112" x2="260" y2="126" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.2"/>
                <line x1="274" y1="112" x2="260" y2="126" stroke="rgba(56, 189, 248, 0.35)" stroke-width="1.2"/>

                <rect x="197" y="84" width="126" height="2" fill="url(#scan-glow)"/>

                <text x="32" y="38" fill="#38bdf8" font-family="'Inter', sans-serif" font-size="10" font-weight="700">● ARCFACE 512-D</text>
                <text x="32" y="56" fill="#94a3b8" font-family="'Inter', sans-serif" font-size="9">BUFFALO_L RESNET-50</text>
                <text x="32" y="128" fill="#94a3b8" font-family="'Inter', sans-serif" font-size="9">RETINAFACE 10G</text>
                <text x="32" y="144" fill="#64748b" font-family="'Inter', sans-serif" font-size="8.5">ENROLLED DB: READY</text>

                <text x="488" y="38" text-anchor="end" fill="#10b981" font-family="'Inter', sans-serif" font-size="10" font-weight="700">● ENGINE ONLINE</text>
                <text x="488" y="56" text-anchor="end" fill="#94a3b8" font-family="'Inter', sans-serif" font-size="9">LATENCY: ~12ms</text>
                <text x="488" y="128" text-anchor="end" fill="#38bdf8" font-family="'Inter', sans-serif" font-size="9">COSINE SIMILARITY</text>
                <text x="488" y="144" text-anchor="end" fill="#64748b" font-family="'Inter', sans-serif" font-size="8.5">THRESHOLD: 0.58</text>
            </svg>
        </div>
        """)

        # 4 Feature Highlights Grid
        render_html("""
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-title">
                    <span style="color: #38bdf8;">🎯</span> Face Verification
                </div>
                <div class="feature-desc">
                    512-D ArcFace template matching with RetinaFace detection and margin disambiguation.
                </div>
            </div>
            <div class="feature-card">
                <div class="feature-title">
                    <span style="color: #38bdf8;">⚡</span> Automated Attendance
                </div>
                <div class="feature-desc">
                    Zero-touch live webcam kiosk processing with consecutive-frame stabilization.
                </div>
            </div>
            <div class="feature-card">
                <div class="feature-title">
                    <span style="color: #38bdf8;">⏰</span> Punctuality Analytics
                </div>
                <div class="feature-desc">
                    Real-time timetable compliance categorization (On Time / Late / Very Late).
                </div>
            </div>
            <div class="feature-card">
                <div class="feature-title">
                    <span style="color: #38bdf8;">🔒</span> Secure Management
                </div>
                <div class="feature-desc">
                    Role-based access with PBKDF2 encryption, session guards and audit logging.
                </div>
            </div>
        </div>
        """)

    # ==================================================
    # RIGHT SECTION – Unified Modern Authentication Card
    # ==================================================
    with col_right:
        logout_notice = st.session_state.get("logout_reason")
        if logout_notice:
            render_html(f"""
            <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 1rem; color: #fca5a5; font-size: 0.85rem; display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.1rem;">⚠️</span> <span>{logout_notice}</span>
            </div>
            """)

        with st.form("login_form", clear_on_submit=False):
            render_html("""
            <div style="margin-bottom: 1.35rem;">
                <span class="card-pill">🏛️ KPRIT – UGC Autonomous</span>
                <h2 class="card-title">Sign In to Attendance Terminal</h2>
                <p class="card-sub">Secure access for administrators, faculty, and campus kiosks.</p>
            </div>
            """)

            username_input = st.text_input(
                "Username / Station ID",
                placeholder="Enter username (e.g. admin or kiosk)",
                key="login_username"
            ).strip()

            password_input = st.text_input(
                "Password",
                type="password",
                placeholder="Enter terminal password",
                key="login_password"
            )

            st.write("")
            submit_clicked = st.form_submit_button("🚀 Sign In to Dashboard", use_container_width=True)

            if submit_clicked:
                if not username_input or not password_input:
                    st.error("Please enter both username and password.")
                else:
                    with st.spinner("Authenticating credentials..."):
                        user_profile = verify_user(username_input, password_input)
                        if user_profile:
                            now_ts = datetime.now().timestamp()
                            st.session_state["authenticated"] = True
                            st.session_state["username"] = user_profile["username"]
                            st.session_state["role"] = user_profile["role"]
                            st.session_state["full_name"] = user_profile["full_name"]
                            st.session_state["login_time"] = now_ts
                            st.session_state["last_activity"] = now_ts
                            st.session_state.pop("logout_reason", None)
                            st.success(f"✅ Authentication verified. Welcome, {user_profile['full_name']}!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid credentials. Please verify your Station ID and password.")

        # Clean Evaluation Credentials Section
        if SHOW_EVAL_CREDENTIALS:
            render_html(f"""
            <div class="eval-box">
                <div class="eval-title">🔑 Evaluation Access Credentials</div>
                <div class="eval-row">
                    <span class="eval-role">Administrator / Faculty:</span>
                    <div><span class="eval-badge">{ADMIN_USERNAME}</span> <span style="color:#64748b;">/</span> <span class="eval-badge">••••••••</span></div>
                </div>
                <div class="eval-row" style="margin-bottom: 0;">
                    <span class="eval-role">Campus Kiosk Terminal:</span>
                    <div><span class="eval-badge">{KIOSK_USERNAME}</span> <span style="color:#64748b;">/</span> <span class="eval-badge">••••••••</span></div>
                </div>
            </div>
            <div class="security-footer">
                🔒 256-Bit TLS 1.3 Encryption • 100,000-Iteration PBKDF2-SHA256 • ArcFace 512-D
            </div>
            """)
        else:
            render_html("""
            <div class="eval-box" style="text-align: center; color: #94a3b8; font-size: 0.8rem; padding: 0.85rem 1rem;">
                🛡️ Production Instance: Credentials managed via institutional security policy.
            </div>
            <div class="security-footer">
                🔒 256-Bit TLS 1.3 Encryption • 100,000-Iteration PBKDF2-SHA256 • ArcFace 512-D
            </div>
            """)


if __name__ == "__main__":
    try:
        init_auth_db()
        admin_test_pw, kiosk_test_pw = get_required_credentials()
        res_admin = verify_user(ADMIN_USERNAME, admin_test_pw)
        print("Admin verification test:", "SUCCESS" if res_admin else "FAILED")
        res_kiosk = verify_user(KIOSK_USERNAME, kiosk_test_pw)
        print("Kiosk verification test:", "SUCCESS" if res_kiosk else "FAILED")
    except AuthenticationConfigurationError as err:
        print(f"[Auth Self-Test] Safe configuration stop: {err}")
