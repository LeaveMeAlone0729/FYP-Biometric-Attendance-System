# MySQL-first disposable FYP setup

Preferred new teammate workflow. Existing .env, port 3306, ordinary backend 8000
and MariaDB 3322/8002/8003 are unchanged. Tested/allowed release: **MySQL Community
Server 8.4.3, Windows x64**. Other versions require validation before approval.

Default endpoints: database **127.0.0.1:3332**, student API
**http://127.0.0.1:8012**, admin **http://127.0.0.1:8013/login**.
All listeners are loopback-only. No firewall/service installation or tunnel is
needed. Port 3306 is blocked before a connection is made.

## Teammate setup without editing Python

Run from the repository root in PowerShell 7. Use Python 3.12 and a tested
MySQL Community 8.4.3 installation. On a new checkout only, if no venv exists:

```powershell
py -3.12 -m venv backend\venv
.\backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Existing Windows dlib/face-recognition dependencies may need the normal CMake/C++
toolchain. This work adds no Python dependency or MariaDB installation requirement.
Keep an existing working venv. Do not run setup.py against an existing database.
Install the liveness model separately. This command makes no database connection:

```powershell
.\backend\venv\Scripts\python.exe .\backend\setup.py --model-only
```

```powershell
$mysqlHome = Read-Host 'Full MySQL 8.4.3 installation folder containing bin, lib and share'
.\fyp-mysql.ps1 setup --mysql-home $mysqlHome
.\fyp-mysql.ps1 admin-init
.\fyp-mysql.ps1 start
.\fyp-mysql.ps1 status
```

Admin-init prompts for a username and unique 12-128-character password twice.
Use an interactive terminal; never put a password in argv or pipe it. There is
no shared/default admin password. A second physical laptop has not been tested;
the installed binary here and setup using alternative ports have been tested.
On an existing profile, use `start` without repeating setup or admin-init.

If default ports are occupied, choose unused ports on first setup:

```powershell
.\fyp-mysql.ps1 setup --mysql-home $mysqlHome --db-port 3342 --backend-port 8032 --panel-port 8033
```

Later commands use the saved profile, not assumed ports. Reserved existing ports
3306/3322/8000/8002/8003 and duplicate ports are rejected. HTTP ports cannot be in
the database range. Busy listeners are never killed or adopted as a new server.

## Daily lifecycle

```powershell
.\fyp-mysql.ps1 start
.\fyp-mysql.ps1 status
.\fyp-mysql.ps1 stop
```

Startup waits for database identity/readiness, validates schema, then starts the
backend and verifies its identity before starting the panel. Missing admin
credentials are explicitly reported: run admin-init and start again. Startup
does not migrate or reseed. Shutdown is graceful and limited to exact saved
executable/arguments/creation-time identities. Stale PIDs cannot target unrelated
processes. Failed starts clean up owned services and report failures.

Setup prints a private environment path under `%USERPROFILE%\FYP-MySQL-Testing`.
The MySQL-only selector is current.json there. Explicit environments are supported:

```powershell
.\fyp-mysql.ps1 start --environment '<PRIVATE_ENVIRONMENT_PATH>'
.\fyp-mysql.ps1 stop --environment '<PRIVATE_ENVIRONMENT_PATH>'
```

To create an additional environment, explicitly use setup --new-environment with
unused ports. Add --no-select to leave the current MySQL selector unchanged.
Existing environments are never deleted/overwritten. No reset command is exposed.

MariaDB keeps its existing fyp-test.ps1 and start-admin-testing.ps1 commands.
The current port 8000 source also registers classroom Wi-Fi and BLE routes.
Route registration does not migrate the database or add requirements to existing sessions.

## Isolation, schema and credentials

Only bin/lib/share program resources are copied. Existing data directories,
my.ini/my.cnf and private installation keys are not copied. Initialization uses
--no-defaults and a fresh datadir; startup uses the exact private server.ini.
MySQL X protocol is disabled, so no extra listener appears on its default port.
The private directory ACL permits only the current user and SYSTEM.

Each DB connection validates endpoint, schema, actor, vendor/exact version,
server UUID, basedir and datadir. Native config changes are rejected before
launch. There is no root/.env fallback or arbitrary database selection.
Startup validates the full 43-table schema and never creates missing tables.
Migration/setup is an explicit offline step, not a web endpoint.

MySQL uses ENFORCED CHECK metadata instead of MariaDB's check_constraint_checks;
probes accept MySQL error 3819. Generated expressions, PKs, unique guards, FKs,
CHECK definitions and InnoDB engines are validated. Read-only MySQL policy and
provenance rows use shared transaction locks instead of granting students write
privileges. MariaDB retains its previous lock behavior.

Accounts are separate:

- Runtime: table/column-scoped application writes; no DDL, DELETE, school-roster
  editing or enrollment-revision UPDATE/DELETE.
- Panel operator: academic/session/policy operations and audits, no student,
  face, device or approval editing; no DDL, DELETE or administrative rights.
  Schema-scoped LOCK TABLES supports existing serialized session creation without
  granting UPDATE on school groups.
- Offline provisioner: private root of this new instance only, used for setup,
  validation and lifecycle. Web requests use the runtime/operator actors.

Private files include profile, independent Fernet key, random DB credentials,
panel password hash and STUDENT_CREDENTIALS.txt. The private initializer log
contains the initial temporary expired root password; setup replaces it promptly
and never prints it. Keep every private file and datadir outside Git/chat.

## Synthetic student and security boundaries

Setup creates **MYSQLTEST01**, its school-provisioning attestation, a test group
and existing class **FYPATT01**. Its unique assigned password is in the printed
private STUDENT_CREDENTIALS.txt. No face/device/attendance is pre-filled. No
DEMO001 records, original templates, device keys and sessions stay in the
original environment. The disposable setup does not connect to port 3306.

First face enrollment is ACCOUNT_BOUND_FYP, not institution-verified identity.
Legacy templates are never upgraded automatically. Slot 2/replacement still
require genuine fresh face/liveness, bound single-use server authorization and
candidate Keystore signatures. The panel cannot issue approvals. Algorithms,
thresholds, key aliases and the final attendance writer are unchanged.

The same panel provides session creation, one-time PIN display and regeneration, closure, CIDRs, classroom
Wi-Fi and experimental BLE policies. Wi-Fi attendance requirements apply only
when explicitly assigned to a session. BLE remains standalone, not mandatory;
BLE_EVIDENCE_FUTURE is not fixed or bypassed here. Student/IP/PIN/biometric and
duplicate controls stay fail-closed. No real campus CIDR is seeded.

An emulator can use API_BASE_URL=http://10.0.2.2:8012. An explicitly approved test
installation can use USB reverse for login/device/face testing, but localhost
is NOT attendance network proof. Physical attendance requires separately reviewed
private-LAN transport; new ports were not exposed to LAN/public networks. No APK
or original Samsung installation/key was modified.

## Tests and troubleshooting

```powershell
.\backend\venv\Scripts\python.exe -B -m unittest discover -s backend\tests -p test_mysql_profiles.py -v
.\backend\venv\Scripts\python.exe -B backend\tests\run_mysql_acceptance.py --output .work\mysql-new-run
.\backend\venv\Scripts\python.exe -B backend\tests\run_mysql_acceptance.py --suite admin --output .work\mysql-admin-new-run
```

Output directories must be new. Acceptance uses fresh fypmysqlcase_<random>
schemas, synthetic inference and disposable signing keys; test schemas are
cleaned afterward. This does not prove physical camera/Keystore/campus behavior.
Account-bound tests use the actual local approval provider, not a mock grant.

Unsupported version: supply tested 8.4.3 Community; do not fake version checks.
Busy/protected port: select unused ports, never terminate the original server.
Native config/identity/schema mismatch: stop and investigate, never remove guards
or reset data. Missing admin: initialize interactively. Failed setup retains
private files and reports incomplete cleanup rather than touching foreign PIDs.

Do not commit .env, private profiles/keys/credentials/datadirs, logs, .work or
generated builds. Keep local recovery backups outside the repository.

Make MySQL the shared default only after both teammates validate their supported
installations and explicitly approve a configuration switch. Current defaults
and the working MariaDB environment have not been changed.
