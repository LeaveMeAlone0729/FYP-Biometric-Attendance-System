# Final test cases

17 November 2026. PASS is scoped to the stated evidence. Skipped automated cases are **NOT TESTED**, not PASS. Manual/historical evidence is not merged into fresh automated counts.

## Reproduction and safety

Evidence: `C:\FYP\Final-Acceptance\20261117-final` (`backend.xml`, backend.log, flutter.log, analyze.log, build.log, live.json, database.json, mdns.json, powershell.json, lease-tests.log, firewall-comparison.json).

Backend command: `venv\Scripts\python.exe` with the existing temporary pytest dependency path and a process-local wrapper that removes ATTENDANCE_API_URL, sets ATTENDANCE_DEVICE_MYSQL_TESTS=0 and replaces mysql.connector.connect with a function raising FINAL_ACCEPTANCE_LIVE_DATABASE_CONNECTION_BLOCKED; then `pytest.main(["tests", "-q", "--junitxml=.../backend.xml"])`. Do not enable live opt-ins against production. Guarded runner is saved in the evidence folder.

Flutter commands from frontend: `flutter test --no-pub --reporter expanded`; `flutter analyze --no-pub`; `flutter build apk --debug --no-pub --dart-define-from-file=C:\FYP\Deployment-Checkpoints\secure-lan-20261117-004116\paired-public-build-defines.json`. Build only, no install.

## Functional acceptance cases

Each AUTO case: prerequisites = existing backend venv + test-only dependencies; synthetic/in-memory fixtures, live DB blocked. Steps = run the cited suite within the guarded full pytest invocation, inspect its assertions/JUnit and associated Flutter regression suite. Expected = all executable assertions pass, negative cases reject and fixture attendance remains protected; skipped live concurrency is explicitly unexecuted.

| ID | Objective | Prerequisites / steps | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| AUTO-01 | Student login, active-account/expiry and logout revocation | Synthetic fixtures; run backend/tests/test_workflow.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 38 passed, 0 skipped. Both: synthetic PASS; Full live credentials not exercised | PASS |
| AUTO-02 | Student/admin separation, localhost admin authorization, CSRF and session security | Synthetic fixtures; run backend/tests/test_admin_testing.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 21 passed, 0 skipped. Both: synthetic PASS; Full live /login 200 | PASS |
| AUTO-03 | Profile, class/history/summary scoping | Synthetic fixtures; run backend/tests/test_workflow.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 38 passed, 0 skipped. Both: synthetic PASS; live authenticated read not run | PASS |
| AUTO-04 | School-provisioned account / account-bound first enrollment | Synthetic fixtures; run backend/tests/test_account_bound_enrollment.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 11 passed, 0 skipped. Both: policy tests PASS; not institutional identity verification | PASS |
| AUTO-05 | Slot 1/2 registration and key ownership | Synthetic fixtures; run backend/tests/test_device_registration.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 16 passed, 1 skipped. Both: synthetic PASS; existing two device rows read | PASS |
| AUTO-06 | Slot 2 pending proof and genuine face/liveness integration | Synthetic fixtures; run backend/tests/test_pending_device_enrollment.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 11 passed, 1 skipped. Both: synthetic PASS; no new real activation | PASS |
| AUTO-07 | Biometric approval and provenance restrictions | Synthetic fixtures; run backend/tests/test_device_biometrics.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 18 passed, 1 skipped. Both: synthetic PASS; legacy templates not silently trusted | PASS |
| AUTO-08 | Device activation and single-use approval | Synthetic fixtures; run backend/tests/test_device_activation.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 20 passed, 1 skipped. Both: synthetic PASS; local demo remains explicitly scoped | PASS |
| AUTO-09 | Slot 1/2 replacement, old-key revocation and unaffected slot | Synthetic fixtures; run backend/tests/test_device_replacement.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 13 passed, 1 skipped. Both: synthetic PASS; no physical destructive replacement | PASS |
| AUTO-10 | Standalone signed-device verification | Synthetic fixtures; run backend/tests/test_device_verification.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 21 passed, 1 skipped. Both: synthetic PASS | PASS |
| AUTO-11 | Attendance PIN/session/group/expiry and duplicate protection | Synthetic fixtures; run backend/tests/test_workflow.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 38 passed, 0 skipped. Both: synthetic PASS; no new real attendance written | PASS |
| AUTO-12 | Admin session create/close/PIN regeneration and policy management | Synthetic fixtures; run backend/tests/test_admin_testing.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 21 passed, 0 skipped. Both: synthetic PASS; no live form mutation | PASS |
| AUTO-13 | CIDR source-IP verification, loopback and forwarded-header rejection | Synthetic fixtures; run backend/tests/test_network_verification.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 15 passed, 1 skipped. Both: synthetic PASS; hotspot unauthorized result historical user evidence | PASS |
| AUTO-14 | Classroom Wi-Fi signatures, freshness and replay | Synthetic fixtures; run backend/tests/test_classroom_wifi.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 16 passed, 1 skipped. Both: synthetic PASS; real home Wi-Fi historical user evidence | PASS |
| AUTO-15 | Session/classroom binding and Wi-Fi preflight/final checks | Synthetic fixtures; run backend/tests/test_classroom_attendance.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 20 passed, 1 skipped. Both: synthetic PASS; concurrency DB case skipped | PASS |
| AUTO-16 | Final fresh device/network authorization, forged/replayed/wrong-session rejection | Synthetic fixtures; run backend/tests/test_attendance_authorization.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 23 passed, 0 skipped. Both: synthetic PASS; no diagnostic PASS accepted as authorization | PASS |
| AUTO-17 | Partner face/hand processing and real-model rejection | Synthetic fixtures; run backend/tests/test_biometric_inference.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 9 passed, 0 skipped. Both: test PASS; physical accuracy/anti-spoof robustness NOT TESTED | PASS |
| AUTO-18 | Passive anti-spoof evidence and final-write protection | Synthetic fixtures; run backend/tests/test_passive_liveness.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 15 passed, 0 skipped. Both: synthetic/model tests PASS; fresh phone liveness pending | PASS |
| AUTO-19 | Head-movement challenges | Synthetic fixtures; run backend/tests/test_head_movement.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 20 passed, 0 skipped. Both: tests PASS; fresh phone performance pending | PASS |
| AUTO-20 | Secure LAN discovery, certificate/name/mode/database pin validation | Synthetic fixtures; run backend/tests/test_lan_discovery.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 21 passed, 0 skipped. Both: tests PASS; Full live pinned TLS + host mDNS PASS | PASS |
| AUTO-21 | Full start/install/stop ownership, bounded readiness and BLE reuse | Synthetic fixtures; run backend/tests/test_fyp_operator.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 27 passed, 0 skipped. Full: mocked lifecycle PASS; no disruptive cold start today | PASS |
| AUTO-22 | Partner Local independent profile, identity and no Full fallback | Synthetic fixtures; run backend/tests/test_partner_local_mode.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 13 passed, 0 skipped. Local: tests PASS; own laptop/profile/physical deployment NOT TESTED | PASS |
| AUTO-23 | Restricted public gateway and authenticated sensitive-route denial | Synthetic fixtures; run backend/tests/test_public_gateway.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 33 passed, 0 skipped. Full: tests PASS; local/public config 200 and public sensitive GET 404; Local: NOT APPLICABLE | PASS |
| AUTO-24 | BLE standalone UUID/RSSI/sample/freshness/skew/signature checks | Synthetic fixtures; run backend/tests/test_classroom_ble.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 25 passed, 1 skipped. Both: synthetic PASS; fresh phone radio test pending | PASS |
| AUTO-25 | BLE shadow cannot independently authorize or reject attendance | Synthetic fixtures; run backend/tests/test_attendance_ble_shadow.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 8 passed, 0 skipped. Both: tests PASS; BLE process currently Started | PASS |
| AUTO-26 | Temporary diagnostic feature disabled and never attendance-writing | Synthetic fixtures; run backend/tests/test_network_ble_test_mode.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 10 passed, 0 skipped. Both: tests PASS; Full live config false | PASS |
| AUTO-27 | Schema migration compatibility and additive guards | Synthetic fixtures; run backend/tests/test_migrations.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 3 passed, 0 skipped. Both: isolated tests PASS; no migration applied today | PASS |
| AUTO-28 | Original database identity/schema guard | Synthetic fixtures; run backend/tests/test_original_fyp.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 30 passed, 0 skipped. Full: tests PASS + fresh read-only schema check; Local: NOT APPLICABLE | PASS |
| AUTO-29 | Production unsafe configuration rejection | Synthetic fixtures; run backend/tests/test_production_guard.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 13 passed, 0 skipped. Both: tests PASS | PASS |
| AUTO-30 | MySQL profile guard compatibility | Synthetic fixtures; run backend/tests/test_mysql_profiles.py in guarded suite; inspect assertions | Executable tests pass; rejected cases never grant unauthorized access | 6 passed, 0 skipped. Tested configuration logic; actual current server remains MariaDB | PASS |
| MAN-01 | Public hotspot automatic mDNS | Same verified trusted hotspot; actual peers captured; approved exact-peer 30-minute lease armed. Steps: Connect Xiaomi, Refresh Classroom connection | Trusted paired server discovered on Windows Public | User confirmed automatic discovery connected on Public hotspot; actual peers verified | PASS |
| MAN-02 | Public hotspot manual pinned HTTPS | MAN-01 network and valid lease. Steps: Enter actual current laptop IPv4 in paired manual fallback | Correct pinned TLS server accepted; no new trust accepted | User confirmed manual paired HTTPS connection on Public hotspot | PASS |
| MAN-03 | Reachable unauthorized hotspot rejection | Pinned HTTPS reachable on hotspot. Steps: Run Network Verification | NETWORK_NOT_AUTHORIZED; no attendance grant | User confirmed NETWORK_NOT_AUTHORIZED on reachable Public hotspot | PASS |
| MAN-04 | Independent cleanup arming/rehearsal and early rollback | Actual lease ACTIVE with fixed deadline. Steps: Observe deadline or stop early; inspect owned rules/tasks and baseline | Two exact-peer exceptions removed; unrelated rules unchanged | 24 offline checks; real SYSTEM scheduled cleanup rehearsal PASS; early stop at 23:19:55, rules removed and baseline restored. Full 30-minute timer not waited out | PASS |
| MAN-05 | Actual authorized school Public Wi-Fi | School site identity/peers verified; separate activation approval. Steps: Prepare exact-peer lease, test mDNS then manual pinned TLS | Reachable trusted backend; no broad /16 firewall rule | School not visited/tested | NOT TESTED |
| MAN-06 | Fresh complete normal attendance | Eligible legitimate open session, assigned credentials, matching approved Wi-Fi/CIDR/device. Steps: PIN → preflight → face/actions/liveness → final proof; inspect history | One real attendance record; security checks all enforced | Earlier Slot 2 attendance user PASS; current complete phone run pending | NOT TESTED |
| MAN-07 | Fresh duplicate attendance | MAN-06 completed. Steps: Repeat submission for same student/session | Duplicate rejected; no extra record | Not executed on phone in this run | NOT TESTED |
| MAN-08 | Mobile-data login/profile/classes/history/logout | Xiaomi mobile data and public gateway reachable. Steps: Wi-Fi off; login, load general pages and logout | General HTTPS works; revoked session cannot authenticate | Fresh mobile test pending | NOT TESTED |
| MAN-09 | Mobile-data attendance fails closed | Authenticated mobile-data session. Steps: Attempt classroom verification/attendance | Quick unavailable/rejection before camera; no public fallback | Automated PASS; fresh phone test pending | NOT TESTED |
| MAN-10 | Switch Wi-Fi → mobile → Wi-Fi | Existing authenticated paired app. Steps: Interrupt classroom operation, switch network, reopen general pages, return for fresh attempt | General recovery; old signed requests abandoned; fresh proof required | Automated PASS; fresh phone test pending | NOT TESTED |
| MAN-11 | Current phone face/liveness and spoof rejection | Genuine authorized user; unchanged partner models. Steps: Complete genuine challenge; separately try approved negative live-camera cases | Genuine completion accepted; invalid evidence rejected | Algorithm/unit tests PASS; fresh physical accuracy/spoof performance unmeasured | NOT TESTED |
| MAN-12 | Partner Local physical end-to-end | Partner laptop own validated schema/profile/trust, no Full port conflict. Steps: Run three commands with -Mode Local; login and legitimate verification | Independent Local works without Cloudflare or Full credentials | Not configured on this laptop; fixtures PASS only | NOT TESTED |
| MAN-13 | Fresh BLE shadow observation | Current phone, correct classroom and existing beacon. Steps: Observe correct/stopped/wrong UUID/Bluetooth-off statuses; compare /ble | BLE outcomes accurate but never authorize/veto attendance | Publisher Started and automated tests PASS; fresh phone shadow run pending | NOT TESTED |

## Fresh operational checks

| ID | Objective / prerequisites | Steps | Expected | Actual | Status |
|---|---|---|---|---|---|
| OPS-01 | Original HTTP health; services running | GET localhost and observed LAN /config | 200; diagnostic false | Both 200; false | PASS |
| OPS-02 | Original database guard; configured safe read access | original_fyp.probe() and SELECT version/table count/row counts | Matching original identity; all required schema readable | MariaDB 10.4.27; original :3306; 43 tables; 8 attendance rows | PASS |
| OPS-03 | Pinned HTTPS; existing public anchor | load_trust and probe_tls at actual IPv4 | Valid certificate/name and exact identity | Verified true | PASS |
| OPS-04 | Local multicast advertisement | Six-second host ServiceBrowser, current Wi-Fi interface | Correct service/address/port | 192.168.0.162:8005 | PASS (host only) |
| OPS-05 | Local admin availability | GET loopback /login | 200 without mutations | 200 | PASS |
| OPS-06 | Restricted gateway | Exact Host local /config, public /config and unauth /me | 200, 200, 401 | As expected | PASS |
| OPS-07 | Public sensitive routes blocked | Probe disallowed GET routes; run authenticated denial fixture tests | 404; no sensitive origin request | 404 and test assertions passed | PASS |
| OPS-08 | BLE publisher operational | Inspect exact executable, continuous argument and current Started log | Original broadcaster running | PID 41196, status Started | PASS (publisher only) |
| OPS-09 | Public lease leaves baseline intact | Inspect precheck/result/task/rules and hash eight original rules | No inactive-attempt mutation | No active lease; all eight baseline hashes match | PASS |
| OPS-10 | Local lease controller guards | Run Test-PublicLeaseLogic.ps1 with mocked OS mutations | All offline assertions pass | 21 passed; no real task expiry exercised | PASS |
| OPS-11 | Static/build checks | Flutter analyze/build, parse 13 root PS scripts, git diff --check | Clean analysis, build and parser success | Passed; deprecation/cache warnings only | PASS |

## Complete backend assertion inventory

Each row identifies an actual JUnit testcase. Objective is its test name. Prerequisite/step: the suite-specific fixtures and guarded execution above. Expected: its checked assertions succeed; actual/status below. This inventory preserves all 596 collected outcomes without guessing individual results.

| ID | Suite / exact test objective | Actual | Status |
|---|---|---|---|
| PY-001 | `tests.test_account_bound_enrollment.AccountBoundTests.test_account_bound_slot1_replacement` | All assertions passed | PASS |
| PY-002 | `tests.test_account_bound_enrollment.AccountBoundTests.test_account_bound_slot2_replacement` | All assertions passed | PASS |
| PY-003 | `tests.test_account_bound_enrollment.AccountBoundTests.test_enrollment_expiry_rolls_back_template_and_revision` | All assertions passed | PASS |
| PY-004 | `tests.test_account_bound_enrollment.AccountBoundTests.test_first_enrollment_login_and_immutable_id` | All assertions passed | PASS |
| PY-005 | `tests.test_account_bound_enrollment.AccountBoundTests.test_legacy_template_not_upgraded` | All assertions passed | PASS |
| PY-006 | `tests.test_account_bound_enrollment.AccountBoundTests.test_policy_disabled_after_enrollment_blocks_grant` | All assertions passed | PASS |
| PY-007 | `tests.test_account_bound_enrollment.AccountBoundTests.test_provenance_storage_failure_rolls_back_first_enrollment` | All assertions passed | PASS |
| PY-008 | `tests.test_account_bound_enrollment.AccountBoundTests.test_slot2_account_bound_policy_full_flow_and_replay` | All assertions passed | PASS |
| PY-009 | `tests.test_account_bound_enrollment.AccountBoundTests.test_unattested_and_public_self_registered_account_cannot_qualify` | All assertions passed | PASS |
| PY-010 | `tests.test_account_bound_enrollment.AccountBoundTests.test_unauthenticated_and_wrong_student_enrollment` | All assertions passed | PASS |
| PY-011 | `tests.test_account_bound_enrollment.AccountBoundTests.test_wrong_face_liveness_and_signature_never_authorize` | All assertions passed | PASS |
| PY-012 | `tests.test_admin_testing.AdminPanelTests.test_admin_initialization_hash_only_and_no_overwrite_or_database_connection` | All assertions passed | PASS |
| PY-013 | `tests.test_admin_testing.AdminPanelTests.test_admin_login_logout_revocation_and_student_credentials_rejected` | All assertions passed | PASS |
| PY-014 | `tests.test_admin_testing.AdminPanelTests.test_ajax_pin_regeneration_replaces_hash_and_preserves_session` | All assertions passed | PASS |
| PY-015 | `tests.test_admin_testing.AdminPanelTests.test_backend_probe_rejects_ordinary_port8000_missing_isolation_contract` | All assertions passed | PASS |
| PY-016 | `tests.test_admin_testing.AdminPanelTests.test_ble_management_disabled_default_experimental_only` | All assertions passed | PASS |
| PY-017 | `tests.test_admin_testing.AdminPanelTests.test_both_local_hosts_login_and_redirect_to_real_dashboard` | All assertions passed | PASS |
| PY-018 | `tests.test_admin_testing.AdminPanelTests.test_classroom_assignment_only_existing_and_integrated` | All assertions passed | PASS |
| PY-019 | `tests.test_admin_testing.AdminPanelTests.test_csrf_missing_forged_duplicate_and_cross_origin_rejected` | All assertions passed | PASS |
| PY-020 | `tests.test_admin_testing.AdminPanelTests.test_database_error_rolls_back_and_does_not_expose_connection_secrets` | All assertions passed | PASS |
| PY-021 | `tests.test_admin_testing.AdminPanelTests.test_every_management_page_and_mutation_requires_admin` | All assertions passed | PASS |
| PY-022 | `tests.test_admin_testing.AdminPanelTests.test_login_keeps_exact_origin_check_and_requires_csrf` | All assertions passed | PASS |
| PY-023 | `tests.test_admin_testing.AdminPanelTests.test_loopback_host_and_forwarding_guards` | All assertions passed | PASS |
| PY-024 | `tests.test_admin_testing.AdminPanelTests.test_management_script_is_same_origin_and_pages_have_inline_targets` | All assertions passed | PASS |
| PY-025 | `tests.test_admin_testing.AdminPanelTests.test_missing_optional_schema_is_unavailable_without_auto_migration` | All assertions passed | PASS |
| PY-026 | `tests.test_admin_testing.AdminPanelTests.test_network_management_existing_validator_and_simulation_boundary` | All assertions passed | PASS |
| PY-027 | `tests.test_admin_testing.AdminPanelTests.test_pin_once_session_duration_close_and_unchanged_attendance` | All assertions passed | PASS |
| PY-028 | `tests.test_admin_testing.AdminPanelTests.test_pin_regeneration_requires_admin_csrf_and_open_window` | All assertions passed | PASS |
| PY-029 | `tests.test_admin_testing.AdminPanelTests.test_session_expiry_and_fixed_login_throttle` | All assertions passed | PASS |
| PY-030 | `tests.test_admin_testing.AdminPanelTests.test_unknown_actions_extra_fields_and_large_forms_rejected` | All assertions passed | PASS |
| PY-031 | `tests.test_admin_testing.AdminPanelTests.test_validation_overlap_and_stopped_backend_do_not_insert` | All assertions passed | PASS |
| PY-032 | `tests.test_admin_testing.AdminPanelTests.test_wifi_management_escapes_html_and_keeps_validation` | All assertions passed | PASS |
| PY-033 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_atomic_publish_preserves_a_racing_initializer` | All assertions passed | PASS |
| PY-034 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_check_only_checks_ready_environment_without_admin_then_reports_setup_required` | All assertions passed | PASS |
| PY-035 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_eof_and_permission_failures_report_stage_without_secret_details` | All assertions passed | PASS |
| PY-036 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_exhausted_validation_never_creates_a_file` | All assertions passed | PASS |
| PY-037 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_hash_failure_never_leaves_empty_credentials` | All assertions passed | PASS |
| PY-038 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_missing_credentials_start_has_precise_error_and_never_checks_database` | All assertions passed | PASS |
| PY-039 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_short_password_and_confirmation_mismatch_can_be_corrected` | All assertions passed | PASS |
| PY-040 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_unsupported_hidden_input_is_rejected_without_echo_fallback` | All assertions passed | PASS |
| PY-041 | `tests.test_admin_testing_launcher.AdminLauncherTests.test_valid_credentials_start_uses_pinned_environment_and_loopback_listener` | All assertions passed | PASS |
| PY-042 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_different_attendance_attempt_cannot_reuse_signature` | All assertions passed | PASS |
| PY-043 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_either_active_slot_can_sign_and_other_slot_is_preserved` | All assertions passed | PASS |
| PY-044 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_existing_writer_cannot_be_called_without_biometrics_or_request_auth` | All assertions passed | PASS |
| PY-045 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_expired_attendance_signature_cannot_write` | All assertions passed | PASS |
| PY-046 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_failed_biometrics_never_reaches_writer` | All assertions passed | PASS |
| PY-047 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_invalid_signature_consumes_nonce_and_preserves_failure_audit` | All assertions passed | PASS |
| PY-048 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_late_insert_deadline_failure_rolls_back_attendance_but_audits_rejection` | All assertions passed | PASS |
| PY-049 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_loopback_cannot_authorize_attendance` | All assertions passed | PASS |
| PY-050 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_missing_disabled_or_invalid_policy_fail_closed` | All assertions passed | PASS |
| PY-051 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_missing_proof_and_client_pass_flags_cannot_write` | All assertions passed | PASS |
| PY-052 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_network_is_rechecked_on_final_request_and_spoofed_headers_ignored` | All assertions passed | PASS |
| PY-053 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_preflight_confirm_rechecks_connection_and_ignores_spoofed_header` | All assertions passed | PASS |
| PY-054 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_preflight_disabled_missing_invalid_policies_reject_before_camera` | All assertions passed | PASS |
| PY-055 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_preflight_invalid_signature_expiry_revoked_and_wrong_session_fail` | All assertions passed | PASS |
| PY-056 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_preflight_pass_then_device_revoked_still_rejects_final_write` | All assertions passed | PASS |
| PY-057 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_preflight_pass_then_policy_disabled_still_rejects_final_write` | All assertions passed | PASS |
| PY-058 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_preflight_passes_before_face_without_grant_or_attendance_and_cannot_replace_final_proof` | All assertions passed | PASS |
| PY-059 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_preflight_then_separate_final_proof_succeeds` | All assertions passed | PASS |
| PY-060 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_profile_device_pass_is_never_an_attendance_proof` | All assertions passed | PASS |
| PY-061 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_revocation_after_challenge_is_rechecked_at_the_insert_boundary` | All assertions passed | PASS |
| PY-062 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_success_uses_single_attempt_nonce_and_fresh_network_then_replay_fails` | All assertions passed | PASS |
| PY-063 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_unknown_revoked_or_pending_device_cannot_obtain_attendance_proof` | All assertions passed | PASS |
| PY-064 | `tests.test_attendance_authorization.AttendanceAuthorizationTests.test_wrong_student_or_login_cannot_issue_or_submit` | All assertions passed | PASS |
| PY-065 | `tests.test_attendance_ble_shadow.AttendanceBleShadowTests.test_admin_monitor_uses_real_attempts_and_redacts_evidence` | All assertions passed | PASS |
| PY-066 | `tests.test_attendance_ble_shadow.AttendanceBleShadowTests.test_binding_rejects_wrong_identity_classroom_device_attempt_and_signature` | All assertions passed | PASS |
| PY-067 | `tests.test_attendance_ble_shadow.AttendanceBleShadowTests.test_ble_pass_cannot_substitute_for_face_or_final_device_proof` | All assertions passed | PASS |
| PY-068 | `tests.test_attendance_ble_shadow.AttendanceBleShadowTests.test_missing_beacon_does_not_block_and_pass_cannot_bypass_wifi_or_network` | All assertions passed | PASS |
| PY-069 | `tests.test_attendance_ble_shadow.AttendanceBleShadowTests.test_missing_wrong_weak_stale_future_and_unavailable_are_non_authorizing` | All assertions passed | PASS |
| PY-070 | `tests.test_attendance_ble_shadow.AttendanceBleShadowTests.test_pass_binds_to_preflight_and_never_writes_attendance` | All assertions passed | PASS |
| PY-071 | `tests.test_attendance_ble_shadow.AttendanceBleShadowTests.test_wifi_only_classroom_records_not_configured_without_starting_scan` | All assertions passed | PASS |
| PY-072 | `tests.test_attendance_ble_shadow.AttendanceBleShadowTests.test_wrong_classroom_requires_wifi_before_beacon_can_be_not_detected` | All assertions passed | PASS |
| PY-073 | `tests.test_biometric_api_contract.BiometricContractTests.test_camera_contract_uses_authenticated_multipart_requests` | All assertions passed | PASS |
| PY-074 | `tests.test_biometric_api_contract.BiometricContractTests.test_exported_openapi_matches_the_application` | All assertions passed | PASS |
| PY-075 | `tests.test_biometric_api_contract.BiometricContractTests.test_face_verification_requires_head_movement_before_hand_challenge` | All assertions passed | PASS |
| PY-076 | `tests.test_biometric_api_contract.BiometricContractTests.test_result_contract_contains_no_template_or_teammate_verification_fields` | All assertions passed | PASS |
| PY-077 | `tests.test_biometric_api_contract.BiometricContractTests.test_student_template_deletion_is_not_exposed` | All assertions passed | PASS |
| PY-078 | `tests.test_biometric_inference.ImageProcessingTests.test_finger_geometry_is_mirror_invariant` | All assertions passed | PASS |
| PY-079 | `tests.test_biometric_inference.ImageProcessingTests.test_folded_fingers_are_not_treated_as_naturally_bent_open_fingers` | All assertions passed | PASS |
| PY-080 | `tests.test_biometric_inference.ImageProcessingTests.test_gesture_face_check_accepts_either_side_without_centering` | All assertions passed | PASS |
| PY-081 | `tests.test_biometric_inference.ImageProcessingTests.test_guided_face_rejects_off_center_or_badly_sized_faces` | All assertions passed | PASS |
| PY-082 | `tests.test_biometric_inference.ImageProcessingTests.test_hand_detection_distinguishes_missing_and_multiple_hands` | All assertions passed | PASS |
| PY-083 | `tests.test_biometric_inference.ImageProcessingTests.test_invalid_and_oversized_images_rejected` | All assertions passed | PASS |
| PY-084 | `tests.test_biometric_inference.ImageProcessingTests.test_naturally_bent_fingers_keep_their_count_across_camera_aspect_ratios` | All assertions passed | PASS |
| PY-085 | `tests.test_biometric_inference.ImageProcessingTests.test_real_image_decoding_and_face_rejection` | All assertions passed | PASS |
| PY-086 | `tests.test_biometric_inference.ImageProcessingTests.test_real_mediapipe_model_runs_and_rejects_missing_hand` | All assertions passed | PASS |
| PY-087 | `tests.test_ble_bundle.test_missing_app_local_dependencies_recovered_without_changing_original` | All assertions passed | PASS |
| PY-088 | `tests.test_ble_bundle.test_exact_cache_version_missing_does_not_choose_latest` | All assertions passed | PASS |
| PY-089 | `tests.test_ble_bundle.test_mismatched_assembly_version_rejected` | All assertions passed | PASS |
| PY-090 | `tests.test_ble_bundle.test_active_bundle_never_overwritten` | All assertions passed | PASS |
| PY-091 | `tests.test_ble_bundle.test_unexpected_manifest_runtime_library_rejected` | All assertions passed | PASS |
| PY-092 | `tests.test_ble_bundle.test_beacon_launch_uses_its_bundle_directory` | All assertions passed | PASS |
| PY-093 | `tests.test_ble_bundle.test_failed_publisher_exits_immediately_with_code_and_log` | All assertions passed | PASS |
| PY-094 | `tests.test_ble_bundle.test_healthy_existing_probe_reused_without_repackaging` | All assertions passed | PASS |
| PY-095 | `tests.test_ble_bundle.test_retries_in_same_second_have_distinct_publisher_logs` | All assertions passed | PASS |
| PY-096 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_authorized_final_commit_and_duplicate_preserves_single_attendance` | All assertions passed | PASS |
| PY-097 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_changed_requirement_revision_invalidates_snapshot` | All assertions passed | PASS |
| PY-098 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_concurrent_final_requests_insert_once_mariadb` | Not executed: MariaDB row-lock suite | NOT TESTED |
| PY-099 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_deadline_crossed_inside_writer_savepoint_rolls_back_attendance` | All assertions passed | PASS |
| PY-100 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_disabled_policy_after_wifi_pass_rejected_at_final_commit` | All assertions passed | PASS |
| PY-101 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_loopback_never_accepted_with_correct_wifi` | All assertions passed | PASS |
| PY-102 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_missing_proof_and_diagnostic_pass_do_not_authorize` | All assertions passed | PASS |
| PY-103 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_missing_wifi_proof_fail_closed` | All assertions passed | PASS |
| PY-104 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_multiple_bssids_and_optional_ssid` | All assertions passed | PASS |
| PY-105 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_nonce_expiry_and_replayed_confirmation` | All assertions passed | PASS |
| PY-106 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_permission_unavailable_malformed_ssid_and_stale_cannot_authorize` | All assertions passed | PASS |
| PY-107 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_preflight_checks_wifi_before_camera_and_not_final_authority` | All assertions passed | PASS |
| PY-108 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_refresh_after_long_biometric_delay_uses_new_reading` | All assertions passed | PASS |
| PY-109 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_requirement_immutable_during_attempt_and_removal_explicit` | All assertions passed | PASS |
| PY-110 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_same_authorized_ip_wrong_bssid_cannot_write` | All assertions passed | PASS |
| PY-111 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_session_creation_with_classroom_uses_existing_operator` | All assertions passed | PASS |
| PY-112 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_stale_receipt_after_biometric_delay_rejected_and_fresh_replacement_works` | All assertions passed | PASS |
| PY-113 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_wrong_attempt_receipt_cannot_cross_bind` | All assertions passed | PASS |
| PY-114 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_wrong_device_receipt_binding_rejected` | All assertions passed | PASS |
| PY-115 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_wrong_ip_correct_bssid_and_forwarding_spoof_cannot_write` | All assertions passed | PASS |
| PY-116 | `tests.test_classroom_attendance.ClassroomAttendanceTests.test_wrong_session_student_and_signature_rejected` | All assertions passed | PASS |
| PY-117 | `tests.test_classroom_ble.ClassroomBleTests.test_auth_classrooms_and_client_pass_rejected` | All assertions passed | PASS |
| PY-118 | `tests.test_classroom_ble.ClassroomBleTests.test_bluetooth_and_permissions_unavailable_are_uncertain` | All assertions passed | PASS |
| PY-119 | `tests.test_classroom_ble.ClassroomBleTests.test_captured_scan_completion_skew_passes_signed_verification` | All assertions passed | PASS |
| PY-120 | `tests.test_classroom_ble.ClassroomBleTests.test_concurrent_confirmations_consume_once_mariadb` | Not executed: Real MariaDB row locks | NOT TESTED |
| PY-121 | `tests.test_classroom_ble.ClassroomBleTests.test_disabled_or_changed_policy_after_issue_cannot_pass` | All assertions passed | PASS |
| PY-122 | `tests.test_classroom_ble.ClassroomBleTests.test_duplicate_copies_of_one_sample_rejected_but_equal_rssi_allowed` | All assertions passed | PASS |
| PY-123 | `tests.test_classroom_ble.ClassroomBleTests.test_duplicate_uuid_cannot_be_enabled_in_same_or_other_classroom` | All assertions passed | PASS |
| PY-124 | `tests.test_classroom_ble.ClassroomBleTests.test_expired_challenge_and_replay_rejected` | All assertions passed | PASS |
| PY-125 | `tests.test_classroom_ble.ClassroomBleTests.test_expired_session_rejects_scan_within_future_cap` | All assertions passed | PASS |
| PY-126 | `tests.test_classroom_ble.ClassroomBleTests.test_invalid_signature_consumes_challenge` | All assertions passed | PASS |
| PY-127 | `tests.test_classroom_ble.ClassroomBleTests.test_malformed_rssi_sample_bound_duration_and_client_median` | All assertions passed | PASS |
| PY-128 | `tests.test_classroom_ble.ClassroomBleTests.test_modifying_signed_timestamps_inside_future_cap_is_rejected` | All assertions passed | PASS |
| PY-129 | `tests.test_classroom_ble.ClassroomBleTests.test_multiple_approved_beacons_and_unrelated_ignored` | All assertions passed | PASS |
| PY-130 | `tests.test_classroom_ble.ClassroomBleTests.test_operator_commands_are_implemented_and_disabled_by_default` | All assertions passed | PASS |
| PY-131 | `tests.test_classroom_ble.ClassroomBleTests.test_policy_age_checked_for_each_sample` | All assertions passed | PASS |
| PY-132 | `tests.test_classroom_ble.ClassroomBleTests.test_policy_disabled_by_default_enable_disable_remove_preserves_audit` | All assertions passed | PASS |
| PY-133 | `tests.test_classroom_ble.ClassroomBleTests.test_positive_skew_cannot_extend_scan_or_sample_age` | All assertions passed | PASS |
| PY-134 | `tests.test_classroom_ble.ClassroomBleTests.test_same_report_resigned_under_another_preissued_nonce_rejected` | All assertions passed | PASS |
| PY-135 | `tests.test_classroom_ble.ClassroomBleTests.test_samples_insufficient_uncertain_weak_fail` | All assertions passed | PASS |
| PY-136 | `tests.test_classroom_ble.ClassroomBleTests.test_scan_must_fit_after_challenge_issuance` | All assertions passed | PASS |
| PY-137 | `tests.test_classroom_ble.ClassroomBleTests.test_signed_scan_wall_clock_boundaries_and_timezone_offset` | All assertions passed | PASS |
| PY-138 | `tests.test_classroom_ble.ClassroomBleTests.test_stale_and_future_timestamps_rejected` | All assertions passed | PASS |
| PY-139 | `tests.test_classroom_ble.ClassroomBleTests.test_start_plus_duration_cannot_exceed_future_cap` | All assertions passed | PASS |
| PY-140 | `tests.test_classroom_ble.ClassroomBleTests.test_valid_beacon_pass_median_recomputed_no_attendance` | All assertions passed | PASS |
| PY-141 | `tests.test_classroom_ble.ClassroomBleTests.test_wrong_student_session_classroom_and_inactive_device` | All assertions passed | PASS |
| PY-142 | `tests.test_classroom_ble.ClassroomBleTests.test_wrong_uuid_and_beacon_missing_fail` | All assertions passed | PASS |
| PY-143 | `tests.test_classroom_wifi.ClassroomWifiTests.test_authentication_fields_and_classroom_listing` | All assertions passed | PASS |
| PY-144 | `tests.test_classroom_wifi.ClassroomWifiTests.test_concurrent_submissions_one_success_mariadb` | Not executed: Real row-lock test runs in isolated MariaDB suite | NOT TESTED |
| PY-145 | `tests.test_classroom_wifi.ClassroomWifiTests.test_disable_retire_and_current_policy_rechecked_after_challenge` | All assertions passed | PASS |
| PY-146 | `tests.test_classroom_wifi.ClassroomWifiTests.test_evidence_tampering_rejected` | All assertions passed | PASS |
| PY-147 | `tests.test_classroom_wifi.ClassroomWifiTests.test_invalid_signature_consumes_challenge` | All assertions passed | PASS |
| PY-148 | `tests.test_classroom_wifi.ClassroomWifiTests.test_malformed_signed_json_and_audit` | All assertions passed | PASS |
| PY-149 | `tests.test_classroom_wifi.ClassroomWifiTests.test_migration_keeps_core_metadata_optional_and_data` | All assertions passed | PASS |
| PY-150 | `tests.test_classroom_wifi.ClassroomWifiTests.test_missing_permissions_and_location` | All assertions passed | PASS |
| PY-151 | `tests.test_classroom_wifi.ClassroomWifiTests.test_multiple_access_points_optional_ssid_and_no_rssi_gate` | All assertions passed | PASS |
| PY-152 | `tests.test_classroom_wifi.ClassroomWifiTests.test_operator_cli_add_list_enable_disable_retire_and_invalid_values` | All assertions passed | PASS |
| PY-153 | `tests.test_classroom_wifi.ClassroomWifiTests.test_replay_challenge_and_observation_resigned_under_new_nonce` | All assertions passed | PASS |
| PY-154 | `tests.test_classroom_wifi.ClassroomWifiTests.test_revoked_device_unknown_fingerprint_and_expiry` | All assertions passed | PASS |
| PY-155 | `tests.test_classroom_wifi.ClassroomWifiTests.test_stale_future_and_prechallenge_evidence` | All assertions passed | PASS |
| PY-156 | `tests.test_classroom_wifi.ClassroomWifiTests.test_two_active_slots_can_independently_submit_signed_observations` | All assertions passed | PASS |
| PY-157 | `tests.test_classroom_wifi.ClassroomWifiTests.test_unavailable_mobile_missing_and_malformed` | All assertions passed | PASS |
| PY-158 | `tests.test_classroom_wifi.ClassroomWifiTests.test_wrong_bssid_and_ssid` | All assertions passed | PASS |
| PY-159 | `tests.test_classroom_wifi.ClassroomWifiTests.test_wrong_student_and_session_cannot_consume_owner_challenge` | All assertions passed | PASS |
| PY-160 | `tests.test_device_activation.ActivationTests.test_approval_expiry_reuse_and_untrusted_result_are_rechecked_at_confirmation` | All assertions passed | PASS |
| PY-161 | `tests.test_device_activation.ActivationTests.test_both_slots_occupied_rejects_third_device` | All assertions passed | PASS |
| PY-162 | `tests.test_device_activation.ActivationTests.test_changed_candidate_or_approval_binding_after_issue` | All assertions passed | PASS |
| PY-163 | `tests.test_device_activation.ActivationTests.test_every_approval_binding_field_is_validated` | All assertions passed | PASS |
| PY-164 | `tests.test_device_activation.ActivationTests.test_expired_and_replayed_activation_challenges` | All assertions passed | PASS |
| PY-165 | `tests.test_device_activation.ActivationTests.test_expired_reused_and_untrusted_template_approvals` | All assertions passed | PASS |
| PY-166 | `tests.test_device_activation.ActivationTests.test_full_rest_flow_with_isolated_trusted_provider` | All assertions passed | PASS |
| PY-167 | `tests.test_device_activation.ActivationTests.test_invalid_signature_consumes_nonce_and_logs_failure` | All assertions passed | PASS |
| PY-168 | `tests.test_device_activation.ActivationTests.test_missing_and_untrusted_approvals_fail_closed` | All assertions passed | PASS |
| PY-169 | `tests.test_device_activation.ActivationTests.test_only_key_proven_and_unexpired_candidates_are_eligible` | All assertions passed | PASS |
| PY-170 | `tests.test_device_activation.ActivationTests.test_persisted_b3_test_id_cannot_be_relabelled_as_a_trusted_result` | All assertions passed | PASS |
| PY-171 | `tests.test_device_activation.ActivationTests.test_provider_consumption_rolls_back_with_failed_activation` | All assertions passed | PASS |
| PY-172 | `tests.test_device_activation.ActivationTests.test_real_provider_fails_closed_through_authenticated_public_routes` | All assertions passed | PASS |
| PY-173 | `tests.test_device_activation.ActivationTests.test_revision_or_template_change_after_issuance_is_rejected` | All assertions passed | PASS |
| PY-174 | `tests.test_device_activation.ActivationTests.test_slot_two_occupied_never_becomes_replacement_shortcut` | All assertions passed | PASS |
| PY-175 | `tests.test_device_activation.ActivationTests.test_trust_revision_switch_after_issuance_is_rejected` | All assertions passed | PASS |
| PY-176 | `tests.test_device_activation.ActivationTests.test_untrusted_or_mismatched_fresh_result_never_authorizes_activation` | All assertions passed | PASS |
| PY-177 | `tests.test_device_activation.ActivationTests.test_valid_atomic_activation_with_isolated_trusted_grant` | All assertions passed | PASS |
| PY-178 | `tests.test_device_activation.ActivationTests.test_wrong_pending_id_and_cross_operation_signature_are_rejected` | All assertions passed | PASS |
| PY-179 | `tests.test_device_activation.ActivationTests.test_wrong_student_or_new_login_cannot_consume_challenge` | All assertions passed | PASS |
| PY-180 | `tests.test_device_activation.ActivationMariaDBTests.test_parallel_activation_is_single_use_and_preserves_slot_one` | Not executed: Opt-in isolated MariaDB B4 races. | NOT TESTED |
| PY-181 | `tests.test_device_biometrics.DeviceBiometricTests.test_adjustment_codes_and_safe_correlated_logs` | All assertions passed | PASS |
| PY-182 | `tests.test_device_biometrics.DeviceBiometricTests.test_candidate_binding_mismatch_is_rejected` | All assertions passed | PASS |
| PY-183 | `tests.test_device_biometrics.DeviceBiometricTests.test_controlled_randomness_covers_all_five_fresh_challenges` | All assertions passed | PASS |
| PY-184 | `tests.test_device_biometrics.DeviceBiometricTests.test_expiry_and_slow_inference_never_produce_pass` | All assertions passed | PASS |
| PY-185 | `tests.test_device_biometrics.DeviceBiometricTests.test_face_substitution_during_liveness_fails` | All assertions passed | PASS |
| PY-186 | `tests.test_device_biometrics.DeviceBiometricTests.test_frame_budget_and_audit_results` | All assertions passed | PASS |
| PY-187 | `tests.test_device_biometrics.DeviceBiometricTests.test_inference_unavailable_is_audited_and_never_passes` | All assertions passed | PASS |
| PY-188 | `tests.test_device_biometrics.DeviceBiometricTests.test_liveness_wrong_gesture_resets_then_can_recover` | All assertions passed | PASS |
| PY-189 | `tests.test_device_biometrics.DeviceBiometricTests.test_missing_unproven_and_expired_pending_are_rejected` | All assertions passed | PASS |
| PY-190 | `tests.test_device_biometrics.DeviceBiometricTests.test_quality_error_and_rate_limits` | All assertions passed | PASS |
| PY-191 | `tests.test_device_biometrics.DeviceBiometricTests.test_random_challenge_is_server_generated_and_begin_retry_is_idempotent` | All assertions passed | PASS |
| PY-192 | `tests.test_device_biometrics.DeviceBiometricTests.test_replayed_frame_and_completed_session_cannot_advance_again` | All assertions passed | PASS |
| PY-193 | `tests.test_device_biometrics.DeviceBiometricTests.test_session_reuse_keeps_one_gesture_and_three_frames_do_not_reroll` | All assertions passed | PASS |
| PY-194 | `tests.test_device_biometrics.DeviceBiometricTests.test_success_remains_untrusted_nonconsumable_and_creates_no_attendance` | All assertions passed | PASS |
| PY-195 | `tests.test_device_biometrics.DeviceBiometricTests.test_template_replacement_invalidates_existing_test` | All assertions passed | PASS |
| PY-196 | `tests.test_device_biometrics.DeviceBiometricTests.test_wrong_face_is_terminal_and_no_client_pass_flag_is_accepted` | All assertions passed | PASS |
| PY-197 | `tests.test_device_biometrics.DeviceBiometricTests.test_wrong_gesture_resets_progress_without_generating_a_new_challenge` | All assertions passed | PASS |
| PY-198 | `tests.test_device_biometrics.DeviceBiometricTests.test_wrong_student_session_and_unknown_pending_are_rejected` | All assertions passed | PASS |
| PY-199 | `tests.test_device_biometrics.DeviceBiometricMariaDBTests.test_concurrent_creation_and_frame_replay_and_migration` | Not executed: Isolated MariaDB B3 concurrency. | NOT TESTED |
| PY-200 | `tests.test_device_frame_orientation.DeviceFrameOrientationTests.test_all_jpeg_exif_orientations_are_upright_before_inference` | All assertions passed | PASS |
| PY-201 | `tests.test_device_management.ManagementTests.test_expired_grant_and_challenge_cannot_activate` | All assertions passed | PASS |
| PY-202 | `tests.test_device_management.ManagementTests.test_face_deletion_and_reenrollment_stay_blocked` | All assertions passed | PASS |
| PY-203 | `tests.test_device_management.ManagementTests.test_failed_insert_rolls_back_local_approval_consumption` | All assertions passed | PASS |
| PY-204 | `tests.test_device_management.ManagementTests.test_forged_device_identity_and_wrong_operation_are_rejected` | All assertions passed | PASS |
| PY-205 | `tests.test_device_management.ManagementTests.test_invalid_signature_consumes_activation_challenge` | All assertions passed | PASS |
| PY-206 | `tests.test_device_management.ManagementTests.test_invalidated_or_changed_template_during_scan_cannot_get_grant` | All assertions passed | PASS |
| PY-207 | `tests.test_device_management.ManagementTests.test_local_demo_activates_only_bound_slot2_and_is_disabled_without_credential` | All assertions passed | PASS |
| PY-208 | `tests.test_device_management.ManagementTests.test_local_slot1_replacement_revokes_old_key_preserves_slot2` | All assertions passed | PASS |
| PY-209 | `tests.test_device_management.ManagementTests.test_local_slot2_replacement_revokes_old_key_preserves_slot1` | All assertions passed | PASS |
| PY-210 | `tests.test_device_management.ManagementTests.test_microsecond_clock_progress_does_not_lose_genuine_completion` | All assertions passed | PASS |
| PY-211 | `tests.test_device_management.ManagementTests.test_migration_rejects_production_endpoint_before_connecting` | All assertions passed | PASS |
| PY-212 | `tests.test_device_management.ManagementTests.test_missing_biometric_proof_is_rejected_even_with_provenance` | All assertions passed | PASS |
| PY-213 | `tests.test_device_management.ManagementTests.test_schema_compiles_for_mysql_and_runtime_cannot_write_enrollment_trust` | All assertions passed | PASS |
| PY-214 | `tests.test_device_management.ManagementTests.test_self_enrolled_face_does_not_get_provenance_or_authorization` | All assertions passed | PASS |
| PY-215 | `tests.test_device_management.ManagementTests.test_signed_supervised_reverification_requires_a_new_scan_and_preserves_slot_one` | All assertions passed | PASS |
| PY-216 | `tests.test_device_management.ManagementTests.test_slot2_full_flow_with_local_provider_and_independent_keys` | All assertions passed | PASS |
| PY-217 | `tests.test_device_management.ManagementTests.test_storage_missing_fails_closed_without_breaking_raw_biometric_checks` | All assertions passed | PASS |
| PY-218 | `tests.test_device_management.ManagementTests.test_supervised_evidence_rejects_untrusted_signature_stale_scan_and_changed_template` | All assertions passed | PASS |
| PY-219 | `tests.test_device_management.ManagementTests.test_synthetic_provenance_without_isolated_session_marker_is_not_trust` | All assertions passed | PASS |
| PY-220 | `tests.test_device_management.ManagementTests.test_third_device_and_initial_api_shortcut_remain_blocked` | All assertions passed | PASS |
| PY-221 | `tests.test_device_management.ManagementTests.test_trust_added_after_completed_scan_cannot_relabel_old_result` | All assertions passed | PASS |
| PY-222 | `tests.test_device_management.ManagementTests.test_wrong_face_cannot_issue_authorization` | All assertions passed | PASS |
| PY-223 | `tests.test_device_management.ManagementTests.test_wrong_operation_in_approval_binding_fails` | All assertions passed | PASS |
| PY-224 | `tests.test_device_management.ManagementTests.test_wrong_student_session_and_client_pass_are_rejected` | All assertions passed | PASS |
| PY-225 | `tests.test_device_registration.DeviceRegistrationTests.test_all_routes_require_authentication` | All assertions passed | PASS |
| PY-226 | `tests.test_device_registration.DeviceRegistrationTests.test_challenge_cannot_cross_accounts_or_logins` | All assertions passed | PASS |
| PY-227 | `tests.test_device_registration.DeviceRegistrationTests.test_challenge_rate_limit` | All assertions passed | PASS |
| PY-228 | `tests.test_device_registration.DeviceRegistrationTests.test_client_flags_private_key_and_non_android_are_rejected` | All assertions passed | PASS |
| PY-229 | `tests.test_device_registration.DeviceRegistrationTests.test_duplicate_does_not_replace_registered_key` | All assertions passed | PASS |
| PY-230 | `tests.test_device_registration.DeviceRegistrationTests.test_expiry_consumes_challenge_and_preserves_failed_audit` | All assertions passed | PASS |
| PY-231 | `tests.test_device_registration.DeviceRegistrationTests.test_invalid_key_and_wrong_curve_are_rejected` | All assertions passed | PASS |
| PY-232 | `tests.test_device_registration.DeviceRegistrationTests.test_key_cannot_be_registered_to_another_account` | All assertions passed | PASS |
| PY-233 | `tests.test_device_registration.DeviceRegistrationTests.test_logout_prevents_confirmation` | All assertions passed | PASS |
| PY-234 | `tests.test_device_registration.DeviceRegistrationTests.test_malformed_signature_is_denied` | All assertions passed | PASS |
| PY-235 | `tests.test_device_registration.DeviceRegistrationTests.test_migration_is_additive_idempotent_and_preserves_existing_rows` | All assertions passed | PASS |
| PY-236 | `tests.test_device_registration.DeviceRegistrationTests.test_replaced_pending_challenge_cannot_be_confirmed` | All assertions passed | PASS |
| PY-237 | `tests.test_device_registration.DeviceRegistrationTests.test_replay_is_rejected_and_logged` | All assertions passed | PASS |
| PY-238 | `tests.test_device_registration.DeviceRegistrationTests.test_success_persists_public_key_and_audit_without_attendance` | All assertions passed | PASS |
| PY-239 | `tests.test_device_registration.DeviceRegistrationTests.test_tampered_operation_payload_cannot_be_signed_instead` | All assertions passed | PASS |
| PY-240 | `tests.test_device_registration.DeviceRegistrationTests.test_wrong_signature_consumes_nonce` | All assertions passed | PASS |
| PY-241 | `tests.test_device_registration.MySQLDeviceConcurrencyTests.test_parallel_confirmation_and_shared_key_race` | Not executed: Opt-in: disposable MySQL registration concurrency schema. | NOT TESTED |
| PY-242 | `tests.test_device_replacement.ReplacementTests.test_cancelled_inflight_activation_cannot_revoke_target` | All assertions passed | PASS |
| PY-243 | `tests.test_device_replacement.ReplacementTests.test_duplicate_conflict_cancel_and_restart` | All assertions passed | PASS |
| PY-244 | `tests.test_device_replacement.ReplacementTests.test_expired_consumed_or_invalid_revision_approval_preserves_old_device` | All assertions passed | PASS |
| PY-245 | `tests.test_device_replacement.ReplacementTests.test_failed_face_ends_pending_replacement_without_revocation` | All assertions passed | PASS |
| PY-246 | `tests.test_device_replacement.ReplacementTests.test_insert_failure_rolls_back_revocation_and_grant` | All assertions passed | PASS |
| PY-247 | `tests.test_device_replacement.ReplacementTests.test_invalid_proof_and_expiry` | All assertions passed | PASS |
| PY-248 | `tests.test_device_replacement.ReplacementTests.test_mutated_slot_or_old_fingerprint_rejected` | All assertions passed | PASS |
| PY-249 | `tests.test_device_replacement.ReplacementTests.test_replacement_biometrics_reuse_untrusted_workflow` | All assertions passed | PASS |
| PY-250 | `tests.test_device_replacement.ReplacementTests.test_session_signature_expiry_replay_and_changed_target` | All assertions passed | PASS |
| PY-251 | `tests.test_device_replacement.ReplacementTests.test_slot_one_replacement_and_revoked_proof_rejection` | All assertions passed | PASS |
| PY-252 | `tests.test_device_replacement.ReplacementTests.test_slot_two_replacement_preserves_slot_one` | All assertions passed | PASS |
| PY-253 | `tests.test_device_replacement.ReplacementTests.test_unavailable_untrusted_and_wrong_binding_fail_closed` | All assertions passed | PASS |
| PY-254 | `tests.test_device_replacement.ReplacementTests.test_wrong_student_slot_and_existing_key_rejected` | All assertions passed | PASS |
| PY-255 | `tests.test_device_replacement.ReplacementMariaDBTests.test_serialized_replacements_and_activation_replay` | Not executed: Opt-in isolated MariaDB replacement race | NOT TESTED |
| PY-256 | `tests.test_device_verification.DeviceVerificationTests.test_all_routes_require_authentication` | All assertions passed | PASS |
| PY-257 | `tests.test_device_verification.DeviceVerificationTests.test_challenge_cannot_cross_account_or_login` | All assertions passed | PASS |
| PY-258 | `tests.test_device_verification.DeviceVerificationTests.test_changed_registration_key_denied` | All assertions passed | PASS |
| PY-259 | `tests.test_device_verification.DeviceVerificationTests.test_client_failure_cannot_cancel_another_login` | All assertions passed | PASS |
| PY-260 | `tests.test_device_verification.DeviceVerificationTests.test_client_key_failure_is_negative_untrusted_telemetry_only` | All assertions passed | PASS |
| PY-261 | `tests.test_device_verification.DeviceVerificationTests.test_corrupt_registered_public_key_cannot_pass` | All assertions passed | PASS |
| PY-262 | `tests.test_device_verification.DeviceVerificationTests.test_expiry_consumes_challenge` | All assertions passed | PASS |
| PY-263 | `tests.test_device_verification.DeviceVerificationTests.test_independent_concurrent_operations_do_not_supersede_each_other` | All assertions passed | PASS |
| PY-264 | `tests.test_device_verification.DeviceVerificationTests.test_invalid_signature_is_terminal_and_logged` | All assertions passed | PASS |
| PY-265 | `tests.test_device_verification.DeviceVerificationTests.test_issuance_rate_limit` | All assertions passed | PASS |
| PY-266 | `tests.test_device_verification.DeviceVerificationTests.test_logout_blocks_verification` | All assertions passed | PASS |
| PY-267 | `tests.test_device_verification.DeviceVerificationTests.test_malformed_signature_is_rejected` | All assertions passed | PASS |
| PY-268 | `tests.test_device_verification.DeviceVerificationTests.test_migration_preserves_phase_one_public_key` | All assertions passed | PASS |
| PY-269 | `tests.test_device_verification.DeviceVerificationTests.test_non_active_device_denied_at_issuance_and_confirmation` | All assertions passed | PASS |
| PY-270 | `tests.test_device_verification.DeviceVerificationTests.test_operation_mismatch_is_denied` | All assertions passed | PASS |
| PY-271 | `tests.test_device_verification.DeviceVerificationTests.test_pass_is_fresh_bound_and_never_attendance_authorization` | All assertions passed | PASS |
| PY-272 | `tests.test_device_verification.DeviceVerificationTests.test_replay_does_not_overwrite_original_pass` | All assertions passed | PASS |
| PY-273 | `tests.test_device_verification.DeviceVerificationTests.test_signature_work_cannot_cross_deadline` | All assertions passed | PASS |
| PY-274 | `tests.test_device_verification.DeviceVerificationTests.test_signed_payload_tampering_cannot_pass` | All assertions passed | PASS |
| PY-275 | `tests.test_device_verification.DeviceVerificationTests.test_unregistered_student_gets_failed_audit` | All assertions passed | PASS |
| PY-276 | `tests.test_device_verification.DeviceVerificationTests.test_unsupported_attendance_operation_and_pass_flags_rejected` | All assertions passed | PASS |
| PY-277 | `tests.test_device_verification.MySQLVerificationConcurrencyTests.test_same_nonce_and_failure_vs_pass_races` | Not executed: Opt-in disposable MySQL verification races. | NOT TESTED |
| PY-278 | `tests.test_disposable_processes.ProcessIdentityTests.test_exited_pid_and_free_port_retire_stale_state` | All assertions passed | PASS |
| PY-279 | `tests.test_disposable_processes.ProcessIdentityTests.test_foreign_owner_of_8002_still_fails_closed` | All assertions passed | PASS |
| PY-280 | `tests.test_disposable_processes.ProcessIdentityTests.test_forward_and_backward_slashes_are_equivalent` | All assertions passed | PASS |
| PY-281 | `tests.test_disposable_processes.ProcessIdentityTests.test_inspection_failure_does_not_erase_identity` | All assertions passed | PASS |
| PY-282 | `tests.test_disposable_processes.ProcessIdentityTests.test_legacy_valid_pid_upgrades_to_birth_and_executable` | All assertions passed | PASS |
| PY-283 | `tests.test_disposable_processes.ProcessIdentityTests.test_missing_state_can_adopt_exact_owned_listener` | All assertions passed | PASS |
| PY-284 | `tests.test_disposable_processes.ProcessIdentityTests.test_parallel_cli_lock_is_rejected_and_released` | All assertions passed | PASS |
| PY-285 | `tests.test_disposable_processes.ProcessIdentityTests.test_recycled_pid_pointing_to_port8000_process_is_never_controlled` | All assertions passed | PASS |
| PY-286 | `tests.test_disposable_processes.ProcessIdentityTests.test_reused_pid_observer_detects_original_exit` | All assertions passed | PASS |
| PY-287 | `tests.test_disposable_processes.ProcessIdentityTests.test_substring_in_unrelated_command_is_not_ownership` | All assertions passed | PASS |
| PY-288 | `tests.test_disposable_processes.ProcessIdentityTests.test_unreadable_live_identity_is_not_classified_as_stale` | All assertions passed | PASS |
| PY-289 | `tests.test_disposable_processes.ProcessIdentityTests.test_valid_stored_pid_does_not_hide_foreign_listener` | All assertions passed | PASS |
| PY-290 | `tests.test_fyp_operator.test_cold_start_order_and_stop_preserves_shared_services` | All assertions passed | PASS |
| PY-291 | `tests.test_fyp_operator.test_healthy_services_reused_never_adopted_for_shutdown` | All assertions passed | PASS |
| PY-292 | `tests.test_fyp_operator.test_duplicate_backends_block_before_any_new_launch` | All assertions passed | PASS |
| PY-293 | `tests.test_fyp_operator.test_wrong_database_never_launches_backend_or_gateway` | All assertions passed | PASS |
| PY-294 | `tests.test_fyp_operator.test_database_start_requires_confirmation_and_no_database_ownership` | All assertions passed | PASS |
| PY-295 | `tests.test_fyp_operator.test_missing_beacon_reports_failure_without_substitution` | All assertions passed | PASS |
| PY-296 | `tests.test_fyp_operator.test_changing_lan_ip_used_for_install_and_explicit_device_selection` | All assertions passed | PASS |
| PY-297 | `tests.test_fyp_operator.test_device_selection_does_not_choose_other_or_ambiguous_device` | All assertions passed | PASS |
| PY-298 | `tests.test_fyp_operator.test_missing_adb_stops_before_install` | All assertions passed | PASS |
| PY-299 | `tests.test_fyp_operator.test_recycled_pid_never_stopped_and_state_retained` | All assertions passed | PASS |
| PY-300 | `tests.test_fyp_operator.test_tampered_stored_command_cannot_stop_unrelated_program` | All assertions passed | PASS |
| PY-301 | `tests.test_fyp_operator.test_diagnostic_mode_true_refuses_existing_backend` | All assertions passed | PASS |
| PY-302 | `tests.test_fyp_operator.test_cloudflare_token_is_not_saved_and_mapping_changes_rejected` | All assertions passed | PASS |
| PY-303 | `tests.test_fyp_operator.test_native_stop_rejects_wrong_creation_time_before_any_windows_termination` | All assertions passed | PASS |
| PY-304 | `tests.test_fyp_operator.test_wrong_listener_binding_never_reused` | All assertions passed | PASS |
| PY-305 | `tests.test_fyp_operator.test_owned_venv_listener_child_recorded_separately` | All assertions passed | PASS |
| PY-306 | `tests.test_fyp_operator.test_service_ownership_not_recorded_when_already_running` | All assertions passed | PASS |
| PY-307 | `tests.test_fyp_operator.test_cloudflare_stopped_requires_manual_service_action_without_launch` | All assertions passed | PASS |
| PY-308 | `tests.test_fyp_operator.test_host_launch_forces_diagnostic_off_and_hidden_logs` | All assertions passed | PASS |
| PY-309 | `tests.test_fyp_operator.test_public_config_mismatch_blocks_install_without_any_adb_action` | All assertions passed | PASS |
| PY-310 | `tests.test_fyp_operator.test_protected_service_token_file_not_read_and_metadata_change_blocks` | All assertions passed | PASS |
| PY-311 | `tests.test_fyp_operator.test_token_file_parser_never_reads_protected_contents` | All assertions passed | PASS |
| PY-312 | `tests.test_fyp_operator.test_readiness_failure_has_bounded_deadline` | All assertions passed | PASS |
| PY-313 | `tests.test_fyp_operator.test_install_signature_failure_reports_no_destructive_recovery` | All assertions passed | PASS |
| PY-314 | `tests.test_fyp_operator.test_install_before_start_is_actionable_and_never_builds_or_installs` | All assertions passed | PASS |
| PY-315 | `tests.test_fyp_operator.test_nested_installer_process_policy_handles_exact_disabled_scripts_failure` | All assertions passed | PASS |
| PY-316 | `tests.test_fyp_operator.test_enforced_child_policy_failure_stops_without_retry_or_device_commands` | All assertions passed | PASS |
| PY-317 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_add_requires_explicit_simulation_and_id` | All assertions passed | PASS |
| PY-318 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_bad_cidr_and_bad_restore_do_not_change_committed_policy` | All assertions passed | PASS |
| PY-319 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_cli_requires_explicit_simulation_for_setting_a_policy` | All assertions passed | PASS |
| PY-320 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_disable_one_id_does_not_disable_other_cidr` | All assertions passed | PASS |
| PY-321 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_duplicate_add_and_missing_id_do_not_overwrite_policy` | All assertions passed | PASS |
| PY-322 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_export_restore_preserves_audits_and_other_policy_rows` | All assertions passed | PASS |
| PY-323 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_id_scoped_restore_and_ipv6_range` | All assertions passed | PASS |
| PY-324 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_login_profile_independent_for_two_devices_with_different_network_results` | All assertions passed | PASS |
| PY-325 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_loopback_and_spoofed_forwarding_never_gain_attendance_authorization` | All assertions passed | PASS |
| PY-326 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_multi_cidr_login_profile_independent_after_one_is_disabled` | All assertions passed | PASS |
| PY-327 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_non_simulation_policies_are_not_mutable_by_test_manager` | All assertions passed | PASS |
| PY-328 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_policy_change_enable_disable_and_committed_state` | All assertions passed | PASS |
| PY-329 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_remove_disables_and_retains_prior_verification_and_audit` | All assertions passed | PASS |
| PY-330 | `tests.test_fyp_test_workflow.SimpleNetworkWorkflowTests.test_two_simultaneous_cidrs_match_independently_and_outside_fails` | All assertions passed | PASS |
| PY-331 | `tests.test_head_movement.HeadGeometryTests.test_action_selection_uses_secure_sampling_and_excludes_eye_closure_holds` | All assertions passed | PASS |
| PY-332 | `tests.test_head_movement.HeadGeometryTests.test_direction_and_pitch_limits_cannot_be_satisfied_by_tilt_or_invalid_values` | All assertions passed | PASS |
| PY-333 | `tests.test_head_movement.HeadGeometryTests.test_expression_scores_require_valid_bilateral_eyes_without_jaw_output` | All assertions passed | PASS |
| PY-334 | `tests.test_head_movement.HeadGeometryTests.test_real_model_rejects_blank_scene` | All assertions passed | PASS |
| PY-335 | `tests.test_head_movement.HeadGeometryTests.test_transform_reports_signed_turns_without_translation_or_scale_effects` | All assertions passed | PASS |
| PY-336 | `tests.test_head_movement.HeadWorkflowTests.test_brief_blink_requires_open_blink_and_reopened_eyes` | All assertions passed | PASS |
| PY-337 | `tests.test_head_movement.HeadWorkflowTests.test_cancel_discards_head_evidence` | All assertions passed | PASS |
| PY-338 | `tests.test_head_movement.HeadWorkflowTests.test_closed_eyes_alone_or_a_sustained_hold_cannot_complete_blink` | All assertions passed | PASS |
| PY-339 | `tests.test_head_movement.HeadWorkflowTests.test_expiry_during_head_inference_never_advances` | All assertions passed | PASS |
| PY-340 | `tests.test_head_movement.HeadWorkflowTests.test_forged_success_fields_and_preview_flag_cannot_skip_head_actions` | All assertions passed | PASS |
| PY-341 | `tests.test_head_movement.HeadWorkflowTests.test_hand_stage_requires_completed_head_proof` | All assertions passed | PASS |
| PY-342 | `tests.test_head_movement.HeadWorkflowTests.test_head_match_is_still_bound_to_identity_and_presentation_checks` | All assertions passed | PASS |
| PY-343 | `tests.test_head_movement.HeadWorkflowTests.test_head_sequence_must_finish_before_fingers_and_never_records_attendance_itself` | All assertions passed | PASS |
| PY-344 | `tests.test_head_movement.HeadWorkflowTests.test_instant_burst_cannot_complete_hold_and_wrong_pose_resets_it` | All assertions passed | PASS |
| PY-345 | `tests.test_head_movement.HeadWorkflowTests.test_model_failure_fails_closed` | All assertions passed | PASS |
| PY-346 | `tests.test_head_movement.HeadWorkflowTests.test_one_eye_wink_does_not_satisfy_bilateral_blink` | All assertions passed | PASS |
| PY-347 | `tests.test_head_movement.HeadWorkflowTests.test_other_student_cannot_submit_head_frames_to_the_original_challenge` | All assertions passed | PASS |
| PY-348 | `tests.test_head_movement.HeadWorkflowTests.test_replaying_the_same_pixels_resets_hold` | All assertions passed | PASS |
| PY-349 | `tests.test_head_movement.HeadWorkflowTests.test_restart_and_cache_database_mismatch_require_new_challenge` | All assertions passed | PASS |
| PY-350 | `tests.test_head_movement.HeadWorkflowTests.test_up_down_and_turn_sequence_completes_before_fingers` | All assertions passed | PASS |
| PY-351 | `tests.test_lan_discovery.test_explicit_new_identity_and_no_overwrite` | All assertions passed | PASS |
| PY-352 | `tests.test_lan_discovery.test_wrong_environment_or_database_rejected[Local-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]` | All assertions passed | PASS |
| PY-353 | `tests.test_lan_discovery.test_wrong_environment_or_database_rejected[Full-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb]` | All assertions passed | PASS |
| PY-354 | `tests.test_lan_discovery.test_unrelated_network_addresses_rejected[127.0.0.1]` | All assertions passed | PASS |
| PY-355 | `tests.test_lan_discovery.test_unrelated_network_addresses_rejected[0.0.0.0]` | All assertions passed | PASS |
| PY-356 | `tests.test_lan_discovery.test_unrelated_network_addresses_rejected[8.8.8.8]` | All assertions passed | PASS |
| PY-357 | `tests.test_lan_discovery.test_unrelated_network_addresses_rejected[169.254.1.3]` | All assertions passed | PASS |
| PY-358 | `tests.test_lan_discovery.test_unrelated_network_addresses_rejected[::1]` | All assertions passed | PASS |
| PY-359 | `tests.test_lan_discovery.test_unrelated_network_addresses_rejected[224.0.0.251]` | All assertions passed | PASS |
| PY-360 | `tests.test_lan_discovery.test_private_wifi_hint[192.168.0.162]` | All assertions passed | PASS |
| PY-361 | `tests.test_lan_discovery.test_private_wifi_hint[10.46.58.220]` | All assertions passed | PASS |
| PY-362 | `tests.test_lan_discovery.test_private_wifi_hint[172.16.2.8]` | All assertions passed | PASS |
| PY-363 | `tests.test_lan_discovery.test_tls_config_loads_private_ca_and_key` | All assertions passed | PASS |
| PY-364 | `tests.test_lan_discovery.test_identity_tls_only_and_asgi_source_preserved` | All assertions passed | PASS |
| PY-365 | `tests.test_lan_discovery.test_public_allowlist_unchanged_for_authenticated_discovery_and_security` | All assertions passed | PASS |
| PY-366 | `tests.test_lan_discovery.test_legacy_launch_unchanged_without_profile` | All assertions passed | PASS |
| PY-367 | `tests.test_lan_discovery.test_partial_provisioning_fails_closed` | All assertions passed | PASS |
| PY-368 | `tests.test_lan_discovery.test_launcher_rejects_unrelated_tls_process` | All assertions passed | PASS |
| PY-369 | `tests.test_lan_discovery.test_installer_only_exports_public_trust_never_provisions` | All assertions passed | PASS |
| PY-370 | `tests.test_lan_discovery.test_advertisement_is_interface_bound_and_contains_no_private_identity` | All assertions passed | PASS |
| PY-371 | `tests.test_lan_discovery.test_lifecycle_rebind_and_cleanup_stay_in_same_process` | All assertions passed | PASS |
| PY-372 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_explicit_disposable_profile` | All assertions passed | PASS |
| PY-373 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_lan_listener_requires_current_private_interface_and_matching_prefix` | All assertions passed | PASS |
| PY-374 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_lan_requires_explicit_rfc1918_subnet` | All assertions passed | PASS |
| PY-375 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_lan_selection_has_no_per_device_configuration` | All assertions passed | PASS |
| PY-376 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_native_server_cannot_select_production_port_paths_or_init_file` | All assertions passed | PASS |
| PY-377 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_no_missing_or_extra_profile_fields` | All assertions passed | PASS |
| PY-378 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_policy_and_algorithm_changes_rejected` | All assertions passed | PASS |
| PY-379 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_production_data_directory_and_weak_secret_rejected` | All assertions passed | PASS |
| PY-380 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_production_endpoint_root_and_schema_rejected` | All assertions passed | PASS |
| PY-381 | `tests.test_manual_android_config.ManualAndroidConfigTests.test_subprocess_guard_proves_ipv4_ipv6_localhost_denial_without_connecting` | All assertions passed | PASS |
| PY-382 | `tests.test_manual_sessions.ManualSessionTests.test_bad_duration_expiry_and_midnight_are_rejected` | All assertions passed | PASS |
| PY-383 | `tests.test_manual_sessions.ManualSessionTests.test_close_is_seen_by_attendance_boundary_even_with_cached_session` | All assertions passed | PASS |
| PY-384 | `tests.test_manual_sessions.ManualSessionTests.test_close_preserves_history_and_allows_a_new_session` | All assertions passed | PASS |
| PY-385 | `tests.test_manual_sessions.ManualSessionTests.test_concurrent_creations_serialize_on_group_in_mariadb` | Not executed: MariaDB row-lock integration only | NOT TESTED |
| PY-386 | `tests.test_manual_sessions.ManualSessionTests.test_elapsed_sessions_hidden_but_available_in_all_listing` | All assertions passed | PASS |
| PY-387 | `tests.test_manual_sessions.ManualSessionTests.test_expire_is_safe_and_idempotent` | All assertions passed | PASS |
| PY-388 | `tests.test_manual_sessions.ManualSessionTests.test_explicit_expiry_converts_to_backend_timezone` | All assertions passed | PASS |
| PY-389 | `tests.test_manual_sessions.ManualSessionTests.test_failed_transaction_does_not_create_a_session` | All assertions passed | PASS |
| PY-390 | `tests.test_manual_sessions.ManualSessionTests.test_generated_pin_is_hashed_and_not_in_session_list` | All assertions passed | PASS |
| PY-391 | `tests.test_manual_sessions.ManualSessionTests.test_missing_class_and_wrong_group_are_rejected` | All assertions passed | PASS |
| PY-392 | `tests.test_manual_sessions.ManualSessionTests.test_overlap_rejected_without_replacing_first_session` | All assertions passed | PASS |
| PY-393 | `tests.test_manual_sessions.ManualSessionTests.test_stopped_backend_reports_actionable_error_without_http` | All assertions passed | PASS |
| PY-394 | `tests.test_migrations.MigrationTests.test_fresh_schema_and_empty_database_need_no_pad_column` | All assertions passed | PASS |
| PY-395 | `tests.test_migrations.MigrationTests.test_retiring_device_columns_preserves_biometrics_sessions_and_attendance` | All assertions passed | PASS |
| PY-396 | `tests.test_migrations.MigrationTests.test_retiring_pad_column_preserves_existing_challenges` | All assertions passed | PASS |
| PY-397 | `tests.test_mysql_integration.MySQLSessionTests.test_logout_revocation_is_visible_immediately` | Not executed: Set ATTENDANCE_API_URL to run the live MySQL regression. | NOT TESTED |
| PY-398 | `tests.test_mysql_profiles.MySQLProfileTests.test_actual_connection_identity_rejects_vendor_version_port_schema_account_uuid_and_paths` | All assertions passed | PASS |
| PY-399 | `tests.test_mysql_profiles.MySQLProfileTests.test_charset_reflection_normalization_keeps_checks` | All assertions passed | PASS |
| PY-400 | `tests.test_mysql_profiles.MySQLProfileTests.test_exact_profile_accepted` | All assertions passed | PASS |
| PY-401 | `tests.test_mysql_profiles.MySQLProfileTests.test_network_guard_blocks_ipv4_ipv6_localhost_production_before_connection` | All assertions passed | PASS |
| PY-402 | `tests.test_mysql_profiles.MySQLProfileTests.test_unknown_fields_rejected` | All assertions passed | PASS |
| PY-403 | `tests.test_mysql_profiles.MySQLProfileTests.test_vendor_version_host_schema_directory_and_policy_mismatches_rejected` | All assertions passed | PASS |
| PY-404 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_admin_test_table_requires_login_and_redacts_payloads` | All assertions passed | PASS |
| PY-405 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_ble_skew_cap_staleness_and_expiry_preserved` | All assertions passed | PASS |
| PY-406 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_disabled_by_default_and_routes_require_authentication` | All assertions passed | PASS |
| PY-407 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_missing_wrong_weak_insufficient_and_bluetooth_off_fail` | All assertions passed | PASS |
| PY-408 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_replay_cross_test_and_signature_tampering_rejected` | All assertions passed | PASS |
| PY-409 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_same_evidence_resigned_under_a_new_test_nonce_is_rejected` | All assertions passed | PASS |
| PY-410 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_session_pin_classroom_and_device_validation` | All assertions passed | PASS |
| PY-411 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_valid_session_pin_wifi_device_and_beacon_return_only_test_pass` | All assertions passed | PASS |
| PY-412 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_wifi_failure_and_network_changes_fail_closed` | All assertions passed | PASS |
| PY-413 | `tests.test_network_ble_test_mode.NetworkBleTestModeTests.test_wrong_student_login_and_disabled_cidr_cannot_produce_test_pass` | All assertions passed | PASS |
| PY-414 | `tests.test_network_verification.NetworkTests.test_actual_socket_ignores_spoofed_forwarded_header` | All assertions passed | PASS |
| PY-415 | `tests.test_network_verification.NetworkTests.test_authorized_asgi_peers_and_forged_vendor_header` | All assertions passed | PASS |
| PY-416 | `tests.test_network_verification.NetworkTests.test_authorized_pass_has_server_policy_audit_and_zero_attendance` | All assertions passed | PASS |
| PY-417 | `tests.test_network_verification.NetworkTests.test_fake_wifi_claims_never_authorize_network` | All assertions passed | PASS |
| PY-418 | `tests.test_network_verification.NetworkTests.test_forwarded_headers_ignored_and_client_ip_fields_rejected` | All assertions passed | PASS |
| PY-419 | `tests.test_network_verification.NetworkTests.test_fresh_check_after_disabling_policy_never_reuses_pass` | All assertions passed | PASS |
| PY-420 | `tests.test_network_verification.NetworkTests.test_invalid_enabled_policy_blocks_even_another_matching_policy` | All assertions passed | PASS |
| PY-421 | `tests.test_network_verification.NetworkTests.test_ipv6_ipv4_mapping_and_longest_prefix_selection` | All assertions passed | PASS |
| PY-422 | `tests.test_network_verification.NetworkTests.test_later_attendance_interface_requires_server_owned_attempt` | All assertions passed | PASS |
| PY-423 | `tests.test_network_verification.NetworkTests.test_login_profile_available_without_authorized_attendance_network` | All assertions passed | PASS |
| PY-424 | `tests.test_network_verification.NetworkTests.test_loopback_never_silently_authorized_even_by_a_policy` | All assertions passed | PASS |
| PY-425 | `tests.test_network_verification.NetworkTests.test_missing_invalid_unspecified_and_multicast_source_fail_and_audit` | All assertions passed | PASS |
| PY-426 | `tests.test_network_verification.NetworkTests.test_no_policy_write_api_and_authentication_required` | All assertions passed | PASS |
| PY-427 | `tests.test_network_verification.NetworkTests.test_outside_network_and_missing_or_disabled_policy_fail` | All assertions passed | PASS |
| PY-428 | `tests.test_network_verification.NetworkTests.test_policy_input_validation_and_configuration_audit` | All assertions passed | PASS |
| PY-429 | `tests.test_network_verification.NetworkMariaDBTests.test_additive_migration_constraints_and_parallel_audits` | Not executed: Opt-in isolated MariaDB FR-06 migration and concurrency | NOT TESTED |
| PY-430 | `tests.test_original_fyp.OriginalGuards.test_boolean_reflection_accepts_only_tinyint_one_alias` | All assertions passed | PASS |
| PY-431 | `tests.test_original_fyp.OriginalGuards.test_canonical_inventory_has_43_tables_no_test_tables` | All assertions passed | PASS |
| PY-432 | `tests.test_original_fyp.OriginalGuards.test_failed_health_prevents_every_process_start` | All assertions passed | PASS |
| PY-433 | `tests.test_original_fyp.OriginalGuards.test_no_fallback_to_other_databases` | All assertions passed | PASS |
| PY-434 | `tests.test_original_fyp.OriginalGuards.test_original_panel_label` | All assertions passed | PASS |
| PY-435 | `tests.test_original_fyp.OriginalGuards.test_readiness_rejects_other_backend_identity` | All assertions passed | PASS |
| PY-436 | `tests.test_original_fyp.OriginalPanelIntegration.test_admin_initialization_hash_only_and_no_overwrite_or_database_connection` | All assertions passed | PASS |
| PY-437 | `tests.test_original_fyp.OriginalPanelIntegration.test_admin_login_logout_revocation_and_student_credentials_rejected` | All assertions passed | PASS |
| PY-438 | `tests.test_original_fyp.OriginalPanelIntegration.test_ajax_pin_regeneration_replaces_hash_and_preserves_session` | All assertions passed | PASS |
| PY-439 | `tests.test_original_fyp.OriginalPanelIntegration.test_backend_probe_rejects_ordinary_port8000_missing_isolation_contract` | All assertions passed | PASS |
| PY-440 | `tests.test_original_fyp.OriginalPanelIntegration.test_ble_management_disabled_default_experimental_only` | All assertions passed | PASS |
| PY-441 | `tests.test_original_fyp.OriginalPanelIntegration.test_both_local_hosts_login_and_redirect_to_real_dashboard` | All assertions passed | PASS |
| PY-442 | `tests.test_original_fyp.OriginalPanelIntegration.test_classroom_assignment_only_existing_and_integrated` | All assertions passed | PASS |
| PY-443 | `tests.test_original_fyp.OriginalPanelIntegration.test_csrf_missing_forged_duplicate_and_cross_origin_rejected` | All assertions passed | PASS |
| PY-444 | `tests.test_original_fyp.OriginalPanelIntegration.test_database_error_rolls_back_and_does_not_expose_connection_secrets` | All assertions passed | PASS |
| PY-445 | `tests.test_original_fyp.OriginalPanelIntegration.test_every_management_page_and_mutation_requires_admin` | All assertions passed | PASS |
| PY-446 | `tests.test_original_fyp.OriginalPanelIntegration.test_login_keeps_exact_origin_check_and_requires_csrf` | All assertions passed | PASS |
| PY-447 | `tests.test_original_fyp.OriginalPanelIntegration.test_loopback_host_and_forwarding_guards` | All assertions passed | PASS |
| PY-448 | `tests.test_original_fyp.OriginalPanelIntegration.test_management_script_is_same_origin_and_pages_have_inline_targets` | All assertions passed | PASS |
| PY-449 | `tests.test_original_fyp.OriginalPanelIntegration.test_missing_optional_schema_is_unavailable_without_auto_migration` | All assertions passed | PASS |
| PY-450 | `tests.test_original_fyp.OriginalPanelIntegration.test_network_management_existing_validator_and_simulation_boundary` | All assertions passed | PASS |
| PY-451 | `tests.test_original_fyp.OriginalPanelIntegration.test_original_mode_http_login_dashboard_session_and_policy` | All assertions passed | PASS |
| PY-452 | `tests.test_original_fyp.OriginalPanelIntegration.test_original_policy_management_uses_existing_validator_and_audit` | All assertions passed | PASS |
| PY-453 | `tests.test_original_fyp.OriginalPanelIntegration.test_pin_once_session_duration_close_and_unchanged_attendance` | All assertions passed | PASS |
| PY-454 | `tests.test_original_fyp.OriginalPanelIntegration.test_pin_regeneration_requires_admin_csrf_and_open_window` | All assertions passed | PASS |
| PY-455 | `tests.test_original_fyp.OriginalPanelIntegration.test_session_expiry_and_fixed_login_throttle` | All assertions passed | PASS |
| PY-456 | `tests.test_original_fyp.OriginalPanelIntegration.test_shared_app_routes_registered_without_relaxing_authentication` | All assertions passed | PASS |
| PY-457 | `tests.test_original_fyp.OriginalPanelIntegration.test_unknown_actions_extra_fields_and_large_forms_rejected` | All assertions passed | PASS |
| PY-458 | `tests.test_original_fyp.OriginalPanelIntegration.test_validation_overlap_and_stopped_backend_do_not_insert` | All assertions passed | PASS |
| PY-459 | `tests.test_original_fyp.OriginalPanelIntegration.test_wifi_management_escapes_html_and_keeps_validation` | All assertions passed | PASS |
| PY-460 | `tests.test_partner_local_mode.test_local_start_without_cloudflare_or_gateway_and_optional_ble` | All assertions passed | PASS |
| PY-461 | `tests.test_partner_local_mode.test_local_install_same_lan_uses_own_identity_and_requires_switch_confirmation` | All assertions passed | PASS |
| PY-462 | `tests.test_partner_local_mode.test_local_does_not_touch_running_full_gateway` | All assertions passed | PASS |
| PY-463 | `tests.test_partner_local_mode.test_local_never_uses_original_db_identity` | All assertions passed | PASS |
| PY-464 | `tests.test_partner_local_mode.test_missing_local_database_does_not_start_or_create_anything` | All assertions passed | PASS |
| PY-465 | `tests.test_partner_local_mode.test_local_stop_rejects_full_ownership_even_for_matching_pid` | All assertions passed | PASS |
| PY-466 | `tests.test_partner_local_mode.test_full_defaults_remain_same_and_state_directories_separate` | All assertions passed | PASS |
| PY-467 | `tests.test_partner_local_mode.test_private_profile_explicit_secrets_flags_and_original_schema_guard` | All assertions passed | PASS |
| PY-468 | `tests.test_partner_local_mode.test_empty_initialization_uses_all_existing_tables_no_records_and_refuses_second_run` | All assertions passed | PASS |
| PY-469 | `tests.test_partner_local_mode.test_local_http_adapter_cannot_call_public_even_accidentally` | All assertions passed | PASS |
| PY-470 | `tests.test_partner_local_mode.test_local_installer_arguments_pin_both_urls_and_own_backend` | All assertions passed | PASS |
| PY-471 | `tests.test_partner_local_mode.test_private_identity_pin_is_explicit_and_drift_cannot_overwrite` | All assertions passed | PASS |
| PY-472 | `tests.test_partner_local_mode.test_local_guard_accepts_own_clone_and_never_requires_authors_absolute_path` | All assertions passed | PASS |
| PY-473 | `tests.test_passive_liveness.PassiveEvidenceTests.test_both_models_and_ensemble_must_pass` | All assertions passed | PASS |
| PY-474 | `tests.test_passive_liveness.PassiveEvidenceTests.test_pad_preprocessing_uses_bgr_pixels_and_class_one` | All assertions passed | PASS |
| PY-475 | `tests.test_passive_liveness.PassiveEvidenceTests.test_state_requires_valid_face_and_unique_passing_frame_evidence` | All assertions passed | PASS |
| PY-476 | `tests.test_passive_liveness.PresentationWorkflowTests.test_cancel_discards_runtime_scores` | All assertions passed | PASS |
| PY-477 | `tests.test_passive_liveness.PresentationWorkflowTests.test_client_flags_cannot_override_screen_detection` | All assertions passed | PASS |
| PY-478 | `tests.test_passive_liveness.PresentationWorkflowTests.test_completed_result_survives_runtime_cleanup` | All assertions passed | PASS |
| PY-479 | `tests.test_passive_liveness.PresentationWorkflowTests.test_face_and_head_then_three_passive_hand_frames_complete` | All assertions passed | PASS |
| PY-480 | `tests.test_passive_liveness.PresentationWorkflowTests.test_missing_or_incomplete_runtime_evidence_cannot_write_attendance` | All assertions passed | PASS |
| PY-481 | `tests.test_passive_liveness.PresentationWorkflowTests.test_photo_and_video_fail_face_preview_and_final_matching` | All assertions passed | PASS |
| PY-482 | `tests.test_passive_liveness.PresentationWorkflowTests.test_restart_requires_a_new_challenge_without_bypassing_checks` | All assertions passed | PASS |
| PY-483 | `tests.test_passive_liveness.PresentationWorkflowTests.test_screen_replacement_resets_all_consecutive_evidence_and_can_recover` | All assertions passed | PASS |
| PY-484 | `tests.test_passive_liveness.PresentationWorkflowTests.test_unavailable_or_invalid_inference_fails_closed_at_face_and_hand` | All assertions passed | PASS |
| PY-485 | `tests.test_passive_liveness.RuntimeLivenessTests.test_expiry_and_capacity_are_bounded` | All assertions passed | PASS |
| PY-486 | `tests.test_passive_liveness.RuntimeLivenessTests.test_failed_scores_cannot_be_saved_and_restart_loses_evidence` | All assertions passed | PASS |
| PY-487 | `tests.test_passive_liveness.RuntimeLivenessTests.test_runtime_data_is_copied_and_bound_to_student_login_and_challenge` | All assertions passed | PASS |
| PY-488 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_duplicate_is_idempotent_without_resetting_expiry` | All assertions passed | PASS |
| PY-489 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_expiry_replay_and_retry_keep_original_registration` | All assertions passed | PASS |
| PY-490 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_invalid_signature_consumes_challenge_and_logs_failure` | All assertions passed | PASS |
| PY-491 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_missing_signature_and_missing_login_are_rejected` | All assertions passed | PASS |
| PY-492 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_missing_untrusted_stale_reused_mismatched_server_approvals` | All assertions passed | PASS |
| PY-493 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_no_slot_one_or_historical_second_device_requires_other_workflow` | All assertions passed | PASS |
| PY-494 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_pending_database_constraints` | All assertions passed | PASS |
| PY-495 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_proof_is_bound_and_never_activates_or_records_attendance` | All assertions passed | PASS |
| PY-496 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_registered_key_initial_endpoint_and_extra_flags_cannot_bypass` | All assertions passed | PASS |
| PY-497 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_trusted_provider_remains_closed_while_untrusted_biometrics_need_template` | All assertions passed | PASS |
| PY-498 | `tests.test_pending_device_enrollment.PendingDeviceTests.test_wrong_student_and_login_session_cannot_read_or_consume` | All assertions passed | PASS |
| PY-499 | `tests.test_pending_device_enrollment.PendingMariaDBTests.test_concurrent_creation_proof_and_resumable_schema` | Not executed: Opt-in isolated MariaDB B2 races. | NOT TESTED |
| PY-500 | `tests.test_production_guard.ProfileTests.test_cli_missing_profile_fails_without_database` | All assertions passed | PASS |
| PY-501 | `tests.test_production_guard.ProfileTests.test_explicit_profile_ignores_unsafe_inherited_environment` | All assertions passed | PASS |
| PY-502 | `tests.test_production_guard.ProfileTests.test_importing_guarded_entry_point_does_not_load_config_or_open_socket` | All assertions passed | PASS |
| PY-503 | `tests.test_production_guard.ProfileTests.test_private_profile_exact_fields_duplicates_and_paths` | All assertions passed | PASS |
| PY-504 | `tests.test_production_guard.ProfileTests.test_profile_secrets_not_in_repr` | All assertions passed | PASS |
| PY-505 | `tests.test_production_guard.ProfileTests.test_unsafe_values_rejected_before_connection` | All assertions passed | PASS |
| PY-506 | `tests.test_production_guard.GrantTests.test_broad_missing_role_and_cross_schema_grants_fail` | All assertions passed | PASS |
| PY-507 | `tests.test_production_guard.GrantTests.test_exact_reviewed_privileges_accepted` | All assertions passed | PASS |
| PY-508 | `tests.test_production_guard.ConnectionTests.test_all_identity_and_safety_mismatches_fail` | All assertions passed | PASS |
| PY-509 | `tests.test_production_guard.ConnectionTests.test_connector_errors_do_not_disclose_secrets` | All assertions passed | PASS |
| PY-510 | `tests.test_production_guard.ConnectionTests.test_expected_server_only_read_statements` | All assertions passed | PASS |
| PY-511 | `tests.test_production_guard.ConnectionTests.test_lifespan_rejects_before_requests_and_cleans_up` | All assertions passed | PASS |
| PY-512 | `tests.test_production_guard.ConnectionTests.test_url_override_rejected_before_connection` | All assertions passed | PASS |
| PY-513 | `tests.test_public_gateway.test_general_api_and_forwarding_headers_stripped` | All assertions passed | PASS |
| PY-514 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/attendance/start]` | All assertions passed | PASS |
| PY-515 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/verify-face]` | All assertions passed | PASS |
| PY-516 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/liveness/frame]` | All assertions passed | PASS |
| PY-517 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/api/v1/networks/verifications]` | All assertions passed | PASS |
| PY-518 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/api/v1/devices]` | All assertions passed | PASS |
| PY-519 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/register]` | All assertions passed | PASS |
| PY-520 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/register-face]` | All assertions passed | PASS |
| PY-521 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/local-fyp/identity]` | All assertions passed | PASS |
| PY-522 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/local-fyp/demo-slot2]` | All assertions passed | PASS |
| PY-523 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/docs]` | All assertions passed | PASS |
| PY-524 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/openapi.json]` | All assertions passed | PASS |
| PY-525 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/ble]` | All assertions passed | PASS |
| PY-526 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/api/v1/network-ble-tests/start]` | All assertions passed | PASS |
| PY-527 | `tests.test_public_gateway.test_sensitive_routes_never_reach_origin[/api/v1/classroom-wifi/challenges]` | All assertions passed | PASS |
| PY-528 | `tests.test_public_gateway.test_host_method_query_body_and_identity` | All assertions passed | PASS |
| PY-529 | `tests.test_public_gateway.test_authentication_failures_throttle_and_origin_timeout_remain_fail_closed` | All assertions passed | PASS |
| PY-530 | `tests.test_public_gateway.test_aggregate_login_limit_ignores_forged_client_headers_and_expires` | All assertions passed | PASS |
| PY-531 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/admin]` | All assertions passed | PASS |
| PY-532 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/sessions]` | All assertions passed | PASS |
| PY-533 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/wifi]` | All assertions passed | PASS |
| PY-534 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/networks]` | All assertions passed | PASS |
| PY-535 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/verification/test]` | All assertions passed | PASS |
| PY-536 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/api/v1/attendance/preflight-challenges]` | All assertions passed | PASS |
| PY-537 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/api/v1/classroom-ble/challenges]` | All assertions passed | PASS |
| PY-538 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/api/v1/device-approvals]` | All assertions passed | PASS |
| PY-539 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/api/v1/devices/pending-registrations]` | All assertions passed | PASS |
| PY-540 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/redoc]` | All assertions passed | PASS |
| PY-541 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/login/]` | All assertions passed | PASS |
| PY-542 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/%6cogin]` | All assertions passed | PASS |
| PY-543 | `tests.test_public_gateway.test_additional_sensitive_and_encoded_paths_are_not_forwarded[/login%2f..%2fattendance/start]` | All assertions passed | PASS |
| PY-544 | `tests.test_public_gateway.test_nonloopback_requests_rejected_even_with_local_forwarding_claim` | All assertions passed | PASS |
| PY-545 | `tests.test_public_gateway.test_valid_isolated_backend_session_does_not_unlock_sensitive_routes` | All assertions passed | PASS |
| PY-546 | `tests.test_sample_data.SampleDataTests.test_history_integrity_rerun_and_existing_record_preservation` | All assertions passed | PASS |
| PY-547 | `tests.test_setup.SetupTests.test_fresh_demo_password_requires_interactive_matching_input` | All assertions passed | PASS |
| PY-548 | `tests.test_setup.SetupTests.test_model_only_bypasses_database_configuration` | All assertions passed | PASS |
| PY-549 | `tests.test_two_device_stage_a.TwoDeviceStageATests.test_ambiguous_legacy_current_fails_closed` | All assertions passed | PASS |
| PY-550 | `tests.test_two_device_stage_a.TwoDeviceStageATests.test_fingerprint_alone_cannot_pass_for_other_key` | All assertions passed | PASS |
| PY-551 | `tests.test_two_device_stage_a.TwoDeviceStageATests.test_isolated_revocation_does_not_change_other_device` | All assertions passed | PASS |
| PY-552 | `tests.test_two_device_stage_a.TwoDeviceStageATests.test_list_two_and_verify_each_key_independently` | All assertions passed | PASS |
| PY-553 | `tests.test_two_device_stage_a.TwoDeviceStageATests.test_missing_local_key_audit_is_unbound_to_either_device` | All assertions passed | PASS |
| PY-554 | `tests.test_two_device_stage_a.TwoDeviceStageATests.test_selector_is_owner_scoped_and_required` | All assertions passed | PASS |
| PY-555 | `tests.test_two_device_stage_a.TwoDeviceStageATests.test_stage_a_blocks_second_enrollment_and_even_old_pending_confirmation` | All assertions passed | PASS |
| PY-556 | `tests.test_two_device_stage_a.TwoDeviceStageATests.test_third_slot_duplicate_slot_and_invalid_status_are_rejected` | All assertions passed | PASS |
| PY-557 | `tests.test_two_device_stage_a.StageAMariaDBTests.test_constraints_selection_and_concurrent_signatures` | Not executed: Opt-in disposable MariaDB Stage A races. | NOT TESTED |
| PY-558 | `tests.test_two_device_stage_a.StageAMariaDBTests.test_legacy_migration_resumes_and_keeps_old_guard_when_new_check_is_wrong` | Not executed: Opt-in disposable MariaDB Stage A races. | NOT TESTED |
| PY-559 | `tests.test_workflow.WorkflowTests.test_attendance_requires_pin_face_then_three_live_frames` | All assertions passed | PASS |
| PY-560 | `tests.test_workflow.WorkflowTests.test_auto_enrollment_requires_consent_and_preview_never_saves_a_template` | All assertions passed | PASS |
| PY-561 | `tests.test_workflow.WorkflowTests.test_auto_scan_can_recover_then_complete_without_preview_recording_attendance` | All assertions passed | PASS |
| PY-562 | `tests.test_workflow.WorkflowTests.test_auto_scan_identity_mismatch_is_terminal_even_in_preview` | All assertions passed | PASS |
| PY-563 | `tests.test_workflow.WorkflowTests.test_auto_scan_still_checks_expiry_after_slow_detection` | All assertions passed | PASS |
| PY-564 | `tests.test_workflow.WorkflowTests.test_cancel_never_records_attendance` | All assertions passed | PASS |
| PY-565 | `tests.test_workflow.WorkflowTests.test_challenge_expiry` | All assertions passed | PASS |
| PY-566 | `tests.test_workflow.WorkflowTests.test_challenge_stays_bound_to_the_login_that_started_it` | All assertions passed | PASS |
| PY-567 | `tests.test_workflow.WorkflowTests.test_challenges_cannot_cross_student_accounts` | All assertions passed | PASS |
| PY-568 | `tests.test_workflow.WorkflowTests.test_consumed_challenge_and_duplicate_class_rejected` | All assertions passed | PASS |
| PY-569 | `tests.test_workflow.WorkflowTests.test_enrollment_requires_consent_and_encrypts_template` | All assertions passed | PASS |
| PY-570 | `tests.test_workflow.WorkflowTests.test_expired_session_rejected` | All assertions passed | PASS |
| PY-571 | `tests.test_workflow.WorkflowTests.test_face_must_remain_visible_during_gesture` | All assertions passed | PASS |
| PY-572 | `tests.test_workflow.WorkflowTests.test_face_registration_is_independent_but_attendance_requires_authorized_source` | All assertions passed | PASS |
| PY-573 | `tests.test_workflow.WorkflowTests.test_failed_pins_are_logged_without_blocking_a_valid_pin` | All assertions passed | PASS |
| PY-574 | `tests.test_workflow.WorkflowTests.test_inactive_session_rejected` | All assertions passed | PASS |
| PY-575 | `tests.test_workflow.WorkflowTests.test_live_course_history_and_percentage_are_scoped_to_student` | All assertions passed | PASS |
| PY-576 | `tests.test_workflow.WorkflowTests.test_liveness_cannot_be_called_before_face` | All assertions passed | PASS |
| PY-577 | `tests.test_workflow.WorkflowTests.test_liveness_face_mismatch_resets_progress_but_allows_a_fresh_genuine_streak` | All assertions passed | PASS |
| PY-578 | `tests.test_workflow.WorkflowTests.test_login_only_needs_credentials_and_new_session_can_verify` | All assertions passed | PASS |
| PY-579 | `tests.test_workflow.WorkflowTests.test_logout_revokes_session_and_cancels_challenge` | All assertions passed | PASS |
| PY-580 | `tests.test_workflow.WorkflowTests.test_malformed_pin_is_rejected` | All assertions passed | PASS |
| PY-581 | `tests.test_workflow.WorkflowTests.test_missing_face_is_rejected` | All assertions passed | PASS |
| PY-582 | `tests.test_workflow.WorkflowTests.test_missing_or_inactive_template_does_not_allow_student_reenrollment` | All assertions passed | PASS |
| PY-583 | `tests.test_workflow.WorkflowTests.test_outside_class_hours_rejected` | All assertions passed | PASS |
| PY-584 | `tests.test_workflow.WorkflowTests.test_production_disables_self_assigned_groups_and_signup` | All assertions passed | PASS |
| PY-585 | `tests.test_workflow.WorkflowTests.test_registration_hashes_password_and_validates_duplicate_email` | All assertions passed | PASS |
| PY-586 | `tests.test_workflow.WorkflowTests.test_removed_deletion_endpoint_cannot_unlock_registration_or_change_records` | All assertions passed | PASS |
| PY-587 | `tests.test_workflow.WorkflowTests.test_repeated_wrong_faces_and_nonfinite_distances_never_advance_liveness` | All assertions passed | PASS |
| PY-588 | `tests.test_workflow.WorkflowTests.test_result_is_read_only_and_does_not_trust_client_flags` | All assertions passed | PASS |
| PY-589 | `tests.test_workflow.WorkflowTests.test_result_reports_failed_and_cancelled_verifications` | All assertions passed | PASS |
| PY-590 | `tests.test_workflow.WorkflowTests.test_result_requires_the_original_authenticated_login` | All assertions passed | PASS |
| PY-591 | `tests.test_workflow.WorkflowTests.test_result_tracks_server_evidence_and_persists_after_success` | All assertions passed | PASS |
| PY-592 | `tests.test_workflow.WorkflowTests.test_same_frame_cannot_be_replayed` | All assertions passed | PASS |
| PY-593 | `tests.test_workflow.WorkflowTests.test_unknown_or_missing_auth_rejected` | All assertions passed | PASS |
| PY-594 | `tests.test_workflow.WorkflowTests.test_wrong_face_never_records_attendance` | All assertions passed | PASS |
| PY-595 | `tests.test_workflow.WorkflowTests.test_wrong_gesture_resets_consecutive_count_and_is_logged` | All assertions passed | PASS |
| PY-596 | `tests.test_workflow.WorkflowTests.test_wrong_group_pin_is_rejected_and_logged` | All assertions passed | PASS |

## Counts and limitations

- Backend assertion inventory: **582 PASS / 0 FAIL / 14 NOT TESTED** (skipped live/concurrency cases).
- Flutter executable assertions: **331 PASS / 0 FAIL / 1 SKIPPED**; see expanded log for exact names. Flutter widgets/fake platform channels do not prove Android radio/permission behavior.
- Functional/operational summary cases overlap underlying assertions; do not add their counts to 582/331 or historical phone cases.
- Physical acceptance summary: **4 PASS / 9 NOT TESTED** after the Public-hotspot test and early cleanup. PASS combines user-observed phone outcomes with independently verified host cleanup. Actual elapsed 30-minute expiry was not waited out; scheduled cleanup was rehearsed before activation.
- No fresh production write, MariaDB restart durability, school reachability, or quantitative biometric accuracy claim is made.

## Public-hotspot physical acceptance update — 17 November, 23:20 MYT

MAN-01–03 are now user-confirmed real Xiaomi PASS; MAN-04 cleanup protection/early rollback PASS is host-verified. No attendance was submitted by the agent. Full 30-minute elapsed expiry and school networking remain untested. Evidence: `C:\FYP\Final-Acceptance\20261117-final\hotspot-physical-results.json` and `hotspot-cleanup-verification.json`.

Post-cleanup checks: original identity unchanged, backend/admin/public config healthy, pinned HTTPS valid, diagnostic false, public attendance route 404. Read-only attendance count remains **8**, matching the earlier check. This is a count comparison, not a complete row-content hash comparison.
