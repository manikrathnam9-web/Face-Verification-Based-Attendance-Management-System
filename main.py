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

import argparse
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.attendance import create_database
from database.attendance_queries import display_summary, export_attendance_to_csv


def banner():
    print(r"""
===================================================================
  _  ______  ____  ___ _____
 | |/ /  _ \|  _ \|_ _|_   _|
 | ' /| |_) | |_) || |  | |
 | . \|  __/|  _ < | |  | |
 |_|\_\_|   |_| \_\___| |_|

  KOMMURI PRATAP REDDY INSTITUTE OF TECHNOLOGY (KPRIT)
  Department of Computer Science & Engineering (Data Science)
  Face Verification-Based Smart Attendance System (ArcFace)
===================================================================
    """)


def launch_dashboard(use_https=False):
    """Runs streamlit web dashboard with optional SSL/TLS encryption."""
    dashboard_path = os.path.join(PROJECT_ROOT, "app", "dashboard.py")
    python_exe = sys.executable

    cmd = [python_exe, "-m", "streamlit", "run", dashboard_path]

    if use_https:
        cert_path = os.path.join(PROJECT_ROOT, "certs", "cert.pem")
        key_path = os.path.join(PROJECT_ROOT, "certs", "key.pem")

        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            print("\n[Launcher] SSL certificates not found. Auto-generating self-signed certificates...")
            from scripts.generate_ssl_certs import generate_certificates
            generate_certificates()

        cmd.extend([
            "--server.sslCertFile", cert_path,
            "--server.sslKeyFile", key_path
        ])
        print("\n" + "="*65)
        print("  🔒 SECURE HTTPS DASHBOARD LAUNCHED")
        print(f"  • Local URL:   https://localhost:8501")
        print(f"  • Cert File:   {cert_path}")
        print(f"  • Key File:    {key_path}")
        print("  • Note: For self-signed certificates in browser, click 'Advanced' -> 'Proceed to localhost'.")
        print("="*65 + "\n")
    else:
        print("\n[Launcher] Launching Streamlit Web Dashboard (HTTP on http://localhost:8501)...")

    subprocess.run(cmd)


def run_live_kiosk():
    """Starts live webcam attendance."""
    from app.attendance_runner import run_live_webcam_attendance
    run_live_webcam_attendance()


def process_image(img_path):
    """Processes 1:N attendance from image."""
    from app.attendance_runner import process_attendance_from_image
    print(f"\n[Launcher] Processing attendance for image: {img_path}")
    results = process_attendance_from_image(img_path)
    print(f"Done! {len(results)} face(s) evaluated.")


def run_verification(student_id=None, image_path=None):
    """Runs 1:1 verification."""
    from app.verification import verify_student, verify_cli
    if student_id and image_path:
        res = verify_student(student_id, image_path)
        print("\n----------------------------------------")
        print(f"Status:     {res['status']}")
        print(f"Similarity: {res['similarity_score']}")
        print(f"Threshold:  {res['threshold']}")
        print(f"Message:    {res['message']}")
        print("----------------------------------------")
    else:
        verify_cli()


def run_enrollment():
    """Runs enrollment wizard."""
    from app.enrollment import enroll_cli
    enroll_cli()


def run_evaluation():
    """Runs evaluation and generates plots."""
    from tests.generate_evaluation_report import generate_evaluation_artifacts
    generate_evaluation_artifacts()


def main():
    create_database()

    parser = argparse.ArgumentParser(description="Face Verification-Based Smart Attendance System")
    parser.add_argument("--dashboard", action="store_true", help="Launch Streamlit Web Dashboard")
    parser.add_argument("--https", action="store_true", help="Launch dashboard over encrypted HTTPS/TLS")
    parser.add_argument("--live", action="store_true", help="Launch Live Webcam Attendance Kiosk")
    parser.add_argument("--image", type=str, help="Process 1:N attendance from an image file")
    parser.add_argument("--verify", nargs=2, metavar=("STUDENT_ID", "IMAGE_PATH"), help="Run 1:1 verification")
    parser.add_argument("--enroll", action="store_true", help="Enroll a new student")
    parser.add_argument("--summary", action="store_true", help="Display attendance and punctuality summary")
    parser.add_argument("--evaluate", action="store_true", help="Run model evaluation and generate charts")
    parser.add_argument("--export", action="store_true", help="Export attendance records to CSV")
    parser.add_argument("--generate-certs", action="store_true", help="Generate self-signed SSL/TLS certificates")

    args = parser.parse_args()

    # Handle explicit command line flags
    if args.generate_certs:
        from scripts.generate_ssl_certs import generate_certificates
        generate_certificates(force=True)
        return
    elif args.dashboard:
        launch_dashboard(use_https=args.https)
        return
    elif args.live:
        run_live_kiosk()
        return
    elif args.image:
        process_image(args.image)
        return
    elif args.verify:
        run_verification(args.verify[0], args.verify[1])
        return
    elif args.enroll:
        run_enrollment()
        return
    elif args.summary:
        display_summary()
        return
    elif args.evaluate:
        run_evaluation()
        return
    elif args.export:
        export_attendance_to_csv()
        return

    # Interactive CLI Menu
    while True:
        banner()
        print("1.  🚀 Launch Streamlit Web Dashboard (HTTP - Local)")
        print("2.  🔒 Launch Streamlit Web Dashboard (HTTPS / TLS Encrypted)")
        print("3.  🎥 Start Live Webcam Attendance Kiosk (OpenCV HUD)")
        print("4.  📸 Process Attendance from Image (1:N Auto-Identification)")
        print("5.  🔍 Run 1:1 Face Verification")
        print("6.  👤 Enroll New Student")
        print("7.  📊 View Attendance & Punctuality System Summary")
        print("8.  🧪 Run Model Evaluation & Generate Charts")
        print("9.  📤 Export Attendance Records to CSV")
        print("10. 🔑 Generate / Regenerate SSL/TLS Certificates")
        print("11. 🚪 Exit")
        print("===================================================================")

        try:
            choice = input("\nEnter your choice (1-11): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            launch_dashboard(use_https=False)
            break
        elif choice == "2":
            launch_dashboard(use_https=True)
            break
        elif choice == "3":
            run_live_kiosk()
        elif choice == "4":
            default_img = "data/test_images/DS001_verify_02.jpeg"
            p = input(f"Enter image path (or press Enter for '{default_img}'): ").strip()
            if not p:
                p = default_img
            process_image(p)
        elif choice == "5":
            run_verification()
        elif choice == "6":
            run_enrollment()
        elif choice == "7":
            display_summary()
        elif choice == "8":
            run_evaluation()
        elif choice == "9":
            export_attendance_to_csv()
        elif choice == "10":
            from scripts.generate_ssl_certs import generate_certificates
            generate_certificates(force=True)
        elif choice == "11":
            print("\nThank you for using Smart Attendance. Goodbye!")
            break
        else:
            print("\nInvalid choice. Please select 1-11.")

        input("\nPress ENTER to return to menu...")


if __name__ == "__main__":
    main()
