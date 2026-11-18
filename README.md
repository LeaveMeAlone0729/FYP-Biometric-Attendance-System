# FYP Biometric Attendance System

Flutter Android app with a FastAPI backend and MySQL/MariaDB.

## Run on your laptop

Start Laragon MySQL, then run these commands from the project root:

```powershell
.\fyp-start.ps1 -Mode Local
.\fyp-install.ps1 -Mode Local
.\fyp-stop.ps1 -Mode Local
```

Local mode uses your private database profile. Your configured Laragon database
is `biometric_attendance` on port `3306`. The phone and laptop must share the
reachable LAN. The launcher checks the database and backend identity before
installing. Open the local admin panel at `http://127.0.0.1:8003/login` to create
an attendance session and get its PIN. Apache is not required for the API.

See [Local setup and troubleshooting](docs/PARTNER_LOCAL_MODE.md) for first-time
configuration, credentials and port conflicts. Keep the laptop and MySQL running
while using the app.

The teammate's Cloudflare workflow remains available through the same three
commands without `-Mode Local`. Full is still the command default; see
[Full mode](docs/FYP_THREE_COMMANDS.md). A domain does not run the backend itself.

## First-time dependencies

Use Python 3.12, Flutter with Dart 3.11 or compatible, and the Android SDK.
Building dlib may require CMake and Visual C++ build tools.

```powershell
py -3.12 -m venv backend\venv
.\backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\venv\Scripts\python.exe backend\setup.py --model-only
Push-Location frontend
flutter pub get
Pop-Location
```

The model-only command downloads verified models without changing the database.
Keep `backend/.env`, the existing biometric encryption key, private profiles and
database backups secure. Replacing the key makes existing face templates unreadable.

## Project layout

| Folder | Contents |
| --- | --- |
| `backend/` | API, operator tools and feature modules |
| `frontend/` | Flutter app, Android bridge and assets |
| `scripts/` | Optional launch, install and administration helpers |
| `docs/` | Current setup and integration guides |
| `runtime/` | Local process ownership and service state; generated and ignored |

Only the three daily commands stay at the root. Optional tools now use paths
such as `.\scripts\start-backend.ps1`, `.\scripts\start-frontend.ps1` and
`.\scripts\fyp-mysql.ps1`. The MySQL helper creates a separate disposable
environment; it is not needed for your existing Laragon database.

Obsolete standalone migration launchers and generated build output are excluded.
Backend/Flutter regression suites and relevant dated test evidence are retained.
Shared schema helpers remain because setup and validation use them. Normal startup never creates or migrates a database. For an existing
database, retain its key and verify a backup before a reviewed schema upgrade;
do not rerun setup or seed data as a repair.

Flutter regenerates dependencies/build output when needed. From `frontend/`, run
`flutter pub get`, `flutter test --no-pub` and `flutter analyze --no-pub`. Backend
regressions use synthetic fixtures; live SQL integrations are opt-in. Run tests
in an isolated test process/environment and never enable database integration
flags against original student or attendance data.

## App and integration

Attendance requires a valid class PIN, class/group checks, device/network proof,
facial matching and liveness. Final authorization runs again before attendance
is saved. Classroom Wi-Fi applies when assigned to the session; BLE remains
experimental. Use one backend worker because in-progress challenges are held
in memory. This academic app is not certified presentation-attack detection.

- [API and camera integration](docs/API_INTEGRATION.md); live schema: `/openapi.json`.
- [Module ownership](docs/MODULE_OWNERSHIP.md).
- [Admin panel and PINs](docs/ADMIN_TESTING_PANEL.md).
- [Enrollment policy](docs/FYP_ACCOUNT_BOUND_ENROLLMENT.md).
- [Device management](docs/SELF_SERVICE_DEVICE_MANAGEMENT.md) and
  [biometric authorization contract](docs/TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md).
