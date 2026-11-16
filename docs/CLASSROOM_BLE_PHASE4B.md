# Phase 4B — standalone experimental classroom BLE verification

This document records the original isolated Phase 4B rollout on backend 8002
and MariaDB 3322. See **Phase 1 classroom observation** below for the current
diagnostic workflow. Phase 4C attendance
integration is **not enabled**. Existing attendance, IP/CIDR, Wi-Fi BSSID,
PIN/session, Keystore, face/liveness and duplicate rules are unchanged.

## Status and assurance

The user confirmed Phase 4A hardware tests: Samsung SM-A346E legacy advertising
works with nRF Connect; Xiaomi saw the test UUID near (-55 dBm median, 23 samples),
far (-101 dBm median, five samples), and not when advertising stopped. These are
**user-reported Phase 4A observations**, not execution of the new signed 4B API.
They do not calibrate a production threshold or establish classroom separation.

A valid Keystore signature identifies which ACTIVE registered device submitted
the report. It does not attest that RSSI or BLE packets are genuine. A static
service UUID can be copied, rebroadcast or relayed; a modified client can fabricate
measurements/timestamps. Equal RSSI values can be legitimate; distinct timestamps
are required, but they are still client reports. No BLE result is campus-IP proof,
institution-verified presence, or attendance authorization.

## Implemented architecture

- New `backend/modules/classroom_ble/` routers, service, policies and separate
  metadata reuse the existing classroom IDs and device authentication/crypto.
- Routes are installed only in `manual_android_test.py`, not the production app
  factory. No public operator mutation API exists.
- Four additive tables: `classroom_ble_policies`, `classroom_ble_challenges`,
  `classroom_ble_events`, `classroom_ble_policy_events`.
- Native BLE diagnostics retains its eight-second limit and Stop action. It now
  records per-service-UUID sample offsets from packets actually received, rather
  than tagging old RSSI values with an identifier cached from an earlier packet.
- Scan owner IDs isolate the general diagnostics card from verification. A
  diagnostics card leaving the viewport cannot cancel a challenge-owned scan.
- Only the explicit **Verify classroom BLE** action scans/signs/uploads. General
  BLE Diagnostics remains local-only. No pairing, automatic enablement or
  background scanning is added. The existing Android permissions remain intact.

## Policy and operator commands (PowerShell 7)

Each policy contains ID, classroom, canonical 128-bit service UUID, optional label,
enabled/retired state, sample minimum, median threshold, maximum sample age,
simulation-only flag, revision and creation/update timestamps.

Defaults are **disabled**, minimum five observations, median threshold **-65 dBm**,
maximum age **15 seconds**. They are experimental defaults, not calibrated campus
values. Allowed ranges: minimum 3–50, threshold -127–0 dBm, age 10–30 seconds.
Policies must be explicitly enabled. Multiple policies are ORed; any approved
beacon meeting its own criteria may PASS. At most eight enabled policies covering
four distinct UUIDs are accepted per classroom. Removal retires/disables without
deleting audit history and cannot be reversed; use a new policy ID if needed.

The live disposable database was migrated but **no policy was seeded/enabled**.

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System
.\fyp-test.ps1 status
.\fyp-test.ps1 ble list

# Add once, initially DISABLED:
.\fyp-test.ps1 ble add --id classroom-a-samsung-test --classroom CLASSROOM_A --uuid 7d9a6c10-326a-4c60-9e01-1ef000000001 --label 'Samsung test beacon - experimental' --minimum-samples 5 --threshold -65 --max-age-seconds 15 --simulation
.\fyp-test.ps1 ble list --classroom CLASSROOM_A
# Explicit operator enable:
.\fyp-test.ps1 ble enable --id classroom-a-samsung-test

# Reversible disable/re-enable:
.\fyp-test.ps1 ble disable --id classroom-a-samsung-test
.\fyp-test.ps1 ble enable --id classroom-a-samsung-test
# Permanent retirement, ONLY when finished:
# .\fyp-test.ps1 ble remove --id classroom-a-samsung-test
.\fyp-test.ps1 ble list --all
```

The existing PS wrapper forwards these implemented `ble` commands to the pinned
offline operator. It cannot take an arbitrary DB URL or fall back to production.
To change threshold/minimum/age, retire the old policy and add a new ID with
reviewed settings, then explicitly enable it. Do not leave a looser old policy
enabled and assume only the new one applies. Shared classroom rows are reused;
no attendance session gets a BLE requirement in this phase.

## Authenticated REST contracts

All three routes require the existing Bearer student session:

1. `GET /api/v1/classroom-ble/classrooms`
   returns `{success:true,simulation_only:true,classrooms:[{classroom_id,name,policies:[...]}]}`.
   Policies expose the reviewed UUID/limits/flags/revision, not nearby-device data.
2. `POST /api/v1/classroom-ble/challenges`

   ```json
   {"classroom_id":"CLASSROOM_A","public_key_fingerprint":"<64 lowercase hex>"}
   ```

   Server verifies current session/student, ownership and ACTIVE public key,
   current enabled policies, and a 20-challenges/student/minute limit. 201 returns
   `success`, `operation:classroom_ble_verification`, `challenge_id`, `classroom_id`,
   `device_id`, `public_key_fingerprint`, `signing_payload` (base64), `expires_at`,
   `approved_policies` and `scan_window_ms:8000`.

   The nonce payload binds student, hashed login session, device/fingerprint,
   classroom, purpose, current enabled-policy hash, server issuance/expiry and a
   random nonce. TTL is 45 seconds or login expiry, whichever is earlier.
3. Flutter obtains a NEW native scan after the nonce, filters approved UUIDs and
   encodes this bounded UTF-8 JSON (illustrative timing, use actual values):

   ```json
   {
     "scan_status":"COMPLETE",
     "bluetooth_enabled":true,
     "scan_permission":"GRANTED",
     "connect_permission":"GRANTED",
     "location_permission":"PRECISE_GRANTED",
     "location_enabled":true,
     "scan_started_at_ms":1794000000000,
     "scan_completed_at_ms":1794000008000,
     "scan_duration_ms":8000,
     "beacons":[{
       "service_uuid":"7d9a6c10-326a-4c60-9e01-1ef000000001",
       "samples":[
         {"offset_us":100000,"rssi_dbm":-55},
         {"offset_us":1100000,"rssi_dbm":-54},
         {"offset_us":2100000,"rssi_dbm":-56},
         {"offset_us":3100000,"rssi_dbm":-55},
         {"offset_us":4100000,"rssi_dbm":-55}
       ]
     }]
   }
   ```

   Offsets use Android's monotonic reception time relative to scan start; cached
   callbacks predating scan start are discarded. No Bluetooth address, name,
   unrelated UUID, manufacturer payload or client-computed median is uploaded.
   At most four UUID groups / 50 total observations / 4500 JSON bytes are allowed.
   The client retains the latest bounded samples, sorts offsets and removes
   duplicate offsets; the backend independently rejects duplicate/unsorted offsets.
4. Sign **decoded server nonce payload + one LF byte + exact observation JSON
   bytes**, base64-encoded for the existing Android Keystore channel. It signs
   SHA256withECDSA P-256 and returns base64 DER. The private key never leaves
   Android. A missing key is not silently recreated. The existing 8192-character
   native signing-input limit is checked before signing.
5. `POST /api/v1/classroom-ble/verifications`

   ```json
   {"challenge_id":"<server challenge>","evidence_payload":"<base64 JSON>","signature":"<base64 DER signature>"}
   ```

   200 returns `success:true`, `result:PASS|FAIL|UNCERTAIN`, `reason_code`, `message`,
   `verification_id`, `challenge_id`, `classroom_id`, `device_id`, `sample_count`,
   backend `median_rssi_dbm`, evaluated threshold/minimum/age, evaluated policy ID,
   matched policy ID (PASS only), `verified_at`, operation,
   `evidence_source:CLIENT_REPORTED_ANDROID_BLE`, `attendance_authorized:false`.
   Proof/schema errors use the existing `{success:false,code,message}` HTTP error
   convention. Client PASS flags, student/device-ID overrides and median fields
   are forbidden. HTTP/transport errors never become a cached authorization.

## Server evaluation and replay handling

The transaction locks student/auth, nonce, ACTIVE device and enabled policy rows.
Wrong-account/session requests cannot consume another owner's challenge. Owned
invalid/expired proofs are consumed and audited. Canonical evidence hashing plus
a student/device/evidence unique constraint rejects the same report re-signed
under another nonce; JSON whitespace, UUID case and beacon-group order do not
create new observations. Policy removal/disable/revision changes after nonce
issuance fail closed. Concurrent confirmations produce at most one successful use.

RSSI values must be integer -127–126 dBm. Offsets must be unique, increasing and
inside the scan. Duration is bounded to ten seconds; a COMPLETE window shorter
than seven seconds is UNCERTAIN. STOPPED/CANCELLED is UNCERTAIN even if some
samples arrived.

The server compares the later of reported completion and scan start plus
duration with its current time at validation. A lead of more than 2,000 ms
returns `BLE_EVIDENCE_FUTURE`. A lead within the cap is subtracted from the
reported start for the challenge issuance check only. A start before issuance
after that adjustment returns `BLE_EVIDENCE_STALE`.

For freshness, the server uses the later of challenge issuance and the
reported start minus 2,000 ms as the earliest plausible start. The 30-second
scan-age limit and each policy's sample-age limit use that start. This prevents
an apparently newer wall-clock reading from extending freshness. Signed bytes,
the replay hash, and server-side session and challenge expiry are unchanged.
The 2,000 ms cap covers the measured 1,500 ms tablet clock lead with 500 ms of
headroom. It applies only to the standalone BLE diagnostic.

If local observation succeeds but the signed check reports a future timestamp,
compare Android's `adb -s <serial> shell date '+%s%3N'` with Windows'
`[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()`. Read Windows before and
after the ADB call to bound the delay. Both readings are epoch milliseconds.
Android uses elapsed real time for the scan duration and packet offsets, and
wall time for scan start and completion. A tablet ahead of the backend can
produce a completion time later than server receipt. Check automatic date and
time on the tablet and sync Windows under **Settings → Time & language → Date
& time → Sync now**, then run a new **Verify classroom BLE** check. A timezone
label change alone does not synchronize the clocks.

A successful NTP refresh can leave a subsecond difference in the operating
system clock. Recheck the measured offset after synchronization. On Windows,
`w32tm /stripchart /computer:time.windows.com /dataonly /samples:5` compares
the host with its time source. On Android, `adb shell dumpsys time_detector`
reports the time source and configured system-clock update threshold. A local
beacon detection still works when these clocks disagree. The signed check may
reject skew above the cap or a scan whose timestamps fail the challenge or
freshness checks.

Backend computes the median from distinct submitted observations for approved
UUIDs only. No beacon => FAIL. Enough fresh samples and median >= threshold =>
PASS. Below threshold => FAIL. Too few samples => UNCERTAIN. With multiple
policies, any PASS wins; otherwise an UNCERTAIN candidate wins over a definite
FAIL. Unrelated advertisers cannot satisfy a policy. Errors/unavailability do
not prove physical absence.

| Code | Result/meaning |
|---|---|
| BLE_APPROVED | PASS, experimental observation criteria met |
| BLE_BEACON_NOT_FOUND | FAIL, no approved UUID in a complete healthy scan |
| BLE_SIGNAL_WEAK | FAIL, backend median below threshold |
| BLE_INSUFFICIENT_SAMPLES | UNCERTAIN, repeat a full scan |
| NO_ENABLED_BLE_POLICY / BLE_POLICY_CHANGED / BLE_POLICY_INVALID | FAIL, configuration unavailable/changed/invalid |
| BLE_PERMISSION_REQUIRED / BLUETOOTH_OFF / BLE_UNAVAILABLE | UNCERTAIN, no supported classroom decision |
| BLE_SCAN_INCOMPLETE | UNCERTAIN, stopped/short scan |
| BLE_EVIDENCE_STALE / BLE_EVIDENCE_FUTURE | FAIL, timing outside bounds |
| BLE_DUPLICATE_OBSERVATION / BLE_EVIDENCE_REPLAYED | Reject repeated samples/report |
| BLE_EVIDENCE_MALFORMED | Reject invalid/oversized data |
| BLE_CHALLENGE_NOT_FOUND / EXPIRED / REPLAYED | Reject ownership/lifecycle mismatch |
| INVALID_DEVICE_SIGNATURE / DEVICE_NOT_ACTIVE | Reject cryptographic/device prerequisite |

Audit rows retain outcome, binding, policy match, count, median and evidence hash,
not raw scans or authentication tokens. General diagnostics still never uploads.

## Migration, backup and recovery

Verified private backup: `C:\FYP\DB-DeviceManagement\classroom-ble-backup-20261108-0340`.
The existing migration tool now accepts `--component ble`. It verifies the pinned
actual 3322 schema/account/datadir/version, stops only the identity-verified 8002
backend, dumps all 39 pre-existing InnoDB tables with matching private config,
restores into a fresh schema and compares every original row/hash. It runs the
four-table migration twice and CHECK TABLE before applying to the disposable
source, then compares source rows again. No production SQL or schema is touched.

Runtime grants: SELECT policies; SELECT/INSERT/UPDATE challenges; INSERT-only
verification events. Operator policy audits have no runtime grant. Existing
runtime grants remain. No policy is seeded or enabled by migration.

Future explicit repeat (use a NEW private backup folder; already applied here):

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_classroom_wifi_test.py --component ble --apply --output C:\FYP\DB-DeviceManagement\ble-backup-NEW-UNIQUE
.\fyp-test.ps1 start --lan
```

If anything fails, the tool leaves the backend stopped. Preserve that backup and
config; restore to another new schema first, compare and review. Do not overwrite
the source or reset its database. The tested recovery path is a verified logical
restore into a separate schema, not destructive rollback over existing records.

## Xiaomi build, update and manual test

No APK was installed automatically. Build uses the existing intended private LAN
URL `http://192.168.0.162:8002`; recheck the operator's READY URL if it has changed.

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System\frontend
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.0.162:8002
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
& $adb -s 7732690b install -r 'C:\FYP\FYP-Biometric-Attendance-System\frontend\build\app\outputs\flutter-apk\app-debug.apk'
if ($LASTEXITCODE -ne 0) { throw 'STOP. Do not uninstall, clear data, or recreate keys.' }
& $adb -s 7732690b shell am start -n com.example.frontend/.MainActivity
```

1. On Samsung use the existing separate nRF Connect legacy advertiser, service
   UUID `7d9a6c10-326a-4c60-9e01-1ef000000001`, small payload/no personal name.
   Keep its original Attend app and Keystore untouched. Advertising success was
   confirmed by the user in Phase 4A; keep the advertiser foreground for this test.
2. Keep Xiaomi/laptop on the reachable home/private LAN. Log in as **FYPTEST001**
   using the existing assigned credentials and ACTIVE tablet key. Enable Bluetooth,
   Nearby Devices, precise location and Location Services through the existing
   diagnostics controls; no silent enable or pairing.
3. Add/enable the policy above. Open Network Verification → **Classroom BLE
   Verification**, Reload BLE policies, select CLASSROOM_A, press Verify.
4. Near beacon: if >=5 approved samples, age passes and backend median >=-65,
   expect PASS. Far: median below -65 should FAIL BLE_SIGNAL_WEAK; fewer than
   five samples => UNCERTAIN. The old 4A counts may differ because only actual
   UUID-tagged packets now count.
5. Stop advertising: a full healthy window should FAIL BLE_BEACON_NOT_FOUND.
   Advertise a different test UUID ending `0002`: it must not satisfy the `0001`
   policy. Other nearby devices remain visible in general diagnostics but are
   filtered out of the upload.
6. Bluetooth OFF/permission denied => UNCERTAIN with the actual reason; backend
   unreachable/timeout => UNCERTAIN, no confirmed policy verdict. Disable policy
   => FAIL NO_ENABLED_BLE_POLICY. Restore only the test settings you intended.

Record actual server code, count, median, threshold, scan duration/age and test
location privately. Repeat multiple windows with transmitter power/interval and
scanner orientation controlled. Phase 4B physical tests are **NOT RUN** until this
new APK/API flow is executed. The earlier 4A radio tests are separate evidence.

BLE diagnostic PASS may coexist with IP/CIDR FAIL: neither diagnostic authorizes
attendance. USB reverse remains invalid campus-IP proof. Do not start a tunnel or
weaken source-IP checks to make a test pass. A connection timeout is never proof
of beacon absence.

## Phase 4C remains separate

Before actual attendance enforcement: evaluate RSSI overlap across real rooms,
agree uncertainty/retention/security semantics, then separately approve mapping
session requirements, immutable attempt snapshots and fresh BLE proof binding to
the existing final writer. Never reuse this standalone PASS or replace current
device/IP/Wi-Fi/PIN/biometric checks. Static beacons/relay and fabricated signed
reports need an explicit threat model; stronger assurance may require authenticated
rotating or challenge-response beacon hardware. No 4C endpoint/adapter is enabled.

## Phase 1 classroom observation

On **Network Verification → Classroom BLE Observation**, select a classroom
with an enabled service UUID and choose **Observe classroom beacon (8 seconds)**.
The existing Android scanner accepts packets timestamped inside that scan,
counts packets that actually carried the configured UUID and calculates median
RSSI over retained matching samples. It never pairs. A weak observation still
means detected. An empty completed scan means not detected. Bluetooth,
permissions, timeout and stale or incomplete data produce an unavailable result.

Local observation works with the existing authenticated classroom policy list.
It does not submit a record or need a new backend version. **Verify classroom
BLE** remains an optional fresh, signed server check through the existing
challenge and verification endpoints. Its response adds observation status,
scan duration and the observed configured UUID when detected. The existing
policy verdict and freshness checks still apply. Audit records bind to the
classroom, student and registered installation, with no attendance session
binding. The original admin panel can show the last signed-check result per
classroom without exposing student or device identifiers. Scoped panels without
access to the BLE event table only show policy configuration.

Use the existing **Experimental BLE** admin form to add and enable a test
policy. UUIDs are validated and canonicalized. An enabled UUID cannot be
assigned a second active policy, and a classroom can enable up to four UUIDs.
Previously stored policies remain untouched. These guards and the signed
observation summary require the updated backend or panel process respectively.
No schema migration or attendance authorization change is needed.

For a physical check, use an explicitly configured test policy for the
Windows beacon UUID and, for the wrong-UUID control, a different enabled
test policy in another classroom. Scan at 1–2 metres, repeat after stopping
the beacon, then repeat at a greater distance. Record detection, duration,
advertisement count and median RSSI. Use a fresh scan for each comparison.
RSSI depends on distance, obstructions and radio conditions. The reported
UUID and RSSI are untrusted diagnostic observations.

## Attendance shadow mode and Chapter 5 evidence

The student enters the PIN and completes the existing signed device and
network preflight, including classroom Wi-Fi when required. When that
preflight identifies a classroom, Flutter opens the existing biometric camera
and independently requests a BLE challenge. The BLE panel in the camera
route displays progress and the diagnostic result. It never waits before
opening the camera, requests no new permissions, and does not retry the scan.
It cancels a pending scan on leaving the route or after an 18-second UI budget.
Classrooms without an enabled BLE policy get no scan. Sessions without a
classroom skip the BLE request altogether.

The existing `POST /api/v1/classroom-ble/challenges` accepts the optional pair
`attendance_attempt_id` and `preflight_proof_id` alongside `classroom_id` and
`public_key_fingerprint`. With the pair present the server chooses operation
`attendance_ble_shadow`, checks the classroom snapshot and a consumed PASS
preflight for the same login, attempt and device, and limits issuance to one
challenge per attempt. The same nonce and evidence-signing protocol and
`POST /api/v1/classroom-ble/verifications` endpoint apply. Confirm revalidates
the live attempt binding and ACTIVE key. Shadow results always contain
`attendance_authorized: false`. Final attendance uses its own device proof,
Wi-Fi and CIDR checks, and genuine face and liveness completion. It neither
reads nor consumes BLE receipts. Old Flutter builds can continue taking
attendance without shadow checks.

No schema migration is needed. The existing BLE challenge stores the signed
attempt binding. Its server-derived primary key limits duplicate issuance and
lets the admin panel join results to the existing attendance attempt snapshot.
The existing BLE event table retains its diagnostic audit. The authenticated
original panel's **Experimental BLE** page lists the last 50 attempt snapshots
with local time, classroom, numeric verification attempt, session, result and
reason. It displays PASS, FAIL, UNAVAILABLE or NOT CHECKED. An issued check
without a result is pending until the attempt ends or the BLE deadline expires,
then it becomes UNAVAILABLE. A request that never reaches issuance leaves
NOT CHECKED. When a bound request has no enabled BLE policy, the app displays
**BLE not configured for this classroom** and the panel records
`NO_ENABLED_BLE_POLICY` without issuing a scan. A logged Wi-Fi preflight
failure can also explain NOT CHECKED in the panel. Client timeouts cannot be inferred from the server alone, and a
committed result may appear in the panel even if the client never received it.
This panel shows the device used for preflight only through the associated
result. It does not expose device identifiers, signed payloads, or templates.
Scoped simulation panel profiles retain their existing permissions and show
attempt monitoring as unavailable.

The 2,000 ms future cap and conservative scan and sample ages above also
apply to shadow checks. A client with access to its own signing key can still
report observations that the server cannot independently confirm. Static
service UUIDs can be copied or relayed, and RSSI varies with hardware,
orientation, obstructions and radio interference. Report the BLE result as
classroom diagnostic evidence and keep attendance enforcement independent.

### Deployment and rollback

Run the original read-only startup check. After separate service approval,
stop only the identified port 8000 listener and start the existing launcher.
If the current live backend is loopback-only, use `--lan` for the Xiaomi.
Leave MariaDB running. Restart the existing panel separately after approval
to load its new view. Run these in separate PowerShell terminals.

```powershell
$repo = 'C:\FYP\FYP-Biometric-Attendance-System'
& "$repo\start-fyp.ps1" check
& "$repo\backend\venv\Scripts\python.exe" "$repo\backend\original_fyp.py" serve-backend --lan --local-demo-slot2
```

```powershell
$repo = 'C:\FYP\FYP-Biometric-Attendance-System'
& "$repo\backend\venv\Scripts\python.exe" "$repo\backend\original_fyp.py" serve-panel
```

Check loopback `/local-fyp/identity`, loopback and LAN `/config`, and
`http://127.0.0.1:8003/ble` through the existing admin login. Verify the current
Wi-Fi IPv4 and Xiaomi serial before running the LAN installer. For a laptop
still using `192.168.0.162`, the install command is:

```powershell
& 'C:\FYP\FYP-Biometric-Attendance-System\install-fyp-android.ps1' -Serial 7732690b -LanIp 192.168.0.162
```

For rollback, use the previous source and APK checkpoint and the same approved
backend and panel launchers. There is no schema rollback and existing BLE audit
rows can be retained. The old APK skips shadow requests. The new APK treats a
missing or incompatible shadow endpoint as an optional diagnostic failure and
continues the existing attendance flow.

### Physical test checklist

Use the existing authorized Wi-Fi, enrolled Xiaomi and approved FYP class
sessions. Use a fresh legitimate attendance session for each case so duplicate
prevention cannot obscure the diagnostic outcome.

Check the actual classroom IDs in all three places before testing: the
session assignment, the enabled Wi-Fi policy's classroom, and the enabled BLE
policy's classroom. A policy's own ID is independent of the classroom it is
assigned to. In the original test configuration, `ClASSROOM_A` and
`ClASSROOM_B` had BLE policies, while the Wi-Fi policies were assigned to
`Classrooom_A` and `Classs_B`. Configure approved Wi-Fi for the exact BLE
classrooms before using them in a test session. A Wi-Fi preflight rejection
does not start the optional BLE scan. A completed, healthy scan with no
matching UUID returns `BLE_BEACON_NOT_FOUND`.

| Scenario | Expected BLE outcome | Attendance expectation |
|---|---|---|
| Classroom A, `SENGHIN` running | `BLE_APPROVED` if count and RSSI meet policy | One record if all existing checks pass |
| Classroom A, beacon stopped | `BLE_BEACON_NOT_FOUND` | One record if all existing checks pass |
| Classroom B, only Classroom A UUID transmitting | `BLE_BEACON_NOT_FOUND` | One record if all existing checks pass, including B's Wi-Fi |
| Bluetooth off with Wi-Fi available | `BLUETOOTH_OFF` or unavailable | Camera and attendance remain usable under existing checks |
| Repeat a completed session | Existing duplicate rejection | No additional attendance record |
| Valid BLE, then an unauthorized final network or Wi-Fi | Independent BLE result | No attendance record |

For Chapter 5, record the APK/backend version, attempt and session numbers,
admin status and reason, and attendance count before and after each case.
Use redacted screenshots. Record the earlier standalone Xiaomi results as
standalone evidence. Mark physical attendance shadow cases **NOT RUN** until
the new APK and both services are deployed and the Xiaomi tests are executed.

Automated evidence for this implementation run on `SH`: the focused backend
BLE, attendance, classroom Wi-Fi and original panel suites reported 104 passed
and two skips for real MariaDB row-lock tests. They used in-memory fixtures,
real ECDSA signatures and the actual attendance writer with synthetic inputs.
The focused Flutter suites reported 54 passed, Flutter analysis reported no
issues, and the LAN-configured Android debug APK built successfully. The
tablet attendance shadow flow and live admin view still require deployment
and physical verification.
