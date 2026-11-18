# SH module cleanup report — Yap Seng Hin

18 November 2026 (MYT), branch SH, HEAD ccec246. Documentation-only cleanup. No staging, commit, push, branch switch, service restart, APK action or database operation.

## Ownership inventory before edits

The complete [374-file inventory](sh/OWNERSHIP_INVENTORY.csv) was prepared before edits and checked against docs/MODULE_OWNERSHIP.md, Git history, module paths and dependencies. It classifies 93 files MY MODULE, 16 PARTNER MODULE, 168 SHARED and 97 UNKNOWN OWNERSHIP. This is a conservative cleanup permission map, not a transfer of ownership. All shared/partner/unknown files stayed read-only. In particular, tests are conservatively shared even when testing an SH module; migrations/schema/seed files are protected regardless of author.

Evidence: MODULE_OWNERSHIP.md assigns facial/liveness folders to Chew Zhexuan and separates device/network module ownership. Git history attributes the archived UI report to Seng-hin commit 0974cce and original BLE proposal to Seng-hin commit 1c5e4cc. The provider contract and cross-system final acceptance/setup documents are shared integration material, so they remain untouched.

The task baseline already contained 43 modified/new files. These include shared integrations from earlier approved work; their presence in git diff is not a change made by this cleanup. A per-file SHA-256 baseline and recoverable copies of all 43 files, staged/unstaged patches and status were preserved outside Git before edits:

`C:\FYP\Cleanup-Checkpoints\sh-module-20261118-023738`

Restore documentation only by copying the corresponding original-documents file back to its original docs path. Pre-existing uncommitted implementation copies are under working-copy with their repository-relative paths. Review before restoring; do not reset/clean the repository or overwrite newer implementation work. No private runtime/ignored files were copied, moved or removed.

## Documentation audit and actions

19 confirmed SH-owned documents were reviewed for purpose, dated state, references and consolidation. Exact duplicate content was not established; no evidence report was deleted as redundant. Instead, one reading-order index replaces the need to repeat instructions. No test results were merged or relabelled as fresh PASS.

| Existing document | Action | Reason |
|---|---|---|
| docs/ATTENDANCE_AUTHORIZATION_PHASE5.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/ATTENDANCE_RETRY_NETWORK_FIX.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/BLE_BEACON_PHASE4A.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/BLE_BEACON_PHASE4B_DESIGN.md | ARCHIVE | Full original retained in SH archive; stable forwarding page preserved. |
| docs/CLASSROOM_BLE_PHASE4B.md | KEEP | Added historical-scope notice and current reference; original evidence retained below. |
| docs/CLASSROOM_WIFI_ATTENDANCE_PHASE3.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/CLASSROOM_WIFI_PHASE2.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/DEMO001_SLOT2_RESET_TEST.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/DEVICE_PREPARATION_CONNECTION_AND_NAME_FIX.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/FLUTTER_NOTICE_CLEANUP.md | ARCHIVE | Full original retained in SH archive; stable forwarding page preserved. |
| docs/FYP_MULTIPLE_NETWORK_POLICIES.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/FYP_NETWORK_TEST_WORKFLOW.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/LOCAL_DEMO_SLOT1_REPLACEMENT_PLAN.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/NETWORK_BLE_TEST_MODE.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/NETWORK_VERIFICATION_PHASE4.md | KEEP | Added historical-scope notice and current reference; original evidence retained below. |
| docs/REUSABLE_DEVICE_REPLACEMENT.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/SECURE_LAN_DISCOVERY.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |
| docs/SELF_SERVICE_DEVICE_MANAGEMENT.md | KEEP | Added historical-scope notice and current reference; original evidence retained below. |
| docs/WIFI_DISCOVERY_PHASE1.md | KEEP | Current contract, implementation evidence, troubleshooting or explicit historical test record. Preserve; index rather than duplicate. |

Two originals are now fully preserved under docs/sh/archive, with only an archive notice and relocation of the BLE document's relative link. Their original paths remain forwarding pages; no shared link needed modification. Three other reports gained an explicit historical-scope notice, without replacing their implementation evidence. The SH module guide gives a current reading order, distinguishes original versus disposable commands and explains that historical IP/PID observations are not runtime configuration.

No untracked implementation or existing untracked report was edited, deleted or moved. No program code, script, SQL, configuration, security mechanism or migration was removed. Files awaiting deletion approval: **0**; no safe program deletion was established.

## Program-file audit

74 exclusively SH-owned program files were inventoried and checked for filename/module references in imports, calls, route registration, Flutter/service integration, tests, documentation and launch configuration. All had reference evidence. Filename/static reference counts do not prove runtime use, and zero counts would not prove safe deletion. Python AST checks parsed 42 exclusively owned Python files. Device approval/provider state and legacy local-test evidence are security dependencies, not dead code. Keep them without refactoring.

Standalone reset, provisioning, restored-database and acceptance helpers are operator/test entry points, often launched outside the app. Keep them, their history and tests. Recent local_account_verification/reset_demo_slot2 files are untracked implementation, and were preserved. Old literal IP addresses inside dated reports or negative tests are not proof of unused runtime fallback. No hardcoded-IP source deletion is proposed.

## Migration observations — static only

backend/application_schema.py dynamically collects device, authorization, network, classroom Wi-Fi and BLE models across their metadata. backend/setup.py still references named upgrade entry points. This means old-looking migration modules can remain live dependencies. No claim is made that every historical migration is redundant or that a partner consolidation is complete. All migration/schema/seed files and history are unchanged, and no migration, tracking-table query or schema verification was run against MariaDB.

## Validation

| Check | Fresh result |
|---|---|
| Full guarded backend suite | **620 passed, 14 skipped**, 2 dependency deprecation warnings; 298.84 seconds. |
| Full Flutter suite | **340 passed, 1 skipped**. |
| Flutter analysis | **PASS**, no issues; 26.8 seconds. |
| Owned Python syntax | **42 parsed**, no failures. |
| Cleanup-document local links | **40 checked**, none broken. |
| Archive content preservation | **2/2 match** original content after documented link relocation. |
| Git whitespace check | **PASS**; existing LF/CRLF warnings concern earlier source changes. |
| Ownership boundary | **PASS**, only the ten named SH documentation files differ from the task baseline. |
| Backup/staged preservation | **43/43 pre-existing changed files verified**, staged diff unchanged. |

Logs, JUnit XML, syntax/link/boundary details and recoverable originals are in the checkpoint above. Skips remain unexecuted tests; dependency deprecations were not repaired by changing shared dependencies. Historical test results in archived/shared reports were not replaced.

Full backend tests use the existing guarded runner with all mysql.connector.connect calls rejected in the test process and live integration opt-ins disabled. Synthetic passing results are not physical-device or MariaDB concurrency proof. Flutter tests and analysis use --no-pub. Python AST validation writes no bytecode. No PowerShell script changed, so affected-script syntax checks are not applicable. Documentation local-link checks cover the ten cleanup files and archive relocation; external web links and private historical evidence paths are not fetched.

## Exact task diff and preservation

Five pre-existing tracked SH documents changed:
- docs/BLE_BEACON_PHASE4B_DESIGN.md
- docs/CLASSROOM_BLE_PHASE4B.md
- docs/FLUTTER_NOTICE_CLEANUP.md
- docs/NETWORK_VERIFICATION_PHASE4.md
- docs/SELF_SERVICE_DEVICE_MANAGEMENT.md

Five new SH documentation artifacts:
- docs/SH_MODULE_GUIDE.md
- docs/SH_MODULE_CLEANUP_REPORT.md
- docs/sh/OWNERSHIP_INVENTORY.csv
- docs/sh/archive/BLE_BEACON_PHASE4B_DESIGN.md
- docs/sh/archive/FLUTTER_NOTICE_CLEANUP.md

Files merged: **0** (reading-order/navigation consolidated in the new SH guide). Files removed: **0**. Files awaiting program-deletion approval: **0**.

No file was deleted. Two documents were archived with stable original-path forwarding pages. No shared reference was edited. Baseline byte hashes distinguish this documentation delta from all earlier uncommitted source work. The final boundary verification and exact task diff are recorded in the checkpoint. Existing staged content is preserved.

No live database connection or write was performed by cleanup tooling. Backend test processes were blocked from live SQL. No SQL writes, migration, face/key operation, device reset, service action, firewall/Cloudflare/TLS change or private-file removal occurred. Database records were not re-read just to claim a redundant before/after verification. The unchanged services were not exercised through mutation endpoints.

## Presentation qualification / remaining recommendations

Documentation organization is ready; source features were intentionally not changed. Use [the SH module guide](SH_MODULE_GUIDE.md) and existing presentation runbook. Whole-system and Partner Local acceptance documents are dated shared evidence and remain unchanged. School Public-Wi-Fi physical acceptance and a successful real Slot 2 replacement with an eligible distinct candidate remain separate physical tests. Samsung's retained historical key is ineligible (KEY_ALREADY_REGISTERED); never erase app data, rotate its key or delete history for demonstration convenience. Partner biometric accuracy and school radio coverage cannot be established by these synthetic tests.

Read shared startup/configuration instructions directly instead of duplicating them into SH docs. Coordinate any desired shared-document correction with the partner. Do not purge recovery/test tooling immediately before presentation. No additional development, production cleanup or deletion approval is needed for this documentation-only result.
