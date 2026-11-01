"""Regression checks with an isolated database and synthetic face vectors."""
import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
import cv2
from fastapi import HTTPException, UploadFile
import auth
import classroom as app


class ClassroomTests(unittest.TestCase):
    def setUp(self):
        embedding_mock = patch.object(app, 'embed_face', side_effect=lambda image, face: face.embedding)
        self.embedding_mock = embedding_mock.start()
        self.addCleanup(embedding_mock.stop)
        self.directory = tempfile.TemporaryDirectory(prefix="test-classroom-", dir=Path(__file__).resolve().parent)
        self.old_path = app.DB_PATH
        app.DB_PATH = Path(self.directory.name) / "test.db"
        app.init_db()
        with app.database() as db:
            db.execute("INSERT INTO teachers(id,username,name,password_hash) VALUES(1,'test','Test','unused')")
        identity = patch.object(app, 'current_teacher', return_value={'id':1, 'name':'Test', 'role':'admin'})
        admin_identity = patch.object(auth, 'current_teacher', return_value={'id':1,'name':'Test','role':'admin'})
        admin_identity.start()
        self.addCleanup(admin_identity.stop)
        identity.start()
        self.addCleanup(identity.stop)
        clock = patch.object(app, 'datetime', wraps=datetime)
        clock_mock = clock.start()
        clock_mock.now.return_value = datetime(2026,10,28,12,0,tzinfo=app.VN_TIME)
        self.addCleanup(clock.stop)
        self.class_id = app.create_class(app.ClassInput(owner_id=1, name="10A1"))["id"]
        self.session_id = app.create_session(self.class_id, app.SessionInput(name="Buổi 1",day=app.today(),starts_at="00:00",ends_at="23:59:59"))["id"]
        app.change_session_status(self.class_id, self.session_id, app.SessionStatus(status="open"))

    def tearDown(self):
        app.DB_PATH = self.old_path
        assert Path(self.directory.name).resolve().parent == Path(__file__).resolve().parent
        self.directory.cleanup()

    def add_student(self, code="000001", name="Học sinh kiểm thử"):
        with patch.object(app, 'extract_embedding', return_value=np.array([1., 0.])):
            return app.create_student(self.class_id, name, code,
                [UploadFile(filename="test.jpg", file=io.BytesIO(b"test"))])["id"]

    def test_duplicate_class_and_student(self):
        with self.assertRaises(HTTPException) as error:
            app.create_class(app.ClassInput(owner_id=1, name="10A1"))
        self.assertEqual(error.exception.status_code, 409)

    def test_recurring_schedule_dates_persistence_and_stop(self):
        result = app.create_session(self.class_id, app.SessionInput(name='Weekly',day='2026-10-28',starts_at='07:00',ends_at='11:00',weekdays=[2,4],ends_on='2026-11-04'))
        sid = result['schedule_id']
        first = [s for s in app.list_sessions(self.class_id)['sessions'] if s['name']=='Weekly']
        self.assertEqual(len(first),1)
        self.assertEqual(first[0]['status'],'closed')
        app.init_db()
        self.assertEqual(app.list_schedules(self.class_id)['schedules'][0]['id'],sid)
        self.assertEqual([s for s in app.list_sessions(self.class_id)['sessions'] if s['name']=='Weekly'][0]['id'],first[0]['id'])
        with app.database() as db:
            app.materialize_schedules(db,self.class_id,'2026-10-29')
            app.materialize_schedules(db,self.class_id,'2026-10-30')
            app.materialize_schedules(db,self.class_id,'2026-10-30')
            app.materialize_schedules(db,self.class_id,'2026-11-06')
            rows=db.execute("SELECT day FROM sessions WHERE name='Weekly' ORDER BY day").fetchall()
            self.assertEqual([r['day'] for r in rows],['2026-10-28','2026-10-30'])
        other=app.create_class(app.ClassInput(owner_id=1, name='Other'))['id']
        with self.assertRaises(HTTPException): app.stop_schedule(other,sid)
        app.stop_schedule(self.class_id,sid)
        self.assertEqual(app.list_schedules(self.class_id)['schedules'],[])
        with app.database() as db:
            app.materialize_schedules(db,self.class_id,'2026-11-04')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions WHERE name='Weekly'").fetchone()[0],2)

    def test_recurring_schedule_validation(self):
        for weekdays,end in [([7],None),([1],'2026-10-27')]:
            with self.assertRaises(HTTPException):
                app.create_session(self.class_id,app.SessionInput(name='Bad',day='2026-10-28',starts_at='07:00',ends_at='11:00',weekdays=weekdays,ends_on=end))

    def test_duplicate_student(self):

        self.add_student()
        with self.assertRaises(HTTPException) as error:
            self.add_student()
        self.assertEqual(error.exception.status_code, 409)

    def test_two_sessions_same_day_and_legacy_history(self):
        student_id = self.add_student()
        with app.database() as db:
            db.execute('INSERT INTO class_attendance(student_id,day,time,method,class_id) VALUES(?,?,?,?,?)',
                       (student_id,app.today(),'06:00:00','manual',self.class_id))
        other = app.create_session(self.class_id,app.SessionInput(name='Buổi 2',day=app.today(),starts_at='00:00',ends_at='23:59:59'))['id']
        app.change_session_status(self.class_id,other,app.SessionStatus(status='open'))
        first = app.record_attendance(student_id,'face',.9,self.session_id)
        second = app.record_attendance(student_id,'face',.9,other)
        duplicate = app.record_attendance(student_id,'face',.8,other)
        self.assertEqual([first['status'],second['status'],duplicate['status']],['success','success','duplicate'])
        self.assertEqual(app.dashboard()['present'],1)
        self.assertEqual(app.roster(self.class_id,app.today())[0]['time'],'06:00:00')
        self.assertEqual(app.roster(self.class_id,app.today(),other)[0]['time'],'12:00:00')
        output=app.export(self.class_id,session_id=other).body.decode('utf-8-sig')
        self.assertIn('Buổi 2',output)
        self.assertIn('12:00:00',output)
        app.init_db()
        with app.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM class_attendance').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM session_attendance').fetchone()[0],2)

    def test_session_guards_before_ai_and_after_close_during_ai(self):
        student = self.add_student()
        upload=lambda: UploadFile(filename='test.jpg',file=io.BytesIO(b'image'))
        app.change_session_status(self.class_id,self.session_id,app.SessionStatus(status='closed'))
        with patch.object(app,'extract_embedding') as extract:
            with self.assertRaises(HTTPException): app.recognize(self.class_id,upload(),self.session_id)
            with self.assertRaises(HTTPException): app.recognize(self.class_id,upload())
            extract.assert_not_called()
        app.change_session_status(self.class_id,self.session_id,app.SessionStatus(status='open'))
        def close_while_processing(*args,**kwargs):
            app.change_session_status(self.class_id,self.session_id,app.SessionStatus(status='closed'))
            return np.array([1.,0.])
        with patch.object(app,'extract_embedding',side_effect=close_while_processing):
            with self.assertRaises(HTTPException): app.recognize(self.class_id,upload(),self.session_id)
        self.assertIsNone(app.roster(self.class_id,app.today(),self.session_id)[0]['time'])

    def test_sessions_validate_time_and_class_ownership(self):
        with self.assertRaises(HTTPException):
            app.create_session(self.class_id,app.SessionInput(name='Invalid',day=app.today(),starts_at='14:00',ends_at='08:00'))
        other = app.create_class(app.ClassInput(owner_id=1, name='Other'))['id']
        with self.assertRaises(HTTPException): app.get_roster(other,session_id=self.session_id)
        with self.assertRaises(HTTPException): app.change_session_status(other,self.session_id,app.SessionStatus(status='closed'))
        with self.assertRaises(HTTPException): app.export(other,session_id=self.session_id)
        student = self.add_student()
        for day,start,end in [('2026-10-29','00:00','23:59'),(app.today(),'13:00','14:00'),(app.today(),'10:00','12:00')]:
            session = app.create_session(self.class_id,app.SessionInput(name=f'{day}-{start}',day=day,starts_at=start,ends_at=end))['id']
            app.change_session_status(self.class_id,session,app.SessionStatus(status='open'))
            with self.assertRaises(HTTPException): app.record_attendance(student,'face',session_id=session)

    def test_atomic_session_attendance(self):
        student_id = self.add_student()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: app.record_attendance(student_id, "manual", session_id=self.session_id), range(8)))
        self.assertEqual(sum(r['status'] == 'success' for r in results), 1)
        self.assertEqual(len(app.roster(self.class_id, app.today())), 1)
        self.assertIsNotNone(app.roster(self.class_id, app.today())[0]['time'])
        self.assertEqual(app.roster(self.class_id, '2000-01-01'), [])

    def test_recognition_and_class_isolation(self):
        student_id = self.add_student()
        image = lambda: UploadFile(filename="test.jpg", file=io.BytesIO(b"test"))
        with patch.object(app, 'extract_embedding', return_value=np.array([0., 1.])):
            self.assertEqual(app.recognize(self.class_id, image(), session_id=self.session_id)['status'], 'unknown')
        with patch.object(app, 'extract_embedding', return_value=np.array([1., 0.])):
            result = app.recognize(self.class_id, image(), session_id=self.session_id)
        self.assertEqual(result['student']['id'], student_id)
        other = app.create_class(app.ClassInput(owner_id=1, name="10A2"))['id']
        with self.assertRaises(HTTPException):
            app.recognize(other, image(), session_id=self.session_id)

    def test_reject_invalid_photo_without_creating_student(self):
        with self.assertRaises(HTTPException):
            app.create_student(self.class_id, 'Test', '000001',
                [UploadFile(filename="bad.jpg", file=io.BytesIO(b"invalid image"))])
        self.assertEqual(app.roster(self.class_id, app.today()), [])

    def test_camera_enrollment_ignores_bystanders_but_upload_remains_strict(self):
        raw = cv2.imencode('.jpg', np.zeros((200, 200, 3), dtype=np.uint8))[1].tobytes()
        inside = SimpleNamespace(bbox=np.array([80,70,120,130]), embedding=np.array([1.,0.]))
        outside = SimpleNamespace(bbox=np.array([0,50,35,110]), embedding=np.array([0.,1.]))
        photo = lambda: [UploadFile(filename='camera.jpg', file=io.BytesIO(raw))]
        with patch.object(app, 'detect_faces', return_value=[outside,inside]):
            result = app.create_student(self.class_id, 'Inside', '000011', photo(), use_guide=True)
            self.assertIsNotNone(result['id'])
            self.assertEqual(self.embedding_mock.call_count, 1)
            self.assertIs(self.embedding_mock.call_args.args[1], inside)
            with self.assertRaises(HTTPException):
                app.create_student(self.class_id, 'Upload', '000012', photo(), use_guide=False)
        for faces in ([outside], [inside,inside]):
            with patch.object(app, 'detect_faces', return_value=faces):
                with self.assertRaises(HTTPException):
                    app.create_student(self.class_id, 'Invalid', '000013', photo(), use_guide=True)
        self.assertEqual(len(app.roster(self.class_id, app.today())), 1)

    def test_export_escaping_and_date_filter(self):
        self.add_student(name='=1+1')
        output = app.export(self.class_id, date.fromisoformat(app.today())).body.decode('utf-8-sig')
        self.assertIn("'=1+1", output)
        self.assertIn('Chưa điểm danh', output)
        self.assertNotIn('000001', app.export(self.class_id, date(2000,1,1)).body.decode())

    def test_guide_rejects_outside_and_partial_faces_without_attendance(self):
        self.add_student()
        raw = cv2.imencode('.jpg', np.zeros((200, 200, 3), dtype=np.uint8))[1].tobytes()
        for bbox in ([5, 60, 45, 120], [100, 60, 160, 140], [30, 20, 170, 180]):
            face = SimpleNamespace(bbox=np.array(bbox), embedding=np.array([1., 0.]))
            with self.subTest(bbox=bbox), patch.object(app, 'detect_faces', return_value=[face]):
                with self.assertRaises(HTTPException) as error:
                    app.recognize(self.class_id, UploadFile(filename='face.jpg', file=io.BytesIO(raw)), session_id=self.session_id)
                self.assertEqual(error.exception.status_code, 400)
                self.assertIn('ngoài vòng', error.exception.detail)
                self.assertIsNone(app.roster(self.class_id, app.today())[0]['time'])
                # Enrollment is intentionally independent of the attendance guide.
                np.testing.assert_allclose(app.extract_embedding(raw), [1., 0.])

    def test_dashboard_counts_classes_and_daily_history(self):
        with patch.object(app, 'today', return_value='2026-10-27'):
            empty = app.dashboard()
            self.assertEqual((empty['total'], empty['present'], empty['rate']), (0, 0, 0))
            student = self.add_student()
            app.create_class(app.ClassInput(owner_id=1, name='Empty class'))
            with app.database() as db:
                db.execute("INSERT INTO class_attendance(student_id,day,time,method,class_id) VALUES(?,?,?,?,?)",
                           (student, '2026-10-27', '08:00:00', 'face',self.class_id))
                db.execute("INSERT INTO class_attendance(student_id,day,time,method,class_id) VALUES(?,?,?,?,?)",
                           (student, '2026-10-28', '08:00:00', 'face',self.class_id))
            result = app.dashboard()
            self.assertEqual((result['class_count'], result['total'], result['present'], result['pending'], result['rate']), (2,1,1,0,100))
            self.assertEqual(len(result['trend']), 7)
            self.assertEqual(result['trend'][0], {'day':'2026-10-21','total':0,'present':0})
            self.assertEqual(result['trend'][-1], {'day':'2026-10-27','total':1,'present':1})
            self.assertEqual(len(result['recent']), 1)
            self.assertEqual(sum(c['present'] for c in result['classes']), 1)

    def test_oval_does_not_require_empty_box_corners_inside(self):
        self.assertTrue(app.face_inside_guide([50, 30, 150, 170], 200, 200))
        self.assertFalse(app.face_inside_guide([0, 30, 100, 170], 200, 200))

    def test_guide_accepts_centered_face_after_resize(self):
        self.add_student()
        raw = cv2.imencode('.jpg', np.zeros((2000, 2000, 3), dtype=np.uint8))[1].tobytes()
        face = SimpleNamespace(bbox=np.array([640, 560, 960, 1040]), embedding=np.array([1., 0.]))
        with patch.object(app, 'detect_faces', return_value=[face]) as detect:
            result = app.recognize(self.class_id, UploadFile(filename='face.jpg', file=io.BytesIO(raw)), session_id=self.session_id)
        self.assertEqual(detect.call_args.args[0].shape[:2], (1600, 1600))
        self.assertEqual(result['status'], 'success')


    def test_only_inside_face_is_recognized_even_with_bystanders(self):
        student_id = self.add_student()
        raw = cv2.imencode('.jpg', np.zeros((200, 200, 3), dtype=np.uint8))[1].tobytes()
        inside = SimpleNamespace(bbox=np.array([80, 70, 120, 130]), embedding=np.array([1., 0.]))
        outside = SimpleNamespace(bbox=np.array([0, 50, 35, 110]), embedding=np.array([0., 1.]))
        for faces in ([outside, inside], [inside, outside]):
            with patch.object(app, 'detect_faces', return_value=faces):
                result = app.recognize(self.class_id, UploadFile(filename='face.jpg', file=io.BytesIO(raw)), session_id=self.session_id)
                self.assertEqual(result['student']['id'], student_id)
                self.assertIn(result['status'], ('success', 'duplicate'))
                with self.assertRaises(HTTPException):
                    app.extract_embedding(raw)
        # A known bystander must not be used when the person inside is unknown.
        inside.embedding, outside.embedding = outside.embedding, inside.embedding
        with patch.object(app, 'detect_faces', return_value=[outside, inside]):
            result = app.recognize(self.class_id, UploadFile(filename='face.jpg', file=io.BytesIO(raw)), session_id=self.session_id)
            self.assertEqual(result['status'], 'unknown')

    def test_zero_or_multiple_inside_faces_do_not_mark_attendance(self):
        self.add_student()
        raw = cv2.imencode('.jpg', np.zeros((200, 200, 3), dtype=np.uint8))[1].tobytes()
        def face(box):
            return SimpleNamespace(bbox=np.array(box), embedding=np.array([1., 0.]))
        for faces in ([], [face([0, 40, 30, 90]), face([170, 40, 200, 90])],
                      [face([70, 80, 90, 120]), face([110, 80, 130, 120])]):
            with self.subTest(count=len(faces)), patch.object(app, 'detect_faces', return_value=faces):
                with self.assertRaises(HTTPException) as error:
                    app.recognize(self.class_id, UploadFile(filename='face.jpg', file=io.BytesIO(raw)), session_id=self.session_id)
                self.assertEqual(error.exception.status_code, 400)
                self.assertIsNone(app.roster(self.class_id, app.today())[0]['time'])
                self.embedding_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
