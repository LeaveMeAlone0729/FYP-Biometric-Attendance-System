# Remaining essential acceptance gaps

17 November 2026. **No fresh executable regression failed. No additional source fix or optional feature is justified by this review.**

1. **Public-profile hotspot is COMPLETE for the three requested phone checks and early rollback.** User confirmed automatic discovery, manual pinned HTTPS and NETWORK_NOT_AUTHORIZED. Cleanup at 23:19:55 MYT removed the two rules; all eight baseline hashes match; original Private category restored. The helper’s rule-name parsing defect was fixed with a regression; 24 offline checks pass. This is no longer a blocker. Actual 30-minute elapsed expiry was not waited out, although scheduled SYSTEM cleanup was rehearsed and the deadline armed before activation.
2. **School connectivity is unproven.** Existing backend policy 172.22.0.0/16 stays unchanged. At school, verify actual network/peer addresses, prepare a temporary exact-peer Public-profile lease and obtain site activation approval. mDNS blocking, client isolation or VLAN separation may require school IT. Pinned manual IP is only useful if direct HTTPS is permitted. Never authorize the entire /16 in Windows Firewall or route attendance publicly.
3. **Fresh end-to-end phone rehearsal is pending.** Test normal PIN → preflight → current partner face/actions/liveness → final signed attendance → duplicate rejection, then network switching and mobile-data general APIs. Historical Slot 2/home/diagnostic successes do not substitute for this fresh full flow. Do not delete attendance or reset devices for repetition. Any agent-created real session/attendance requires authorization; this review performed no real write.
4. **Partner Local deployment is not validated on an actual partner laptop.** Source/fixtures pass; this laptop has no independent Local settings/identity/TLS trust. Partner needs their own schema/profile and provisioning, not copied Full credentials or biometric/key records. Do not start it concurrently over the working Full ports.

## Warnings, not new blockers

- Original MariaDB application schema is readable and validated (43 tables). Earlier system-table corruption is not declared repaired; a read-only health check is not a fresh backup/restore/durability test. Existing verified checkpoints remain important. No repair or server restart was attempted.
- 14 backend live/concurrency tests and one Flutter test were skipped intentionally. Earlier isolated MariaDB acceptance/soak evidence is historical, not rerun against original data.
- Biometric tests cover contracts, processing and rejection assertions; they do not establish population accuracy or comprehensive real-world spoof resistance.
- Backend emitted TestClient and pkg_resources deprecation warnings plus a pytest cache permission warning. All assertions passed; evidence/JUnit saved outside the repository. Android build emitted existing toolchain future-support warnings; build succeeded. Do not upgrade tooling two days before the demonstration without a confirmed need.
- Existing implementation-snapshot docs contain older deployment-not-executed wording; use this dated acceptance report and deployment checkpoint for actual current Full status.

## Readiness decision

**Known Private-network demonstration: provisionally READY for rehearsal. Full school/Public acceptance: PARTIAL, not signed off.** Finish the normal attendance phone rehearsal and school network checks before claiming those capabilities at the presentation. If school networking cannot be proven in time, present the secure working Private-network flow and explicitly label school connectivity NOT TESTED. Never bypass attendance requirements to turn an untested path into a demo PASS.

No database/schema/policy/key changes, service restarts, APK installation, firewall edits or Git commits were performed by this final acceptance task.

## Later Public-hotspot update — 17 November, 23:15 MYT

The earlier precheck outcome above is historical. Both devices are now verified on the trusted Samsung hotspot. A rule-name array parsing defect in the external helper was fixed and regression-tested (24 offline checks); its first attempt rolled back before activation. A fresh exact-peer Public lease is now ACTIVE until **23:44:50 MYT**, with real scheduled SYSTEM cleanup rehearsal and watcher arming verified. Laptop 10.46.58.220, Xiaomi 10.46.58.11. No service restart or APK reinstall. Phone mDNS/manual pinned TLS/network rejection and final cleanup remain pending; no physical PASS claimed. Follow `C:\FYP\PublicLAN-Tests\hotspot-20261117-231435\REPORT.md` for the latest lease result. School remains NOT TESTED.

## Latest disposition — 23:20 MYT

The ACTIVE-lease note above is historical: the lease is now CLEANED. Public-hotspot physical connectivity and unauthorized-network rejection passed. Remaining essential physical work is school connectivity, fresh normal attendance/network-switching rehearsal, and partner Local deployment if required for the presentation. No new firewall exception remains.

## Attendance retry update — investigation after Public-hotspot acceptance

Two Flutter transport lifecycle defects reproduced and corrected: stale old request invalidating a new paired client, and new PIN submission reusing a stale cached address. Native key timeout presentation corrected separately. Fresh results: 130 backend PASS/2 skipped, 337 Flutter PASS/1 skipped, analysis clean and paired APK built. **The installed APK has not been updated; physical Xiaomi retry remains PENDING.** No backend restart or security-policy change is needed. See `docs/ATTENDANCE_RETRY_NETWORK_FIX.md`. Earlier readiness statements are conditional on this newly reported retry issue being physically retested.
