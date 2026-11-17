# Final system status

Acceptance review: 17 November 2026 (MYT); branch SH, HEAD ccec246. Evidence folder: `C:\FYP\Final-Acceptance\20261117-final`.

**Decision: PARTIAL acceptance. The deployed Full system is healthy and suitable for rehearsing the known Private-Wi-Fi demonstration. Public-hotspot physical acceptance now passed; complete the remaining physical checks before claiming school acceptance. No fresh automated failure was found.**

## Fresh results

- Backend: **582 PASS, 14 SKIPPED**, all 596 collected tests accounted for. Live SQL/API integration opt-ins disabled; real mysql.connector connections blocked in the test process. Synthetic/SQLite tests are not production write or real MariaDB concurrency tests.
- Flutter: **331 PASS, 1 SKIPPED**. `flutter analyze --no-pub`: no issues. Paired Full debug APK build: PASS; no installation performed.
- PowerShell: all **13 root scripts parse**. Temporary firewall lease logic: **21 offline checks PASS**, no real firewall/task mutations.
- `git diff --check`: PASS, with an existing LF/CRLF conversion warning only.
- Fresh read-only MariaDB check: **10.4.27-MariaDB**, original `attendance_proposal_xampp:3306`, **43 tables**, **1 student / 8 attendance / 2 registered-device rows**. Full schema guard PASS. No migration, login, attendance submission or policy mutation was executed.
- The test runner did not connect to the live DB. Read-only live requests and SELECT metadata/counts were separate. No before/after complete database hash comparison or new durability rehearsal is claimed.

## Operational dashboard

| Component | Fresh observation | Status |
|---|---|---|
| Original HTTP 8000 | 0.0.0.0, PID 45804; localhost + 192.168.0.162 /config 200 | PASS |
| Trusted HTTPS 8005 | 192.168.0.162, same PID 45804; pinned CA/name/identity verified | PASS |
| Host mDNS | _fyp-classroom._tcp.local advertises 192.168.0.162:8005 | PASS (host only) |
| Admin 8003 | loopback PID 50604; login page 200; authenticated mutations tested synthetically | PASS (scoped) |
| Gateway 8004 | loopback PID 56012; exact Host config 200 | PASS |
| Cloudflare | service Running; HTTPS config 200, unauthenticated /me 401 | PASS |
| Public sensitive routes | attendance, biometric, devices, sessions and diagnostic probes 404; exhaustive/authenticated fixture tests passed | PASS |
| BLE | PID 41196, BleProbe.exe --continuous; log continues Windows status Started | PASS (publisher only) |
| Diagnostic mode | local and public config network_ble_test_mode=false | PASS |
| Tablet ADB / fresh physical capture | no attached device at this audit | NOT TESTED |
| Public hotspot | Later real Xiaomi: auto discovery + manual paired TLS connected; NETWORK_NOT_AUTHORIZED as expected | PASS (user-confirmed) |
| School Public Wi-Fi | no activation or school physical test | NOT TESTED |

## Function audit — both modes

PASS below means the actual named automated suite passed, not that every physical/environmental variation was tried. Details and skipped IDs are in FINAL_TEST_CASES.md.

| Function | Automated status | Scope / physical qualification |
|---|---|---|
| Student login, active-account/expiry and logout revocation | PASS (38 passed; 0 skipped) | Both: synthetic PASS; Full live credentials not exercised |
| Student/admin separation, localhost admin authorization, CSRF and session security | PASS (21 passed; 0 skipped) | Both: synthetic PASS; Full live /login 200 |
| Profile, class/history/summary scoping | PASS (38 passed; 0 skipped) | Both: synthetic PASS; live authenticated read not run |
| School-provisioned account / account-bound first enrollment | PASS (11 passed; 0 skipped) | Both: policy tests PASS; not institutional identity verification |
| Slot 1/2 registration and key ownership | PASS (16 passed; 1 skipped) | Both: synthetic PASS; existing two device rows read |
| Slot 2 pending proof and genuine face/liveness integration | PASS (11 passed; 1 skipped) | Both: synthetic PASS; no new real activation |
| Biometric approval and provenance restrictions | PASS (18 passed; 1 skipped) | Both: synthetic PASS; legacy templates not silently trusted |
| Device activation and single-use approval | PASS (20 passed; 1 skipped) | Both: synthetic PASS; local demo remains explicitly scoped |
| Slot 1/2 replacement, old-key revocation and unaffected slot | PASS (13 passed; 1 skipped) | Both: synthetic PASS; no physical destructive replacement |
| Standalone signed-device verification | PASS (21 passed; 1 skipped) | Both: synthetic PASS |
| Attendance PIN/session/group/expiry and duplicate protection | PASS (38 passed; 0 skipped) | Both: synthetic PASS; no new real attendance written |
| Admin session create/close/PIN regeneration and policy management | PASS (21 passed; 0 skipped) | Both: synthetic PASS; no live form mutation |
| CIDR source-IP verification, loopback and forwarded-header rejection | PASS (15 passed; 1 skipped) | Both: synthetic PASS; hotspot unauthorized result historical user evidence |
| Classroom Wi-Fi signatures, freshness and replay | PASS (16 passed; 1 skipped) | Both: synthetic PASS; real home Wi-Fi historical user evidence |
| Session/classroom binding and Wi-Fi preflight/final checks | PASS (20 passed; 1 skipped) | Both: synthetic PASS; concurrency DB case skipped |
| Final fresh device/network authorization, forged/replayed/wrong-session rejection | PASS (23 passed; 0 skipped) | Both: synthetic PASS; no diagnostic PASS accepted as authorization |
| Partner face/hand processing and real-model rejection | PASS (9 passed; 0 skipped) | Both: test PASS; physical accuracy/anti-spoof robustness NOT TESTED |
| Passive anti-spoof evidence and final-write protection | PASS (15 passed; 0 skipped) | Both: synthetic/model tests PASS; fresh phone liveness pending |
| Head-movement challenges | PASS (20 passed; 0 skipped) | Both: tests PASS; fresh phone performance pending |
| Secure LAN discovery, certificate/name/mode/database pin validation | PASS (21 passed; 0 skipped) | Both: tests PASS; Full live pinned TLS + host mDNS PASS |
| Full start/install/stop ownership, bounded readiness and BLE reuse | PASS (27 passed; 0 skipped) | Full: mocked lifecycle PASS; no disruptive cold start today |
| Partner Local independent profile, identity and no Full fallback | PASS (13 passed; 0 skipped) | Local: tests PASS; own laptop/profile/physical deployment NOT TESTED |
| Restricted public gateway and authenticated sensitive-route denial | PASS (33 passed; 0 skipped) | Full: tests PASS; local/public config 200 and public sensitive GET 404; Local: NOT APPLICABLE |
| BLE standalone UUID/RSSI/sample/freshness/skew/signature checks | PASS (25 passed; 1 skipped) | Both: synthetic PASS; fresh phone radio test pending |
| BLE shadow cannot independently authorize or reject attendance | PASS (8 passed; 0 skipped) | Both: tests PASS; BLE process currently Started |
| Temporary diagnostic feature disabled and never attendance-writing | PASS (10 passed; 0 skipped) | Both: tests PASS; Full live config false |
| Schema migration compatibility and additive guards | PASS (3 passed; 0 skipped) | Both: isolated tests PASS; no migration applied today |
| Original database identity/schema guard | PASS (30 passed; 0 skipped) | Full: tests PASS + fresh read-only schema check; Local: NOT APPLICABLE |
| Production unsafe configuration rejection | PASS (13 passed; 0 skipped) | Both: tests PASS |
| MySQL profile guard compatibility | PASS (6 passed; 0 skipped) | Tested configuration logic; actual current server remains MariaDB |

| Additional scope item | Status | Explanation |
|---|---|---|
| Student in-app face delete/replace and faculty identity recovery | NOT APPLICABLE | Deliberately outside confirmed FYP scope; deletion/re-enrollment blocked, not a missing demo feature. |
| General institutional faculty/lecturer RBAC portal | NOT IMPLEMENTED | Existing supported roles are student API and separate local administrator; no broader institutional portal claimed. |
| Editable student ID or self-service enrollment reset | NOT APPLICABLE | Intentionally restricted. |
| Partner Local live DB, TLS pairing and phone deployment on this laptop | NOT TESTED | Independent private settings, identity pin and TLS trust are absent; Full must not be reused as Local. |
| Fresh real MariaDB concurrent writes/restart durability | NOT TESTED | 14 backend integration tests skipped; historical disposable results are separate. |

## Firewall and Public-hotspot disposition

Current network: **Ultraman_yap_5Ghz, Private, 192.168.0.162**. Last hotspot request expected another network and stopped before mutations. No activation result, no FYP temporary Public lease task/rule or protected lease folder was found. All **8 existing FYP/shared-Python rule hashes match the saved baseline**. Four shared Python allow-all rules remain disabled; existing FYP Private TCP 8000/8005 and UDP 5353 remain enabled. No cleanup was needed because activation never occurred. Actual timed-expiry execution is NOT TESTED; offline controller logic passed.

## Historical evidence (not fresh acceptance)

User reported: home automatic discovery + network PASS; hotspot Private paired HTTPS worked after IP change without APK reinstall and returned NETWORK_NOT_AUTHORIZED; Public hotspot initially blocked. Previously real Xiaomi Slot 2 attendance succeeded. Five temporary Network + BLE diagnostic physical cases were reported PASS, then mode was disabled. Earlier disposable database integration/acceptance/soak results are not a fresh concurrency or restore test of today’s original server.

## Changes and preservation

Only the six Markdown files in `docs/final_acceptance/` were added in this acceptance task. The prior 16 secure-discovery source/document files remain pending. No source fix was needed, no branch switch/staging/commit/push, no service restart, no firewall/category change, no APK install, no key provisioning, no database write or migration. Earlier implementation-snapshot wording in existing discovery/Local docs may be superseded by this dated live report.

See REMAINING_BLOCKERS.md for acceptance gaps, PHYSICAL_TEST_CHECKLIST.md for exact next steps and PRESENTATION_DEMO.md for the stable demonstration path.

## Later Public-hotspot update — 17 November, 23:15 MYT

The earlier precheck outcome above is historical. Both devices are now verified on the trusted Samsung hotspot. A rule-name array parsing defect in the external helper was fixed and regression-tested (24 offline checks); its first attempt rolled back before activation. A fresh exact-peer Public lease is now ACTIVE until **23:44:50 MYT**, with real scheduled SYSTEM cleanup rehearsal and watcher arming verified. Laptop 10.46.58.220, Xiaomi 10.46.58.11. No service restart or APK reinstall. Phone mDNS/manual pinned TLS/network rejection and final cleanup remain pending; no physical PASS claimed. Follow `C:\FYP\PublicLAN-Tests\hotspot-20261117-231435\REPORT.md` for the latest lease result. School remains NOT TESTED.

## Final Public-hotspot result — 17 November, 23:20 MYT

**PASS:** real Xiaomi automatically discovered the paired server, manual pinned HTTPS connected, and the unauthorized hotspot returned NETWORK_NOT_AUTHORIZED while Windows classified the hotspot as Public. User supplied these phone observations. The temporary lease was stopped early at **23:19:55 MYT**; host verification confirms zero FYP-Public rules, all **8 baseline rule hashes unchanged**, and hotspot category restored to Private. Backend PID 45804, admin 50604 and gateway 56012 remain unchanged. No APK reinstall or service restart. The earlier ACTIVE/pending descriptions are superseded by this result. Scheduled SYSTEM cleanup rehearsal passed; a full 30-minute wall-clock expiry was not waited out. School connectivity remains NOT TESTED.

Latest evidence: `C:\FYP\PublicLAN-Tests\hotspot-20261117-231435\REPORT.md`. For school, use the corrected helpers/preparation procedure and obtain separate site activation approval; never use broad /16 firewall access.

Post-cleanup checks: original identity unchanged, backend/admin/public config healthy, pinned HTTPS valid, diagnostic false, public attendance route 404. Read-only attendance count remains **8**, matching the earlier check. This is a count comparison, not a complete row-content hash comparison.

## Attendance retry update — investigation after Public-hotspot acceptance

Two Flutter transport lifecycle defects reproduced and corrected: stale old request invalidating a new paired client, and new PIN submission reusing a stale cached address. Native key timeout presentation corrected separately. Fresh results: 130 backend PASS/2 skipped, 337 Flutter PASS/1 skipped, analysis clean and paired APK built. **The installed APK has not been updated; physical Xiaomi retry remains PENDING.** No backend restart or security-policy change is needed. See `docs/ATTENDANCE_RETRY_NETWORK_FIX.md`. Earlier readiness statements are conditional on this newly reported retry issue being physically retested.
