# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Machine-readable contracts must match the running biometric API."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from export_openapi import main as export_openapi


class BiometricContractTests(unittest.TestCase):
    def test_face_verification_requires_head_movement_before_hand_challenge(self):
        schemas = app.openapi()["components"]["schemas"]
        face = schemas["FaceVerified"]
        self.assertIn("anti_spoof_verified", face["required"])
        self.assertEqual(face["properties"]["anti_spoof_verified"]["const"], True)
        self.assertEqual(face["properties"]["head_movement_verified"]["const"], True)
        head = schemas["HeadMovementProgress"]
        self.assertEqual(head["properties"]["liveness_step"]["const"], "head")
        self.assertEqual(set(head["properties"]["head_action"]["enum"]),
                         {"look_straight", "turn_left", "turn_right", "look_up", "look_down", "blink"})
        self.assertEqual(head["properties"]["head_steps"]["const"], 7)
        for name in ("FaceVerified", "LivenessProgress"):
            properties = schemas[name]["properties"]
            self.assertEqual(properties["liveness_step"]["const"], "hand")
            self.assertNotIn("face_action", properties)
            self.assertNotIn("face_actions_completed", properties)

    def test_student_template_deletion_is_not_exposed(self):
        specification = app.openapi()
        self.assertNotIn("/biometrics", specification["paths"])
        self.assertNotIn("BiometricRemoved", specification["components"]["schemas"])

    def test_exported_openapi_matches_the_application(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "openapi.json"
            with patch.object(sys, "argv", ["export_openapi.py", "--output", str(path)]):
                export_openapi()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), app.openapi())

    def test_camera_contract_uses_authenticated_multipart_requests(self):
        specification = app.openapi()
        for path, required, operation_id in (
            ("/register-face", {"consent", "file"}, "registerFace"),
            ("/verify-face", {"challenge_id", "file"}, "verifyFace"),
            ("/liveness/frame", {"challenge_id", "file"}, "submitLivenessFrame"),
        ):
            with self.subTest(path=path):
                operation = specification["paths"][path]["post"]
                self.assertEqual(operation["operationId"], operation_id)
                self.assertEqual(operation["security"], [{"HTTPBearer": []}])
                reference = operation["requestBody"]["content"]["multipart/form-data"][
                    "schema"
                ]["$ref"]
                schema = specification["components"]["schemas"][
                    reference.rsplit("/", 1)[1]
                ]
                self.assertEqual(set(schema["required"]), required)
                self.assertEqual(
                    operation["responses"]["422"]["content"]["application/json"][
                        "schema"
                    ]["$ref"],
                    "#/components/schemas/ErrorResponse",
                )
                self.assertNotEqual(
                    operation["responses"]["200"]["content"]["application/json"][
                        "schema"
                    ],
                    {},
                )

    def test_result_contract_contains_no_template_or_teammate_verification_fields(self):
        specification = app.openapi()
        operation = specification["paths"]["/verification/{challenge_id}"]["get"]
        self.assertEqual(operation["operationId"], "getVerificationResult")
        self.assertEqual(operation["security"], [{"HTTPBearer": []}])
        properties = specification["components"]["schemas"]["VerificationResult"][
            "properties"
        ]
        self.assertTrue(
            {
                "student_id",
                "session_id",
                "verification_id",
                "face_verified",
                "liveness_verified",
                "face_liveness_verified",
                "status",
                "attendance_id",
            }
            <= properties.keys()
        )
        self.assertTrue(
            {
                "face_encoding",
                "face_distance",
                "device_verified",
                "network_verified",
            }.isdisjoint(properties)
        )
