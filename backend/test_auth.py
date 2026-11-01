"""HTTP/ASGI authorization regression tests using a temporary database."""
import asyncio
import json
import io
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException, UploadFile
import auth
import classroom
from app import app


class AuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='test-auth-')
        self.patch = patch.object(classroom, 'DB_PATH', Path(self.tmp.name)/'test.db')
        self.patch.start()
        classroom.init_db()
        with classroom.database() as db:
            for uid in (1,2):
                db.execute('INSERT INTO teachers(id,username,name,password_hash,active) VALUES(?,?,?,?,1)', (uid,f'teacher{uid}',f'Teacher {uid}',auth.password_hash('123456')))
                db.execute('INSERT INTO classes(id,name,owner_id,teacher) VALUES(?,?,?,?)', (uid,f'Course {uid}',uid,f'Teacher {uid}'))
                db.execute('INSERT INTO students(id,code,name,created_on) VALUES(?,?,?,?)', (uid,f'{uid:06}',f'Student {uid}',classroom.today()))
                db.execute('INSERT INTO enrollments VALUES(?,?,?)',(uid,uid,classroom.today()))
                db.execute("INSERT INTO sessions(id,class_id,name,day,starts_at,ends_at) VALUES(?,?,?,?,'00:00:00','23:59:59')",(uid,uid,'Lesson',classroom.today()))
            db.execute("INSERT INTO teachers(id,username,name,password_hash,role) VALUES(3,'teacher3','Admin',?,'admin')",(auth.password_hash('123456'),))
            db.execute("INSERT INTO classes(name) VALUES('Legacy unassigned')")

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    async def request(self, method, path, data=None, cookie=None, origin=None):
        headers = [(b'host',b'testserver'), (b'x-requested-with',b'attendance-web')]
        if cookie: headers.append((b'cookie',cookie.encode()))
        if origin: headers.append((b'origin',origin.encode()))
        body = json.dumps(data).encode() if data is not None else b''
        if data is not None: headers.append((b'content-type',b'application/json'))
        path, _, query = path.partition('?')
        scope = {'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},
                 'http_version':'1.1','method':method,'scheme':'http','path':path,
                 'raw_path':path.encode(),'query_string':query.encode(), 'root_path':'',
                 'headers':headers,'client':('127.0.0.1',1234),'server':('testserver',80)}
        sent = []
        received = False
        async def receive():
            nonlocal received
            if received:
                await asyncio.Event().wait()
            received = True
            return {'type':'http.request','body':body,'more_body':False}
        async def send(message): sent.append(message)
        await asyncio.wait_for(app(scope,receive,send),5)
        start = next(m for m in sent if m['type']=='http.response.start')
        payload = b''.join(m.get('body',b'') for m in sent if m['type']=='http.response.body')
        try: result = json.loads(payload)
        except ValueError: result = payload.decode('utf-8-sig')
        return start['status'], result, dict(start['headers'])

    async def login(self, uid=1):
        status, user, headers = await self.request('POST','/api/auth/login',{'username':f'teacher{uid}','password':'123456'})
        self.assertEqual(status,200,user)
        self.assertIn(b'HttpOnly', headers[b'set-cookie'])
        return headers[b'set-cookie'].decode().split(';')[0]

    async def test_authentication_and_logout(self):
        self.assertEqual((await self.request('GET','/api/classes'))[0],401)
        self.assertEqual((await self.request('POST','/api/auth/login',{'username':'teacher1','password':'wrong'}))[0],401)
        cookie = await self.login()
        self.assertEqual((await self.request('GET','/api/auth/me',cookie=cookie))[1]['id'],1)
        self.assertEqual((await self.request('POST','/api/auth/logout',cookie=cookie))[0],200)
        self.assertEqual((await self.request('GET','/api/classes',cookie=cookie))[0],401)

    async def test_all_course_routes_deny_other_teacher(self):
        cookie = await self.login()
        routes = [('GET','/roster',None),('GET','/export',None),('GET','/sessions',None),
                  ('GET','/schedules',None),('DELETE','/schedules/99',None),
                  ('PATCH','/sessions/2',{'status':'open'}),
                  ('POST','/sessions',{'name':'New','day':classroom.today(),'starts_at':'08:00','ends_at':'09:00'})]
        for method, suffix, body in routes:
            status, result, _ = await self.request(method,'/api/classes/2'+suffix,body,cookie)
            self.assertEqual(status,403 if method in ('POST','DELETE') else 404,(method,suffix,result))
        self.assertEqual((await self.request('GET','/api/classes/1/roster?session_id=2',cookie=cookie))[0],404)
        self.assertEqual((await self.request('GET','/api/classes/1/roster',cookie=cookie))[0],200)

    async def test_lists_dashboard_and_owner_spoofing(self):
        cookie = await self.login()
        classes = (await self.request('GET','/api/classes',cookie=cookie))[1]['classes']
        self.assertEqual([c['id'] for c in classes],[1])
        dashboard = (await self.request('GET','/api/dashboard',cookie=cookie))[1]
        self.assertEqual(dashboard['class_count'],1)
        self.assertEqual(dashboard['total'],1)
        self.assertEqual(dashboard['trend'][-1]['total'],1)
        status, result, _ = await self.request('POST','/api/classes',{'name':'Course 2','teacher':'Forged','owner_id':2},cookie)
        self.assertEqual(status,403,result)
        self.assertEqual((await self.request('GET','/api/students',cookie=cookie))[0],403)
        self.assertEqual((await self.request('POST','/api/classes/1/enrollments',{'student_id':2},cookie))[0],403)
        admin = await self.login(3)
        status, result, _ = await self.request('POST','/api/classes',{'name':'Giải tích 2','owner_id':2},admin)
        self.assertEqual(status,201,result)
        with classroom.database() as db:
            row = db.execute('SELECT owner_id,teacher FROM classes WHERE id=?',(result['id'],)).fetchone()
            self.assertEqual(tuple(row),(2,'Teacher 2'))
        other = await self.login(2)
        self.assertEqual(len((await self.request('GET','/api/classes',cookie=other))[1]['classes']),2)

    async def test_foreign_enrollment_and_recognition_never_run_ai(self):
        token = auth.actor.set({'id':1,'name':'Teacher 1'})
        try:
            with patch.object(classroom, 'extract_embedding') as ai:
                for expected, operation in [
                    (403, lambda: classroom.create_student(2, 'Test', 'NEW', [UploadFile(filename='a.jpg',file=io.BytesIO(b'image'))])),
                    (404, lambda: classroom.recognize(2, UploadFile(filename='a.jpg',file=io.BytesIO(b'image')),session_id=2)),
                ]:
                    with self.assertRaises(HTTPException) as error: operation()
                    self.assertEqual(error.exception.status_code,expected)
                ai.assert_not_called()
        finally:
            auth.actor.reset(token)

    async def test_shared_student_has_separate_attendance_per_course(self):
        admin = await self.login(3)
        self.assertEqual((await self.request('POST','/api/classes/2/enrollments',{'student_id':1},admin))[0],201)
        self.assertEqual((await self.request('POST','/api/classes/2/enrollments',{'student_id':1},admin))[0],409)
        token = auth.actor.set({'id':3,'name':'Admin','role':'admin'})
        try:
            classroom.change_session_status(1,1,classroom.SessionStatus(status='open'))
            classroom.record_attendance(1,'manual',session_id=1)
            self.assertIsNotNone(classroom.roster(1,classroom.today())[0]['time'])
            other = {s['id']:s for s in classroom.roster(2,classroom.today())}
            self.assertIsNone(other[1]['time'])
            self.assertIsNone(other[1]['time'])
            self.assertEqual(classroom.dashboard()['present'],1)
            with classroom.database() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM students WHERE id=1').fetchone()[0],1)
        finally: auth.actor.reset(token)

    async def test_only_admin_schedules_teacher_can_open_attendance(self):
        teacher = await self.login(1)
        admin = await self.login(3)
        lesson = {'name':'Admin lesson','day':classroom.today(),'starts_at':'00:00','ends_at':'23:59:59'}
        self.assertEqual((await self.request('POST','/api/classes/1/sessions',lesson,teacher))[0],403)
        self.assertEqual((await self.request('DELETE','/api/classes/1/schedules/1',cookie=teacher))[0],403)
        status, result, _ = await self.request('POST','/api/classes/1/sessions',lesson,admin)
        self.assertEqual(status,201,result)
        self.assertEqual((await self.request('PATCH',f"/api/classes/1/sessions/{result['id']}",{'status':'open'},teacher))[0],200)
        lesson['weekdays'] = [0,1,2,3,4,5,6]
        lesson['name'] = 'Weekly admin'
        self.assertEqual((await self.request('POST','/api/classes/1/sessions',lesson,teacher))[0],403)
        status, schedule, _ = await self.request('POST','/api/classes/1/sessions',lesson,admin)
        self.assertEqual(status,201,schedule)
        self.assertEqual((await self.request('DELETE',f"/api/classes/1/schedules/{schedule['schedule_id']}",cookie=admin))[0],200)

    async def test_calendar_scope_projection_and_no_duplicate_writes(self):
        from datetime import date, timedelta
        target = date.fromisoformat(classroom.today()) + timedelta(days=7)
        with classroom.database() as db:
            db.execute("INSERT INTO schedules(class_id,name,starts_on,starts_at,ends_at,weekdays) VALUES(1,'Weekly',?,'08:00:00','10:00:00',?)",(classroom.today(),json.dumps([target.weekday()])))
            before=db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
        teacher=await self.login(1)
        status,result,_=await self.request('GET',f'/api/teaching-calendar?day={target}&view=day',cookie=teacher)
        self.assertEqual(status,200,result)
        self.assertEqual(len(result['events']),1)
        self.assertTrue(result['events'][0]['planned'])
        self.assertEqual((await self.request('GET','/api/teaching-calendar?teacher_id=2',cookie=teacher))[0],403)
        with classroom.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],before)
            db.execute("INSERT INTO sessions(class_id,name,day,starts_at,ends_at) VALUES(1,'Weekly',?,'08:00:00','10:00:00')",(str(target),))
        result=(await self.request('GET',f'/api/teaching-calendar?day={target}&view=day',cookie=teacher))[1]
        self.assertEqual(len(result['events']),1)
        self.assertFalse(result['events'][0]['planned'])
        admin=await self.login(3)
        result=(await self.request('GET',f'/api/teaching-calendar?day={classroom.today()}&view=day',cookie=admin))[1]
        self.assertEqual({e['teacher_id'] for e in result['events']},{1,2})

    async def test_bulk_import_preview_confirm_and_permissions(self):
        import zipfile
        import bulk_import as bulk
        token=auth.actor.set({'id':3,'role':'admin','name':'Admin'})
        try:
            with classroom.database() as db:
                db.execute("UPDATE classes SET course_code='TEST',room='201' WHERE id=1")
                db.execute("UPDATE students SET embedding='[1.0,0.0]' WHERE id=1")
                db.execute("INSERT INTO schedules(class_id,name,starts_on,starts_at,ends_at,weekdays) VALUES(1,'Test',?,'08:00:00','10:00:00','[1]')",(classroom.today(),))
            text=','.join(bulk.FIELDS)+'\n000001,Student 1,,TEST,teacher1,3,08:00,10:00,201\n000999,New,,TEST,teacher1,3,08:00,10:00,WRONG\n'
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w') as z: z.writestr('danh_sach.csv',text)
            data.seek(0)
            preview=bulk.preview(UploadFile(filename='test.zip',file=data))
            self.assertEqual([r['status'] for r in preview['rows']],['ready','error'])
            result=bulk.next_row(preview['id'])
            self.assertEqual(result['rows'][0]['status'],'skipped')
            result=bulk.next_row(preview['id'])
            self.assertTrue(result['done'])
            self.assertTrue(bulk.next_row(preview['id'])['done'])
            with classroom.database() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM students').fetchone()[0],2)
        finally: auth.actor.reset(token)
        teacher=await self.login(1)
        self.assertEqual((await self.request('POST','/api/imports/anything/next',cookie=teacher))[0],403)

    async def test_expiry_origin_and_rate_limit(self):
        cookie = await self.login()
        self.assertEqual((await self.request('POST','/api/classes',{'name':'Bad'},cookie,'https://other.example'))[0],403)
        with classroom.database() as db: db.execute('UPDATE auth_sessions SET expires_at=?',(time.time()-1,))
        self.assertEqual((await self.request('GET','/api/classes',cookie=cookie))[0],401)
        for _ in range(10):
            self.assertEqual((await self.request('POST','/api/auth/login',{'username':'teacher1','password':'wrong'}))[0],401)
        self.assertEqual((await self.request('POST','/api/auth/login',{'username':'teacher1','password':'123456'}))[0],429)


if __name__ == '__main__': unittest.main()
