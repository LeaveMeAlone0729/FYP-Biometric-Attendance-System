"""Pinned model downloads for face presentation checks and hand landmarks.

MiniFASNet models: minivision-ai/Silent-Face-Anti-Spoofing, Apache-2.0.
ONNX exports and preprocessing: github.com/yakhyo/face-anti-spoofing.
MediaPipe model: Google, developers.google.com/edge/mediapipe.
"""

import hashlib
from pathlib import Path
from urllib.request import urlopen

MODEL_ASSETS = {
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
        "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
    ),
    "MiniFASNetV2.onnx": (
        "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV2.onnx",
        "b32929adc2d9c34b9486f8c4c7bc97c1b69bc0ea9befefc380e4faae4e463907",
    ),
    "MiniFASNetV1SE.onnx": (
        "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV1SE.onnx",
        "ebab7f90c7833fbccd46d3a555410e78d969db5438e169b6524be444862b3676",
    ),
}


def verified_model(path):
    path = Path(path)
    expected = MODEL_ASSETS[path.name][1]
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError("Biometric model missing or invalid. Run python -m modules.biometrics.model_assets.")
    return path


def download_models(directory=None):
    root = Path(directory or Path(__file__).resolve().parents[2] / "models")
    root.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in MODEL_ASSETS.items():
        target = root / name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            continue
        with urlopen(url, timeout=60) as response:
            data = response.read(20 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(f"Model checksum failed: {name}")
        temporary = target.with_suffix(target.suffix + ".download")
        temporary.write_bytes(data)
        temporary.replace(target)


if __name__ == "__main__":
    download_models()
    print("Biometric models verified.")
