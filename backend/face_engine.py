import pickle
import cv2
from sklearn.metrics.pairwise import cosine_similarity
from insightface.app import FaceAnalysis



# Load InsightFace Model

face_app = FaceAnalysis()

face_app.prepare(
    ctx_id=-1,
    det_size=(640, 640)
)



# Global Embedding Storage


stored_embeddings = {}



# Load Embeddings


def load_embeddings():

    global stored_embeddings

    try:

        with open("embeddings/encodings.pkl", "rb") as f:

            stored_embeddings = pickle.load(f)

        print("Embeddings Loaded Successfully")

    except FileNotFoundError:

        stored_embeddings = {}

        print("encodings.pkl not found")


# ----------------------------
# Recognize Face
# ----------------------------

def recognize_face(img):

    faces = face_app.get(img)

    if len(faces) == 0:

        return {
            "status": "error",
            "message": "No Face Detected"
        }

    live_embedding = faces[0].embedding

    best_match = None

    best_similarity = 0

    for employee_id, stored_embedding in stored_embeddings.items():

        similarity = cosine_similarity(

            [live_embedding],

            [stored_embedding]

        )[0][0]

        if similarity > best_similarity:

            best_similarity = similarity

            best_match = employee_id

    THRESHOLD = 0.70

    if best_similarity >= THRESHOLD:

        return {

            "status": "success",

            "employee_id": best_match,

            "similarity": float(best_similarity)

        }

    return {

        "status": "unknown",

        "similarity": float(best_similarity)

    }

load_embeddings()