"""Lazy, shared InsightFace model used by detection and recognition."""
from functools import lru_cache
import os
from pathlib import Path


@lru_cache(maxsize=1)
def get_face_app():
    # Import the heavy AI runtime only when recognition is actually requested.
    from insightface.app import FaceAnalysis

    face_app = FaceAnalysis(
        root=os.getenv("INSIGHTFACE_HOME", str(Path(__file__).resolve().parents[1] / ".insightface")),
        providers=["CPUExecutionProvider"],
    )
    face_app.prepare(ctx_id=-1, det_size=(640, 640))
    return face_app


class LazyFaceApp:
    """Keep the existing face_app interface without loading a model on import."""
    def __getattr__(self, name):
        return getattr(get_face_app(), name)


face_app = LazyFaceApp()
