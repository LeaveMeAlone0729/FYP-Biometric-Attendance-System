# Remaining physical acceptance

17 November 2026. Never mark a phone test PASS until observed and recorded. Current fresh ADB listing has no device. No APK was installed during this acceptance run.

## Fastest safe sequence

1. Keep the existing working paired APK and private trust identity. Connect Xiaomi **7732690b** over USB, unlock and accept debugging. Check `adb devices -l`; do not select Samsung or reinstall either app.
2. On known approved home Private Wi-Fi, open Network Verification → Classroom connection → Refresh. Expect automatic paired server and HTTPS 8005. Record laptop/tablet addresses, time and screenshot; do not capture bearer tokens or passwords.
3. Separately exercise manual fallback: enter the CURRENT laptop Wi-Fi IPv4 in the existing paired-server manual field. Expect certificate, server ID/mode/database pin verification; a random other machine must not be accepted. Manual IP does not authorize a network.
4. Login, profile, classes and history; logout then login again. Use assigned credentials privately. Full general APIs should use Cloudflare. Account state survives a Wi-Fi/mobile switch; interrupted signed operations need a fresh attempt.
5. Student selects a legitimate, eligible OPEN class/session and obtains its PIN from the authenticated localhost admin. Confirm exact classroom spelling and approved existing access point. Do not add/rename policies to make a test pass.
6. Normal attendance: PIN → fresh device/network/Wi-Fi preflight → partner face/actions/liveness → fresh final proof → one recorded attendance. **This deliberately writes a real attendance record and needs explicit permission before an agent executes it.** User may perform their intended demonstration with a legitimate session. Compare history and admin count. Duplicate must reject without a second row.
7. For an unauthorized network, expect network FAIL before camera; an unreachable backend is an unavailable connection, not proof of NETWORK_NOT_AUTHORIZED. Never use ADB reverse as attendance network evidence.

## Public hotspot: still NOT TESTED

The last helper stopped before mutation: `SITE_CHANGED_NO_RULES:Name`. Laptop was back on home Wi-Fi. No active 30-minute lease or real expiry rehearsal is established by that attempt.

- Connect laptop and Xiaomi to the **same trusted Samsung hotspot**, USB connected. Reply `hotspot ready`; leave the Windows category unchanged until fresh identity/IP checks.
- Re-verify SSID/BSSID, actual laptop/tablet IPs, subnet, backend executable/PID/creation and original DB identity. Old hotspot IPs must not be reused blindly.
- Only after a reviewed fresh request: normal UAC/admin launch of the existing `Start-PublicHotspotTest.ps1`. It must first prove scheduled cleanup, protected task files, fixed 30-minute deadline and watcher heartbeat before changing the verified hotspot to Public or enabling exceptions.
- Only Public TCP 8005 and UDP 5353, exact peer/executable/Wi-Fi/local addresses; no Public TCP 8000. Watcher removes exceptions on network/backend identity change.
- Test automatic discovery, then manual pinned TLS separately; record both outcomes. If manual works but mDNS fails, multicast is the likely remaining transport limitation, not permission to weaken TLS.
- Run authenticated Network Verification. Reachable unauthorized hotspot must return NETWORK_NOT_AUTHORIZED. Do not interpret timeout as policy rejection.
- Stop early with the site's `Stop-PublicHotspotTest.ps1`, or allow expiry. Confirm PUBLIC_LEASE_CLEANED, both owned rules absent/disabled and no lease task remaining. Confirm no unrelated rules changed. Record real deadline/cleanup evidence.

## School Public Wi-Fi: NOT TESTED; separate site approval required

Backend CIDR **172.22.0.0/16 is already configured**; do not edit it. School multicast/client isolation and VLAN routing are unproven. At school verify the real network identity and both IPs, prepare exact-peer temporary rules, and request approval before activation. Never use the whole /16 as a firewall remote allowance or automatically mark school Wi-Fi Private.

Read the existing operator procedure:
`C:\FYP\PublicLAN-Tests\hotspot-20261117-201139\SCHOOL-PROCEDURE.md`.
In Administrator PowerShell (preparation only):

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System
.\backend\venv\Scripts\python.exe 'C:\FYP\PublicLAN-Tests\hotspot-20261117-201139\Prepare-SchoolSite.py' --expected-ssid 'ACTUAL_APPROVED_SCHOOL_SSID' --serial 7732690b
```

Review the NEW folder and actual exact peers. After separate approval, use that folder's `Start-PublicHotspotTest.ps1 -ApprovedSchoolSite`; stop using its `Stop-PublicHotspotTest.ps1`. It must retain Public category, fixed expiry and network-change cleanup. Different subnets may be intentionally rejected by the app; do not remove the subnet/TLS guard. If school client isolation blocks direct HTTPS, ask network staff for an approved reachable network or demonstrate on the proven Private test network. Cloudflare is not an attendance fallback.

## BLE shadow and partner phone tests

Existing user-reported physical results: correct beacon PASS, stopped/wrong UUID beacon-not-found, Bluetooth-off unavailable, Wi-Fi mismatch rejected in temporary diagnostic mode. Mode is now OFF. For normal attendance shadow, compare Flutter status with admin `/ble` attempt/reason/time; BLE cannot grant or veto attendance. No pairing required; RSSI alone does not prove presence.

Remaining: fresh full normal attendance with current partner biometric code, duplicate attempt, mobile-data general APIs, switch-away/back with fresh proofs, Public-hotspot cleanup, actual school discovery/manual fallback. Partner Local needs a separate laptop's own pinned schema/settings/trust and physical device trial; do not run concurrently with Full on these ports or copy Full private keys.

## Later Public-hotspot update — 17 November, 23:15 MYT

The earlier precheck outcome above is historical. Both devices are now verified on the trusted Samsung hotspot. A rule-name array parsing defect in the external helper was fixed and regression-tested (24 offline checks); its first attempt rolled back before activation. A fresh exact-peer Public lease is now ACTIVE until **23:44:50 MYT**, with real scheduled SYSTEM cleanup rehearsal and watcher arming verified. Laptop 10.46.58.220, Xiaomi 10.46.58.11. No service restart or APK reinstall. Phone mDNS/manual pinned TLS/network rejection and final cleanup remain pending; no physical PASS claimed. Follow `C:\FYP\PublicLAN-Tests\hotspot-20261117-231435\REPORT.md` for the latest lease result. School remains NOT TESTED.

## Final Public-hotspot result — 17 November, 23:20 MYT

**PASS:** real Xiaomi automatically discovered the paired server, manual pinned HTTPS connected, and the unauthorized hotspot returned NETWORK_NOT_AUTHORIZED while Windows classified the hotspot as Public. User supplied these phone observations. The temporary lease was stopped early at **23:19:55 MYT**; host verification confirms zero FYP-Public rules, all **8 baseline rule hashes unchanged**, and hotspot category restored to Private. Backend PID 45804, admin 50604 and gateway 56012 remain unchanged. No APK reinstall or service restart. The earlier ACTIVE/pending descriptions are superseded by this result. Scheduled SYSTEM cleanup rehearsal passed; a full 30-minute wall-clock expiry was not waited out. School connectivity remains NOT TESTED.

Latest evidence: `C:\FYP\PublicLAN-Tests\hotspot-20261117-231435\REPORT.md`. For school, use the corrected helpers/preparation procedure and obtain separate site activation approval; never use broad /16 firewall access.
