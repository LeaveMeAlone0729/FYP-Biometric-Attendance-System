# DEMO001 real Slot 2 reset and re-registration

18 November 2026, SH. User explicitly authorized destructive DEMO001 Slot 2 demo state changes. No unrelated users, Samsung Slot 1, face, attendance, security policies or Keystore data changed.

## Actual results

| Case | Result | Evidence |
|---|---|---|
| Verified affected-record backup before reset | PASS | Protected external checkpoint; fsync + SHA-256 verified before deletion and afterward |
| Narrow local-demo Slot 2 reset | PASS | Archived exact Xiaomi row and FK-dependent demo proofs; LOCAL_DEMO_SLOT2_RESET audit; no schema or service changes |
| Old registration cannot access device verification while unregistered | PASS | DEVICE_KEY_NOT_REGISTERED server audit at 00:15:36, 00:15:52, 00:16:23 |
| Genuine Xiaomi re-enrollment | PASS | New KEY_PROVEN request, real face/liveness completion, fresh approval issued/consumed, activation PASS at 00:17 |
| Registered key possession after re-enrollment | PASS | Real DEVICE_VERIFIED at 00:17:00 and 00:17:47; same retained key, new server registration ID |
| Samsung Slot 1 and other protected records preserved | PASS | Full-row hashes match; 8 attendance rows preserved; 2 ACTIVE devices |
| Real replacement / old-target revocation / new different-device activation | BLOCKED / NOT TESTED | Distinct candidate not connected; current LOCAL FYP DEMO evidence is enrollment-only |

Current database: original attendance_proposal_xampp on port 3306. Slot 1 samsung SM-A346E ACTIVE. Slot 2 Xiaomi 2410CRP4CG ACTIVE; user-entered new name is [LOCAL FYP DEMO] sh tablet. Assurance remains UNVERIFIED; no institutional claim.

## Utility and guardrails

`backend/reset_demo_slot2.py` is an OFFLINE operator utility, not an API or launch hook. Default-disabled, requires a process-only explicit opt-in, exact fingerprint/confirmation, existing original demo profile and matching private operator credential. Requires exact local-demo Xiaomi Slot 2 and active Samsung, transactional tables, no active scan, and a fresh private checkpoint. Locks the student/target, archives FK descendants, refuses cross-student/protected data changes, verifies preserved rows before commit, records reset audit. It never sets a device ACTIVE or creates approval evidence. Enrollment afterward uses unchanged genuine face/liveness, signature and single-use approval services.

This destructive reset is not ordinary student removal or replacement. Historical key uniqueness is deliberately cleared only for this archived local demo reset. Production/student registration semantics are unchanged. No live automatic restore is provided. Do not rerun it casually before the presentation.

Affected private checkpoint (DO NOT COMMIT):
`C:\FYP\Device-Checkpoints\slot2-reset-20261118-001426`.
Read REPORT.md there for backup counts, integrity manifest, regression evidence and recovery limitations. A previous metadata-only review checkpoint also remains intact.

`backend/tests/test_demo_slot2_reset.py`: 5 tests cover default-disabled/wrong-key, cross-account/protected dependencies, archive/FK restore rehearsal with typed timestamps, preservation and rollback failure. Combined device regression: 89 passed, 4 skipped. No automated synthetic test is labeled a real phone PASS.

## Missing replacement authorization prerequisite

Existing local_demo.permits_binding only permits enroll_second_device/Slot 2 for the previously witnessed tablet key. It intentionally rejects replace_device. The reset did not change it. A genuinely different device/key is also required; one retained Android key cannot replace itself. Existing emulator profiles were listed but not started.

Before a full real replacement, obtain the distinct candidate and explicit approval of a narrowly scoped local-demo operation-verification design. Proposed scope: only DEMO001/local credential, exact replace_device target/key/session/challenge binding, genuine fresh server-confirmed face/liveness + candidate key proof, short-lived single-use authorization, audited LOCAL DEMO / UNVERIFIED assurance, old device remains ACTIVE until atomic replacement commit. No fabricated institutional approval, unconditional trust or direct ACTIVE update. This extension is **not implemented or enabled** by this task.

No uninstall/data clear, Keystore reset, database creation, migration, Cloudflare/TLS/firewall change, service restart, commit or push.
