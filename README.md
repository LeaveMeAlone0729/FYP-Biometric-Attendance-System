# Attend student attendance system

Flutter Android app, FastAPI biometric services and MySQL for the **facial recognition and liveness detection module** of the Mobile Biometric Attendance System. Login, class PINs and attendance history provide a working demo around the biometric module. The student workflow is:

**Six-digit class PIN → group and class-window validation → facial match → random finger-count challenge → attendance confirmation.**

Attendance is inserted only after all checks pass. Face verification alone cannot record attendance.

Module owner: **Chew Zhexuan**. See the [module/file map](docs/MODULE_OWNERSHIP.md)
and [API integration guide](docs/API_INTEGRATION.md) for the organized code,
request contracts, teammate integration points and importable OpenAPI file.

Device registration is now available as the teammate's separate Phase 1 module in the shared backend and Android app; see [the registration guide](docs/DEVICE_REGISTRATION.md). Installation binding for attendance, device replacement, Wi-Fi/campus verification and IP allowlists are not enforced yet. The phone still needs an ordinary connection to the backend API.

For an existing database, run `backend\venv\Scripts\python.exe backend\migrate.py` from the project root before restarting the updated backend. This removes only the retired `device_hash` columns from `students` and `auth_sessions`, preserving accounts, encrypted face templates, consent, login sessions and attendance history. `setup.py` also applies this idempotent migration; fresh databases already use the current schema.

## Start on this Windows computer

1. Start **MySQL in XAMPP**. Keep Laragon's MySQL stopped: both installations use port 3306, so they cannot run on that port together. The attendance app uses XAMPP's separate `attendance_proposal_xampp` database.
2. If dependencies or the database have not been initialized, run from `C:\Users\User\source\repos\FYP-Biometric-Attendance-System`:

   ```powershell
   cd backend
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   .\venv\Scripts\python.exe setup.py
   cd ..
   cd frontend
   flutter pub get
   cd ..
   ```

   The existing virtual environment uses Python 3.12. If rebuilding it on another computer, install Python 3.12 and create a new `backend\venv` first. `face_recognition` needs dlib; compiling dlib on Windows requires CMake and the Visual C++ build tools. The existing environment already contains dlib.

3. Start the API in one PowerShell terminal:

   ```powershell
   .\start-backend.ps1
   ```

   Check `http://localhost:8000/docs`. If port 8000 is already used by the existing reloading backend, use that terminal or stop its process with Ctrl+C before starting another.

4. Start an Android emulator, then run in a second terminal:

   ```powershell
   .\start-frontend.ps1 -DeviceId emulator-5554
   ```

   Android emulator API address defaults to `http://10.0.2.2:8000`. For a physical phone on the same Wi-Fi:

   ```powershell
   .\start-frontend.ps1 -DeviceId YOUR_DEVICE_ID -ApiBaseUrl http://YOUR_PC_IPV4:8000
   ```

   `flutter devices` lists device IDs. The URL is configured in one place using `API_BASE_URL`; no Dart source edits are needed.

## Realistic sample data for testing

Run `./seed-sample-data.ps1` to add 36 fictional students with realistic names and
academic IDs, courses, weekly timetables and varied attendance history. See
[SAMPLE_DATA.md](SAMPLE_DATA.md) for accounts, class PINs, the 2 November testing
schedule, and the current student-only role limitation. The generated account
list is `.work/testing-accounts.txt`.

## Original single-account demonstration

- Student ID: **DEMO001**
- Password: **DemoAttend2026!**
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
| Privacy | Encrypted facial encodings, no permanent raw capture storage, explicit biometric-template deletion |

The eight main entities are `programmes`, `student_groups`, `students`, `courses`, `class_schedules`, `class_sessions`, `attendance`, and `verification_attempts`. `auth_sessions` and `verification_challenges` support secure workflow state. The database uses `student_groups` to avoid the SQL keyword `GROUP`.

## Configuration and boundaries

`backend/setup.py` creates the ignored `backend/.env` from `.env.example` with a random Fernet key. Back up this key securely with the database; changing or losing it makes existing biometric templates unreadable. Do not commit it.

- `DB_NAME=attendance_proposal_xampp` is the active schema. Obsolete prototype databases were archived and removed during the 29 October 2026 cleanup; see [CLEANUP.md](CLEANUP.md).
- `DEMO_MODE=true` enables demo fixtures, demo labels and self-registration. In production mode, student accounts and groups must be provisioned by an operator; clients cannot choose their own academic group.
- `APP_TIMEZONE=Asia/Kuala_Lumpur` controls all academic dates and class windows. `tzdata` is required on Windows. The camera timer uses elapsed time rather than the emulator's wall clock.
- `CHALLENGE_SECONDS=90` limits the complete verification flow. Logout, cancellation, successful completion and template deletion invalidate pending challenges.
- `FACE_DISTANCE_THRESHOLD=0.45` preserves the original project's matching threshold. Calibrate it using consented research participants rather than treating it as an evaluated accuracy guarantee.
- Login accepts `student_id` and `password` only. `/me` reports the student and biometric status. Neither login nor biometric/attendance responses include device or network verification flags. Challenge ownership remains bound to the authenticated login, with expiry and single-use enforcement.
- The example uses local HTTP for emulator development. Use HTTPS and a restricted database account before handling real students over a shared network. Keep the database reachable only by the backend.
- A randomized 2D hand gesture is an academic liveness heuristic, not certified presentation-attack detection. It does not prove resistance to all prerecorded videos, composites, deepfakes or modified clients. Conduct the proposal's authorized spoofing and usability evaluation before making effectiveness claims.
- Biometric registration verifies the signed-in student's account ownership but does not independently prove the first enrolled face belongs to an institutionally verified person. Real deployment needs supervised identity enrollment and account recovery.

Camera captures are temporarily produced by the device camera plugin, read for upload and removed immediately. The backend processes the received image in memory and stores only encrypted encodings and verification outcomes. Multipart upload buffering may use OS temporary storage; there is no application-level photo archive.

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
# Optional live MySQL regression, with the demo backend running:
$env:ATTENDANCE_API_URL = 'http://127.0.0.1:8000'
.\venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:ATTENDANCE_API_URL
cd ..\frontend
flutter analyze
flutter test
flutter build apk --debug
```

Backend tests use an isolated in-memory SQL database and synthetic biometric responses for deterministic workflow checks. Additional tests run the actual face detector and MediaPipe model on blank images and verify rejection. These tests establish workflow behavior, not real-world biometric accuracy. Real face/gesture acceptance, device compatibility and spoof resistance still require consented camera testing.

Original source and earlier work artifacts are archived in `.work/cleanup-20261029/work-history.zip`.

The app database was transferred from Laragon to XAMPP after a port-3306 conflict. It uses `attendance_proposal_xampp`. Earlier migration backups are in `.work/cleanup-20261029/work-history.zip`; current cleanup backups are described in [CLEANUP.md](CLEANUP.md). Use XAMPP's MySQL control for this project and leave Laragon's MySQL stopped.

Implementation references: [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python), [Flutter camera plugin](https://pub.dev/packages/camera), [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/).

## Device registration — Phase 1

Student → Account & Sign Out → **My Device** registers one Android installation
using an Android Keystore public key and signed server challenge. Apply the
additive migration with `backend\venv\Scripts\python.exe backend\migrate_devices.py`.
See [device registration setup, REST contracts and USB testing](docs/DEVICE_REGISTRATION.md).
Registration does not yet gate attendance; login and the biometric/liveness flow
continue unchanged. No device replacement shortcut is provided.
