import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATABASE_PATH = os.path.join(PROJECT_ROOT, "database", "attendance.db")
EXPORTS_DIR = os.path.join(PROJECT_ROOT, "data", "exports")


def get_connection():
    """Returns a SQLite connection to attendance.db."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def get_all_attendance():
    """Fetch all attendance entries sorted newest first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            id,
            student_id,
            name,
            department,
            attendance_date,
            entry_time,
            similarity_score,
            verification_status
        FROM attendance
        ORDER BY attendance_date DESC, entry_time DESC
    """)
    records = cur.fetchall()
    conn.close()
    return records


def get_today_attendance():
    """Fetch attendance logged today."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            id,
            student_id,
            name,
            department,
            attendance_date,
            entry_time,
            similarity_score,
            verification_status
        FROM attendance
        WHERE attendance_date = ?
        ORDER BY entry_time ASC
    """, (today,))
    records = cur.fetchall()
    conn.close()
    return records


def get_student_attendance(student_id: str):
    """Fetch attendance history for a single student."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            id,
            student_id,
            name,
            department,
            attendance_date,
            entry_time,
            similarity_score,
            verification_status
        FROM attendance
        WHERE student_id = ?
        ORDER BY attendance_date DESC, entry_time DESC
    """, (student_id,))
    records = cur.fetchall()
    conn.close()
    return records


def get_today_attendance_count():
    """Count unique students verified today."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(DISTINCT student_id)
        FROM attendance
        WHERE attendance_date = ?
        AND verification_status = 'VERIFIED'
    """, (today,))
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_total_students():
    """Count enrolled students with valid consent."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM students
        WHERE consent_status = 'yes'
    """)
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_department_attendance():
    """Count verified attendance group by department."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            department,
            COUNT(*) AS attendance_count
        FROM attendance
        WHERE verification_status = 'VERIFIED'
        GROUP BY department
        ORDER BY attendance_count DESC
    """)
    records = cur.fetchall()
    conn.close()
    return records


def export_attendance_to_csv(output_path: str = None) -> str:
    """Exports attendance records to a CSV file in data/exports/."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(EXPORTS_DIR, f"attendance_report_{timestamp}.csv")

    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            id AS Record_ID,
            student_id AS Student_ID,
            name AS Name,
            department AS Department,
            attendance_date AS Date,
            entry_time AS Entry_Time,
            similarity_score AS Similarity_Score,
            verification_status AS Status
        FROM attendance
        ORDER BY attendance_date DESC, entry_time DESC
    """, conn)
    conn.close()

    df.to_csv(output_path, index=False)
    print(f"[Export] Saved {len(df)} records to: {output_path}")
    return output_path


def display_summary():
    """Print command-line summary of system metrics."""
    total_students = get_total_students()
    today_count = get_today_attendance_count()
    dept_data = get_department_attendance()

    print("\n========================================")
    print("ATTENDANCE SYSTEM METRICS SUMMARY")
    print("========================================")
    print(f"Total Registered Students: {total_students}")
    print(f"Today's Present Students:   {today_count}")
    print(f"Today's Absent Students:    {max(0, total_students - today_count)}")
    if total_students > 0:
        att_rate = (today_count / total_students) * 100
        print(f"Attendance Rate:           {att_rate:.1f}%")

    print("\nDepartment-wise Breakdown:")
    if not dept_data:
        print("  No records yet.")
    else:
        for dept, count in dept_data:
            print(f"  - {dept}: {count} attendance event(s)")
    print("========================================")


if __name__ == "__main__":
    display_summary()