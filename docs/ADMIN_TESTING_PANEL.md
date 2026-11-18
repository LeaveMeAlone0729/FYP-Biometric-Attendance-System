# Local admin panel

For the new admin/teacher workspace, open **http://127.0.0.1:8000/** and see
[Staff portal](STAFF_PORTAL.md). It includes manual Present/Absent recording and
all four sections below in the new UI with one staff login.
The separate port-8003 policy panel described below keeps its existing scope.

The panel manages attendance sessions, PINs and network/classroom policies.
It runs only on the laptop at **http://127.0.0.1:8003/login**. Keep its listener
private; the phone uses the student API instead.

## Your Laragon / Local setup

```powershell
.\fyp-start.ps1 -Mode Local
```

Use the administrator credentials created for your Local profile. Student
credentials cannot sign in here, and there is no default admin password.
For first-time initialization, follow [Local setup](PARTNER_LOCAL_MODE.md).
The [Full workflow](FYP_THREE_COMMANDS.md) uses its own pinned profile.

## Create a class PIN

1. Sign in and open **Attendance Sessions**.
2. Choose an existing course, student group when required, and duration.
3. Select a classroom only if its configured Wi-Fi check should be required.
4. Create the session. The result shows its six-digit PIN with **Copy PIN**.
5. Enter that PIN in the student app and complete normal device/network and face checks.

A PIN is displayed after creation or regeneration; the session table does not
reveal saved PINs. Regenerating invalidates the old PIN for new submissions.
Closing a session preserves attendance and verification history. Create a new
session to repeat a completed attendance flow. The panel creates sessions,
not attendance records or device approvals.

## Other pages

- **Network Policies:** manage the intended source CIDRs through existing
  validation and audit services. Localhost is not attendance network proof.
- **Classroom Wi-Fi:** manage classrooms/AP policies and explicitly assign
  classroom requirements to sessions.
- **Experimental BLE:** manage standalone beacon policies. BLE remains experimental
  and is not enforced by attendance.

Policy changes affect verification immediately. The panel does not edit student
faces, keys, device approval grants or attendance records, and never migrates a
schema automatically.

## Credentials and troubleshooting

Private `panel-admin.json` stores a salted password hash, never the plaintext
password. Initialization refuses to overwrite an existing file. Sessions expire
after 30 minutes and are cleared on restart. POST actions require the matching
origin and CSRF token. Use `127.0.0.1` consistently; reload stale forms.

`ADMIN_PORT_IDENTITY_CONFLICT` means port 8003 belongs to another profile or
unrecognized process. Stop that service through its original launcher or terminal,
then start the intended mode. Do not kill unrelated processes or delete ownership
state to bypass the check. Missing schema/identity errors require checking the
configured database, not disabling guards.

For a separate disposable environment, use [MySQL setup](MYSQL_TESTING.md).
Existing isolated MariaDB users can still run `.\scripts\fyp-test.ps1 start`
and initialize/start its panel with `.\scripts\start-admin-testing.ps1`.
These optional tools are separate from your Laragon Local profile.
