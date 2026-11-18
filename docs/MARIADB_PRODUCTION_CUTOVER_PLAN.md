# MariaDB production recovery and cutover plan — REVIEW ONLY

Prepared on branch SH, 4 November 2026. This is a runbook proposal, not an executable change or authorization. No production database connection, service control, account grant, configuration edit, recovery or Flutter change was performed while preparing it. All commands below are for later approved stages only. No passwords are included.

## Decision and scope

**Current status: conditional GO to request a separately approved maintenance window; NO-GO to execute cutover now.** Disposable acceptance passed 20 backend scenario groups and 44 permission checks; a separate 30-minute soak passed 800 workflow cycles, 10 restarts and 24 offline Aria checks. The opt-in startup guard now passes offline and real disposable MariaDB validation. Fresh source snapshot/reconciliation and explicit operational approval remain mandatory; the corruption mechanism remains unproven. See [the current readiness checklist](MARIADB_CUTOVER_READINESS.md) for evidence, commands and rollback gates. The six attendance rows are the 3 November backup baseline, not a promise that the current source still has exactly six rows.

Recommended design: a separately initialized replacement server under a NEW permanent directory, for example C:/FYP/MariaDB-Recovery/releases/<approved-release>, bound to 127.0.0.1:3308. Restore into a NEW schema named fyprecoveredproduction. Keep the original C:/xampp/mysql/data and its backups intact; never replace its mysql folder or repair it as part of this cutover. Do not promote the disposable candidate2 directory itself. Other XAMPP databases and their unknown account requirements are outside this FYP-only migration and must be inventoried before a server-wide outage.

Keep the FastAPI HTTP address/port and Flutter API_BASE_URL unchanged. Database port/schema/account changes are backend-internal. No forwarded-IP trust changes belong in this operation.

## 1. Inspected backend and required configuration

backend/config.py loads backend/.env with os.environ.setdefault and captures Settings defaults at import. Process environment wins over the file, and existing workers/SQLAlchemy pools retain old settings until replaced. The effective inspected configuration was DB_HOST=127.0.0.1, DB_PORT=3306, DB_NAME=attendance_proposal_xampp, DB_USER=root, no password, DEMO_MODE=true. BIOMETRIC_KEY was present; its value was not displayed.

backend/database.py creates a mysql+mysqlconnector URL, pool_pre_ping and READ COMMITTED sessions. The existing main:app development entry point remains unguarded; the new opt-in production_app.py entry point uses production_guard.py. Use only the separately approved guarded launcher during recovery. Its optional URL argument is for callers/tests and must not silently override the approved target. start-backend.ps1 currently uses --reload and inherited settings: do not use it unchanged for this maintenance launch.

Proposed approved replacement profile:

```text
DB_HOST=127.0.0.1
DB_PORT=3308
DB_NAME=fyprecoveredproduction
DB_USER=fyp_prod_runtime
DB_PASSWORD=<private unique runtime secret>
DEMO_MODE=false
BIOMETRIC_KEY=<preserve the exact existing value; never regenerate>
```

Preserve timezone, matching threshold, challenge/session policy and all other configuration unless separately reviewed. In particular, keep the encrypted template's matching Fernet key. No setup.py, sample/demo seeder, automatic upgrade or migration is needed merely to restore the existing schema. DEMO_MODE=false is an explicit proposed security change: public account registration and automatic demo timetable/PIN generation cease. Approve this behavior before cutover; missing current class sessions must not be disguised by seeding production.

A dedicated private launch profile/startup guard is now implemented and disposable-tested (production_guard.py, production_app.py and start-recovered-backend.ps1): require exact host/port/schema, expected @@datadir/basedir/version, runtime CURRENT_USER and approved grants before listening for HTTP requests. Reject missing settings, root/empty credentials, the old endpoint or an unapproved URL override. The ordinary start-backend.ps1, production .env and running backend configuration have not been changed. application_factory.py holds shared composition, and app.py preserves the existing compatibility entry point. The guarded path does not import/create the legacy default root engine.

## 2. Explicit replacement-account policy

These are NEW policies, not guesses about lost historical grants. All accounts are restricted to the exact local TCP host, use independent random secrets and have no roles or GRANT OPTION. Privileges apply only to the new schema. No runtime DELETE, DDL, FILE, PROCESS, SUPER, replication, system-table, global write or CREATE USER permission. The application does not need root. Keep original student passwords and session records unchanged by the database cutover; any student credential hardening is a separate reviewed change.

Runtime minimum inferred from actual handlers/services with DEMO_MODE=false:

| Tables | Runtime permissions / rationale |
|---|---|
| student_groups, courses, class_schedules, class_sessions, network_policies | SELECT; reference data/policy only |
| students | SELECT; UPDATE only face_encoding, biometric_status, consent_at, updated_at for existing partner lifecycle behavior |
| registered_devices | SELECT, INSERT; UPDATE only status, revoked_at, revocation_reason; existing key/fingerprint/slot/timestamp immutable through UPDATE |
| auth_sessions, verification_attempts, verification_challenges | SELECT, INSERT, UPDATE; login, cancellation and verification state |
| device_registration_challenges, device_verification_challenges, pending_device_registrations, device_biometric_sessions, device_activation_challenges, attendance_device_challenges | SELECT, INSERT, UPDATE; expiring single-use state |
| attendance | SELECT, INSERT only; existing final writer |
| device_registration_events, device_verification_events, device_enrollment_events, device_activation_events, attendance_authorization_events | SELECT, INSERT; append audit plus rate-limit queries |
| device_biometric_events, network_verification_events | INSERT only; current runtime appends these logs |
| programmes, network_policy_events | No runtime grant in the current production routes; provisioning/operator responsibilities |

The DELETE /biometrics HTTP route performs UPDATE, not SQL DELETE. Device replacement inserts a new registration and updates the old status; it must not delete either slot. Partner inference and lifecycle authorization rules are not redesigned here. Future trusted-biometric tables/provider changes need their own permission review; never pre-grant broad access for them.

Use dedicated operators, never the web runtime:

- fyp_network_operator: SELECT/INSERT/UPDATE on network_policies, INSERT on network_policy_events; no student/device/attendance or schema privileges. Run the policy CLI with an explicit operator profile targeting only the new instance.
- fyp_identity_operator: SELECT on programmes/student_groups/students and INSERT on students for approved offline provisioning. No template, registration, attendance or privilege-system updates. Additional account-status/password administration requires a separate defined column policy.
- Read-only validation/audit identity: SELECT only on the required restored tables, with sensitive template/token/password-hash access restricted to the approved offline verifier.
- Schema/restore administrator: separate local operator, protected secret, not used by FastAPI. Schema DDL and physical backup/restore are maintenance-only. Do not leave a broadly privileged migration account unlocked for normal use. Never restore damaged mysql grants into the clean server.

### Reviewed runtime GRANT proposal (NOT RUN)

Create accounts only after confirming the exact target identity and account absence. Use a parameterized operator connection with a cryptographically random secret from a protected store; never put a real password on a command line or in this document. For example, the operator code would execute `CREATE USER 'fyp_prod_runtime'@'127.0.0.1' IDENTIFIED BY %s` with a bound private parameter. Do not use a literal placeholder as a password or use CREATE USER IF NOT EXISTS to hide a collision.

```sql
GRANT SELECT ON fyprecoveredproduction.student_groups TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT ON fyprecoveredproduction.courses TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT ON fyprecoveredproduction.class_schedules TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT ON fyprecoveredproduction.class_sessions TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT ON fyprecoveredproduction.network_policies TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT ON fyprecoveredproduction.students TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT UPDATE(face_encoding,biometric_status,consent_at,updated_at) ON fyprecoveredproduction.students TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT ON fyprecoveredproduction.registered_devices TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT UPDATE(status,revoked_at,revocation_reason) ON fyprecoveredproduction.registered_devices TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.auth_sessions TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.verification_attempts TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.verification_challenges TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.device_registration_challenges TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.device_verification_challenges TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.pending_device_registrations TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.device_biometric_sessions TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.device_activation_challenges TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE ON fyprecoveredproduction.attendance_device_challenges TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT ON fyprecoveredproduction.attendance TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT ON fyprecoveredproduction.device_registration_events TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT ON fyprecoveredproduction.device_verification_events TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT ON fyprecoveredproduction.device_enrollment_events TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT ON fyprecoveredproduction.device_activation_events TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT SELECT, INSERT ON fyprecoveredproduction.attendance_authorization_events TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT INSERT ON fyprecoveredproduction.device_biometric_events TO 'fyp_prod_runtime'@'127.0.0.1';
GRANT INSERT ON fyprecoveredproduction.network_verification_events TO 'fyp_prod_runtime'@'127.0.0.1';
```

These exact grants have now passed disposable write-capable acceptance and guard tests on MariaDB 10.4.27; future provider tables and untested workflows still require their own review. Isolated acceptance exercised SQLAlchemy inserts/generated IDs/dirty-column updates, constraints, savepoints and every SELECT ... FOR UPDATE under MariaDB 10.4.27 with server read_only OFF. Do not let read_only denials substitute for proving missing grants. If a locking read or ORM readback needs another privilege, record the exact SQL/error and review a narrowly scoped fix; do not silently grant UPDATE on network policies or broad global/table permissions. Unknown historical accounts, other applications and the future partner provider are not covered by this policy.

## 3. Aria recurrence investigation and release gate

Observed, not assumed:

| First candidate | Successful candidate2 |
|---|---|
| Hidden Start-Process without explicit stdin/stdout/stderr redirection | CREATE_NO_WINDOW with stdin=DEVNULL, explicit private stdout/stderr file handles |
| log-error file destination | --console, no log-error setting; redirected stderr/stdout |
| Fresh mysql.db later failed after restart; log-like text in its index | 24 system tables clean, restart/persistence and final offline checks clean |

Both used 10.4.27 binaries. The initial first candidate also used skip-name-resolve and later changed it; candidate2 started without it and secured the generated hostname-root account before normal testing. They used different freshly initialized data directories. This was NOT a controlled one-variable experiment. The outcomes support further investigation of logging/handle behavior, but do not prove that it caused either the original or first-candidate corruption.

Read-only review in this planning turn compared both configurations and inspected bounded Windows events. The storage-provider warning/error query found no matches in the last 30 days; this is not a disk-health certificate or a root-cause exclusion. Informational Ntfs events and unrelated same-number CPU/boot events must not be described as disk failures. The earlier MariaDB log's access violation and repeated crash recovery remain relevant history.

Before production approval, on disposable instances only:

1. Preserve failed candidate1, successful candidate2 and their private logs; do not truncate or repair evidence.
2. Use hash-checked compatible binaries and an explicit defaults file. Verify all data/log/temp/control paths point only at the selected directory. Never launch through a default XAMPP button/script that might select the original directory or ambiguous handles.
3. Use valid persistent standard handles and --console with explicit private redirection. Do not mix competing log-error/console destinations without a reviewed reason. The process host/service wrapper must keep those handles valid for the server lifetime and capture clean startup/shutdown markers.
4. Repeat at least 10 clean start/write/check/shutdown/restart cycles plus a representative-duration soak. Exercise synthetic login, challenge/audit writes, approved disposable account/grant operations and a concurrent workload under the proposed runtime account. No forced shutdown or automatic repair.
5. Check all Aria system tables and data hashes before/after cycles. Stop on any checksum/index error, unexpected log text in privilege files, missing grant, crash, recovery-at-normal-start or source/target identity mismatch. Do not disable checksums or use forced auto-recovery to hide a failure.
6. Review actual storage health/free space, Windows Application/Disk/Ntfs/StorPort events and antivirus/backup/synchronization interference using non-destructive diagnostics. Do not disable security software or run filesystem repair without separate approval.

Document the launch recipe and obtain an explicit residual-risk acceptance if the mechanism remains unresolved. A single successful restart is insufficient evidence that recurrence is solved. Recovery stays version-compatible; a supported-version upgrade is a separate tested project, not a repair command to combine into this cutover.

## 4. Bounded checks and comparison specification

Every operator connection must set connection/read/write deadlines (example 3/5/5 seconds) plus a subprocess wall-clock limit (example 10 seconds for probes). Pin 127.0.0.1 and the approved port explicitly; never rely on client defaults. Do not retry forever or kill mysqld on a health timeout. Identity check before any write:

```sql
SET STATEMENT max_statement_time=2 FOR
  SELECT VERSION(), @@port, @@datadir, @@basedir, @@read_only, CURRENT_USER();
```

Reject any mismatch with the approved target. Read-only validation captures SHOW CREATE TABLE, table engine, columns/types, primary/unique indexes, checks and foreign keys, normalizing only the approved schema-name difference. Reject unexpected views, triggers, events, routines, DEFINER objects, external tablespaces or cross-schema references until reviewed. All 26 expected tables must be InnoDB. Unexpected table additions/schema changes require an updated plan, not silent omission.

For all 26 tables: record exact counts and length-prefixed SHA-256 over sorted canonical JSON rows with fixed columns, deterministic date/byte serialization and no data printed. Use the established production-before.json format, but generate a NEW baseline at the approved freeze. Include every auth/audit/challenge row; do not compare only attendance. Also compare all attendance primary keys/student/session/verification IDs/timestamps/status, explicitly separating the six old rows from any later legitimate rows.

Samsung: compare the entire registered_devices row by device_id: owner, Slot 1, ACTIVE status, public-key SPKI bytes, fingerprint, name/model, registered_at, revoked_at/reason and generated active slot. Compare public-key fingerprint computed from stored SPKI. No getOrCreate, key rotation, replacement, revocation or re-enrollment test on the real Samsung.

Biometrics: compare the entire student row plus a private SHA-256 of the encrypted face_encoding string and enrollment/consent/status metadata. Verify the matching BIOMETRIC_KEY file/secret digest without displaying it. In an authorized isolated process, decrypt without saving/printing the encoding and validate it through the unchanged partner reference path. A ciphertext hash alone does not prove the correct decryption key or genuine live matching. Never fix a decryption failure by re-enrolling the student or generating a new secret.

Run CHECK TABLE for all 26 application tables and the clean mysql system tables, with per-command deadlines and a planned longer bounded limit for any large table. Require OK, not merely connection success. CHECK is an administrative validation on the replacement/disposable server, not a production-read probe during this planning turn. Record logs and manifests privately with restricted ACLs.

## 5. Approval stages and fresh backup gate

Stage A — separate disposable-only approval: prove the runtime grants and recurring-Aria controls above, using synthetic students, signing keys and policy/source-IP fixtures. Do not connect the real production backend to a rehearsal database. Existing tests that create/drop temporary MariaDB schemas must run only under an explicit disposable administrator profile. The restored test runner has configuration/manifest assumptions and is not a plug-and-play production validation command.

Stage B — explicit original-maintenance approval: name the original PID/path/port, maintenance window, all affected applications, writer-quiescence method, graceful shutdown request and backup destination. Notify users. Freeze ALL writers before the cutoff: FastAPI workers/reloader children, phpMyAdmin/operators, scheduled tasks and other applications using this MariaDB instance. Do not kill arbitrary Python processes or let the XAMPP Stop button silently fall back to a force kill.

Stage C — immediately before cutover, create additional fresh backups:

1. With writers frozen and if SQL is responsive, take a bounded consistent logical dump and fresh canonical baseline from the original, preserving schema, routines/events/triggers and all records. All tables being transactionally dumped must be InnoDB. Do not let any DDL run during the dump. Verify exit/completion, source/table list, counts, checksums and unchanged source row digests.
2. Request a separately approved graceful original shutdown, verify the exact process exited and port/PID file are gone. If it does not exit normally, STOP. No force kill, aria repair, skip-grants startup or blind file copy is authorized by this runbook.
3. Only while fully stopped, copy the ENTIRE original data directory plus matching configuration/secrets into a NEW restricted backup location, outside all original/replacement directories. Check external .isl tablespaces/reparse points. Hash every file and directory, rehash source, verify the copy and retain the old 3 November backup untouched. A compatible hot-backup alternative needs its own validated preparation/verification procedure; do not claim a live ordinary copy is consistent.
4. Compare fresh logical/restored data and counts. The historical 26-table/six-attendance snapshot is only a reference. Any later legitimate attendance, device, template, policy or session changes must be preserved. Do not overwrite them with the older backup.
5. Restore the fresh logical dump into a NEW replacement schema under the exact new release directory; validate before creating runtime accounts or opening the application. Capture a final clean replacement cold backup and successful restart evidence before release.

**Hard stop:** if the unhealthy original cannot provide a fresh logical snapshot/baseline or a verified consistent fresh backup, no routine cutover proceeds. The old backup cannot silently become the new source of truth. Escalate for a separately approved forensic shutdown/snapshot/extraction plan. If only the old backup is usable, the exact recovery point and potential later-record loss require explicit owner approval; this plan does not authorize that loss.

Illustrative future dump command (NOT RUN; credentials through a protected option file, never inline):

```powershell
& '<approved-runtime>\bin\mysqldump.exe' --defaults-extra-file='<private-original-client.ini>' --host=127.0.0.1 --port=3306 --single-transaction --quick --skip-lock-tables --skip-add-locks --routines --events --triggers --hex-blob --complete-insert --skip-extended-insert --default-character-set=utf8mb4 --result-file='<fresh-backup>\attendance_proposal_xampp.sql' attendance_proposal_xampp
```

The operator wrapper must enforce a deadline, stop on nonzero exit, and capture output privately. Stop the original only through the explicitly approved identity-checked administrative session and bounded SHUTDOWN; do not use a generic taskkill/Stop-Process command. These commands are not executed in this planning task.

## 6. Replacement and backend switch

Initialize fresh system tables in the approved NEW release directory with the matching Windows initializer, no service/remote-root/default-user flags. Do not copy mysql tables from the damaged installation. Set strong local bootstrap credentials before accepting normal connections. Review initializer test/test_% grants, anonymous/default/hostname accounts and clear them only with explicit fresh-instance cleanup approval. Keep clean mariadb.sys semantics and reviewed local administration.

Example initialization/start recipes, NOT RUN:

```text
<approved-runtime>/bin/mysql_install_db.exe --datadir=<new-release>/data --port=3308 --skip-networking
<approved-runtime>/bin/mysqld.exe --defaults-file=<new-release>/server.ini --console --init-file=<private-bootstrap.sql>
```

The launcher supplies stdin=DEVNULL, explicit private stdout/stderr handles and CREATE_NO_WINDOW; no inherited production options or process handles. No Windows service registration is assumed. A future service wrapper needs its own tested lifecycle/stdio configuration. Every data/log/control/temp path is explicitly under the NEW release; bind 127.0.0.1 only; disable LOCAL INFILE, restrict secure_file_priv, replica autostart and automatic table repair. Keep read_only ON until controlled-write acceptance is approved; then configure the replacement OFF for normal non-SUPER app writes. Do not grant SUPER/READ_ONLY ADMIN to bypass it.

Restore only the FYP schema from the FRESH dump into absent fyprecoveredproduction, using an explicit port-3308 administrator connection and target identity guard. Review the dump for database-switch/cross-schema statements before importing. Do not use candidate2 credentials, its old data or a source mysqld defaults file as the final production profile.

Before changing the backend, validate schema/data/keys read-only, apply the reviewed new account grants, then exercise full write-capable behavior under that account in the disposable acceptance environment. The production replacement must still equal the fresh source baseline before any authorized acceptance writes.

Prepare protected .env.next and a rollback copy of the current environment. Show a redacted diff containing only the approved DB host/port/schema/user/password-presence and DEMO_MODE changes. Verify matching BIOMETRIC_KEY digest. Stop all old FastAPI workers and SQLAlchemy connection pools gracefully. Confirm no process/environment DB_* override can select the original even after the file changes. Atomically replace the environment file only after approval; do not echo secrets or commit it. Keep a protected rollback environment copy.

Start the backend through start-recovered-backend.ps1 without --reload, using an explicitly reviewed private JSON profile and the new identity guard. The guarded profile supplies every Settings field directly; DB_* and BIOMETRIC_KEY environment/default values cannot override it. Maintain its existing LAN HTTP endpoint and --no-proxy-headers so Flutter needs no change. Do not change firewall rules or expose a new public listener as a side effect.

```text
<backend-python> -B backend/production_app.py --profile <private-profile-under-.work/recovery/profile.json> --host <existing-approved-LAN-binding> --port 8000
```

No fallback to root, port 3306 or the prior database is permitted on a connection/permission error. Do not release maintenance until the target identity and planned acceptance checks pass. Record the first permitted target write/cutover epoch for rollback accounting.

## 7. Application security acceptance matrix

Complete on disposable restored data first with the ACTUAL proposed runtime grants, server read_only OFF, real cryptographic signing fixtures and no production mock/bypass:

| Area | Mandatory evidence |
|---|---|
| Login | Correct login creates hashed session; incorrect/expired/revoked session fails; generic errors and throttle work; DEMO_MODE=false blocks public registration/seeding |
| Device | Both ACTIVE slots independently verify disposable keys; unknown/pending/revoked/wrong owner/session/key fail; invalid/expired/replayed and concurrent proofs fail correctly; Samsung baseline row remains unchanged |
| Network | Actual ASGI authorised IPv4/IPv6 PASS; outside/loopback/absent/disabled/invalid policy FAIL; forged CF/XFF/Forwarded ignored; no client IP/PASS accepted |
| Early preflight | Disabled/unreachable/rejected device/network prevents camera; readiness creates no attendance and is never final proof |
| Final attendance | Existing /liveness/frame writer requires genuine biometric state, fresh attempt/session-bound single-use ACTIVE-device signature and CURRENT source-IP policy check in the insertion transaction; no alternate writer |
| TOCTOU/replay | Policy/network/device changes after readiness still fail final insert; duplicate/concurrent final submissions produce at most one synthetic attendance row |
| Biometrics | Same partner inference/threshold/random gesture/three-frame behavior; correct encryption key; no template mutation; COMPLETED_UNTRUSTED never activates Slot 2 |
| Privileges | Runtime SQL operations succeed under narrow grants; policy writes, audit UPDATE/DELETE, student password/account-status writes, registered-key UPDATE, DDL/system/original-schema/FILE/admin access are denied |

All negative attendance cases must have zero attendance delta. Positive attendance tests write ONLY synthetic isolated students/classes; never create test production attendance and then delete it to hide testing. No real Samsung replacement/revocation or getOrCreate/Keystore rotation. Trusted-biometric provider remains unavailable/fail closed unless independently integrated later.

After switch, restricted production smoke testing may use normal login, read-only device listing and approved existing-key device verification; these create known auth/audit records, so baseline comparisons must distinguish approved test writes from unexpected changes. Real network diagnostic must honor the restored policy as-is; do not enable/seed broad CIDRs or authorise localhost to force PASS. Actual successful live attendance requires a legitimate approved class submission, not a maintenance test. Keep global traffic closed until the baseline and core identity checks pass.

Planned test commands, only in dedicated disposable test profiles:

```text
<backend-python> -B -m unittest discover -s backend/tests
flutter test
flutter analyze
```

MariaDB opt-in integration and restored-database runners require separately verified disposable administrator configuration and correct fresh manifests; do not simply run them with the original or live replacement credentials. The acceptance report records 20 write-capable backend scenario groups and 44 privilege checks; the soak and guard readiness reports add repeated restart and startup isolation evidence. These remain disposable results, not live production smoke-test approval.

## 8. Rollback without losing records

Before accepted production writes: stop/quiesce the NEW backend workers, keep replacement data and diagnostics, and restore the protected prior backend environment only as a configuration rollback. Do NOT automatically restart or route traffic to the known-corrupt original. It is not a healthy availability fallback. Stay in maintenance unless a separately verified healthy original or prior healthy replacement is explicitly approved. Do not delete the new release or overwrite original files.

After ANY accepted production writes: the new server is authoritative for those writes. Freeze traffic/writers again, take a new consistent backup and record all 26 table states, attendance IDs and audit/session changes. Roll back backend code/configuration against that same current dataset when possible. If another database release is required, restore/migrate the latest complete authoritative data into it and revalidate before release. Never restore the old six-row snapshot over new attendance, merge records ad hoc, dual-write the old database, or silently accept data loss. No automatic record deletion or old/new session merge.

If corruption or backup failure prevents a zero-loss rollback, keep maintenance enabled and escalate. Preserve evidence. Restarting the original, forced shutdown, discarding accepted records, original file replacement or recovery requires another explicit approval. Every expired challenge must restart with a fresh server proof; reusing old PASS results is never a recovery shortcut.

## 9. Approval record and remaining risks

Approval must name: maintenance scope/PIDs/ports, all affected applications, fresh backup method and recovery point, replacement directory/schema/accounts/grants, explicit DEMO_MODE change, exact backend configuration diff, accepted Aria residual risk, permitted production smoke-test writes, rollback owner and zero-loss policy. The user must separately approve ORIGINAL health/database connections and any original shutdown/backup/configuration operation before execution. This document grants none of those permissions.

Remaining blockers: recurring-corruption root cause; fresh source responsiveness/consistent backup; unknown other-server accounts/applications; long-term supported-version plan; unchanged demo/student credential risks; post-write rollback/backup operational capability. The root cause is not assumed solved by console redirection. Candidate2 and existing cold/logical backups remain untouched evidence, not drop-in production system databases.

References: [MariaDB Windows console options](https://mariadb.com/docs/server/server-management/starting-and-stopping-mariadb/mariadbd-options), [error-log destinations](https://mariadb.com/docs/server/server-management/server-monitoring-logs/error-log). Existing local evidence: C:/FYP/DB-Clean-Rehearsal/20261104-001217/candidate2/REPORT.md and validation JSON files; C:/FYP/DB-Backups/20261103-134817/REPORT.md and manifests.

## Planning validation performed

Static review matched all 26 backup table names: the 26 proposed runtime GRANT statements cover exactly 24 tables, excluding programmes and network_policy_events. Proposed column-limited updates match the recorded students/registered_devices columns. No runtime DELETE/DDL/global-administration grant is present; Markdown fences/control characters and git diff whitespace checks passed. No SQL GRANT, backup, service action, functional test, application launch or cutover command in this document was executed. Subsequent disposable acceptance passed privilege/locking-read validation under the unchanged proposed grants; see the readiness report. No production account/grant operation was performed.

## Readiness update — 4 November 2026

The current evidence and exact pre/post/rollback checkpoints are in [MARIADB_CUTOVER_READINESS.md](MARIADB_CUTOVER_READINESS.md). The dedicated guard validates connection identity and exact runtime privileges on every pool checkout, checks required runtime-visible InnoDB tables and existing template decryption before serving, and has no fallback to the old endpoint. It remains opt-in; no production configuration change was made. Private source-key compatibility evidence confirms the current BIOMETRIC_KEY matches configuration/backend.env in the verified backup and decrypts the restored template in an isolated process. No template/key change or institutional trust approval occurred.

A separately approved maintenance window may now be requested with explicit conditional gates. Approval to schedule a window must not be interpreted as permission to discard newer data or repair/force-stop the original. A fresh consistent source snapshot at the cutoff remains a hard NO-GO gate for routine cutover.
