"""Local administrator CLI; passwords are entered privately, never command arguments."""
import argparse
import getpass
import os
import re
import sqlite3
from pathlib import Path
from auth import password_hash
from auth_migration import migrate
from course_migration import migrate_courses


def main():
    parser = argparse.ArgumentParser(description="Quản lý tài khoản giảng viên trên máy chủ")
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--username', required=True)
    create.add_argument('--name', required=True)
    create.add_argument('--role', choices=['teacher','admin'], default='teacher')
    assign = sub.add_parser('assign')
    assign.add_argument('--username', required=True)
    assign.add_argument('--class-id', type=int, required=True)
    reset = sub.add_parser('reset-password')
    reset.add_argument('--username', required=True)
    sub.add_parser('list')
    args = parser.parse_args()
    path = Path(os.getenv('SIC_DATABASE_PATH', Path(__file__).resolve().parent / 'classroom.db'))
    if not path.exists():
        parser.error('Hãy khởi động server một lần để tạo database.')
    migrate(path)
    migrate_courses(path)
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        if args.command == 'list':
            print('GIẢNG VIÊN (id, username, tên):')
            for row in db.execute('SELECT id,username,name,role FROM teachers'): print(row)
            print('LỚP MÔN HỌC (id, tên, môn, tài khoản sở hữu):')
            for row in db.execute('SELECT c.id,c.name,c.subject,t.username FROM classes c LEFT JOIN teachers t ON t.id=c.owner_id'): print(row)
            return
        username = args.username.strip().lower()
        if not re.fullmatch(r'[a-z0-9_.-]{3,60}', username):
            parser.error('Tên đăng nhập: 3–60 ký tự a-z, 0-9, _, . hoặc -')
        if args.command in ('create', 'reset-password'):
            password = getpass.getpass('Mật khẩu mới (6–128 ký tự): ')
            if password != getpass.getpass('Nhập lại mật khẩu: '):
                parser.error('Hai mật khẩu không khớp.')
            encoded = password_hash(password)
            if args.command == 'create':
                name = args.name.strip()
                if not 1 <= len(name) <= 100: parser.error('Tên dài từ 1 đến 100 ký tự.')
                db.execute('INSERT INTO teachers(username,name,password_hash,role) VALUES(?,?,?,?)', (username,name,encoded,args.role))
            else:
                row = db.execute('SELECT id FROM teachers WHERE username=?',(username,)).fetchone()
                if row is None: parser.error('Không có tài khoản này.')
                db.execute('UPDATE teachers SET password_hash=? WHERE id=?', (encoded,row[0]))
                db.execute('DELETE FROM auth_sessions WHERE teacher_id=?', (row[0],))
        elif args.command == 'assign':
            row = db.execute("SELECT id,name FROM teachers WHERE username=? AND active=1 AND role='teacher'",(username,)).fetchone()
            if row is None: parser.error('Không có tài khoản này.')
            result = db.execute('UPDATE classes SET owner_id=?,teacher=? WHERE id=? AND owner_id IS NULL', (row[0],row[1],args.class_id))
            if result.rowcount != 1: parser.error('Lớp không tồn tại hoặc đã có giảng viên sở hữu.')
    print('Đã lưu thành công.')


if __name__ == '__main__':
    main()
