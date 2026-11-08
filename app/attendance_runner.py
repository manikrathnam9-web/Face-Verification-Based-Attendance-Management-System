import os
import sys
from datetime import datetime
import sqlite3
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.face_engine import face_engine, DEFAULT_VERIFICATION_THRESHOLD, DEFAULT_MIN_MARGIN
from app.attendance import record_attendance, has_attended_today
from database.punctuality import classify_punctuality

DATABASE_PATH = os.path.join(PROJECT_ROOT, "database", "attendance.db")
EMBEDDINGS_DIR = os.path.join(PROJECT_ROOT, "data", "embeddings")


def load_enrolled_students() -> list:
    """
    Fetch all active students with consent='yes' and their 512-D embeddings.
    Returns list of dicts: [{'student_id', 'name', 'department', 'year', 'embedding'}]
    """
    if not os.path.exists(DATABASE_PATH):
        return []

    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT student_id, name, department, year, consent_status
        FROM students
        WHERE consent_status = 'yes'
    """)
    rows = cur.fetchall()
    conn.close()

    enrolled = []
    for row in rows:
        s_id, name, dept, year, _ = row
        emb_path = os.path.join(EMBEDDINGS_DIR, f"{s_id}.npy")
        if os.path.exists(emb_path):
            try:
                emb = np.load(emb_path)
                enrolled.append({
                    "student_id": s_id,
                    "name": name,
                    "department": dept,
                    "year": year,
                    "embedding": emb
                })
            except Exception as err:
                print(f"[Warning] Failed loading embedding for {s_id}: {err}")
        else:
            print(f"[Warning] Embedding file missing for enrolled student: {s_id}")

    return enrolled


class LiveAttendanceTracker:
    """
    Stateful real-time face tracking and automatic attendance stabilization engine.
    - Requires N consecutive frames of verified detection before recording attendance.
    - Maintains in-memory session cache to avoid redundant SQLite queries on every frame.
    - Enforces verification threshold and ambiguity margin.
    - Evaluates multiple faces in the same frame independently.
    - Generates color-coded HUD annotations on video frames.
    """

    def __init__(self, consecutive_required: int = 3):
        self.consecutive_required = consecutive_required
        self.consecutive_counts = {}  # student_id -> int consecutive count
        self.session_logged = set()   # student_ids recorded today in this session
        self.enrolled_students = []
        self.refresh_enrolled_students()

    def refresh_enrolled_students(self):
        """Reloads enrolled students and clears in-memory state."""
        self.enrolled_students = load_enrolled_students()
        return self.enrolled_students

    def reset_counts(self):
        """Resets consecutive frame counts."""
        self.consecutive_counts.clear()

    def process_frame(
        self,
        frame: np.ndarray,
        threshold: float = DEFAULT_VERIFICATION_THRESHOLD,
        min_margin: float = DEFAULT_MIN_MARGIN,
        auto_record: bool = True
    ) -> tuple:
        """
        Processes a single video frame:
        1. Detects all faces.
        2. Computes embeddings and compares against enrolled students with margin check.
        3. Stabilizes verification across consecutive frames.
        4. Auto-records attendance in SQLite on reaching stability without duplicate inserts.
        5. Draws HUD annotations on a copy of the frame.

        Returns:
            annotated_frame (np.ndarray),
            face_evaluations (list of dicts),
            newly_recorded (list of dicts)
        """
        display_frame = frame.copy()
        h, w, _ = display_frame.shape

        if not self.enrolled_students:
            self.refresh_enrolled_students()

        face_evaluations = []
        newly_recorded = []
        seen_students_this_frame = set()

        try:
            faces = face_engine.detect_faces(frame)
        except Exception as e:
            print(f"[LiveAttendanceTracker] Detection error: {e}")
            faces = []

        now_str = datetime.now().strftime("%H:%M:%S")
        punctuality_status = classify_punctuality(now_str)

        for idx, face in enumerate(faces, start=1):
            q_emb = getattr(face, "embedding", None)
            bbox = face.bbox if hasattr(face, "bbox") else np.array([0, 0, 0, 0])

            if q_emb is None:
                continue

            # Run 1:N Identification with threshold and margin checks
            match_info = face_engine.identify_1_to_n(
                query_embedding=q_emb,
                enrolled_students=self.enrolled_students,
                threshold=threshold,
                min_margin=min_margin
            )

            is_verified = match_info["verified"]
            status = match_info["status"]
            best_student = match_info["best_student"]
            best_score = match_info["best_score"]
            score_margin = match_info["score_margin"]
            is_ambiguous = match_info["is_ambiguous"]

            already_marked = False
            rec_result = None

            if is_verified and best_student:
                sid = best_student["student_id"]
                s_name = best_student["name"]
                s_dept = best_student["department"]
                seen_students_this_frame.add(sid)

                # Increment consecutive frame count
                current_count = self.consecutive_counts.get(sid, 0) + 1
                self.consecutive_counts[sid] = current_count

                # Check if already marked present today
                if sid in self.session_logged:
                    already_marked = True
                else:
                    already_marked = has_attended_today(sid)
                    if already_marked:
                        self.session_logged.add(sid)

                if already_marked:
                    tag = f"{s_name} ({sid})"
                    sub = f"ALREADY LOGGED TODAY | Score: {best_score:.2f}"
                    color = (0, 215, 255)  # Amber / Gold
                    eval_status = "ALREADY_LOGGED"
                elif current_count >= self.consecutive_required:
                    # Consecutive stability reached -> Record attendance
                    if auto_record:
                        rec_result = record_attendance(
                            student_id=sid,
                            name=s_name,
                            department=s_dept,
                            similarity_score=best_score,
                            verification_status="VERIFIED"
                        )
                        self.session_logged.add(sid)
                        if rec_result.get("success"):
                            newly_recorded.append(rec_result)

                    tag = f"{s_name} [{punctuality_status}] - VERIFIED"
                    sub = f"ATTENDANCE MARKED | Score: {best_score:.2f} (Margin: {score_margin:.2f})"
                    color = (0, 255, 0)  # Green
                    eval_status = "VERIFIED"
                else:
                    # Stabilizing across consecutive frames
                    tag = f"VERIFYING: {s_name} ({current_count}/{self.consecutive_required})"
                    sub = f"HOLD STILL... | Score: {best_score:.2f}"
                    color = (255, 200, 0)  # Cyan/Teal
                    eval_status = "STABILIZING"

                face_evaluations.append({
                    "face_index": idx,
                    "bbox": bbox,
                    "status": eval_status,
                    "verified": is_verified,
                    "student_id": sid,
                    "name": s_name,
                    "department": s_dept,
                    "score": best_score,
                    "score_margin": score_margin,
                    "is_ambiguous": is_ambiguous,
                    "already_marked": already_marked,
                    "consecutive_count": current_count,
                    "consecutive_required": self.consecutive_required,
                    "punctuality": punctuality_status,
                    "attendance_record": rec_result
                })

            elif is_ambiguous:
                # Ambiguous identity match
                tag = "UNKNOWN / UNCERTAIN"
                sub = f"AMBIGUOUS MATCH (Margin: {score_margin:.2f} < {min_margin:.2f})"
                color = (0, 140, 255)  # Orange
                eval_status = "UNCERTAIN"

                face_evaluations.append({
                    "face_index": idx,
                    "bbox": bbox,
                    "status": eval_status,
                    "verified": False,
                    "student_id": None,
                    "name": "Unknown",
                    "department": "N/A",
                    "score": best_score,
                    "score_margin": score_margin,
                    "is_ambiguous": True,
                    "already_marked": False,
                    "consecutive_count": 0,
                    "consecutive_required": self.consecutive_required,
                    "punctuality": "N/A",
                    "attendance_record": None
                })
            else:
                # Rejected / Unknown face
                tag = "UNKNOWN / REJECTED"
                sub = f"Score: {best_score:.2f} < {threshold:.2f}"
                color = (0, 0, 255)  # Red
                eval_status = "REJECTED"

                face_evaluations.append({
                    "face_index": idx,
                    "bbox": bbox,
                    "status": eval_status,
                    "verified": False,
                    "student_id": None,
                    "name": "Unknown",
                    "department": "N/A",
                    "score": best_score,
                    "score_margin": score_margin,
                    "is_ambiguous": False,
                    "already_marked": False,
                    "consecutive_count": 0,
                    "consecutive_required": self.consecutive_required,
                    "punctuality": "N/A",
                    "attendance_record": None
                })

            # Draw HUD overlay
            face_engine.draw_hud(display_frame, bbox, tag, color=color, subtitle=sub)

        # Reset consecutive counts for students not seen in this frame
        for sid in list(self.consecutive_counts.keys()):
            if sid not in seen_students_this_frame:
                self.consecutive_counts[sid] = 0

        # Draw top info banner
        curr_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.rectangle(display_frame, (0, 0), (w, 36), (25, 25, 25), -1)
        banner_text = f"KPRIT SMART ATTENDANCE | Faces Detected: {len(faces)} | {curr_time_str}"
        cv2.putText(
            display_frame,
            banner_text,
            (12, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )

        return display_frame, face_evaluations, newly_recorded


def process_attendance_from_image(
    image_or_path,
    record: bool = True,
    threshold: float = DEFAULT_VERIFICATION_THRESHOLD,
    min_margin: float = DEFAULT_MIN_MARGIN
) -> list:
    """
    Processes all faces detected in an image for 1:N identification and attendance.
    Includes verification threshold and ambiguity margin checks.
    Returns list of results per detected face.
    """
    enrolled_students = load_enrolled_students()
    if not enrolled_students:
        print("[AttendanceRunner] No enrolled students available in database.")
        return []

    if isinstance(image_or_path, str):
        if not os.path.isabs(image_or_path):
            image_or_path = os.path.join(PROJECT_ROOT, image_or_path)
        if not os.path.exists(image_or_path):
            print(f"[AttendanceRunner] Image file not found: {image_or_path}")
            return []
        image = cv2.imread(image_or_path)
    elif isinstance(image_or_path, np.ndarray):
        image = image_or_path
    else:
        print("[AttendanceRunner] Invalid image format.")
        return []

    faces = face_engine.detect_faces(image)
    if len(faces) == 0:
        print("[AttendanceRunner] No faces detected in image.")
        return []

    results = []
    print(f"\n[AttendanceRunner] Detected {len(faces)} face(s). Processing identification...")

    for idx, face in enumerate(faces, start=1):
        query_embedding = getattr(face, "embedding", None)
        if query_embedding is None:
            continue

        match_info = face_engine.identify_1_to_n(
            query_embedding=query_embedding,
            enrolled_students=enrolled_students,
            threshold=threshold,
            min_margin=min_margin
        )

        is_verified = match_info["verified"]
        status_str = match_info["status"]
        best_student = match_info["best_student"]
        best_score = match_info["best_score"]
        score_margin = match_info["score_margin"]
        is_ambiguous = match_info["is_ambiguous"]

        now_time = datetime.now().strftime("%H:%M:%S")
        punctuality_status = classify_punctuality(now_time)

        face_result = {
            "face_index": idx,
            "bbox": face.bbox.tolist() if hasattr(face, "bbox") else [],
            "verified": is_verified,
            "status": status_str,
            "best_score": best_score,
            "score_margin": score_margin,
            "is_ambiguous": is_ambiguous,
            "threshold": threshold,
            "min_margin": min_margin,
            "punctuality": punctuality_status if is_verified else "N/A",
            "student": best_student,
            "attendance_record": None
        }

        if is_verified and best_student:
            s_id = best_student["student_id"]
            s_name = best_student["name"]
            s_dept = best_student["department"]

            print(f"Face {idx}: MATCH -> {s_id} ({s_name}) | Score: {best_score:.4f} (Margin: {score_margin:.4f}) | Punctuality: {punctuality_status}")
            if record:
                rec = record_attendance(
                    student_id=s_id,
                    name=s_name,
                    department=s_dept,
                    similarity_score=best_score,
                    verification_status="VERIFIED"
                )
                face_result["attendance_record"] = rec
        elif is_ambiguous:
            print(f"Face {idx}: UNCERTAIN -> Ambiguous match between top candidates (Margin: {score_margin:.4f} < {min_margin})")
        else:
            print(f"Face {idx}: REJECTED -> Highest score: {best_score:.4f} < {threshold}")

        results.append(face_result)

    return results


def run_live_webcam_attendance(
    camera_index: int = 0,
    threshold: float = DEFAULT_VERIFICATION_THRESHOLD,
    min_margin: float = DEFAULT_MIN_MARGIN,
    consecutive_frames: int = 3
):
    """
    Runs a real-time smart attendance kiosk using OpenCV and standard webcam.
    Displays live bounding boxes, student information, similarity scores,
    and automatic attendance logging with visual feedback.
    Press 'q' or 'ESC' to exit.
    """
    print("\n========================================")
    print("STARTING REAL-TIME SMART ATTENDANCE KIOSK")
    print("========================================")
    print(f"Initializing camera at index {camera_index}... (Press 'q' or 'ESC' to exit)")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[ERROR] Could not open webcam at index {camera_index}.")
        print("[ERROR] Please check camera connection and OS camera permissions.")
        return

    tracker = LiveAttendanceTracker(consecutive_required=consecutive_frames)
    print(f"Loaded {len(tracker.enrolled_students)} enrolled student template(s).")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[Warning] Failed to grab frame from camera.")
                break

            annotated_frame, face_evals, newly_recorded = tracker.process_frame(
                frame=frame,
                threshold=threshold,
                min_margin=min_margin,
                auto_record=True
            )

            for rec in newly_recorded:
                print(f"[KIOSK] Auto-Recorded: {rec['student_id']} ({rec['name']}) at {rec['time']}")

            cv2.imshow("Face Verification Smart Attendance", annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if key in [ord('q'), ord('Q'), 27]:
                print("\nExiting Live Attendance...")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[KIOSK] Camera released and windows closed successfully.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        run_live_webcam_attendance()
    else:
        test_img = "data/test_images/DS001_verify_02.jpeg"
        print(f"Testing batch attendance from test image: {test_img}")
        res = process_attendance_from_image(test_img)
        print("Attendance processing finished. Faces processed:", len(res))
