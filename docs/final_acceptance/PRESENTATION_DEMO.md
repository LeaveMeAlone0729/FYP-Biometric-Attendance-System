# Thursday demonstration runbook

Presentation: 19 November 2026. Prefer the already-proven approved Private Wi-Fi; do not depend on untested school multicast. Keep laptop awake, powered, Bluetooth ON and both devices on the approved access point.

## Before the presentation

- Preserve installed Xiaomi APK/app data/Keystore. Existing rollback APK and paired deployment evidence: `C:\FYP\Deployment-Checkpoints\secure-lan-20261117-004116`.
- Verify assigned credentials privately and the legitimate existing class/session/classroom. Normal attendance needs an OPEN eligible session, current PIN, enabled CIDR + classroom Wi-Fi policy, active registered key and genuine face/liveness.
- BLE is shadow-only; Network + BLE diagnostic feature remains OFF. Do not change security policies at the lectern.
- Do not rerun provisioning/migrations or pair a new TLS identity. Do not use ADB reverse for attendance.

## Supported commands (manual operations; not executed by this report)

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System
.\fyp-start.ps1
# Only if an approved new APK installation is actually necessary:
.\fyp-install.ps1 -Serial 7732690b
# After the demonstration, stop verified FYP-owned processes only:
.\fyp-stop.ps1
```

Startup reuses owned healthy components and checks identity/readiness. Do not run generic uvicorn or create duplicate listeners. The original backend command is `original_fyp.py serve-backend --lan --local-demo-slot2`; management is `original_fyp.py serve-panel`. The workflow does not restart MariaDB. Its stop preserves MariaDB and the separately managed cloudflared Windows service; it is **not** a complete Cloudflare-service shutdown command.

Partner commands, after their OWN documented setup:

```powershell
.\fyp-start.ps1 -Mode Local
.\fyp-install.ps1 -Mode Local -Serial THEIR_DEVICE_SERIAL
.\fyp-stop.ps1 -Mode Local
```

Full and Local contend for the same application ports; never start Local over a running Full deployment. Follow `docs/PARTNER_LOCAL_MODE.md` and `docs/SECURE_LAN_DISCOVERY.md` for an independently provisioned Local profile and optional paired identity. Older wording that says discovery was not deployed describes the implementation snapshot, not today's Full deployment.

## Live URLs

- Admin: http://127.0.0.1:8003/sessions; `/networks`, `/wifi`, `/ble`.
- General APIs: https://api.bioattsys.xyz (exact allowlist, not a browser landing website).
- Current home backend: http://192.168.0.162:8000; classroom app transport is **pinned HTTPS 8005**, automatically discovered.
- IPs are observations, not permanent settings. After an IP change use Refresh/manual pinned fallback; no APK rebuild for the same paired identity.

## Five-minute core demonstration

1. Show admin login and existing sessions/classroom policies without revealing credentials. Create a legitimate session only when intending a real attendance test; display its new PIN privately. PIN regeneration invalidates the old PIN.
2. Xiaomi login → profile/classes/history. Explain Cloudflare general API vs direct classroom route.
3. Network Verification → paired server → authorized source-IP policy and classroom Wi-Fi result. Explain that SSID/BSSID are signed client observations, not physical-presence proof.
4. Normal Take Attendance: PIN, early preflight, genuine partner face/actions/liveness, fresh key signature and final checks. Show accepted attendance/history; duplicate rejects. This is a real authorized write, not a diagnostic simulation.
5. Show an unauthorized-network rejection before the camera, if a known reachable test path has already been proven. A timeout is an availability failure; do not describe it as verified CIDR rejection.
6. Optional: show BLE observation/shadow status and admin audit. Explain it cannot authorize or independently reject attendance. Stop here if time is short.

## Troubleshooting and rollback checkpoints

- Public APIs down: inspect gateway 8004/cloudflared; do not route sensitive paths through Cloudflare. Local classroom transport cannot replace Full public login automatically.
- Discovery fails: verify same Wi-Fi/subnet and network category, then try CURRENT laptop IP using the existing pinned manual field. TLS failure must stop capture; never accept a new certificate or remove pinning.
- Public school Wi-Fi fails: use the separately reviewed exact-peer lease procedure only after approval. Client isolation may need school network staff. Safe fallback is the proven approved Private demonstration network, not broad firewall rules or attendance-policy bypass.
- Biometric failure: lighting/framing and genuine retry using a fresh PIN attempt; do not disable checks or replace the partner algorithm.
- Expired session/duplicate: use legitimate admin session management; preserve existing history and do not delete attendance to repeat a PASS.
- Do not downgrade a paired APK or disable discovery automatically. Existing backend/firewall rollback scripts and saved APK live in the deployment checkpoint; review their effects and obtain approval first. Old shared-firewall rollback restores broader Python permissions and is not routine recovery.
- Before any service stop/restart, recheck live PID, command line, creation time and ownership; stale PID values in reports are never commands.

## Final Public-hotspot result — 17 November, 23:20 MYT

**PASS:** real Xiaomi automatically discovered the paired server, manual pinned HTTPS connected, and the unauthorized hotspot returned NETWORK_NOT_AUTHORIZED while Windows classified the hotspot as Public. User supplied these phone observations. The temporary lease was stopped early at **23:19:55 MYT**; host verification confirms zero FYP-Public rules, all **8 baseline rule hashes unchanged**, and hotspot category restored to Private. Backend PID 45804, admin 50604 and gateway 56012 remain unchanged. No APK reinstall or service restart. The earlier ACTIVE/pending descriptions are superseded by this result. Scheduled SYSTEM cleanup rehearsal passed; a full 30-minute wall-clock expiry was not waited out. School connectivity remains NOT TESTED.

Latest evidence: `C:\FYP\PublicLAN-Tests\hotspot-20261117-231435\REPORT.md`. For school, use the corrected helpers/preparation procedure and obtain separate site activation approval; never use broad /16 firewall access.
