# Original FYP setup (backend 8000, database 3306, panel 8003)

## Existing environment

The original profile uses schema `attendance_proposal_xampp` on
`127.0.0.1:3306`. Backend 8000 and panel 8003 use the same pinned database.
Use the existing admin credentials when already initialized. For a fresh
teammate setup, use [the disposable MySQL guide](MYSQL_TESTING.md).

```powershell
.\start-fyp.ps1 check
.\start-fyp.ps1
```

Run these commands from the repository root. Application readiness checks the
FYP schema and does not verify MariaDB system-table integrity. Keep recovery
evidence and database backups private.

## Historical pre-recovery blocker (resolved for application access)

Verified on 9 November 2026: the configured server answers `SELECT VERSION(),
@@port,DATABASE()` as MariaDB 10.4.27, port 3306, schema
`attendance_proposal_xampp`. Metadata lists 26 application tables. However,
bounded reads of both `students` and `attendance` time out. Several existing
connections are stuck in `Opening tables` or `Statistics`. This identifies a
database readiness problem; it does **not** establish its underlying cause.

No original table, row, account, setting or encryption key was changed. No new
database was created. No backup is claimed from this unhealthy running server,
and no schema updates were attempted. Existing older backups are not substitutes
for a fresh verified backup before this change. Database recovery, restarting
MariaDB, terminating its sessions and replacing files are outside this change.

During that earlier outage, application identity and records could not be verified.
Never create replacement accounts or promote a legacy template to work around
a database readiness problem.

## What changed

* The ordinary `main:app` now includes the existing authenticated classroom Wi-Fi
  and standalone experimental BLE routers. Previously only the disposable
  launcher included them, explaining the two 404 responses.
* Classroom attendance requirements still apply per session. A session without
  a classroom requirement does not acquire one merely by enabling the router.
  BLE has no attendance authorization adapter and remains experimental.
* `original_fyp.py` uses the existing `backend/.env` and encryption key, but rejects
  any endpoint other than 127.0.0.1:3306 / attendance_proposal_xampp. It pins the
  actual version, directories, account and encryption-key hash outside Git and
  validates application-table reads, required tables/columns and existing
  read-only type/key/CHECK/generated-column guards before
  starting a service. It does not initialize or migrate a database.
* The existing panel has an explicit original-database mode. Its CIDR forms use
  the same policy validator and audit writer; they can manage original policies
  without the disposable `SIMULATION ONLY` naming restriction. Existing disposable
  launchers retain that restriction. No policies are enabled automatically.
* Local credentials and process state live in `%USERPROFILE%\FYP-Original-Local`,
  protected for the current user and SYSTEM. The existing database credentials
  and biometric encryption key remain in their original configuration; no new
  encryption key is generated. Do not delete or recreate that key.

## Commands

Run from the repository using PowerShell:

```powershell
.\start-fyp.ps1 check
```

The health guard prints `BLOCKED` if application tables stall again. Do not
repeatedly retry a stalled database. Start the existing local services with:

```powershell
.\start-fyp.ps1
```

Only an operator who has no local admin credentials should run `start-fyp.ps1
admin-init` once interactively.
Passwords and hashes must not be copied into Git or chat.

The launcher starts only backend 8000 and panel 8003, both on **127.0.0.1**. It
does not start or stop MariaDB. If those ports belong to earlier launchers, stop
those servers in their own terminals with Ctrl+C first. An older `main:app`
process does not implement the new pinned identity route and is not silently
adopted. Unrelated listeners are never terminated. New children are terminated
if this invocation fails. Logs contain no request bodies, tokens or PINs.

URLs after readiness succeeds:

* Backend: http://127.0.0.1:8000 for laptop clients. The explicit `--lan` option
  is available for approved private-LAN testing.
* Panel: http://127.0.0.1:8003/login
* Authenticated classroom lists: `/api/v1/classroom-wifi/classrooms` and
  `/api/v1/classroom-ble/classrooms`.

## Schema installation and future migration safety

The current application inventory contains 43 tables. The original schema had
26; the 17 missing tables have now been added: five enrollment/provenance tables,
eight classroom Wi-Fi tables and four experimental BLE tables. No existing table
was altered. `application_schema.py` exposes
the canonical inventory, excluding test fixture models. Existing isolated-only
migration guards have **not** been weakened to accept production.

Before an original-schema migration:

1. Restore reliable bounded reads of the original tables without guessing the
   cause or automatically repairing MariaDB.
2. Quiesce application writers, retain the original configuration/encryption
   key privately, and create a fresh consistent logical backup. A cold full
   backup requires a separately approved graceful database shutdown. Never copy
   live data files and call that a consistent backup.
3. Verify backup integrity and restoration evidence, table counts, row hashes,
   attendance, device registrations and encrypted-template hashes.
4. Compare existing columns and constraints with the models. Apply a reviewed
   create-missing-tables-only migration with step verification and resumability;
   do not call `setup.py`, recreate existing tables, seed accounts or overwrite
   provenance. `original_schema_upgrade.py` gates the create-missing-only operation
   on a verified original logical backup and unchanged original row hashes.
5. Compare original records again and validate the pinned startup checks.

Schema availability alone never trusts a template. Existing legacy templates
need legitimate provenance; an empty enrollment-revision table cannot authorize
Slot 2/replacement. `ACCOUNT_BOUND_FYP` remains an explicit lower-assurance opt-in,
requires a school-provisioning record and a genuine first enrollment, and is not
institution-verified identity. No flag or UI can elevate an existing unknown face.

## USB Android build and install (after backend readiness)

```powershell
# Uses installed SDK paths from frontend/android/local.properties.
.\install-fyp-android.ps1 -BuildOnly
$deviceId = Read-Host 'ADB device serial'
.\install-fyp-android.ps1 -Serial $deviceId
```

The second command verifies the selected device and original backend, configures
`adb reverse tcp:8000 tcp:8000`, builds with
`--dart-define=API_BASE_URL=http://127.0.0.1:8000`, then uses `adb install -r`.
It never uninstalls, clears data or rotates keys. If signatures conflict, stop;
do not uninstall to force installation. Confirm connectivity with `adb devices`.

**USB reverse cannot prove an authorized campus network.** The ASGI source is
loopback, which attendance deliberately rejects. Login and other permitted
transport tests can use USB, but attendance PASS requires a real reachable LAN
backend and an explicitly configured matching CIDR, plus any classroom policy.
Do not authorize loopback or forwarded headers to force a PASS. LAN exposure and
firewall changes are separate from this loopback launcher.
Use `-LanIp <laptop IPv4>` on the installer for an approved direct-LAN test.

## End-to-end checks once the database is ready

Use the existing student and classroom records. Create a session in the panel;
the PIN appears once after commit. Login in Flutter, enter that PIN, and verify
early device/network preflight before camera capture. Final attendance still
requires fresh single-use device proof, genuine face/liveness success, final
ASGI-source CIDR validation and any session Wi-Fi proof. Repeat submission must
be rejected. Slot 2/replacement must use valid template provenance and candidate
Keystore signatures; never use `COMPLETED_UNTRUSTED` as a grant.

The original Xiaomi Slot 2 tablet has recorded attendance in a separate physical
test. This result used the explicitly enabled [LOCAL FYP DEMO workflow](SUPERVISED_ENROLLMENT_VERIFICATION.md#local-fyp-demo-on-the-original-server),
with institutional assurance remaining `UNVERIFIED`. Automated fixtures
cannot establish physical biometric performance on another installation.

## Teammate handoff

Git transfers code, not accounts, face templates, policies or schema updates.
Keep each laptop's `.env`, encryption key and panel password private. With the
same original host/port/schema, this launcher pins that laptop's actual database
identity on its first healthy run. Copying another laptop's identity file is
incorrect. MySQL compatibility work is preserved, but this task did not create
or test another MySQL environment. A different schema/port needs an explicitly
reviewed target configuration; the original launcher will not guess a fallback.

Keep all current FYP source and tests. Exclude `.env`, private profiles, logs,
database dumps/data directories, APKs and generated build files from Git.

## Evidence and preservation

Pre-change source backup:
`C:\FYP\Source-Backups\original-setup-20261109-030809`
(500 Git-visible tracked/untracked files individually SHA-256 verified, plus
status, binary diff and restoration instructions). The earlier full-tree backup
at `C:\FYP\Source-Backups\mysql-support-20261109-005211` additionally preserves
ignored local state from before the MySQL work. Neither is a fresh database backup.

Local regression logs (ignored): `.work/original-setup-tests.log`,
`.work/original-backend-regressions.log`, `.work/original-flutter-test.log`,
`.work/original-flutter-analyze.log`, `.work/original-api-timings.json`.

Measured existing-process timings: `/` 31 ms, `/config` 16 ms, both classroom
routes 404 before restart. Database identity 90 ms; original student/attendance
reads exceeded a four-second socket deadline. No authenticated login timing is
claimed. Unknown account and incorrect password messages intentionally remain
indistinguishable; PIN, enrollment, device and network failures keep their
existing separate reason handling.

## Changed files for this original-setup task

* `backend/application_factory.py`, `backend/app.py`: shared app composition.
* `backend/admin_testing.py`: explicit original-policy mode; existing disposable
  defaults, authentication, CSRF, session and localhost protections preserved.
* `backend/modules/classroom_wifi/router.py`,
  `backend/modules/classroom_wifi/attendance.py`: updated composition descriptions/tags.
* `backend/application_schema.py`: canonical application-table inventory.
* `backend/original_fyp.py`, `start-fyp.ps1`: pinned original readiness/startup.
* `install-fyp-android.ps1`: SDK-based USB build/install-r workflow.
* `backend/tests/test_original_fyp.py`: original-mode offline regressions.
* `docs/openapi.json`: regenerated from the shared app, no database connection.
* `docs/ORIGINAL_FYP_SETUP.md`, `README.md`: instructions and blocker report.

These are incremental changes; earlier uncommitted FYP/MySQL work remains intact.

## Historical validation before original migration

* Backend full discovery: **413 run, 399 passed, 14 skipped** (193.701 seconds).
  The initial stale OpenAPI failure was fixed by regenerating the specification.
* Original-setup focused tests: **26 passed**, including inherited admin security
  regressions, original-mode forms, session creation and authenticated route registration.
* Flutter: **255 passed, 1 skipped**. Analysis: **no issues**.
* USB-configured Android debug APK: **build passed**, not installed. Existing
  Kotlin plugin deprecation notice is non-blocking; Gradle files were not changed.
* PowerShell parser checks, Python compilation and `git diff --check`: passed.
* At this earlier stage, original database migration and live testing were
  pending. See **Existing environment** and **End-to-end checks** above for the
  later state.

No new database, environment, public endpoint, student, policy or attendance
record was created during this original-setup task. No Git commit/push occurred.
