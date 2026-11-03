# B3 device camera orientation fix

## Root cause and diagnostic evidence

The Pixel_Tablet AVD uses front webcam0 and reports sensor orientation 90 degrees.
The installed camera_android_camerax 0.7.2 selects ImageReaderRotatedPreview
(handlesCropAndRotation=false). On this naturally-landscape AVD its front-preview
mirror-axis correction displays the image upside down. B3 did not previously add
a RotatedBox/Transform: the incorrect transform is inside the platform preview.
The fixed 3/4 parent box was a separate landscape sizing problem.

Resetting the virtual accelerometer from reverse to natural landscape did NOT fix
the problem (confirmed by the user), and a renderer opt-out did not switch the
plugin path. Neither workaround is retained. Diagnostic tests confirmed the
preview was upside down while the captured JPEG, EXIF orientation 6, normalized
upright. Do not rotate upload bytes merely to compensate for a preview defect.

The issue matches upstream camera preview mirroring reports for naturally-landscape
ImageReader devices:
https://github.com/flutter/flutter/issues/190907
https://github.com/flutter/flutter/issues/156974
Local source inspected: camera 0.12.0+2 camera_preview.dart, and CameraX 0.7.2
rotated_preview_delegate.dart/image_reader_rotated_preview.dart.

## Fix scope

DeviceCameraPreview lets CameraPreview own its normal sensor/display rotation,
aspect ratio and mirror, and bounds preview height to avoid an oversized portrait
box in landscape. It follows CameraValue updates on rotation.

An explicit DEBUG-only build profile, B3_WEBCAM_PROFILE=Pixel_Tablet:webcam0,
permits a preview-only correction of the diagnosed wrong mirror axis. It requires
Android, native is_emulator=true (ranchu/goldfish hardware), AVD name Pixel_Tablet,
product sdk_gtablet_x86_64, front-facing camera and sensor orientation 90. The
native channel reads environment metadata only; it never accesses keys or camera
files. Without all conditions, correction is zero. Release builds and physical
phones including Samsung always retain normal behavior, even with the define.

The correction is not enabled globally and does not infer trust from model names:
metadata is used only for display compatibility. It affects only the device-owned
B3 preview, not the partner camera or backend. Wrong-axis reflection is the correct
front mirror composed with a half-turn; the correction restores upright mirrored
selfie display rather than introducing another mirror. Remove/re-evaluate this
workaround when upgrading the pinned camera plugin or changing AVD front-camera
configuration. Do not enable this profile for a different camera source.

Capture remains independent: takePicture is not orientation-locked or modified,
JPEG bytes and EXIF are uploaded unchanged, and existing backend ImageOps.exif_transpose
normalizes them before inference. No inference algorithm, biometric lifecycle,
attendance route, database schema or activation behavior changed.

## Verify on the affected emulator

The normal app is restored in-place on emulator-5554, built with this explicit
profile. The temporary camera-only diagnostic was not a biometric or attendance
test and made no backend requests. It confirmed an upright preview in landscape
and portrait after the scoped correction; captured JPEG orientation was inspected
separately. Temporary preview/capture images are removed after diagnostics.

For future rebuilds:

```powershell
Set-Location 'C:\FYP\FYP-Biometric-Attendance-System\frontend'
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug --target lib/main.dart --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=B3_WEBCAM_PROFILE=Pixel_Tablet:webcam0
$attendanceAdb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $attendanceAdb -s emulator-5554 install -r build\app\outputs\flutter-apk\app-debug.apk
& $attendanceAdb -s emulator-5554 reverse tcp:8000 tcp:8000
& $attendanceAdb -s emulator-5554 shell am start -n com.example.frontend/.MainActivity
```

Stop on install failure; never uninstall or clear app data as a workaround. The
candidate key remains in Android Keystore. A process restart requires signing in
again because the app's login token is in memory; this is not a key reset. Renew
an expired pending request using the existing candidate key, then start B3 facial
verification. Check upright face/gesture guide, both landscape directions and
portrait, and confirm the front preview behaves as a mirror. Biometric completion
must still say awaiting trusted biometric approval; Slot 2 remains inactive.

For Samsung/other physical-device builds, omit B3_WEBCAM_PROFILE. No Samsung app,
key or registration was modified during this fix.

## Tests

- Flutter portrait/landscape layouts, controller orientation changes, sensor
  orientations 0/90/270, mirror preservation and exact workaround gating.
- Original captured-byte preservation in the device upload test.
- Existing camera lifecycle, permissions, error and device API tests.
- Synthetic JPEG test covers all eight EXIF orientation/mirror values through the
  existing backend decode function. No raw biometric image fixture is stored.

## Files changed by this fix

- frontend/lib/modules/devices/screens/device_biometric_approval_screen.dart
- frontend/lib/modules/devices/widgets/device_camera_preview.dart (new)
- frontend/lib/modules/devices/services/device_camera_orientation.dart (new)
- frontend/android/app/src/main/kotlin/com/example/frontend/DeviceCameraChannel.kt (new)
- frontend/android/app/src/main/kotlin/com/example/frontend/MainActivity.kt (channel registration only)
- frontend/test/device_camera_preview_test.dart (new)
- frontend/test/device_biometric_test.dart (unchanged upload-byte assertion)
- backend/tests/test_device_frame_orientation.py (new, decode regression only)
- docs/DEVICE_CAMERA_ORIENTATION.md (new)
- docs/SECOND_DEVICE_STAGE_B3.md (guide link)

## Final verification

Flutter analysis: no issues. Full Flutter suite: 84 passed. Android debug build
and strict in-place emulator installation succeeded. Synthetic backend EXIF test
passed all eight orientation/mirror cases. Live camera-only diagnostic confirmed
upright portrait/landscape preview and independently inspected capture metadata.
Normal B3 app restored; initial emulator landscape pose restored. All generated
diagnostic JPEGs and private screenshots were removed. Samsung registration was
compared against the verified B3 backup and is exactly unchanged, ACTIVE Slot 1;
ACTIVE Slot 2 count is zero. No database writes/migrations, commits, pushes or
merges were performed for this fix.
