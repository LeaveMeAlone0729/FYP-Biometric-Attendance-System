# BLE Phase 4B — proposal only, no enforcement implemented

Update, 8 November 2026: standalone policy verification is now implemented in
[CLASSROOM_BLE_PHASE4B.md](CLASSROOM_BLE_PHASE4B.md). This original proposal is
retained for design history. Its attendance-integration ideas remain unimplemented
Phase 4C work; a standalone BLE PASS never authorizes attendance.

Prerequisite: confirm Samsung advertising and Xiaomi scanning physically, then
collect classroom/corridor/library distributions. Phase 4A only displays local
observations. No API, database table, RSSI gate or attendance condition is added
by this design document.

## Candidate policy and measurement

Reuse the existing classroom identifier and offline policy-management style in
a separately approved phase. Suggested policy fields: classroom ID, policy ID,
identifier type (initial experiment: 128-bit service UUID), approved identifier,
enabled/retired state, scan window (e.g. eight seconds), minimum samples,
experimental median-RSSI threshold, uncertainty margin and revision.

Do not bind a classroom to a Samsung personal Bluetooth address, device model,
advertised name, or a real student's phone. The synthetic Phase 4A UUID is only
an experiment marker. Multiple approved beacons per room can be supported after
physical coverage assessment. Reusing an existing classroom ID does not imply
changing current Wi-Fi or attendance policies.

For an explicit verification action:

1. Obtain server context/nonce first if this is a future server-bound check.
2. Run the existing short scanner automatically when Bluetooth/permissions are
   ready; otherwise return clear unavailability and offer the normal system prompt.
3. Select samples belonging to the approved identifier in the current window;
   validate observation times and retain several RSSI values. Account for the
   Phase 4A caps (last 50 samples, 40 advertisers). Collect per-identifier samples
   rather than blindly mixing changing advertisement payloads.
4. Calculate median from valid samples. RSSI is not converted to guaranteed metres.
   Calibrate a threshold and uncertainty band using separate training/validation
   locations/devices; do not select a threshold just to make the demo pass.

Illustrative result rules (values intentionally not production defaults):

| Diagnostic result | Condition/reason |
|---|---|
| PASS | Approved ID freshly observed, enough samples, median clearly above calibrated threshold |
| FAIL | Complete healthy scan with no approved beacon, or calibrated median clearly below the threshold/band |
| UNCERTAIN | Too few samples, near-boundary median, unstable/old observations, interrupted scan |
| UNCERTAIN / unavailable | Bluetooth off, permission denied, Location Services off, scanner timeout/failure; do not assert physical absence |

Even diagnostic PASS means only that reported radio observations meet an
experimental rule. A failed/incomplete scan cannot grant authorization. Future
attendance must fail closed on FAIL/UNCERTAIN if the session explicitly requires
BLE, while preserving historical unconfigured sessions.

## Freshness and replay-resistant integration contract

Extend the existing device challenge/attendance-attempt machinery, rather than
accepting a standalone screen PASS or creating a second attendance writer.

- Server generates a short-lived single-use nonce bound to authenticated student,
  login/session, ACTIVE device key fingerprint, attendance session/attempt,
  classroom, operation, policy revision and allowed scan window.
- Start scanning after nonce issuance. Include exact nonce payload, selected
  beacon identifier, scan start/end, received sample timestamps/offsets, sample
  values/count and duration in the canonical signed observation. Preserve exact
  signed-byte semantics as in classroom Wi-Fi; never sign a cached screen result.
- Use the existing Android Keystore P-256 key. Server verifies the signature,
  key ownership/ACTIVE status, operation/attempt/session/classroom binding,
  expiry and nonce/evidence replay before evaluating the current policy.
- Check/consume the authorization in the existing atomic final attendance
  boundary, rechecking fresh source-IP CIDR and all existing device/PIN/face/
  liveness/duplicate restrictions. Preflight is not final authorization. Refresh
  evidence if biometrics takes longer than its freshness allowance.
- Store/audit only the reviewed minimum data with explicit retention and privacy
  policy. No backend table or route is authorized by this document.

This rejects verbatim old signed-message replay and cross-account/attempt use.
It **does not** prove that a modified registered client honestly measured RSSI,
prevent rebroadcast/relay of a static UUID, or establish that radio coverage ends
at a classroom door. Client clocks/OS timestamps are observations, not hardware
attestation. Median filtering reduces outliers; it does not make RSSI cryptographic.
Stronger assurance would need a separately evaluated authenticated/rotating
beacon or challenge-response design, relay analysis and appropriate hardware.
No static-beacon or development bypass should replace that analysis.

## Approval gates before implementation

1. Record real Samsung advertiser capability and Xiaomi scanner results.
2. Check overlap between classroom, corridor and library RSSI distributions,
   including body/orientation, walls, crowds, phone power and OS background effects.
3. If distributions overlap materially, report UNCERTAIN/insufficient feasibility
   instead of claiming classroom discrimination.
4. Agree on policy semantics, limits, retention and security claims with supervisor.
5. Separately approve backend/migration/attendance work, with isolated tests,
   backup rehearsal, fresh proof replay tests and unchanged final authorization.

Current scope stops at physical Phase 4A testing.
