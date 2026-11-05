"""Passive PAD regressions. Synthetic tests do not measure camera accuracy."""

import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.biometrics.inference import BiometricError
from modules.biometrics.passive_liveness import new_state, read_state
from modules.biometrics.presentation import face_crop, real_probability, validate_scores
from models import AuthSession, Challenge, Student, ClassSession
from modules.devices.service import DeviceRegistrationError
from security import digest
from services.attendance import record_verified_attendance
import test_workflow as workflow


class PassiveEvidenceTests(unittest.TestCase):
    def test_both_models_and_ensemble_must_pass(self):
        self.assertEqual(validate_scores([0.8, 0.8]), [0.8, 0.8])
        self.assertEqual(validate_scores([0.65, 0.95]), [0.65, 0.95])
        for scores in ([0.64, 1.0], [1.0, 0.64], [0.79, 0.8]):
            with self.subTest(scores=scores), self.assertRaises(BiometricError):
                validate_scores(scores)
        for scores in (None, [], [1], [1, 1, 1], [float('nan'), 1], [float('inf'), 1], [-0.1, 1], [1.1, 1], ['1', 1], [True, 1]):
            with self.subTest(scores=scores), self.assertRaises(RuntimeError):
                validate_scores(scores)

    def test_state_requires_valid_face_and_unique_passing_frame_evidence(self):
        state = new_state([0.99, 0.98])
        self.assertEqual(state['frames'], [])
        self.assertEqual(read_state(json.dumps(state)), state)
        for index in range(3):
            state['frames'].append({'hash': f'{index:064x}', 'scores': [0.9, 0.9]})
        self.assertEqual(read_state(json.dumps(state)), state)
        bad_states = []
        for location in ('face', 'hand'):
            bad = copy.deepcopy(state)
            if location == 'face':
                bad['face_scores'] = [0.1, 0.99]
            else:
                bad['frames'][0]['scores'] = [0.1, 0.99]
            bad_states.append(bad)
        bad = copy.deepcopy(state)
        bad['frames'][1]['hash'] = bad['frames'][0]['hash']
        bad_states.append(bad)
        bad = copy.deepcopy(state)
        bad['frames'].append({'hash': 'f' * 64, 'scores': [0.9, 0.9]})
        bad_states.append(bad)
        bad = copy.deepcopy(state)
        bad['frames'][0]['hash'] = 'client-claimed-pass'
        bad_states.append(bad)
        for bad in bad_states:
            self.assertIsNone(read_state(json.dumps(bad)))
        for value in (None, '', 'null', '{}', '[1,2]', '{"version":1,"complete":true}'):
            self.assertIsNone(read_state(value))

    def test_pad_preprocessing_uses_bgr_pixels_and_class_one(self):
        image = np.zeros((120, 160, 3), dtype=np.uint8)
        image[:, :] = [10, 20, 30]
        tensor = face_crop(image, (25, 105, 85, 45), 2.7)
        self.assertEqual(tensor.shape, (1, 3, 80, 80))
        self.assertEqual(tensor[0, :, 0, 0].tolist(), [30, 20, 10])
        self.assertGreater(real_probability([[0, 8, 0]]), 0.99)
        self.assertLess(real_probability([[8, 0, 0]]), 0.01)
        for output in ([[float('nan'), 0, 0]], [[1, 2]]):
            with self.assertRaises(RuntimeError):
                real_probability(output)


class PresentationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow.WorkflowTests.setUpClass()

    def setUp(self):
        self.fixture = workflow.WorkflowTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def test_face_then_three_passive_hand_frames_complete_without_facial_actions(self):
        f = self.fixture
        identifier = f.start()
        response = f.face(identifier).json()
        self.assertEqual(response['liveness_step'], 'hand')
        self.assertTrue(response['anti_spoof_verified'])
        self.assertNotIn('face_action', response)
        for index in range(3):
            response = f.image('/liveness/frame', identifier, f'genuine-{index}'.encode())
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['complete'], index == 2)
            self.assertEqual(f.count_attendance(), int(index == 2))
            result = f.client.get(f'/verification/{identifier}', headers=f.headers).json()
            self.assertEqual(result['face_liveness_verified'], index == 2)
        with f.sessions() as db:
            state = read_state(db.get(Challenge, identifier).face_liveness_state)
            self.assertEqual(len(state['frames']), 3)

    def test_photo_and_video_fail_face_preview_and_final_matching(self):
        f = self.fixture
        identifier = f.start()
        for frame in (b'photo-on-phone', b'video-on-phone'):
            for preview in (True, False):
                response = f.auto_face(identifier, frame, preview=preview)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertFalse(response.json()['ready'])
                with f.sessions() as db:
                    self.assertEqual(db.get(Challenge, identifier).stage, 'face')
        response = f.image('/verify-face', identifier, b'screen-replay')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(f.count_attendance(), 0)

    def test_screen_replacement_resets_all_consecutive_evidence_and_can_recover(self):
        f = self.fixture
        identifier = f.start()
        f.face(identifier)
        for index in range(2):
            f.image('/liveness/frame', identifier, f'genuine-{index}'.encode())
        response = f.image('/liveness/frame', identifier, b'screen-replacement')
        self.assertEqual(response.json()['valid_frames'], 0)
        self.assertFalse(response.json()['complete'])
        with f.sessions() as db:
            self.assertEqual(read_state(db.get(Challenge, identifier).face_liveness_state)['frames'], [])
        self.assertEqual(f.count_attendance(), 0)
        for index in range(3):
            response = f.image('/liveness/frame', identifier, f'recovered-{index}'.encode())
        self.assertTrue(response.json()['complete'])
        self.assertEqual(f.count_attendance(), 1)

    def test_unavailable_or_invalid_inference_fails_closed_at_face_and_hand(self):
        f = self.fixture
        identifier = f.start()
        for frame in (b'pad-unavailable', b'pad-invalid'):
            self.assertEqual(f.auto_face(identifier, frame).status_code, 503)
        f.face(identifier)
        for frame in (b'pad-unavailable-hand', b'pad-invalid-hand'):
            self.assertEqual(f.image('/liveness/frame', identifier, frame).status_code, 503)
        self.assertEqual(f.count_attendance(), 0)

    def test_client_flags_cannot_override_screen_detection(self):
        f = self.fixture
        identifier = f.start()
        f.face(identifier)
        for index in range(3):
            response = f.client.post('/liveness/frame', headers=f.headers,
                data={'challenge_id': identifier, 'anti_spoof_verified': 'true', 'face_liveness_verified': 'true', 'valid_frames': '3', 'real_scores': '[1,1]'},
                files={'file': ('frame.jpg', f'video-claimed-pass-{index}'.encode(), 'image/jpeg')})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['valid_frames'], 0)
            self.assertFalse(response.json()['complete'])
        self.assertEqual(f.count_attendance(), 0)

    def test_legacy_missing_or_incomplete_evidence_cannot_write_attendance(self):
        f = self.fixture
        for state in (None, '{"version":1,"complete":true}', json.dumps(new_state([0.99, 0.99]))):
            identifier = f.start()
            f.face(identifier)
            with f.sessions.begin() as db:
                challenge = db.get(Challenge, identifier)
                challenge.face_liveness_state = state
                challenge.valid_frames = 3
            self.assertEqual(f.image('/liveness/frame', identifier, b'legacy-bypass').status_code, 409)
            with f.sessions.begin() as db:
                challenge = db.get(Challenge, identifier)
                student = db.get(Student, 'TEST001')
                session = db.get(ClassSession, challenge.session_id)
                auth = db.get(AuthSession, digest(f.headers['Authorization'].split()[1]))
                with self.assertRaises(DeviceRegistrationError) as error:
                    record_verified_attendance(f.app.state.context, db, student, challenge, session,
                        auth=auth, request_scope={'client': ('192.0.2.10', 50000)})
                self.assertEqual(error.exception.code, 'ATTENDANCE_BIOMETRICS_REQUIRED')
        self.assertEqual(f.count_attendance(), 0)
