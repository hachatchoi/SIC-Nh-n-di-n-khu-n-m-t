from datetime import datetime
from database import conn, cursor


def save_attendance(employee_id, device_info):

    # Check Employee Exists

    cursor.execute(
        """
        SELECT *
        FROM employees
        WHERE employee_id = ?
        """,
        (employee_id,)
    )

    employee = cursor.fetchone()

    if employee is None:

        return {
            "status": "error",
            "message": "Employee not found"
        }

    # Current Date & Time

    now = datetime.now()

    attendance_date = now.strftime("%Y-%m-%d")
    attendance_time = now.strftime("%H:%M:%S")

    # Duplicate Attendance Check

    cursor.execute(
        """
        SELECT *
        FROM attendance
        WHERE employee_id = ?
        AND attendance_date = ?
        """,
        (
            employee_id,
            attendance_date
        )
    )

    existing = cursor.fetchone()

    if existing:

        return {
            "status": "error",
            "message": "Attendance already marked today"
        }

    # Save Attendance

    cursor.execute(
        """
        INSERT INTO attendance
        (
            employee_id,
            attendance_date,
            attendance_time,
            device_info,
            status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            employee_id,
            attendance_date,
            attendance_time,
            device_info,
            "Present"
        )
    )

    conn.commit()

    return {
        "status": "success",
        "employee_id": employee_id,
        "attendance_date": attendance_date,
        "attendance_time": attendance_time,
        "message": "Attendance Marked Successfully"
    }