"""Admin ZIP import: bounded preview, explicit confirmation, one row per request."""
import base64
import csv
import io
import json
import re
import secrets
import time
import zipfile
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from auth import require_teacher, require_admin
import classroom as c
from student_codes import normalize_student_code

router = APIRouter(prefix='/api/imports', dependencies=[Depends(require_teacher)])
FIELDS = ['ma_sinh_vien','ho_ten','anh','ma_lop_mon_hoc','tai_khoan_giang_vien','thu','gio_bat_dau','gio_ket_thuc','phong']


def setup(db):
    db.execute('''CREATE TABLE IF NOT EXISTS import_jobs (
        id TEXT PRIMARY KEY, owner INTEGER NOT NULL, expires REAL NOT NULL,
        rows TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT 0)''')
    db.execute('DELETE FROM import_jobs WHERE expires<?', (time.time(),))


def validate(db, row):
    code, name = normalize_student_code(row['ma_sinh_vien']), row['ho_ten']
    row['ma_sinh_vien'] = code
    if not 1 <= len(name) <= 100:
        raise ValueError('Tên hoặc mã sinh viên không hợp lệ.')
    matches = db.execute('''SELECT c.* FROM classes c JOIN teachers t ON t.id=c.owner_id
        WHERE c.course_code=? AND t.username=? AND t.active=1 AND t.role='teacher' AND c.room=?''',
        (row['ma_lop_mon_hoc'],row['tai_khoan_giang_vien'].lower(),row['phong'])).fetchall()
    if len(matches)!=1: raise ValueError('Mã lớp, giảng viên hoặc phòng không khớp duy nhất.')
    course=matches[0]
    weekday = 6 if row['thu'].upper()=='CN' else int(row['thu'])-2
    if weekday not in range(7): raise ValueError('Thứ phải là 2–7 hoặc CN.')
    start,end = row['gio_bat_dau'],row['gio_ket_thuc']
    if not all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',x) for x in (start,end)) or start>=end:
        raise ValueError('Giờ phải có dạng HH:MM, giờ kết thúc sau bắt đầu.')
    schedules=db.execute('SELECT * FROM schedules WHERE class_id=? AND active=1 AND (ends_on IS NULL OR ends_on>=?)',(course['id'],c.today())).fetchall()
    if not any(weekday in json.loads(s['weekdays']) and s['starts_at'][:5]==start and s['ends_at'][:5]==end for s in schedules):
        raise ValueError('Ca học không khớp lịch cố định đang áp dụng của lớp.')
    student=db.execute('SELECT * FROM students WHERE code=?',(code,)).fetchone()
    if student and student['name'].strip().casefold()!=name.casefold():
        raise ValueError('Mã đã tồn tại nhưng khác họ tên; cần kiểm tra thủ công.')
    if student and not student['embedding']: raise ValueError('Hồ sơ cũ chưa có khuôn mặt.')
    return course,student


def public(job_id, rows, cursor=0):
    return {'id':job_id,'cursor':cursor,'total':len(rows),'done':cursor>=len(rows),
            'rows':[{k:v for k,v in r.items() if k!='image'} for r in rows]}


@router.post('/preview')
def preview(file: UploadFile = File(...)):
    user=require_admin()
    raw=file.file.read(50*1024*1024+1)
    if len(raw)>50*1024*1024: raise HTTPException(400,'ZIP tối đa 50 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos=archive.infolist()
            if len(infos)>1000 or sum(i.file_size for i in infos)>100*1024*1024:
                raise ValueError('ZIP tối đa 1000 mục và 100 MB sau giải nén.')
            names=[i.filename for i in infos]
            if len(names)!=len(set(names)): raise ValueError('ZIP có đường dẫn trùng.')
            if any('\\' in n or PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts for n in names):
                raise ValueError('Đường dẫn ZIP không hợp lệ.')
            if 'danh_sach.csv' not in names: raise ValueError('Cần danh_sach.csv ở gốc ZIP.')
            if archive.getinfo('danh_sach.csv').file_size>1024*1024: raise ValueError('CSV quá lớn.')
            reader=csv.DictReader(io.StringIO(archive.read('danh_sach.csv').decode('utf-8-sig')))
            if reader.fieldnames!=FIELDS: raise ValueError('Tên hoặc thứ tự cột CSV không đúng mẫu.')
            rows=[]; seen=set()
            with c.database() as db:
                setup(db)
                if db.execute('SELECT COUNT(*) FROM import_jobs WHERE owner=?',(user['id'],)).fetchone()[0]>=3:
                    raise ValueError('Tối đa 3 lượt xem trước trong 30 phút. Hoàn tất lượt cũ hoặc chờ hết hạn.')
                for number, data in enumerate(reader,2):
                    if len(rows)>=200: raise ValueError('Mỗi ZIP tối đa 200 dòng.')
                    item={'line':number,'data':{},'status':'ready','message':'Sẵn sàng'}
                    try:
                        if None in data or any(v is None for v in data.values()): raise ValueError('Sai số cột.')
                        data={k:v.strip() for k,v in data.items()}; item['data']=data
                        course,student=validate(db,data)
                        key=(data['ma_sinh_vien'].upper(),course['id'])
                        if key in seen: raise ValueError('Trùng sinh viên/lớp trong CSV; mỗi lớp chỉ cần một dòng.')
                        seen.add(key)
                        if not student:
                            name=data['anh']
                            if name not in names or not 0<archive.getinfo(name).file_size<=10*1024*1024:
                                raise ValueError('Thiếu ảnh hoặc ảnh vượt 10 MB.')
                            image=archive.read(name)
                            import cv2
                            import numpy as np
                            decoded=cv2.imdecode(np.frombuffer(image,np.uint8),cv2.IMREAD_COLOR)
                            if decoded is None: raise ValueError('Không đọc được ảnh.')
                            item['image']=base64.b64encode(image).decode()
                            item['message']='Tạo hồ sơ và ghi danh; khuôn mặt sẽ kiểm tra khi nhập.'
                        else: item['message']='Dùng hồ sơ có sẵn, chỉ ghi danh.'
                    except (ValueError,KeyError) as error:
                        item['status']='error'; item['message']=str(error)
                    rows.append(item)
                if not rows: raise ValueError('CSV không có sinh viên.')
                job=secrets.token_urlsafe(24)
                db.execute('INSERT INTO import_jobs(id,owner,expires,rows) VALUES(?,?,?,?)',
                           (job,user['id'],time.time()+1800,json.dumps(rows,ensure_ascii=False)))
            return public(job,rows)
    except (ValueError,zipfile.BadZipFile,UnicodeError,RuntimeError,NotImplementedError) as error:
        raise HTTPException(400,str(error))


@router.post('/{job_id}/next')
def next_row(job_id: str):
    user=require_admin()
    with c.database() as db:
        db.execute('BEGIN IMMEDIATE')
        setup(db)
        job=db.execute('SELECT * FROM import_jobs WHERE id=? AND owner=?',(job_id,user['id'])).fetchone()
        if not job: raise HTTPException(404,'Lượt nhập không tồn tại hoặc hết hạn; tải lại ZIP.')
        rows=json.loads(job['rows']); index=job['cursor']
        if index>=len(rows): return public(job_id,rows,index)
        item=rows[index]
        if item['status']=='ready':
            db.execute('SAVEPOINT import_row')
            try:
                course,student=validate(db,item['data'])
                if student is None:
                    vector=c.extract_embedding(base64.b64decode(item.get('image','')),require_guide=False)
                    if not __import__('numpy').isfinite(vector).all(): raise ValueError('Embedding không hợp lệ.')
                    sid=db.execute('INSERT INTO students(code,name,embedding,photo_count,created_on) VALUES(?,?,?,?,?)',
                        (item['data']['ma_sinh_vien'].upper(),item['data']['ho_ten'],json.dumps(vector.tolist()),1,c.today())).lastrowid
                else: sid=student['id']
                result=db.execute('INSERT OR IGNORE INTO enrollments VALUES(?,?,?)',(course['id'],sid,c.today()))
                item['status']='success' if result.rowcount else 'skipped'
                item['message']='Đã ghi danh' if result.rowcount else 'Đã có trong lớp, bỏ qua'
                db.execute('RELEASE import_row')
            except (ValueError,HTTPException) as error:
                db.execute('ROLLBACK TO import_row'); db.execute('RELEASE import_row')
                item['status']='error'; item['message']=str(error.detail if isinstance(error,HTTPException) else error)
        item.pop('image',None)
        db.execute('UPDATE import_jobs SET rows=?,cursor=?,expires=? WHERE id=?',
                   (json.dumps(rows,ensure_ascii=False),index+1,time.time()+1800,job_id))
        return public(job_id,rows,index+1)
