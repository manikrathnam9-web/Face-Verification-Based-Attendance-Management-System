import unittest
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from streamlit.testing.v1 import AppTest

DASHBOARD_FILE = os.path.join(PROJECT_ROOT, "app", "dashboard.py")


class TestSidebarAndNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("ADMIN_PASSWORD", "TestEnvAdminSecurePassword2026!")
        os.environ.setdefault("KIOSK_PASSWORD", "TestEnvKioskSecurePassword2026!")

    def test_unauthenticated_login_screen(self):
        """Verify unauthenticated user gets login screen without exceptions."""
        at = AppTest.from_file(DASHBOARD_FILE, default_timeout=45)
        at.run()
        self.assertFalse(at.exception, f"App threw exception: {at.exception}")
        self.assertTrue(len(at.sidebar) == 0 or len(at.sidebar.radio) == 0, "Sidebar navigation should not be visible when unauthenticated")

    def test_authenticated_dashboard_and_sidebar_navigation(self):
        """Verify authenticated admin sees dashboard, sidebar, and can switch between all 6 pages."""
        at = AppTest.from_file(DASHBOARD_FILE, default_timeout=45)
        at.session_state["authenticated"] = True
        at.session_state["role"] = "admin"
        at.session_state["full_name"] = "KPRIT Administrator"
        at.session_state["username"] = "admin"
        at.run()

        self.assertFalse(at.exception, f"App threw exception on initial load: {at.exception}")

        # Check sidebar radio options
        self.assertTrue(len(at.sidebar.radio) > 0, "Sidebar must have navigation radio")
        nav_radio = at.sidebar.radio[0]
        options = nav_radio.options
        expected_options = [
            "📊 Dashboard",
            "📸 Live Attendance & Verification",
            "👥 Student Management",
            "📋 Attendance History",
            "⏰ Punctuality Analytics",
            "ℹ️ System Information"
        ]
        self.assertEqual(options, expected_options)

        # Test navigating into every single section
        for option in expected_options:
            nav_radio.set_value(option)
            at.run()
            self.assertFalse(at.exception, f"Exception occurred while navigating to {option}: {at.exception}")

    def test_administrator_role_badge_rendering(self):
        """Verify administrator badge renders with class 'admin-role-badge' and correct text."""
        at = AppTest.from_file(DASHBOARD_FILE, default_timeout=45)
        at.session_state["authenticated"] = True
        at.session_state["role"] = "admin"
        at.session_state["full_name"] = "KPRIT Administrator"
        at.session_state["username"] = "admin"
        at.run()

        self.assertFalse(at.exception, f"Admin session threw exception: {at.exception}")
        # Check that sidebar markdown contains the admin-role-badge class
        sidebar_markdowns = [m.value for m in at.sidebar.markdown]
        badge_found = any("admin-role-badge" in m and "ADMINISTRATOR (admin)" in m for m in sidebar_markdowns)
        self.assertTrue(badge_found, "Administrator badge with class 'admin-role-badge' and text 'ADMINISTRATOR (admin)' must be present in sidebar")

    def test_kiosk_role_sidebar(self):
        """Verify campus kiosk terminal gets restricted sidebar with live attendance."""
        at = AppTest.from_file(DASHBOARD_FILE, default_timeout=45)
        at.session_state["authenticated"] = True
        at.session_state["role"] = "kiosk"
        at.session_state["full_name"] = "Campus Attendance Kiosk"
        at.session_state["username"] = "kiosk"
        at.run()

        self.assertFalse(at.exception, f"Kiosk view threw exception: {at.exception}")
        nav_radio = at.sidebar.radio[0]
        self.assertEqual(nav_radio.options, ["📸 Live Attendance & Verification"])

    def test_css_sidebar_collapse_and_expand_rules(self):
        """Verify the CSS in dashboard.py contains the essential sidebar toggle, expand rules, and admin badge styles."""
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
            code = f.read()

        # Check that header visibility is NOT hidden
        self.assertNotIn("header {visibility: hidden;}", code, "header {visibility: hidden;} must not be present!")
        self.assertNotIn("header { visibility: hidden", code, "header must not be hidden!")

        # Check for stExpandSidebarButton and stSidebarCollapseButton styling
        self.assertIn("stExpandSidebarButton", code, "stExpandSidebarButton must be styled in CSS")
        self.assertIn("stSidebarCollapseButton", code, "stSidebarCollapseButton must be styled in CSS")
        self.assertIn("collapsedControl", code, "collapsedControl must be styled for backwards compatibility")
        self.assertIn("max-width: 100% !important", code, "block-container must have fluid width")

        # Check Administrator Badge CSS requirements
        self.assertIn(".admin-role-badge", code, ".admin-role-badge class must be defined in CSS")
        self.assertIn("#1D4ED8", code, "Badge background must be #1D4ED8")
        self.assertIn("#3B82F6", code, "Badge border must be #3B82F6")
        self.assertIn("#FFFFFF", code, "Badge text must be #FFFFFF")


if __name__ == "__main__":
    unittest.main()
