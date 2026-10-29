# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Server-side inference. Raw camera images are decoded in memory and never saved."""

import io
import math
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .constants import MAX_IMAGE_BYTES


class BiometricError(ValueError):
    pass


def finger_count(points):
    """Count extended fingers using joint angles and distance from the wrist.

    Students hold an upright open palm toward the camera. Geometry avoids
    assumptions about handedness and selfie-preview mirroring.
    """

    def distance(a, b):
        return math.sqrt(
            sum((getattr(a, axis) - getattr(b, axis)) ** 2 for axis in ("x", "y", "z"))
        )

    def angle(a, b, c):
        v = np.array([a.x - b.x, a.y - b.y, a.z - b.z])
        w = np.array([c.x - b.x, c.y - b.y, c.z - b.z])
        denom = float(np.linalg.norm(v) * np.linalg.norm(w))
        return math.degrees(
            math.acos(float(np.clip(np.dot(v, w) / max(denom, 1e-9), -1, 1)))
        )

    count = 0
    for base, joint, tip in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)):
        if (
            angle(points[base], points[joint], points[tip]) > 155
            and distance(points[tip], points[0])
            > distance(points[joint], points[0]) * 1.12
        ):
            count += 1
    # Thumb must be straight and spread away from the index knuckle.
    if (
        angle(points[1], points[2], points[4]) > 150
        and distance(points[4], points[5]) > distance(points[3], points[5]) * 1.2
    ):
        count += 1
    return count


class Biometrics:
    def __init__(self, model_path=None):
        self.model_path = Path(
            model_path
            or Path(__file__).resolve().parents[2] / "models" / "hand_landmarker.task"
        )
        self._hand_detector = None
        self._lock = threading.Lock()

    def decode(self, data):
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise BiometricError("Use an image smaller than 6 MB.")
        try:
            with Image.open(io.BytesIO(data)) as source:
                if source.width * source.height > 16_000_000:
                    raise BiometricError("Image resolution is too large.")
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((960, 960))
                return np.asarray(image)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise BiometricError("The camera image could not be read.") from exc

    def face(self, image, *, guided=False):
        import face_recognition

        locations = face_recognition.face_locations(image, model="hog")
        if len(locations) != 1:
            raise BiometricError("Keep exactly one face visible in the camera frame.")
        top, right, bottom, left = locations[0]
        if min(bottom - top, right - left) < 80:
            raise BiometricError("Move closer so your face is clear and well lit.")
        if guided:
            height, width = image.shape[:2]
            center_x = (left + right) / (2 * width)
            center_y = (top + bottom) / (2 * height)
            face_width = (right - left) / width
            face_height = (bottom - top) / height
            if face_width > 0.66 or face_height > 0.66:
                raise BiometricError(
                    "Move a little farther away to fit your face inside the circle."
                )
            if face_width < 0.24 or face_height < 0.20:
                raise BiometricError(
                    "Move closer and keep your face inside the circle."
                )
            if abs(center_x - 0.5) > 0.12 or abs(center_y - 0.5) > 0.15:
                raise BiometricError(
                    "Center your face inside the circle and look at the camera."
                )
        encodings = face_recognition.face_encodings(
            image, known_face_locations=locations
        )
        if len(encodings) != 1:
            raise BiometricError(
                "Your face could not be read. Improve the lighting and try again."
            )
        return encodings[0]

    def guided_face(self, image):
        return self.face(image, guided=True)

    def distance(self, encoding, reference):
        return float(np.linalg.norm(np.asarray(encoding) - np.asarray(reference)))

    def hand(self, image):
        if not self.model_path.exists():
            raise RuntimeError("Hand detection model is missing. Run python setup.py.")
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions

        with self._lock:
            if self._hand_detector is None:
                self._hand_detector = HandLandmarker.create_from_options(
                    HandLandmarkerOptions(
                        base_options=BaseOptions(model_asset_path=str(self.model_path)),
                        num_hands=2,
                        min_hand_detection_confidence=0.65,
                        min_hand_presence_confidence=0.65,
                    )
                )
            result = self._hand_detector.detect(
                mp.Image(
                    image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(image)
                )
            )
        if len(result.hand_landmarks) != 1:
            raise BiometricError(
                "Show exactly one full hand anywhere in the frame, palm toward the camera. Keep all fingertips visible without covering your face."
            )
        return finger_count(result.hand_landmarks[0])

    def close(self):
        if self._hand_detector is not None:
            self._hand_detector.close()
