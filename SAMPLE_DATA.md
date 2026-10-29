# Realistic sample database

Run `./seed-sample-data.ps1` from the project root while XAMPP MySQL is running.
This inserts fictional academic data into the database selected by `backend/.env`
and requires `DEMO_MODE=true`. Existing rows, passwords, face registrations,
biometric templates and attendance are preserved. Identifier collisions abort the
transaction. Repeating the command does not duplicate the dataset.

The dataset contains 36 Malaysian-style student names and academic IDs, two
programmes, three groups, six courses, 12 weekly schedules and 144 dated sessions
from 28 September through 18 December 2026. The course catalogue and lecturer
names are fictional examples, not an official institutional timetable. Email
addresses use `student.example.test`.

The generated account and PIN reference is `.work/testing-accounts.txt`. All new
accounts start with `CampusAttend2026!`. For example, sign in as `24WMR10001`
(Aiman Hakim bin Zulkifli, RIT3S1-G1). Use `24WMR10009` for lower attendance,
`24WMR10010` for an empty history, or `24WMR10011` for an inactive login rejection.
Equivalent scenarios exist in each group. These are student accounts: this app
does not yet implement admin or lecturer logins or RBAC. Lecturers are timetable
fields only; this seed does not complete that requirement in the assignment.

Historical attendance is generated only before the seeding date. The seed has
varied attendance and unsuccessful attempts, with absences represented by missing
attendance records as expected by the existing summary API. Every generated
verification attempt is tagged `stage=sample_data` and has a `[SAMPLE]` explanation.
The imported successful attendance entries do not represent observed face or
liveness verification. No facial templates, consent, challenges
or authentication sessions are generated. Enroll your own face after first login
to perform camera testing. The app's general demo-mode label still applies.

PINs work only for the student's group, on the scheduled date and during the class
window in Asia/Kuala_Lumpur. On Monday 2 November 2026, the classes are:

| Group | Course | Window | PIN |
| --- | --- | --- | --- |
| RIT3S1-G1 | BMIT3173 Mobile Application Development | 09:00–11:00 | 482731 |
| RCS3S1-G1 | BMCS3013 Artificial Intelligence | 11:00–13:00 | 671429 |
| RIT3S1-G2 | BMIT3173 Mobile Application Development | 14:00–16:00 | 563817 |

For a presentation at a different time, create a dated session with `backend/manage.py
create-session` as documented in README.md. Sign in from any phone that can reach
the backend API, then register your face and complete the face/gesture checks.
Rerunning this seed deliberately does not reset passwords or face registrations.

The original database was backed up before the first load to
`.work/sample-data-backup-20261029.sql` (now inside
`.work/cleanup-20261029/work-history.zip`). The existing legacy `DEMO001` account and
its records remain intact; the realistic sample accounts use separate groups.

The backend virtual environment uses the installed Python 3.12. Restricted
execution may prevent it from accessing that installation; this initially looked
like a missing runtime. Run the backend with the required Windows filesystem
access. The seeding command also supports Python 3.13 with the database-only
dependencies in `.work/seed-runtime` as a fallback; that fallback runs the seeder
only.

Validate the dataset without MySQL:

```powershell
$env:PYTHONPATH = "$PWD\.work\seed-runtime"
python -m unittest discover -s backend/tests -p test_sample_data.py -v
Remove-Item Env:PYTHONPATH
```
