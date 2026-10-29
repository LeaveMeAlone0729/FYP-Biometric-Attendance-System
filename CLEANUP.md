# Project cleanup — 29 October 2026

Removed the unreferenced `student_home_screen.dart`, unused profile image,
manual `test_face.py`/`test_import.py` scripts, and old `temp.jpg`/`verify.jpg`
captures. The active Flutter portal and automated tests remain. Removed the unused
`image_picker` and `cupertino_icons` packages and refreshed the package lockfile
and plugin registrations. Removed the obsolete `manage.py import-legacy` command.

Deleted generated Flutter build output, Dart/Gradle/Kotlin caches, obsolete IDE
metadata and Python bytecode. Earlier screenshots, logs, source snapshots and
migration artifacts are consolidated into one verified history archive.
Platform source projects, required assets, dependency lockfiles, the Python
environment, MediaPipe model, `.env` and `.work/seed-runtime` remain necessary.

The active XAMPP database is `attendance_proposal_xampp`. Its ten tables are all
used and were retained. All 38 students, 515 attendance records and 664
verification attempts present at cleanup were retained, together with academic
data. Pruned eight consumed/expired verification challenges and four expired
authentication sessions; the remaining live session was retained. All foreign
key checks passed.

Removed two obsolete databases from the running XAMPP instance:

- `attendance_system`: old prototype, backed up as a complete SQL dump.
- `attendance_proposal`: abandoned schema with an orphaned `programmes` table
  that MariaDB could not read (error 1932). Its original `db.opt`, `.frm` and `.ibd`
  files were archived before removal. These raw files are forensic backups;
  recovery of this already-broken table is not guaranteed.

Unrelated databases and the stopped Laragon installation were left intact.

## Backups

All cleanup artifacts are under `.work/cleanup-20261029/` (ignored by Git):

| File | Contents |
| --- | --- |
| `project-before.zip` | Project source and configuration before cleanup, including `.env` |
| `work-history.zip` | Earlier work artifacts, source snapshots and database migration backups |
| `attendance_proposal_xampp.sql` | Complete active database before cleanup |
| `attendance_system.sql` | Complete obsolete prototype database |
| `attendance_proposal-orphaned-files.zip` | Exact original files of the broken schema |
| `database-result.json` | Database counts, backup hashes and integrity results |

The archives contain secrets and biometric/account data; keep them private.
Restoring source files only requires extracting the selected paths from
`project-before.zip`. SQL dumps include database creation statements and can be
imported with XAMPP's MySQL client; restoring the active dump replaces tables,
so restore it only as a deliberate rollback with the API stopped. Restore the
matching `.env` biometric key when restoring encrypted facial templates.

Build caches regenerate with `flutter pub get` and the next build. See README.md
for normal startup and verification commands.

## Verification

- Flutter analysis: no issues.
- Flutter tests: all 18 passed.
- Backend tests: 37 passed; one optional live API regression skipped because
  `ATTENDANCE_API_URL` was not set. Real face detection and MediaPipe checks passed.
- Android debug APK: built successfully after removing the unused packages.
- Live MySQL: only the active attendance schema remains; all foreign key checks
  passed and academic, student, attendance and attempt records were preserved.

Removed approximately 3.1 GiB of pre-existing generated files and caches. Build
output created during verification was removed again; the next build regenerates
it. Minimal Dart package configuration remains so editor imports still resolve.
