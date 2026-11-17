# FYP code explanation

Review date: 17 November 2026. Repository branch SH. This explains the current source, not an institutional identity assurance claim.

## Request flow

Flutter → general route allowlist → Cloudflare HTTPS → loopback restricted gateway 8004 → original FastAPI 8000 → MariaDB. Classroom/security traffic instead uses authenticated discovery → pinned direct HTTPS 8005 → the same FastAPI application and database. A successful discovery or diagnostic result never authorizes attendance.

## Flutter and Android

- `frontend/lib/services/api_routes.dart`, `ApiRoutes.general/uri/attendanceProof`: exact general API allowlist; all remaining endpoints use the classroom transport. Full general APIs use `https://api.bioattsys.xyz`. Local mode has its own LAN configuration and no public dependency.
- `frontend/lib/services/api_client.dart`, `ApiClient`: bearer authentication, network-change recovery and transport selection. Read-only general recovery is distinct from signed POST/upload operations; signed proofs are abandoned rather than automatically replayed after network changes.
- `frontend/lib/services/lan_discovery.dart`: installer-provided public CA, server ID, mode and database identity; bounded discovery and manual IP candidates; real TLS certificate/name/identity validation before credentials or images are sent. No trust-on-first-use and no certificate-validation bypass.
- `frontend/android/app/src/main/kotlin/com/example/frontend/LanDiscoveryChannel.kt`: Wi-Fi-scoped Android NSD discovery and local IPv4 prefix evidence. Discovery advertisements are untrusted hints, not an authorization decision.
- `frontend/android/app/src/main/kotlin/com/example/frontend/NetworkChangesChannel.kt`: invalidate an old classroom connection when connectivity or addresses change.
- `frontend/lib/modules/networks/widgets/classroom_connection_card.dart`: paired server Refresh and manual IP fallback. An IP change does not require a new APK when the server trust identity is unchanged.
- `frontend/lib/screens/attendance_flow_screen.dart`, `_submit`: validate PIN through `/attendance/start`, complete signed device/network/classroom preflight, then allow camera work. Failed preflight supplies a result-screen failure rather than opening biometric capture. BLE work is a shadow diagnostic beside this flow.
- `frontend/lib/modules/devices/services/attendance_device_authorization.dart`: attendance-specific fresh proof and classroom Wi-Fi integration. A previous Profile verification PASS is insufficient.
- `frontend/lib/modules/biometrics/screens/camera_screen.dart`: partner-owned camera/biometric interaction; no algorithm changes in this final acceptance task.

## FastAPI, transactions and attendance

- `backend/application_factory.py`, `create_app`: installs account, attendance, biometric, device and network routers; classroom capabilities are explicit. Original and Local launchers configure the same existing application architecture.
- `backend/api/accounts.py`: password-hash login, active-account checks, hashed expiring bearer sessions, logout/revocation. `backend/api/dependencies.py`, `authenticated/get_db`: server-owned student identity; commit before successful response and rollback on errors.
- `backend/api/attendance.py`, `start_attendance`: eligible class/session/group/time, PIN and duplicate checks; creates an expiring student/login-bound verification attempt. It does not insert attendance. In demo mode some class/start operations may seed demo data; this audit did not call authenticated live class/start routes.
- `backend/modules/biometrics/service.py`, `BiometricService.register_face/verify_face/liveness_frame`: enrollment restrictions, encrypted template comparison, facial action/head-movement and anti-spoof evidence, live gesture frames and replay/frame rejection. `liveness_frame` calls the final writer only after genuine server-side progress. Synthetic tests do not prove real-world biometric accuracy or spoof resistance.
- `backend/services/attendance.py`, `record_verified_attendance`: runtime attendance insert boundary. It invokes `AttendanceAuthorizationService.authorize`, checks fresh authorization within a nested transaction, consumes the attempt and writes one Attendance row; a concurrency/uniqueness failure is rejected.
- `backend/modules/authorization/service.py`, `AttendanceAuthorizationService`: fresh single-use challenge, student/login/session/operation/device/key binding, signature and active-slot checks, preflight and final authorization. Final checks are repeated; preflight cannot grant future attendance access.
- `backend/modules/networks/service.py`, `NetworkVerificationService.verify`, and `cidr.py`, `connection_ip/parse_cidr`: actual ASGI connection source, enabled CIDR policies, fail closed for absent/invalid policies and loopback. Forwarded headers, claimed Wi-Fi and Cloudflare egress never establish campus presence.
- `backend/modules/classroom_wifi/attendance.py`, `AttendanceClassroomService.freeze/check/fresh`: session/classroom requirement binding and fresh signed Wi-Fi evidence. Classroom identifiers must match exactly. BSSID/SSID observations are client-reported, not cryptographic location proof.

## Device management and enrollment assurance

`backend/modules/devices/biometric_service.py`, activation/replacement services and enrollment revision models bind genuine face/liveness completion to fresh device operations. `activation_service.py` issues/consumes the operation approval; `replacement_service.py` scopes replacement and preserves the other slot. Android Keystore signs fresh server payloads; unknown, mismatched, expired and replayed proofs are rejected.

ACCOUNT_BOUND_FYP is a demonstration policy for genuine first enrollment by authenticated school-provisioned accounts, not INSTITUTION_VERIFIED identity. Legacy templates are not silently upgraded. `backend/modules/devices/local_demo.py` keeps explicitly labeled local demo evidence separate and checks permitted bindings/devices. Original startup currently uses `--local-demo-slot2`; its private credential is not copied to a partner. Face deletion and unauthorized re-enrollment remain blocked.

## Cloudflare and administration

`backend/public_gateway.py`, `create_gateway`: loopback origin, exact public Host and method/path allowlist, 8 KiB body cap, aggregate login throttle, no forwarded-header trust, no redirects/cookie leakage. Permitted paths: `/config`, `/login`, `/logout`, `/me`, `/classes`, `/attendance/history`, `/attendance/summary`. Public security/biometric/attendance-writing/admin routes are denied even with a valid student token. Cloudflare forwards only to 127.0.0.1:8004.

`backend/admin_testing.py`, `create_panel/checked_form/perform`: separately authenticated localhost administrator, password hash, expiring sessions, exact-origin and CSRF checks, escaped HTML and same-page AJAX. Session PINs are hashed; open-session regeneration invalidates the previous PIN and reveals the new value only to the administrator. Management operations reuse the policy/session services. Opening an unauthenticated login page is not proof of a successful live admin login; synthetic tests cover authenticated mutations.

## Persistence and operations

`backend/models.py` plus module models/migrations define the application schema. Fresh read-only verification found MariaDB 10.4.27, 43 application tables, 1 student, 8 attendance rows and 2 registered-device rows. This proves current readability/schema compatibility, not repair of previously corrupted MariaDB system tables or a new durability/restore rehearsal.

`backend/original_fyp.py`, `probe/create_backend/serve`: original schema/port/server identity guards, bounded application-table reads, schema validation and explicit local-demo configuration. `backend/local_fyp.py`, `private/load_profile/probe`: independent per-clone private profile and pinned database; rejects protected original schema/root/empty credentials; does not fall back to Full secrets.

`backend/lan_discovery.py`, `provision/load_trust/probe_tls/Advertisement/serve`: explicit offline environment pairing, separate server key and discarded CA signing key, validated trust, same-process HTTPS listener and mDNS on the current Wi-Fi IP. IP changes withdraw/rebind the listener and advertisement; manual pinned TLS is available when multicast fails. Private keys stay outside Git.

`fyp-start.ps1`, `fyp-install.ps1`, `fyp-stop.ps1` → `backend/fyp_operator.py`, `Workflow/Host/LocalHost`: guarded ownership and bounded readiness checks, reuse verified existing processes, no unknown-process termination, APK update with `adb install -r`. Full and Local share ports and cannot be run simultaneously; use `-Mode Local` consistently for partner operation.

## BLE

`backend/modules/classroom_ble/service.py`: UUID/policy, signatures, samples/RSSI, freshness and replay checks; BLE-only maximum future lead 2,000 ms does not extend challenge/session expiry. `backend/tests/test_attendance_ble_shadow.py` and Flutter attendance tests cover non-authoritative shadow behavior. BLE PASS cannot authorize attendance and BLE failure alone cannot reject otherwise authorized attendance. Network + BLE Test Mode is OFF. Historical physical diagnostic tests are recorded separately from fresh automated evidence.
