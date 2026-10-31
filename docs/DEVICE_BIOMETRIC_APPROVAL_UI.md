# Device enrollment UI refinement and Stage B3 capture integration preparation

## Implemented now

The device-owned preparation screen treats KEY_PROVEN as completion of key
preparation, not completion of registration. It shows "Device key verified
successfully", an explicit inactive-registration notice and the pending expiry.
The preparation/name form is hidden while proof is current. Refresh pending status
is a read-only server status action; it does not issue or sign another challenge.
Expired/failed requests explain how to start a new request with the retained key.
There are no attendance-related messages in either new enrollment screen.

A separate DeviceBiometricApprovalScreen opens from View biometric approval
requirements. It displays the two future face/liveness steps, expiry and an
unavailable explanation. Its start button is permanently disabled. It contains
no camera initialization, API client, inference, key operation, success callback,
approval flag or activation action. Opening/tapping it sends no request and asks
for no camera permission. No backend changes or migrations are part of this UI
refinement. Slot 2 activation remains disabled by the existing B2 backend.

## Keys, restart and session behavior

The existing AndroidKeyStore bridge and per-student alias are unchanged.
Verification/preparation reads an existing key first; reopening the preparation
screen only reads key metadata. A server pending result is displayed only when
its fingerprint matches this installation's retained public key. A missing or
mismatched local key produces an error instead of generating a replacement.

Android Keystore retains the candidate key across ordinary app process restarts.
The updated service checks login revision while restoring pending state. The
existing app does not persist its in-memory login token across process death;
a new login is a DIFFERENT server session. It cannot reuse another session's
pending request. Wait for the old five-minute request to expire, then explicitly
start a new pending request using the same local key. Do not persist/export the
private key, delete an alias, uninstall the app or clear its data as recovery.

The displayed expiry comes from the server. Local expiry display is informational;
there is no client authorization decision or live countdown. Refresh retrieves
server state. Correct server enforcement of expiry and single use remains mandatory.

## Partner camera inspection

The current partner module is not a reusable camera-only widget:

- `frontend/lib/modules/biometrics/screens/camera_screen.dart` initializes
  BiometricApi directly, owns camera capture/disposal, scan timers, face feedback,
  challenge prompts, progress and completion behavior.
- Its enrollment branch calls /register-face. Its verification branch calls
  /verify-face and /liveness/frame and handles completion as recorded attendance.
- Its cancellation/status paths also use attendance-specific workflow identifiers.
- Camera feedback, challenge UI and progress are private state/build fragments,
  rather than exported presentation components.

Consequently, do not navigate to CameraScreen with a device approval ID, use its
`enrollment` flag for device approval, subclass it, or redirect the global API base
URL. Those approaches could register a face, record attendance or use the wrong
challenge context. No partner-owned source was modified for this preparation.

## Proposed safe reuse boundary (partner review required)

Extract or expose presentation/capture components without algorithm changes:

| Component | Responsibility | Must not own |
|---|---|---|
| Camera capture host/controller | Front camera lifecycle, capture bytes, temporary-file cleanup, pause/dispose | API URLs, approval decisions, attendance completion |
| Face feedback overlay | Positioning/feedback supplied by workflow controller | Face matching or client PASS decisions |
| Liveness challenge/progress view | Render server-provided gesture, required-frame count and current progress | Random challenge generation or approval authorization |

The existing attendance CameraScreen can continue using these shared components
through its existing BiometricApi. The device screen will use the same capture/UI
components with a SEPARATE device-owned workflow controller and REST adapter.
Until this refactor is agreed, the independent device screen remains a disabled
layout rather than embedding the unsafe all-in-one partner screen. No temporary
mock camera success or permissive adapter is supplied.

## Future Stage B3 workflow

1. Restore and revalidate the owned, unexpired KEY_PROVEN pending registration and
   matching local key under the same authenticated login.
2. Call POST /api/v1/device-approvals with pending_registration_id. Require a real
   server approval ID and face-required state. Today this returns APPROVAL_UNAVAILABLE.
3. Only after a reviewed trusted provider is deployed, initialize the shared capture
   host. Submit new frames to /api/v1/device-approvals/{id}/face, not /verify-face.
4. Render the fresh server liveness challenge and send new frames to
   /api/v1/device-approvals/{id}/liveness/frame, not /liveness/frame.
5. Read /api/v1/device-approvals/{id} for definitive progress and uncertain responses.
   Handle failed, expired, changed-template and changed-session states without a
   fabricated success or automatic retry of consumed authorization.
6. Server approval must remain bound to student, login, pending/candidate IDs,
   fingerprint, operation, Slot 2 and current institution-trusted template revision.
   The B1 recovery/provenance checks are prerequisites, not client configuration.
7. Even biometric approval is not ACTIVE registration. Future atomic activation
   needs a fresh candidate-signed activation challenge, single-use approval
   consumption and capacity checks. There is no activation route in B2.
8. Only after a committed server activation can ordinary automatic Phase 2 device
   verification run for the new registration. No separate verify button is needed.

No camera frames should be submitted while B2 scaffolds are unavailable. Future
API field names and state contracts must be agreed with the partner before wiring
capture; client state only presents server results and never supplies PASS flags.

## Tests and limits

Flutter tests cover preparation success/incomplete/failure/expiry/load errors,
read-only refresh/reopening, retained and mismatched local keys, disabled independent
approval navigation, zero network/camera activity and narrow-screen layout.
Existing signature, session-change, lost-response, registration and automatic
verification regressions remain. A test fixture's retained key simulates service
recreation; it does not claim a new physical tablet restart test was performed.
No phone/tablet installation, native key change or production database mutation
is needed for these automated tests. Existing backend tests use isolated data.


## Files changed in this follow-up

- `frontend/lib/modules/devices/screens/pending_device_screen.dart`: distinct
  proof/expiry/error states, read-only refresh, no repeat preparation after proof.
- `frontend/lib/modules/devices/screens/device_biometric_approval_screen.dart`:
  independent disabled biometric requirements screen, without camera/API access.
- `frontend/lib/modules/devices/services/pending_device_service.dart`: session-safe
  read-only matching of restored pending state to this installation's retained key.
- `frontend/test/pending_device_test.dart`: additional UI-state, restart/read-only,
  mismatched-key, expiry, disabled-camera/API and narrow-layout coverage.
- `docs/DEVICE_BIOMETRIC_APPROVAL_UI.md`: this integration and camera reuse guide.
- `docs/SECOND_DEVICE_STAGE_B2.md`: follow-up behavior and guide link.

Prior uncommitted B2 implementation files remain present; this follow-up did not
modify backend implementation, native bridge or partner-owned biometric sources.
The debug APK was built but not installed on either physical device.


## Verification results

- Flutter analysis: no issues.
- Flutter unit/widget suite: all 64 tests passed.
- Android debug APK: built successfully; existing toolchain future-support warnings remain.
- Full backend suite with isolated MariaDB device tests: 109 run, 108 passed,
  one optional live API regression skipped. Log: .work/device-ui-review-20261031/backend-tests.log.
- Read-only production comparison against the verified B2 backup: the complete
  original registered_devices data is identical. Samsung SM-A346E / sh phone is
  ACTIVE Slot 1, registered_at 2026-10-30 03:16:59; ACTIVE Slot 2 count is zero.
- Protected biometric/attendance/native sources unchanged. No production database
  writes, migrations, app installations, key changes, commits, pushes or merges
  were performed for this UI follow-up.

## Superseded placeholder: Stage B3

The earlier disabled placeholder described above is now replaced by the separate
working device face/liveness TEST workflow. Institutional trust and activation
remain disabled. See [SECOND_DEVICE_STAGE_B3.md](SECOND_DEVICE_STAGE_B3.md) for the
current behavior and security boundary.
