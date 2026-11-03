import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/devices/widgets/device_biometric_feedback.dart';

void main() {
  for (final size in [
    const Size(390, 844),
    const Size(844, 390),
    const Size(777, 1164),
    const Size(1164, 777),
  ]) {
    for (final liveness in [false, true]) {
      testWidgets('Device feedback fits $size, liveness=$liveness', (
        tester,
      ) async {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ListView(
                children: [
                  SizedBox(
                    height: size.height * .55,
                    child: DeviceBiometricGuide(
                      feedback: DeviceGuideFeedback.confirmed,
                      liveness: liveness,
                      acceptedFrames: liveness ? 1 : 0,
                    ),
                  ),
                  const DeviceLivenessPanel(
                    fingers: 1,
                    acceptedFrames: 1,
                    requiredFrames: 3,
                  ),
                ],
              ),
            ),
          ),
        );
        expect(find.text('Show 1 finger'), findsOneWidget);
        expect(find.text('1/3 consecutive checks accepted'), findsOneWidget);
        expect(
          find.textContaining('Neither needs to be centered'),
          findsOneWidget,
        );
        final guide = tester.getRect(
          find.byKey(
            ValueKey(liveness ? 'device-liveness-guide' : 'device-face-guide'),
          ),
        );
        expect(guide.width, lessThanOrEqualTo(size.width));
        expect(guide.height, lessThanOrEqualTo(size.height * .55));
        expect(tester.takeException(), isNull);
      });
    }
  }
}
