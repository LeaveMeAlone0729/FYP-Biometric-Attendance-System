# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Compatibility imports; implementation lives in modules.biometrics.inference."""

from modules.biometrics.inference import BiometricError, Biometrics, finger_count

__all__ = ["BiometricError", "Biometrics", "finger_count"]
