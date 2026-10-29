"""Proposal attendance workflow. All decisions are made on the server."""
import hashlib
import json
import logging
import re
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from cryptography.fernet import InvalidToken
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from biometrics import BiometricError, Biometrics
from config import Settings, iso_time, local_now
from database import make_engine, make_sessions
from demo import seed_demo
from models import Attendance, AuthSession, Challenge, ClassSchedule, ClassSession, Course, Student, StudentGroup, VerificationAttempt
from security import decrypt_encoding, digest, encrypt_encoding, hash_password, verify_password

class Registration(BaseModel):
    student_id: str = Field(min_length=3, max_length=11, pattern=r'^[A-Za-z0-9]+$')
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    group_id: int = Field(gt=0)

    @field_validator('email')
    @classmethod
    def email_format(cls, value):
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address.')
        return value.strip().lower()

    @field_validator('student_id')
    @classmethod
    def uppercase_id(cls, value):
        return value.upper()

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError('Enter your full name.')
        return value.strip()

class Login(BaseModel):
    student_id: str = Field(min_length=1, max_length=11)
    password: str = Field(min_length=1, max_length=128)

class PinEntry(BaseModel):
    pin: str = Field(pattern=r'^\d{6}$')

def create_app(settings=None, engine=None, biometrics=None, clock=None):
    settings = settings or Settings()
    engine = engine or make_engine(settings)
    sessions = make_sessions(engine)
    bio = biometrics or Biometrics()
    now = clock or (lambda: local_now(settings))
    login_failures = {}
    login_lock = threading.Lock()
    # Generate once to equalize unknown-student and wrong-password verification cost.
    dummy_password = hash_password(secrets.token_urlsafe(24))

    @asynccontextmanager
    async def lifespan(app):
        if not settings.biometric_key:
            raise RuntimeError('BIOMETRIC_KEY is missing. Run python setup.py first.')
        yield
        bio.close()
        engine.dispose()

    app = FastAPI(title='Mobile Biometric Attendance', version='2.0.0', lifespan=lifespan)
    app.state.sessions = sessions
    app.state.settings = settings

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo passwords, biometric data, or whole request bodies in errors.
        return JSONResponse(status_code=422, content={'success': False, 'message': 'Check the fields and try again.',
            'fields': [{'field': str(e['loc'][-1]), 'message': e['msg']} for e in exc.errors()]})

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={'success': False, 'message': str(exc.detail)}, headers=exc.headers)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logging.error('Database operation failed: %s', type(exc).__name__)
        return JSONResponse(status_code=503, content={'success': False, 'message': 'The database is unavailable. Please try again.'})

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logging.error('Request failed: %s', type(exc).__name__)
        return JSONResponse(status_code=500, content={'success': False, 'message': 'Verification is temporarily unavailable. Please try again.'})

    def get_db():
        # Every dependent uses function scope: commit before sending a success response.
        with sessions() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    bearer = HTTPBearer(auto_error=False)

    def authenticated(credentials: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db, scope='function')):
        if credentials is None:
            raise HTTPException(401, 'Please sign in to continue.')
        auth = db.get(AuthSession, digest(credentials.credentials))
        if auth is None or auth.expires_at <= now():
            raise HTTPException(401, 'Your session has expired. Please sign in again.')
        student = db.get(Student, auth.student_id)
        if student is None or student.account_status != 'active':
            raise HTTPException(403, 'This account is not active.')
        return student, auth

    def audit(db, student_id, stage, reason, session_id=None, result='failed'):
        attempt = VerificationAttempt(student_id=student_id, session_id=session_id, stage=stage,
            verification_result=result, failure_reason=reason, attempted_at=now())
        db.add(attempt)
        db.flush()
        return attempt

    def reject(db, student_id, stage, reason, session_id=None, status=400, challenge=None):
        if challenge:
            challenge.consumed = True
            root = db.get(VerificationAttempt, challenge.verification_id)
            root.verification_result = 'failed'
            root.failure_reason = reason
            root.stage = stage
        audit(db, student_id, stage, reason, session_id)
        db.commit()  # Failed attempts must survive the HTTP exception rollback.
        raise HTTPException(status, reason)

    def session_open(session, student, db):
        schedule = db.get(ClassSchedule, session.schedule_id)
        current = now()
        return (schedule.group_id == student.group_id and session.status == 'active'
            and session.session_date == current.date()
            and session.start_time <= current.time() <= session.end_time
            and schedule.start_date <= current.date() <= schedule.end_date)

    def get_challenge(identifier, expected_stage, db, student, auth):
        challenge = db.scalar(select(Challenge).where(Challenge.challenge_id == identifier).with_for_update())
        if challenge is None or challenge.student_id != student.student_id or challenge.auth_token_hash != auth.token_hash:
            reject(db, student.student_id, expected_stage, 'This verification request is not valid.', status=403)
        if challenge.consumed:
            reject(db, student.student_id, expected_stage, 'This verification has already ended. Start again.', challenge.session_id, 409)
        if challenge.expires_at <= now():
            reject(db, student.student_id, expected_stage, 'Verification timed out. Enter the attendance PIN again.', challenge.session_id, 410, challenge)
        if challenge.stage != expected_stage:
            reject(db, student.student_id, expected_stage, 'Complete the verification steps in order.', challenge.session_id, 409)
        session = db.get(ClassSession, challenge.session_id)
        if not session_open(session, student, db):
            reject(db, student.student_id, 'session', 'The class attendance window is closed.', session.session_id, 409, challenge)
        return challenge, session

    def read_image(file):
        return bio.decode(file.file.read(6 * 1024 * 1024 + 1))

    def reference(student):
        if not student.face_encoding or student.biometric_status != 'active':
            raise BiometricError('Register your face in Profile before taking attendance.')
        try:
            return decrypt_encoding(student.face_encoding, settings.biometric_key)
        except (InvalidToken, ValueError) as exc:
            raise BiometricError('Your biometric registration needs to be renewed. Contact the project administrator.') from exc

    def profile(student, db):
        group = db.get(StudentGroup, student.group_id)
        return {'student_id': student.student_id, 'name': student.name, 'email': student.email,
            'group_id': group.group_id, 'group_name': group.group_name, 'programme_code': group.programme_code,
            'biometric_status': student.biometric_status, 'consent_at': iso_time(student.consent_at, settings)}

    @app.get('/')
    def health():
        return {'message': 'Backend running', 'version': '2.0.0', 'demo_mode': settings.demo_mode}

    @app.get('/config')
    def config():
        return {'demo_mode': settings.demo_mode, 'server_time': iso_time(now(), settings),
            'verification_seconds': settings.challenge_seconds, 'required_frames': 3}

    @app.get('/groups')
    def groups(db=Depends(get_db, scope='function')):
        if not settings.demo_mode:
            # Production group assignment is controlled through pre-provisioned student accounts.
            return []
        return [{'group_id': g.group_id, 'group_name': g.group_name, 'programme_code': g.programme_code}
            for g in db.scalars(select(StudentGroup).order_by(StudentGroup.group_id))]

    @app.post('/register', status_code=201)
    def register(data: Registration, db=Depends(get_db, scope='function')):
        if not settings.demo_mode:
            raise HTTPException(403, 'Student accounts must be provisioned by the institution.')
        if db.get(StudentGroup, data.group_id) is None:
            raise HTTPException(400, 'Choose a valid student group.')
        if db.scalar(select(Student).where((Student.student_id == data.student_id) | (Student.email == data.email))):
            raise HTTPException(409, 'An account with this student ID or email already exists.')
        db.add(Student(student_id=data.student_id, group_id=data.group_id, name=data.name, email=data.email,
            password_hash=hash_password(data.password), created_at=now()))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'An account with this student ID or email already exists.')
        return {'success': True, 'message': 'Account created successfully'}

    @app.post('/login')
    def login(data: Login, db=Depends(get_db, scope='function')):
        identifier = data.student_id.strip().upper()
        throttle_key = identifier
        with login_lock:
            cutoff = now() - timedelta(minutes=15)
            failures = [t for t in login_failures.get(throttle_key, []) if t > cutoff]
            if len(failures) >= 8:
                raise HTTPException(429, 'Too many unsuccessful sign-ins. Try again in 15 minutes.')
            # Count before doing expensive work so concurrent requests cannot bypass the limit.
            login_failures[throttle_key] = failures + [now()]
            if len(login_failures) > 2000:
                for key in list(login_failures):
                    if not any(t > cutoff for t in login_failures[key]):
                        del login_failures[key]
        student = db.scalar(select(Student).where(Student.student_id == identifier).with_for_update())
        valid = verify_password(data.password, student.password_hash if student else dummy_password)
        if not student or not valid or student.account_status != 'active':
            raise HTTPException(401, 'Invalid student ID or password.')
        with login_lock:
            login_failures.pop(throttle_key, None)
        token = secrets.token_urlsafe(48)
        expires = now() + timedelta(hours=settings.session_hours)
        db.add(AuthSession(token_hash=digest(token), student_id=student.student_id, expires_at=expires))
        return {'success': True, 'access_token': token, 'token_type': 'bearer',
            'expires_at': iso_time(expires, settings), 'student': profile(student, db)}

    @app.post('/logout')
    def logout(identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        # Keep token row for challenge foreign keys, but revoke it immediately.
        # MySQL DATETIME has whole-second precision; ensure revocation is already in the past.
        auth.expires_at = now() - timedelta(seconds=1)
        for challenge in db.scalars(select(Challenge).where(Challenge.auth_token_hash == auth.token_hash, Challenge.consumed == False)):
            challenge.consumed = True
            root = db.get(VerificationAttempt, challenge.verification_id)
            root.verification_result = 'cancelled'
            root.failure_reason = 'Signed out before verification completed.'
        return {'success': True}

    @app.get('/me')
    def me(identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        return profile(student, db)

    @app.post('/register-face')
    def register_face(consent: bool = Form(...), file: UploadFile = File(...),
                      auto_capture: bool = Form(False), preview_only: bool = Form(False),
                      identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        # Lock student so simultaneous enrollment requests cannot overwrite a template.
        student = db.scalar(select(Student).where(Student.student_id == student.student_id).with_for_update())
        if not consent:
            raise HTTPException(400, 'Your consent is required before registering facial biometrics.')
        if student.face_encoding:
            raise HTTPException(409, 'Your face is already registered. Remove the existing registration first.')
        try:
            image = read_image(file)
            encoding = bio.guided_face(image) if auto_capture else bio.face(image)
        except BiometricError as exc:
            if auto_capture:
                return {'success': True, 'ready': False, 'retryable': True, 'message': str(exc)}
            reject(db, student.student_id, 'enrollment', str(exc))
        if preview_only:
            return {'success': True, 'ready': True, 'preview_only': True,
                    'message': 'Face detected. Hold still for automatic capture.'}
        student.face_encoding = encrypt_encoding(encoding, settings.biometric_key)
        student.biometric_status = 'active'
        student.consent_at = now()
        student.updated_at = now()
        audit(db, student.student_id, 'enrollment', None, result='success')
        return {'success': True, 'ready': True, 'registered': True, 'message': 'Face registered successfully'}

    @app.delete('/biometrics')
    def remove_biometrics(identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        student = db.scalar(select(Student).where(Student.student_id == student.student_id).with_for_update())
        student.face_encoding = None
        student.biometric_status = 'not_registered'
        student.consent_at = None
        student.updated_at = now()
        for c in db.scalars(select(Challenge).where(Challenge.student_id == student.student_id, Challenge.consumed == False)):
            c.consumed = True
            root = db.get(VerificationAttempt, c.verification_id)
            root.verification_result = 'cancelled'
            root.failure_reason = 'Biometric registration was removed.'
        return {'success': True, 'message': 'Biometric registration removed. Attendance records have been retained.'}

    @app.post('/attendance/start')
    def start_attendance(data: PinEntry, identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        # Serializes starts for a student, and prevents overlapping active challenges.
        student = db.scalar(select(Student).where(Student.student_id == student.student_id).with_for_update())
        failures = db.scalar(select(func.count()).select_from(VerificationAttempt).where(
            VerificationAttempt.student_id == student.student_id, VerificationAttempt.stage == 'pin',
            VerificationAttempt.verification_result == 'failed', VerificationAttempt.attempted_at > now()-timedelta(minutes=5)))
        if failures >= 5:
            raise HTTPException(429, 'Too many incorrect attendance PINs. Try again in five minutes.')
        if settings.demo_mode:
            seed_demo(db, now())
        matches = db.scalars(select(ClassSession).join(ClassSchedule).where(
            ClassSchedule.group_id == student.group_id, ClassSession.session_date == now().date(),
            ClassSession.pin_hash == digest(data.pin), ClassSession.status == 'active')).all()
        matches = [session for session in matches if session_open(session, student, db)]
        if len(matches) != 1:
            reject(db, student.student_id, 'pin', 'The PIN does not match an active class for your group.')
        session = matches[0]
        if db.scalar(select(Attendance).where(Attendance.session_id == session.session_id, Attendance.student_id == student.student_id)):
            reject(db, student.student_id, 'duplicate', 'Your attendance for this class has already been recorded.', session.session_id, 409)
        if student.biometric_status != 'active':
            reject(db, student.student_id, 'face', 'Register your face in Profile before taking attendance.', session.session_id, 409)
        for old in db.scalars(select(Challenge).where(Challenge.student_id == student.student_id, Challenge.consumed == False)):
            old.consumed = True
            root = db.get(VerificationAttempt, old.verification_id)
            root.verification_result = 'cancelled'
            root.failure_reason = 'Replaced by a new verification request.'
        attempt = audit(db, student.student_id, 'face', None, session.session_id, 'pending')
        challenge = Challenge(challenge_id=secrets.token_urlsafe(32), student_id=student.student_id,
            session_id=session.session_id, auth_token_hash=auth.token_hash, verification_id=attempt.verification_id,
            stage='face', expires_at=now()+timedelta(seconds=settings.challenge_seconds))
        db.add(challenge)
        schedule = db.get(ClassSchedule, session.schedule_id)
        course = db.get(Course, schedule.course_code)
        return {'success': True, 'challenge_id': challenge.challenge_id, 'expires_at': iso_time(challenge.expires_at, settings),
            'course_name': course.course_name, 'session_id': session.session_id, 'venue': session.venue,
            'stage': 'face', 'expires_in': settings.challenge_seconds}

    @app.post('/verify-face')
    def verify_face(challenge_id: str = Form(...), file: UploadFile = File(...),
                    auto_capture: bool = Form(False), preview_only: bool = Form(False),
                    identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        challenge, session = get_challenge(challenge_id, 'face', db, student, auth)
        try:
            image = read_image(file)
            encoding = bio.guided_face(image) if auto_capture else bio.face(image)
        except BiometricError as exc:
            if auto_capture:
                if challenge.expires_at <= now() or not session_open(session, student, db):
                    reject(db, student.student_id, 'face', 'Verification timed out. Start again.', session.session_id, 410, challenge)
                return {'success': True, 'ready': False, 'retryable': True, 'message': str(exc)}
            reject(db, student.student_id, 'face', str(exc), session.session_id, 400, challenge)
        try:
            distance = bio.distance(encoding, reference(student))
        except BiometricError as exc:
            reject(db, student.student_id, 'face', str(exc), session.session_id, 400, challenge)
        if distance >= settings.face_threshold:
            reject(db, student.student_id, 'face', 'Face not matched. Start again using your own registered face.', session.session_id, 400, challenge)
        if challenge.expires_at <= now() or not session_open(session, student, db):
            reject(db, student.student_id, 'face', 'Verification timed out. Start again.', session.session_id, 410, challenge)
        if preview_only:
            return {'success': True, 'ready': True, 'preview_only': True,
                    'message': 'Face matched. Hold still for automatic capture.'}
        challenge.stage = 'liveness'
        challenge.fingers = secrets.randbelow(5) + 1
        # An enrollment/face frame can never count as a liveness response.
        challenge.frame_hashes = json.dumps([hashlib.sha256(image.tobytes()).hexdigest()])
        root = db.get(VerificationAttempt, challenge.verification_id)
        root.stage = 'liveness'
        root.face_distance = distance
        return {'success': True, 'ready': True, 'face_verified': True, 'stage': 'liveness', 'fingers': challenge.fingers,
            'required_frames': 3, 'expires_at': iso_time(challenge.expires_at, settings),
            'message': f'Show {challenge.fingers} finger(s), palm toward the camera. Keep your face and hand fully visible anywhere in the frame; neither needs to be centered.'}

    @app.post('/liveness/frame')
    def liveness_frame(challenge_id: str = Form(...), file: UploadFile = File(...),
                       identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        challenge, session = get_challenge(challenge_id, 'liveness', db, student, auth)
        if len(json.loads(challenge.frame_hashes)) >= 60:
            reject(db, student.student_id, 'liveness', 'Too many verification frames. Start again.', session.session_id, 429, challenge)
        try:
            image = read_image(file)
            frame_hash = hashlib.sha256(image.tobytes()).hexdigest()
            hashes = json.loads(challenge.frame_hashes)
            if frame_hash in hashes:
                raise BiometricError('Use the live camera. Keep your face and hand fully visible anywhere in the frame.')
            hashes.append(frame_hash)
            challenge.frame_hashes = json.dumps(hashes)
            distance = bio.distance(bio.face(image), reference(student))
            if distance >= settings.face_threshold:
                reject(db, student.student_id, 'liveness', 'Your registered face must remain visible throughout verification.', session.session_id, 400, challenge)
            count = bio.hand(image)
            if count != challenge.fingers:
                raise BiometricError(f'Detected {count} finger(s). Show {challenge.fingers} with your palm toward the camera.')
        except BiometricError as exc:
            challenge.valid_frames = 0
            audit(db, student.student_id, 'liveness', str(exc), session.session_id)
            return {'success': True, 'complete': False, 'valid_frames': 0, 'required_frames': 3, 'message': str(exc)}
        if challenge.expires_at <= now() or not session_open(session, student, db):
            reject(db, student.student_id, 'liveness', 'The verification or class attendance window has expired. Start again.', session.session_id, 410, challenge)
        challenge.valid_frames += 1
        if challenge.valid_frames < 3:
            return {'success': True, 'complete': False, 'valid_frames': challenge.valid_frames, 'required_frames': 3,
                'message': 'Correct gesture. Hold steady; your face and hand do not need to be centered.'}
        challenge.consumed = True
        challenge.stage = 'complete'
        root = db.get(VerificationAttempt, challenge.verification_id)
        root.verification_result = 'success'
        root.stage = 'complete'
        root.failure_reason = None
        record = Attendance(student_id=student.student_id, session_id=session.session_id,
            verification_id=root.verification_id, taken_at=now(), status='Present')
        db.add(record)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            reject(db, student.student_id, 'duplicate', 'Attendance has already been recorded for this class.', session.session_id, 409)
        return {'success': True, 'complete': True, 'face_verified': True, 'liveness_verified': True,
            'attendance_id': record.attendance_id,
            'recorded_at': iso_time(record.taken_at, settings), 'message': 'Attendance accepted'}

    @app.post('/attendance/cancel/{challenge_id}')
    def cancel(challenge_id: str, identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        challenge = db.scalar(select(Challenge).where(Challenge.challenge_id == challenge_id).with_for_update())
        if challenge is None or challenge.student_id != student.student_id or challenge.auth_token_hash != auth.token_hash:
            raise HTTPException(404, 'Verification request not found.')
        if not challenge.consumed:
            challenge.consumed = True
            root = db.get(VerificationAttempt, challenge.verification_id)
            root.verification_result = 'cancelled'
            root.failure_reason = 'Cancelled by the student.'
        return {'success': True}

    @app.get('/classes')
    def classes(identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        if settings.demo_mode:
            seed_demo(db, now())
        rows = db.execute(select(ClassSession, ClassSchedule, Course).select_from(ClassSession)
            .join(ClassSchedule, ClassSession.schedule_id == ClassSchedule.schedule_id)
            .join(Course, ClassSchedule.course_code == Course.course_code).where(
            ClassSchedule.group_id == student.group_id,
            ClassSession.session_date.between(now().date(), now().date()+timedelta(days=7)))
            .order_by(ClassSession.session_date, ClassSession.start_time)).all()
        attended = set(db.scalars(select(Attendance.session_id).where(Attendance.student_id == student.student_id)))
        return [{'session_id': session.session_id, 'course_code': course.course_code, 'course_name': course.course_name,
            'date': session.session_date.isoformat(), 'start_time': session.start_time.isoformat(), 'end_time': session.end_time.isoformat(),
            'venue': session.venue, 'class_type': schedule.class_type, 'lecturer': schedule.lecturer,
            'is_open': session_open(session, student, db), 'attended': session.session_id in attended}
            for session, schedule, course in rows]

    @app.get('/attendance/history')
    def history(identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        rows = db.execute(select(Attendance, ClassSession, Course).select_from(Attendance)
            .join(ClassSession, Attendance.session_id == ClassSession.session_id)
            .join(ClassSchedule, ClassSession.schedule_id == ClassSchedule.schedule_id)
            .join(Course, ClassSchedule.course_code == Course.course_code)
            .where(Attendance.student_id == student.student_id).order_by(Attendance.taken_at.desc()).limit(200)).all()
        return [{'attendance_id': record.attendance_id, 'session_id': session.session_id,
            'course_code': course.course_code, 'course_name': course.course_name,
            'session_date': session.session_date.isoformat(), 'taken_at': iso_time(record.taken_at, settings),
            'status': record.status, 'verification_id': record.verification_id} for record, session, course in rows]

    @app.get('/attendance/summary')
    def summary(identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        if settings.demo_mode:
            seed_demo(db, now())
        rows = db.execute(select(ClassSession, Course).select_from(ClassSession)
            .join(ClassSchedule, ClassSession.schedule_id == ClassSchedule.schedule_id)
            .join(Course, ClassSchedule.course_code == Course.course_code).where(
            ClassSchedule.group_id == student.group_id, ClassSession.status != 'cancelled',
            ClassSession.session_date <= now().date())).all()
        attended = set(db.scalars(select(Attendance.session_id).where(Attendance.student_id == student.student_id)))
        counts = {}
        for session, course in rows:
            # Exclude sessions that have not ended, unless attendance was already submitted.
            ended = datetime.combine(session.session_date, session.end_time) < now()
            if ended or session.session_id in attended:
                item = counts.setdefault(course.course_code, {'course_code': course.course_code, 'course_name': course.course_name, 'attended': 0, 'total': 0})
                item['total'] += 1
                item['attended'] += int(session.session_id in attended)
        return [{**item, 'percentage': round(item['attended'] / item['total'] * 100, 1)} for item in counts.values()]

    @app.get('/verification-attempts')
    def attempts(identity=Depends(authenticated), db=Depends(get_db, scope='function')):
        student, auth = identity
        expired = db.scalars(select(Challenge).where(Challenge.student_id == student.student_id,
            Challenge.consumed == False, Challenge.expires_at <= now())).all()
        for c in expired:
            c.consumed = True
            root = db.get(VerificationAttempt, c.verification_id)
            root.verification_result = 'failed'
            root.failure_reason = 'Verification timed out.'
        db.flush()
        rows = db.scalars(select(VerificationAttempt).where(VerificationAttempt.student_id == student.student_id)
            .order_by(VerificationAttempt.verification_id.desc()).limit(100))
        return [{'verification_id': row.verification_id, 'result': row.verification_result, 'stage': row.stage,
            'attempted_at': iso_time(row.attempted_at, settings), 'failure_reason': row.failure_reason} for row in rows]

    return app

app = create_app()
