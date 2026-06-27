import pickle
import cv2
from insightface.app import FaceAnalysis
from sklearn.metrics.pairwise import cosine_similarity


# Load Stored Embeddings

with open("embeddings/encodings.pkl", "rb") as f:
    stored_embeddings = pickle.load(f)


# Load InsightFace

face_app = FaceAnalysis()

face_app.prepare(  ctx_id=-1,  det_size=(640, 640))


# Test Image

image_path = "dataset/EMP003/test.jpg"

img = cv2.imread(image_path)

if img is None:
    print("Image Not Found")
    exit()


# Extract Face

faces = face_app.get(img)

if len(faces) == 0:
    print("No Face Detected")
    exit()


# Live Embedding

live_embedding = faces[0].embedding


# Recognition Logic

best_match = None
best_similarity = 0


for employee_id, stored_embedding in stored_embeddings.items():

    similarity = cosine_similarity( [live_embedding], [stored_embedding])[0][0]

    print(  f"{employee_id} -> {similarity:.4f}" )

    if similarity > best_similarity:

        best_similarity = similarity
        best_match = employee_id


# Threshold

THRESHOLD = 0.70

print("\n-------------------")

if best_similarity > THRESHOLD:

    print( f"Recognized: {best_match}")

    print( f"Similarity: {best_similarity:.4f}")

else:

    print("Unknown Person")

    print( f"Highest Similarity: {best_similarity:.4f}")