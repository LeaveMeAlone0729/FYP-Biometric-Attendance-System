# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Machine-readable contracts must match the running biometric API."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app


class BiometricContractTests(unittest.TestCase):
    def test_exported_openapi_matches_the_application(self):
        path = Path(__file__).resolve().parents[2] / "docs/openapi.json"
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8")),
            app.openapi(),
            "Regenerate the handoff specification with backend/export_openapi.py.",
        )

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
