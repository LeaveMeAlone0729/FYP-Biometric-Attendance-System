"""Short-lived server-memory PAD evidence; never stored in the database."""

import json
import re
import threading
from collections import OrderedDict

from .constants import REQUIRED_LIVENESS_FRAMES
from .inference import BiometricError
from .presentation import validate_scores

VERSION = 3


class RuntimeLiveness:
    """Process-local evidence bound to one student, login and attendance challenge.

    Database row locking serializes requests for a challenge. Reads return copies;
    a rollback/cache mismatch fails closed and requires a fresh verification.
    Run one backend worker: workers/restarts do not share this temporary state.
    """

    def __init__(self, clock, capacity=4096):
        if capacity < 1:
            raise ValueError("Runtime evidence capacity must be positive.")
        self._clock = clock
        self._capacity = capacity
        self._entries = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _binding(challenge):
        return (challenge.student_id, challenge.auth_token_hash, challenge.session_id,
                challenge.verification_id, challenge.fingers, challenge.expires_at)

    def _prune(self):
        now = self._clock()
        for key in list(self._entries):
            if self._entries[key][0][-1] <= now:
                del self._entries[key]

    def start(self, challenge, face_scores, *, head_verified=False):
        state = new_state(face_scores, head_verified=head_verified)
        with self._lock:
            self._prune()
            if challenge.expires_at <= self._clock():
                return False
            self._entries.pop(challenge.challenge_id, None)
            while len(self._entries) >= self._capacity:
                self._entries.popitem(last=False)
            self._entries[challenge.challenge_id] = (self._binding(challenge), json.dumps(state))
        return True

    def read(self, challenge):
        with self._lock:
            self._prune()
            entry = self._entries.get(challenge.challenge_id)
            if entry is None or entry[0] != self._binding(challenge):
                return None
            return read_state(entry[1])

    def save(self, challenge, state):
        encoded = json.dumps(state)
        if read_state(encoded) is None:
            raise ValueError("Invalid runtime anti-spoof evidence.")
        with self._lock:
            self._prune()
            entry = self._entries.get(challenge.challenge_id)
            if entry is None or entry[0] != self._binding(challenge):
                return False
            self._entries[challenge.challenge_id] = (entry[0], encoded)
        return True

    def discard(self, challenge):
        with self._lock:
            self._entries.pop(challenge.challenge_id, None)

    def clear(self):
        with self._lock:
            self._entries.clear()


def new_state(face_scores, *, head_verified=False):
    return {"version": VERSION, "face_scores": validate_scores(face_scores),
            "head_verified": head_verified, "frames": []}


def read_state(value):
    try:
        state = json.loads(value)
        if type(state) is not dict or state.get("version") != VERSION:
            return None
        validate_scores(state["face_scores"])
        if type(state.get("head_verified")) is not bool:
            return None
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
