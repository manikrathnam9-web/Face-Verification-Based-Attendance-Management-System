"""
Standalone Launcher for Face Verification Attendance Dashboard over HTTPS.
Ensures certificates exist, configures TLS parameters, and executes Streamlit.
"""

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

import subprocess

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
DASHBOARD_PATH = os.path.join(PROJECT_ROOT, "app", "dashboard.py")
CERT_PATH = os.path.join(PROJECT_ROOT, "certs", "cert.pem")
KEY_PATH = os.path.join(PROJECT_ROOT, "certs", "key.pem")


def main():
    if not os.path.exists(CERT_PATH) or not os.path.exists(KEY_PATH):
        print("[HTTPS Launcher] Generating SSL/TLS certificates...")
        from scripts.generate_ssl_certs import generate_certificates
        generate_certificates()

    port = os.getenv("STREAMLIT_SERVER_PORT", "8501")
    address = os.getenv("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")

    print("\n" + "=" * 70)
    print("  🔒 KPRIT SMART ATTENDANCE - SECURE HTTPS SERVER")
    print("=" * 70)
    print(f"  • Local HTTPS URL:   https://localhost:{port}")
    print(f"  • Network Binding:   https://{address}:{port}")
    print(f"  • Certificate:       {CERT_PATH}")
    print(f"  • Private Key:       {KEY_PATH}")
    print("  • TLS Protocol:      TLS 1.2 / TLS 1.3")
    print("  • CSRF Protection:   Active (server.enableXsrfProtection=true)")
    print("  • Session Guard:     Inactivity Timeout Enforced")
    print("-" * 70)
    print("  ℹ️  Browser Certificate Notice:")
    print("     Because this certificate is self-signed for localhost development,")
    print("     your browser will display an initial security warning.")
    print("     Click 'Advanced' -> 'Proceed to localhost (unsafe)' to open.")
    print("=" * 70 + "\n")

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        DASHBOARD_PATH,
        "--server.port", port,
        "--server.address", address,
        "--server.sslCertFile", CERT_PATH,
        "--server.sslKeyFile", KEY_PATH,
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[HTTPS Launcher] Dashboard server stopped.")


if __name__ == "__main__":
    main()
