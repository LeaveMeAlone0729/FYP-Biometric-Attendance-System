# FYP Biometric Attendance System

For the preferred **new isolated MySQL teammate setup**, use
[MySQL testing setup](docs/MYSQL_TESTING.md). It preserves the existing MariaDB
environment and does not change the original database or port 8000 defaults.

Flutter Android and FastAPI with MySQL or MariaDB. The student workflow is:

**Six-digit class PIN → group/class-window validation → device/network preflight → facial match and passive anti-spoofing → random finger-count challenge → final device/network authorization and any session-specific classroom Wi-Fi check → attendance confirmation.**

Attendance is inserted only after all checks pass. Face verification alone cannot record attendance.

For synthetic Android testing on isolated MariaDB **3322** and FastAPI **8002**,
use the [simple private-LAN workflow](docs/FYP_NETWORK_TEST_WORKFLOW.md):
`./fyp-test.ps1 start --lan`, then configure an explicitly labeled simulation
policy with `./fyp-test.ps1 policy set --cidr <test-CIDR> --simulation`.
Login/profile access is separate from attendance network authorization. Do not
use the original production launcher or database for this disposable exercise.

Passive anti-spoofing runs during face matching and on every counted finger frame. Its temporary scores and frame evidence stay in server memory, bound to the student, login and challenge; they are cleared on completion, cancellation or expiry. No `face_liveness_state` database column is required. Use one backend worker. A backend restart or reload requires a fresh PIN challenge for any unfinished verification; saved attendance remains available.

Module owner: **Chew Zhexuan**. See the [module/file map](docs/MODULE_OWNERSHIP.md)
and [API integration guide](docs/API_INTEGRATION.md) for the organized code,
request contracts, teammate integration points and importable OpenAPI file.

Attendance requires an active Android Keystore registration and an authorized CIDR. A session assigned to a classroom also requires its configured Wi-Fi check. [BLE](docs/CLASSROOM_BLE_PHASE4B.md) remains experimental and separate from attendance.

## Start from a fresh checkout on Windows

Use PowerShell 7 from the cloned repository. Install Python 3.12, Flutter with
Dart 3.11 or compatible, and the Android SDK. If dlib must compile, install
CMake and the Visual C++ build tools.

1. Install dependencies and the checksum-verified hand and anti-spoofing models. The model
   command does not load database settings or initialize a schema.

   ```powershell
   py -3.12 -m venv backend\venv
   .\backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   .\backend\venv\Scripts\python.exe .\backend\setup.py --model-only
   Push-Location frontend
   flutter pub get
   Pop-Location
   ```

2. Provision your own disposable MySQL profile using the tested MySQL
   Community 8.4.3 binaries. Setup creates the current 43-table schema,
   per-environment credentials and a synthetic school-provisioned student.
   Start the panel with the administrator password you choose interactively.

   ```powershell
   $mysqlHome = Read-Host 'MySQL 8.4.3 installation folder'
   .\fyp-mysql.ps1 setup --mysql-home $mysqlHome
   .\fyp-mysql.ps1 admin-init
   .\fyp-mysql.ps1 start
   .\fyp-mysql.ps1 status
   ```

   The panel is at [127.0.0.1:8013/login](http://127.0.0.1:8013/login) and the
   API at [127.0.0.1:8012/docs](http://127.0.0.1:8012/docs) by default.
   See [MySQL setup](docs/MYSQL_TESTING.md) for the private synthetic credentials,
   port overrides, migrations and shutdown.

3. For the emulator, select a device listed by `flutter devices` and run:

   ```powershell
   .\start-frontend.ps1 -DeviceId emulator-5554 -ApiBaseUrl http://10.0.2.2:8012
   ```

   For an explicitly configured private-LAN backend on port 8000, use:

   ```powershell
   $deviceId = Read-Host 'Flutter device ID'
   $lanIp = Read-Host 'Laptop private-LAN IPv4'
   .\start-frontend.ps1 -DeviceId $deviceId -ApiBaseUrl "http://${lanIp}:8000"
   ```

   The disposable MySQL profile binds to loopback. A physical attendance PASS requires a reachable
   LAN backend and matching CIDR. ADB reverse is transport for login and other
   permitted tests. Loopback cannot authorize attendance.

For an existing database, use the appropriate [original MariaDB guide](docs/ORIGINAL_FYP_SETUP.md)
or [disposable MySQL guide](docs/MYSQL_TESTING.md). Verify the schema and a
consistent backup before applying reviewed migrations. Keep `backend/.env`,
database credentials, biometric encryption keys and admin credentials local.
Setup scripts for fresh profiles should not be run against an existing schema.
The new runtime does not need the legacy face_liveness_state column. If
retiring it or older device_hash columns, review backend/migrate.py and
run it explicitly only against the backed-up intended schema.

## Synthetic sample data

Use the disposable setup above for normal testing. The legacy seed-sample-data.ps1
script is intended only for a reviewed synthetic database. Keep generated
account lists and data exports private. Choose a unique initial password at
the interactive prompt. Existing sample account passwords are preserved.

## Original single-account demonstration

- Student ID: **DEMO001**
- Use the assigned password. Legacy commits published a demo fixture password.
  Treat it as exposed wherever it is still accepted. Fresh legacy demo setup
  prompts for a unique password and preserves existing accounts.
- Group: **DEMO-A**
- Attendance PINs: **123456** for Biometric Attendance Lab, **654321** for Software Security.
- DEMO-B is a separate group with PIN **222222**. DEMO-A students cannot use it.

You can also create your own demo student account from the sign-in screen. Demo class windows run all day in Kuala Lumpur time. Dated sessions for today and the preceding three days are generated for demonstration; these are not real institutional attendance records. Historical demo sessions are counted as eligible classes, with zero attendance until actual successful submissions exist. No successful biometric results are prefilled.

1. Sign in and open **Student → Register Face**.
2. Read the consent text and enable consent. The 30-second automatic face scan starts when the camera is ready. Center your face in the circle; red means adjust your position, green means hold still. A second clear frame registers your face automatically.
3. Open **Student → Attendance**, enter a class PIN and tap the circular check button. Hold the delete key to clear all six digits.
4. Face verification starts automatically, with a 30-second face-scan limit inside the existing 90-second attendance challenge. The circle turns red for recoverable detection/positioning issues and green when your face matches. Hold still for the second check; the server then chooses a random number from one to five. A different person's face ends the attempt.
5. Show that many fingers on **one hand**, palm facing the camera, alongside your visible face. The face circle is replaced by a guide around the full camera frame: **neither your face nor your hand needs to be centered** during the gesture. Keep your hand separate from your face and all fingertips in view; move the phone slightly farther away if necessary. The frame turns green for accepted checks and red when you need to adjust. Hold steady for three consecutive checks; attendance is recorded automatically after the final check.
6. Confirm the result; view the recorded class and time in **Attendance → Today**, or course percentages in **Overall**. The Student page also provides Verification Activity and Account & Sign Out.

Use a physical phone with a working front camera to evaluate facial and hand accuracy. Emulator virtual scenes often do not contain a usable real face or hand. Enable the host webcam in the AVD camera settings if testing on the emulator.

For this computer's Pixel 10 Pro XL AVD, the front camera uses `webcam0` (HD Webcam), and the rear camera uses `emulated`. Cold boot the AVD after changing camera settings so Android reloads the camera configuration. Keep the webcam free for the front camera while testing attendance.

## Proposal coverage

| Requirement | Implemented behavior |
| --- | --- |
| FR-01 attendance PIN | Six editable PIN slots, keypad, clear/delete and validation |
| FR-02 active class | Server checks PIN, academic date, class window, status and student's assigned group |
| FR-03 face registration | Front-camera capture, informed consent, exactly one face, encrypted template |
| FR-04 face verification | `face_recognition` encoding comparison using configured distance threshold |
| FR-05 random challenge | Server chooses 1–5 fingers only after a successful facial match |
| FR-06 liveness | MediaPipe hand landmarks; same registered face must remain visible in every evaluated frame |
| FR-07 verification order | Server-side, expiring, single-use challenge bound to the authenticated account and session |
| FR-08 recording | Atomic attendance write and unique student/class-session constraint |
| FR-09 result | Separate face, gesture and attendance outcomes with recorded time |
| FR-10 unsuccessful attempts | Failed PIN, face and gesture checks recorded; own activity visible in History |
| Attendance history | Real course records and computed percentages; no hardcoded percentages |
| Account protection | PBKDF2 password hashes, revocable expiring bearer sessions, server-side ownership checks |
| Privacy | Encrypted facial encodings, no permanent raw capture storage; removal requests handled by the department |

The eight main entities are `programmes`, `student_groups`, `students`, `courses`, `class_schedules`, `class_sessions`, `attendance`, and `verification_attempts`. `auth_sessions` and `verification_challenges` support secure workflow state. The database uses `student_groups` to avoid the SQL keyword `GROUP`.

## Configuration and boundaries

`backend/setup.py` creates the ignored `backend/.env` from `.env.example` with a random Fernet key. Back up this key securely with the database; changing or losing it makes existing biometric templates unreadable. Do not commit it.

- `DB_NAME=attendance_proposal_xampp` is the active schema. The guarded original launcher verifies this target before use.
- `DEMO_MODE=true` enables legacy demo fixtures and self-registration. Leave it
  disabled for real accounts. The separate `FYP_ACCOUNT_BOUND_ENROLLMENT` option
  accepts only the genuine first enrollment of a school-provisioned account.
- `APP_TIMEZONE=Asia/Kuala_Lumpur` controls all academic dates and class windows. `tzdata` is required on Windows. The camera timer uses elapsed time rather than the emulator's wall clock.
- `CHALLENGE_SECONDS=90` limits the complete verification flow. Logout, cancellation and successful completion invalidate pending challenges.
- `FACE_DISTANCE_THRESHOLD=0.45` preserves the original project's matching threshold. Calibrate it using consented research participants rather than treating it as an evaluated accuracy guarantee.
- Login accepts `student_id` and `password` only. `/me` reports the student and
  biometric status. Attendance preflight and final authorization perform their
  own device and network checks. Challenges are bound to the authenticated
  session, expire, and are single-use.
- The example uses local HTTP for emulator development. Use HTTPS and a restricted database account before handling real students over a shared network. Keep the database reachable only by the backend.
- A randomized 2D hand gesture is an academic liveness heuristic, not certified presentation-attack detection. It does not prove resistance to all prerecorded videos, composites, deepfakes or modified clients. Conduct the proposal's authorized spoofing and usability evaluation before making effectiveness claims.
- Biometric registration verifies the signed-in student's account ownership but does not independently prove the first enrolled face belongs to an institutionally verified person. Real deployment needs supervised identity enrollment and account recovery.

Camera captures are temporarily produced by the device camera plugin, read for upload and removed immediately. The backend processes the received image in memory and stores only encrypted encodings and verification outcomes. Multipart upload buffering may use OS temporary storage; there is no application-level photo archive.

## Facial registration and recovery

Students register their own face once with consent. After enrollment the template
is locked: the student app has no delete or replacement action, and the former
`DELETE /biometrics` endpoint is removed. A repeat `POST /register-face` returns
409 without changing the template. An inactive registration or an active
registration with missing template data also requires department assistance.

For repeated recognition failures, students ask the lecturer to record attendance
manually through the lecturer's attendance service, then visit the department for
identity verification and supervised re-registration. Facial data removal requests
are also handled by the department. Department authorization/reset and manual
attendance belong to the teammate's services; this change does not implement
those workflows or expose a student reset API. Their authenticated API contracts
must be supplied before connecting recovery. Existing templates and attendance
records are preserved; no database migration is needed.

The first enrollment still requires institutional supervision for verified identity;
locking later changes does not establish whose face was initially enrolled.

## Local operator tools

Run these from `backend` with the virtual environment's Python. These operations are unavailable through student API routes.

```powershell
# Create a real academic programme/group when moving beyond demo data.
.\venv\Scripts\python.exe manage.py create-group --programme-code CS --programme-name "Computing Programme" --name G1 --year-of-study 3 --semester 1 --academic-year 2026

# Provision an account (password is entered securely at the prompt).
.\venv\Scripts\python.exe manage.py create-student STUDENT_ID --name "Student Name" --email student@example.test --group-id 1

# Create a dated class session. Date/time must match the intended attendance window.
.\venv\Scripts\python.exe manage.py create-session --group-id 1 --course-code CS101 --course-name "Example Course" --date 2026-10-21 --start 10:00 --end 12:00 --venue "Lab A" --lecturer "Example Lecturer" --pin 830641
```

## Verification

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest discover -s tests -v
# Optional pytest runner, installed separately from runtime dependencies:
.\venv\Scripts\python.exe -m pip install pytest
.\venv\Scripts\python.exe -m pytest -q
cd ..\frontend
flutter analyze
flutter test
flutter build apk --debug
```

Backend tests use an isolated in-memory SQL database and synthetic biometric responses for deterministic workflow checks. Additional tests run the actual face detector and MediaPipe model on blank images and verify rejection. These tests establish workflow behavior, not real-world biometric accuracy. Real face/gesture acceptance, device compatibility and spoof resistance still require consented camera testing.

Local backups,
logs, build artifacts and test evidence are kept outside the shared source.

Implementation references: [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python), [Flutter camera plugin](https://pub.dev/packages/camera), [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/).

## Android device registration and replacement

Open Student → Account & Sign Out → My Device. The app generates a
Keystore key and proves possession to register or verify an installation.
The account can have two active slots. Adding a second device or replacing
one requires fresh bound face/liveness and key proof against an eligible
enrollment. See [device management](docs/SELF_SERVICE_DEVICE_MANAGEMENT.md)
and the [approval contract](docs/TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md).

The opt-in [ACCOUNT_BOUND_FYP policy](docs/FYP_ACCOUNT_BOUND_ENROLLMENT.md)
records the first enrollment of a school-provisioned account. The explicit
[LOCAL FYP DEMO workflow](docs/SUPERVISED_ENROLLMENT_VERIFICATION.md#local-fyp-demo-on-the-original-server)
is test-only and leaves institutional assurance UNVERIFIED. Keep the
demo credential, enrolled faces and device bindings on their original installation.

## Phase 4 network verification

Profile provides an independent Network Verification diagnostic. The backend
matches the actual ASGI peer IP against enabled database CIDRs. The diagnostic
does not authorize attendance. See [the Phase 4 contract and operator CLI](docs/NETWORK_VERIFICATION_PHASE4.md).

## Phase 5 mandatory attendance authorization

Attendance now requires server-confirmed face/liveness, a fresh attempt-bound Keystore signature from an ACTIVE registration and a matching enabled CIDR policy on the final request. The existing /liveness/frame writer is guarded; old APKs without the new proof cannot record attendance. No production policy was seeded, and USB localhost is denied. Use an isolated restored database for later home/Samsung tests. See [implementation report and exact testing instructions](docs/ATTENDANCE_AUTHORIZATION_PHASE5.md).
## Original local setup

Use [the original-environment guide](docs/ORIGINAL_FYP_SETUP.md) for database
3306, backend 8000 and localhost panel 8003. The pinned launcher checks all
43 application tables before use.
Do not use setup/reset scripts or treat application readiness as proof that the
earlier MariaDB system-table corruption has been repaired.
