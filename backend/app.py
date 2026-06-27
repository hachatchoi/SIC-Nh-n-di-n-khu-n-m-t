import cv2
import numpy as np
from register import create_employee
from register import register_employee_image

from fastapi import FastAPI, UploadFile, File, Form
from attendance_service import save_attendance
from database import conn, cursor 
from models import Employee
from face_engine import recognize_face
from collect_dataset import collect_dataset
from generate_embeddings import generate_embeddings



app = FastAPI()


# HOME API

@app.get("/")
def home():
    return {
        "message": "Mobile Attendance Backend Running"
    }


# HEALTH CHECK

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }




@app.post("/generate_embeddings")
def generate():

    return generate_embeddings()



@app.post("/collect_dataset")
def collect_employee_dataset(
    employee_id: str
):

    collect_dataset(employee_id)

    return {

        "status": "success",

        "message": "Dataset Collected Successfully"

    }

#REGISTER EMPLOYEES

@app.post("/employee")
def employee(employee: Employee):

    return create_employee(employee)


#GET ALL EMPLOYEES

@app.get("/employees")
def get_employees():

    cursor.execute(
        """
        SELECT *
        FROM employees
        """
    )

    employees = cursor.fetchall()

    return {
        "employees": employees
    }


# UPLOAD EMPLOYEE IMAGE

@app.post("/register")
async def register(
    employee_id: str = Form(...),
    image: UploadFile = File(...)
):

    return await register_employee_image(
        employee_id,
        image
    )




@app.post("/mark_attendance")
def mark_attendance(
    employee_id: str,
    device_info: str
):

    return save_attendance(
        employee_id,
        device_info
    )

@app.get("/attendance")
def get_attendance():

    cursor.execute(
        """
        SELECT *
        FROM attendance
        ORDER BY id DESC
        """
    )

    records = cursor.fetchall()

    return {
        "attendance": records
    }



@app.post("/recognize")
async def recognize(image: UploadFile = File(...)):

    # Read Image

    image_bytes = await image.read()

    # Bytes -> NumPy

    np_array = np.frombuffer(
        image_bytes,
        np.uint8
    )

    # NumPy -> OpenCV Image

    img = cv2.imdecode(
        np_array,
        cv2.IMREAD_COLOR
    )

    # AI Recognition

    result = recognize_face(img)

    # Face Found

    if result["status"] == "success":

        attendance = save_attendance(
            employee_id=result["employee_id"],
            device_info="Android App"
        )

        attendance["similarity"] = result["similarity"]

        return attendance

    # Face Not Found

    return result



