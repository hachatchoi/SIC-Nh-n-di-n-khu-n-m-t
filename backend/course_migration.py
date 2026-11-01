"""Global student identities and explicit course enrollments; preserve history."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


def migrate_courses(path):
    with closing(sqlite3.connect(path)) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='enrollments'").fetchone():
            return
        backup_dir = Path(path).parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        with closing(sqlite3.connect(backup_dir / ('before-course-enrollments-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db'))) as target:
            db.backup(target)
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute('PRAGMA legacy_alter_table=ON')
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute("ALTER TABLE teachers ADD COLUMN role TEXT NOT NULL DEFAULT 'teacher' CHECK(role IN ('teacher','admin'))")
            db.execute('''CREATE TABLE enrollments (
                class_id INTEGER NOT NULL REFERENCES classes(id),
                student_id INTEGER NOT NULL REFERENCES students(id),
                enrolled_on TEXT NOT NULL, PRIMARY KEY(class_id,student_id))''')
            db.execute('INSERT INTO enrollments SELECT class_id,id,created_on FROM students')
            # Old daily records retain the course they originally belonged to.
            db.execute('ALTER TABLE class_attendance ADD COLUMN class_id INTEGER REFERENCES classes(id)')
            db.execute('UPDATE class_attendance SET class_id=(SELECT class_id FROM students WHERE id=student_id)')
            duplicates = db.execute('SELECT code FROM students GROUP BY code HAVING COUNT(*)>1').fetchall()
            if duplicates:
                raise RuntimeError('Duplicate student codes need review before merging identities; original database preserved.')
            db.execute('DROP VIEW IF EXISTS daily_attendance')
            db.execute('''CREATE TABLE students_new (
                id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                embedding TEXT, photo_count INTEGER NOT NULL DEFAULT 0, created_on TEXT NOT NULL)''')
            db.execute('INSERT INTO students_new SELECT id,code,name,embedding,photo_count,created_on FROM students')
            db.execute('DROP TABLE students')
            db.execute('ALTER TABLE students_new RENAME TO students')
            db.execute('''CREATE VIEW daily_attendance AS
                SELECT student_id,class_id,day,MIN(time) AS time,method,similarity FROM (
                    SELECT student_id,class_id,day,time,method,similarity FROM class_attendance
                    UNION ALL
                    SELECT a.student_id,b.class_id,b.day,a.time,a.method,a.similarity
                    FROM session_attendance a JOIN sessions b ON b.id=a.session_id
                ) GROUP BY student_id,class_id,day''')
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('Course migration foreign key check failed')
            db.commit()
        except Exception:
            db.rollback()
            raise
