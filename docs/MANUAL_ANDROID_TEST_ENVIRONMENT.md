# Private manual Android test environment

For current start/stop, all-device private-LAN transport and terminal simulation
policy commands, use [FYP_NETWORK_TEST_WORKFLOW.md](FYP_NETWORK_TEST_WORKFLOW.md).
The original resource inventory below remains useful; no per-device transport
allowlist is required by the current workflow.

Prepared 6 November 2026, branch SH. Synthetic resources only. No production
database connection, original-account/template/device mutation, Android operation
or public exposure was performed during preparation.

## Running environment

| Component | Address / value |
|---|---|
| MariaDB 10.4.27 | 127.0.0.1:3322 |
| Test schema | fypdevicemgmt_restore_a199e7f82903 |
| Full FYP backend | http://127.0.0.1:8002 |
| Dedicated phpMyAdmin | http://127.0.0.1:8082/ |
| Application DB user | fyp_manual_runtime@127.0.0.1 |
| Read-only phpMyAdmin user | fyp_manual_viewer@127.0.0.1 |
| Synthetic student ID | FYPTEST001 |
| School provisioning | One synthetic offline provisioning record |
| Face status | not_registered; face_encoding=NULL; consent_at=NULL |
| Device bindings / enrollment revisions | Zero / zero |
| Runtime policy | ACCOUNT_BOUND_FYP enabled only in the private profile; DEMO_MODE=false |

The schema name uses the existing migration's restricted disposable namespace.
It was initialized empty from current application models, not restored from real
student rows. No production password hash, template, auth session or Samsung
registration was copied. Twenty-six current core tables were initialized and the
five-table device-management migration applied; its second run was a no-op.

Private instance directory:
`C:\FYP\DB-DeviceManagement\manual-android-20261106-033334-1f0285`

Its ACL allows the current Windows account and SYSTEM. The private directory
contains the backend profile, dedicated operator secrets, data, fresh per-instance
encryption key, cookie configuration and service logs. None belongs in Git.
`USER_CREDENTIALS.txt` contains the student password and read-only phpMyAdmin
password. Database runtime/admin secrets remain in private operator/profile files.
Do not share those files or copy their contents into the repository.

The assigned temporary student password uses the application's existing
`security.hash_password` / `verify_password` mechanism: PBKDF2-SHA256 with 600,000
iterations and a random salt. Only the hash is stored in students. It remains
valid until an operator changes it or the disposable environment is retired;
"temporary" does not imply an automatic expiry timer.

## phpMyAdmin instructions

1. Open http://127.0.0.1:8082/ on this Windows computer. This is a dedicated local
   copy, not a change to the original XAMPP/Laragon phpMyAdmin configuration.
2. Sign in with **fyp_manual_viewer**, using its phpMyAdmin password from the private
   USER_CREDENTIALS.txt. Do not use FYPTEST001/student password here: phpMyAdmin
   authenticates a database user, whereas Flutter authenticates a student.
3. Select **fypdevicemgmt_restore_a199e7f82903 → students → Browse**.
4. Confirm student_id FYPTEST001, account_status active, biometric_status
   not_registered, face_encoding NULL and consent_at NULL.

The UI is pinned to 127.0.0.1:3322 with arbitrary-server selection disabled, and
the viewer has SELECT on synthetic students only. It cannot edit a face/student,
read authentication tokens or system privilege tables, or perform setup work.
The original phpMyAdmin installation and database server selection are unchanged.
No root, runtime or administrator password is required for viewing this student.

## Manual Flutter first enrollment

Do not change the original Samsung installation or point it at this environment.
Use the real test tablet (7732690b), an emulator, or a separate test installation.
First configure the test build explicitly; the existing default/LAN URL might
still point at the original backend and must not be used for these tests.

For the USB-connected real tablet, from the repository root:

```powershell
adb -s 7732690b reverse tcp:8002 tcp:8002
Set-Location frontend
flutter build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8002
adb -s 7732690b install -r build\app\outputs\flutter-apk\app-debug.apk
```

These commands are provided for manual execution; no APK was installed by this
setup. Install only on the specified test tablet. `install -r` retains app data
and existing keys when signing/application ID match. If installation fails due
to signing/version incompatibility, stop; do not uninstall or clear data as a
fallback. A separate test application ID/profile needs its own preparation.

For an Android emulator, build with
`--dart-define=API_BASE_URL=http://10.0.2.2:8002` instead. It reaches this computer's
loopback backend without a public tunnel. Each emulator must use its own retained
Android Keystore key; do not clone app data or keys between emulator instances.

Open the test app, log in as **FYPTEST001** using the assigned student password,
then use the partner's existing Profile → face enrollment flow with consent and
a real live capture. No synthetic inference provider, fake face vector, production
trust row or mock activation grant exists in this environment. The genuine first
capture should create ACCOUNT_BOUND_FYP provenance, not institutional identity
verification. Do not re-enroll an existing legacy face or use DEMO001 here.

No device is registered automatically. Decide which disposable installation is
Slot 1 before starting device registration. If this tablet registers first, it
will be Slot 1; it cannot simultaneously be Slot 2 under the same retained key.
Use distinct test installations/keys for Slot 2 and each replacement. The native
key alias is scoped by student ID, so the new student's alias does not replace a
retained DEMO001 alias. Do not rotate/delete any existing alias.

No authorised network policy was seeded. Device/face enrollment does not require
attendance CIDR authorization. Attendance remains fail closed with no policy;
USB reverse/loopback is not campus-network proof. A later real LAN/campus test
requires separately reviewed source-IP/range and binding configuration.

## Start and stop

From the repository root, gracefully stop only this disposable environment:

```powershell
.\backend\venv\Scripts\python.exe -B backend\prepare_manual_android_test.py --stop `
  --environment C:\FYP\DB-DeviceManagement\manual-android-20261106-033334-1f0285
```

Restart with the same persistent database, credentials and encryption key:

```powershell
.\backend\venv\Scripts\python.exe -B backend\prepare_manual_android_test.py --start `
  --environment C:\FYP\DB-DeviceManagement\manual-android-20261106-033334-1f0285
```

The controller verifies disposable process command lines, requests backend exit
through a private stop signal, stops its private PHP process and sends normal
SHUTDOWN only to its verified 3322/data-directory identity. Startup waits for
MariaDB readiness before the backend and HTTP readiness before returning. No
Windows service, global share, production firewall or original backend setting
is changed. Do not run bare preparation again to restart an enrolled environment;
use --start to preserve its data/key. A busy target port is rejected.

## Isolation and evidence

The standalone backend launcher accepts only an explicit private profile with
127.0.0.1:3322, a dedicated non-root user/schema and the expected disposable data
directory. SQLAlchemy validates the actual account/schema/version/datadir and
pins driver connection arguments; its pure-Python driver uses an audit guard
that rejects port 3306 for IPv4, IPv6 and localhost paths before networking.
All Settings inputs are overridden privately before existing config imports, and
child processes do not inherit production database/key environment defaults.
The serving process's /manual-test/isolation probe verifies the denial event
without sending a packet to production. There is no production fallback.

This is application/process isolation, not a system-wide firewall or a sandbox
against arbitrary malicious native code. No administrator-level OS policy was
changed. Do not publish this full backend/phpMyAdmin or start a public tunnel.

Completed checks:

- Six offline profile/guard tests passed, including rejection of port 3306/root,
  original schema/datadir, altered assurance/thresholds and IPv4/IPv6 denial.
- Full backend regression passed: 246 passed, 10 opt-in/live tests skipped,
  zero failures/errors (256 discovered); external database connections were disabled
  in that separate regression process.
- Eleven expected permission denials passed for runtime and viewer accounts;
  no DDL/admin/system/cross-database access or unauthorized student/provenance edits.
- Real login, wrong-password rejection, Profile, device listing, logout and token
  revocation passed on the new backend. Only synthetic session records were created.
- Dedicated phpMyAdmin cookie login and browsing the actual student row passed.
- One graceful stop/start cycle retained the student/hash/new encryption profile;
  first face, revision, device and attendance counts remained zero.
- All 31 application and 30 MariaDB system tables passed integrity checks; logs
  showed no corruption/crash markers. No repair operation was used.

Sanitized evidence is in the private REPORT.json. Original/student data and keys
were not inspected through any production connection during preparation. The
earlier failed fresh-instance attempt stopped before student creation after a
generic validator misclassified MariaDB Boolean storage; the successful setup
validates Boolean columns as TINYINT(1) without altering application models.
