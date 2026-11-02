"""Classroom attendance with sessions and preserved daily history."""
import csv
import io
import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, time as daytime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from face_engine import face_app
from insightface.app.common import Face

from auth import current_teacher, require_teacher, require_admin
from auth_migration import migrate
from course_migration import migrate_courses
from student_codes import normalize_student_code

router = APIRouter(prefix="/api", dependencies=[Depends(require_teacher)])
DB_PATH = Path(os.getenv("SIC_DATABASE_PATH", Path(__file__).resolve().parent / "classroom.db"))
AI_LOCK = threading.Lock()
VN_TIME = timezone(timedelta(hours=7))


@contextmanager
def database():
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with database() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            subject TEXT NOT NULL DEFAULT '', teacher TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id),
            code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, embedding TEXT,
            photo_count INTEGER NOT NULL DEFAULT 0,
            created_on TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS class_attendance (
            id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
            day TEXT NOT NULL, time TEXT NOT NULL, method TEXT NOT NULL,
            similarity REAL, UNIQUE(student_id, day)
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id),
            name TEXT NOT NULL, day TEXT NOT NULL, starts_at TEXT NOT NULL,
            ends_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'closed'
            CHECK(status IN ('open','closed')),
            UNIQUE(class_id,day,name)
        );
        CREATE TABLE IF NOT EXISTS session_attendance (
            id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id),
            student_id INTEGER NOT NULL REFERENCES students(id), time TEXT NOT NULL,
            method TEXT NOT NULL, similarity REAL, UNIQUE(session_id,student_id)
        );
        CREATE INDEX IF NOT EXISTS sessions_class_day ON sessions(class_id,day);
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY,
            class_id INTEGER NOT NULL REFERENCES classes(id),
            name TEXT NOT NULL, starts_on TEXT NOT NULL, ends_on TEXT,
            starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
            weekdays TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE UNIQUE INDEX IF NOT EXISTS schedules_active_name
            ON schedules(class_id,name) WHERE active=1;
        CREATE VIEW IF NOT EXISTS daily_attendance AS
            SELECT student_id,day,MIN(time) AS time, method, similarity
            FROM (
                SELECT student_id,day,time,method,similarity FROM class_attendance
                UNION ALL
                SELECT a.student_id,b.day,a.time,a.method,a.similarity FROM session_attendance a
                JOIN sessions b ON b.id=a.session_id
            ) GROUP BY student_id,day;
        """)

    migrate(DB_PATH)
    migrate_courses(DB_PATH)
    with database() as db:
        columns = {r[1] for r in db.execute('PRAGMA table_info(classes)')}
        for column in ('course_code', 'room'):
            if column not in columns:
                db.execute(f"ALTER TABLE classes ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")

init_db()


def today():
    return datetime.now(VN_TIME).date().isoformat()


def require_class(db, class_id):
    row = db.execute("SELECT * FROM classes WHERE id=? AND (owner_id=? OR ?)", (class_id, current_teacher()["id"], is_admin())).fetchone()
    if row is None:
        raise HTTPException(404, "Không tìm thấy lớp học.")
    return row


def is_admin():
    return current_teacher().get("role") == "admin"


@router.get('/teaching-calendar')
def teaching_calendar(day: date | None = None, view: str = 'week', teacher_id: int | None = None):
    """Read-only projection: viewing future weeks never creates attendance sessions."""
    if view not in ('day', 'week'):
        raise HTTPException(400, 'Chọn lịch ngày hoặc tuần.')
    user = current_teacher()
    if not is_admin() and teacher_id not in (None, user['id']):
        raise HTTPException(403, 'Bạn chỉ được xem lịch dạy của mình.')
    owner = teacher_id if is_admin() else user['id']
    selected = day or date.fromisoformat(today())
    start = selected if view == 'day' else selected - timedelta(days=selected.weekday())
    days = [(start + timedelta(days=i)).isoformat() for i in range(1 if view == 'day' else 7)]
    with database() as db:
        courses = db.execute('SELECT * FROM classes WHERE (? IS NULL OR owner_id=?) ORDER BY name', (owner, owner)).fetchall()
        events = []
        for course in courses:
            sessions = db.execute('SELECT * FROM sessions WHERE class_id=? AND day BETWEEN ? AND ?', (course['id'],days[0],days[-1])).fetchall()
            keys = {(s['day'],s['name']) for s in sessions}
            base = {'class_id':course['id'],'class_name':course['name'],'subject':course['subject'],
                    'teacher_id':course['owner_id'],'teacher_name':course['teacher'],
                    'course_code':course['course_code'],'room':course['room']}
            for session in sessions:
                events.append({**base, **dict(session), 'session_id':session['id'], 'planned':False})
            schedules = db.execute('SELECT * FROM schedules WHERE class_id=? AND active=1', (course['id'],)).fetchall()
            for schedule in schedules:
                for target in days:
                    # Match automatic materialization: do not fabricate past lessons.
                    if target < today() or target < schedule['starts_on'] or (schedule['ends_on'] and target > schedule['ends_on']):
                        continue
                    if date.fromisoformat(target).weekday() not in json.loads(schedule['weekdays']) or (target,schedule['name']) in keys:
                        continue
                    events.append({**base,'session_id':None,'schedule_id':schedule['id'],'name':schedule['name'],
                                   'day':target,'starts_at':schedule['starts_at'],'ends_at':schedule['ends_at'],
                                   'status':'planned','planned':True})
        events.sort(key=lambda e:(e['day'],e['starts_at'],e['class_name']))
        for event in events:
            event['conflict'] = any(other is not event and event['teacher_id'] is not None
                and other['teacher_id']==event['teacher_id'] and other['day']==event['day']
                and other['starts_at']<event['ends_at'] and other['ends_at']>event['starts_at'] for other in events)
    return {'days':days,'today':today(),'events':events}


class ClassInput(BaseModel):
    course_code: str = Field(default="", max_length=40)
    room: str = Field(default="", max_length=60)
    name: str = Field(min_length=1, max_length=60)
    subject: str = Field(default="", max_length=120)
    teacher: str = Field(default="", max_length=100)
    owner_id: int | None = None


def assigned_teacher(db, owner_id):
    row = db.execute("SELECT id,name FROM teachers WHERE id=? AND active=1 AND role='teacher'", (owner_id,)).fetchone()
    if row is None:
        raise HTTPException(400, 'Hãy chọn giảng viên phụ trách lớp môn học.')
    return row


@router.get('/teachers')
def teachers():
    require_admin()
    with database() as db:
        return {'teachers': [dict(r) for r in db.execute("SELECT id,name,username FROM teachers WHERE active=1 AND role='teacher' ORDER BY name")]}


@router.patch('/classes/{class_id}')
def edit_class(class_id: int, data: ClassInput):
    require_admin()
    if not data.name.strip():
        raise HTTPException(400, 'Nhập tên lớp môn học.')
    try:
        with database() as db:
            require_class(db, class_id)
            owner = assigned_teacher(db, data.owner_id)
            db.execute('UPDATE classes SET name=?,subject=?,teacher=?,owner_id=?,course_code=?,room=? WHERE id=?',
                       (data.name.strip(),data.subject.strip(),owner['name'],owner['id'],data.course_code.strip(),data.room.strip(),class_id))
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Tên lớp môn học đã tồn tại với giảng viên này.')
    return {'id':class_id}


@router.get('/students')
def student_directory():
    require_admin()
    with database() as db:
        return {'students': [dict(r) for r in db.execute('SELECT id,code,name,photo_count FROM students ORDER BY name,code')]}


class EnrollmentInput(BaseModel):
    student_id: int


@router.post('/classes/{class_id}/enrollments', status_code=201)
def enroll_student(class_id: int, data: EnrollmentInput):
    require_admin()
    with database() as db:
        require_class(db, class_id)
        if not db.execute('SELECT id FROM students WHERE id=?', (data.student_id,)).fetchone():
            raise HTTPException(404, 'Không tìm thấy sinh viên.')
        result = db.execute('INSERT OR IGNORE INTO enrollments VALUES(?,?,?)', (class_id,data.student_id,today()))
        if not result.rowcount:
            raise HTTPException(409, 'Sinh viên đã ghi danh lớp môn học này.')
    return {'class_id':class_id,'student_id':data.student_id}


@router.get("/classes")
def classes():
    with database() as db:
        rows = db.execute("""SELECT c.*, COUNT(s.student_id) AS student_count
            FROM classes c LEFT JOIN enrollments s ON s.class_id=c.id
            WHERE (c.owner_id=? OR ?) GROUP BY c.id ORDER BY c.name""", (current_teacher()["id"], is_admin())).fetchall()
    return {"classes": [dict(row) for row in rows], "today": today()}


@router.post("/classes", status_code=201)
def create_class(data: ClassInput):
    require_admin()
    if not data.name.strip():
        raise HTTPException(400, "Vui lòng nhập tên lớp.")
    try:
        with database() as db:
            owner = assigned_teacher(db, data.owner_id)
            result = db.execute("INSERT INTO classes(name,subject,teacher,owner_id,course_code,room) VALUES(?,?,?,?,?,?)",
                                (data.name.strip(), data.subject.strip(), owner["name"], owner["id"], data.course_code.strip(), data.room.strip()))
            return {"id": result.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Tên lớp đã tồn tại.")


@router.get("/dashboard")
def dashboard():
    selected = today()
    days = [(date.fromisoformat(selected) - timedelta(days=i)).isoformat()
            for i in range(6, -1, -1)]
    with database() as db:
        db.execute("BEGIN")  # All figures come from the same database snapshot.
        rows = db.execute("""SELECT c.id,c.name,c.teacher,COUNT(s.student_id) AS total,
            COUNT(a.student_id) AS present FROM classes c
            LEFT JOIN enrollments s ON s.class_id=c.id AND s.enrolled_on<=?
            LEFT JOIN daily_attendance a ON a.student_id=s.student_id AND a.class_id=s.class_id AND a.day=?
            WHERE (c.owner_id=? OR ?) GROUP BY c.id ORDER BY c.name""", (selected, selected, current_teacher()["id"], is_admin())).fetchall()
        trend = []
        for day in days:
            row = db.execute("""SELECT COUNT(s.student_id) AS total, COUNT(a.student_id) AS present
                FROM enrollments s LEFT JOIN daily_attendance a
                ON a.student_id=s.student_id AND a.class_id=s.class_id AND a.day=? WHERE s.enrolled_on<=? AND s.class_id IN (SELECT id FROM classes WHERE owner_id=? OR ?)""", (day, day, current_teacher()["id"], is_admin())).fetchone()
            trend.append({"day": day, **dict(row)})
        recent = db.execute("""SELECT s.name,s.code,c.name AS class_name,a.time
            FROM daily_attendance a JOIN students s ON s.id=a.student_id
            JOIN classes c ON c.id=a.class_id WHERE a.day=? AND (c.owner_id=? OR ?)
            ORDER BY a.time DESC,s.id DESC LIMIT 8""", (selected, current_teacher()["id"], is_admin())).fetchall()
    total = sum(row["total"] for row in rows)
    present = sum(row["present"] for row in rows)
    return {"day": selected, "class_count": len(rows), "total": total,
            "present": present, "pending": total-present,
            "rate": round(present / total * 100) if total else 0,
            "classes": [dict(row) for row in rows], "trend": trend,
            "recent": [dict(row) for row in recent]}


def roster(class_id, day, session_id=None):
    with database() as db:
        require_class(db, class_id)
        if session_id is not None:
            day = require_session(db, session_id, class_id)['day']
            join = 'LEFT JOIN session_attendance a ON a.student_id=s.id AND a.session_id=?'
            key = session_id
        else:
            join = 'LEFT JOIN daily_attendance a ON a.student_id=s.id AND a.class_id=e.class_id AND a.day=?'
            key = day
        rows = db.execute(f"""SELECT s.id,s.code,s.name,s.photo_count,a.time,a.method,a.similarity
            FROM enrollments e JOIN students s ON s.id=e.student_id {join}
            WHERE e.class_id=? AND e.enrolled_on<=? ORDER BY s.name,s.code""",
            (key,class_id,day)).fetchall()
    return [dict(row) for row in rows]


@router.get("/classes/{class_id}/roster")
def get_roster(class_id: int, day: date | None = None, session_id: int | None = None):
    selected = day.isoformat() if day else today()
    if session_id is not None:
        with database() as db:
            selected = require_session(db, session_id, class_id)['day']
    return {"students": roster(class_id, selected, session_id), "day": selected}


class SessionInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    day: date
    starts_at: daytime
    ends_at: daytime
    weekdays: list[int] = Field(default_factory=list)
    ends_on: date | None = None


class SessionStatus(BaseModel):
    status: str = Field(pattern='^(open|closed)$')


def require_session(db, session_id, class_id=None, writable=False):
    session = db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
    if session is None or (class_id is not None and session['class_id'] != class_id):
        raise HTTPException(404, 'Không tìm thấy buổi học trong lớp này.')
    require_class(db, session['class_id'])
    if writable:
        now = datetime.now(VN_TIME)
        if session['status'] != 'open':
            raise HTTPException(409, 'Buổi điểm danh đang đóng. Hãy mở buổi trước.')
        if session['day'] != now.date().isoformat() or not session['starts_at'] <= now.strftime('%H:%M:%S') < session['ends_at']:
            raise HTTPException(409, 'Ngoài ngày hoặc khung giờ của buổi học. Hãy chọn buổi phù hợp.')
    return session


@router.get('/classes/{class_id}/sessions')
def list_sessions(class_id: int, day: date | None = None):
    selected = day.isoformat() if day else today()
    with database() as db:
        require_class(db, class_id)
        # Materialize today's lessons on access, never fabricate past attendance.
        if selected == today():
            materialize_schedules(db, class_id, selected)
        rows = db.execute('SELECT * FROM sessions WHERE class_id=? AND day=? ORDER BY starts_at,id', (class_id, selected)).fetchall()
    now = datetime.now(VN_TIME)
    return {'day': selected, 'sessions': [{**dict(row), 'can_attend': row['status']=='open' and row['day']==now.date().isoformat() and row['starts_at'] <= now.strftime('%H:%M:%S') < row['ends_at']} for row in rows]}


@router.post('/classes/{class_id}/sessions', status_code=201)
def create_session(class_id: int, data: SessionInput):
    require_admin()
    if not data.name.strip() or data.starts_at.tzinfo or data.ends_at.tzinfo or data.starts_at >= data.ends_at:
        raise HTTPException(400, 'Nhập tên buổi và giờ kết thúc sau giờ bắt đầu trong cùng ngày, theo giờ Việt Nam.')
    if any(d < 0 or d > 6 for d in data.weekdays) or (data.ends_on and data.ends_on < data.day):
        raise HTTPException(400, 'Chọn thứ hợp lệ và ngày kết thúc không trước ngày bắt đầu.')
    if data.weekdays and data.day < date.fromisoformat(today()):
        raise HTTPException(400, 'Lịch lặp lại phải bắt đầu từ hôm nay hoặc ngày tương lai.')
    try:
        with database() as db:
            require_class(db, class_id)
            if data.weekdays:
                result = db.execute('INSERT INTO schedules(class_id,name,starts_on,ends_on,starts_at,ends_at,weekdays) VALUES(?,?,?,?,?,?,?)',
                    (class_id,data.name.strip(),data.day.isoformat(),data.ends_on.isoformat() if data.ends_on else None,
                     data.starts_at.isoformat(timespec='seconds'),data.ends_at.isoformat(timespec='seconds'),json.dumps(sorted(set(data.weekdays)))))
                materialize_schedules(db, class_id, today())
                return {'id': None, 'schedule_id': result.lastrowid}
            result = db.execute('INSERT INTO sessions(class_id,name,day,starts_at,ends_at) VALUES(?,?,?,?,?)',
                                (class_id,data.name.strip(),data.day.isoformat(),data.starts_at.isoformat(timespec='seconds'),data.ends_at.isoformat(timespec='seconds')))
            return {'id':result.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Tên buổi hoặc lịch lặp lại đã tồn tại trong lớp.')


def materialize_schedules(db, class_id, selected):
    weekday = date.fromisoformat(selected).weekday()
    for row in db.execute('SELECT * FROM schedules WHERE class_id=? AND active=1 AND starts_on<=? AND (ends_on IS NULL OR ends_on>=?)', (class_id,selected,selected)).fetchall():
        if weekday in json.loads(row['weekdays']):
            db.execute('INSERT OR IGNORE INTO sessions(class_id,name,day,starts_at,ends_at) VALUES(?,?,?,?,?)',
                       (class_id,row['name'],selected,row['starts_at'],row['ends_at']))


@router.get('/classes/{class_id}/schedules')
def list_schedules(class_id: int):
    with database() as db:
        require_class(db, class_id)
        rows = db.execute('SELECT * FROM schedules WHERE class_id=? AND active=1 ORDER BY starts_at,id', (class_id,)).fetchall()
    return {'schedules': [{**dict(row), 'weekdays':json.loads(row['weekdays'])} for row in rows]}


@router.delete('/classes/{class_id}/schedules/{schedule_id}')
def stop_schedule(class_id: int, schedule_id: int):
    require_admin()
    with database() as db:
        require_class(db, class_id)
        result = db.execute('UPDATE schedules SET active=0 WHERE id=? AND class_id=? AND active=1', (schedule_id,class_id))
        if not result.rowcount:
            raise HTTPException(404, 'Không tìm thấy lịch đang áp dụng.')
    return {'status':'stopped'}


@router.patch('/classes/{class_id}/sessions/{session_id}')
def change_session_status(class_id: int, session_id: int, data: SessionStatus):
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        require_session(db, session_id, class_id)
        db.execute('UPDATE sessions SET status=? WHERE id=?', (data.status,session_id))
    return {'id':session_id, 'status':data.status}


def face_inside_guide(bbox, width, height):
    """Check face extents against the oval, not empty corners of its box."""
    x1, y1, x2, y2 = np.asarray(bbox, dtype=float)
    if not np.isfinite([x1, y1, x2, y2]).all() or x2 <= x1 or y2 <= y1:
        return False
    radius_y = min(height * 0.39, width * 0.4 / 0.75)
    radius_x = radius_y * 0.75
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return all(((x - width / 2) / radius_x) ** 2 +
               ((y - height / 2) / radius_y) ** 2 <= 1
               for x, y in ((x1, cy), (x2, cy), (cx, y1), (cx, y2)))


def detect_faces(image):
    boxes, landmarks = face_app.det_model.detect(image, max_num=0, metric="default")
    return [Face(bbox=box[:4], det_score=box[4],
                 kps=landmarks[i] if landmarks is not None else None)
            for i, box in enumerate(boxes)]


def embed_face(image, face):
    return face_app.models["recognition"].get(image, face)


def extract_embedding(raw, require_guide=False):
    if not raw or len(raw) > 10 * 1024 * 1024:
        raise HTTPException(400, "Ảnh phải có dung lượng từ 1 byte đến 10 MB.")
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Không đọc được ảnh. Hãy chọn ảnh JPG hoặc PNG.")
    height, width = image.shape[:2]
    if max(height, width) > 1600:
        image = cv2.resize(image, (round(width * 1600 / max(height, width)),
                                   round(height * 1600 / max(height, width))))
    with AI_LOCK:
        faces = detect_faces(image)
    if require_guide:
        faces = [face for face in faces
                 if face_inside_guide(face.bbox, image.shape[1], image.shape[0])]
        if not faces:
            raise HTTPException(400, "Chưa có mặt nằm trọn trong oval: mặt đang ngoài vòng hoặc sát viền. Hãy đưa mặt vào giữa oval, lùi lại nếu cần.")
        if len(faces) > 1:
            raise HTTPException(400, "Có nhiều khuôn mặt trong oval. Chỉ một người đứng trong oval mỗi lần điểm danh.")
    elif len(faces) != 1:
        raise HTTPException(400, "Ảnh cần có đúng một khuôn mặt rõ nét.")
    # Only run the recognition model on the selected person, never bystanders.
    with AI_LOCK:
        vector = np.asarray(embed_face(image, faces[0]), dtype=np.float32)
    return vector / max(float(np.linalg.norm(vector)), 1e-12)


@router.post("/students", status_code=201)
def create_student(class_id: int = Form(...), name: str = Form(...),
                   code: str = Form(...), images: list[UploadFile] = File(...),
                   use_guide: bool = Form(False)):
    require_admin()
    # Direct Python callers do not receive FastAPI's parsed default.
    guided = use_guide is True
    name = name.strip()
    try:
        code = normalize_student_code(code)
    except ValueError as error:
        raise HTTPException(400, str(error))
    if not name or len(name) > 100:
        raise HTTPException(400, "Tên sinh viên phải có từ 1 đến 100 ký tự.")
    if not 1 <= len(images) <= 5:
        raise HTTPException(400, "Hãy chọn từ 1 đến 5 ảnh.")
    with database() as db:
        require_class(db, class_id)
        if db.execute("SELECT id FROM students WHERE code=?", (code,)).fetchone():
            raise HTTPException(409, "Mã sinh viên đã có hồ sơ. Hãy dùng chức năng Ghi danh sinh viên có sẵn.")
    vectors = [extract_embedding(image.file.read(10 * 1024 * 1024 + 1), require_guide=guided) for image in images]
    if any(float(np.dot(vectors[0], vector)) < 0.4 for vector in vectors[1:]):
        raise HTTPException(400, "Các ảnh không khớp cùng một người. Hãy kiểm tra lại.")
    vector = np.mean(vectors, axis=0)
    vector /= max(float(np.linalg.norm(vector)), 1e-12)
    try:
        with database() as db:
            result = db.execute("""INSERT INTO students(code,name,embedding,photo_count,created_on)
                VALUES(?,?,?,?,?)""", (code, name, json.dumps(vector.tolist()), len(images), today()))
            db.execute("INSERT INTO enrollments VALUES(?,?,?)", (class_id,result.lastrowid,today()))
            return {"id": result.lastrowid, "name": name, "photo_count": len(images)}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Mã sinh viên đã có hồ sơ. Hãy dùng chức năng Ghi danh sinh viên có sẵn.")


def record_attendance(student_id, method, similarity=None, session_id=None):
    now = datetime.now(VN_TIME)
    if session_id is None:
        raise HTTPException(400, 'Hãy chọn buổi học trước khi điểm danh.')
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        student = db.execute("SELECT id,name,code FROM students WHERE id=?", (student_id,)).fetchone()
        if student is None:
            raise HTTPException(404, "Không tìm thấy học sinh.")
        session = require_session(db, session_id, writable=True)
        if not db.execute('SELECT 1 FROM enrollments WHERE class_id=? AND student_id=? AND enrolled_on<=?',
                          (session['class_id'],student_id,session['day'])).fetchone():
            raise HTTPException(400, 'Sinh viên chưa ghi danh trong lớp môn học này.')
        result = db.execute("""INSERT OR IGNORE INTO session_attendance
            (session_id,student_id,time,method,similarity) VALUES(?,?,?,?,?)""",
            (session_id,student_id,now.strftime("%H:%M:%S"),method,similarity))
        duplicate = result.rowcount == 0
        entry = db.execute("SELECT time FROM session_attendance WHERE student_id=? AND session_id=?",
                           (student_id,session_id)).fetchone()
    return {"status": "duplicate" if duplicate else "success", "student": dict(student),
            "time": entry["time"], "similarity": similarity, "session_id":session_id, "session_name":session['name']}


@router.post("/classes/{class_id}/recognize")
def recognize(class_id: int, image: UploadFile = File(...), session_id: int | None = None):
    if session_id is None:
        raise HTTPException(400, 'Hãy chọn buổi học trước khi điểm danh.')
    with database() as db:
        require_class(db, class_id)
        require_session(db, session_id, class_id, writable=True)
        students = db.execute("SELECT s.id,s.embedding FROM students s JOIN enrollments e ON e.student_id=s.id WHERE e.class_id=? AND e.enrolled_on<=?", (class_id,today())).fetchall()
    if not students:
        raise HTTPException(400, "Lớp chưa có học sinh. Hãy thêm học sinh trước.")
    vector = extract_embedding(image.file.read(10 * 1024 * 1024 + 1), require_guide=True)
    matches = [(float(np.dot(vector, np.asarray(json.loads(s["embedding"])))), s["id"]) for s in students]
    similarity, student_id = max(matches)
    if similarity < 0.70:
        return {"status": "unknown", "message": "Chưa nhận ra học sinh trong lớp. Hãy thử ảnh rõ hơn."}
    return record_attendance(student_id, "face", similarity, session_id)


@router.get("/classes/{class_id}/export")
def export(class_id: int, day: date | None = None, session_id: int | None = None):
    selected = day.isoformat() if day else today()
    session_name = 'Tổng hợp ngày (bao gồm dữ liệu cũ)'
    if session_id is not None:
        with database() as db:
            session = require_session(db, session_id, class_id)
            selected, session_name = session['day'], session['name']
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Mã học sinh", "Họ tên", "Ngày", "Trạng thái", "Giờ điểm danh", "Phương thức", "Buổi học"])
    for student in roster(class_id, selected, session_id):
        # Prevent spreadsheet formulas when user-entered text is opened in Excel.
        name = student["name"]
        if name.startswith(("=", "+", "-", "@", "\t", "\r")):
            name = "'" + name
        writer.writerow([student["code"], name, selected, "Có mặt" if student["time"] else "Chưa điểm danh",
                         student["time"] or "", {"face": "Khuôn mặt", "manual": "Thủ công"}.get(student["method"], ""),
                         "'"+session_name if session_name.startswith(('=', '+', '-', '@', '\t', '\r')) else session_name])
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="class-{class_id}-{selected}-session-{session_id or "all"}.csv"'})
