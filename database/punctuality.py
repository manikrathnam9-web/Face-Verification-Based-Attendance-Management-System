import os
import sys
import sqlite3
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATABASE_PATH = os.path.join(PROJECT_ROOT, "database", "attendance.db")

ON_TIME_START = "09:00:00"
ON_TIME_END = "09:30:00"
LATE_END = "09:40:00"


def classify_punctuality(entry_time: str) -> str:
    """
    Classify attendance based on entry time.
    Rules:
        Entry <= 09:30:00 -> ON TIME
        09:30:01 - 09:39:59 -> LATE
        >= 09:40:00 -> VERY LATE
    """
    try:
        time = datetime.strptime(entry_time, "%H:%M:%S").time()
    except ValueError:
        # Handle cases with full timestamp
        try:
            time = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S").time()
        except ValueError:
            return "UNKNOWN"

    on_time_end = datetime.strptime(ON_TIME_END, "%H:%M:%S").time()
    late_end = datetime.strptime(LATE_END, "%H:%M:%S").time()

    if time <= on_time_end:
        return "ON TIME"
    elif time < late_end:
        return "LATE"
    else:
        return "VERY LATE"


def get_attendance_records():
    """Fetch all verified attendance records."""
    if not os.path.exists(DATABASE_PATH):
        return []

    conn = sqlite3.connect(DATABASE_PATH)
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
        WHERE verification_status = 'VERIFIED'
        ORDER BY attendance_date DESC, entry_time ASC
    """)
    records = cur.fetchall()
    conn.close()
    return records


def analyze_punctuality():
    """Analyze and tag each verified record with punctuality status."""
    records = get_attendance_records()
    results = []
    for r in records:
        entry_time = r[5]
        status = classify_punctuality(entry_time)
        results.append({
            "id": r[0],
            "student_id": r[1],
            "name": r[2],
            "department": r[3],
            "attendance_date": r[4],
            "entry_time": entry_time,
            "similarity_score": r[6],
            "verification_status": r[7],
            "punctuality_status": status
        })
    return results


def get_punctuality_summary():
    """Count totals in each punctuality category."""
    results = analyze_punctuality()
    summary = {"ON TIME": 0, "LATE": 0, "VERY LATE": 0}
    for item in results:
        st = item["punctuality_status"]
        if st in summary:
            summary[st] += 1
    return summary


def get_student_punctuality():
    """Compute punctuality breakdown per student."""
    results = analyze_punctuality()
    student_stats = {}

    for r in results:
        sid = r["student_id"]
        if sid not in student_stats:
            student_stats[sid] = {
                "student_id": sid,
                "name": r["name"],
                "department": r["department"],
                "total_attendance": 0,
                "on_time": 0,
                "late": 0,
                "very_late": 0
            }
        student_stats[sid]["total_attendance"] += 1
        st = r["punctuality_status"]
        if st == "ON TIME":
            student_stats[sid]["on_time"] += 1
        elif st == "LATE":
            student_stats[sid]["late"] += 1
        elif st == "VERY LATE":
            student_stats[sid]["very_late"] += 1

    for sid, st in student_stats.items():
        total = st["total_attendance"]
        st["punctuality_percentage"] = round((st["on_time"] / total) * 100, 2) if total > 0 else 0.0

    return list(student_stats.values())


def display_punctuality():
    """Command line display of punctuality analysis."""
    summary = get_punctuality_summary()
    print("\n========================================")
    print("PUNCTUALITY ANALYSIS")
    print("========================================")
    print(f"ON TIME:   {summary['ON TIME']}")
    print(f"LATE:      {summary['LATE']}")
    print(f"VERY LATE: {summary['VERY LATE']}")
    print("========================================")


if __name__ == "__main__":
    display_punctuality()
