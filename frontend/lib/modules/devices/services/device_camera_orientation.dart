import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Explicit, preview-only workaround for the diagnosed CameraX ImageReader
/// front-mirror bug on this AVD. Never applied to captures or physical devices.
class DeviceCameraOrientation {
  static const profile = String.fromEnvironment('B3_WEBCAM_PROFILE');
  static const channel = MethodChannel('attendance/device_camera');

  static int correction({
    required String profile,
    required bool debug,
    required TargetPlatform platform,
    required CameraDescription camera,
    required Map<dynamic, dynamic> environment,
  }) {
    if (debug &&
        platform == TargetPlatform.android &&
        profile == 'Pixel_Tablet:webcam0' &&
        environment['is_emulator'] == true &&
        environment['avd_name'] == 'Pixel_Tablet' &&
        environment['product'] == 'sdk_gtablet_x86_64' &&
        camera.lensDirection == CameraLensDirection.front &&
        camera.sensorOrientation == 90) {
      // Correct the wrong mirror axis observed with camera_android_camerax 0.7.2
      // ImageReader. Equivalent to the correct front mirror, not a frame rotation.
      return 2;
    }
    return 0;
  }

  static Future<int> previewCorrection(CameraDescription camera) async {
    if (!kDebugMode ||
        defaultTargetPlatform != TargetPlatform.android ||
        profile.isEmpty) {
      return 0;
    }
    try {
      final environment = await channel.invokeMapMethod<dynamic, dynamic>(
        'getEnvironment',
      );
      return correction(
        profile: profile,
        debug: kDebugMode,
        platform: defaultTargetPlatform,
        camera: camera,
        environment: environment ?? {},
      );
    } on PlatformException {
      return 0;
    } on MissingPluginException {
      return 0;
    }
  }
}
