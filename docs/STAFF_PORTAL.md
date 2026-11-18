# Admin and teacher portal

Start your usual profile and open **http://127.0.0.1:8000/** on the server laptop.
The homepage opens the BioAttend staff portal. Local mode includes two default
accounts without a database table:

| Role | Username | Password |
| --- | --- | --- |
| Admin | `admin` | `Admin@123` |
| Teacher | `teacher` | `Teacher@123` |

Both roles can manage class sessions, view students, export registers, and mark
attendance. The portal shows the role and saves the username in each attendance
audit. Both roles can view the integrated policy pages; only admins can change
policies. These shared demo accounts do not impose individual course assignments.

Existing private admin credentials also work when their username is different
from the reserved default usernames. Default usernames use the passwords above.
Full mode keeps its existing private admin credentials; Local defaults are not
enabled there. The separate port-8003 panel retains its original credentials.

The portal stays on localhost. The student mobile API remains reachable over the
LAN at its existing addresses. `/health` provides the previous JSON health check.
Policy management is included in the portal with the same staff login and UI.
The older standalone panel remains at `http://127.0.0.1:8003/login` for compatibility.

## Using the portal

- **Overview:** today's sessions, present and absent counts, student totals,
  and recent manual attendance changes.
- **Attendance Sessions:** create a session for an existing course/group, share
  its six-digit PIN, regenerate the PIN, or close student check-in. The complete
  session history is paginated in groups of 50, with session IDs and dates/times.
  PINs appear only after creation/regeneration and are cleared when they expire
  or you leave.
- **Take attendance:** opens the class session list. Select a class or its
  **Open register** button to see students enrolled through that session's group.
  Tick the checkbox beside each present student's name, optionally add a class
  note, then select **Save attendance**. Ticked students are present and unticked
  students are absent on save. Existing Present/Late records are pre-ticked.
  Search and status filters help find students; **Tick all visible** and
  **Untick all visible** change only the currently visible checkboxes. The save
  applies to the full enrolled list, including rows hidden by filters. Export
  the register as CSV when needed. Individual checkboxes and saving also work
  without JavaScript.
- **Students:** search the directory by name, ID, or group.
- **Network Policies:** view source CIDRs and add/enable/disable policies through
  the existing audited operators. Local mode retains the existing restriction
  to simulation-labelled policies; other network policies remain read-only.
- **Classroom Wi-Fi:** view classrooms, register approved BSSIDs and optional
  SSIDs, and enable/disable Wi-Fi policies. Adding a policy creates its classroom
  when needed. Classroom assignment is available when creating sessions.
- **Experimental BLE:** configure service UUIDs, labels, sample counts, RSSI
  thresholds, and sample ages; enable/disable beacons; and review signed-check,
  attendance shadow, and Network + BLE diagnostic results. New beacons start
  disabled. BLE remains observation-only and does not authorize attendance.

All policy pages use the same authentication, CSRF protection, and audit services
as the rest of the portal. A second login to port 8003 is not needed.

During class, students without a record remain **Unmarked**. At the scheduled
class session end, missing attendance automatically becomes **Absent**. Existing
Present, Late, Absent, and corrected records are preserved. Cancelled sessions
are excluded, as are students whose accounts were created after the class ended.

Teachers and admins can correct attendance from class start until **two hours
after the class session ends**. The cutoff is exclusive: a class ending at 16:00
allows corrections before 18:00; at 18:00 the register is read-only. The deadline
uses Asia/Kuala_Lumpur time and can fall on the following day. Closing student
check-in early does not shorten or extend this deadline. Future and cancelled
sessions are read-only. Student self-service check-in stops at the actual class
end and does not use the teacher correction window.

The session list and register display the correction deadline. The browser
disables checkboxes and Save when it expires, and the backend independently
rejects both individual and full-register edits after expiry, including a save
that reaches the deadline before committing. Staff can mark only students
belonging to the session's group. Stale pages must be refreshed before overwriting
a newer record, including a new automatic absence.
The complete class register is saved in a single transaction. A changed student
list or newer attendance record rejects the whole save, so no partial register is
committed. Existing checked Present/Late records retain their original biometric
evidence and timestamp. A blank class note uses a standard roll-call audit note.

Each manual change appends an existing `verification_attempts` audit entry with
stage `teacher_attendance`, result `manual_present` or `manual_absent`, staff
username, previous/new status, reason, and timestamp. The attendance row points
to that audit entry. Existing biometric attempts and earlier audit entries are
retained. Staff records do not claim biometric verification. Outstanding student
proofs for that student/session are cancelled when a staff decision is saved.

Automatic records use the separate `auto_absence` audit stage and `auto_absent`
result. Their attendance timestamp is the class end; their audit timestamp is
when the server processed the absence. The register and CSV identify them as
automatic, rather than biometric or teacher submissions. Pending student proofs
are ended when their absence is finalized.

Local and Full backends run an absence worker every 10 seconds and catch up on
missed processing after restart. Portal and student attendance reads also
reconcile the relevant missing absences immediately. Existing overdue classes
are included in catch-up; the rule is not limited to sessions created after the
feature was enabled. No extra database table, migration, or external scheduler
is required.

Absent records appear in student history and are excluded from attended counts.
The student self-service verification requirements remain in effect. This change
does not require a database migration or new dependencies.

After updating source files, restart the backend to load the portal:

```powershell
.\fyp-stop.ps1 -Mode Local
.\fyp-start.ps1 -Mode Local
```

For Full mode, use the existing Full checkout and omit `-Mode Local`.
The mobile history icon/color update requires rebuilding the app; the corrected
attendance counts are served by the backend immediately after restart.

## Verification

From `backend`, run the offline tests. They use an in-memory SQLite database and
never connect to your Local or Full database:

```powershell
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
```
