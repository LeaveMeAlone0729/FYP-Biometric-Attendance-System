# Temporary Network + BLE Test

This opt-in diagnostic simulation checks a real open session and PIN, the
authenticated student and existing ACTIVE device, CIDR policies, classroom
Wi-Fi and signed BLE evidence. The screen never opens the biometric camera.
The server creates no biometric attendance attempt and never calls the
attendance writer. A result is always labeled TEST PASS or TEST FAIL and
contains `diagnostic_test: true` and `attendance_authorized: false`.

The normal Take Attendance path retains its face, head movement, liveness,
device proof, network and classroom Wi-Fi requirements. Diagnostic nonces
have no matching attendance attempt or attendance Wi-Fi binding, so they
cannot be supplied as attendance authorization.

## Temporary enablement

`NETWORK_BLE_TEST_MODE` defaults to `false`. The backend rejects the diagnostic
routes while disabled and `/config` controls visibility of the temporary
**Network + BLE Test** action on the existing attendance PIN page. Merely
changing the Flutter flag cannot enable the backend routes.

After separate approval for a backend restart, use the existing original
launcher in PowerShell. Stop only the verified old backend first, and keep
MariaDB and the admin panel running unless a separately approved panel
restart is needed to load the new diagnostic audit view.

```powershell
$repo = 'C:\FYP\FYP-Biometric-Attendance-System'
$env:NETWORK_BLE_TEST_MODE = 'true'
& "$repo\backend\venv\Scripts\python.exe" "$repo\backend\original_fyp.py" serve-backend --lan --local-demo-slot2
```

Check the pinned original `/local-fyp/identity`, localhost and LAN `/config`,
and that `/config` reports `network_ble_test_mode: true`. Use the current LAN
IPv4 and the explicitly selected Xiaomi serial to install after deployment
approval. For the verified `192.168.0.162` address:

```powershell
& 'C:\FYP\FYP-Biometric-Attendance-System\install-fyp-android.ps1' -Serial 7732690b -LanIp 192.168.0.162
```

Reopen the app to reload configuration. Open Take Attendance, choose
**Network + BLE Test**, select an eligible session, enter its PIN and choose
**Run diagnostic test**. Eligibility comes from the current server session
window, assigned student group and session classroom. A previously recorded
attendance does not prevent a diagnostic test. No new attendance session or
policy is created by the diagnostic screen.

## REST contract and server checks

All routes require the normal bearer login and the enabled server setting.

* `GET /api/v1/network-ble-tests/sessions` lists eligible open sessions and
  their assigned classrooms without seeding or altering the database.
* `POST /api/v1/network-ble-tests/start` accepts `session_id`, the six-digit
  `pin`, and `public_key_fingerprint`. The server checks the account, ACTIVE
  device selector, PIN, classroom and actual ASGI source IP. A fingerprint
  selects a key and never replaces cryptographic proof.
* If CIDR passes, start returns a `test_id`, `session_id`, `classroom_id`, and
  the existing `wifi` and `ble` signing challenges. Both signed payloads bind
  to the test, session and classroom revision. The BLE challenge additionally
  binds to the exact Wi-Fi challenge. No client PASS fields are accepted.
* Flutter obtains fresh Wi-Fi evidence and a fresh bounded BLE scan, and signs
  each original challenge payload plus a newline and the respective JSON
  evidence using the existing Android Keystore key. It sends both proofs to
  `POST /api/v1/network-ble-tests/finish`.

```json
{
  "test_id": "nbt.57.<server-generated-token>",
  "wifi": {
    "challenge_id": "<server-generated-id>",
    "evidence_payload": "<base64 Wi-Fi JSON>",
    "signature": "<base64 ECDSA DER>"
  },
  "ble": {
    "challenge_id": "<server-generated-id>",
    "evidence_payload": "<base64 BLE JSON>",
    "signature": "<base64 ECDSA DER>"
  }
}
```

Finish checks ownership, login, matching test bindings, device identity,
single use, current session/classroom and expiry. It calls the existing
Wi-Fi and BLE confirmation services, including the 2,000 ms BLE-only future
cap, existing conservative freshness rules, UUID/sample/RSSI policies and
evidence replay hashes. It rechecks CIDR from the finish request's real ASGI
source IP. It consumes any remaining owned nonce on a failed completed test.
An exact replay is rejected with the existing replay code. Existing normal
standalone and attendance validators keep their contracts.

The combined response includes `test_result`, the exact `reason_code`, and
the `network`, `wifi` and `ble` results that the server reached. A stage not
reached is displayed as NOT CHECKED. Only three server-confirmed PASS results
can produce TEST PASS. Bluetooth off produces TEST FAIL / BLUETOOTH_OFF when
the signed report reaches the server. Transport and native-platform failures
produce a visible test failure without claiming an IP or beacon rejection.

## Audit and removal

Existing network, Wi-Fi and BLE diagnostic audit tables are reused. Final
combined results use `TEST_PASS` or `TEST_FAIL` BLE audit events with an
`nbt.<session>.<token>` correlation ID. The original admin `/ble` page has a
separate **Temporary Network + BLE Tests** table. It shows session, classroom,
time and exact final reason without credentials or signed payloads. A client
failure before a server final response may leave only the component nonce
audit records. A server-committed result may be visible even if its response
was lost. No database migration is needed.

Disable after testing by removing the environment setting and restarting only
the approved backend. Reopen the app to refresh `/config`.

```powershell
Remove-Item Env:NETWORK_BLE_TEST_MODE -ErrorAction SilentlyContinue
```

For later source removal, remove the test-mode router composition, the
temporary setting/config field, Flutter entry and test screen/API, and the
separate admin test-history card. Existing audit history can be retained.

## Xiaomi physical checks

Use a legitimate open test session and existing PIN for the exact classroom.
Use direct Wi-Fi transport. ADB reverse and localhost fail the existing CIDR
check. A connection timeout is a test failure with no confirmed network result.

| Case | Setup | Expected server result |
|---|---|---|
| A | `ClASSROOM_A`, approved 5 GHz Wi-Fi, SENGHIN transmitting | TEST PASS if sample/RSSI policy passes |
| B | Same session and Wi-Fi, beacon stopped | TEST FAIL / BLE_BEACON_NOT_FOUND |
| C | `ClASSROOM_B`, approved 2.4 GHz Wi-Fi, only A's UUID transmitting | TEST FAIL / BLE_BEACON_NOT_FOUND |
| D | Approved Wi-Fi and Bluetooth off | TEST FAIL / BLUETOOTH_OFF |
| E | Reachable backend and unapproved classroom access point | TEST FAIL / existing Wi-Fi reason |
| F | Replay exact proofs in an isolated automated test | TEST FAIL / existing challenge replay reason |

Repeat cases with new diagnostic nonces. The same legitimate attendance session
may be reused for diagnostics. Compare the test screen with the separate admin
test table, and verify attendance counts remain unchanged. Raw SSID/BSSID and
BLE UUID/RSSI remain client-reported observations. Cryptographic signatures
protect binding and integrity, but cannot independently prove physical presence.
Record physical results only after execution on the Xiaomi.

## Local validation — 12 November 2026

* Backend BLE/network/attendance/original-launcher regression run: 129 passed,
  3 skipped. The skipped cases require external database concurrency support.
* Dedicated diagnostic tests after adding re-signed evidence replay and admin
  audit-view coverage: 10 passed. Their teardown asserts zero Attendance,
  biometric Challenge and VerificationAttempt rows for every diagnostic case.
* Focused Flutter diagnostic, BLE, classroom attendance, preflight and device
  authorization tests: 67 passed.
* `flutter analyze --no-pub`: no issues found.
* Debug APK built with `API_BASE_URL=http://192.168.0.162:8000`.
* No database migration, live diagnostic execution, service restart or APK
  installation was performed. The running backend remains disabled for this
  feature until separately approved deployment. Physical cases A–E are NOT RUN.

The APK build reports existing Gradle/Android Gradle Plugin/Kotlin version
deprecation warnings; it completes successfully without bypass flags.

## Subsequent Xiaomi physical results — reported by the developer

All five physical cases were reported PASS on Xiaomi 7732690b:

| Case | Observed result |
|---|---|
| Correct beacon and approved Wi-Fi | TEST PASS |
| Beacon stopped | TEST FAIL — beacon not found |
| Wrong classroom UUID | TEST FAIL — beacon not found |
| Bluetooth disabled | TEST FAIL — Bluetooth off |
| Invalid classroom Wi-Fi | TEST FAIL — Wi-Fi BSSID mismatch |

These are user-reported physical results, separate from the earlier automated
validation and its initial NOT RUN status. Keep existing diagnostic audit rows
for Chapter 5. Disabling the feature does not delete these rows. Normal real
attendance tests remain separate from these diagnostic outcomes.
