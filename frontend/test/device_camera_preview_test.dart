import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/devices/widgets/device_camera_preview.dart';
import 'package:frontend/modules/devices/services/device_camera_orientation.dart';

class PreviewCamera extends CameraController {
  PreviewCamera(int sensor)
    : super(
        CameraDescription(
          name: 'front-test',
          lensDirection: CameraLensDirection.front,
          sensorOrientation: sensor,
        ),
        ResolutionPreset.high,
        enableAudio: false,
      );
  void orient(DeviceOrientation orientation) {
    value = value.copyWith(
      isInitialized: true,
      previewSize: const Size(1280, 720),
      deviceOrientation: orientation,
    );
  }

  @override
  Widget buildPreview() => Transform.scale(
    scaleX: -1,
    key: const ValueKey('platform-front-mirror'),
    child: const ColoredBox(
      key: ValueKey('front-platform-preview'),
      color: Colors.black,
    ),
  );
}

void main() {
  for (final sensor in [0, 90, 270]) {
    for (final landscape in [false, true]) {
      testWidgets(
        'Sensor $sensor ${landscape ? 'landscape' : 'portrait'} delegates rotation and preserves mirror',
        (tester) async {
          tester.view.physicalSize = landscape
              ? const Size(1024, 600)
              : const Size(360, 640);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          final camera = PreviewCamera(sensor)
            ..orient(
              landscape
                  ? DeviceOrientation.landscapeLeft
                  : DeviceOrientation.portraitUp,
            );
          addTearDown(camera.dispose);
          await tester.pumpWidget(
            MaterialApp(
              home: Scaffold(body: DeviceCameraPreview(controller: camera)),
            ),
          );
          await tester.pump();
          expect(tester.takeException(), isNull);
          expect(find.byType(CameraPreview), findsOneWidget);
          expect(find.byType(RotatedBox), findsOneWidget);
          expect(
            tester.widget<RotatedBox>(find.byType(RotatedBox)).quarterTurns,
            landscape ? 3 : 0,
          );
          expect(
            tester.widget<AspectRatio>(find.byType(AspectRatio)).aspectRatio,
            landscape ? 1280 / 720 : 720 / 1280,
          );
          final size = tester.getSize(find.byType(CameraPreview));
          expect(
            size.height,
            lessThanOrEqualTo((landscape ? 600 : 640) * 0.55 + 0.01),
          );
          expect(
            size.width / size.height,
            closeTo(landscape ? 1280 / 720 : 720 / 1280, 0.001),
          );
          // Only the platform-owned front mirror remains; the app adds no flip.
          expect(
            find.byKey(const ValueKey('platform-front-mirror')),
            findsOneWidget,
          );
          expect(
            tester
                .widget<Transform>(
                  find.byKey(const ValueKey('platform-front-mirror')),
                )
                .transform
                .entry(0, 0),
            -1,
          );
          expect(camera.value.lockedCaptureOrientation, isNull);
          await tester.pumpWidget(const SizedBox());
          await tester.pump();
        },
        variant: TargetPlatformVariant.only(TargetPlatform.android),
      );
    }
  }
  test(
    'Workaround requires opt-in debug Android plus exact AVD, front sensor and emulator',
    () {
      const front = CameraDescription(
        name: '1',
        lensDirection: CameraLensDirection.front,
        sensorOrientation: 90,
      );
      const environment = {
        'is_emulator': true,
        'avd_name': 'Pixel_Tablet',
        'product': 'sdk_gtablet_x86_64',
      };
      int correction({
        String profile = 'Pixel_Tablet:webcam0',
        bool debug = true,
        TargetPlatform platform = TargetPlatform.android,
        CameraDescription camera = front,
        Map<dynamic, dynamic> metadata = environment,
      }) => DeviceCameraOrientation.correction(
        profile: profile,
        debug: debug,
        platform: platform,
        camera: camera,
        environment: metadata,
      );
      expect(correction(), 2);
      expect(correction(profile: ''), 0);
      expect(correction(debug: false), 0);
      expect(correction(platform: TargetPlatform.iOS), 0);
      expect(correction(metadata: {...environment, 'is_emulator': false}), 0);
      expect(
        correction(metadata: {...environment, 'avd_name': 'Another_AVD'}),
        0,
      );
      expect(correction(metadata: {...environment, 'product': 'a34x'}), 0);
      expect(
        correction(
          camera: const CameraDescription(
            name: '0',
            lensDirection: CameraLensDirection.back,
            sensorOrientation: 90,
          ),
        ),
        0,
      );
      expect(
        correction(
          camera: const CameraDescription(
            name: '1',
            lensDirection: CameraLensDirection.front,
            sensorOrientation: 270,
          ),
        ),
        0,
      );
    },
  );
  testWidgets(
    'Explicit profile correction rotates only the preview and keeps capture unlocked',
    (tester) async {
      final camera = PreviewCamera(90)..orient(DeviceOrientation.landscapeLeft);
      addTearDown(camera.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DeviceCameraPreview(
              controller: camera,
              previewQuarterTurns: 2,
            ),
          ),
        ),
      );
      expect(find.byType(RotatedBox), findsNWidgets(2));
      expect(
        tester
            .widgetList<RotatedBox>(find.byType(RotatedBox))
            .map((w) => w.quarterTurns),
        [2, 3],
      );
      expect(camera.value.lockedCaptureOrientation, isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump();
    },
    variant: TargetPlatformVariant.only(TargetPlatform.android),
  );
  testWidgets(
    'Preview tracks both landscape directions and upside-down portrait without custom correction',
    (tester) async {
      final camera = PreviewCamera(90)..orient(DeviceOrientation.portraitUp);
      addTearDown(camera.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: DeviceCameraPreview(controller: camera)),
        ),
      );
      for (final orientation in [
        DeviceOrientation.landscapeLeft,
        DeviceOrientation.landscapeRight,
        DeviceOrientation.portraitDown,
        DeviceOrientation.portraitUp,
      ]) {
        camera.orient(orientation);
        await tester.pump();
        final turns = {
          DeviceOrientation.landscapeLeft: 3,
          DeviceOrientation.landscapeRight: 1,
          DeviceOrientation.portraitDown: 2,
          DeviceOrientation.portraitUp: 0,
        };
        expect(
          tester.widget<RotatedBox>(find.byType(RotatedBox)).quarterTurns,
          turns[orientation],
        );
        expect(tester.takeException(), isNull);
      }
      await tester.pumpWidget(const SizedBox());
      await tester.pump();
    },
    variant: TargetPlatformVariant.only(TargetPlatform.android),
  );
}
