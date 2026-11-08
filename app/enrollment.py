import os
import json
import sqlite3
from datetime import datetime
import cv2
import numpy as np

from app.face_engine import face_engine

PROFILE_DIR = "data/enrollment"
EMBEDDING_DIR = "data/embeddings"
DATABASE_DIR = "database"
DATABASE_PATH = os.path.join(DATABASE_DIR, "attendance.db")


def enroll_student(student_id: str, name: str, department: str, year: str, image_or_path, consent: str = "yes") -> dict:
    """
    Enrolls a student into the system:
    1. Validates input parameters and consent.
    2. Decodes image and extracts 512-D InsightFace embedding.
    3. Runs quality check (single face, blur, confidence).
    4. Saves JSON profile and .npy embedding vector.
    5. Registers student in SQLite database.

    Returns: dict with status, student info, and file paths.
    """
    # Validation
    student_id = str(student_id).strip()
    name = str(name).strip()
    department = str(department).strip()
    year = str(year).strip()
    consent = str(consent).strip().lower()

    if not student_id:
        return {"success": False, "message": "Student ID cannot be empty."}
    if not name:
        return {"success": False, "message": "Student name cannot be empty."}
    if not department:
        return {"success": False, "message": "Department cannot be empty."}
    if not year:
        return {"success": False, "message": "Year cannot be empty."}
    if consent not in ["yes", "y", "true"]:
        return {"success": False, "message": "Enrollment aborted: Student consent was not provided."}

    # Load and process image
    if isinstance(image_or_path, str):
        if not os.path.exists(image_or_path):
            return {"success": False, "message": f"Image file not found: {image_or_path}"}
        image = cv2.imread(image_or_path)
        if image is None:
            return {"success": False, "message": f"Could not decode image at {image_or_path}."}
    elif isinstance(image_or_path, np.ndarray):
        image = image_or_path
    else:
        return {"success": False, "message": "Invalid image input. Expected file path or numpy array."}

    # Detect faces and extract embedding
    faces = face_engine.detect_faces(image)
    if len(faces) == 0:
        return {"success": False, "message": "Enrollment failed: No face detected in the image."}
    if len(faces) > 1:
        return {"success": False, "message": f"Enrollment failed: Multiple faces ({len(faces)}) detected. Please provide an image with exactly one face."}

    face = faces[0]
    embedding = face.embedding
    if embedding is None:
        return {"success": False, "message": "Enrollment failed: Could not generate face embedding."}

    # Quality check
    quality_ok, quality_msg = face_engine.check_quality(image, face)
    if not quality_ok:
        return {"success": False, "message": f"Quality warning: {quality_msg}"}

    # Create directories
    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(EMBEDDING_DIR, exist_ok=True)
    os.makedirs(DATABASE_DIR, exist_ok=True)

    # Save JSON profile
    profile_data = {
        "student_id": student_id,
        "name": name,
        "department": department,
        "year": year,
        "consent_status": "yes",
        "enrolled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    profile_path = os.path.join(PROFILE_DIR, f"{student_id}.json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=4)

    # Save embedding vector
    embedding_path = os.path.join(EMBEDDING_DIR, f"{student_id}.npy")
    np.save(embedding_path, embedding)

    # Upsert into SQLite database
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            consent_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        INSERT OR REPLACE INTO students (
            student_id, name, department, year, consent_status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id, name, department, year, "yes", created_at))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": f"Student {student_id} ({name}) successfully enrolled.",
        "student_id": student_id,
        "name": name,
        "department": department,
        "year": year,
        "profile_path": profile_path,
        "embedding_path": embedding_path,
        "embedding_shape": embedding.shape
    }


def capture_from_webcam():
    """Captures a single frame from the default webcam."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not access webcam.")
        return None

    print("\n[Webcam] Position your face in front of the camera.")
    print("[Webcam] Press SPACEBAR to capture photo, or ESC to cancel.")

    captured_frame = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Display preview overlay
        display_frame = frame.copy()
        cv2.putText(
            display_frame, "Press SPACE to Capture | ESC to Cancel",
            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
        )
        cv2.imshow("Student Face Capture", display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 32:  # SPACE
            captured_frame = frame
            break
        elif key == 27:  # ESC
            print("Capture cancelled by user.")
            break

    cap.release()
    cv2.destroyAllWindows()
    return captured_frame


def enroll_cli():
    """Interactive CLI enrollment wizard."""
    print("\n========================================")
    print("STUDENT FACE ENROLLMENT WIZARD")
    print("========================================")

    student_id = input("Enter Student ID: ").strip()
    name = input("Enter Student Name: ").strip()
    department = input("Enter Department: ").strip()
    year = input("Enter Year: ").strip()
    consent = input("Has student provided consent? (yes/no): ").strip().lower()

    if consent != "yes":
        print("Enrollment cancelled: Consent is mandatory.")
        return

    print("\nSelect Image Source:")
    print("1. Image file path")
    print("2. Capture via live webcam")
    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        img_path = input("Enter full or relative image file path: ").strip()
        result = enroll_student(student_id, name, department, year, img_path, consent)
    elif choice == "2":
        frame = capture_from_webcam()
        if frame is None:
            print("No photo captured. Enrollment aborted.")
            return
        result = enroll_student(student_id, name, department, year, frame, consent)
    else:
        print("Invalid option selected.")
        return

    print("\n----------------------------------------")
    if result["success"]:
        print("SUCCESS:", result["message"])
        print("Profile saved:", result["profile_path"])
        print("Embedding saved:", result["embedding_path"])
    else:
        print("FAILED:", result["message"])
    print("========================================")


if __name__ == "__main__":
    enroll_cli()
