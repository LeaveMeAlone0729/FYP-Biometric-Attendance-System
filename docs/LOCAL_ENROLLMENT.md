# Local FYP enrollment setup

The partner Local profile can explicitly accept account-bound FYP enrollment.
It does not claim institutional identity verification. Existing face templates
and registered device keys are preserved. No HTTP endpoint writes trust records.

Run commands from the repository root using the existing backend virtual environment.

## Enable once

Stop the Local server, then run:

```powershell
.\fyp-stop.ps1 -Mode Local
& .\backend\venv\Scripts\python.exe -B backend/local_enrollment.py enable --confirm LOCAL-FYP-UNVERIFIED
.\fyp-start.ps1 -Mode Local
```

The tool validates the existing pinned database identity before changing policy,
backs up the private configuration, preserves the database password and biometric
encryption key, and creates a separate private operator credential. It never
copies another operator's key. Backups remain under the protected Local profile's
`enrollment-checkpoints` directory. Repeating enable reuses the same credential.

## Accounts without a face template

An operator must create the student account through the existing offline account
provisioning workflow. Before its first face registration, provision that account:

```powershell
& .\backend\venv\Scripts\python.exe -B backend/local_enrollment.py provision --student STUDENT_ID --confirm LOCAL-FYP-UNVERIFIED
```

Alternatively, `provision --unenrolled` provisions existing active accounts that
have no face template. Their first successful face enrollment creates the normal
`ACCOUNT_BOUND_FYP` revision. Provisioning an already enrolled account does not
retroactively establish trust. Public account signup remains disabled by the
existing account-bound enrollment policy.

## Existing accounts with a face template

1. Start the operator watcher immediately before the account performs setup:

   ```powershell
   & .\backend\venv\Scripts\python.exe -B backend/local_enrollment.py record --student STUDENT_ID --watch --timeout 600 --confirm LOCAL-FYP-UNVERIFIED
   ```

2. On the new phone, cancel any old pending request, prepare a new device request,
   and complete genuine face recognition and liveness. Keep the app open.
3. The watcher records one fresh scan for that exact account. It checks the current
   template, authenticated login, candidate key proof, pending request, server
   completion evidence, and expiry. It records signed **UNVERIFIED Local FYP**
   account evidence; it does not activate a device or issue an operation grant.
4. After `LOCAL_FYP_ACCOUNT_RECORDED_UNVERIFIED`, cancel that setup request,
   prepare another new request, and complete another genuine scan. That new scan
   receives the normal short-lived authorization and the phone signs activation.

An exact unexpired reference can also be recorded using `--scan SCAN_REFERENCE`.
Expired scans, different accounts, reused scans, changed templates, and changed
keys are rejected. Importing audit events alone cannot establish enrollment trust.

Use `local_enrollment.py status` to inspect the non-secret policy state. Disabling
the Local device-management policy or losing its operator credential makes these
Local demo revisions unusable; preserve the private configuration and backups.
The policy is never enabled for the original Full environment by this tool.
