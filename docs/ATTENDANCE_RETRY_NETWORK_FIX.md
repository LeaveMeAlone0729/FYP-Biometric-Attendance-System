# Attendance retry transport investigation and fix

Date: 17 November 2026 (MYT). Branch SH; existing uncommitted secure-discovery work preserved.

**Status: two concrete Flutter transport defects reproduced before the fix and regression tests pass afterward. Physical Xiaomi retry with the new APK is NOT TESTED. Do not describe the original intermittent phone issue as fully resolved yet.**

## Evidence and limits

The original user message exactly matches `NetworkVerificationFailure.unreachableMessage/attendanceMessage`. That presentation is used for TimeoutException, socket/client exceptions and selected transport error codes; it is not an actual CIDR rejection result. Existing backend access logging is disabled, and attendance HTTP requests did not carry the B3 device-enrollment diagnostics, so there is no request-level packet/timing record proving which transport failure caused every historical phone occurrence.

Read-only original database inspection found recent preflight PASS events and NETWORK_AUTHORIZED source 192.168.0.94, as well as separate genuine face mismatch/head-frame-limit failures and cancellations. No lock wait was active in the bounded process-state snapshot. The reviewed backend log had model/telemetry messages but no matching ASGI traceback or database deadlock evidence. A standalone displayed PASS may describe an earlier diagnostic; it does not grant a new attendance attempt. These observations do not establish a physical network outage or a CIDR policy defect.

## Confirmed defects and before/after reproduction

1. **Old request invalidates new connection.** `SecureLanDiscovery.send` previously unconditionally called `invalidate()` when any request failed. An old fire-and-forget `/attendance/cancel/<old attempt>` can complete after a new network refresh/reconnection. Its failure then closes and clears the NEW paired client. The regression explicitly delays an old cancellation, establishes a new paired address, and releases the old failure. Before the fix, expected new address became null; afterward the new connection survives.
2. **New PIN retry reuses a stale paired cache.** `_requestUri` previously always called `ensureReady`, which immediately returned for an existing client. A server IP change without a phone network-change callback left the old literal address cached. A deterministic test performs standalone diagnostic PASS, first PIN/preflight, genuine simulated server face rejection, server IP change and a new submission of the SAME PIN. Before the fix, retry raised the classroom-server-unreachable error; afterward it discovers/verifies the new pinned endpoint and starts a separate attempt. No old face/proof request is retried.
3. **Misleading native timeout presentation.** Device key lookup/signing used raw Future timeouts; the common presenter classified raw TimeoutException as verification-server unreachable. Explicit `DEVICE_KEY_TIMEOUT` errors now identify Android key lookup/signing failures instead. A fake-clock regression exercises the actual signing deadline and verifies no biometric frame is submitted.

The first two are verified causal mechanisms in the code. Whether they account for every real Xiaomi occurrence still requires the requested physical retry; server overload/slow requests cannot be excluded solely by these historical logs.

## Transport comparison

| Property | Standalone Network Verification | Attendance |
|---|---|---|
| Client | ApiClient.instance (unless test injection) | Same ApiClient.instance via flow, device authorization and biometric adapter |
| Endpoint | POST /api/v1/networks/verifications | POST /attendance/start; /api/v1/attendance/preflight-challenges and /preflight; classroom Wi-Fi proof; /verify-face; /liveness/frame |
| Paired transport | Installed CA + stable paired logical hostname, direct HTTPS 8005 at discovered literal Wi-Fi address | Same pinned HTTPS 8005; NEW PIN now performs fresh discovery/TLS identity validation first |
| Public fallback | None for network verification | None for attendance, device, Wi-Fi, face or liveness |
| Authentication | Server bearer session | Same bearer plus student/session/operation-bound fresh server challenges and Keystore proof |
| Timeout | ApiClient classroom request 10s; wrapper 15s | Same classroom request 10s; device/preflight wrappers 15s, preflight workflow bound 40s; image upload 25s |
| State | Current diagnostic result, discarded/refreshed on lifecycle events | Fresh server attempt from PIN; preflight proof differs from final authorization; expiry/consumption enforced server-side |

Compiled legacy HTTP base URLs are retained for explicitly unpaired builds; a paired build overrides these classroom requests with the trusted HTTPS origin. Full general APIs remain Cloudflare HTTPS. Partner Local uses its own configuration/trust, not Full credentials. No alternate HTTP attendance client was found.

## Minimal runtime changes

- `frontend/lib/services/lan_discovery.dart`: add `refresh()` that retires transport and resolves/verifies fresh hints while retaining an explicitly supplied manual candidate. Candidate subnet and pinned identity checks run again. Real network invalidation still clears manual hints. Capture the sending client/revision; invalidate on failure only if that same client/revision remains current.
- `frontend/lib/services/api_client.dart`, `_requestUri`: `/attendance/start` uses refresh; other requests retain ensureReady. This occurs before the one new user-requested PIN POST, not as an automatic retry of a failed POST. No signature request, image or attendance write is replayed.
- `frontend/lib/modules/devices/services/attendance_device_authorization.dart`, `_proof`: key lookup/sign timeouts use `DEVICE_KEY_TIMEOUT`; cryptographic checks/time limits unchanged.

Tests changed:
- `frontend/test/secure_lan_discovery_test.dart`: old-request race, standalone/attendance routing and fresh same-PIN retry across IP change, no public fallback/replay, retained manual fallback revalidation.
- `frontend/test/attendance_preflight_test.dart`: failed camera return followed by new preflight signature, accurate failure presentation, real native-sign deadline.
- `backend/tests/test_attendance_authorization.py`: diagnostic PASS → preflight PASS → invalid face → same PIN creates DIFFERENT attempt and nonce → old proof rejected → fresh legitimate face/liveness/final proof succeeds once → duplicate rejected. Isolated SQLite/synthetic biometric fixture only.

No partner camera, face inference, liveness implementation, backend runtime, database schema, policies, TLS identity, Keystore or Cloudflare/firewall settings were changed.

## Validation

Evidence folder: `C:\FYP\Final-Acceptance\20261117-final`.

- Before-fix race reproduction: FAIL as expected; `retry-before.log`.
- Before-fix stale-IP retry reproduction: FAIL with unreachable error as expected; `retry-ip-before.log`.
- Focused initial Flutter selection: 87 PASS (before the final extra native-deadline test).
- Final complete Flutter suite: **337 PASS, 1 SKIPPED**, `retry-flutter-full.log`.
- Relevant backend: **130 PASS, 2 SKIPPED**, `retry-backend.log/xml`. Live database/API opt-ins disabled and mysql.connector.connect blocked in the test process; no production test writes.
- Flutter analyze: clean, `retry-analyze.log`.
- Paired Full debug APK build: PASS, `retry-build.log`; existing Android toolchain future-support warnings only.
- Git whitespace check: PASS; pre-existing LF/CRLF warning for original_fyp.py.

Commands: from frontend, `flutter test --no-pub --reporter expanded`, `flutter analyze --no-pub`, and `flutter build apk --debug --no-pub --dart-define-from-file=C:\FYP\Deployment-Checkpoints\secure-lan-20261117-004116\paired-public-build-defines.json`. Backend selected suites: test_attendance_authorization, test_network_verification, test_classroom_attendance, test_workflow, test_public_gateway, using the existing guarded pytest wrapper. Do not enable live opt-ins against original data.

## Deployment and physical retest

**APK update required; no backend/admin/MariaDB restart is needed.** Built APK: `frontend/build/app/outputs/flutter-apk/app-debug.apk`. It has not been installed by this task. Preserve package data, signing identity and existing keys; never uninstall/clear data. After installation approval, verify target serial and use the existing paired installer or an explicitly checked `adb -s 7732690b install -r ...`. Never select Samsung or use ADB reverse.

1. Connect Xiaomi 7732690b by USB, keep laptop/tablet on existing approved Wi-Fi, and verify the current laptop address. Do not alter network/classroom policies or TLS pairing.
2. With the updated APK, Network Verification → paired connection → Refresh → diagnostic PASS.
3. Use the same valid OPEN eligible class PIN. Ensure preflight succeeds and camera opens. End an unsuccessful genuine face/liveness attempt normally; return to attendance and immediately enter the SAME PIN again, at least three times. Each attempt must get fresh preflight proof and reach camera if legitimate; biometric failure must remain a biometric failure, not a fabricated network decision.
4. If a genuine timeout occurs, record stage, elapsed time and wall-clock timestamp; inspect safe endpoint/error-code diagnostics, never tokens/PIN/images. Do not keep retrying a possibly successful final attendance write; check history first.
5. Verify a reachable unauthorized network rejects before capture. An unreachable backend must still fail closed as unavailable. No Cloudflare fallback is allowed. No policy changes for this test.
6. On an authorized legitimate final attendance run, confirm exactly one record and duplicate rejection. This is a real write and is separate from the agent’s isolated tests; use an intended legitimate session and do not delete previous attendance to repeat it.
7. Laptop-IP-change handling is automated-test PASS; a separate physical change requires the approved network/firewall conditions. Do not bypass the Public-profile lease or current attendance policy to manufacture a PASS.

Physical result remains **PENDING** until the user repeats the retry on Xiaomi. No service was restarted and no APK installed. No commit or push.
