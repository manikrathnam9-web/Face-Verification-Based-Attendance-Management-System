import os
import sqlite3
from datetime import datetime

# Database path configuration
DATABASE_DIR = "database"
DATABASE_PATH = os.path.join(DATABASE_DIR, "attendance.db")


def get_connection():
    """Returns a SQLite connection to attendance.db."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def create_database():
    """Initializes SQLite schema for students and attendance tables."""
    connection = get_connection()
    cursor = connection.cursor()

    # Students registry table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            consent_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Attendance logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            attendance_date TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            similarity_score REAL NOT NULL,
            verification_status TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def has_attended_today(student_id: str, target_date: str = None) -> bool:
    """
    Check if a student already has a VERIFIED attendance record for the specified date.
    Defaults to today's local date.
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id FROM attendance
        WHERE student_id = ?
        AND attendance_date = ?
        AND verification_status = 'VERIFIED'
    """, (student_id, target_date))

    record = cursor.fetchone()
    connection.close()
    return record is not None


def record_attendance(student_id, name, department, similarity_score, verification_status="VERIFIED"):
    """
    Record an attendance entry into the database.
    Prevents duplicate VERIFIED attendance for the same student on the same date.
    Returns a dictionary with transaction results.
    """
    create_database()

    now = datetime.now()
    attendance_date = now.strftime("%Y-%m-%d")
    entry_time = now.strftime("%H:%M:%S")

    # Duplicate check for verified attendance
    if verification_status == "VERIFIED" and has_attended_today(student_id, attendance_date):
        print(f"[Attendance] Student {student_id} ({name}) has already been recorded for {attendance_date}.")
        return {
            "success": False,
            "status": "DUPLICATE",
            "message": f"Attendance already logged for {student_id} on {attendance_date}.",
            "student_id": student_id,
            "name": name,
            "date": attendance_date,
            "time": entry_time
        }

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO attendance (
            student_id,
            name,
            department,
            attendance_date,
            entry_time,
            similarity_score,
            verification_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        student_id,
        name,
        department,
        attendance_date,
        entry_time,
        float(similarity_score),
        verification_status
    ))

    connection.commit()
    inserted_id = cursor.lastrowid
    connection.close()

    print(f"[Attendance] Successfully recorded {verification_status} for {student_id} ({name}) at {entry_time}.")
    return {
        "success": True,
        "status": "RECORDED",
        "record_id": inserted_id,
        "student_id": student_id,
        "name": name,
        "department": department,
        "date": attendance_date,
        "time": entry_time,
        "similarity_score": round(float(similarity_score), 4),
        "verification_status": verification_status
    }


def get_all_registered_students():
    """Retrieve all students registered in the database with consent='yes'."""
    create_database()
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT student_id, name, department, year, consent_status, created_at
        FROM students
        ORDER BY student_id ASC
    """)
    students = cursor.fetchall()
    connection.close()
    return students


def get_all_attendance_records():
    """Retrieve all attendance entries ordered chronologically."""
    create_database()
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, student_id, name, department, attendance_date, entry_time, similarity_score, verification_status
        FROM attendance
        ORDER BY attendance_date DESC, entry_time DESC
    """)
    records = cursor.fetchall()
    connection.close()
    return records


if __name__ == "__main__":
    create_database()
    students = get_all_registered_students()
    print("Registered students:", len(students))
    records = get_all_attendance_records()
    print("Attendance records:", len(records))