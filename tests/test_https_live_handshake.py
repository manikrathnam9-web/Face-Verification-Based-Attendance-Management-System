"""
Live HTTPS TLS Handshake Test
Spawns Streamlit with --server.sslCertFile and --server.sslKeyFile,
performs an actual TLS handshake verifying the self-signed certificate,
and checks the encrypted /_stcore/health response.
"""

import os
import sys
import time
import subprocess
import ssl
import urllib.request

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CERT_PATH = os.path.join(PROJECT_ROOT, "certs", "cert.pem")
KEY_PATH = os.path.join(PROJECT_ROOT, "certs", "key.pem")
DASHBOARD_PATH = os.path.join(PROJECT_ROOT, "app", "dashboard.py")
TEST_PORT = 8503


def test_https_server():
    print(f"[HTTPS Live Test] Starting Streamlit over HTTPS on port {TEST_PORT}...")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        DASHBOARD_PATH,
        "--server.port", str(TEST_PORT),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--server.sslCertFile", CERT_PATH,
        "--server.sslKeyFile", KEY_PATH,
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        # Give Streamlit up to 10 seconds to initialize Tornado with TLS
        url = f"https://localhost:{TEST_PORT}/_stcore/health"
        ssl_ctx = ssl.create_default_context(cafile=CERT_PATH)

        success = False
        start_time = time.time()
        while time.time() - start_time < 12:
            time.sleep(1.0)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SecurityAuditClient/1.0"})
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=3) as resp:
                    if resp.status == 200:
                        content = resp.read().decode("utf-8")
                        print(f"[HTTPS Live Test] SUCCESS! Verified TLS Handshake with cert.pem.")
                        print(f"  • TLS Version: {resp.version}")
                        print(f"  • Endpoint:    {url}")
                        print(f"  • Response:    {content.strip()}")
                        success = True
                        break
            except Exception as e:
                pass

        if not success:
            raise RuntimeError("HTTPS handshake timed out or failed to connect.")

    finally:
        print("[HTTPS Live Test] Terminating test server process...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[HTTPS Live Test] Test server terminated cleanly.")


if __name__ == "__main__":
    test_https_server()
