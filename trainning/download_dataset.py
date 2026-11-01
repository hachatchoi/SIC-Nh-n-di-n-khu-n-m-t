
from sklearn.datasets import fetch_lfw_people
from pathlib import Path
from PIL import Image
import numpy as np
import csv
import socket
from urllib.error import URLError

# 1. Cấu hình
NUM_STUDENTS = 10
TRAIN_COUNT = 20
VAL_COUNT = 10
TEST_COUNT = 10

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "data"
CACHE = BASE / ".cache"

def to_image(array):
    pixels = np.asarray(array)
    if np.issubdtype(pixels.dtype, np.floating) and pixels.max() <= 1.0:
        pixels = pixels * 255.0
    return np.rint(np.clip(pixels, 0, 255)).astype(np.uint8)
rng = np.random.default_rng(42)

print("Đang tải ảnh khuôn mặt LFW... Lần đầu cần tải bộ dữ liệu, có thể mất vài phút.", flush=True)
print("Thư mục đầu ra:", OUTPUT, flush=True)

# 2. Tải những người có ít nhất 40 ảnh
socket.setdefaulttimeout(60)
try:
    data = fetch_lfw_people(
        data_home=str(CACHE),
        slice_=None,
        min_faces_per_person=TRAIN_COUNT + VAL_COUNT + TEST_COUNT,
        resize=1.0,
        color=True
    )
except (URLError, TimeoutError, ConnectionError) as exc:
    raise SystemExit(
        f"Không tải được LFW: {exc}\n"
        "Kiểm tra kết nối mạng rồi chạy lại. Dữ liệu tải xong được giữ trong "
        f"{CACHE}."
    ) from exc

ids, counts = np.unique(data.target, return_counts=True)
sorted_ids = ids[np.argsort(counts)[::-1]]

# 10 người học sinh + 6 người lạ
if len(sorted_ids) < 16:
    raise ValueError(
        "Dataset không có đủ 16 danh tính "
        "với ít nhất 40 ảnh mỗi người."
    )

students = sorted_ids[:NUM_STUDENTS]
unknown_people = sorted_ids[NUM_STUDENTS:16]

# 3. Chia 40 ảnh cho từng học sinh
mapping = []

for number, person_id in enumerate(students, start=1):
    student_id = f"HS{number:03d}"

    indices = np.where(data.target == person_id)[0]
    selected = rng.choice(indices, size=TRAIN_COUNT + VAL_COUNT + TEST_COUNT, replace=False)

    splits = {
        "train": selected[:TRAIN_COUNT],
        "validation": selected[TRAIN_COUNT:TRAIN_COUNT + VAL_COUNT],
        "test": selected[TRAIN_COUNT + VAL_COUNT:]
    }

    for split, image_ids in splits.items():
        folder = OUTPUT / split / student_id
        folder.mkdir(parents=True, exist_ok=True)

        for i, idx in enumerate(image_ids, start=1):
            image = to_image(data.images[idx])

            Image.fromarray(image).save(
                folder / f"{i:03d}.jpg"
            )

    name = data.target_names[person_id]
    mapping.append([student_id, name])
    print(f"{student_id}: {name} - 20/10/10 ảnh")

# 4. Tạo ảnh Unknown
# Validation và Test dùng những người lạ khác nhau
for split, people in [
    ("validation", unknown_people[:3]),
    ("test", unknown_people[3:6])
]:
    folder = OUTPUT / split / "unknown"
    folder.mkdir(parents=True, exist_ok=True)

    number = 1

    for person_id in people:
        indices = np.where(data.target == person_id)[0]
        selected = rng.choice(indices, size=10, replace=False)

        for idx in selected:
            image = to_image(data.images[idx])

            Image.fromarray(image).save(
                folder / f"{number:03d}.jpg"
            )
            number += 1

    print(f"{split}/unknown: {number - 1} ảnh")

# 5. Lưu bảng mã danh tính
with open(
    BASE / "identity_mapping.csv",
    "w",
    newline="",
    encoding="utf-8"
) as f:
    writer = csv.writer(f)
    writer.writerow(["student_id", "original_name"])
    writer.writerows(mapping)

print("\nHOÀN THÀNH!")
print("Ảnh đã lưu tại:", OUTPUT)
