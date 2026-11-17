# Yap Seng Hin — device and network verification

Presentation reading order, 18 November 2026. This index organizes SH-owned material; it does not replace shared setup instructions or change runtime behavior. Dated reports retain their original test scope. Addresses, PIDs and test counts in old reports are observations, not reusable configuration.

## Current reading order

| Topic | Primary SH reference | Qualification |
|---|---|---|
| Module boundary | [Ownership inventory](sh/OWNERSHIP_INVENTORY.csv) | Shared, partner and unknown files are read-only in this cleanup. |
| Flutter/FastAPI device integration | [Self-service design](SELF_SERVICE_DEVICE_MANAGEMENT.md), [reusable replacement](REUSABLE_DEVICE_REPLACEMENT.md) | Candidate key proof, fresh genuine face/liveness, operation-bound single-use grant; do not reuse setup scans. |
| Device retry and names | [Preparation/routing fix](DEVICE_PREPARATION_CONNECTION_AND_NAME_FIX.md) | User-facing names are separate from audited demo assurance. |
| Attendance retry boundary | [Retry investigation](ATTENDANCE_RETRY_NETWORK_FIX.md) | Fresh paired connection/proofs; no automatic replay of signed writes. |
| Secure automatic LAN discovery | [Pinned HTTPS discovery](SECURE_LAN_DISCOVERY.md) | TLS provisioning and deployment sections are dated. Keep the installed environment's trust identity; never pair by IP alone. |
| Source-IP/CIDR checks | [Phase 4 history](NETWORK_VERIFICATION_PHASE4.md), [multiple policies](FYP_MULTIPLE_NETWORK_POLICIES.md) | Loopback/forwarding claims are not campus proof; old disposable commands are not original-database commands. |
| Classroom Wi-Fi | [Diagnostics](WIFI_DISCOVERY_PHASE1.md), [policy verification](CLASSROOM_WIFI_PHASE2.md), [attendance boundary](CLASSROOM_WIFI_ATTENDANCE_PHASE3.md) | Client-reported SSID/BSSID are observations. Preserve final source-IP and signed-device enforcement. |
| Attendance security boundary | [Final authorization contract](ATTENDANCE_AUTHORIZATION_PHASE5.md) | SH owns proof/network integration, not the partner's biometric algorithms or attendance business logic. |
| BLE observations | [Standalone policy/history](CLASSROOM_BLE_PHASE4B.md), [radio diagnostics](BLE_BEACON_PHASE4A.md) | BLE remains shadow/diagnostic-only. It cannot grant attendance or independently reject otherwise valid attendance. |
| Temporary test-mode evidence | [Diagnostic mode](NETWORK_BLE_TEST_MODE.md) | Historical test procedure, not an instruction to enable it. Keep diagnostic mode OFF. |
| Cleanup / validation | [Cleanup report](SH_MODULE_CLEANUP_REPORT.md) | Fresh cleanup checks are separate from historical acceptance. |

## Shared references — read only

Use the existing [three-command workflow](FYP_THREE_COMMANDS.md), [original environment setup](ORIGINAL_FYP_SETUP.md), [dual-path connectivity](DUAL_PATH_CONNECTIVITY.md), and [Partner Local guide](PARTNER_LOCAL_MODE.md). They are shared operational dependencies and were not reorganized here. Full and Partner Local must keep independent private identities/configuration; do not copy TLS secrets or database records between laptops.

The existing [code explanation](final_acceptance/CODE_EXPLANATION.md), [presentation runbook](final_acceptance/PRESENTATION_DEMO.md), [test cases](final_acceptance/FINAL_TEST_CASES.md) and [physical checklist](final_acceptance/PHYSICAL_TEST_CHECKLIST.md) describe a dated whole-system acceptance review. They remain unchanged because their scope includes partner/shared behavior. Do not read old PIDs or device counts as current.

## Current device-test qualification

The 18 November read-only check confirmed HONOR BRP-NX1 ACTIVE in Slot 1, Xiaomi ACTIVE in Slot 2, and Samsung's old registration REVOKED. HONOR had a real DEVICE_VERIFIED event after normal replacement. Eight attendance records matched the pre-test hash. These are historical observations from that check, not a new cleanup-time database query.

Physical replacement of Slot 2 with Samsung's retained historical key is blocked by KEY_ALREADY_REGISTERED. Do not reset Keystore, erase app data or delete history to make this test pass. Both-slot automated tests are evidence of synthetic behavior; a successful real Slot 2 replacement still requires a genuinely eligible distinct key/device and fresh face/liveness.

School Public-Wi-Fi discovery remains a physical acceptance item. Successful trusted-hotspot discovery does not prove school multicast/VLAN reachability or authorize that hotspot for attendance. No network policy or firewall change is authorized by this guide.

## Historical archive

- [Device/network UI cleanup evidence](sh/archive/FLUTTER_NOTICE_CLEANUP.md).
- [Original BLE Phase 4B proposal](sh/archive/BLE_BEACON_PHASE4B_DESIGN.md).

Original document paths remain as forwarding pages, so shared references keep working. No program, test, migration, private file or untracked implementation was deleted or moved.
