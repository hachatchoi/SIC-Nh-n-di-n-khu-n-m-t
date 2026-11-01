"""Preserve IDs/history while introducing course ownership and scoped codes."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


def migrate(path):
    db = sqlite3.connect(path)
    try:
        columns = {r[1] for r in db.execute('PRAGMA table_info(classes)')}
        if 'owner_id' not in columns:
            backup_dir = Path(path).parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            backup = backup_dir / ('before-teacher-auth-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.db')
            with closing(sqlite3.connect(backup)) as target:
                db.backup(target)
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('PRAGMA legacy_alter_table=ON')
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE classes_new (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                subject TEXT NOT NULL DEFAULT '', teacher TEXT NOT NULL DEFAULT '',
                owner_id INTEGER REFERENCES teachers(id), UNIQUE(owner_id,name))''')
            db.execute('INSERT INTO classes_new(id,name,subject,teacher) SELECT id,name,subject,teacher FROM classes')
            db.execute('DROP TABLE classes')
            db.execute('ALTER TABLE classes_new RENAME TO classes')
            db.execute('''CREATE TABLE students_new (
                id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id),
                code TEXT NOT NULL, name TEXT NOT NULL, embedding TEXT,
                photo_count INTEGER NOT NULL DEFAULT 0, created_on TEXT NOT NULL,
                UNIQUE(class_id,code))''')
            db.execute('INSERT INTO students_new SELECT * FROM students')
            db.execute('DROP TABLE students')
            db.execute('ALTER TABLE students_new RENAME TO students')
            db.commit()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY, teacher_id INTEGER NOT NULL REFERENCES teachers(id), expires_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS login_attempts (
                key TEXT PRIMARY KEY, count INTEGER NOT NULL, started_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS classes_owner ON classes(owner_id);
        ''')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Foreign key check failed after auth migration')
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
