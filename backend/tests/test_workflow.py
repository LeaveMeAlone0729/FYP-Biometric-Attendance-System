"""Contract tests use synthetic biometric results; they do not claim camera accuracy."""
import io
import json
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from biometrics import Biometrics, BiometricError, finger_count
from config import Settings
from database import make_sessions
from demo import seed_demo
from models import Base, Student, Challenge, Attendance, VerificationAttempt, ClassSession, AuthSession
from security import hash_password, encrypt_encoding, decrypt_encoding, digest, verify_password

class SyntheticImage:
    def __init__(self, value): self.value = value
    def tobytes(self): return self.value

class SyntheticBiometrics:
    def __init__(self): self.gesture = 1
    def decode(self, data): return SyntheticImage(data)
    def face(self, image):
        if image.value.startswith(b'no-face'): raise BiometricError('Keep exactly one face visible in the camera frame.')
        return [1.0] * 128 if image.value.startswith(b'other-face') else [0.0] * 128
    def guided_face(self, image): return self.face(image)
    def hand(self, image):
        if image.value.startswith(b'no-hand'): raise BiometricError('Show one hand next to your face.')
        return self.gesture
    def distance(self, value, reference): return float(np.linalg.norm(np.array(value) - np.array(reference)))
    def close(self): pass

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password('test-password')
        cls.key = Fernet.generate_key().decode()

    def setUp(self):
        self.current = datetime(2026, 10, 20, 12, 0, 0)
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        @event.listens_for(self.engine, 'connect')
        def foreign_keys(connection, record): connection.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        self.sessions = make_sessions(self.engine)
        self.settings = replace(Settings(), demo_mode=True, biometric_key=self.key)
        with self.sessions.begin() as db:
            seed_demo(db, self.current)
            db.add(Student(student_id='TEST001', group_id=1, name='Test Student', email='student@example.test',
                password_hash=self.password_hash, face_encoding=encrypt_encoding([0.0]*128, self.key),
                biometric_status='active', consent_at=self.current, created_at=self.current))
            db.add(Student(student_id='TEST002', group_id=2, name='Other Student', email='other@example.test',
                password_hash=self.password_hash, created_at=self.current))
        self.bio = SyntheticBiometrics()
        self.app = create_app(self.settings, self.engine, self.bio, lambda: self.current)
        self.client = TestClient(self.app, client=('127.0.0.1', 50000))
        response = self.client.post('/login', json={'student_id':'TEST001', 'password':'test-password'})
        self.assertEqual(response.status_code, 200, response.text)
        self.headers = {'Authorization': 'Bearer ' + response.json()['access_token']}

    def tearDown(self):
        self.client.close(); self.engine.dispose()

    def start(self, pin='123456'):
        response = self.client.post('/attendance/start', json={'pin':pin}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['challenge_id']

    def image(self, endpoint, identifier, data=b'neutral'):
        return self.client.post(endpoint, data={'challenge_id':identifier}, files={'file':('capture.jpg',data,'image/jpeg')}, headers=self.headers)

    def face(self, identifier):
        response = self.image('/verify-face', identifier)
        self.assertEqual(response.status_code, 200, response.text)
        self.bio.gesture = response.json()['fingers']
        return response

    def count_attendance(self):
        with self.sessions() as db: return db.scalar(select(func.count()).select_from(Attendance))

    def complete(self):
        identifier = self.start(); self.face(identifier)
        for index in range(3):
            response = self.image('/liveness/frame', identifier, f'live-frame-{index}'.encode())
            self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['complete'])
        return identifier, response

    def test_attendance_requires_pin_face_then_three_live_frames(self):
        identifier = self.start()
        self.assertEqual(self.count_attendance(), 0)
        self.face(identifier)
        self.assertEqual(self.count_attendance(), 0)
        for index in range(3):
            response = self.image('/liveness/frame', identifier, f'frame-{index}'.encode())
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['complete'], index == 2)
            self.assertEqual(self.count_attendance(), int(index == 2))
        self.assertTrue(response.json()['liveness_verified'])
        self.assertEqual(len(self.client.get('/attendance/history', headers=self.headers).json()), 1)
        with self.sessions() as db:
            attendance = db.scalar(select(Attendance))
            self.assertEqual(db.get(VerificationAttempt, attendance.verification_id).verification_result, 'success')

    def test_wrong_group_pin_is_rejected_and_logged(self):
        response = self.client.post('/attendance/start', json={'pin':'222222'}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        attempts = self.client.get('/verification-attempts', headers=self.headers).json()
        self.assertEqual(attempts[0]['stage'], 'pin')
        self.assertEqual(attempts[0]['result'], 'failed')

    def test_pin_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/attendance/start', json={'pin':'999999'}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/attendance/start', json={'pin':'123456'}, headers=self.headers).status_code, 429)

    def test_malformed_pin_is_rejected(self):
        self.assertEqual(self.client.post('/attendance/start', json={'pin':'abc'}, headers=self.headers).status_code, 422)

    def test_inactive_session_rejected(self):
        with self.sessions.begin() as db:
            for session in db.scalars(select(ClassSession)): session.status = 'closed'
        self.assertEqual(self.client.post('/attendance/start', json={'pin':'123456'}, headers=self.headers).status_code, 400)

    def test_outside_class_hours_rejected(self):
        from datetime import time
        with self.sessions.begin() as db:
            for session in db.scalars(select(ClassSession)): session.end_time = time(10)
        self.assertEqual(self.client.post('/attendance/start', json={'pin':'123456'}, headers=self.headers).status_code, 400)

    def test_unknown_or_missing_auth_rejected(self):
        self.assertEqual(self.client.get('/me').status_code, 401)
        self.assertEqual(self.client.get('/attendance/history', headers={'Authorization':'Bearer fake'}).status_code, 401)

    def test_login_only_needs_credentials_and_new_session_can_verify(self):
        login = self.client.post('/login', json={'student_id':'TEST001','password':'test-password'})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertNotIn('registered_device', login.json())
        self.headers = {'Authorization':'Bearer '+login.json()['access_token']}
        self.assertNotIn('registered_device', self.client.get('/me', headers=self.headers).json())
        _, result = self.complete()
        self.assertNotIn('device_verified', result.json())
        self.assertNotIn('network_verified', result.json())

    def test_face_registration_and_attendance_work_from_any_client_address(self):
        with TestClient(self.app, client=('203.0.113.5', 50000)) as remote:
            self.assertEqual(remote.delete('/biometrics', headers=self.headers).status_code, 200)
            response = remote.post('/register-face', data={'consent':'true'},
                files={'file':('face.jpg', b'enrollment', 'image/jpeg')}, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            with patch.object(self, 'client', remote):
                self.complete()
            self.assertEqual(self.count_attendance(), 1)

    def test_challenge_stays_bound_to_the_login_that_started_it(self):
        identifier = self.start()
        login = self.client.post('/login', json={'student_id':'TEST001','password':'test-password'})
        response = self.client.post('/verify-face', data={'challenge_id':identifier},
            files={'file':('face.jpg',b'neutral')},
            headers={'Authorization':'Bearer '+login.json()['access_token']})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.count_attendance(), 0)

    def test_wrong_face_never_records_attendance(self):
        identifier = self.start()
        self.assertEqual(self.image('/verify-face', identifier, b'other-face').status_code, 400)
        self.assertEqual(self.count_attendance(), 0)
        self.assertEqual(self.image('/verify-face', identifier).status_code, 409)

    def test_missing_face_is_rejected(self):
        identifier = self.start()
        self.assertEqual(self.image('/verify-face', identifier, b'no-face').status_code, 400)

    def auto_face(self, identifier, data=b'neutral', preview=False):
        return self.client.post('/verify-face',
            data={'challenge_id': identifier, 'auto_capture': 'true', 'preview_only': str(preview).lower()},
            files={'file': ('capture.jpg', data, 'image/jpeg')}, headers=self.headers)

    def test_auto_scan_can_recover_then_complete_without_preview_recording_attendance(self):
        identifier = self.start()
        response = self.auto_face(identifier, b'no-face')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['ready'])
        with self.sessions() as db:
            self.assertFalse(db.get(Challenge, identifier).consumed)
            self.assertEqual(db.get(Challenge, identifier).stage, 'face')
        response = self.auto_face(identifier, preview=True)
        self.assertTrue(response.json()['ready'])
        self.assertTrue(response.json()['preview_only'])
        self.assertEqual(self.count_attendance(), 0)
        with self.sessions() as db:
            self.assertEqual(db.get(Challenge, identifier).stage, 'face')
        response = self.auto_face(identifier)
        self.assertTrue(response.json()['face_verified'])
        self.bio.gesture = response.json()['fingers']
        for index in range(3):
            response = self.image('/liveness/frame', identifier, f'auto-live-{index}'.encode())
            self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['complete'])
        self.assertEqual(self.count_attendance(), 1)

    def test_auto_scan_identity_mismatch_is_terminal_even_in_preview(self):
        identifier = self.start()
        self.assertEqual(self.auto_face(identifier, b'other-face', preview=True).status_code, 400)
        self.assertEqual(self.auto_face(identifier).status_code, 409)
        self.assertEqual(self.count_attendance(), 0)

    def test_auto_scan_still_checks_expiry_after_slow_detection(self):
        identifier = self.start()
        def slow_detection(image):
            self.current += timedelta(seconds=91)
            return [0.0] * 128
        self.bio.guided_face = slow_detection
        self.assertEqual(self.auto_face(identifier, preview=True).status_code, 410)
        self.assertEqual(self.count_attendance(), 0)

    def test_auto_enrollment_requires_consent_and_preview_never_saves_a_template(self):
        with self.sessions.begin() as db:
            student = db.get(Student, 'TEST001')
            student.face_encoding = None
            student.biometric_status = 'not_registered'
            student.consent_at = None
        def enroll(image, consent='true', preview='true'):
            return self.client.post('/register-face',
                data={'consent': consent, 'auto_capture': 'true', 'preview_only': preview},
                files={'file': ('capture.jpg', image, 'image/jpeg')}, headers=self.headers)
        self.assertEqual(enroll(b'neutral', consent='false').status_code, 400)
        self.assertFalse(enroll(b'no-face').json()['ready'])
        self.assertTrue(enroll(b'neutral').json()['ready'])
        with self.sessions() as db:
            self.assertIsNone(db.get(Student, 'TEST001').face_encoding)
            self.assertIsNone(db.get(Student, 'TEST001').consent_at)
        self.assertTrue(enroll(b'neutral', preview='false').json()['registered'])
        with self.sessions() as db:
            self.assertIsNotNone(db.get(Student, 'TEST001').face_encoding)
            self.assertIsNotNone(db.get(Student, 'TEST001').consent_at)

    def test_liveness_cannot_be_called_before_face(self):
        identifier = self.start()
        self.assertEqual(self.image('/liveness/frame', identifier, b'frame').status_code, 409)
        self.assertEqual(self.count_attendance(), 0)

    def test_wrong_gesture_resets_consecutive_count_and_is_logged(self):
        identifier = self.start(); self.face(identifier)
        self.image('/liveness/frame', identifier, b'frame-one')
        self.bio.gesture = self.bio.gesture % 5 + 1
        response = self.image('/liveness/frame', identifier, b'wrong-gesture')
        self.assertFalse(response.json()['complete'])
        self.assertEqual(response.json()['valid_frames'], 0)
        self.assertEqual(self.count_attendance(), 0)
        with self.sessions() as db:
            self.assertTrue(db.scalar(select(VerificationAttempt).where(VerificationAttempt.verification_result=='failed', VerificationAttempt.stage=='liveness')))

    def test_face_must_remain_visible_during_gesture(self):
        identifier = self.start(); self.face(identifier)
        response = self.image('/liveness/frame', identifier, b'no-face-live')
        self.assertEqual(response.json()['valid_frames'], 0)
        self.assertEqual(self.count_attendance(), 0)

    def test_face_substitution_closes_challenge(self):
        identifier = self.start(); self.face(identifier)
        self.assertEqual(self.image('/liveness/frame', identifier, b'other-face-live').status_code, 400)
        self.assertEqual(self.image('/liveness/frame', identifier, b'legit-frame').status_code, 409)

    def test_same_frame_cannot_be_replayed(self):
        identifier = self.start(); self.face(identifier)
        self.image('/liveness/frame', identifier, b'one-identical-frame')
        response = self.image('/liveness/frame', identifier, b'one-identical-frame')
        self.assertEqual(response.json()['valid_frames'], 0)
        self.assertEqual(self.count_attendance(), 0)

    def test_challenge_expiry(self):
        identifier = self.start()
        self.current += timedelta(seconds=91)
        self.assertEqual(self.image('/verify-face', identifier).status_code, 410)
        self.assertEqual(self.count_attendance(), 0)

    def test_consumed_challenge_and_duplicate_class_rejected(self):
        identifier, response = self.complete()
        self.assertEqual(self.image('/liveness/frame', identifier, b'extra').status_code, 409)
        self.assertEqual(self.client.post('/attendance/start', json={'pin':'123456'}, headers=self.headers).status_code, 409)
        self.assertEqual(self.count_attendance(), 1)

    def test_challenges_cannot_cross_student_accounts(self):
        identifier = self.start()
        login = self.client.post('/login', json={'student_id':'TEST002','password':'test-password'})
        response = self.client.post('/verify-face', data={'challenge_id':identifier}, files={'file':('x.jpg',b'neutral')},
            headers={'Authorization':'Bearer '+login.json()['access_token']})
        self.assertEqual(response.status_code, 403)
        history = self.client.get('/attendance/history', headers={'Authorization':'Bearer '+login.json()['access_token']})
        self.assertEqual(history.json(), [])

    def test_logout_revokes_session_and_cancels_challenge(self):
        identifier = self.start()
        self.assertEqual(self.client.post('/logout', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/me', headers=self.headers).status_code, 401)
        with self.sessions() as db: self.assertTrue(db.get(Challenge, identifier).consumed)

    def test_cancel_never_records_attendance(self):
        identifier = self.start(); self.face(identifier)
        self.assertEqual(self.client.post('/attendance/cancel/'+identifier, headers=self.headers).status_code, 200)
        self.assertEqual(self.count_attendance(), 0)

    def test_enrollment_requires_consent_and_encrypts_template(self):
        with self.sessions.begin() as db:
            student = db.get(Student, 'TEST001'); student.face_encoding = None; student.biometric_status = 'not_registered'
        files = {'file':('face.jpg', b'enrollment', 'image/jpeg')}
        self.assertEqual(self.client.post('/register-face', data={'consent':'false'}, files=files, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/register-face', data={'consent':'true'}, files=files, headers=self.headers).status_code, 200)
        with self.sessions() as db:
            student = db.get(Student, 'TEST001')
            self.assertEqual(decrypt_encoding(student.face_encoding, self.key), [0.0]*128)
            self.assertNotIn('[0.0', student.face_encoding)
            self.assertIsNotNone(student.consent_at)
        self.assertEqual(self.client.post('/register-face', data={'consent':'true'}, files=files, headers=self.headers).status_code, 409)

    def test_remove_template_cancels_pending_verification_and_keeps_history(self):
        self.complete()
        identifier = self.start('654321')
        self.assertEqual(self.client.delete('/biometrics', headers=self.headers).status_code, 200)
        with self.sessions() as db:
            self.assertIsNone(db.get(Student,'TEST001').face_encoding)
            self.assertTrue(db.get(Challenge, identifier).consumed)
        self.assertEqual(self.count_attendance(), 1)

    def test_live_course_history_and_percentage_are_scoped_to_student(self):
        self.complete()
        classes = self.client.get('/classes', headers=self.headers)
        self.assertEqual(classes.status_code, 200, classes.text)
        self.assertEqual(len(classes.json()), 2)
        summary = self.client.get('/attendance/summary', headers=self.headers).json()
        lab = next(x for x in summary if x['course_code']=='DEMO101')
        self.assertEqual(lab['attended'], 1); self.assertEqual(lab['total'], 4); self.assertEqual(lab['percentage'], 25.0)

    def test_registration_hashes_password_and_validates_duplicate_email(self):
        data = {'student_id':'NEW001','name':'New Student','email':'new@example.test','password':'new-password','group_id':1}
        response = self.client.post('/register', json=data)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.client.post('/register', json=data).status_code, 409)
        with self.sessions() as db:
            student = db.get(Student,'NEW001')
            self.assertNotEqual(student.password_hash, data['password'])
            self.assertTrue(verify_password(data['password'], student.password_hash))

    def test_production_disables_self_assigned_groups_and_signup(self):
        prod = create_app(replace(self.settings, demo_mode=False), self.engine, self.bio, lambda:self.current)
        with TestClient(prod, client=('127.0.0.1',50000)) as client:
            self.assertEqual(client.get('/groups').json(), [])
            self.assertEqual(client.post('/register', json={'student_id':'NEW001','name':'Student','email':'new@example.test','password':'long-password','group_id':1}).status_code, 403)

    def test_expired_session_rejected(self):
        self.current += timedelta(hours=9)
        self.assertEqual(self.client.get('/me', headers=self.headers).status_code, 401)

class ImageProcessingTests(unittest.TestCase):
    def test_gesture_face_check_accepts_either_side_without_centering(self):
        detector = SimpleNamespace(face_locations=lambda image, model: [],
            face_encodings=lambda image, known_face_locations: [np.zeros(128)])
        bio = Biometrics()
        image = np.zeros((640, 480, 3), dtype=np.uint8)
        with patch.dict(sys.modules, {'face_recognition': detector}):
            for box in ((160, 180, 360, 40), (160, 440, 360, 300)):
                with self.subTest(box=box):
                    detector.face_locations = lambda image, model, box=box: [box]
                    # The gesture stage uses face(), retaining identity matching
                    # without the positioning constraints of guided_face().
                    self.assertEqual(len(bio.face(image)), 128)
                    with self.assertRaisesRegex(BiometricError, 'Center your face'):
                        bio.guided_face(image)

    def test_guided_face_rejects_off_center_or_badly_sized_faces(self):
        detector = SimpleNamespace(face_locations=lambda image, model: [(220, 310, 420, 170)],
            face_encodings=lambda image, known_face_locations: [np.zeros(128)])
        bio = Biometrics()
        image = np.zeros((640, 480, 3), dtype=np.uint8)
        with patch.dict(sys.modules, {'face_recognition': detector}):
            self.assertEqual(len(bio.guided_face(image)), 128)
            for box, message in (
                ((40, 180, 240, 40), 'Center your face'),
                ((120, 450, 520, 30), 'farther away'),
                ((270, 290, 370, 190), 'Move closer'),
            ):
                detector.face_locations = lambda image, model, box=box: [box]
                with self.assertRaisesRegex(BiometricError, message): bio.guided_face(image)

    def test_finger_geometry_is_mirror_invariant(self):
        # Synthetic landmarks exercise handedness independence without collecting biometrics.
        for count in range(1, 6):
            points = [SimpleNamespace(x=0.0, y=0.0, z=0.0) for _ in range(21)]
            for index, (base, joint, tip) in enumerate(((5,6,8),(9,10,12),(13,14,16),(17,18,20))):
                x = (index + 1) * .2
                points[base] = SimpleNamespace(x=x, y=1.0, z=0.0)
                points[joint] = SimpleNamespace(x=x, y=2.0, z=0.0)
                points[tip] = SimpleNamespace(x=x, y=3.0 if index < min(count,4) else 1.2, z=0.0)
            points[1] = SimpleNamespace(x=-.2,y=.2,z=0.0)
            points[2] = SimpleNamespace(x=-.4,y=.4,z=0.0)
            points[3] = SimpleNamespace(x=-.6,y=.6,z=0.0)
            points[4] = SimpleNamespace(x=-1.0,y=1.0,z=0.0) if count==5 else SimpleNamespace(x=.1,y=1.0,z=0.0)
            self.assertEqual(finger_count(points),count)
            mirrored = [SimpleNamespace(x=-p.x,y=p.y,z=p.z) for p in points]
            self.assertEqual(finger_count(mirrored),count)

    def test_invalid_and_oversized_images_rejected(self):
        bio = Biometrics()
        with self.assertRaises(BiometricError): bio.decode(b'not-an-image')
        with self.assertRaises(BiometricError): bio.decode(b'x'*(6*1024*1024+1))

    def test_real_image_decoding_and_face_rejection(self):
        buffer = io.BytesIO(); Image.new('RGB',(300,300),(100,100,100)).save(buffer,format='JPEG')
        bio = Biometrics(); image = bio.decode(buffer.getvalue())
        self.assertEqual(image.shape, (300,300,3))
        with self.assertRaises(BiometricError): bio.face(image)

    def test_real_mediapipe_model_runs_and_rejects_missing_hand(self):
        bio = Biometrics()
        if not bio.model_path.exists(): self.skipTest('Run setup.py to download the official MediaPipe model.')
        with self.assertRaises(BiometricError): bio.hand(np.zeros((300,300,3), dtype=np.uint8))
        bio.close()

if __name__ == '__main__': unittest.main()
