# Disposable startup identity fix — 6 November 2026

## Findings

The old `prepare_manual_android_test.py:verified_pid` stored only integer PIDs
and required an environment-path substring in CommandLine. It did not record
process creation time or executable identity, distinguish stale/recycled PIDs,
or reconcile the role's actual listening process. Its slash replacement also
doubled forward slashes into two backslashes, which could falsely reject an
equivalent Windows path. That false-rejection pattern is reproduced in tests.

At investigation, processes.json referred to backend PID **92552**, which no
longer existed. No process listened on 8002. Database PID 97676 and phpMyAdmin
PID 108364 were still the correctly configured isolated services. The historical
identity of PID 92552 at the moment of the user's mismatch cannot now be proven;
PID reuse is tested as a failure mode, not claimed as a witnessed historical fact.
A controlled pre-fix start succeeded, confirming the problem was intermittent.

The two existing port-8000 uvicorn entries are a Windows venv redirector parent
PID **105108** and its base-Python child **85560**, with the latter owning the
listener. They are not two independently bound 8000 listeners. Both processes
were preserved; PID, creation time, executable and command line matched before
and after all lifecycle tests. Production SQL was never queried.

## Fix and preserved safeguards

- `backend/disposable_processes.py` validates the exact role-specific executable
  and parsed arguments, normalizing Windows path spelling without substring
  trust. Backend, database and PHP each have different expected commands.
- Process state now stores PID, UTC creation time and executable, written with
  atomic replacement. Valid legacy integer entries are migrated only after live
  ownership validation. Python venv parents and actual listener children are
  recognized using their exact script/profile bindings.
- A stale or recycled PID is never terminated. If its role port is free, its
  stale metadata is retired into process-state-history.jsonl. If that port is
  occupied, only a process with the exact expected identity may be adopted.
  Foreign listeners, unreadable identities and failed inspection remain errors.
  An unrelated command merely containing the test directory is not ownership.
- Startup validates **all role owners before control actions**, starts MariaDB
  first, checks actual private datadir/version/port, then waits for API and PHP
  readiness even when an existing process was found. Native ini validation and
  the pre-connect production-port guard remain intact.
- Shutdown signals only the owned backend's stop file and waits for its original
  process lifetime to end. PHP termination uses a verified process handle and
  creation time rather than taskkill on a bare PID. MariaDB receives normal
  authenticated SHUTDOWN only after private identity verification. Entries are
  cleared after confirmed exits.
- Start/stop CLI operations use a nonblocking environment lock; concurrent
  lifecycle commands report DISPOSABLE_LIFECYCLE_BUSY. Failed cleanup does not
  hide the original startup exception. No process on 8000 is selected for control.
- `status` reports JSON STOPPED/BACKEND_NOT_RUNNING (exit 1) when absent,
  UNAVAILABLE/BACKEND_NOT_READY when an owned process is not ready, and READY
  only after its isolation endpoint succeeds. It no longer reports an unexplained
  ConnectionError for a stopped backend.

Changed runtime files: `backend/prepare_manual_android_test.py`,
`backend/fyp_test.py`, new `backend/disposable_processes.py`.
Added tests: `backend/tests/test_disposable_processes.py`.
No Flutter, biometric, attendance, student, policy or Android-key logic changed.

## Shell discovery

Windows PowerShell **5** on this laptop rejects .ps1 files because script
execution is disabled. The initial subprocess test using that host failed before
the wrapper ran. The existing permitted PowerShell **7** host ran the wrapper
successfully. No execution policy, UAC setting or administrator privilege was
changed. Use PowerShell 7, or call the same Python entry point directly in your
existing terminal; do not add ExecutionPolicy Bypass.

## Actual validation

- Full backend regression: **267 passed, 10 skipped**, 277 discovered.
- Final targeted process-identity suite: **12 passed** (includes one added
  unreadable-identity test after the full suite had already loaded).
- Actual cold start plus **two further cold restart cycles** passed.
- Idempotent warm `start`, ready `status`, complete `stop`, stopped `status`,
  and `start --lan` passed through the actual PowerShell 7 wrapper.
- The two original 8000 processes were identical before/after.
- Student/template/provenance/device/attendance/network-policy row hashes and
  the private profile/key/credentials hash were unchanged across the cycles.
- Final state: isolated API 127.0.0.1 and 192.168.0.162:8002; database loopback
  3322; phpMyAdmin loopback 8082. No new firewall change or public exposure.

Evidence: `outputs/startup-identity-20261106/lifecycle-results.json`,
`backend-results.json`, `process-tests.log`. The full/backend test totals overlap;
do not count them as separate manual cases. No physical app installation or
real attendance test was performed during this startup fix.

Pre-edit source/state/process evidence is retained at
`C:\FYP\Work-Backups\startup-identity-20261106`. Do not restore an old PID file
as a running-state recovery method: those PIDs can now belong to other processes.

## Supervisor network PASS/FAIL demonstration

In PowerShell **7**, from the repository root:

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System
.\fyp-test.ps1 start --lan
.\fyp-test.ps1 status
.\fyp-test.ps1 policy list

# PASS simulation: this is HOME TESTING, not university authorization.
.\fyp-test.ps1 policy set --cidr 192.168.0.0/24 --simulation
# On the tablet: Profile -> Network Verification -> Check again.
# Direct LAN source 192.168.0.94 should match and PASS.

# FAIL simulation: exclude the tablet's actual source.
.\fyp-test.ps1 policy set --cidr 192.0.2.0/24 --simulation
# Check again: FAIL / NETWORK_NOT_AUTHORIZED. Login/profile still work.

# No configured enabled simulation network:
.\fyp-test.ps1 policy disable
# Check again: FAIL / NO_ENABLED_NETWORK_POLICY, if no other policy is enabled.

.\fyp-test.ps1 stop
.\fyp-test.ps1 status   # Expected STOPPED, exit code 1.
.\fyp-test.ps1 start --lan
.\fyp-test.ps1 status
```

The 192.168 addresses are the observed current LAN, not source-code constants.
On another network use the URL printed by start --lan and explicitly choose its
intended simulation CIDR. Review all rows from policy list: other enabled policies
can still match even when fyp-simulation is disabled. Localhost/ADB reverse cannot
produce a network PASS. These network diagnostics never insert attendance.
The final writer still requires PIN, genuine face/liveness, an ACTIVE device's
fresh single-use signature, and its own fresh network check.

If the terminal is Windows PowerShell 5, substitute the direct entry point:

```powershell
.\backend\venv\Scripts\python.exe -B backend\fyp_test.py start --lan
.\backend\venv\Scripts\python.exe -B backend\fyp_test.py status
.\backend\venv\Scripts\python.exe -B backend\fyp_test.py policy set --cidr 192.168.0.0/24 --simulation
```

The same arguments (policy list/disable, stop) work with that Python entry point.
Do not run the original port-8000 launcher, reset the database, manually kill PID
92552 or delete arbitrary process state to make a demo pass.
