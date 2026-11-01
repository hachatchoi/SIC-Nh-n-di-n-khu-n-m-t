"""Trich embedding offline; khong import backend hay ghi vao database cua web."""
from pathlib import Path
import csv
import json

import cv2
import numpy as np
from insightface.app import FaceAnalysis


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUTPUT = BASE / "artifacts"
MODEL_ROOT = BASE.parent / ".insightface"
SPLITS = ("train", "validation", "test")
EXTENSIONS = {".jpg", ".jpeg", ".png"}


def main():
    # Kiem tra truoc khi khoi tao model, tranh tu tai model qua mang.
    if not list((MODEL_ROOT / "models" / "buffalo_l").glob("*.onnx")):
        raise SystemExit(f"Khong tim thay model buffalo_l trong {MODEL_ROOT}")
    for split in SPLITS:
        if not (DATA / split).is_dir():
            raise SystemExit(f"Thieu thu muc: {DATA / split}")

    # Dung cung model va kich thuoc detector voi web, chi nap 2 tac vu can thiet.
    app = FaceAnalysis(
        name="buffalo_l",
        root=str(MODEL_ROOT),
        allowed_modules=["detection", "recognition"],
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=-1, det_size=(640, 640))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rejected = []
    summary = {}

    for split in SPLITS:
        vectors, labels, paths = [], [], []
        files = sorted(p for p in (DATA / split).glob("*/*")
                       if p.is_file() and p.suffix.lower() in EXTENSIONS)
        for index, path in enumerate(files, 1):
            relative = path.relative_to(DATA).as_posix()
            # imdecode ho tro ca duong dan co dau; anh dau vao la BGR.
            pixels = np.fromfile(path, dtype=np.uint8)
            image = cv2.imdecode(pixels, cv2.IMREAD_COLOR) if pixels.size else None
            reason = None
            if image is None:
                reason = "cannot_read_image"
            else:
                # InsightFace tu can chinh mat theo landmarks truoc khi trich vector.
                faces = app.get(image)
                if len(faces) != 1:
                    # Khong tu chon mot mat vi co the gan sai nhan danh tinh.
                    reason = f"face_count_{len(faces)}"
                else:
                    vector = np.asarray(faces[0].embedding, dtype=np.float32)
                    norm = np.linalg.norm(vector)
                    if not np.isfinite(vector).all() or not np.isfinite(norm) or norm <= 0:
                        reason = "invalid_embedding"
                    else:
                        vectors.append(vector / norm)
                        labels.append(path.parent.name)
                        paths.append(relative)
            if reason:
                rejected.append([split, relative, reason])
            if index % 25 == 0 or index == len(files):
                print(f"{split}: {index}/{len(files)}, hop le: {len(vectors)}", flush=True)

        # Moi split luu rieng; unknown chi dung validation/test, khong train.
        X = np.stack(vectors) if vectors else np.empty((0, 512), dtype=np.float32)
        np.savez_compressed(
            OUTPUT / f"{split}_embeddings.npz",
            X=X,
            y=np.asarray(labels, dtype=str),
            paths=np.asarray(paths, dtype=str),
        )
        summary[split] = {
            "total": len(files), "accepted": len(vectors),
            "rejected": len(files) - len(vectors),
            "labels": {label: labels.count(label) for label in sorted(set(labels))},
        }

    with (OUTPUT / "rejected_images.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["split", "path", "reason"])
        writer.writerows(rejected)
    report = {"model": "buffalo_l", "det_size": [640, 640],
              "normalized": True, "splits": summary}
    (OUTPUT / "extraction_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Hoan thanh. Ket qua: {OUTPUT}")
    print(f"Anh bi loai: {len(rejected)}. Kiem tra bao cao truoc khi train.")


if __name__ == "__main__":
    main()
