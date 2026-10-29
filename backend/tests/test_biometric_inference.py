# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Inference geometry and real-model rejection tests; no accuracy claims."""

import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from biometrics import BiometricError, Biometrics, finger_count


class ImageProcessingTests(unittest.TestCase):
    def test_gesture_face_check_accepts_either_side_without_centering(self):
        detector = SimpleNamespace(
            face_locations=lambda image, model: [],
            face_encodings=lambda image, known_face_locations: [np.zeros(128)],
        )
        bio = Biometrics()
        image = np.zeros((640, 480, 3), dtype=np.uint8)
        with patch.dict(sys.modules, {"face_recognition": detector}):
            for box in ((160, 180, 360, 40), (160, 440, 360, 300)):
                with self.subTest(box=box):
                    detector.face_locations = lambda image, model, box=box: [box]
                    # The gesture stage uses face(), retaining identity matching
                    # without the positioning constraints of guided_face().
                    self.assertEqual(len(bio.face(image)), 128)
                    with self.assertRaisesRegex(BiometricError, "Center your face"):
                        bio.guided_face(image)

    def test_guided_face_rejects_off_center_or_badly_sized_faces(self):
        detector = SimpleNamespace(
            face_locations=lambda image, model: [(220, 310, 420, 170)],
            face_encodings=lambda image, known_face_locations: [np.zeros(128)],
        )
        bio = Biometrics()
        image = np.zeros((640, 480, 3), dtype=np.uint8)
        with patch.dict(sys.modules, {"face_recognition": detector}):
            self.assertEqual(len(bio.guided_face(image)), 128)
            for box, message in (
                ((40, 180, 240, 40), "Center your face"),
                ((120, 450, 520, 30), "farther away"),
                ((270, 290, 370, 190), "Move closer"),
            ):
                detector.face_locations = lambda image, model, box=box: [box]
                with self.assertRaisesRegex(BiometricError, message):
                    bio.guided_face(image)

    def test_finger_geometry_is_mirror_invariant(self):
        # Synthetic landmarks exercise handedness independence without collecting biometrics.
        for count in range(1, 6):
            points = [SimpleNamespace(x=0.0, y=0.0, z=0.0) for _ in range(21)]
            for index, (base, joint, tip) in enumerate(
                ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20))
            ):
                x = (index + 1) * 0.2
                points[base] = SimpleNamespace(x=x, y=1.0, z=0.0)
                points[joint] = SimpleNamespace(x=x, y=2.0, z=0.0)
                points[tip] = SimpleNamespace(
                    x=x, y=3.0 if index < min(count, 4) else 1.2, z=0.0
                )
            points[1] = SimpleNamespace(x=-0.2, y=0.2, z=0.0)
            points[2] = SimpleNamespace(x=-0.4, y=0.4, z=0.0)
            points[3] = SimpleNamespace(x=-0.6, y=0.6, z=0.0)
            points[4] = (
                SimpleNamespace(x=-1.0, y=1.0, z=0.0)
                if count == 5
                else SimpleNamespace(x=0.1, y=1.0, z=0.0)
            )
            self.assertEqual(finger_count(points), count)
            mirrored = [SimpleNamespace(x=-p.x, y=p.y, z=p.z) for p in points]
            self.assertEqual(finger_count(mirrored), count)

    def test_invalid_and_oversized_images_rejected(self):
        bio = Biometrics()
        with self.assertRaises(BiometricError):
            bio.decode(b"not-an-image")
        with self.assertRaises(BiometricError):
            bio.decode(b"x" * (6 * 1024 * 1024 + 1))

    def test_real_image_decoding_and_face_rejection(self):
        buffer = io.BytesIO()
        Image.new("RGB", (300, 300), (100, 100, 100)).save(buffer, format="JPEG")
        bio = Biometrics()
        image = bio.decode(buffer.getvalue())
        self.assertEqual(image.shape, (300, 300, 3))
        with self.assertRaises(BiometricError):
            bio.face(image)

    def test_real_mediapipe_model_runs_and_rejects_missing_hand(self):
        bio = Biometrics()
        if not bio.model_path.exists():
            self.skipTest("Run setup.py to download the official MediaPipe model.")
        with self.assertRaises(BiometricError):
            bio.hand(np.zeros((300, 300, 3), dtype=np.uint8))
        bio.close()


if __name__ == "__main__":
    unittest.main()
