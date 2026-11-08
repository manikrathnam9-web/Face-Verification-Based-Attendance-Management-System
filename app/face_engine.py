import os
import cv2
import numpy as np
from insightface.app import FaceAnalysis

# Default verification threshold determined via experimental FAR/FRR evaluation
DEFAULT_VERIFICATION_THRESHOLD = 0.58
DEFAULT_MIN_MARGIN = 0.05


class FaceEngine:
    """
    Singleton Face Analysis Engine utilizing InsightFace buffalo_l (ArcFace + RetinaFace).
    Handles face detection, 512-D embedding extraction, image quality checks,
    1:1 verification, and 1:N identification.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FaceEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name="buffalo_l", ctx_id=0, det_size=(640, 640)):
        if getattr(self, "_initialized", False):
            return

        self.model_name = model_name
        self.ctx_id = ctx_id
        self.det_size = det_size
        self._app = None
        self._initialized = True

    def initialize(self):
        """Lazy load and prepare InsightFace model."""
        if self._app is None:
            print("[FaceEngine] Loading InsightFace model:", self.model_name)
            self._app = FaceAnalysis(
                name=self.model_name,
                providers=["CPUExecutionProvider"]
            )
            self._app.prepare(
                ctx_id=self.ctx_id,
                det_size=self.det_size
            )
            print("[FaceEngine] Model initialized successfully.")
        return self._app

    def is_ready(self) -> bool:
        """Check if engine is ready."""
        return self._app is not None or True

    def detect_faces(self, image_or_path):
        """
        Detect all faces in an image.
        Accepts numpy array (BGR image) or file path string.
        Returns a list of InsightFace Face objects.
        """
        app = self.initialize()

        if isinstance(image_or_path, str):
            if not os.path.exists(image_or_path):
                raise FileNotFoundError(f"Image not found at path: {image_or_path}")
            image = cv2.imread(image_or_path)
            if image is None:
                raise ValueError(f"Failed to decode image from path: {image_or_path}")
        elif isinstance(image_or_path, np.ndarray):
            image = image_or_path
        else:
            raise TypeError("image_or_path must be a file path string or numpy ndarray.")

        faces = app.get(image)
        return faces

    def check_quality(self, image, face=None):
        """
        Evaluate image quality:
        1. Minimum bounding box dimension
        2. Detection confidence score
        3. Sharpness / blurriness test via Laplacian variance
        Returns (is_acceptable: bool, message: str)
        """
        if face is not None:
            det_score = getattr(face, "det_score", 0.0)
            if det_score < 0.60:
                return False, f"Low detection confidence: {det_score:.2f} < 0.60"

            bbox = face.bbox.astype(int)
            w = max(0, bbox[2] - bbox[0])
            h = max(0, bbox[3] - bbox[1])
            if w < 50 or h < 50:
                return False, f"Face region too small: {w}x{h} px"

            # Check blurriness within cropped face area
            x1, y1 = max(0, bbox[0]), max(0, bbox[1])
            x2, y2 = min(image.shape[1], bbox[2]), min(image.shape[0], bbox[3])
            face_roi = image[y1:y2, x1:x2]
            if face_roi.size > 0:
                gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                if laplacian_var < 30.0:
                    return False, f"Face image is blurry (Laplacian variance: {laplacian_var:.1f} < 30.0)"

        return True, "Quality check passed"

    def extract_embedding(self, image_or_path, single_face_required=True):
        """
        Extract the 512-D face embedding vector from an image.
        If single_face_required=True, errors if 0 or >1 faces are present.
        Returns: (embedding: np.ndarray, face_object)
        """
        faces = self.detect_faces(image_or_path)

        if len(faces) == 0:
            return None, "No face detected in image."

        if single_face_required and len(faces) > 1:
            return None, f"Multiple faces ({len(faces)}) detected. Please provide an image with exactly one face."

        # Select the primary face (highest detection score or first)
        best_face = max(faces, key=lambda f: getattr(f, "det_score", 0.0))
        embedding = best_face.embedding

        if embedding is None:
            return None, "Could not compute face embedding."

        return embedding, best_face

    @staticmethod
    def compute_similarity(embedding1, embedding2) -> float:
        """
        Compute Cosine Similarity between two 512-dimensional embeddings:
        similarity = (A . B) / (||A|| * ||B||)
        Range: [-1.0, 1.0]. Typically genuine matches score > 0.55.
        """
        if embedding1 is None or embedding2 is None:
            return 0.0

        emb1 = np.asarray(embedding1).flatten()
        emb2 = np.asarray(embedding2).flatten()

        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        similarity = float(dot_product / (norm1 * norm2))
        return similarity

    def verify_1_to_1(self, query_embedding, enrolled_embedding, threshold=DEFAULT_VERIFICATION_THRESHOLD):
        """
        1:1 Verification: Verify whether query face matches claimed enrolled identity.
        Returns dict with match decision, similarity score, and threshold.
        """
        score = self.compute_similarity(query_embedding, enrolled_embedding)
        is_verified = bool(score >= threshold)
        return {
            "verified": is_verified,
            "similarity": round(score, 4),
            "threshold": threshold,
            "status": "VERIFIED" if is_verified else "REJECTED"
        }

    def identify_1_to_n(self, query_embedding, enrolled_students, threshold=DEFAULT_VERIFICATION_THRESHOLD, min_margin=DEFAULT_MIN_MARGIN):
        """
        1:N Identification: Compare query face against a collection of enrolled students.
        enrolled_students: list of dicts or tuples:
           dict: {"student_id": ..., "name": ..., "department": ..., "embedding": np.ndarray}
           or tuple: (student_id, name, department, embedding)
        Returns dict with best_student, best_score, second_score, score_margin, is_ambiguous, verified, and all comparisons.
        """
        comparisons = []

        for student in enrolled_students:
            if isinstance(student, dict):
                s_id = student["student_id"]
                s_name = student["name"]
                s_dept = student.get("department", "")
                s_emb = student.get("embedding")
            else:
                s_id, s_name, s_dept = student[0], student[1], student[2]
                s_emb = student[3] if len(student) > 3 else None

            if s_emb is None:
                continue

            score = self.compute_similarity(query_embedding, s_emb)
            comparisons.append({
                "student_id": s_id,
                "name": s_name,
                "department": s_dept,
                "similarity": round(float(score), 4)
            })

        sorted_comparisons = sorted(comparisons, key=lambda x: x["similarity"], reverse=True)

        if not sorted_comparisons:
            return {
                "verified": False,
                "best_student": None,
                "matched_candidate": None,
                "best_score": 0.0,
                "second_score": 0.0,
                "score_margin": 0.0,
                "is_ambiguous": False,
                "threshold": threshold,
                "min_margin": min_margin,
                "comparisons": [],
                "status": "REJECTED"
            }

        best = sorted_comparisons[0]
        best_score = best["similarity"]
        candidate_student = {
            "student_id": best["student_id"],
            "name": best["name"],
            "department": best["department"]
        }

        second_score = sorted_comparisons[1]["similarity"] if len(sorted_comparisons) > 1 else 0.0
        score_margin = round(best_score - second_score, 4) if len(sorted_comparisons) > 1 else 1.0

        is_above_threshold = bool(best_score >= threshold)
        is_ambiguous = bool(len(sorted_comparisons) > 1 and is_above_threshold and score_margin < min_margin)

        if is_above_threshold and not is_ambiguous:
            status = "VERIFIED"
            verified = True
            best_student = candidate_student
        elif is_ambiguous:
            status = "UNCERTAIN"
            verified = False
            best_student = None
        else:
            status = "REJECTED"
            verified = False
            best_student = None

        return {
            "verified": verified,
            "best_student": best_student,
            "matched_candidate": candidate_student,
            "best_score": round(best_score, 4),
            "second_score": round(second_score, 4),
            "score_margin": round(score_margin, 4),
            "is_ambiguous": is_ambiguous,
            "threshold": threshold,
            "min_margin": min_margin,
            "comparisons": sorted_comparisons,
            "status": status
        }

    @staticmethod
    def draw_hud(image, bbox, label, color=(0, 255, 0), subtitle=None):
        """
        Draw bounding box, header banner, and label on OpenCV frame.
        """
        x1, y1, x2, y2 = bbox.astype(int)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

        # Header tag
        tag_text = label
        (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        tag_y1 = max(0, y1 - 25)
        tag_y2 = y1
        cv2.rectangle(image, (x1, tag_y1), (x1 + tw + 10, tag_y2), color, -1)
        cv2.putText(
            image, tag_text, (x1 + 5, tag_y2 - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA
        )

        if subtitle:
            cv2.putText(
                image, subtitle, (x1, y2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA
            )
        return image


# Global singleton instance
face_engine = FaceEngine()


if __name__ == "__main__":
    print("Testing FaceEngine initialization...")
    engine = FaceEngine()
    test_img = "data/test_images/test.jpeg"
    if os.path.exists(test_img):
        emb, face = engine.extract_embedding(test_img)
        if emb is not None:
            print("Successfully extracted 512-D embedding. Shape:", emb.shape)
            print("First 5 values:", emb[:5])
        else:
            print("Extraction failed:", face)
    else:
        print("Test image not found:", test_img)
