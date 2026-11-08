import os
import sqlite3
import numpy as np
import cv2

from app.face_engine import face_engine, DEFAULT_VERIFICATION_THRESHOLD
from app.attendance import record_attendance

DATABASE_PATH = "database/attendance.db"
EMBEDDINGS_DIR = "data/embeddings"


def get_student_record(student_id: str):
    """Retrieve student profile from database."""
    if not os.path.exists(DATABASE_PATH):
        return None

    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT student_id, name, department, year, consent_status
        FROM students
        WHERE student_id = ?
    """, (student_id,))
    student = cur.fetchone()
    conn.close()
    return student


def verify_student(
    student_id: str,
    image_or_path,
    record_on_verify: bool = True,
    threshold: float = DEFAULT_VERIFICATION_THRESHOLD
) -> dict:
    """
    1:1 Face Verification:
    Compares the face in image_or_path against the enrolled template of claimed student_id.
    Logs attendance automatically if verified and record_on_verify=True.
    """
    student_id = str(student_id).strip()

    # 1. Fetch student info
    student = get_student_record(student_id)
    if student is None:
        return {
            "verified": False,
            "status": "REJECTED",
            "message": f"Student ID '{student_id}' not found in registry.",
            "similarity_score": 0.0,
            "threshold": threshold
        }

    s_id, s_name, s_dept, s_year, s_consent = student
    if str(s_consent).lower() != "yes":
        return {
            "verified": False,
            "status": "REJECTED",
            "message": f"Student '{student_id}' does not have valid consent.",
            "similarity_score": 0.0,
            "threshold": threshold
        }

    # 2. Check enrolled embedding file
    enrolled_emb_path = os.path.join(EMBEDDINGS_DIR, f"{student_id}.npy")
    if not os.path.exists(enrolled_emb_path):
        return {
            "verified": False,
            "status": "REJECTED",
            "message": f"Enrolled embedding file missing for {student_id}.",
            "similarity_score": 0.0,
            "threshold": threshold
        }

    enrolled_embedding = np.load(enrolled_emb_path)

    # 3. Extract query face embedding
    if isinstance(image_or_path, str):
        if not os.path.exists(image_or_path):
            return {
                "verified": False,
                "status": "REJECTED",
                "message": f"Verification image not found: {image_or_path}",
                "similarity_score": 0.0,
                "threshold": threshold
            }
        image = cv2.imread(image_or_path)
    elif isinstance(image_or_path, np.ndarray):
        image = image_or_path
    else:
        return {
            "verified": False,
            "status": "REJECTED",
            "message": "Invalid verification image format.",
            "similarity_score": 0.0,
            "threshold": threshold
        }

    faces = face_engine.detect_faces(image)
    if len(faces) == 0:
        return {
            "verified": False,
            "status": "REJECTED",
            "message": "No face detected in verification image.",
            "similarity_score": 0.0,
            "threshold": threshold
        }

    query_embedding = faces[0].embedding
    if query_embedding is None:
        return {
            "verified": False,
            "status": "REJECTED",
            "message": "Could not extract face embedding.",
            "similarity_score": 0.0,
            "threshold": threshold
        }

    # 4. Cosine similarity
    similarity = face_engine.compute_similarity(enrolled_embedding, query_embedding)
    is_verified = bool(similarity >= threshold)
    status_str = "VERIFIED" if is_verified else "REJECTED"

    attendance_result = None
    if is_verified and record_on_verify:
        attendance_result = record_attendance(
            student_id=s_id,
            name=s_name,
            department=s_dept,
            similarity_score=similarity,
            verification_status=status_str
        )

    return {
        "verified": is_verified,
        "status": status_str,
        "student_id": s_id,
        "name": s_name,
        "department": s_dept,
        "year": s_year,
        "similarity_score": round(similarity, 4),
        "threshold": threshold,
        "attendance_record": attendance_result,
        "message": f"Face {status_str} with similarity score {similarity:.4f} (Threshold: {threshold})."
    }


def verify_cli():
    """Interactive CLI verification tool."""
    print("\n========================================")
    print("1:1 FACE VERIFICATION")
    print("========================================")

    student_id = input("Enter Student ID to verify (e.g. DS001): ").strip()
    if not student_id:
        student_id = "DS001"
        print(f"Using default student ID: {student_id}")

    default_image = "data/test_images/test_same_person.jpeg"
    print(f"Enter image path (leave blank for default '{default_image}'): ")
    image_path = input().strip()
    if not image_path:
        image_path = default_image

    result = verify_student(student_id, image_path, record_on_verify=True)

    print("\n----------------------------------------")
    print("Verification Result:", result["status"])
    print("Student ID:        ", result.get("student_id", student_id))
    print("Name:              ", result.get("name", "Unknown"))
    print("Department:        ", result.get("department", "Unknown"))
    print("Similarity Score:  ", result["similarity_score"])
    print("Threshold:         ", result["threshold"])
    print("Message:           ", result["message"])

    if result.get("attendance_record"):
        rec = result["attendance_record"]
        print("Attendance:        ", rec.get("status", "N/A"), f"({rec.get('message', '')})")
    print("========================================")


if __name__ == "__main__":
    verify_cli()