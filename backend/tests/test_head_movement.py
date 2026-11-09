"""Head-motion geometry and isolated workflow checks; no camera accuracy claims."""
import math
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Challenge
from modules.biometrics.head_movement import RuntimeHeadMovement, pose_matches, challenge_actions, RANDOM_ACTIONS
from modules.biometrics.inference import head_angles, expression_scores, Biometrics, BiometricError
import test_workflow as workflow


class HeadGeometryTests(unittest.TestCase):
    def test_action_selection_uses_secure_sampling_and_excludes_eye_closure_holds(self):
        with patch('modules.biometrics.head_movement.secrets.SystemRandom') as generator:
            generator.return_value.sample.return_value = ['blink', 'turn_right', 'look_up']
            self.assertEqual(challenge_actions(), ['blink', 'turn_right', 'look_up'])
            generator.return_value.sample.assert_called_once_with(RANDOM_ACTIONS, 3)
        self.assertNotIn('close_eyes', RANDOM_ACTIONS)
        self.assertNotIn('open_mouth', RANDOM_ACTIONS)
        self.assertEqual(len(RANDOM_ACTIONS), len(set(RANDOM_ACTIONS)))

    def test_expression_scores_require_valid_bilateral_eyes_without_jaw_output(self):
        categories = [SimpleNamespace(category_name=name, score=score) for name, score in
                      [('eyeBlinkLeft', 0.1), ('eyeBlinkRight', 0.2)]]
        self.assertEqual(expression_scores(categories), {'blink_left': 0.1, 'blink_right': 0.2})
        with self.assertRaises(RuntimeError):
            expression_scores(categories[:1])
        categories[0].score = float('nan')
        with self.assertRaises(RuntimeError):
            expression_scores(categories)

    def test_transform_reports_signed_turns_without_translation_or_scale_effects(self):
        for degrees in (-30, 0, 30):
            angle = math.radians(degrees)
            matrix = np.eye(4)
            matrix[:3, :3] = np.array([[math.cos(angle), 0, math.sin(angle)],
                                      [0, 1, 0], [-math.sin(angle), 0, math.cos(angle)]]) * 1.5
            matrix[:3, 3] = [10, 20, -40]
            pose = head_angles(matrix)
            self.assertAlmostEqual(pose['yaw'], degrees)
            self.assertAlmostEqual(pose['pitch'], 0)
            self.assertAlmostEqual(pose['roll'], 0)
        for matrix in (np.eye(3), np.zeros((4, 4)), np.full((4, 4), float('nan'))):
            with self.assertRaises(RuntimeError):
                head_angles(matrix)

    def test_direction_and_pitch_limits_cannot_be_satisfied_by_tilt_or_invalid_values(self):
        neutral = dict(blink_left=0, blink_right=0)
        for action, yaw in [('look_straight', 0), ('turn_left', 25), ('turn_right', -25)]:
            self.assertTrue(pose_matches(action, dict(yaw=yaw, pitch=0, roll=0, **neutral)))
        for pose in (dict(yaw=-25, pitch=0, roll=0), dict(yaw=25, pitch=30, roll=0),
                     dict(yaw=25, pitch=0, roll=30), dict(yaw=float('nan'), pitch=0, roll=0), None):
            self.assertFalse(pose_matches('turn_left', None if pose is None else {**neutral, **pose}))
        for action, pitch in [('look_up', -20), ('look_down', 20)]:
            self.assertTrue(pose_matches(action, dict(yaw=0, pitch=pitch, roll=0, **neutral)))
        for pitch in (-12, 12):
            self.assertFalse(pose_matches('look_straight', dict(yaw=0, pitch=pitch, roll=0, **neutral)))
        self.assertFalse(pose_matches('open_mouth', dict(yaw=0, pitch=0, roll=0, **neutral)))
        self.assertTrue(pose_matches('look_straight', dict(yaw=0, pitch=0, roll=0, mouth_open=1, **neutral)))
        self.assertFalse(pose_matches('look_straight', dict(yaw=0, pitch=0, roll=0, blink_left=0.9, blink_right=0.9)))

    def test_real_model_rejects_blank_scene(self):
        detector = Biometrics()
        try:
            with self.assertRaisesRegex(BiometricError, 'exactly one'):
                detector.head_pose(np.zeros((300, 300, 3), dtype=np.uint8))
        finally:
            detector.close()


class HeadWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow.WorkflowTests.setUpClass()

    def setUp(self):
        self.f = workflow.WorkflowTests()
        self.f.setUp()
        self.frame = 0

    def tearDown(self):
        self.f.tearDown()

    def send(self, identifier, action='look_straight', **fields):
        self.frame += 1
        self.f.current += timedelta(milliseconds=500)
        return self.f.client.post('/verify-face', headers=self.f.headers,
            data={'challenge_id': identifier, 'auto_capture': 'true', **fields},
            files={'file': ('frame.jpg', f'head-{action}-{self.frame}'.encode(), 'image/jpeg')})

    def test_head_sequence_must_finish_before_fingers_and_never_records_attendance_itself(self):
        identifier = self.f.start()
        with patch('modules.biometrics.head_movement.challenge_actions', return_value=['turn_right', 'blink', 'look_down']):
            response = self.send(identifier)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['head_action'], 'look_straight')
        self.assertNotIn('face_verified', response.json())
        self.assertEqual(self.f.image('/liveness/frame', identifier).status_code, 409)
        observed = [response.json()['head_action']]
        blink_frames = iter(('blink_open', 'blink_closed', 'blink_reopen'))
        while not response.json().get('face_verified'):
            action = response.json()['head_action']
            if action == 'blink':
                action = next(blink_frames)
            response = self.send(identifier, action)
            self.assertEqual(response.status_code, 200, response.text)
            if response.json().get('head_action') and response.json()['head_action'] != observed[-1]:
                observed.append(response.json()['head_action'])
        self.assertEqual(observed, ['look_straight', 'turn_right', 'look_straight', 'blink', 'look_straight', 'look_down', 'look_straight'])
        self.assertTrue(response.json()['head_movement_verified'])
        self.assertEqual(response.json()['stage'], 'liveness')
        self.assertEqual(self.f.count_attendance(), 0)
        with self.f.sessions() as db:
            challenge = db.get(Challenge, identifier)
            self.assertIsNone(self.f.app.state.context.runtime_head.read(challenge))
            self.assertTrue(self.f.app.state.context.runtime_liveness.read(challenge)['head_verified'])

    def test_forged_success_fields_and_preview_flag_cannot_skip_head_actions(self):
        identifier = self.f.start()
        for _ in range(8):
            response = self.send(identifier, head_movement_verified='true', head_action='complete',
                                 face_verified='true', valid_frames='3', yaw='25', preview_only='false')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['liveness_step'], 'head')
            self.assertNotIn('face_verified', response.json())
        response = self.send(identifier, preview_only='true')
        self.assertEqual(response.json()['liveness_step'], 'head')
        with self.f.sessions() as db:
            self.assertEqual(db.get(Challenge, identifier).stage, 'face')
        self.assertEqual(self.f.count_attendance(), 0)

    def begin_blink(self):
        identifier = self.f.start()
        with patch('modules.biometrics.head_movement.challenge_actions', return_value=['blink', 'turn_left', 'look_up']):
            self.send(identifier)
        response = self.send(identifier)
        self.assertEqual(response.json()['head_action'], 'blink')
        return identifier

    def test_brief_blink_requires_open_blink_and_reopened_eyes(self):
        identifier = self.begin_blink()
        self.assertEqual(self.send(identifier, 'blink_open').json()['head_step'], 2)
        closed = self.send(identifier, 'blink_closed')
        self.assertEqual(closed.json()['head_step'], 2)
        self.assertEqual(closed.json()['held_frames'], 1)
        reopened = self.send(identifier, 'blink_reopen')
        self.assertEqual(reopened.json()['head_step'], 3)
        self.assertEqual(reopened.json()['head_action'], 'look_straight')
        self.assertEqual(self.f.count_attendance(), 0)

    def test_closed_eyes_alone_or_a_sustained_hold_cannot_complete_blink(self):
        identifier = self.begin_blink()
        self.send(identifier, 'blink_closed')
        opened = self.send(identifier, 'blink_reopen')
        self.assertEqual(opened.json()['head_step'], 2)
        self.send(identifier, 'blink_closed')
        for _ in range(4):
            response = self.send(identifier, 'blink_closed')
            self.assertEqual(response.json()['head_step'], 2)
        self.assertEqual(self.send(identifier, 'blink_reopen').json()['head_step'], 2)
        self.assertEqual(self.f.count_attendance(), 0)

    def test_one_eye_wink_does_not_satisfy_bilateral_blink(self):
        identifier = self.begin_blink()
        self.send(identifier, 'blink_open')
        wink = dict(yaw=0, pitch=0, roll=0, blink_left=0.9, blink_right=0)
        with patch.object(self.f.bio, 'head_pose', return_value=wink):
            self.send(identifier, 'wink')
        self.assertEqual(self.send(identifier, 'blink_reopen').json()['head_step'], 2)

    def test_up_down_and_turn_sequence_completes_before_fingers(self):
        identifier = self.f.start()
        with patch('modules.biometrics.head_movement.challenge_actions', return_value=['look_up', 'turn_left', 'look_down']):
            response = self.f.face(identifier)
        self.assertTrue(response.json()['head_movement_verified'])
        self.assertEqual(response.json()['stage'], 'liveness')
        self.assertEqual(self.f.count_attendance(), 0)

    def test_replaying_the_same_pixels_resets_hold(self):
        identifier = self.f.start()
        first = self.f.auto_face(identifier, b'head-look_straight-same')
        self.assertEqual(first.json()['held_frames'], 1)
        self.f.current += timedelta(milliseconds=500)
        replay = self.f.auto_face(identifier, b'head-look_straight-same')
        self.assertEqual(replay.json()['held_frames'], 0)
        self.assertEqual(replay.json()['head_step'], 1)

    def test_instant_burst_cannot_complete_hold_and_wrong_pose_resets_it(self):
        identifier = self.f.start()
        self.send(identifier)
        burst = self.f.auto_face(identifier, b'head-look_straight-burst')
        self.assertEqual(burst.json()['held_frames'], 1)
        self.assertEqual(burst.json()['head_step'], 1)
        wrong = self.f.auto_face(identifier, b'head-turn_left-wrong-for-center')
        self.assertEqual(wrong.json()['held_frames'], 0)
        first = self.send(identifier)
        self.assertEqual(first.json()['held_frames'], 1)
        second = self.send(identifier)
        self.assertEqual(second.json()['head_step'], 2)

    def test_other_student_cannot_submit_head_frames_to_the_original_challenge(self):
        identifier = self.f.start()
        self.send(identifier)
        login = self.f.client.post('/login', json={'student_id': 'TEST002', 'password': 'test-password'})
        headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
        response = self.f.client.post('/verify-face', headers=headers,
            data={'challenge_id': identifier}, files={'file': ('frame.jpg', b'head-look_straight-stolen', 'image/jpeg')})
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.f.count_attendance(), 0)

    def test_head_match_is_still_bound_to_identity_and_presentation_checks(self):
        for pixels in (b'other-face-head', b'screen-head'):
            identifier = self.f.start()
            self.send(identifier)
            response = self.f.auto_face(identifier, pixels)
            if pixels.startswith(b'other-face'):
                self.assertEqual(response.status_code, 400, response.text)
            else:
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['held_frames'], 0)
            self.assertEqual(self.f.count_attendance(), 0)

    def test_expiry_during_head_inference_never_advances(self):
        identifier = self.f.start()
        def slow_pose(image):
            self.f.current += timedelta(seconds=91)
            return dict(yaw=0, pitch=0, roll=0)
        with patch.object(self.f.bio, 'head_pose', side_effect=slow_pose):
            response = self.send(identifier)
        self.assertEqual(response.status_code, 410, response.text)
        self.assertEqual(self.f.count_attendance(), 0)

    def test_model_failure_fails_closed(self):
        identifier = self.f.start()
        with patch.object(self.f.bio, 'head_pose', side_effect=RuntimeError('missing model')):
            response = self.send(identifier)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(self.f.count_attendance(), 0)

    def test_restart_and_cache_database_mismatch_require_new_challenge(self):
        for restart in (True, False):
            identifier = self.f.start()
            self.send(identifier)
            if restart:
                self.f.app.state.context.runtime_head = RuntimeHeadMovement(lambda: self.f.current)
            else:
                with self.f.sessions.begin() as db:
                    db.get(Challenge, identifier).valid_frames = 0
            response = self.send(identifier)
            self.assertEqual(response.status_code, 409, response.text)

    def test_cancel_discards_head_evidence(self):
        identifier = self.f.start()
        self.send(identifier)
        self.f.client.post(f'/attendance/cancel/{identifier}', headers=self.f.headers)
        with self.f.sessions() as db:
            self.assertIsNone(self.f.app.state.context.runtime_head.read(db.get(Challenge, identifier)))

    def test_hand_stage_requires_completed_head_proof(self):
        identifier = self.f.start()
        self.f.face(identifier)
        with self.f.sessions() as db:
            challenge = db.get(Challenge, identifier)
            self.f.app.state.context.runtime_liveness.start(challenge, [0.99, 0.99])
        response = self.f.image('/liveness/frame', identifier, b'forged-hand-stage')
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.f.count_attendance(), 0)


if __name__ == '__main__':
    unittest.main()
