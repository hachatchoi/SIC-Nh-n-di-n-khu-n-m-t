#  AI Powered Facial Recognition Attendance System using FastAPI and InsightFace

A production-ready Facial Recognition Attendance System developed using FastAPI, InsightFace, OpenCV, and SQLite. The system registers employees, generates face embeddings, recognizes faces using cosine similarity, and automatically marks attendance while preventing duplicate entries.
 
---


#  Features

- Employee Registration
- Employee Image Upload
- Dataset Collection
- Face Embedding Generation
- Face Recognition using InsightFace
- Cosine Similarity Matching
- Automatic Attendance Marking (Backend)
- Duplicate Attendance Prevention
- Attendance History API
- REST API using FastAPI
- SQLite Database

---

#  Tech Stack

- Python 3.10+
- FastAPI
- InsightFace
- OpenCV
- NumPy
- Scikit-Learn
- SQLite
- ONNX Runtime

---

#  Project Structure

```
Facial-Recognition-Attendance-System
│
├── backend
│   ├── app.py
│   ├── database.py
│   ├── models.py
│   ├── register.py
│   ├── attendance_service.py
│   ├── face_engine.py
│   ├── recognize.py
│   ├── collect_dataset.py
│   ├── generate_embeddings.py
│   ├── requirements.txt
│   ├── .gitignore
│   ├── dataset
│   └── embeddings
│
├── mobile_app          (Future)
├── docs                (Future)
└── README.md
```

---

#  Installation

## 1 Clone Repository

```bash
git clone https://github.com/Vishal7-hub/Facial-Recognition-Attendance-System.git
```

Move into project

```bash
cd Facial-Recognition-Attendance-System/backend
```

---

## 2 Create Virtual Environment

Windows

```bash
python -m venv venv
```

Activate

```bash
venv\Scripts\activate
```

---

## 3 Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4 Download InsightFace Model

The first time you run the project, InsightFace automatically downloads the required models.

No manual setup is required.

---

## 5 Run Backend

```bash
uvicorn app:app --reload
```

Backend runs on

```
http://127.0.0.1:8000
```

Swagger Documentation

```
http://127.0.0.1:8000/docs
```

---

#  Database

SQLite database is automatically created.

```
attendance.db
```

No manual database setup is required.

---

#  Dataset Collection

Employee images are stored inside

```
dataset/

    EMP001/

    EMP002/

    EMP003/
```

---

#  Generate Face Embeddings

Run

```bash
python generate_embeddings.py
```

Generated file

```
embeddings/encodings.pkl
```

---

#  API Endpoints

| Method | Endpoint | Description |
|----------|-------------------------|----------------------------|
| GET | / | Home API |
| GET | /health | Health Check |
| POST | /employee | Register Employee |
| GET | /employees | Employee List |
| POST | /register | Upload Employee Images |
| POST | /mark_attendance | Mark Attendance |
| POST | /recognize | Face Recognition |
| GET | /attendance | Attendance History |

---

#  Project Workflow

```
Register Employee
        │
        ▼
Upload Images
        │
        ▼
Generate Face Embeddings
        │
        ▼
Store encodings.pkl
        │
        ▼
Capture Face
        │
        ▼
InsightFace Recognition
        │
        ▼
Cosine Similarity
        │
        ▼
Attendance Marked
        │
        ▼
SQLite Database
```

---

#  Dependencies

- FastAPI
- Uvicorn
- InsightFace
- OpenCV
- NumPy
- Scikit-Learn
- ONNX Runtime
- Python Multipart
- Pydantic

---

#  Troubleshooting

## encodings.pkl not found

Run

```bash
python generate_embeddings.py
```

---

## No Face Detected

Ensure that

- Face is clearly visible
- Good lighting
- Single face in image

---

## Camera not opening

Close other applications using the webcam.

---

## CUDA Warning

If you see

```
CUDAExecutionProvider not found
```

Ignore it.

The project automatically uses CPU Execution Provider.

---

#  Future Improvements

- Android Application
- Live Camera Attendance
- Liveness Detection
- Cloud Deployment
- Admin Dashboard
- Attendance Analytics
- Multi-camera Support

---

