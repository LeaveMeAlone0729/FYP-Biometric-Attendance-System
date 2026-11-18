# MariaDB production cutover readiness — 4 November 2026

**Conditional GO to request a separately approved maintenance window. NO-GO to execute production cutover now.** The source database has no new verified cutoff snapshot, and operational decisions below still require approval. No original database query, source backup, process control, production profile/configuration change, Android operation or cutover was performed in this review.

## Evidence and completed gates

| Gate | Evidence |
|---|---|
| Write-capable account/workflow acceptance | C:/FYP/DB-Acceptance/20261104-003620/REPORT.md: 20 backend groups, 44 permission checks, 10 restart cycles; all 26 historical table hashes match |
| Extended stability | C:/FYP/DB-Soak/20261104-005337/REPORT.md: 1,802.9 seconds, 800 login/device/network/logout cycles, 4,902 requests, 10 restarts, 52 integrity snapshots, 24 offline Aria checks |
| Startup guard | backend/tests/test_production_guard.py plus real MariaDB acceptance in C:/FYP/DB-Readiness/20261104-211507/guard-acceptance-results.json; results recorded in the final review report |
| Key compatibility | Private encryption-key-compatibility.json: current backend/.env key equals the verified configuration/backend.env key; the one historical encrypted template decrypted successfully on the disposable server |
| Historical preservation | All 26 restored row hashes, six historical attendance rows, complete Samsung ACTIVE Slot 1 row and encrypted template match; these are backup-baseline facts, not a new live-source inventory |

The latest disposable copy uses 127.0.0.1:3311 and its own data/runtime paths. Both readiness attempts are preserved, with the first rejecting MariaDB's unquoted column-grant formatting; the parser was corrected without broadening privileges. Accepted/soak/backup environments were not used as writable test targets. All disposable servers are left stopped.

Current validation: 13 offline guard tests PASS; 17 real disposable MariaDB scenarios PASS; complete backend regression reports 226 tests, OK with 10 opt-in live/database tests skipped. The real guard suite separately exercised actual MariaDB identity/grants/decryption and pooled-connection drift. Final 24 read-only offline Aria checks and all 26 historical row hashes passed. Launcher PowerShell syntax and git diff whitespace checks passed. No Flutter code changed; Flutter checks were not rerun for this backend-only review.

Offline reproduction: `backend/venv/Scripts/python.exe -B -m unittest discover -s backend/tests -p test_production_guard.py -v`. The opt-in real runner is `backend/tests/run_production_guard_disposable.py --disposable-root <NEW-verified-copy-under-C:/FYP/DB-Readiness>`; it refuses completed rehearsals and requires untouched source-copy hashes before starting only port 3311. It is an operator test, not a production route or configuration option. Do not point generic live-test flags or integration URLs at production.

## Opt-in guarded launch

New components:

- `backend/production_guard.py`: immutable explicit profile, key fingerprint validation, fixed-code diagnostics, exact runtime grants and database identity checks.
- `backend/production_app.py`: CLI/check-only entry point; no default production settings or root engine are created on import.
- `start-recovered-backend.ps1`: dedicated launcher; no reload, no proxy headers, explicit HTTP binding and private profile required.
- `backend/application_factory.py`: extracted existing router/context composition, with optional lifespan validation and cleanup on startup failure. `backend/app.py` preserves existing imports/development behavior. No route/algorithm/threshold changed.

The private profile schema is shown in `backend/production-profile.example.json`. It deliberately contains invalid placeholders. Store a completed profile only under `.work/recovery/`, excluded from Git, with operator/SYSTEM/Administrators ACLs and no ordinary-user read/write access. The JSON contains runtime and encryption secrets; never paste, print or publish it. Do not copy disposable credentials into production. Account/profile creation for the real replacement is a later approved operator step.

Before creating the real private profile, create a NEW named child directory under `.work/recovery/` and restrict its ACL using the same reviewed private-backup recipe. Verify its ACL with `icacls` and have a separate operator inspect it before populating secrets. The loader verifies location, fields and key pin; it does not infer Windows ACL safety or certify the operator's approval. Pin resolved physical data paths too: a junction into protected source/backup/rehearsal directories is rejected.

The example proposes 127.0.0.1:3308, schema `fyprecoveredproduction`, runtime `fyp_prod_runtime@127.0.0.1`, and exact approved release directories. The guard allows an explicitly reviewed replacement port/schema, but always rejects port 3306, root/other runtime identities, original schema names and protected original/backup/rehearsal directories. A private profile is an operator trust input; it is not an institution-issued biometric approval or protection against a malicious local administrator.

Before API serving and again at lifespan startup, the guard requires the correct engine URL, server port/database/CURRENT_USER/datadir/basedir/version, loopback binding, writes enabled, LOCAL INFILE disabled, events disabled and automatic Aria/MyISAM recovery disabled. Every SQLAlchemy pool checkout repeats connection identity and exact SHOW GRANTS validation, including reused connections. No role, global privilege, broad schema grant, DELETE/DDL, extra column/table grant, GRANT OPTION or missing required privilege is accepted. The 24 runtime-visible tables must be InnoDB base tables. The separate offline administrator still validates all 26 application tables and system tables.

The approved key must match its pinned SHA-256 and be valid Fernet. Startup decrypts existing ciphertext through the unchanged partner template function, discarding the plaintext immediately. This establishes decryption compatibility only; it does not trust a template, authenticate a face or enable Slot 2. Empty template sets still require the independently pinned key; do not derive a new pin from a newly generated key.

Connections have 3-second connect and 5-second read/write deadlines. The check-only operator command should additionally be run under a 20-second process deadline; timeout means STOP, never fallback. Startup runs SELECT/SHOW/decryption only; no migrations, seeders, repairs or write probes. Failed startup closes resources and serves no API. Environment DB_* / BIOMETRIC_KEY / demo defaults cannot override the explicit settings supplied by the guarded profile. The existing unguarded `main:app` launcher remains available for the current development workflow; choosing it during cutover would bypass this new guard and is prohibited by this runbook.

Future approved commands, **not run against production**:

```powershell
# After the private profile and new server have passed offline validation:
& .\backend\venv\Scripts\python.exe -B .\backend\production_app.py --profile '<absolute-private-profile-under-.work/recovery/profile.json>' --check-only
& .\start-recovered-backend.ps1 -Profile '<absolute-private-profile-under-.work/recovery/profile.json>' -ListenHost '<existing-approved-LAN-binding>' -Port 8000
```

No `.env` swap is required by this launcher. Preserve the original `.env` unchanged; the separately approved new profile supplies settings directly. Preserve APP_TIMEZONE/session/challenge/threshold values in the profile. The example's defaults are proposals: compare them with the approved current effective settings before the window. Explicitly approve `DEMO_MODE=false` and offline provisioning; do not seed classes/PINs to hide this behavior change. No Flutter API_BASE_URL change is needed.

## Fresh source backup procedure — later approval required

This procedure is prepared only. The source on 3306 was not contacted, backed up, stopped or changed in this review. All following source operations require a separately named window, operator and approval.

1. **Record scope and identity.** Reconfirm executable, PID, version, source data/config paths and all XAMPP consumers. The historical PID is not a permanent identifier. Approve graceful shutdown and its outage impact. List every FastAPI worker/reloader, scheduler, phpMyAdmin/operator and other writer. If any writer cannot be frozen, stop the routine cutover.
2. **Create a NEW restricted backup directory.** For example `C:/FYP/DB-Backups/<approved-window>-fresh`. Require absence, space for source+dump+restore+rollback copies, no reparse/junction/external tablespace surprises, and private ACLs. Preserve the 20261103-134817 backup and manifest unchanged.
3. **Freeze writers and mark checkpoint R1.** Gracefully quiesce only the explicitly identified application workers. No arbitrary Python/MySQL kill commands. Record UTC/local cutoff, latest permitted write, effective configuration digests and key pin. Keep traffic closed until release. Confirm no DDL, migrations or seeders are running.
4. **Bounded source read gate.** Via an explicit approved local operator connection, pin 127.0.0.1:3306/schema and verify expected version/datadir/basedir. Connect/read/write deadlines 3/5/5 seconds; an outer probe deadline of 10 seconds. Confirm all expected tables are InnoDB and no unexpected views, routines, triggers, events, cross-schema references, DEFINER objects, .isl paths or changed constraints exist. Review surprises before proceeding. Do not run CHECK/repair/upgrade on the unhealthy source as a diagnostic shortcut.
5. **Fresh canonical source baseline.** Under writer freeze, capture all 26 table definitions, ordered columns, exact counts, primary/unique/foreign/check constraints and canonical whole-row hashes. Capture full attendance/device/student rows privately through hashes, not console dumps. Reconfirm the table inventory: additions require explicit plan review rather than silent omission.
6. **Consistent logical dump.** With all tables InnoDB, writers/DDL frozen and protected credentials in a dedicated option file, use the compatible 10.4.27 dump tool. Keep secrets off command lines. Use the existing plan's command below under an outer bounded wrapper. Nonzero exit, timeout, incomplete output or source read failure is NO-GO; never silently remove security/consistency flags to make it pass.
7. **Repeat baseline after dump.** All counts/schema/row hashes must match the pre-dump baseline. Verify dump exit/completion marker, schema/table list and file SHA-256. An isolated restore is the decisive dump validation, not grep/counting INSERT lines alone. A single-transaction flag does not excuse unfrozen writers or DDL.
8. **Approved graceful source shutdown and checkpoint R2.** Only if separately authorized, issue identity-checked SHUTDOWN and wait boundedly for the named process to exit, port to close and PID file to disappear. If unhealthy SQL/shutdown hangs or cannot finish, STOP. No forced kill, skip-grants mode, repair, restart or live file copy is authorized by this routine procedure.
9. **Consistent full cold copy.** Once fully stopped, copy the entire source data directory, all system databases/control/log files, matching my.ini variants and protected effective application configuration/secrets. Manifest all relative paths, directories, file sizes and SHA-256; verify destination and rehash unchanged stopped source. Resolve external/reparse dependencies explicitly. Do not describe a live changing directory copy as consistent. Keep this as evidence, including corrupted privilege tables; never import its mysql tables into the replacement.
10. **Restore and compare in another NEW isolated instance.** Initialize clean matching system tables, restore the fresh logical application dump into an absent schema and compare every schema/count/hash against the fresh baseline. Validate all 26 tables, system tables, 24 Aria files offline after graceful stop, and a clean restart. Reconfirm matching decryption key. Historical differences are allowed only when explained as legitimate preserved later data. The six old attendance rows remain; newer rows must also be retained.
11. **Checkpoint R3.** Sign off the complete backup manifest, successful isolated restore, fresh all-table comparison, key compatibility, and a clean replacement cold snapshot before backend routing changes. Keep all preceding evidence immutable.

Future dump command; never substitute a shell password:

```text
<approved-runtime>/bin/mysqldump.exe --defaults-extra-file=<private-original-client.ini> --host=127.0.0.1 --port=3306 --single-transaction --quick --skip-lock-tables --skip-add-locks --routines --events --triggers --hex-blob --complete-insert --skip-extended-insert --default-character-set=utf8mb4 --result-file=<fresh-backup>/attendance_proposal_xampp.sql attendance_proposal_xampp
```

`--defaults-extra-file` is the first tool option. An operator wrapper uses `subprocess.run([...], timeout=<reviewed-limit>, stdin=DEVNULL, stdout=<private-log>, stderr=<private-log>, creationflags=CREATE_NO_WINDOW)`, checks exit 0 and handles timeout as NO-GO. If the dump client must be terminated after timeout, that action concerns only the explicitly created dump client; it never authorizes terminating mysqld. Large data requires a reviewed longer bounded deadline, not an infinite retry.

For each table, use the established `production-before.json` algorithm: `SELECT *`, fixed column order, canonical `json.dumps(dict(zip(columns,row)), default=str, sort_keys=True, separators=(',',':')).encode('utf-8')`, sort encoded rows, and SHA-256 each row's 8-byte big-endian length followed by its bytes. Save columns/count/hash privately. Use the identical connector/serialization version for source and restore; independently review any new binary/decimal/date types. No JSON hash may omit auth/audit/challenge tables.

Attendance: compare every primary key, student/class/session/verification reference, timestamp and status, including rows newer than the historical six. Samsung: compare the entire device row by immutable device_id, public SPKI bytes/hash and recomputed fingerprint, slot/status, name/model, registered/revoked metadata and generated active slot. Never re-register/revoke it as a test. Biometric: compare complete student row and encrypted-string hash; decrypt only in an authorized isolated verifier with the matching pinned key, without saving images/encodings. Require exact metadata and ciphertext preservation, not re-enrollment.

**Hard stop:** if the original cannot supply a fresh consistent baseline/logical dump and verified backup, request a separate forensic extraction/shutdown plan. The older backup cannot silently become current truth. Recovery to an older point and any possible lost records need explicit owner approval; this review grants none.

## Encryption-key custody

`BIOMETRIC_KEY` is the backend Fernet key; it is separate from the Samsung Android Keystore private key, which stays on the phone. The existing current `.env` and verified `configuration/backend.env` remain intact. Private readiness evidence records only their hashes, key digest and decryption outcome.

At the window, verify their key fingerprints again and capture the approved effective key, including any worker environment override, in the protected new profile and fresh configuration backup. Copy the exact key string; never call setup.py, Fernet.generate_key or a seeder. Keep independent restricted offline copies and the rollback configuration. Compare the profile key against the protected reference digest, then require template decryption before serving. A mismatch means STOP; do not repair it by changing ciphertext or enrollment. Neither losing the key nor automatically trusting historical templates is an acceptable recovery action.

## Checklists and rollback checkpoints

| Checkpoint | Required evidence / action | Failure / rollback action |
|---|---|---|
| R0 — before maintenance | Named approval, account/profile/DEMO_MODE decisions, target paths/port/schema, original identity, writers, operator and rollback owner, residual corruption risk acceptance | No operational action; retain original configuration and evidence |
| R1 — writers frozen | Known last source write, closed traffic, bounded source identity, all-table fresh baseline | Remain in maintenance; no source shutdown/backup fallback/repair without its approval |
| R2 — fresh backups | Valid logical dump plus fully stopped consistent cold copy and protected config/key manifests | Preserve partial evidence; stop routine cutover; no old-snapshot substitution |
| R3 — replacement validated | Fresh restore equals all fresh counts/hashes, key decrypts, clean system/application checks and restart, exact accounts/grants, replacement cold snapshot | Do not route backend; preserve replacement diagnostics; original remains preserved |
| R4 — guarded backend / zero release writes | Guard check-only PASS with deadline; no old workers/pools; explicit new profile and same approved HTTP endpoint; no reload/proxy-header trust; no general traffic | Stop only new workers and retain diagnostics. Restore prior launch selection only as configuration rollback; the known-corrupt original is not an automatic healthy fallback |
| R5 — approved smoke writes | Record first target write/epoch; permit only named login/auth/audit/device-proof writes; log every expected delta; all attendance/template/Samsung fields remain unchanged | Freeze target, back up latest complete authoritative data; never discard smoke writes or merge old/new sessions ad hoc |
| R6 — traffic released | Operator signs baseline+expected deltas, normal security responses and continued health/log monitoring; record new recovery point | After any accepted write, new data is authoritative. Quiesce and back up; rollback code/config against same current dataset, or restore all latest data into another validated release |

Before R4: verify the approved private profile differs only in reviewed database/security settings; original key/session/timezone/threshold values remain correct. No automatic migrations/seeding/public student registration. Confirm restored policies as-is; absent/disabled policies must keep attendance blocked. Do not authorize localhost, broaden CIDRs, invoke a replacement on Samsung or enable Slot 2 to make smoke tests pass.

After R4, before traffic release: run read-only health/config/device listing and the separately approved normal login/device-proof/network diagnostics. Auth/audit writes are real writes and move rollback to R5. Require generic wrong-password denial, revoked/unknown device rejection with disposable fixtures only, actual ASGI source-IP policy results and disabled/absent-policy rejection. Use existing isolated acceptance evidence for positive/negative attendance, signature replay/expiry, policy changes after preflight and concurrent final submissions. Live successful attendance is only a legitimate approved class submission; maintenance never creates/deletes fake attendance. Keep final device proof, fresh CIDR and biometric checks unchanged.

Never restart or route traffic to the known-corrupt original automatically. After accepted writes, an old six-row snapshot is not a zero-loss rollback. Any data loss, original repair/restart or forced shutdown requires a new explicit decision. If a verified zero-loss path is unavailable, remain in maintenance and preserve evidence.

## Remaining risks and account decisions

- Recurring Aria corruption cause is unresolved. The explicit-stdio/console recipe passed modest sequential load and graceful restarts; it does not prove protection against concurrent heavy load, abrupt power loss, memory/storage/antivirus interference or the historical access violation. No destructive filesystem repair or security-software exclusion is proposed. A supported-version upgrade is a separate tested project.
- Fresh source responsiveness and records newer than the old backup remain unknown. No current-source query was authorized in this review.
- The passive final port observation showed mysqld PID 107672 on 3306, different from the historical 70532. The executable path was unavailable through the read-only process metadata query; current health/datadir were not queried. Reconfirm identity under the later explicit maintenance approval before any source operation. No process restart was performed in this review.
- Approve the exact runtime `@127.0.0.1` account and tested grants. Do not reconstruct the missing historical mysql.db records by guessing. Changing plugin/host/grant/resource-limit syntax requires a guard/policy review; unexpected grants fail closed.
- Confirm named owners and independent private secrets for runtime, network operator, identity provisioner, offline verifier and restore administrator. Limit/lock maintenance accounts outside windows. Define password/account-status administration separately; the tested identity role currently inserts students and cannot change passwords/status. Audit access exposes sensitive hashes/ciphertext and belongs only to the approved offline verifier.
- Approve DEMO_MODE=false and legitimate timetable/class provisioning. Existing student/demo credentials and public lifecycle authorization concerns are separate security work, not solved by MariaDB account recovery. Partner trusted-biometric tables/provider permissions remain a future dependency; COMPLETED_UNTRUSTED remains insufficient for activation.
- Inventory other XAMPP applications/accounts before any original shutdown. This FYP-only recovery does not restore unknown historical grants or recover other schemas into the new server.
- Agree retention, encryption-key custody, monitoring owner, fresh-backup capacity, smoke-write accounting and zero-loss post-write rollback before approving the window.

The requested approval may schedule and name a controlled window with these hard stop gates. Execution GO is issued only at the applicable checkpoints after fresh source evidence is available. No task in this review grants permission to operate on production.
