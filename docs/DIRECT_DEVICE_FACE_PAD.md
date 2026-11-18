# Direct face/PAD for device management

18 November 2026. Direct face/PAD code was deployed through the approved original-backend restart and signing-matched paired Xiaomi APK update. Deployment did not activate/revoke devices or change accounts, schema or keys. A real direct-face registration/replacement scan is still NOT TESTED unless separately confirmed by the tester.

## Scope and reused components

Only Slot 2 enrollment and replacement of Slot 1 or Slot 2 use this device-owned path. Backend reuses `context.bio.face_observation(image, guided=True)` from the partner biometric inference and the same `modules.biometrics.presentation.validate_scores` evaluator (existing ensemble mean threshold 0.95 and per-model floor 0.65, not new thresholds). No new face/PAD algorithm, head-pose engine or hand detector is introduced.

The existing device front-camera lifecycle, DeviceCameraPreview and face oval are retained. The attendance CameraScreen owns attendance challenges and its completion writer; it is intentionally not repurposed into a device-registration screen. No partner runtime module, shared API client, normal attendance head/gesture flow or final writer changes.

## Protocol and evidence

- Candidate key preparation/proof, enrollment eligibility, login binding and target slot checks remain required.
- Create `/api/v1/device-approvals` with pending_registration_id and verification_mode=`DIRECT_FACE_PAD_V1`. Missing/old protocol is rejected; no legacy gesture fallback.
- Server records DIRECT_FACE_PAD_SESSION_CREATED. Old sessions without this marker cannot be relabelled direct/PAD verified. Cancel expired/old pending requests through the existing UI and prepare a fresh operation with the retained key.
- First `/face` frame performs genuine face recognition AND PAD. Then three fresh consecutive frames perform the same face/PAD checks automatically. No finger count or head-action sequence is issued.
- Existing storage stage `LIVENESS` and `/liveness/frame` URI are retained only as compatibility names for passive face/PAD continuation. No database columns, tables or migration changes. `fingers` is always null.
- Any identity mismatch, missing/invalid/unavailable PAD, expired login/pending/scan, replayed decoded frame or changed candidate/operation/template fails closed or resets the consecutive quality checks. Three accepted continuation frames are audited separately. No photos/templates/scores are added to logs.
- `anti_spoof_verified` is true only after genuine completion; the legacy `liveness_verified` response field denotes passive PAD completion here, not an interactive gesture/head proof. UI says Anti-spoofing, never fabricated gesture/liveness PASS.
- Raw completion remains COMPLETED_UNTRUSTED with trusted/consumable/activation_eligible false. This raw result cannot activate a device or authorize attendance. Existing eligible pre-scan provenance plus the normal short-lived single-use operation grant and fresh candidate activation signature are still necessary.
- Replacement atomically revokes only the selected old registration, preserves the other slot and enforces the existing historical-key/two-device restrictions. No database status edits or replacement bypass.

## Provenance limitations

This change does not make a partner database's DEMO001 eligible merely because the tables match or a face matches. School-provisioned ACCOUNT_BOUND_FYP provenance must be established through its supported first enrollment under the explicit FYP policy. Legacy/unknown records need the existing separately authorized local-demo account-verification procedure or legitimate institution evidence. LOCAL FYP assurance remains UNVERIFIED and local-only; no evidence is copied between databases.

Passive PAD is deliberately the requested substitute for device interactive challenges. It is not cryptographic camera attestation, certified spoof resistance or institution identity proof. Automated photo/screen/video fixture rejection tests verify integration and fail-closed behavior, not real-camera attack accuracy. Physically retest the real phone and intended spoof negatives after separately approved deployment. Attendance's stronger interactive workflow remains unchanged.

## Deployment procedure — approval required for each future deployment

1. Confirm tests/build and the existing paired trust identity/signing certificate.
2. Approve restarting only the identity-verified backend using its supported original_fyp launcher, preserving --lan --local-demo-slot2 and diagnostic OFF. Do not restart MariaDB or create migrations.
3. Approve an in-place signing-matched paired APK update on an explicitly named phone. Never uninstall, clear app data or regenerate its Keystore.
4. New APK and backend must be deployed together for new device scans. An old client is rejected with DIRECT_FACE_SCAN_REQUIRED; an old scan with BIOMETRIC_PROTOCOL_CHANGED; an incompatible backend fails the new adapter's direct protocol check. Existing ACTIVE devices still use their unchanged keys/verification endpoints.
5. On the candidate: choose Slot 2 enrollment if empty, otherwise Replace the exact slot; prepare/prove retained candidate key; Start facial verification; keep face centered while recognition/PAD progress completes. No hands, blinks or head turns requested. Normal secure activation and My Device refresh follow.
6. Confirm the replacement signature, old-key rejection, unaffected slot and unchanged attendance. Separately test normal attendance to confirm its PIN/network/device/head/gesture flow remains intact.

For Partner Local, use the partner's own backend/profile/database/public trust and signing configuration. Do not install a Full-mode paired APK expecting it to trust a different Local server, or copy Full private TLS/operator credentials.

## Rollback

Source-before snapshots and test/build evidence are outside Git in the current direct-face-pad checkpoint. The approved backend/APK deployment has occurred; no live device/account data was changed by that deployment. Any rollback requires a reviewed backend/APK pair with matching signing identity; never restore device rows, revive consumed grants or change provenance to fix a protocol mismatch. Do not downgrade over pending in-flight scans; cancel/wait for expiry and start a new genuine operation.

Final actual test/build/signing results are in the checkpoint REPORT.md. Physical direct-device scanning is NOT TESTED until user confirmation.
