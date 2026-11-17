# Partner LOCAL mode

After one-time setup, use PowerShell in your own Windows clone on any named
branch (including Chew-Zhexuan). Full mode retains its original SH/path checks.

```powershell
.\fyp-start.ps1 -Mode Local
.\fyp-install.ps1 -Mode Local
.\fyp-stop.ps1 -Mode Local
```

Omitting Mode still selects existing **Full** behavior. Local needs no Cloudflare
credentials, service or gateway and never accesses api.bioattsys.xyz. No server
discovery is added: only this laptop's current Wi-Fi IPv4 is detected.

## Prerequisites

Use Python 3.12/backend requirements, MySQL 8.4.x (for example Laragon) or MariaDB,
compatible Flutter/Dart and Android SDK/ADB. Set your own SDK paths in ignored
android/local.properties. Start the database separately. Apache is optional and
is only needed if you use a PHP database administration page served through it.

```powershell
py -3.12 -m venv backend\venv
.\backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\venv\Scripts\python.exe .\backend\setup.py --model-only
Push-Location frontend
flutter pub get
Pop-Location
```

Optional BLE needs compatible Windows hardware, Bluetooth on, .NET 9, and your
existing compatible GATT BleProbe utility with its exact SDK cache dependencies.
No broadcaster is downloaded or substituted. No biometric/signing secrets from
the author's laptop are needed or safe to copy.

## Own database and private settings

Use your successfully restored application schema, or create a dedicated
development schema/account using your local DB administration tool. Example
names: biometric_attendance/fyp_local_app (not supplied credentials).
Grant only your schema: runtime SELECT/INSERT/UPDATE and metadata visibility;
initial empty-table creation also needs temporary CREATE/INDEX/REFERENCES. Revoke
DDL after setup. Never grant global administration or original-schema access.

Local rejects root, empty passwords, remote DB hosts, system schemas and the
protected attendance_proposal_xampp name. It does not fall back to backend/.env
DB credentials. Use a dedicated own schema if an old schema has that name.
Compatible own existing schemas can be used without initialization. Existing
face data requires its original matching encryption key, never a replacement.

### Configure an existing restored Laragon database

In your Laragon database tool, confirm the actual server before changing accounts:

```sql
SELECT VERSION(), @@port, @@datadir;
```

Use MySQL 8.4.x and the port shown here (the configure command defaults to 3306).
The restored schema must contain all application tables and its original data.
Do not run init-empty or seed/setup commands on that schema.

Create a dedicated application account for that schema through your database
administration tool. MySQL 8.4 accounts should use caching_sha2_password and a
unique password of at least 12 characters. Grant SELECT, INSERT and UPDATE only
on the application schema; use your separate administrator for migration/DDL.
Do not import the XAMPP mysql system schema. Error 1524 generally indicates an
account still requesting the disabled mysql_native_password plugin; address the
account authentication through a working administrator session rather than
disabling authentication or changing application data.

Create the Local connection profile in an interactive terminal:

```powershell
.\backend\venv\Scripts\python.exe -B .\backend\local_fyp.py configure
```

Enter the actual port, restored schema, dedicated username and password. Secret
input is hidden. At the biometric-key prompt, Enter reuses BIOMETRIC_KEY from
this checkout's backend/.env; use this only when it is the key corresponding to
the restored templates. Alternatively enter that existing key privately. No
new key is generated. The command creates only the private settings.json with
restricted Windows permissions; it performs no SQL and never overwrites an
existing profile or identity. ACCOUNT_BOUND_FYP starts disabled; review it in
the private profile before first pinning if your own deployment requires it.

Validate the configured server and every application table definition:

```powershell
.\backend\venv\Scripts\python.exe -B .\backend\local_fyp.py check
```

Review the server/schema, then type PIN once to save its verified identity. This
command does not change the database. Later version, port, account, paths, key
or policy changes are rejected rather than silently adopting a different target.
If the profile already exists, review that private file instead of rerunning
configure or deleting an identity pin.

For manual configuration or a new empty database, prepare per-clone private
settings outside Git, separate from Full's files (skip this if configure ran):

```powershell
$python = Join-Path (Get-Location) 'backend\venv\Scripts\python.exe'
$private = & $python -c "import sys; sys.path.insert(0,'backend'); from local_fyp import private; print(private())"
if (-not (Test-Path -LiteralPath $private)) {
    New-Item -ItemType Directory -Path $private | Out-Null
    $owner = "$env:USERDOMAIN\$env:USERNAME"
    & icacls $private /inheritance:r /grant:r "$($owner):(OI)(CI)F" 'SYSTEM:(OI)(CI)F'
}
if (-not (Test-Path -LiteralPath "$private\settings.json")) {
    Copy-Item .\backend\partner-local.example.json "$private\settings.json"
}
notepad "$private\settings.json"
```

Fill your loopback host/port/schema, dedicated credentials and own biometric key.
Choose fyp_account_bound_enrollment before first pinning: false is conservative;
true opts into the existing ACCOUNT_BOUND_FYP demonstration policy for genuine
fresh first enrollment by school-provisioned accounts. It never trusts unknown
templates or claims institutional verification. demo_mode and Network + BLE Test
Mode are forced false. No Full-mode demo approval secret is copied.

For a NEW EMPTY schema only, save a fresh key privately without displaying it:

```powershell
& $python -c "import sys,json; sys.path.insert(0,'backend'); from local_fyp import private; from cryptography.fernet import Fernet; p=private()/'settings.json'; v=json.loads(p.read_text()); assert not v['biometric_key'] and not (private()/'identity.json').exists(); v['biometric_key']=Fernet.generate_key().decode(); p.write_text(json.dumps(v,indent=2)); print('New Local key saved privately; no key displayed')"
```

ble_executable can be empty (optional BLE unavailable) or an absolute path to
your existing compatible BleProbe.exe. UUID/GATT/continuous-mode markers are
checked; dependencies are prepared under ignored runtime/local/ble-beacon.

## Optional EMPTY-schema initialization

On your already-created, completely empty schema, this explicit offline command
wraps existing application_tables definitions/Table.create operations:

```powershell
.\backend\venv\Scripts\python.exe .\backend\local_fyp.py init-empty
```

It validates the configured supported database identity, requires EMPTY confirmation and
refuses ANY existing table. It creates no database, modifies no existing table,
and seeds no account, face, device or attendance records. Startup/install never
call it. A partial failure requires schema-owner review, not automatic reset.
Do not run old setup/migration scripts against the author's .env by mistake.

Provision your own student/group/class and school-roster records through reviewed
offline provisioning. Existing mechanisms use security.hash_password and
SchoolProvisionedAccount. No default demo password or new account-management
system is introduced. Empty schemas cannot log in until your own accounts exist.
Do not insert fake encodings/revisions: enroll genuinely through the app. No
author's records are needed. Existing own schemas must pass read-only validation.

## Start and connect

Start your Laragon MySQL or MariaDB normally, then run Local start. A stopped DB gives an
actionable error; it is not started/reset automatically. The launcher checks
the supported vendor/version, configured schema/port/account/datadir/key and all application tables.
Type PIN once to bind the verified own database. Later identity/policy/key drift
blocks startup; do not delete the pin to conceal an unexplained change.
First start can initialize your own Local panel password interactively using
the existing hashing implementation, separate from Full credentials.

Backend: local_fyp.py serve-backend --lan, port 8000. Panel: local_fyp.py
serve-panel, loopback-only port 8003. Dashboard says LOCAL and Cloudflare/gateway
NOT USED. Missing/failed BLE is optional NOT READY with a log; it neither
authorizes attendance nor bypasses any check. Fresh physical scans are still
required before claiming beacon detection success.

Phone and laptop must share approved private Wi-Fi. USB debugging is for ADB
installation, not reverse forwarding. Any needed Private-profile firewall rule
for port 8000 needs separate approval; these scripts do not change it. Unfamiliar
school Wi-Fi is NOT automatically authorized: configure real approved CIDR and
classroom SSID/BSSID policies separately in your own DB. HTTP is for an approved
private development network only, never untrusted public Wi-Fi. Mobile data
cannot reach this LAN-only backend by design.

## Install, shutdown and switching

Install defaults only to the sole connected Xiaomi; ambiguous devices require
selection. Optional: `.\fyp-install.ps1 -Mode Local -Serial DEVICE_SERIAL`.
Both PUBLIC_API_BASE_URL and CLASSROOM_API_BASE_URL use the SAME current LAN URL,
with explicit FYP_LOCAL_MODE=true. Flutter permits only matching canonical
RFC1918 HTTP origins on port 8000 under that flag. Full public URLs still require
HTTPS. Local installation warns and requires LOCAL confirmation: retained
sessions/device bindings may not belong to this database. No records/keys are
copied or reset. Prefer distinct synthetic student IDs for partner testing.
adb install -r/package/hash checks remain. Signing/version errors never trigger
uninstall, data clear or key regeneration.

State/logs are separated: Local runtime/local, Full existing runtime. Both use a
common lifecycle lock because ports overlap. Local stop touches only verified
Local-owned processes, not Full, shared/reused publishers, the database or Cloudflared.
Modes cannot own the same ports simultaneously. An existing original backend
on 8000 or panel on 8003 must first be stopped using its original terminal or
verified owning launcher. Local never adopts it or terminates an unknown PID.
Local also refuses an active
gateway on 8004 so an existing Full proxy cannot expose Local data; it reports
the conflict and never stops that proxy automatically.

To switch back intentionally, stop Local-owned processes, use commands without
-Mode Local, then rebuild/install Full. Confirm student/database first. Reused
processes left behind need separately reviewed cleanup. Full's settings,
Cloudflare, gateway and BLE UUID stay unchanged. PIN, device signatures,
replay/freshness, ASGI-source CIDR, Wi-Fi, face, liveness and duplicate protection
remain authoritative; BLE remains shadow-only.

Never commit private settings/.env, Cloudflare credentials, DB dumps, passwords,
biometric records, signing keys or runtime artifacts. Keep database backups
outside the repository.
