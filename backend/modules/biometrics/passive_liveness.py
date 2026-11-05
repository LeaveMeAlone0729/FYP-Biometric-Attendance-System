"""Persist server-observed PAD evidence; client success flags never count."""

import json
import re

from .constants import REQUIRED_LIVENESS_FRAMES
from .inference import BiometricError
from .presentation import validate_scores

VERSION = 2


def new_state(face_scores):
    return {"version": VERSION, "face_scores": validate_scores(face_scores), "frames": []}


def read_state(value):
    try:
        state = json.loads(value)
        if type(state) is not dict or state.get("version") != VERSION:
            return None
        validate_scores(state["face_scores"])
        frames = state["frames"]
        if type(frames) is not list or len(frames) > REQUIRED_LIVENESS_FRAMES:
            return None
        hashes = []
        for frame in frames:
            digest = frame["hash"]
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                return None
            validate_scores(frame["scores"])
            hashes.append(digest)
        return state if len(set(hashes)) == len(hashes) else None
    except (ValueError, TypeError, KeyError, AttributeError, RuntimeError, BiometricError):
        return None
