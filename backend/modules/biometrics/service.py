# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Biometric workflow; HTTP parsing and attendance storage live outside this file."""

import hashlib
import json
import math
import secrets

from config import iso_time
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from models import Attendance, Challenge, Student, VerificationAttempt
from services.attendance import record_verified_attendance
from sqlalchemy import select

from .constants import MAX_IMAGE_BYTES, MAX_LIVENESS_FRAMES, REQUIRED_LIVENESS_FRAMES
from .inference import BiometricError
from .passive_liveness import new_state, read_state
from .presentation import validate_scores
from .templates import decrypt_encoding, encrypt_encoding


class BiometricService:
    def __init__(self, context):
        self.context = context

    def read_image(self, file):
        return self.context.bio.decode(file.file.read(MAX_IMAGE_BYTES + 1))

    def face_evidence(self, image):
        try:
            return validate_scores(self.context.bio.face_evidence(image)["real_scores"])
        except (RuntimeError, ImportError, KeyError, TypeError) as exc:
            raise HTTPException(503, "Face anti-spoof verification is unavailable. Check the backend models before retrying.") from exc

    def liveness_progress(self, challenge, *, message=None, ready=False):
        state = read_state(challenge.face_liveness_state)
        if state is None:
            raise HTTPException(409, "Start a new verification to use the updated anti-spoof check.")
        return {
            "success": True, "complete": False, "ready": ready,
            "valid_frames": challenge.valid_frames,
            "required_frames": REQUIRED_LIVENESS_FRAMES,
            "liveness_step": "hand",
            "message": message or "Keep your face and the requested fingers visible while the camera checks automatically.",
        }

    def check_deadline(self, student, db, challenge, session):
        if challenge.expires_at <= self.context.now() or not self.context.session_open(session, student, db):
            self.context.reject(db, student.student_id, "liveness", "The verification or class attendance window has expired. Start again.", session.session_id, 410, challenge)

    def reference(self, student):
        if not student.face_encoding or student.biometric_status != "active":
            raise BiometricError(
                "Register your face in Profile before taking attendance."
                if student.biometric_status == "not_registered" and not student.face_encoding
                else "Your facial registration needs attention. Visit your department for supervised re-registration. Ask your lecturer to record attendance manually while this is resolved."
            )
        try:
            return decrypt_encoding(
                student.face_encoding, self.context.settings.biometric_key
            )
        except (InvalidToken, ValueError) as exc:
            raise BiometricError(
                "Your facial registration needs attention. Visit your department for supervised re-registration. Ask your lecturer to record attendance manually while this is resolved."
            ) from exc

    def register_face(
        self, student, db, file, consent, *, auto_capture=False, preview_only=False
    ):
        # Lock student so simultaneous enrollment requests cannot overwrite a template.
        student = db.scalar(
            select(Student)
            .where(Student.student_id == student.student_id)
            .with_for_update()
        )
        if not consent:
            raise HTTPException(
                400, "Your consent is required before registering facial biometrics."
            )
        if student.face_encoding or student.biometric_status != "not_registered":
            raise HTTPException(
                409,
                "Facial registration is locked. Visit your department if re-registration is needed. Ask your lecturer to record attendance manually while this is resolved.",
            )
        try:
            image = self.read_image(file)
            encoding = (
                self.context.bio.guided_face(image)
                if auto_capture
                else self.context.bio.face(image)
            )
            self.face_evidence(image)
        except BiometricError as exc:
            if auto_capture:
                return {
                    "success": True,
                    "ready": False,
                    "retryable": True,
                    "message": str(exc),
                }
            self.context.reject(db, student.student_id, "enrollment", str(exc))
        if preview_only:
            return {
                "success": True,
                "ready": True,
                "preview_only": True,
                "message": "Face detected. Hold still for automatic capture.",
            }
        student.face_encoding = encrypt_encoding(
            encoding, self.context.settings.biometric_key
        )
        student.biometric_status = "active"
        student.consent_at = self.context.now()
        student.updated_at = self.context.now()
        self.context.audit(db, student.student_id, "enrollment", None, result="success")
        return {
            "success": True,
            "ready": True,
            "registered": True,
            "message": "Face registered successfully",
        }

    def verify_face(
        self,
        student,
        auth,
        db,
        challenge_id,
        file,
        *,
        auto_capture=False,
        preview_only=False,
    ):
        challenge, session = self.context.get_challenge(
            challenge_id, "face", db, student, auth
        )
        try:
            image = self.read_image(file)
            encoding = (
                self.context.bio.guided_face(image)
                if auto_capture
                else self.context.bio.face(image)
            )
            face_scores = self.face_evidence(image)
        except BiometricError as exc:
            if auto_capture:
                if (
                    challenge.expires_at <= self.context.now()
                    or not self.context.session_open(session, student, db)
                ):
                    self.context.reject(
                        db,
                        student.student_id,
                        "face",
                        "Verification timed out. Start again.",
                        session.session_id,
                        410,
                        challenge,
                    )
                return {
                    "success": True,
                    "ready": False,
                    "retryable": True,
                    "message": str(exc),
                }
            self.context.reject(
                db,
                student.student_id,
                "face",
                str(exc),
                session.session_id,
                400,
                challenge,
            )
        try:
            distance = self.context.bio.distance(encoding, self.reference(student))
        except BiometricError as exc:
            self.context.reject(
                db,
                student.student_id,
                "face",
                str(exc),
                session.session_id,
                400,
                challenge,
            )
        if not math.isfinite(distance) or distance >= self.context.settings.face_threshold:
            self.context.reject(
                db,
                student.student_id,
                "face",
                "Face not matched. Start again using your own registered face.",
                session.session_id,
                400,
                challenge,
            )
        if challenge.expires_at <= self.context.now() or not self.context.session_open(
            session, student, db
        ):
            self.context.reject(
                db,
                student.student_id,
                "face",
                "Verification timed out. Start again.",
                session.session_id,
                410,
                challenge,
            )
        if preview_only:
            return {
                "success": True,
                "ready": True,
                "preview_only": True,
                "message": "Face matched. Hold still for automatic capture.",
            }
        challenge.stage = "liveness"
        challenge.fingers = secrets.randbelow(5) + 1
        state = new_state(face_scores)
        challenge.face_liveness_state = json.dumps(state)
        # An enrollment/face frame can never count as a liveness response.
        challenge.frame_hashes = json.dumps(
            [hashlib.sha256(image.tobytes()).hexdigest()]
        )
        root = db.get(VerificationAttempt, challenge.verification_id)
        root.stage = "liveness"
        root.face_distance = distance
        return {
            "success": True,
            "ready": True,
            "face_verified": True,
            "stage": "liveness",
            "fingers": challenge.fingers,
            "required_frames": REQUIRED_LIVENESS_FRAMES,
            "expires_at": iso_time(challenge.expires_at, self.context.settings),
            "liveness_step": "hand",
            "anti_spoof_verified": True,
            "message": f"Face and anti-spoof checks passed. Show {challenge.fingers} finger(s) beside your face, palm toward the camera.",
        }

    def liveness_frame(self, student, auth, db, challenge_id, file, *, request_scope=None, device_challenge_id=None, device_signature=None):
        challenge, session = self.context.get_challenge(
            challenge_id, "liveness", db, student, auth
        )
        state = read_state(challenge.face_liveness_state)
        if state is None or len(state["frames"]) != challenge.valid_frames:
            raise HTTPException(409, "Start a new verification to use the updated anti-spoof check.")
        if len(json.loads(challenge.frame_hashes)) >= MAX_LIVENESS_FRAMES:
            self.context.reject(
                db,
                student.student_id,
                "liveness",
                "Too many verification frames. Start again.",
                session.session_id,
                429,
                challenge,
            )
        try:
            image = self.read_image(file)
            frame_hash = hashlib.sha256(image.tobytes()).hexdigest()
            hashes = json.loads(challenge.frame_hashes)
            if frame_hash in hashes:
                raise BiometricError(
                    "Use the live camera. Keep your face and hand fully visible anywhere in the frame."
                )
            hashes.append(frame_hash)
            challenge.frame_hashes = json.dumps(hashes)
            distance = self.context.bio.distance(
                self.context.bio.face(image), self.reference(student)
            )
            if (
                not math.isfinite(distance)
                or distance >= self.context.settings.face_threshold
            ):
                # Never count an unmatched face. Let the student recover from
                # blur or a brief head turn without restarting the whole flow.
                raise BiometricError(
                    "Face not matched in this frame. Look toward the camera and keep your hand beside, rather than over, your face."
                )
            frame_scores = self.face_evidence(image)
            self.check_deadline(student, db, challenge, session)
            count = self.context.bio.hand(image)
            if count != challenge.fingers:
                raise BiometricError(
                    f"Detected {count} finger(s). Show {challenge.fingers} with your palm toward the camera."
                )
        except BiometricError as exc:
            challenge.valid_frames = 0
            state["frames"] = []
            challenge.face_liveness_state = json.dumps(state)
            self.context.audit(
                db, student.student_id, "liveness", str(exc), session.session_id
            )
            self.check_deadline(student, db, challenge, session)
            return self.liveness_progress(challenge, message=str(exc))
        if challenge.expires_at <= self.context.now() or not self.context.session_open(
            session, student, db
        ):
            self.context.reject(
                db,
                student.student_id,
                "liveness",
                "The verification or class attendance window has expired. Start again.",
                session.session_id,
                410,
                challenge,
            )
        challenge.valid_frames += 1
        state["frames"].append({"hash": frame_hash, "scores": frame_scores})
        challenge.face_liveness_state = json.dumps(state)
        if challenge.valid_frames < REQUIRED_LIVENESS_FRAMES:
            return self.liveness_progress(challenge, ready=True, message="Correct gesture. Hold steady; your face and hand do not need to be centered.")
        return record_verified_attendance(self.context, db, student, challenge, session, auth=auth, request_scope=request_scope, device_challenge_id=device_challenge_id, device_signature=device_signature)

    def cancel(self, student, auth, db, challenge_id):
        challenge = db.scalar(
            select(Challenge)
            .where(Challenge.challenge_id == challenge_id)
            .with_for_update()
        )
        if (
            challenge is None
            or challenge.student_id != student.student_id
            or challenge.auth_token_hash != auth.token_hash
        ):
            raise HTTPException(404, "Verification request not found.")
        if not challenge.consumed:
            challenge.consumed = True
            root = db.get(VerificationAttempt, challenge.verification_id)
            root.verification_result = "cancelled"
            root.failure_reason = "Cancelled by the student."
        return {"success": True}

    def result(self, student, auth, db, challenge_id):
        """Read persisted evidence; never accept a verification flag from a client."""
        challenge = db.get(Challenge, challenge_id)
        if (
            challenge is None
            or challenge.student_id != student.student_id
            or challenge.auth_token_hash != auth.token_hash
        ):
            raise HTTPException(404, "Verification request not found.")
        root = db.get(VerificationAttempt, challenge.verification_id)
        status = root.verification_result
        if status == "pending" and challenge.expires_at <= self.context.now():
            status = "expired"
        elif status == "failed" and root.failure_reason == "Verification timed out.":
            status = "expired"
        attendance_id = db.scalar(
            select(Attendance.attendance_id).where(
                Attendance.verification_id == challenge.verification_id
            )
        )
        return {
            "success": True,
            "challenge_id": challenge.challenge_id,
            "verification_id": challenge.verification_id,
            "student_id": challenge.student_id,
            "session_id": challenge.session_id,
            "status": status,
            "stage": challenge.stage,
            "face_verified": root.face_distance is not None
            and root.face_distance < self.context.settings.face_threshold,
            "liveness_verified": status == "success" and challenge.stage == "complete",
            "face_liveness_verified": status == "success" and len((read_state(challenge.face_liveness_state) or {}).get("frames", [])) == REQUIRED_LIVENESS_FRAMES,
            "valid_frames": challenge.valid_frames,
            "required_frames": REQUIRED_LIVENESS_FRAMES,
            "expires_at": iso_time(challenge.expires_at, self.context.settings),
            "attendance_id": attendance_id,
        }

    def attempts(self, student, db):
        expired = db.scalars(
            select(Challenge).where(
                Challenge.student_id == student.student_id,
                Challenge.consumed == False,
                Challenge.expires_at <= self.context.now(),
            )
        ).all()
        for c in expired:
            c.consumed = True
            root = db.get(VerificationAttempt, c.verification_id)
            root.verification_result = "failed"
            root.failure_reason = "Verification timed out."
        db.flush()
        rows = db.scalars(
            select(VerificationAttempt)
            .where(VerificationAttempt.student_id == student.student_id)
            .order_by(VerificationAttempt.verification_id.desc())
            .limit(100)
        )
        return [
            {
                "verification_id": row.verification_id,
                "result": row.verification_result,
                "stage": row.stage,
                "attempted_at": iso_time(row.attempted_at, self.context.settings),
                "failure_reason": row.failure_reason,
            }
            for row in rows
        ]
