# Facial recognition and liveness API

Module owner: **Chew Zhexuan**. API release: **2.1.0**.

This is a REST API with JSON responses and multipart camera uploads. Existing
demo URLs are preserved. The module includes face enrollment, facial matching,
random finger-count liveness and a protected verification-result lookup. Login,
class PINs and attendance storage currently supply the demo context.

## API files and interactive documentation

- Run the backend with `./start-backend.ps1` from the repository root.
- Swagger UI: `http://localhost:8000/docs`.
- Live OpenAPI specification: `http://localhost:8000/openapi.json`.
- Handoff specification: [openapi.json](openapi.json). Import it into Postman
  using **Import → File** to create the requests and inspect response schemas.
- Regenerate the handoff specification after changing a public contract:

  ```powershell
  .\backend\venv\Scripts\python.exe backend\export_openapi.py
  ```

For a physical phone, use the PC's reachable address as the API base URL. The
Flutter entry point remains:

```powershell
.\start-frontend.ps1 -ApiBaseUrl http://YOUR_PC_IPV4:8000
```

## Authentication and identifiers

Send `POST /login` with a JSON body:

```json
{"student_id": "YOUR_STUDENT_ID", "password": "YOUR_PASSWORD"}
```

Read `access_token` from the response. Protected requests use:

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
```

This is an opaque bearer token backed by `auth_sessions`, not a JWT. Use the
**same login token** to start, verify, cancel and read a challenge. A second login
for the same student cannot take over the first login's challenge. Logout revokes
that login and cancels its pending challenges.

| Identifier | Type | Meaning |
| --- | --- | --- |
| `student_id` | string | Shared student account identifier |
| `session_id` | integer | Dated class session, not the login session |
| `challenge_id` | string | Expiring face/liveness challenge |
| `verification_id` | integer | Persisted verification audit record |
| `attendance_id` | integer or null | Demo attendance record after completion |

Use these identifiers when mapping your teammate's records. The server derives
the student from authentication; clients do not choose another student in an
image-upload request.

## Workflow and requests

| Step | Request | Input | Result |
| --- | --- | --- | --- |
| Register face | `POST /register-face` | Multipart: `file`, `consent`; optional `auto_capture`, `preview_only` | Retry feedback, ready preview, or encrypted template saved |
| Start demo verification | `POST /attendance/start` | JSON: `{"pin":"123456"}` | `challenge_id`, `session_id`, expiry and stage `face` |
| Match face | `POST /verify-face` | Multipart: `challenge_id`, `file`; optional `auto_capture`, `preview_only` | Retry feedback, ready preview, or random `fingers` and stage `liveness` |
| Check gesture | `POST /liveness/frame` | Multipart: `challenge_id`, fresh `file` | Progress, or completed demo attendance |
| Read result | `GET /verification/{challenge_id}` | Original bearer token | Stored verification state; no mutation |
| Cancel | `POST /attendance/cancel/{challenge_id}` | Original bearer token | Cancels pending verification |
| Remove template | `DELETE /biometrics` | Bearer token | Removes template/consent and cancels pending challenges; retains attendance |
| Read activity | `GET /verification-attempts` | Bearer token | Own verification activity; pending expired attempts are finalized |

The demo start endpoint validates the student's class PIN, group and attendance
window. Its response includes `expires_in` (currently 90 seconds). Enrollment
does not require a class PIN. `GET /me` reports `biometric_status`.

Uploads use the exact field name `file`. Let the HTTP library create the
multipart boundary. Images are limited to 6 MB, decoded in memory, corrected for
EXIF orientation and resized for inference. Invalid images receive detection
feedback or an error. No raw images, face encodings or distance scores are
returned in the API.

### Automatic face scanning

The Flutter module sends `auto_capture=true` to check guided face positioning.
It first sends `preview_only=true`; when ready, it captures a new frame and sends
`preview_only=false` to register the face or advance the attendance challenge.
Both flags default to `false` for compatibility with manual API clients.

Recoverable detection/positioning response:

```json
{"success":true,"ready":false,"retryable":true,"message":"Keep exactly one face visible in the camera frame."}
```

Ready preview:

```json
{"success":true,"ready":true,"preview_only":true,"message":"Face matched. Hold still for automatic capture."}
```

A preview does not store a template, advance the challenge or record attendance.
An identity mismatch ends the challenge even during preview. With
`auto_capture=false`, a detection failure uses the error response instead of
retry feedback.

After successful facial verification:

```json
{
  "success": true,
  "ready": true,
  "face_verified": true,
  "stage": "liveness",
  "fingers": 3,
  "required_frames": 3,
  "expires_at": "2026-10-29T22:01:30+08:00",
  "message": "Show 3 finger(s), palm toward the camera. Keep your face and hand fully visible anywhere in the frame; neither needs to be centered."
}
```

### Liveness checks

Send camera frames sequentially, waiting for each response before the next
upload. The server requires three consecutive valid frames with the requested
finger count and the same registered face visible. Face centering is only part
of the guided face scan; during liveness the face and hand may be elsewhere in
the full frame. Exactly one face and one hand must be detectable.

An incorrect gesture, missing detection or repeated frame resets `valid_frames`
to zero. An identity substitution ends the challenge. Enrollment and facial
verification frames cannot be replayed as gesture frames.

```json
{"success":true,"complete":false,"valid_frames":1,"required_frames":3,"message":"Correct gesture. Hold steady; your face and hand do not need to be centered."}
```

After the third accepted frame, the **current demo records attendance**:

```json
{
  "success": true,
  "complete": true,
  "face_verified": true,
  "liveness_verified": true,
  "attendance_id": 42,
  "recorded_at": "2026-10-29T22:01:15+08:00",
  "message": "Attendance accepted"
}
```

`success=true` means the request was processed; it does not by itself mean a face
or gesture passed. Inspect `ready`, `registered`, `face_verified`, `complete` and
`liveness_verified` as appropriate. The result endpoint also exposes explicit
`status` values: `pending`, `success`, `failed`, `cancelled`, `expired`.

### Reading a result

`GET /verification/{challenge_id}` provides a read-only result under the original
bearer login. Example after completed demo attendance:

```json
{
  "success": true,
  "challenge_id": "CHALLENGE_FROM_START",
  "verification_id": 123,
  "student_id": "YOUR_STUDENT_ID",
  "session_id": 12,
  "status": "success",
  "stage": "complete",
  "face_verified": true,
  "liveness_verified": true,
  "valid_frames": 3,
  "required_frames": 3,
  "expires_at": "2026-10-29T22:01:30+08:00",
  "attendance_id": 42
}
```

For incomplete results, `attendance_id` is null. Successful results remain
successful after the challenge's capture deadline, while the bearer login is
valid. Polling an expired pending challenge returns `expired` without changing
database state. Unknown challenges and challenges owned by another login return
404; missing authentication returns 401.

## Combining with the teammate's module

The simplest integration is to add the teammate's router/service to the same
FastAPI backend and register it in `backend/app.py`. Reuse the authenticated
student and class session from the shared dependencies and context. Keep each
module's business logic in its own folder.

Current integration points:

1. `backend/api/dependencies.py`: shared bearer login and transaction handling.
   Adapt the authentication dependency here if the combined project already has
   a central login service; do not trust a student ID submitted by Flutter.
2. `backend/api/attendance.py`: the demo admission/PIN flow creates the challenge.
   A combined coordinator can run the teammate's prerequisites here before
   starting the biometric challenge.
3. `backend/modules/biometrics/service.py`: face and liveness decisions.
4. `backend/services/attendance.py`: the final demo attendance write, inside the
   verification transaction. Extend/replace this completion step so the combined
   coordinator confirms all required module results before recording attendance.

The current liveness endpoint already writes demo attendance; it is not yet a
biometric-only proof service for an independently recording backend. Do not
append teammate checks after its successful attendance response and expect them
to gate that existing write. Agree on the combined completion step first.

If the teammate uses a separate backend, agree on authenticated server-to-server
access and shared identifiers before connecting the services. The current result
endpoint requires the initiating user's login; it does not introduce service
credentials, callbacks or webhooks. Passing `face_verified=true` or similar flags
from Flutter never creates a verified result.

Device/network verification remains outside this module. Its result is neither
implemented nor claimed by these endpoints.

## Errors and validation

Errors use `{"success":false,"message":"..."}`. Request validation errors also
include `fields: [{"field":"...","message":"..."}]`. Clients should branch on
HTTP status and documented response fields, rather than matching message text.

| Status | Meaning |
| --- | --- |
| 400 | Invalid input/capture or biometric mismatch |
| 401 | Sign-in required or expired |
| 403 | Account/challenge ownership invalid |
| 404 | Requested verification not available to this login |
| 409 | Wrong stage, ended challenge, duplicate attendance or closed class |
| 410 | Verification/attendance deadline expired |
| 422 | Missing or invalid request fields |
| 429 | Attempt/frame limit reached |
| 500 / 503 | Verification or database temporarily unavailable |

The automated tests validate contract, ownership and workflow behavior. Real
face/gesture acceptance and spoof resistance still require consented camera
evaluation; the finger challenge is a research liveness heuristic.

## Device registration API (Phase 1)

The shared backend now also exposes authenticated device registration at
`/api/v1/devices/registration-challenges`, `/api/v1/devices/registrations` and
`/api/v1/devices/current`. See [DEVICE_REGISTRATION.md](DEVICE_REGISTRATION.md)
for signing bytes, contracts, migration, failure handling and USB phone testing.
Registration is independent: it does not change any biometric endpoint or gate
attendance. Automatic device verification is now provided by Phase 2 below.
Replacement, CIDR checks and the final authorization coordinator remain later phases.

## Automatic device verification API (Phase 2)

The device router adds `/api/v1/devices/verification-challenges`,
`/api/v1/devices/verifications` and negative-only `/api/v1/devices/verification-failures`.
See [DEVICE_VERIFICATION.md](DEVICE_VERIFICATION.md) for full contracts, operation
binding, replay rules, audit and the additive migration. Only `device_status` is
currently enabled; PASS is point-in-time evidence and never attendance authority.
Phase 5 must add server-validated attendance-attempt binding and invoke the Flutter
service automatically, then gate the final insert. Existing biometric endpoints
and attendance completion remain unchanged in Phase 2.

## Stage A device selection

GET `/api/v1/devices` lists up to two owned ACTIVE registrations. Automatic
verification challenges now require the local `public_key_fingerprint` selector;
a valid signature remains mandatory. Initial registration endpoints cannot
activate a second device. No biometric or attendance API behavior changed. See
[TWO_DEVICE_STAGE_A.md](TWO_DEVICE_STAGE_A.md) for contracts and rollout safety.

## Stage B2 preparation boundary

Device-owned pending registration/proof endpoints and fail-closed device approval
scaffolds are documented in [SECOND_DEVICE_STAGE_B2.md](SECOND_DEVICE_STAGE_B2.md).
No activation route exists. Initial registration and biometric/attendance APIs stay
unchanged; `additional_enrollment_enabled` remains false.

## Stage B3 updates to device-approval URLs

The B2 scaffolds now host attendance-free face/liveness TEST sessions; they do not
issue trusted approvals. Every result remains untrusted, non-consumable and
ineligible for activation. See [SECOND_DEVICE_STAGE_B3.md](SECOND_DEVICE_STAGE_B3.md).

## Current second-device activation REST API

The authenticated device activation API and Flutter automatic signing flow are
implemented. The default trusted provider remains unavailable; COMPLETED_UNTRUSTED
cannot activate a device. Under /api/v1/devices/pending-registrations/{pending_id}:

- POST /activation-readiness with {} finds a genuine server approval.
- POST /activation-challenges with {approval_id} issues a signed-proof nonce.
- POST /activate with {approval_id, challenge_id, signature} requires fresh key proof.
- GET /activation-status reconciles final committed registration state.

See [full contracts and migration evidence](SECOND_DEVICE_ACTIVATION_INTEGRATION.md)
and [partner adapter schema](TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md). OpenAPI includes
all four paths. The two additive activation tables are installed in production;
existing registrations, templates and attendance were preserved. No production
mock or client-controlled trust path exists.

## Stage C1 device replacement

Device-owned replacement now uses POST /api/v1/devices/replacements and the shared pending proof/status/cancellation, attendance-free biometric and trusted activation routes for either occupied slot. Existing algorithms and attendance routes are unchanged. The old device remains ACTIVE until an atomic trusted handover succeeds; the other slot is preserved. The provider methods are unchanged, with replacement target ID/fingerprint added to the exact binding. Production remains fail closed without the partner provider. See [complete replacement contract, migration and tests](DEVICE_REPLACEMENT_C1.md).
