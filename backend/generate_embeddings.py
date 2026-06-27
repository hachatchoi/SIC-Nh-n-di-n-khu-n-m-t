import os
import cv2
import pickle

from insightface.app import FaceAnalysis


# -----------------------------
# Load InsightFace
# -----------------------------

face_app = FaceAnalysis()

face_app.prepare(
    ctx_id=-1,
    det_size=(640, 640)
)


# -----------------------------
# Paths
# -----------------------------

DATASET_DIR = "dataset"
EMBEDDING_DIR = "embeddings"

os.makedirs(
    EMBEDDING_DIR,
    exist_ok=True
)

EMBEDDING_FILE = os.path.join(
    EMBEDDING_DIR,
    "encodings.pkl"
)


# -----------------------------
# Generate Embeddings
# -----------------------------

def generate_embeddings():

    stored_embeddings = {}

    # Dataset Exists?

    if not os.path.exists(DATASET_DIR):

        return {

            "status": "error",

            "message": "Dataset folder not found"

        }

    employees = os.listdir(DATASET_DIR)

    if len(employees) == 0:

        return {

            "status": "error",

            "message": "No Employees Found"

        }

    # Process Every Employee

    for employee_id in employees:

        employee_folder = os.path.join(
            DATASET_DIR,
            employee_id
        )

        embeddings = []

        print(f"\nProcessing : {employee_id}")

        for image_name in os.listdir(employee_folder):

            image_path = os.path.join(
                employee_folder,
                image_name
            )

            img = cv2.imread(image_path)

            if img is None:

                print(f"Cannot Read : {image_name}")

                continue

            faces = face_app.get(img)

            if len(faces) == 0:

                print(f"No Face : {image_name}")

                continue

            embedding = faces[0].embedding

            embeddings.append(
                embedding
            )

            print(f"Processed : {image_name}")

        # Skip if no embeddings

        if len(embeddings) == 0:

            print(f"No Valid Images : {employee_id}")

            continue

        # Average Embedding

        avg_embedding = sum(embeddings) / len(embeddings)

        stored_embeddings[employee_id] = avg_embedding

    # Save Encodings

    with open(EMBEDDING_FILE, "wb") as f:

        pickle.dump(
            stored_embeddings,
            f
        )

    print("\nEmbeddings Saved Successfully")

    print(f"Employees : {len(stored_embeddings)}")

    return {

        "status": "success",

        "message": "Embeddings Generated Successfully",

        "employees": len(stored_embeddings)

    }


# -----------------------------
# Run Directly
# -----------------------------

if __name__ == "__main__":

    result = generate_embeddings()

    print(result)