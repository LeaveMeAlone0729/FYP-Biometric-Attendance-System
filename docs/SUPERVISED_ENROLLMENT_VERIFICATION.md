# Supervised identity verification for legacy Slot 2 enrollment

This handoff records a new institutional verification of an existing legacy face
template. An authorized institutional verifier checks the person's identity
against the institution record and witnesses a fresh Slot 2 face and liveness
scan on the candidate device. The verifier signs the exact server evidence on
their own workstation. The student app displays the scan reference for the
handoff.

## Prepare the verifier

The operator must independently confirm the verifier's institutional authority
and the SHA-256 fingerprint of their Ed25519 public PEM through an authenticated
institutional channel. Place that public PEM at this fixed location in the
existing private original-environment directory:

```text
%USERPROFILE%\FYP-Original-Local\institution-enrollment-verifier.pem
```

The verifier retains the corresponding private key. The original environment
has no authorized verifier key provisioned by this change. An enrollment
attestation relies on the verifier's independent identity check and signature.

## Complete the handoff

1. With the verifier present, sign in as `DEMO001` on tablet `7732690b`. In
   **My Device**, choose **Prepare this second device** and start a fresh pending
   request. Complete key proof, then open facial recognition and liveness.
   Give the verifier the **Scan reference** shown on the completed screen.
2. On the original FYP laptop, run the following from the repository root. Use
   the reference from the witnessed scan and the verifier's institutional case
   reference. Use an opaque case ID, such as the case identifier in the faculty
   record. The export and recording must both occur within ten minutes of scan
   completion.

   ```powershell
   $scan = Read-Host 'Supervised scan reference'
   $case = Read-Host 'Institutional case ID'
   $evidence = Join-Path $env:USERPROFILE "FYP-Original-Local\enrollment-$scan.json"
   .\backend\venv\Scripts\python.exe .\backend\verify_enrollment_identity.py prepare --student DEMO001 --scan $scan --case $case --out $evidence
   ```

3. Send the JSON to the authorized verifier using the institution's approved
   channel. They review the signed statement, account, reference, case ID and
   completion time against their witnessed event and sign the original file
   bytes. For example, on their workstation with OpenSSL 3:

   ```text
   openssl pkeyutl -sign -rawin -inkey verifier-private.pem -in enrollment.json -out enrollment.sig
   ```

4. Save the returned raw signature next to the evidence file as
   `enrollment-<scan-reference>.json.sig`, then record it on the original laptop:

   ```powershell
   .\backend\venv\Scripts\python.exe .\backend\verify_enrollment_identity.py record --evidence $evidence --signature "$evidence.sig"
   ```

   Retain both signed evidence files with the institutional case record. The
   command verifies the pinned signature, the exact current encrypted-template
   hash, the completed server scan, its candidate-key binding and freshness. It
   inserts one current `external_verified` / `INSTITUTION_VERIFIED` revision and
   an audit event. The timestamp is the time the verifier's statement is recorded.

5. On the tablet, return to **My Device** and open **Prepare this second device**.
   Cancel the earlier pending request if it is still open. Start a fresh request,
   prove the tablet key and complete face and liveness again. The server captures
   the new revision at scan creation. After completion it can issue the usual
   short-lived activation grant, then require the tablet's activation signature.
   Refresh **My Device** to confirm both active slots.

The handoff works with the original database identity guard and the existing
enrollment and audit tables. Existing revision history requires institutional
recovery. The earlier scan provides evidence to the verifier. The later scan
and key proof are what the activation service evaluates for Slot 2.

## Local FYP demo on the original server

The isolated port 3322 test profile uses `FYP_ACCOUNT_BOUND_ENROLLMENT=true`.
Its school-provisioned FYPTEST001 acquired an `ACCOUNT_BOUND_FYP` revision when
it first enrolled. The original port 3306 profile has that policy disabled.
DEMO001's existing legacy template has no such revision. Both profiles run the
same device approval checks for their respective enrollment policy.

For a developer-operated demonstration on the original database, initialize
the private demo operator credential once and start the original backend with
the explicit demo option after closing the previous backend listener:

```powershell
.\backend\venv\Scripts\python.exe .\backend\verify_enrollment_identity.py init-demo
.\backend\venv\Scripts\python.exe .\backend\original_fyp.py serve-backend --lan --local-demo-slot2
```

1. As DEMO001 on the tablet, open **My Device → Prepare this second device**.
   Cancel an older pending request if needed. Prepare the tablet key and run
   face recognition and liveness. The completion screen displays **LOCAL DEMO
   EVIDENCE REQUIRED** and a **Scan reference**.
2. From the original laptop's local operator terminal, record that exact scan
   reference within ten minutes of completion:

   ```powershell
   $scan = Read-Host 'LOCAL DEMO scan reference'
   .\backend\venv\Scripts\python.exe .\backend\verify_enrollment_identity.py record-demo --scan $scan
   ```

3. Start a fresh Slot 2 request using the same installed app and tablet key.
   Complete face recognition and liveness again. The normal activation flow
   uses a fresh single-use server grant and the tablet's challenge signature.
   Return to **My Device** to check the resulting active device.

The operator command records a current, authenticated `LOCAL_FYP_DEMO`
evidence reference and audit event. The revision retains `UNVERIFIED`
institutional assurance. It binds to the exact enrolled template and tablet
key. The demo profile accepts this evidence only for DEMO001 Slot 2 enrollment.
The resulting registration carries a `[LOCAL FYP DEMO]` label. Its key is
accepted only while the original backend runs with that demo profile and
credential. PIN, network, face, liveness and attendance device signatures
continue through the normal checks.
