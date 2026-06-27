import cv2
import os

DATASET_DIR = "dataset"


def collect_dataset(employee_id):

    employee_folder = os.path.join(DATASET_DIR, employee_id)
    os.makedirs(employee_folder, exist_ok=True)

    cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Camera Open Failed")
        return

    image_count = 0
    MAX_IMAGES = 20

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        cv2.putText(
            frame,
            f"Images : {image_count}/{MAX_IMAGES}",
            (20,40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0,255,0),
            2
        )

        cv2.putText(
            frame,
            "SPACE = Capture",
            (20,80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255,255,255),
            2
        )

        cv2.imshow("Collect Dataset", frame)

        key = cv2.waitKey(1) & 0xFF

        # SPACE
        if key == 32:

            image_count += 1

            image_path = os.path.join(
                employee_folder,
                f"{image_count}.jpg"
            )

            cv2.imwrite(image_path, frame)

            print(f"Saved {image_count}")

        # Quit
        elif key == ord("q"):
            break

        if image_count >= MAX_IMAGES:
            break

    cap.release()
    cv2.destroyAllWindows()

    print("Dataset Collection Completed")


