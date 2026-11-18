# Multiple simulation CIDRs

Use PowerShell 7 from `C:\FYP\FYP-Biometric-Attendance-System`.
`fyp-test.ps1` remains a pass-through to the existing guarded test CLI. It always
uses the disposable profile, validates the actual 127.0.0.1:3322 schema/account/
datadir, and has no production fallback. Do not use the original generic
manage_network_policy.py command for this disposable exercise: it loads .env.

The existing backend already checks **all enabled** NetworkPolicy rows. No new
policy table, service, API route or attendance authorization path was introduced.
The wrapper now exposes named-row management through the same put_policy and
NetworkPolicyEvent implementation. No schema migration or backend restart is needed.

## Commands

Your existing `fyp-simulation` row currently authorizes home simulation CIDR
`192.168.0.0/24`. Add a second policy without replacing it:

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System

# EXAMPLE second test network: replace with the actual intended simulation CIDR.
.\fyp-test.ps1 policy add --id sim-second --name 'Second test LAN' --cidr 192.168.1.0/24 --simulation
.\fyp-test.ps1 policy list

.\fyp-test.ps1 policy disable --id sim-second
.\fyp-test.ps1 policy enable --id sim-second
.\fyp-test.ps1 policy remove --id sim-second
.\fyp-test.ps1 policy list --all
```

If starting from a different database without the legacy home row, add home with
its own ID too:

```powershell
.\fyp-test.ps1 policy add --id sim-home --name 'Home simulation' --cidr 192.168.0.0/24 --simulation
```

`add` requires an ID and explicit --simulation, enables the new row and forces
the name to start with **SIMULATION ONLY -**. IDs are unique; duplicate add fails
without replacing the existing range. Use `set --id ... --cidr ... --simulation`
to deliberately change an existing simulation row. Existing commands without an
ID still target `fyp-simulation`, preserving the previous demonstration workflow.

`remove` is audited retirement: it sets enabled=false and appends a REMOVED event.
It retains the row and prior verification/audit references, rather than deleting
history or breaking foreign keys. Normal list hides retired disabled rows;
`list --all` includes them with removed=true. `enable --id ...` explicitly restores
a retired row, or `set --id ...` deliberately updates it. A retired ID cannot be
silently overwritten by add.

The test CLI rejects modifications to existing rows that lack the SIMULATION ONLY
label. It does not alter the production policy manager's .env/configuration, and
students still have no policy-write endpoint.

## Backup/restore per policy

```powershell
.\fyp-test.ps1 policy export --id sim-second --output C:\FYP\sim-second-before.json
.\fyp-test.ps1 policy restore --id sim-second --input C:\FYP\sim-second-before.json
```

The output file must not already exist. Each snapshot covers one ID, not every
policy. A snapshot from another ID is rejected. The old no-ID export/restore
commands continue to target fyp-simulation. Restoration preserves audit history;
it does not destructively remove referenced rows.

## Expected behavior and caveats

- Either enabled matching CIDR produces a fresh server network PASS. Unmatched
  sources fail. Disabled/retired rows do not authorize requests.
- Multiple matches use the existing longest-prefix rule, then network ID for ties.
- Disabling one row is not a global network ban. Another enabled overlapping
  policy may still match. In particular, disabling sim-home does not cause FAIL
  if the existing fyp-simulation still enables the same home range.
- Login/profile remain independent of attendance policy for reachable clients.
- Any invalid enabled policy fails closed under the existing service behavior.
- Client IP/SSID claims and untrusted forwarding headers remain ignored; loopback
  remains rejected. Attendance still performs its own fresh check at the insert.
- These are simulation networks, not verified university CIDRs. A second CIDR
  does not create routing or make the laptop reachable from that network. Physical
  multi-network/campus tests still require actual network reachability.
- IPv6 policies are supported by the verifier; the current LAN launcher binds
  IPv4. IPv6 source tests here use controlled ASGI peers, not a physical IPv6 LAN.

## Validation and preservation

- Fourteen workflow tests passed on SQLite and on fresh synthetic MariaDB schemas
  at port 3322. Coverage includes two simultaneous ranges, outside rejection,
  independent disable/enable, IPv6, duplicate IDs, scoped restoration, preserved
  removal audits and login/profile independence.
- Full backend regression: **276 passed, 10 skipped**, zero failures/errors
  (286 discovered). Existing attendance/device/biometric regressions remain passing.
- Actual guarded CLI add/list/duplicate rejection/disable/enable/remove passed.
  The two CLI-check rows are now retired/disabled and visible only with list --all.
  Existing policy rows (including enabled home simulation) were unchanged.
- No services were restarted and no live student/device/template/attendance data
  was changed for this task. Synthetic schemas were removed after testing.
- No production connection, key change, public tunnel, commit or push occurred.

Evidence: `outputs/multi-cidr-20261106/`. These tests use controlled source IPs;
they are not claims that two real physical Wi-Fi networks were tested.

For Windows PowerShell 5 with script execution disabled, use the same arguments
after `backend\venv\Scripts\python.exe -B backend\fyp_test.py`, for example:

```powershell
.\backend\venv\Scripts\python.exe -B backend\fyp_test.py policy list
```
