# Phase 1: connected Wi-Fi discovery

Open **Profile → Network Verification → Wi-Fi diagnostics**. Tap **Refresh** to
take a local Android snapshot. The card shows SSID, access-point BSSID, RSSI in
dBm, default connection type, Wi-Fi association, permission status, Location
services state and device sample time. This is connected-AP discovery, not a scan
of all nearby access points.

The CIDR result above remains the backend's result. No Wi-Fi field is submitted
to the backend, stored in MariaDB, or used by attendance/preflight. A readable
SSID, strong RSSI or AVAILABLE diagnostic status is **not authorization**. Denying
location permission does not disable the existing backend network check.

## Compatibility and permissions

The project has http, camera and url_launcher but no connectivity/permission
plugin. This feature uses the existing Flutter MethodChannel pattern instead of
adding a package or changing SDK/toolchain versions. Minimum Android is API 24;
the inspected APK targets/compiles API 36. Android 12/API 31+ uses a bounded
ConnectivityManager callback with FLAG_INCLUDE_LOCATION_INFO; API 24–30 uses the
read-only WifiManager connection-info fallback.

Manifest additions:

- ACCESS_NETWORK_STATE and ACCESS_WIFI_STATE: normal Android permissions for
  transport/Wi-Fi state.
- ACCESS_COARSE_LOCATION and ACCESS_FINE_LOCATION: requested together only after
  the student taps **Allow precise location**. Android 12+ approximate-only access
  is displayed separately and may leave identifiers unavailable.

Connected SSID/BSSID are location-sensitive. Android may require fine permission
and Location services enabled and may still redact fields on a particular OEM.
This is why fine permission is not limited to API 32. No background location,
GPS-coordinate request, nearby-AP scan, hotspot/P2P/RTT operation or Wi-Fi connection
change is performed. NEARBY_WIFI_DEVICES is not requested: this snapshot does not
use the connection-management APIs requiring it. No neverForLocation assertion is
made for classroom-location discovery.

Only a permission-requested boolean is retained in a separate Android preference.
SSID, BSSID and RSSI stay in the displayed snapshot, not an app file, log, database
or HTTP payload. Any manually saved screenshots/notes are your own local records.

Behavior:

- First opening reads status without an automatic permission dialog.
- Denied/approximate access: readable guidance and an explicit permission action.
- Settings-required denial: **Open app permissions**, then refresh on returning.
- Location off: **Open Location settings**; the app does not enable it silently.
- Wi-Fi off: **Open Wi-Fi settings**; mobile data/offline remains a separate
  default transport value.
- Unknown SSID and placeholder BSSIDs such as 02:00:00:00:00:00 are shown as
  unavailable/redacted; invalid RSSI is not converted into a signal reading.
- VPN/default mobile transport can coexist with a Wi-Fi association. The card
  does not infer which network carried a particular attendance request.
- Native callbacks unregister after completion or a bounded 1.8-second wait.
  Flutter also bounds snapshot waiting at five seconds. No continuous/background
  listener is kept. Background/resume and refresh discard old in-flight readings.
- Refresh asks Android for its latest available observation; it does not force
  a scan or guarantee a new RF measurement. Repeated RSSI values can be OS caching.

References:
[Android Wi-Fi permissions](https://developer.android.com/develop/connectivity/wifi/wifi-permissions),
[location-aware callbacks](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback#FLAG_INCLUDE_LOCATION_INFO),
[WifiInfo redaction](https://developer.android.com/reference/android/net/wifi/WifiInfo).

## Safe build and launch on a real device

No physical installation was performed during implementation. New native code and
permissions need a full APK update; hot reload alone is insufficient.

Use the laptop's current LAN URL. The observed address is 192.168.0.162; it may
change at university. Local diagnostics can refresh without backend connectivity
once the signed-in screen is open, but login/navigation after app restart can
still require the backend. Do not publish a tunnel just to collect Wi-Fi samples.

Because these installations contain protected Keystore keys, use an explicit
**adb install -r** update. The installed Flutter tool's Android install routine
can uninstall and retry after an installation failure, which is inappropriate
for a protected installation. Do not use automatic reinstall recovery. Android's
normal -r signature/version failure must be treated as a stop condition.

PowerShell 7:

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System\frontend
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.0.162:8002

$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l

# Confirm the actual serial/model before choosing a target:
$testDevice = '7732690b'  # Xiaomi tablet, previously model 2410CRP4CG
& $adb -s $testDevice shell getprop ro.product.model

# Only after approving an in-place update of this target:
& $adb -s $testDevice install -r 'build\app\outputs\flutter-apk\app-debug.apk'
if ($LASTEXITCODE -ne 0) { throw 'STOP: keep the existing app/data/keys; do not uninstall or force downgrade.' }
& $adb -s $testDevice shell am start -n com.example.frontend/.MainActivity

# Optional Flutter debugging of the safely updated, already launched app:
flutter attach -d $testDevice
```

For Samsung SM-A346E, its previously observed serial was **RFCW30BZKAZ**. Confirm
it with adb devices/model first. Only after explicit approval to update that
protected installation, repeat the same sequence with that serial. Never omit
the device selector, uninstall/clear data, force a downgrade, rotate the signing
key, register/replace a device, or regenerate a Keystore alias for this feature.
If signatures/version do not match, stop and review the build; the original app
and keys must remain. Application ID, key alias implementation and signing setup
were not changed by this feature.

In Android Studio attach the Flutter debugger to the already launched app rather
than accepting an uninstall/reinstall suggestion. Use FYPTEST001 and the existing
disposable 8002 environment for testing; do not enroll/change DEMO001 or production.

## Collection protocol: Samsung and Xiaomi

1. Update only the approved device in place. Log in while the backend is reachable,
   then open Network Verification and scroll to Wi-Fi diagnostics.
2. Tap Allow precise location, select **Precise** and **While using the app** (or
   Only this time). Turn on Android Location services if necessary. Permission is
   optional for attendance; decline if you do not want to collect these identifiers.
3. Join the same intended campus SSID on both devices. Record device model,
   Android version, permission/Location state, and whether VPN/mobile data is active.
4. At the classroom seat/center, remain stationary for 15–30 seconds. Hold each
   device in the same orientation/height, then collect **five Refresh readings,
   about five seconds apart**. Wait for each reading to complete.
5. Repeat in the corridor outside the room and at a distinct campus location.
   Keep the relative position/orientation consistent. Record AP roaming rather
   than assuming the same SSID means the same AP.
6. For every reading, record location label, device, sample time, default transport,
   SSID, BSSID and RSSI. If redacted/unavailable, record that fact and permission/
   Location state; do not invent a value or force-grant permissions using ADB.
7. Compare readings **per device and per BSSID**. Use the median and range of the
   five RSSI samples. A less-negative number is stronger; do not convert RSSI to
   meters or assume the phone/tablet share a calibration.

Suggested manual note columns:

| Location | Device / Android | Sample time | Default transport | SSID | BSSID | RSSI dBm | Permission / Location | Notes |
|---|---|---|---|---|---|---|---|---|
| Classroom seat | | | | | | | | |
| Corridor | | | | | | | | |
| Other campus location | | | | | | | | |

Keep actual campus identifiers/room mappings in private notes, outside Git.
Screenshots should show only the diagnostic panel, not faces or authentication
tokens. Collection is manual; this feature does not save a location history.

## Negative checks

- Deny location: permission state visible, identifiers unavailable, existing CIDR
  check still works normally.
- Select approximate-only on Android 12+: show APPROXIMATE ONLY, not precise.
- Disable Location services: show off/unavailable, then recover after returning.
- Disable Wi-Fi and use mobile data (Samsung) or offline mode (Wi-Fi-only tablet):
  show the actual default transport, with no stale SSID/BSSID/RSSI.
- Return from Android Settings or move/roam between APs: Refresh must replace the
  old reading and update its sample time. Network and Wi-Fi Refresh are independent.
- A strong/readable Wi-Fi result must never turn a backend CIDR FAIL into PASS.

## Limits and validation status

SSID can be shared or spoofed. BSSID identifies an AP radio, not a trusted student
device; the same AP may cover a room and corridor. RSSI varies with hardware,
orientation, people, obstacles and caching. These observations do not establish
the correct classroom or defeat spoofing. Classroom authorization design remains
future work; existing final attendance security is unchanged.

Automated Flutter tests cover channel values, redaction, permission states,
location/Wi-Fi off, mobile transport, timeout/retry/disposal/resume, portrait and
landscape, and independence from backend PASS/FAIL. The Android debug APK builds.
Real Samsung/Xiaomi permission/OEM readings and campus collection are **NOT RUN**
until an approved in-place update and manual tests occur. No classroom-success
result or supervisor physical PASS is inferred from mocks/build success.
