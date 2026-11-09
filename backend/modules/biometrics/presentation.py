import threading
from pathlib import Path

import numpy as np

from .inference import BiometricError
from .model_assets import verified_model

MIN_REAL_SCORE = 0.80


def validate_scores(scores):
    if (
        not isinstance(scores, (list, tuple)) or len(scores) != 2
        or any(type(score) not in (int, float) or not np.isfinite(score) or not 0 <= score <= 1 for score in scores)
    ):
        raise RuntimeError("Anti-spoof inference returned invalid scores.")
    if min(scores) < 0.65 or sum(scores) / len(scores) < MIN_REAL_SCORE:
        raise BiometricError("Photo or screen presentation could not be ruled out. Use your real face directly in front of the camera in even lighting.")
    return list(map(float, scores))


def face_crop(image, box, scale):
    """Expand the detected face with the training-time context crop."""
    import cv2

    height, width = image.shape[:2]
    top, right, bottom, left = box
    box_width, box_height = right - left, bottom - top
    if min(box_width, box_height) <= 0:
        raise BiometricError("Keep your full face visible.")
    scale = min((height - 1) / box_height, (width - 1) / box_width, scale)
    center_x, center_y = (left + right) / 2, (top + bottom) / 2
    x1, y1 = max(0, int(center_x - box_width * scale / 2)), max(0, int(center_y - box_height * scale / 2))
    x2, y2 = min(width - 1, int(center_x + box_width * scale / 2)), min(height - 1, int(center_y + box_height * scale / 2))
    # The application decodes RGB; these classifiers were trained on BGR.
    crop = image[y1:y2 + 1, x1:x2 + 1, ::-1]
    resized = cv2.resize(crop, (80, 80))
    return np.ascontiguousarray(resized.transpose(2, 0, 1)[None], dtype=np.float32)


def real_probability(logits):
    values = np.asarray(logits, dtype=np.float64).reshape(-1)
    if values.size != 3 or not np.isfinite(values).all():
        raise RuntimeError("Anti-spoof inference returned invalid output.")
    probabilities = np.exp(values - values.max())
    probabilities /= probabilities.sum()
    return float(probabilities[1])


class PresentationChecker:
    def __init__(self, model_directory=None):
        import cv2

        root = Path(model_directory or Path(__file__).resolve().parents[2] / "models")
        self._lock = threading.Lock()
        self._models = [
            (cv2.dnn.readNetFromONNX(str(verified_model(root / name))), scale)
            for name, scale in (("MiniFASNetV2.onnx", 2.7), ("MiniFASNetV1SE.onnx", 4.0))
        ]

    def observe(self, image, box):
        with self._lock:
            scores = []
            for model, scale in self._models:
                model.setInput(face_crop(image, box, scale))
                scores.append(real_probability(model.forward()))
        return {"real_scores": validate_scores(scores)}

    def close(self):
        with self._lock:
            self._models.clear()
