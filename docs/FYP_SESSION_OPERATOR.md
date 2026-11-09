# Synthetic attendance sessions — PowerShell 7

These commands target only the guarded disposable backend **8002**, MariaDB
**127.0.0.1:3322**, and `fypdevicemgmt_restore_a199e7f82903`. They reuse the
existing `manage.py create-session` routine and the same Course, ClassSchedule,
ClassSession and PIN hashing. No new attendance system, API route or schema exists.
Do not use the generic manage.py CLI with production .env defaults for this test.

## Start and inspect

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System
.\fyp-test.ps1 start --lan
.\fyp-test.ps1 status
.\fyp-test.ps1 session list
.\fyp-test.ps1 session list --class FYPATT01 --all
```

Normal list shows sessions open **now**. `--all` also shows closed, elapsed and
scheduled records, with IDs, class/group, times and attendance counts. Neither
listing exposes a PIN or stored PIN hash. Session commands first require the
identified isolated backend to be ready; they do not silently start another server.

## Create the next test session

Use the session list to identify any overlapping open session. If you have
finished it, close it explicitly before creating a new one:

```powershell
.\fyp-test.ps1 session close --id (Read-Host 'Existing session ID to close')
.\fyp-test.ps1 session create --class FYPATT01 --minutes 30
```

Creation prints the new **session_id**, start/expiry and generated six-digit
**pin**, once, only after its transaction commits. Save the PIN privately if
needed. It is not a CLI argument, written to a manifest, or logged by the wrapper;
only the existing digest is stored in ClassSession. The list cannot recover it.
If you lose it, close that test session and create another; do not edit hashes or
reset attendance. Earlier manually created PIN manifests are historical artifacts
and are not rewritten by these commands.

The default duration is 30 minutes if --minutes is omitted. You can instead choose
an absolute expiry (this is an alternative create command, not an extension):

```powershell
# Choose a future time on the current MYT date; replace this example as needed.
.\fyp-test.ps1 session create --class FYPATT01 --expires-at '2026-11-06T18:00:00+08:00'
```

Do not run both creation examples back-to-back without closing the first: their
windows overlap. Existing course and group data are required; the wrapper does
not auto-create an unknown class. If the course belongs to multiple groups:

```powershell
.\fyp-test.ps1 session create --class FYPATT01 --group-id 1 --minutes 45
```

Each creation uses the existing workflow to add a dated schedule/session for that
course/group; it never overwrites the earlier schedule, PIN or attendance. New
sessions use a different PIN from all existing sessions for the same group/day.
Concurrent creates for a class/group are serialized. Overlap is rejected for that
class/group regardless of PIN, including the shared boundary instant.

Expiry times use backend Asia/Kuala_Lumpur. Offset-bearing ISO timestamps are
converted to that timezone; an omitted offset means local MYT. Duration must be
1–1440 minutes and the end must be after now on the **same date**. Cross-midnight
sessions are rejected because existing attendance eligibility is date-bound.

## Close or expire safely

Use an ID from session list. These commands prompt for it so they can be copied
without assuming which auto-generated ID you received:

```powershell
.\fyp-test.ps1 session close --id (Read-Host 'Session ID to close')
.\fyp-test.ps1 session expire --id (Read-Host 'Session ID to expire now')
.\fyp-test.ps1 session list --all
```

`close` and `expire` both immediately set an active session's existing status to
closed. `expire` is an explicit immediate-expiry alias, not a rewrite of its
original end time. Existing timestamps, attendance and verification history remain
intact. Repeating the operation is safe (changed=false). A closed session cannot
be reopened through these commands; create a new dated session for a fresh test.

The existing attendance boundary re-reads the session under a lock and rejects
closed/expired sessions, including an in-progress verification. No PIN, network,
device or biometric bypass is added. Do not close a session while another student
is intentionally completing a test unless you want to test that rejection.

## Clear errors

| Error | Meaning / action |
|---|---|
| BACKEND_NOT_RUNNING | Run fyp-test.ps1 start --lan. |
| BACKEND_NOT_READY | Inspect fyp-test.ps1 status and isolated logs. No production fallback. |
| CLASS_NOT_FOUND | Use an existing course code, e.g. FYPATT01. |
| CLASS_HAS_NO_EXISTING_GROUP_SCHEDULE | Class/group provisioning is missing; this command does not invent it. |
| CLASS_GROUP_AMBIGUOUS | Choose --group-id from the existing class data. |
| CLASS_GROUP_NOT_FOUND | The chosen group is not assigned to that course. |
| SESSION_OVERLAP | Explicitly close the old session when finished, or wait for expiry. |
| INVALID_DURATION / INVALID_EXPIRY | Correct the minutes or ISO timestamp. |
| EXPIRY_MUST_BE_IN_FUTURE / SESSION_CANNOT_CROSS_MIDNIGHT | Choose a future expiry on the current MYT date. |
| SESSION_NOT_FOUND | Check the ID in session list --all. |

## Normal attendance testing

Keep the intended simulation CIDR enabled and use the actual LAN API URL. Log in
as FYPTEST001 on the registered tablet. Use the newly printed PIN, then complete
normal fresh device/network preflight and genuine face/liveness. The final writer
still requires a separate fresh signed proof and network check. The class window
is independent of the shorter **90-second verification attempt / up-to-60-second
device challenge** deadlines.

One record per student/session remains enforced. To repeat a successful test, use
a new session, never delete the successful record. Test unauthorized network
rejection before PASS for the same session; after success duplicate protection
takes precedence. Login/profile remain independent of attendance network policy.

Windows PowerShell 5 may block script files on this machine. Without changing
execution policy, the same commands can be run using the direct entry point:

```powershell
.\backend\venv\Scripts\python.exe -B backend\fyp_test.py session list
.\backend\venv\Scripts\python.exe -B backend\fyp_test.py session create --class FYPATT01 --minutes 30
```

All operator credentials stay in the existing private profile; no password, token,
face template, Keystore material or PIN hash is printed. No production DB or
original Samsung registration is involved. No commit or push is performed.
