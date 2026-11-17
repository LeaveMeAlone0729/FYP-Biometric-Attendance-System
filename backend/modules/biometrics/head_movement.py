"""Server-issued facial actions, bound to one attendance attempt."""

import copy
import math
import secrets
import threading
from collections import OrderedDict

HOLD_FRAMES = 2
MIN_FRAME_SECONDS = 0.25
MAX_BLINK_SECONDS = 1.5
RANDOM_ACTION_COUNT = 2
RANDOM_ACTIONS = ("turn_left", "turn_right", "blink")
MESSAGES = {
    "turn_left": "Slowly turn your head slightly to your left and hold briefly.",
    "turn_right": "Slowly turn your head slightly to your right and hold briefly.",
    "blink": "Blink once normally, then look at the camera with both eyes open.",
}


def challenge_actions():
    """Two distinct actions, selected without exposing future instructions."""
    return secrets.SystemRandom().sample(RANDOM_ACTIONS, RANDOM_ACTION_COUNT)


def observation(pose):
    try:
        values = {key: float(pose[key]) for key in
                  ("yaw", "pitch", "roll", "blink_left", "blink_right")}
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in values.values()):
        return None
    if any(not 0 <= values[key] <= 1 for key in ("blink_left", "blink_right")):
        return None
    return values


def pose_matches(action, pose):
    """Angles come only from server inference on unmirrored camera pixels."""
    values = observation(pose)
    if values is None:
        return False
    yaw, pitch, roll = (values[key] for key in ("yaw", "pitch", "roll"))
    if abs(roll) > 20:
        return False
    if action == "turn_left":
        return 18 <= yaw <= 40 and abs(pitch) <= 20
    if action == "turn_right":
        return -40 <= yaw <= -18 and abs(pitch) <= 20
    return False


def blink_needs_identity(state, pose):
    """Only verified evidence may establish or advance a blink transition.

    Other observations can wait, expire or reset progress, but cannot contribute
    positive evidence. This is an inference filter, never a client pose flag.
    """
    values = observation(pose)
    if values is None or abs(values['yaw']) > 8 or abs(values['pitch']) > 12 or abs(values['roll']) > 20:
        return False
    opened = max(values['blink_left'], values['blink_right']) <= 0.25
    blinked = min(values['blink_left'], values['blink_right']) >= 0.6
    phase = state['blink_phase']
    return ((phase == 'open' and opened)
            or (phase == 'blink' and blinked)
            or (phase == 'reopen' and opened)
            or phase not in ('open', 'blink', 'reopen'))


class RuntimeHeadMovement:
    """No client pose/flags, photos or head landmarks are retained.

    Like runtime PAD evidence, this requires one backend worker. A restart or
    database/cache progress mismatch requires a fresh attendance challenge.
    """

    def __init__(self, clock, capacity=4096):
        if capacity < 1:
            raise ValueError("Head movement evidence capacity must be positive.")
        self._clock = clock
        self._capacity = capacity
        self._entries = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _binding(challenge):
        return (challenge.student_id, challenge.auth_token_hash,
                challenge.session_id, challenge.verification_id, challenge.expires_at)

    def _prune(self):
        now = self._clock()
        for key in list(self._entries):
            if self._entries[key][0][-1] <= now:
                del self._entries[key]

    def start(self, challenge):
        actions = challenge_actions()
        state = {"actions": actions, "step": 0, "held": 0, "progress": 0,
                 "last_at": None, "blink_phase": "open", "blink_at": None,
                 "blink_processing_seconds": 0, "blink_closed_frames": 0}
        with self._lock:
            self._prune()
            if challenge.expires_at <= self._clock():
                return None
            while len(self._entries) >= self._capacity:
                self._entries.popitem(last=False)
            self._entries[challenge.challenge_id] = (self._binding(challenge), state)
        return copy.deepcopy(state)

    def read(self, challenge):
        with self._lock:
            self._prune()
            entry = self._entries.get(challenge.challenge_id)
            if entry is None or entry[0] != self._binding(challenge):
                return None
            return copy.deepcopy(entry[1])

    def advance(self, challenge, pose=None, *, processing_started_at=None):
        with self._lock:
            self._prune()
            entry = self._entries.get(challenge.challenge_id)
            if entry is None or entry[0] != self._binding(challenge):
                return None
            state = entry[1]
            if state["progress"] != challenge.valid_frames:
                return None
            if state["step"] == len(state["actions"]):
                return copy.deepcopy(state)
            now = self._clock()
            action = state["actions"][state["step"]]
            if action == "blink":
                # This timestamp comes only from the service, never the client.
                # Inference on queued burst frames must not consume idle time.
                processing_seconds = (max(0, (now-processing_started_at).total_seconds())
                                      if processing_started_at is not None else 0)
                self._blink(state, pose, now, processing_seconds)
                state["progress"] = state["step"] * HOLD_FRAMES + state["held"]
                return copy.deepcopy(state)
            if not pose_matches(action, pose):
                state["held"] = 0
                state["progress"] = state["step"] * HOLD_FRAMES
                state["last_at"] = now
                return copy.deepcopy(state)
            # Even a faster client cannot satisfy a hold with an instant burst.
            if state["last_at"] is not None and (now-state["last_at"]).total_seconds() < MIN_FRAME_SECONDS:
                return copy.deepcopy(state)
            state["last_at"] = now
            state["held"] += 1
            if state["held"] >= HOLD_FRAMES:
                state["step"] += 1
                state["held"] = 0
                if (state["step"] < len(state["actions"])
                        and state["actions"][state["step"]] == "blink"):
                    # A verified turn can supply the open-eye baseline too;
                    # there is no intervening recenter or look-straight hold.
                    values = observation(pose)
                    if max(values['blink_left'], values['blink_right']) <= 0.25:
                        state["blink_phase"] = "blink"
            state["progress"] = state["step"] * HOLD_FRAMES + state["held"]
            return copy.deepcopy(state)

    @staticmethod
    def _blink(state, pose, now, processing_seconds=0):
        """Require open -> brief bilateral blink -> reopened, never a closed-eye hold.

        Burst frames are ordered and each passes face/PAD/replay checks in the
        service. A frame limit and server idle time bound the closed phase;
        processing time is excluded and challenge expiry still applies.
        """
        values = observation(pose)
        frontal = values is not None and abs(values['yaw']) <= 8 and abs(values['pitch']) <= 12 and abs(values['roll']) <= 20
        if not frontal:
            state.update(blink_phase='open', blink_at=None, blink_processing_seconds=0,
                         blink_closed_frames=0, held=0)
            return
        opened = max(values['blink_left'], values['blink_right']) <= 0.25
        blinked = min(values['blink_left'], values['blink_right']) >= 0.6
        phase = state['blink_phase']
        if phase == 'open' and opened:
            state['blink_phase'] = 'blink'
        elif phase == 'blink' and blinked:
            state.update(blink_phase='reopen', blink_at=now, blink_processing_seconds=0,
                         blink_closed_frames=1, held=1)
        elif phase == 'reopen':
            state['blink_processing_seconds'] += processing_seconds
            idle_seconds = ((now-state['blink_at']).total_seconds()
                            - state['blink_processing_seconds'])
            if idle_seconds > MAX_BLINK_SECONDS:
                state.update(blink_phase='open', blink_at=None, blink_processing_seconds=0,
                             blink_closed_frames=0, held=0)
            elif opened:
                state['step'] += 1
                state.update(blink_phase='open', blink_at=None, blink_processing_seconds=0,
                             blink_closed_frames=0, held=0, last_at=now)
            elif blinked:
                # Partly reopening eyes are transitional, not another closed
                # frame. Keep the existing hold cap and server time bound.
                state['blink_closed_frames'] += 1
                if state['blink_closed_frames'] > 3:
                    state.update(blink_phase='open', blink_at=None, blink_processing_seconds=0,
                                 blink_closed_frames=0, held=0)

    def discard(self, challenge):
        with self._lock:
            self._entries.pop(challenge.challenge_id, None)

    def clear(self):
        with self._lock:
            self._entries.clear()
