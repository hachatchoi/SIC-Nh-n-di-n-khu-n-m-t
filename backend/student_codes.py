"""Canonical six-digit student identifiers, stored as text."""
import re

def normalize_student_code(value):
    value = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,6}", value):
        raise ValueError("MSSV chỉ gồm 1–6 chữ số; hệ thống tự thêm số 0 để đủ 6 chữ số.")
    return value.zfill(6)
