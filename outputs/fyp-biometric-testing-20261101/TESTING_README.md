# FYP facial recognition and liveness testing pack

Prepared 1 November 2026, Asia/Kuala_Lumpur.

## Included files

- `FYP_Biometric_Test_Plan.xlsx`: executable case catalogue, experiment protocols, blank observations, RBAC matrix, accounts and fixture inventory.
- `Sample_Attendance.sqlite`: a separate fictional SQLite sample database using the existing academic schema and seeder.
- `Sample_Attendance_MySQL.sql`: creates the separate `fyp_biometric_test_20261101` MySQL schema with the same fictional data. It was generated, not executed against MySQL.
- `Test_Accounts.txt`: Notepad-readable student credentials and class PINs, plus proposed staff test credentials clearly marked as not provisioned.

## Scope and roles

For the complete attendance system, three roles are sufficient: Student, Lecturer and Department Administrator. Authorization also needs resource scope: a lecturer sees assigned classes, and a department officer handles authorized students. A role alone must not grant access to every class or department.

The current demo has student authentication and ownership checks. It does not implement lecturer or department login/RBAC. The staff credentials in this pack are planning examples, not working logins. Create them through the teammate's authentication service when its API exists. Your code remains focused on face enrollment, face recognition, liveness and verification results. No teammate business logic was changed for this pack.

Student facial-data deletion and replacement are unavailable. Recognition failures lead to lecturer manual attendance and department-supervised recovery. Those staff services remain pending integration; their tests are listed as such. Initial self-enrollment still does not prove institutional identity, and the current finger gesture is a research heuristic rather than certified presentation-attack detection.

## Database use

The sample database is an **offline reference fixture**, not a replacement for the running MySQL database. Open it with a SQLite viewer to inspect students, academic groups, schedules, dated classes, sample history and relationships. It contains no real face images, face templates, consent, authentication tokens or live verification challenges.

The fixture uses the existing fictional seeder as of 1 November 2026. All student passwords were checked against its PBKDF2 hashes. The configured application database and any existing account passwords were not inspected or changed. Timetable lecturer names are descriptive fields, not staff login accounts.

To run the Android app against the fixtures, import `Sample_Attendance_MySQL.sql` into MySQL. It creates a **separate schema named `fyp_biometric_test_20261101`** and contains no DROP, DELETE or UPDATE statements. Do not replace that schema name with your development database. If the schema already exists, stop and choose a fresh isolated schema name; do not use a client mode that ignores SQL errors. The script was compiled with SQLAlchemy's MySQL dialect and its source counts were checked, but it was not imported into a MySQL server during preparation.

Run a separate backend test configuration pointed at that test schema. Keep the existing development backend/database configuration unchanged. The existing seeder remains available if more dated sessions are needed. `seed-sample-data.ps1` targets the database selected by its backend environment, so inspect that target before using it. The SQLite reference file itself is not a MySQL SQL dump. Staff accounts still require the teammate's future authentication/RBAC service.

Historical attendance and verification attempts are artificial presentation records, tagged `stage=sample_data` with a `[SAMPLE]` explanation. Never count them as experimental recognition or liveness results. An absence is a missing attendance row, not a fabricated failed camera test.

All sample students start without a face registration. Use a distinct fresh test account per consenting person. Once enrolled, do not switch the person assigned to that account. For repeated attendance experiments, create fresh test class sessions or use an isolated research harness; one student cannot record attendance repeatedly for the same class.

Class PINs are valid only for the student's group, academic date and class time. Monday 2 November 2026 examples:

| Student/group | Course | Kuala Lumpur time | PIN |
| --- | --- | --- | --- |
| 24WMR10001 / RIT3S1-G1 | BMIT3173 | 09:00–11:00 | 482731 |
| 24WCS10001 / RCS3S1-G1 | BMCS3013 | 11:00–13:00 | 671429 |
| 24WMR10101 / RIT3S1-G2 | BMIT3173 | 14:00–16:00 | 563817 |

## Executing the workbook

1. Record build/commit, configuration, phone/OS/camera, model and library versions, test date and network conditions in the evidence record.
2. The `Test Cases` sheet follows the seven-column template: Req ID, Test Objective, Test Steps, Expected Result, Actual Result, Pass/Fail and Related Defects. Existing case identifiers remain in Req ID. Supporting details, including availability, requirement mappings, preconditions and test data, are in columns H:R. Execute implemented P0 cases first. Availability describes current capability; it is not a test result.
3. Use the Pass/Fail dropdown to select Pass, Fail, On-Hold, Blocked or Not Applicable. Pass turns green, Fail red, and On-Hold/Blocked yellow. Fill Actual Result and Related Defects, then record tester and date in columns Q:R. All unexecuted cases remain Not Run. Do not mark a pending API test Pass merely because its expected behavior is documented.
4. Use synthetic test doubles for deterministic threshold, expiry and error tests. Use physical consented camera testing for actual recognition, gestures, lighting, devices and spoof experiments. MySQL concurrency tests require MySQL; SQLite row locking is not an equivalent proof.
5. Agree experiment sample sizes and numeric accuracy/performance targets with the supervisor before collecting results. Proposed sample counts in the workbook are planning examples.
6. Enter one attempt per `Trial Log` row. Use pseudonymous participant and claimed-identity codes. Include failed acquisition and rejected attempts. Pending or unattempted rows are excluded from completed-attempt rates.
7. A face comparison uses Match/Non-match only when a comparison was evaluated. Use Not evaluated when acquisition failed. Genuine FTA, genuine FNMR, impostor FMR and final attendance acceptance have different denominators.
8. No measurements are prefilled. Research measures show `n.a.` until observations exist. All functional cases start as Not Run, including scenarios with existing automated-test references.
9. The raw log reserves 500 rows. Extend its table, validation and bounded summary formulas together for larger experiments. Keep raw observations unchanged and analyze P50/P95 duration, per-condition and per-attack results separately when reporting research.
10. Report the number of participants as well as attempts. Repeated attempts from the same person are correlated. Zero observed false acceptances does not prove a population error rate of zero.

This is a comprehensive catalogue for the current module and its defined interfaces. Extend it as supported devices, attacks and teammate API contracts change; a finite list cannot prove every possible scenario has been tested.

## Design references

- OWASP Authorization Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- NIST identity-proofing guidance: https://pages.nist.gov/800-63-4/sp800-63a.html
- Repository sources: `README.md`, `SAMPLE_DATA.md`, `backend/seed_sample.py`, the biometric module, and its existing tests. Source review establishes expected behavior, not measured effectiveness.
