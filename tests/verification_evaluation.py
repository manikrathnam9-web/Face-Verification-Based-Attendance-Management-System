import os
import sys
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.face_engine import face_engine

# ==================================================
# CONFIGURATION
# ==================================================

STUDENT_ID = "DS001"
ENROLLED_EMBEDDING_PATH = os.path.join(PROJECT_ROOT, "data", "embeddings", f"{STUDENT_ID}.npy")

# Genuine images = same person as DS001
GENUINE_IMAGES = [
    os.path.join(PROJECT_ROOT, "data", "test_images", "test_same_person.jpeg"),
    os.path.join(PROJECT_ROOT, "data", "test_images", "test_same_person_02.jpeg"),
    os.path.join(PROJECT_ROOT, "data", "test_images", "test_same_person_03.jpeg"),
    os.path.join(PROJECT_ROOT, "data", "test_images", "test_same_person_04.jpeg"),
]

# Impostor images = different person
IMPOSTOR_IMAGES = [
    os.path.join(PROJECT_ROOT, "data", "test_images", "test_different_person.jpeg"),
]


def run_verification_evaluation():
    print("Loading InsightFace model...")
    face_engine.initialize()
    print("Model loaded successfully.")

    if not os.path.exists(ENROLLED_EMBEDDING_PATH):
        print("ERROR: Enrolled embedding not found:", ENROLLED_EMBEDDING_PATH)
        return

    enrolled_embedding = np.load(ENROLLED_EMBEDDING_PATH)
    print("Enrolled embedding:", enrolled_embedding.shape)

    # --------------------------------------------------
    # GENUINE TESTS
    # --------------------------------------------------
    print("\n========================================")
    print("GENUINE VERIFICATION TESTS")
    print("========================================")

    genuine_scores = []
    for image_path in GENUINE_IMAGES:
        if not os.path.exists(image_path):
            continue
        emb, _ = face_engine.extract_embedding(image_path)
        if emb is None:
            continue
        score = face_engine.compute_similarity(enrolled_embedding, emb)
        genuine_scores.append(score)
        print(f"{os.path.basename(image_path)} -> {score:.4f}")

    # --------------------------------------------------
    # IMPOSTOR TESTS
    # --------------------------------------------------
    print("\n========================================")
    print("IMPOSTOR VERIFICATION TESTS")
    print("========================================")

    impostor_scores = []
    for image_path in IMPOSTOR_IMAGES:
        if not os.path.exists(image_path):
            continue
        emb, _ = face_engine.extract_embedding(image_path)
        if emb is None:
            continue
        score = face_engine.compute_similarity(enrolled_embedding, emb)
        impostor_scores.append(score)
        print(f"{os.path.basename(image_path)} -> {score:.4f}")

    # --------------------------------------------------
    # SUMMARY
    # --------------------------------------------------
    print("\n========================================")
    print("VERIFICATION SCORE SUMMARY")
    print("========================================")

    if genuine_scores:
        print("Genuine minimum: ", round(min(genuine_scores), 4))
        print("Genuine maximum: ", round(max(genuine_scores), 4))
        print("Genuine average: ", round(float(np.mean(genuine_scores)), 4))

    if impostor_scores:
        print("Impostor minimum:", round(min(impostor_scores), 4))
        print("Impostor maximum:", round(max(impostor_scores), 4))
        print("Impostor average:", round(float(np.mean(impostor_scores)), 4))

    print("========================================")
    return genuine_scores, impostor_scores


if __name__ == "__main__":
    run_verification_evaluation()
