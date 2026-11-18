# Slot 2 first-preparation connection and device-label fix

18 November 2026, SH. **Approved deployment completed on 18 November. Label-only update committed, original backend restarted, signing-matched paired APK installed in place on Xiaomi. Fresh phone verification and new-candidate first-preparation confirmation are recorded separately below.**

## Root causes and evidence

### Device preparation connection

Both standalone Network Verification and device preparation use ApiClient.instance and its paired HTTPS 8005 transport. There is no separate hardcoded HTTP attendance endpoint in PendingDeviceService. Existing _requestUri already awaited ensureReady, so this was not an initial request deliberately sent before TLS verification.

However, PendingDeviceService.prepare first called listDevices through a possibly stale cached paired transport. The corrected attendance flow refreshed the paired transport at its explicit new-PIN boundary, but device preparation had no equivalent boundary. A laptop-only IP change could leave the phone's transport cached despite a previous Network Verification PASS. The new regression reproduces the exact original message before the fix: Network Verification on address A, server moves to B, first Prepare attempts cached A and fails with the attendance-specific classroom-server message.

The prior separately corrected SecureLanDiscovery.send race also affected registration: a delayed failure from an old request could invalidate a newer transport. That generation/client guard is retained and exercised in the complete Flutter suite. The current installed APK was preserved and compared with the newly built APK; the explicit new prepareDeviceOperation entry point is absent from the installed build and present in the new build.

No timestamped live packet record establishes that every historical first-attempt error had this cause; physical confirmation remains required. Genuine server unavailability must still reject. Existing standalone PASS does not grant enrollment authorization or prove current transport availability.

### Name prefix

backend/modules/devices/activation_service.py added [LOCAL FYP DEMO] to pending.device_name and stored the prefixed/truncated value in registered_devices.device_name. MyDeviceScreen displays that stored value without adding the prefix. Read-only original SQL confirms current Slot 2 name [LOCAL FYP DEMO] sh tablet. Evidence metadata is separate: local-demo device ID, enrollment revision, assurance, approval and audit codes. There is no need to put assurance in a user-entered label.

## Minimal changes

- frontend/lib/services/api_client.dart: explicit prepareDeviceOperation invokes fresh discovery/TLS identity checking without sending a registration request; device-management transport errors use device-registration wording rather than attendance wording. Error codes/fail-closed behavior retained.
- frontend/lib/modules/devices/services/pending_device_service.dart: fresh paired readiness before list/key preparation at an explicit user action; check login revision afterward. Bounded native key operations report DEVICE_KEY_TIMEOUT. Retained key lookup/explicit creation and challenge signing are not repeated automatically.
- frontend/test/secure_lan_discovery_test.dart: reproduces stale first preparation; expects fresh paired server and exactly one candidate creation/signature/proof; no public fallback; unavailable discovery blocks before key creation.
- frontend/test/pending_device_test.dart: actual native signing timeout rejects with no proof submission/replay. Existing lost-response recovery remains read-only status lookup.
- backend/modules/devices/activation_service.py: store pending.device_name directly. Existing whitespace validation/normalization stays unchanged; no demo prefix or prefix-driven truncation is added.
- backend/tests/test_device_management.py: exact submitted name, local-demo registration identity and UNVERIFIED evidence remain enforced; disabling the local credential still denies this device.

No face/liveness algorithm, signature, enrollment/replacement trust policy, proof expiry, replay, attendance authorization, TLS/firewall/Cloudflare or database schema change.

## Final tests

- Full Flutter: **340 PASS / 1 SKIPPED**; prepare-name-flutter-final.log.
- Relevant backend enrollment/activation/replacement: **68 PASS / 3 SKIPPED**; prepare-name-backend.log. Synthetic/SQLite fixtures, live DB connections blocked.
- Flutter analyze: clean; prepare-name-analyze.log.
- Paired Full debug APK build: PASS; prepare-name-build.log. Existing Android toolchain future-support warnings only.
- Before-fix first-preparation regression failed with the exact reported error; prepare-before.log.
- Existing old-request generation, unavailability, no-public-fallback, lost-proof-response/no-replay and attendance regressions pass in the full Flutter suite.

Logs reside at C:\FYP\Device-Checkpoints\slot2-reset-20261118-001426. APK signing review and immutable paired-reviewed.apk reside in the sibling slot2-preparation-ui-20261118-002857 checkpoint. The currently installed APK was pulled there read-only as installed-before.apk for rollback review. Both APKs verify with certificate SHA-256 43be2174f4596c3a47b479bdefacae45c16c765aec6bcbe652569a6508c1284b. Paired public trust anchor exists in the reviewed build. No APK was installed.

## Exact required live actions — awaiting approval

1. **Label-only transaction:** original attendance_proposal_xampp:3306; exact DEMO001 ACTIVE Slot 2 ID/key and expected old name must match the saved label-change-plan.json. Back up the current row, lock it, change ONLY registered_devices.device_name to sh tablet, verify all other fields/Slot 1/attendance/evidence/approval hashes unchanged, commit. No registration/key/status change. Plan is prepared; NOT EXECUTED.
2. **Backend-only scoped restart:** reverify PID 45804 (last observed), original_fyp.py serve-backend --lan --local-demo-slot2 and original database identity; stop/restart only that verified backend to load the future-registration naming fix. Same process owns HTTP 8000 and HTTPS 8005/mDNS. Preserve identity/TLS files and diagnostic OFF. Do not restart MariaDB, admin, gateway, cloudflared or BLE. Recheck actual PID at execution time; report values are not termination authority. NOT EXECUTED.
3. **In-place Xiaomi-only update:** verify serial 7732690b, installed package/signing identity and reviewed artifact checksum again; adb -s 7732690b install -r the reviewed paired APK. No uninstall/data clear/Keystore change or ADB reverse. Verify installed artifact/package identity afterward. NOT EXECUTED.

Original Slot 1 and Slot 2 remain ACTIVE; existing name still has the prefix until action 1 is approved. No records were updated in this task. Read-only device-row snapshot and protected table hashes are saved in the private UI-fix checkpoint. No commit/push.

## Physical retest

- After approved deployment: Xiaomi My Device → Refresh; expect sh tablet, ACTIVE and fresh signed-device PASS. Face/liveness and internal demo assurance remain unchanged.
- With a genuinely unregistered candidate/approved test reset only, Network Verification PASS → enter name → press Prepare ONCE. Expect fresh paired readiness and KEY_PROVEN without first-attempt transport failure. Then genuine face/liveness/activation if eligible. **Current Xiaomi is already registered: KEY_ALREADY_REGISTERED is the correct result for attempting to enroll it again; do not reset it automatically just to rerun preparation.**
- First-preparation physical acceptance therefore requires a separately approved reset/candidate. This task did not reuse the previous destructive approval for a new reset.
- Test genuinely unavailable backend: preparation fails closed, no key proof accepted, no public fallback and no automatic signed replay.
- If IP-change testing is needed, use only the existing approved network/firewall conditions; manual fallback still requires the same pinned trust. Do not reopen a Public hotspot lease or change attendance policy without approval.

## Approved deployment — 18 November, 00:39 MYT

The three approved live operations are complete; the AWAITING APPROVAL / NOT EXECUTED plan descriptions above record the pre-deployment review and are superseded by this dated result.

- Label transaction changed ONLY registered_devices.device_name to **sh tablet** for the exact DEMO001 ACTIVE Slot 2. All other row fields (including device ID, SPKI/fingerprint and status), Samsung/other device rows, students/face data, enrollment revisions, biometric authorizations, trust audit and all 8 attendance rows matched before/after hashes. Backups and compare evidence are in the private UI-fix checkpoint.
- Only verified backend PID **45804** was stopped using the existing ownership/creation-time guard. Its old wrapper had already exited. Supported original_fyp.py serve-backend --lan --local-demo-slot2 restarted successfully under listener PID **31420** on HTTP 8000 and HTTPS 8005. Owned-process state updated through existing workflow helpers. Private TLS key/certificate/public anchor hashes unchanged. Diagnostic OFF.
- MariaDB PID **54372**, admin PID **50604** and gateway PID **56012** remained unchanged. No restart of MariaDB/admin/gateway/Cloudflare/BLE. Localhost and LAN config 200, admin login 200, local gateway/public config 200, public attendance 404, pinned TLS verification PASS. Host mDNS re-advertisement checked separately; phone discovery is still a physical test.
- Xiaomi **7732690b**, model 2410CRP4CG, owner user 0: fresh installed-APK backup/signature comparison, then **adb install -r** only. Package UID **10466 → 10466**. Installed APK SHA-256 matches reviewed **34d401d1c75c0481816d085414cfd79a0b26743b7d37e6bc035fc4e98b5e1255**. No uninstall/data clear/private-key access or ADB reverse.
- Installed app may require normal sign-in because replacement of a running APK ends its in-memory login session. This is not clearing application data or resetting its Keystore. User was asked to sign in privately and open My Device → Refresh. Fresh post-update DEVICE_VERIFIED / visible name confirmation was still PENDING at this check; older 00:17 verification records are not counted as post-deployment PASS.

Private deployment evidence: C:\FYP\Device-Checkpoints\slot2-preparation-ui-20261118-002857 (label-before-apply.json/manifest, label-update-result.json, backend-restart-result.json, installation-result.json, post-deployment-checks.json). No reset, replacement, policy or schema change. No commit/push.

## Physical post-update result — 18 November

User confirmed My Device displays the corrected name and verification succeeds. Original database independently records Slot 2 **sh tablet / ACTIVE / DEVICE_VERIFIED PASS at 00:43:49 MYT**, after deployment. Fresh post-update verification is now PASS. Future-name code uses pending.device_name for all accounts, both Slot 2 enrollment and replacement; no automatic [LOCAL FYP DEMO] name concatenation remains. Internal LOCAL_FYP_DEMO_SLOT2_ACTIVATED/evidence labeling remains unchanged. New-candidate first preparation still requires an eligible separate test; no reset or account/device change was performed for this confirmation.
