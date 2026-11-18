# BLE Phase 4A — bounded local scanner diagnostics

Update, 8 November 2026: the user confirmed Samsung advertising and Xiaomi
near/far/advertising-OFF observations. Standalone signed classroom verification
is described in [CLASSROOM_BLE_PHASE4B.md](CLASSROOM_BLE_PHASE4B.md). Capability
statements below record the original preparation state, not a new physical test.

Branch SH. This replaces the GPS-only Phase 4A feature. No BLE classroom policy,
backend upload or attendance enforcement is enabled. Existing device signatures,
CIDR, classroom Wi-Fi, PIN, face/liveness and duplicate checks remain unchanged.

## GPS removal and preservation

The GPS Dart service/card, Android channel, tests, guide and five output-report/
log files were removed only after verified archival. MainActivity and Network
Verification were edited surgically; no shared file was reset to HEAD. The
Wi-Fi test's asynchronous metadata-settling step is retained with generic wording
because another diagnostics card is still mounted while scrolling.

Backup: `C:\FYP\Source-Backups\ble-phase4-20261107-204758`.
It contains the pre-task source tree (468 Git-visible files), full working diff,
status inventory, hashes and all ten removed GPS files (including three ignored
logs archived separately). Verification found **457 unrelated files unchanged**.
Do not copy that entire old tree over newer work; compare intended files/hunks
first. GPS source/hooks can be reviewed in the backup without restoring them.

Existing ACCESS_FINE_LOCATION / ACCESS_COARSE_LOCATION stay for Wi-Fi and
location-related BLE research. `GPS_PROVIDER` references used solely to check
Android Location Services on older Android versions are not GPS acquisition and
were intentionally retained. No latitude/longitude measurement UI/service remains.

## Scanner architecture and permissions

The native Android `BluetoothLeScanner` is used directly, matching this project's
existing platform-channel approach. No Flutter/plugin/Play Services dependency
was added. Android minimum remains 24.

| Android | Permissions/requirements in this implementation |
|---|---|
| 24–30 | Existing precise foreground location and Location Services; legacy BLUETOOTH and BLUETOOTH_ADMIN capped at SDK 30 |
| 31+ | Runtime BLUETOOTH_SCAN and BLUETOOTH_CONNECT (Nearby Devices), existing precise location and Location Services |

CONNECT is used to read Bluetooth state and request Android's enable prompt;
the app never pairs/connects to a beacon. No ADVERTISE or background-location
permission is requested by this scanner app. BLE hardware is optional in the
manifest so unsupported devices display a clear diagnostic.

`neverForLocation` is deliberately **not** asserted: the research concerns
physical location, and that flag can filter some beacon packets. Requirements
follow [Android's Bluetooth permission guidance](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions).
Requesting permissions is explicit. Declining Nearby Devices does not trigger a
second location prompt. Denied/settings-required states guide users to app settings.

If Bluetooth is off, Enable Bluetooth opens Android's normal
`ACTION_REQUEST_ENABLE` prompt; it never calls a silent adapter-enable API. See
[Android's setup guidance](https://developer.android.com/develop/connectivity/bluetooth/setup).
The user may decline. State is Unknown when permission prevents reading it.

## Scan and displayed observations

Network Verification now includes **BLE Diagnostics**. Opening/returning checks
metadata only; it never starts scanning automatically in the background.
**Scan BLE (8 seconds)** is the explicit diagnostics action. With Bluetooth and
permissions ready, it starts the reusable scanner directly; no pairing or second
scan button is needed. A future explicit beacon-verification action can call the
same service, but no such backend decision exists yet.

- One native scan/callback at a time; overlapping requests reject with BLE_SCAN_BUSY.
- An independent native eight-second deadline, ten-second Dart timeout and
  twelve-second UI backstop prevent indefinite loading. Stop scan returns the
  partial observations already collected. Activity pause/destruction, leaving
  the screen or errors unregister the callback. Late callbacks are ignored.
- A short start cooldown and visible Android scan-error code help diagnose
  throttling. No uncontrolled retries. Wait before repeating rapid start/stop.
- Each scan starts empty; nothing is persisted or uploaded. A completed result
  is a local snapshot, not a live feed or authorization.
- Callback timestamps older than scan start, future timestamps and invalid RSSI
  are ignored. Android's boot-relative observation time supplies timestamp/age;
  see [ScanResult](https://developer.android.com/reference/android/bluetooth/le/ScanResult).
- The display includes Bluetooth/permission/service status, duration, local
  advertiser number, optional advertised name, service UUIDs, service/manufacturer
  data, last RSSI, observed sample count and median RSSI. Missing identifiers are
  labelled rather than invented.
- Maximum 40 advertisers, last 50 RSSI samples per advertiser; UUID/data payload
  lists are bounded and payload hex is truncated to 32 bytes per entry. Median is
  diagnostic only. Android's unavailable RSSI sentinel is not accepted as a sample.
- Bluetooth addresses are used only inside the native eight-second deduplication
  map. They are not sent to Dart, stored, logged or used as classroom policy.
  Other identifiers are shown locally only for the requested diagnostics.
- The age display repaints once per second; that timer never rescans and stops
  when inactive/disposed. On resume only status is refreshed, with prior scan
  results cleared.

No-advertisement COMPLETE means nothing was observed in that window, not proof
of classroom absence. Bluetooth/permission errors are distinct from an empty
scan. Static identifiers and client-reported RSSI are spoofable/relayable and
cannot prove physical presence or distance.

## Samsung SM-A346E transmitter: capability NOT YET VERIFIED

Only Xiaomi 7732690b was connected during preparation. No Samsung APK, original
Attend app, Keystore or Bluetooth setting was changed. Bluetooth/BLE support
alone does not establish that this phone/OS can successfully advertise.

Practical check using a separate advertiser app on Samsung:

1. Manually install/open [Nordic nRF Connect for Mobile](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile)
   from its official store link. Nordic's Android tool includes advertiser
   functionality; UI names can vary by version. This is a separate application,
   not an update/uninstall of Attend.
2. Allow the advertiser's required Nearby Devices/Bluetooth permissions and turn
   Bluetooth on. Open its Advertiser mode/tab and create a **legacy** advertising
   set. Do not enable extended/periodic modes for the first compatibility test.
3. Advertise only this synthetic 128-bit service UUID:
   `7d9a6c10-326a-4c60-9e01-1ef000000001`.
   It is a test marker, not an institutional identity or production policy.
4. Keep the advertising packet small: the service UUID only; omit the personal
   device name/manufacturer data. Do not overfill the legacy 31-byte packet.
   Pairing is unnecessary. Use non-connectable mode if offered.
5. Start advertising and keep the advertiser foreground/screen awake for the
   controlled test. Record actual success or any unsupported/start-error message.
   If the app exposes capabilities, successful availability of Android's LE
   advertiser and a successful start callback are useful checks; the strongest
   practical confirmation is the Xiaomi receiving the exact fresh UUID.
6. If advertising is unsupported or fails, **STOP and report that limitation**.
   Do not mark Samsung transmitter PASS from its model or Bluetooth version.
   Use another known advertising-capable test device/peripheral before proceeding.

Stop the advertiser manually after the experiment. No auto-install, beacon
advertising or phone-setting change is performed by this repository task.

## Xiaomi build and safe in-place update

The debug APK uses the existing intended isolated LAN backend URL
`http://192.168.0.162:8002`. BLE diagnostics is local and can run without FastAPI;
separate CIDR checks may report backend unavailable if the laptop cannot be reached.
Do not confuse that with BLE discovery or relax attendance rules.

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System\frontend
flutter analyze
flutter test
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.0.162:8002

$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
# User-operated Xiaomi update only; no automatic installation by this task:
& $adb -s 7732690b install -r 'C:\FYP\FYP-Biometric-Attendance-System\frontend\build\app\outputs\flutter-apk\app-debug.apk'
if ($LASTEXITCODE -ne 0) { throw 'STOP: update failed. Do not uninstall, clear app data, or regenerate keys.' }
& $adb -s 7732690b shell am start -n com.example.frontend/.MainActivity
```

If the laptop's LAN address changed, rebuild for the actual isolated backend URL;
do not change production 8000 or add a public tunnel. Never authorize USB loopback
as a campus network. No ADB reverse or backend connection is needed for BLE itself.

## Short physical test

1. Start the Samsung test UUID advertisement. On Xiaomi, open Network Verification
   → BLE Diagnostics. Allow scan permissions (Nearby Devices, then existing
   location if needed); enable Bluetooth through the system prompt and turn
   Location Services on. No pairing.
2. At 1–2 metres from the Samsung, press Scan BLE. After eight seconds, look for
   the exact UUID, record sample count, median/latest RSSI, timestamp, age and
   duration. Do not rely on the advertiser name or Bluetooth address.
3. Repeat five full windows at the classroom seat, corridor and library (or clearly
   labelled home-simulation locations), keeping transmitter position, advertising
   interval/power, scanner height/orientation and phone state consistent. Leave a
   few seconds between scans. Record no-beacon windows honestly.
4. Stop advertising on Samsung, scan again and confirm the UUID is no longer
   freshly observed. Re-enable only for the next explicit test.
5. Test Stop during a scan; Bluetooth OFF; permission denial/settings-required
   denial; Location Services OFF; app background during a scan. Expect clear
   diagnostics and cleanup, not an attendance PASS/FAIL. Restore permissions for
   the existing Wi-Fi checks afterward.

Manual note columns: location label / devices / scan time / UUID / sample count /
median RSSI / last RSSI / observation age / scan duration / status / transmitter
settings. Keep notes private; do not publish nearby-device data.

Physical scanner/transmitter/range tests are **NOT RUN** by automated Flutter
tests or a successful APK build. Prepare Phase 4B only after these results are
reviewed; see [BLE_BEACON_PHASE4B_DESIGN.md](BLE_BEACON_PHASE4B_DESIGN.md).
