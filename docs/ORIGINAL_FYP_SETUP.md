# Original FYP setup (backend 8000, database 3306, panel 8003)

## Existing environment

The original profile uses schema `attendance_proposal_xampp` on
`127.0.0.1:3306`. Backend 8000 and panel 8003 use the same pinned database.
Use the existing admin credentials when already initialized. For a fresh
teammate setup, use [the disposable MySQL guide](MYSQL_TESTING.md).

```powershell
.\scripts\start-fyp.ps1 check
.\scripts\start-fyp.ps1
```

Run these commands from the repository root. Application readiness checks the
FYP schema and does not verify MariaDB system-table integrity. Keep recovery
evidence and database backups private.

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
.\scripts\start-fyp.ps1 check
```

The health guard prints `BLOCKED` if application tables stall again. Do not
repeatedly retry a stalled database. Start the existing local services with:

```powershell
.\scripts\start-fyp.ps1
```

Only an operator who has no local admin credentials should run `scripts\start-fyp.ps1
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
.\scripts\install-fyp-android.ps1 -BuildOnly
$deviceId = Read-Host 'ADB device serial'
.\scripts\install-fyp-android.ps1 -Serial $deviceId
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

Keep application source and required schema helpers. Exclude `.env`, private profiles, logs,
database dumps/data directories, APKs and generated build files from Git.
