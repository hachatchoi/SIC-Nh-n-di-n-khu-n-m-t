from database import conn, cursor
import os

DATASET_DIR = "dataset"


def create_employee(employee):

    try:

        cursor.execute(
            """
            INSERT INTO employees
            (name, employee_id, department)
            VALUES (?, ?, ?)
            """,
            (
                employee.name,
                employee.employee_id,
                employee.department
            )
        )

        conn.commit()

        return {
            "status": "success",
            "message": "Employee Registered Successfully"
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }


async def register_employee_image(employee_id, image):

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

    person_folder = os.path.join(
        DATASET_DIR,
        employee_id
    )

    os.makedirs(
        person_folder,
        exist_ok=True
    )

    image_path = os.path.join(
        person_folder,
        image.filename
    )

    with open(image_path, "wb") as f:

        f.write(
            await image.read()
        )

    return {

        "status": "success",

        "employee_id": employee_id,

        "file_saved": image.filename

    }