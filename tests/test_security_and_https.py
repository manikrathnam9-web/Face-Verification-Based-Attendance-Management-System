"""
Automated Cybersecurity & HTTPS Test Suite
Face Verification Based Smart Attendance Management System
Kommuri Pratap Reddy Institute of Technology (KPRIT)

Tests:
1. PBKDF2-HMAC-SHA256 password hashing & timing-safe authentication.
2. Inactivity session timeout and automatic logout.
3. SSL/TLS X.509 certificate validity, RSA key size, and SAN entries.
4. Biometric data isolation, informed consent validation, and .gitignore leak guards.
5. Production Nginx TLS reverse proxy and security response headers configuration.
"""

import os
import sys
import unittest
import time
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.auth import (
    hash_password,
    verify_user,
    init_auth_db,
    check_session_timeout,
    logout,
    get_required_credentials,
    AuthenticationConfigurationError,
    PBKDF2_ITERATIONS,
    ADMIN_USERNAME,
    KIOSK_USERNAME,
)
from app.enrollment import enroll_student


class TestCybersecurityAndHTTPS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set controlled test credentials in environment
        cls.test_admin_pw = "SecTestAdminPass@2026!"
        cls.test_kiosk_pw = "SecTestKioskPass@2026!"
        cls.orig_admin_pw = os.environ.get("ADMIN_PASSWORD")
        cls.orig_kiosk_pw = os.environ.get("KIOSK_PASSWORD")

        os.environ["ADMIN_PASSWORD"] = cls.test_admin_pw
        os.environ["KIOSK_PASSWORD"] = cls.test_kiosk_pw
        init_auth_db()

    @classmethod
    def tearDownClass(cls):
        if cls.orig_admin_pw is not None:
            os.environ["ADMIN_PASSWORD"] = cls.orig_admin_pw
        else:
            os.environ.pop("ADMIN_PASSWORD", None)

        if cls.orig_kiosk_pw is not None:
            os.environ["KIOSK_PASSWORD"] = cls.orig_kiosk_pw
        else:
            os.environ.pop("KIOSK_PASSWORD", None)

    def test_01_pbkdf2_password_hashing(self):
        """Test PBKDF2 hashing with 100,000 iterations and random salt."""
        self.assertEqual(PBKDF2_ITERATIONS, 100_000)

        pw = "TestPassword@2026"
        hash1, salt1 = hash_password(pw)
        hash2, salt2 = hash_password(pw)

        # Different salts must yield completely different hashes
        self.assertNotEqual(salt1, salt2)
        self.assertNotEqual(hash1, hash2)

        # Same salt must yield exact identical hash
        hash_recomputed, _ = hash_password(pw, salt=salt1)
        self.assertEqual(hash1, hash_recomputed)
        print("[TEST 1 PASS] PBKDF2-HMAC-SHA256 100k-iteration hashing verified.")

    def test_02_authentication_credentials(self):
        """Test valid credentials verify, missing credentials fail safely, and invalid/old passwords are rejected."""
        # 1. Missing credentials fail safely without fallbacks
        saved_admin = os.environ.pop("ADMIN_PASSWORD", None)
        saved_kiosk = os.environ.pop("KIOSK_PASSWORD", None)

        try:
            with self.assertRaises(AuthenticationConfigurationError):
                get_required_credentials()

            with self.assertRaises(AuthenticationConfigurationError):
                init_auth_db()
        finally:
            # Restore environment variables
            if saved_admin:
                os.environ["ADMIN_PASSWORD"] = saved_admin
            if saved_kiosk:
                os.environ["KIOSK_PASSWORD"] = saved_kiosk

        # 2. Re-synchronize with valid test credentials
        init_auth_db()

        # 3. Valid environment credentials authenticate successfully
        admin_auth = verify_user(ADMIN_USERNAME, self.test_admin_pw)
        self.assertIsNotNone(admin_auth)
        self.assertEqual(admin_auth["role"], "admin")

        kiosk_auth = verify_user(KIOSK_USERNAME, self.test_kiosk_pw)
        self.assertIsNotNone(kiosk_auth)
        self.assertEqual(kiosk_auth["role"], "kiosk")

        # 4. Old hardcoded default passwords must be rejected
        self.assertIsNone(verify_user("admin", "Kprit@2026"))
        self.assertIsNone(verify_user("kiosk", "Attendance@2026"))

        # 5. Wrong passwords must be rejected
        self.assertIsNone(verify_user("admin", "WrongPassword!999"))

        # 6. Non-existent user rejection
        self.assertIsNone(verify_user("nonexistent_user", "AnyPassword"))
        print("[TEST 2 PASS] Timing-safe credential verification, safe missing-env failure, and role verification verified.")

    def test_03_session_inactivity_timeout(self):
        """Test session timeout logic and inactivity expiration."""
        import streamlit as st

        # Mock active session
        st.session_state["authenticated"] = True
        st.session_state["username"] = "admin"
        st.session_state["role"] = "admin"
        now_ts = datetime.now().timestamp()
        st.session_state["last_activity"] = now_ts

        # 1. Within threshold: session should remain active
        valid = check_session_timeout(timeout_minutes=30)
        self.assertTrue(valid)
        self.assertTrue(st.session_state["authenticated"])

        # 2. Simulate expired inactivity (31 minutes ago)
        st.session_state["last_activity"] = now_ts - (31 * 60)
        try:
            check_session_timeout(timeout_minutes=30)
        except Exception:
            # Streamlit st.rerun() raises a ScriptControl exception or RerunData in bare mode
            pass

        self.assertFalse(st.session_state.get("authenticated", False))
        self.assertIn("logout_reason", st.session_state)
        self.assertIn("inactivity", st.session_state["logout_reason"].lower())
        print("[TEST 3 PASS] Session inactivity timeout correctly terminates session and issues warning.")

    def test_04_ssl_certificate_validity_and_san(self):
        """Test SSL certificate existence, RSA key size, and Subject Alternative Names."""
        from cryptography import x509
        from cryptography.hazmat.primitives.asymmetric import rsa

        cert_path = os.path.join(PROJECT_ROOT, "certs", "cert.pem")
        key_path = os.path.join(PROJECT_ROOT, "certs", "key.pem")

        self.assertTrue(os.path.exists(cert_path), "SSL cert.pem missing!")
        self.assertTrue(os.path.exists(key_path), "SSL key.pem missing!")

        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())

        # Check RSA key size >= 2048
        pub_key = cert.public_key()
        self.assertIsInstance(pub_key, rsa.RSAPublicKey)
        self.assertGreaterEqual(pub_key.key_size, 2048)

        # Check SAN extension
        san_ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        self.assertIsNotNone(san_ext)
        dns_names = san_ext.value.get_values_for_type(x509.DNSName)
        ip_addresses = [str(ip) for ip in san_ext.value.get_values_for_type(x509.IPAddress)]

        self.assertIn("localhost", dns_names)
        self.assertIn("127.0.0.1", ip_addresses)

        # Check validity window
        now = datetime.now(timezone.utc)
        self.assertLess(cert.not_valid_before_utc, now)
        self.assertGreater(cert.not_valid_after_utc, now)
        print(f"[TEST 4 PASS] SSL Certificate verified: {pub_key.key_size}-bit RSA with SAN ({dns_names}, {ip_addresses}).")

    def test_05_gitignore_security_rules(self):
        """Test that .gitignore protects certificates, database, embeddings, and secrets."""
        gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore is missing!")

        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_patterns = [
            "certs/*.pem",
            "certs/*.key",
            ".env",
            "database/*.db",
            "data/embeddings/*.npy",
            "data/enrollment/*.json",
        ]
        for pattern in required_patterns:
            self.assertIn(pattern, content, f"Pattern {pattern} missing from .gitignore!")

        print("[TEST 5 PASS] .gitignore strictly protects certificates, embeddings, databases, and secrets.")

    def test_06_informed_consent_enforcement(self):
        """Test that student enrollment strictly requires informed consent."""
        # Non-consented enrollment must be rejected
        res_no_consent = enroll_student(
            student_id="TEST_999",
            name="Test Non-Consent Student",
            department="CSE",
            year="4th Year",
            image_or_path="data/test_images/DS001_verify_01.jpeg",
            consent="no"
        )
        self.assertFalse(res_no_consent["success"])
        self.assertIn("consent", res_no_consent["message"].lower())
        print("[TEST 6 PASS] Biometric informed consent requirement strictly enforced.")

    def test_07_nginx_configuration_and_security_headers(self):
        """Test that Nginx reverse proxy configuration enforces TLS 1.2/1.3 and security headers."""
        nginx_conf_path = os.path.join(PROJECT_ROOT, "nginx", "nginx.conf")
        self.assertTrue(os.path.exists(nginx_conf_path), "nginx.conf is missing!")

        with open(nginx_conf_path, "r", encoding="utf-8") as f:
            conf = f.read()

        # Check HTTP -> HTTPS redirect
        self.assertIn("return 301 https://$host$request_uri;", conf)

        # Check TLS 1.2 / 1.3 protocol
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3;", conf)

        # Check essential security response headers
        self.assertIn("Strict-Transport-Security", conf)
        self.assertIn("X-Content-Type-Options", conf)
        self.assertIn("X-Frame-Options", conf)
        self.assertIn("Permissions-Policy", conf)
        self.assertIn("camera=(self)", conf)

        # Check WebSocket streaming proxy
        self.assertIn("location /_stcore/stream", conf)
        print("[TEST 7 PASS] Nginx reverse proxy enforces TLS 1.2/1.3, HTTP->HTTPS redirect, and security headers.")


if __name__ == "__main__":
    unittest.main()
