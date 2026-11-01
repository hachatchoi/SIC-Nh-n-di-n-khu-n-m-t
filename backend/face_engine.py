"""Shared InsightFace model used by classroom detection and recognition."""
from pathlib import Path
from insightface.app import FaceAnalysis

face_app = FaceAnalysis(
    root=str(Path(__file__).resolve().parents[1] / ".insightface"),
    providers=["CPUExecutionProvider"],
)
face_app.prepare(ctx_id=-1, det_size=(640, 640))
