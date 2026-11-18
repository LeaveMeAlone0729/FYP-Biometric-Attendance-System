# PR 18 isolated integration resolution

18 November 2026 (MYT). Source origin/SH 5ec2c1f; target origin/main d1ac55a; merge base ccec246. This is a locally prepared merge of main into an isolated SH integration branch, not a GitHub PR merge or a live deployment.

## Exact conflict cause and resolution

Main's b3f9077 cleanup deleted test/document files that SH's 5ec2c1f modified. The latest local Git merge reported eight modify/delete conflicts. The ninth expected file, the Android installer, was renamed by main into scripts/ and merged automatically, but required a real repository-root correction.

| File | Integrated resolution |
|---|---|
| backend/tests/test_attendance_authorization.py | Retain SH retry and final-proof security tests; adapt their shared synthetic inference fixture to main's face_observation API. |
| backend/tests/test_device_management.py | Retain SH device/provenance tests unchanged. |
| docs/BLE_BEACON_PHASE4B_DESIGN.md | Retain SH historical forwarding page and full archive. |
| docs/CLASSROOM_BLE_PHASE4B.md | Retain SH report and historical-scope notice. |
| docs/FLUTTER_NOTICE_CLEANUP.md | Retain SH forwarding page and full archive. |
| docs/NETWORK_VERIFICATION_PHASE4.md | Retain SH report and later final-authorization reference. |
| frontend/test/attendance_preflight_test.dart | Retain SH retry/network/preflight tests unchanged. |
| frontend/test/pending_device_test.dart | Retain SH registration/replacement and key-retention tests unchanged. |
| install-fyp-android.ps1 → scripts/install-fyp-android.ps1 | Preserve main's supported relocation/projectRoot, SH public-trust export and all existing guards. Exporter executable and script must resolve under projectRoot, not scripts/PSScriptRoot. Add a regression. |

Other clean merges preserve main's Local MySQL/MariaDB support and interactive private-profile configuration alongside SH's TLS listener/database binding and ownership checks. No biometric runtime file differs from main. No migration/schema file differs from main, including deliberate deletions of obsolete CLI migration wrappers. No migration ran. Retained manual operator helpers are excluded from automatic collection and were not run against live data. A static filename-reference audit found no literal references to the removed root migration commands. Follow main's current setup documentation for deployment.

## Coverage and fixture integration

Main removed the backend/Flutter test suites and Flutter test SDK dependencies. Restore all existing SH test/helper files and backend/pytest.ini so security coverage and opt-in collection boundaries are retained; no test is silently removed. Restore Flutter's SDK test development dependencies and lockfile entries. No new runtime dependency is introduced.

Adapt only tests to main's current API/UI: combined synthetic face/PAD observation; two permitted randomized head actions; movement-popup acknowledgement; longer pre-captured blink burst; historical-key/replay/face/attendance guards unchanged. The initial open-eye frame can legitimately prime a first blink, so the closed-eyes-only negative test now explicitly begins with closed eyes. Unsupported prior up/down/neutral actions remain rejected under main's contract. Main also tightened the PAD ensemble minimum to 0.95. Retain that threshold: valid fixture scores now meet it, and prior lower-score positive examples are explicitly tested as rejections. No partner biometric algorithm/threshold was changed.

Tests may use an explicit FYP_TEST_PYTHON path for disposable certificate fixture generation in an isolated worktree. No private keys, .env or live configuration were copied. Only public MediaPipe model assets were copied for tests, byte-hash checked and confirmed ignored by Git. 18 restored historical Markdown documents are preserved, not fresh deployment results. Main's deletion of generated docs/openapi.json is retained; contract tests generate an isolated temporary specification instead.

## Validation

Final guarded full backend run: **621 passed, 14 skipped, zero failed**, two dependency deprecation warnings, 392.26 seconds. The 14 skipped live database/concurrency integrations were intentionally disabled; every mysql.connector connection was rejected in the test process. Earlier runs failed obsolete fixtures/model availability; final full rerun is green.

Focused checks: 49 biometric/PAD/head/API tests; 67 installer/Local/discovery/API-contract tests; 24 attendance-authorization tests all passed. No source behavior was relaxed to obtain these results.

Flutter: 340 passed, one skipped; analyze clean. Python syntax: all 179 files parsed after final test-only adapters; PowerShell: all 13 parse. 76 local Markdown links resolve. README descriptions were updated to reflect the retained regression suites; main's teammate setup and scripts/ layout remain intact. Fixture-only changes do not claim real device/campus validation.

Credential-pattern and private/generated-artifact path scan found no matches; this is a heuristic scan, not a new exhaustive security assessment. No secrets were logged. Exact per-parent file inventories, three-way source snapshots, test logs, manifest and final checks are outside the repository at the protected checkpoint.

## Safety / publication

Live checkout remains SH at 5ec2c1f, unchanged and clean. Original database, services, firewall, TLS identities, Cloudflare, Android data and active devices are untouched. No push or PR merge is authorized. A verified Git bundle and SH source tar preserve the pre-merge refs/tree; ignored runtime files are inventoried and never cleaned/moved.

After all validation passes, the local merge commit has SH and main as parents. Publication requires separate approval. From this integration worktree: git fetch origin main SH; verify remote SH/main have not advanced; git push origin HEAD:SH. This is a normal fast-forward of remote SH, never force-push. Do not run that command until approved. Do not merge PR 18 automatically or change the live checkout during this task.
